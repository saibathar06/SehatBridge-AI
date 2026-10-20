import base64
import io
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest
from PIL import Image
from pypdf import PdfWriter, PdfReader
from sqlalchemy import select
from pydantic import ValidationError
from fastapi import HTTPException
from app.db import SessionLocal
from app.models import User, OTP, Refresh, Document, Page, Analysis, Treatment, Medicine, Schedule, Dose, DoseEvent, Device, Preferences, Delivery, now
from app.security import put, read, seal, unseal, hasher, digest, limiter
from app.schemas import Extraction, ScheduleInput
from app.worker import process_one, combine_batches
from app.gemini_service import gemini
from app.scheduling import local_instants, quiet_at
from app.notifications import deliver_due
from app.config import settings


def png(color='white'):
    output = io.BytesIO()
    Image.new('RGB', (200, 300), color).save(output, 'PNG')
    return output.getvalue()


def upload(client, headers, files=None):
    result = client.post('/api/v1/documents', headers=headers,
        files=files or [('files', ('page.png', png(), 'image/png'))], data={'document_type': 'prescription', 'ai_consent': 'true'})
    assert result.status_code == 201, result.text
    return result.json()


def reviewed(client, headers, extraction, monkeypatch):
    monkeypatch.setattr(gemini, 'extract', lambda pages: Extraction.model_validate(extraction))
    d = upload(client, headers)
    assert process_one()
    a = client.get(f'/api/v1/documents/{d["id"]}/analysis', headers=headers)
    assert a.status_code == 200, a.text
    return d, a.json()


def schedule():
    today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
    return {'medicine_index': 0, 'times': ['23:59'], 'timezone': 'Asia/Kolkata', 'start_date': today.isoformat(),
            'end_date': (today + timedelta(days=3)).isoformat(), 'timing_confirmed': True}


def confirmed(client, headers, extraction, monkeypatch):
    d, a = reviewed(client, headers, extraction, monkeypatch)
    result = client.post(f'/api/v1/documents/{d["id"]}/confirm', headers=headers,
                         json={'revision': a['revision'], 'confirmed': True, 'schedules': [schedule()]})
    assert result.status_code == 201, result.text
    return d, result.json()


def test_registration_hashes_and_rotation(client, patient):
    h, tokens, _ = patient()
    with SessionLocal() as db:
        user = db.scalar(select(User))
        assert user.password.startswith('$argon2id$')
        assert 'example' not in user.email
        assert hasher.verify(user.password, 'SyntheticPassword123!')
        refresh = db.scalar(select(Refresh))
        assert tokens['refresh_token'] not in refresh.data
        assert db.scalar(select(OTP)).used
    new = client.post('/api/v1/auth/refresh', json={'refresh_token': tokens['refresh_token']})
    assert new.status_code == 200
    assert new.json()['refresh_token'] != tokens['refresh_token']
    assert client.post('/api/v1/auth/refresh', json={'refresh_token': tokens['refresh_token']}).status_code == 401
    assert client.get('/api/v1/profile', headers=h).status_code == 401


def test_login_logout_and_password(client, patient):
    h, _, _ = patient()
    assert client.post('/api/v1/auth/login', json={'email': 'patient@example.test', 'password': 'WrongPassword123!'}).status_code == 401
    login = client.post('/api/v1/auth/login', json={'email': 'patient@example.test', 'password': 'SyntheticPassword123!'})
    assert login.status_code == 200
    assert client.post('/api/v1/auth/logout', headers=h).status_code == 200
    assert client.get('/api/v1/profile', headers=h).status_code == 401


def test_otp_single_use_attempts_and_cooldown(client, patient):
    h, _, codes = patient()
    assert client.post('/api/v1/auth/otp/verify', json={'email': 'patient@example.test', 'code': codes['patient@example.test']}).status_code == 400
    assert client.post('/api/v1/auth/otp/request', json={'email': 'patient@example.test'}).status_code == 429


