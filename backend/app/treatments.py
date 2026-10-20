from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import re
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy import select
from .db import session
from .models import Document, Analysis, Treatment, Medicine, Schedule, Dose, DoseEvent, FollowUp, LabTest, Instruction, Profile, now
from .schemas import ConfirmInput, Extraction, DoseInput
from .security import current_user, owned, read, put, audit, sensitive_limit
from .scheduling import materialize, deactivate_schedules

router = APIRouter(tags=['Treatments and doses'])


def check_schedules(extraction, schedules):
    seen = set()
    for spec in schedules:
        if spec.medicine_index >= len(extraction.medicines) or spec.medicine_index in seen:
            raise HTTPException(422, 'Invalid or duplicate medicine schedule')
        seen.add(spec.medicine_index)
        med = extraction.medicines[spec.medicine_index]
        if not med.name or not med.dose or not med.dose_unit or not med.frequency:
            raise HTTPException(422, 'Correct missing critical medicine fields before scheduling')
        frequency = re.sub(r'\s+', ' ', med.frequency.strip().lower())
        supported = {'once daily': 1, 'daily': 1, 'od': 1, 'qd': 1, 'once a day': 1,
                     'twice daily': 2, 'twice a day': 2, 'bid': 2, 'bd': 2,
                     'three times daily': 3, 'tid': 3, 'tds': 3, 'four times daily': 4, 'qid': 4}
        expected = supported.get(frequency)
        if expected is None:
            raise HTTPException(422, 'Automatic reminders currently support simple daily schedules only. Keep weekly, tapering, interval and as-needed instructions unscheduled and verify with your clinician.')
        if len(set(spec.times)) != expected:
            raise HTTPException(422, 'The number of daily reminder times must match the confirmed documented frequency')
        if med.clarification_required and (not spec.clinician_verified or not spec.clarification_note.strip()):
            raise HTTPException(422, 'Record clinician/pharmacist clarification before activating uncertain instructions')


def add_schedules(db, user_id, treatment, meds, specs):
    for spec in specs:
        data = spec.model_dump(mode='json')
        data['activated_at'] = int(now())
        db.add(put(Schedule(user_id=user_id, treatment_id=treatment.id, medicine_id=meds[spec.medicine_index].id), data))
    db.flush()
    materialize(db, user_id)


@router.post('/documents/{document_id}/confirm', status_code=201)
def confirm(document_id: str, body: ConfirmInput, user=Depends(current_user), db=Depends(session)):
    doc = owned(db, Document, document_id, user.id, lock=True)
    analysis = db.scalar(select(Analysis).where(Analysis.document_id == doc.id, Analysis.user_id == user.id))
    if not body.confirmed or not analysis or analysis.revision != body.revision:
        raise HTTPException(409, 'Explicit confirmation of the current draft revision is required')
    if db.scalar(select(Treatment.id).where(Treatment.document_id == doc.id)):
        raise HTTPException(409, 'This document is already confirmed')
    extraction = Extraction.model_validate(read(analysis))
    check_schedules(extraction, body.schedules)
    t = put(Treatment(user_id=user.id, document_id=doc.id), {'extraction': extraction.model_dump(mode='json'), 'confirmed_at': now()})
    db.add(t)
    db.flush()
    meds = []
    for index, med in enumerate(extraction.medicines):
        row = put(Medicine(user_id=user.id, treatment_id=t.id), {**med.model_dump(mode='json'), 'extraction_index': index})
        db.add(row)
        meds.append(row)
    for cls, values in ((FollowUp, extraction.follow_ups), (LabTest, extraction.tests), (Instruction, extraction.instructions)):
        for value in values:
            db.add(put(cls(user_id=user.id, treatment_id=t.id), value.model_dump(mode='json')))
    db.flush()
    add_schedules(db, user.id, t, meds, body.schedules)
    doc.status = 'confirmed'
    audit(db, user.id, 'treatment_confirmed', t.id)
    return {'id': t.id, 'revision': t.revision}


def treatment_view(db, t):
    schedules = db.scalars(select(Schedule).where(Schedule.treatment_id == t.id, Schedule.active.is_(True))).all()
    return {'id': t.id, 'document_id': t.document_id, 'status': t.status, 'revision': t.revision, **read(t),
            'schedules': [{'id': s.id, **read(s)} for s in schedules]}