def test_reset_revokes_tokens(client, patient):
    h, _, codes = patient()
    client.post('/api/v1/auth/otp/request', json={'email': 'patient@example.test', 'purpose': 'reset'})
    result = client.post('/api/v1/auth/otp/verify', json={'email': 'patient@example.test', 'purpose': 'reset', 'code': codes['patient@example.test'], 'new_password': 'NewSyntheticPass123!'})
    assert result.status_code == 200, result.text
    assert client.get('/api/v1/profile', headers=h).status_code == 401


def test_ownership_and_private_pages(client, patient):
    h1, _, _ = patient('one@example.test'); h2, _, _ = patient('two@example.test')
    doc = upload(client, h1)
    assert client.get(f'/api/v1/documents/{doc["id"]}', headers=h2).status_code == 404
    assert client.get(f'/api/v1/documents/{doc["id"]}/pages/{doc["pages"][0]["id"]}', headers=h2).status_code == 404
    assert client.get('/api/v1/documents').status_code == 401
    assert client.get('/api/v1/documents', headers=h2).json() == []
    page = client.get(f'/api/v1/documents/{doc["id"]}/pages/{doc["pages"][0]["id"]}', headers=h1)
    assert page.status_code == 200
    assert page.headers['cache-control'] == 'no-store'


def test_multi_image_order_is_selection_not_filename(client, patient):
    h, _, _ = patient()
    d = upload(client, h, [('files', ('z.png', png('red'), 'image/png')), ('files', ('a.png', png('blue'), 'image/png'))])
    assert [p['position'] for p in d['pages']] == [1, 2]
    data = client.get(f'/api/v1/documents/{d["id"]}/pages/{d["pages"][0]["id"]}', headers=h).content
    assert Image.open(io.BytesIO(data)).getpixel((10, 10))[0] > 200


def test_pdf_all_pages_and_private_preview(client, patient, monkeypatch, extraction):
    h, _, _ = patient(); writer = PdfWriter(); writer.add_blank_page(width=200, height=300); writer.add_blank_page(width=500, height=600)
    raw = io.BytesIO(); writer.write(raw)
    d = upload(client, h, [('files', ('summary.pdf', raw.getvalue(), 'application/pdf'))])
    assert len(d['pages']) == 2
    received = []
    monkeypatch.setattr(gemini, 'extract', lambda pages: (received.extend(pages) or Extraction.model_validate(extraction)))
    assert process_one()
    assert [p[0] for p in received] == [1, 2]
    assert len(PdfReader(io.BytesIO(received[1][1])).pages) == 1
    result = client.get(f'/api/v1/documents/{d["id"]}/pages/{d["pages"][0]["id"]}?preview=true', headers=h)
    assert result.status_code == 200 and result.headers['content-type'] == 'image/png'


@pytest.mark.parametrize('raw', [b'not an image', b'%PDF-broken', b'<script>attack</script>', b'\x89PNG\r\n\x1a\nbroken'])
def test_invalid_upload_rejected(client, patient, raw):
    h, _, _ = patient()
    result = client.post('/api/v1/documents', headers=h, files=[('files', ('../bad.png', raw, 'image/png'))], data={'document_type': 'prescription', 'ai_consent': 'true'})
    assert result.status_code == 422
    assert client.get('/api/v1/documents', headers=h).json() == []


def test_extraction_missing_critical_fields(extraction):
    extraction['medicines'][0]['dose'] = None
    ex = Extraction.model_validate(extraction).validate_sources(1)
    assert ex.medicines[0].clarification_required
    assert ex.medicines[0].dose is None
    assert not ex.medicines[0].scheduled_times
    extraction['medicines'][0]['source']['page'] = 2
    with pytest.raises(ValueError):
        Extraction.model_validate(extraction).validate_sources(1)


def test_schema_rejects_unknown_and_invalid_times(extraction):
    with pytest.raises(ValidationError):
        Extraction.model_validate({**extraction, 'diagnosis_guess': 'invalid'})
    extraction['medicines'][0]['scheduled_times'] = ['25:30']
    with pytest.raises(ValidationError):
        Extraction.model_validate(extraction)


def test_batch_conflicts_are_flagged(extraction):
    ex = Extraction.model_validate(extraction)
    merged = combine_batches([ex, ex], 2)
    assert all(m.clarification_required for m in merged.medicines)