@router.get('/treatments')
def treatments(user=Depends(current_user), db=Depends(session)):
    return [treatment_view(db, t) for t in db.scalars(select(Treatment).where(Treatment.user_id == user.id))]


@router.get('/treatments/{treatment_id}')
def treatment(treatment_id: str, user=Depends(current_user), db=Depends(session)):
    return treatment_view(db, owned(db, Treatment, treatment_id, user.id))


@router.put('/treatments/{treatment_id}/schedules')
def replace_schedules(treatment_id: str, body: ConfirmInput, user=Depends(current_user), db=Depends(session)):
    t = owned(db, Treatment, treatment_id, user.id, lock=True)
    if not body.confirmed or t.revision != body.revision or t.status != 'active':
        raise HTTPException(409, 'Confirm the current active treatment revision')
    ex = Extraction.model_validate(read(t)['extraction'])
    check_schedules(ex, body.schedules)
    meds = db.scalars(select(Medicine).where(Medicine.treatment_id == t.id)).all()
    # Map source medicines by stored extraction order, not database row order.
    meds.sort(key=lambda m: read(m)['extraction_index'])
    deactivate_schedules(db, t.id)
    add_schedules(db, user.id, t, meds, body.schedules)
    t.revision += 1
    audit(db, user.id, 'schedules_reconciled', t.id)
    return treatment_view(db, t)


@router.post('/treatments/{treatment_id}/complete')
def complete(treatment_id: str, user=Depends(current_user), db=Depends(session)):
    t = owned(db, Treatment, treatment_id, user.id, lock=True)
    t.status = 'completed'
    deactivate_schedules(db, t.id)
    audit(db, user.id, 'treatment_completed', t.id)
    return {'status': t.status}


@router.get('/doses')
def doses(start: int | None = None, end: int | None = None, day_offset: int = Query(0, ge=-366, le=7), user=Depends(current_user), db=Depends(session)):
    materialize(db, user.id)
    profile = db.scalar(select(Profile).where(Profile.user_id == user.id))
    zone = ZoneInfo(read(profile)['timezone'])
    local = datetime.now(zone).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=day_offset)
    start = start if start is not None else int(local.timestamp())
    end = end if end is not None else int((local + timedelta(days=1)).timestamp())
    if end < start or end - start > 32 * 86400:
        raise HTTPException(422, 'Dose window must be no more than 32 days')
    return [{'id': d.id, 'due_at': d.due_at, 'status': d.status, **read(d)} for d in db.scalars(
        select(Dose).where(Dose.user_id == user.id, Dose.due_at >= start, Dose.due_at < end, Dose.status != 'cancelled').order_by(Dose.due_at))]


@router.post('/doses/{dose_id}/events')
def track(dose_id: str, body: DoseInput, user=Depends(current_user), db=Depends(session)):
    dose = owned(db, Dose, dose_id, user.id, lock=True)
    existing = db.scalar(select(DoseEvent).where(DoseEvent.user_id == user.id, DoseEvent.idempotency_key == body.idempotency_key))
    if existing:
        if existing.dose_id != dose.id or read(existing)['status'] != body.status:
            raise HTTPException(409, 'Idempotency key belongs to another event')
        return {'id': dose.id, 'status': dose.status, 'duplicate': True}
    if dose.status == 'cancelled' or dose.status != body.expected_status:
        raise HTTPException(409, 'Dose changed. Reload before correcting.')
    if dose.due_at > now() + 3600:
        raise HTTPException(422, 'This dose is not due yet')
    before = dose.status
    dose.status = body.status
    db.add(put(DoseEvent(user_id=user.id, dose_id=dose.id, idempotency_key=body.idempotency_key),
               {'before': before, 'status': body.status, 'recorded_at': now()}))
    audit(db, user.id, 'dose_updated', dose.id)
    return {'id': dose.id, 'status': dose.status, 'duplicate': False}


@router.get('/doses/{dose_id}/events')
def dose_history(dose_id: str, user=Depends(current_user), db=Depends(session)):
    owned(db, Dose, dose_id, user.id)
    return [read(e) for e in db.scalars(select(DoseEvent).where(DoseEvent.dose_id == dose_id, DoseEvent.user_id == user.id))]