def test_confirm_requires_explicit_review(client, patient, extraction, monkeypatch):
    h, _, _ = patient(); d, a = reviewed(client, h, extraction, monkeypatch)
    with SessionLocal() as db:
        assert not db.scalar(select(Treatment)) and not db.scalar(select(Schedule))
    url = f'/api/v1/documents/{d["id"]}/confirm'
    assert client.post(url, headers=h, json={'revision': 1, 'confirmed': False}).status_code == 409
    assert client.post(url, headers=h, json={'revision': 10, 'confirmed': True}).status_code == 409
    assert client.post(url, headers=h, json={'revision': 1, 'confirmed': True, 'schedules': [schedule()]}).status_code == 201
    assert client.post(url, headers=h, json={'revision': 1, 'confirmed': True}).status_code == 409


def test_ambiguous_medicine_cannot_schedule(client, patient, extraction, monkeypatch):
    h, _, _ = patient(); extraction['medicines'][0]['confidence'] = 'low'
    d, a = reviewed(client, h, extraction, monkeypatch)
    assert client.post(f'/api/v1/documents/{d["id"]}/confirm', headers=h,
        json={'revision': 1, 'confirmed': True, 'schedules': [schedule()]}).status_code == 422


def test_reconcile_preserves_history_cancels_future(client, patient, extraction, monkeypatch):
    h, _, _ = patient(); _, t = confirmed(client, h, extraction, monkeypatch)
    with SessionLocal() as db:
        old_ids = [d.id for d in db.scalars(select(Dose))]
    result = client.put(f'/api/v1/treatments/{t["id"]}/schedules', headers=h,
                        json={'revision': 1, 'confirmed': True, 'schedules': [{**schedule(), 'times': ['23:58']}]})
    assert result.status_code == 200, result.text
    with SessionLocal() as db:
        assert all(db.get(Dose, i).status == 'cancelled' for i in old_ids)
        assert len(db.scalars(select(Schedule).where(Schedule.active.is_(True))).all()) == 1


def test_duplicate_dose_events_and_corrections(client, patient, extraction, monkeypatch):
    h, _, _ = patient(); confirmed(client, h, extraction, monkeypatch)
    with SessionLocal() as db:
        dose = db.scalar(select(Dose)); dose.due_at = int(now()) - 60; db.commit(); dose_id = dose.id
    url = f'/api/v1/doses/{dose_id}/events'
    payload = {'status': 'taken', 'expected_status': 'upcoming', 'idempotency_key': 'synthetic-event-key-0001'}
    assert client.post(url, headers=h, json=payload).status_code == 200
    assert client.post(url, headers=h, json=payload).json()['duplicate']
    assert client.post(url, headers=h, json={**payload, 'status': 'skipped', 'idempotency_key': 'synthetic-event-key-0002'}).status_code == 409
    assert client.post(url, headers=h, json={**payload, 'status': 'skipped', 'expected_status': 'taken', 'idempotency_key': 'synthetic-event-key-0002'}).status_code == 200
    assert len(client.get(url, headers=h).json()) == 2


def test_timezone_dst_and_quiet_hours():
    from datetime import date
    assert local_instants(date(2026, 3, 8), '02:30', ZoneInfo('America/New_York')) is None
    t = local_instants(date(2026, 10, 18), '08:00', ZoneInfo('Asia/Kolkata'))
    assert datetime.fromtimestamp(t, timezone.utc).hour == 2
    assert quiet_at(t, {'quiet_start': '22:00', 'quiet_end': '09:00'}, 'Asia/Kolkata')
    assert not quiet_at(t, {'quiet_start': '09:00', 'quiet_end': '12:00'}, 'Asia/Kolkata')


def test_slot_conflicts_and_cancel(client, patient):
    h1, _, _ = patient('one@example.test'); h2, _, _ = patient('two@example.test')
    provider = client.get('/api/v1/demo/providers?kind=doctor', headers=h1).json()[0]
    slot = client.get(f'/api/v1/demo/providers/{provider["id"]}/slots', headers=h1).json()[0]
    b = client.post('/api/v1/demo/bookings', headers=h1, json={'slot_id': slot['id']})
    assert b.status_code == 201
    assert client.post('/api/v1/demo/bookings', headers=h2, json={'slot_id': slot['id']}).status_code == 409
    assert client.delete(f'/api/v1/demo/bookings/{b.json()["id"]}', headers=h2).status_code == 404
    assert client.delete(f'/api/v1/demo/bookings/{b.json()["id"]}', headers=h1).status_code == 200
    assert client.post('/api/v1/demo/bookings', headers=h2, json={'slot_id': slot['id']}).status_code == 201


def test_encryption_tamper_and_owner_binding():
    value = seal({'medical': 'synthetic'}, 'owner:a')
    assert 'synthetic' not in value
    assert unseal(value, 'owner:a')['medical'] == 'synthetic'
    with pytest.raises(Exception):
        unseal(value, 'owner:b')
    with pytest.raises(Exception):
        unseal(value[:-8] + 'AAAAAAAA', 'owner:a')


def test_rate_limiting():
    limiter.check('test-destination', 1)
    with pytest.raises(HTTPException) as error:
        limiter.check('test-destination', 1)
    assert error.value.status_code == 429


def test_grounded_hindi_compound_question_without_gemini(client, patient, extraction, monkeypatch):
    h1, _, _ = patient('one@example.test'); h2, _, _ = patient('two@example.test')
    confirmed(client, h1, extraction, monkeypatch)
    monkeypatch.setattr(gemini, 'explain', lambda *a: pytest.fail('Routine question must not call Gemini'))
    question = {'question': 'मुझे आज कौन-कौन सी दवाई लेनी है और मेरा नेक्स्ट टेस्ट कब होगा?', 'language': 'hi'}
    one = client.post('/api/v1/chat', headers=h1, json=question)
    assert one.status_code == 200, one.text
    assert 'SYNTHETIC MEDICINE A' in one.json()['answer'] and '2099-01-01' in one.json()['answer']
    assert one.json()['route'] == 'structured_records'
    two = client.post('/api/v1/chat', headers=h2, json=question)
    assert 'SYNTHETIC' not in two.json()['answer']


def test_ai_missing_key_fails_honestly(client, patient):
    h, _, _ = patient(); d = upload(client, h)
    assert process_one()
    result = client.get('/api/v1/documents/' + d['id'], headers=h).json()
    assert result['status'] == 'error' and 'GEMINI' in result['error']
    assert client.get(f'/api/v1/documents/{d["id"]}/analysis', headers=h).status_code == 409


@pytest.mark.parametrize('code', [429, 504])
def test_quota_timeout_saved_as_recoverable_error(client, patient, monkeypatch, code):
    h, _, _ = patient(); d = upload(client, h)
    def fail(pages):
        raise HTTPException(code, 'AI quota exceeded' if code == 429 else 'AI request timed out')
    monkeypatch.setattr(gemini, 'extract', fail)
    process_one()
    result = client.get('/api/v1/documents/' + d['id'], headers=h).json()
    assert result['status'] == 'error'
    assert client.post(f'/api/v1/documents/{d["id"]}/retry', headers=h).status_code == 200


def test_medicine_safety_fails_closed(client, patient):
    h, _, _ = patient()
    result = client.post('/api/v1/chat', headers=h, json={'question': 'What are the side effects?', 'language': 'en'})
    assert result.status_code == 200 and 'No verified drug-information source' in result.json()['answer']


def test_notification_failure_recorded_without_medical_data(client, patient, extraction, monkeypatch):
    h, _, _ = patient(); confirmed(client, h, extraction, monkeypatch)
    monkeypatch.setattr(settings(), 'firebase_credentials', 'test-only')
    from app import notifications
    monkeypatch.setattr(notifications, 'send_fcm', lambda *a: (_ for _ in ()).throw(RuntimeError('provider failure with sensitive text')))
    with SessionLocal() as db:
        pref = db.scalar(select(Preferences)); put(pref, {'enabled': True, 'remote_enabled': True, 'quiet_start': None, 'quiet_end': None})
        device = put(Device(user_id=pref.user_id, token_hash=digest('testtoken')), {'token': 'testtoken', 'device_name': 'Test'})
        db.add(device); dose = db.scalar(select(Dose)); dose.due_at = int(now()) - 10; db.commit()
        deliver_due(db)
        delivery = db.scalar(select(Delivery))
        assert delivery.status == 'failed'
        assert read(delivery)['error'] == 'provider_delivery_failed'
        deliver_due(db)
        assert len(db.scalars(select(Delivery)).all()) == 1


@pytest.mark.parametrize('frequency,times', [('weekly', ['08:00']), ('as needed', ['08:00']), ('twice daily', ['08:00'])])
def test_unsupported_or_mismatched_frequencies_block_daily_conversion(client, patient, extraction, monkeypatch, frequency, times):
    h, _, _ = patient(); extraction['medicines'][0]['frequency'] = frequency
    d, _ = reviewed(client, h, extraction, monkeypatch)
    result = client.post(f'/api/v1/documents/{d["id"]}/confirm', headers=h,
        json={'revision': 1, 'confirmed': True, 'schedules': [{**schedule(), 'times': times}]})
    assert result.status_code == 422


def test_foreign_confirmed_document_cannot_ground_chat(client, patient, extraction, monkeypatch):
    h1, _, _ = patient('one@example.test'); h2, _, _ = patient('two@example.test')
    d, t = confirmed(client, h1, extraction, monkeypatch)
    assert client.get(f'/api/v1/treatments/{t["id"]}', headers=h2).status_code == 404
    result = client.post('/api/v1/chat', headers=h2, json={'question': 'Explain this report', 'document_id': d['id']})
    assert result.status_code == 404


def test_chat_history_is_opt_in_and_turning_off_deletes(client, patient):
    h, _, _ = patient()
    question = {'question': 'Which medicines today?', 'language': 'en'}
    client.post('/api/v1/chat', headers=h, json=question)
    assert client.get('/api/v1/chat', headers=h).json() == []
    body = {'name': 'Synthetic Patient', 'timezone': 'Asia/Kolkata', 'language': 'en', 'chat_history': True}
    assert client.put('/api/v1/profile', headers=h, json=body).status_code == 200
    client.post('/api/v1/chat', headers=h, json=question)
    assert len(client.get('/api/v1/chat', headers=h).json()) == 1
    client.put('/api/v1/profile', headers=h, json={**body, 'chat_history': False})
    assert client.get('/api/v1/chat', headers=h).json() == []


def test_account_deletion_removes_private_files_and_revokes_access(client, patient):
    from app.storage import storage_root
    h, _, _ = patient(); d = upload(client, h)
    with SessionLocal() as db:
        page = db.scalar(select(Page).where(Page.document_id == d['id']))
        key = read(page)['storage_key']
    assert (storage_root() / key).exists()
    assert client.delete('/api/v1/account', headers=h).status_code == 200
    assert not (storage_root() / key).exists()
    assert client.get('/api/v1/profile', headers=h).status_code == 401


def test_notification_intent_and_preference_reconciliation(client, patient, extraction, monkeypatch):
    h, _, _ = patient(); confirmed(client, h, extraction, monkeypatch)
    assert not client.get('/api/v1/notifications/intent', headers=h).json()['doses']
    pref = {'enabled': True, 'remote_enabled': False, 'quiet_start': None, 'quiet_end': None}
    client.put('/api/v1/notifications/preferences', headers=h, json=pref)
    intent = client.get('/api/v1/notifications/intent', headers=h).json()
    assert 0 < len(intent['doses']) <= 48
    client.put('/api/v1/notifications/preferences', headers=h, json={**pref, 'enabled': False})
    assert not client.get('/api/v1/notifications/intent', headers=h).json()['doses']


def test_tracker_calendar_window_uses_patient_timezone(client, patient, extraction, monkeypatch):
    h, _, _ = patient(); confirmed(client, h, extraction, monkeypatch)
    result = client.get('/api/v1/doses?day_offset=1', headers=h)
    assert result.status_code == 200
    assert len(result.json()) == 1
    dose = result.json()[0]
    assert datetime.fromtimestamp(dose['due_at'], ZoneInfo('Asia/Kolkata')).strftime('%H:%M') == '23:59'
    assert client.get('/api/v1/doses?day_offset=8', headers=h).status_code == 422
