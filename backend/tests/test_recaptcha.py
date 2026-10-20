from datetime import datetime, timedelta, timezone
import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import select
from app import recaptcha, auth
from app.config import settings, Settings
from app.db import SessionLocal
from app.models import User, OTP

TOKEN = 'synthetic-google-token-for-tests-only'
HOST = 'api.example.test'


@pytest.fixture
def protected(monkeypatch):
    cfg = settings()
    for key, value in {
        'recaptcha_enabled': True, 'recaptcha_site_key': 'public-site-key-test-only',
        'recaptcha_secret_key': 'server-secret-test-only', 'recaptcha_public_origin': f'https://{HOST}',
        'recaptcha_allowed_hostnames': [HOST],
    }.items():
        monkeypatch.setattr(cfg, key, value)
    return cfg


def mock_google(monkeypatch, body):
    def verify(url, **kwargs):
        assert url == recaptcha.VERIFY_URL
        assert kwargs['data']['secret'] == 'server-secret-test-only'
        assert kwargs['data']['response'] == TOKEN
        assert kwargs['timeout'] == 8.0 and kwargs['follow_redirects'] is False
        return httpx.Response(200, json=body, request=httpx.Request('POST', url))
    monkeypatch.setattr(recaptcha.httpx, 'post', verify)


def success(**extra):
    return {'success': True, 'hostname': HOST, 'challenge_ts': datetime.now(timezone.utc).isoformat(), **extra}


def test_public_config_and_page_do_not_expose_secret(client, protected):
    config = client.get('/api/v1/auth/recaptcha-config')
    assert config.status_code == 200
    assert config.json() == {'enabled': True, 'type': 'v2_checkbox', 'page_url': f'https://{HOST}/api/v1/auth/mobile-recaptcha'}
    page = client.get('/api/v1/auth/mobile-recaptcha')
    assert page.status_code == 200
    assert 'grecaptcha.render' in page.text and "size:'normal'" in page.text
    assert protected.recaptcha_site_key in page.text
    assert protected.recaptcha_secret_key not in page.text + config.text
    assert page.headers['cache-control'] == 'no-store'
    assert "frame-ancestors 'none'" in page.headers['content-security-policy']
    assert "script-src 'nonce-" in page.headers['content-security-policy']


def test_dev_can_explicitly_disable_captcha(client):
    assert client.get('/api/v1/auth/recaptcha-config').json()['enabled'] is False
    assert client.get('/api/v1/auth/mobile-recaptcha').status_code == 404


@pytest.mark.parametrize('path,body', [
    ('/auth/register', {'email': 'test@example.test', 'password': 'SyntheticPassword123!'}),
    ('/auth/login', {'email': 'test@example.test', 'password': 'SyntheticPassword123!'}),
    ('/auth/otp/request', {'email': 'test@example.test', 'purpose': 'verify'}),
    ('/auth/otp/request', {'email': 'test@example.test', 'purpose': 'reset'}),
])
def test_missing_captcha_blocks_auth_and_email_side_effects(client, protected, monkeypatch, path, body):
    monkeypatch.setattr(auth, 'deliver_otp', lambda *a: pytest.fail('No OTP may be sent without CAPTCHA'))
    monkeypatch.setattr(recaptcha.httpx, 'post', lambda *a, **kw: pytest.fail('Missing token must be rejected locally'))
    result = client.post('/api/v1' + path, json=body)
    assert result.status_code == 403
    with SessionLocal() as db:
        assert db.scalar(select(User)) is None
        assert db.scalar(select(OTP)) is None


def test_verified_captcha_allows_registration(client, protected, monkeypatch):
    sent = []
    monkeypatch.setattr(auth, 'deliver_otp', lambda *args: sent.append(True))
    mock_google(monkeypatch, success())
    result = client.post('/api/v1/auth/register', json={'email': 'test@example.test', 'password': 'SyntheticPassword123!', 'recaptcha_token': TOKEN})
    assert result.status_code == 201, result.text
    assert sent == [True]


@pytest.mark.parametrize('body', [
    {'success': False, 'error-codes': ['timeout-or-duplicate']},
    success(hostname='api.example.test.attacker.test'),
    success(hostname=None),
    success(challenge_ts=(datetime.now(timezone.utc) + timedelta(minutes=3)).isoformat()),
    success(challenge_ts='2026-10-19T00:00:00'),
    success(challenge_ts=None),
    success(success='true'),
])
def test_failed_expired_or_foreign_tokens_never_send_otp(client, protected, monkeypatch, body):
    mock_google(monkeypatch, body)
    monkeypatch.setattr(auth, 'deliver_otp', lambda *a: pytest.fail('Invalid token must not send an OTP'))
    result = client.post('/api/v1/auth/otp/request', json={'email': 'test@example.test', 'recaptcha_token': TOKEN})
    assert result.status_code == 403


def test_consumed_token_cannot_be_reused_for_another_auth_request(client, protected, monkeypatch):
    used = set()
    def verify(url, **kwargs):
        token = kwargs['data']['response']
        body = {'success': False, 'error-codes': ['timeout-or-duplicate']} if token in used else success()
        used.add(token)
        return httpx.Response(200, json=body, request=httpx.Request('POST', url))
    monkeypatch.setattr(recaptcha.httpx, 'post', verify)
    first = client.post('/api/v1/auth/login', json={'email': 'absent@example.test', 'password': 'SyntheticPassword123!', 'recaptcha_token': TOKEN})
    assert first.status_code == 401  # Human check passed; incorrect credentials still rejected.
    second = client.post('/api/v1/auth/otp/request', json={'email': 'absent@example.test', 'recaptcha_token': TOKEN})
    assert second.status_code == 403


def test_google_timeout_fails_closed(client, protected, monkeypatch):
    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout('Synthetic provider timeout')
    monkeypatch.setattr(recaptcha.httpx, 'post', timeout)
    result = client.post('/api/v1/auth/otp/request', json={'email': 'test@example.test', 'recaptcha_token': TOKEN})
    assert result.status_code == 503
    assert TOKEN not in result.text and protected.recaptcha_secret_key not in result.text


def test_valid_token_after_slow_human_challenge_is_accepted(client, protected, monkeypatch):
    mock_google(monkeypatch, success(challenge_ts=(datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()))
    result = client.post('/api/v1/auth/otp/request', json={'email': 'absent@example.test', 'recaptcha_token': TOKEN})
    assert result.status_code == 200


@pytest.mark.parametrize('body', [[], {'success': False, 'error-codes': None}, {'success': False, 'error-codes': ['invalid-input-secret']}])
def test_invalid_provider_configuration_or_response_is_unavailable(client, protected, monkeypatch, body):
    mock_google(monkeypatch, body)
    result = client.post('/api/v1/auth/otp/request', json={'email': 'test@example.test', 'recaptcha_token': TOKEN})
    assert result.status_code == 503


def test_settings_require_complete_keys_and_exact_hostname():
    cfg = settings()
    base = {'_env_file': None, 'jwt_secret': cfg.jwt_secret, 'otp_secret': cfg.otp_secret,
            'encryption_key': cfg.encryption_key, 'recaptcha_enabled': True,
            'recaptcha_site_key': 'public-site-key-test-only', 'recaptcha_secret_key': 'test-only-secret',
            'recaptcha_public_origin': 'https://api.example.test', 'recaptcha_allowed_hostnames': ['api.example.test']}
    assert Settings(**base).recaptcha_enabled
    for override in ({'recaptcha_secret_key': ''}, {'recaptcha_allowed_hostnames': ['other.example.test']},
                     {'recaptcha_public_origin': 'https://user:password@api.example.test'},
                     {'recaptcha_public_origin': 'https://api.example.test/injected-path'}):
        with pytest.raises(ValidationError):
            Settings(**{**base, **override})


def test_production_cannot_disable_captcha():
    cfg = settings()
    with pytest.raises(ValidationError, match='Production requires reCAPTCHA protection'):
        Settings(_env_file=None, environment='production', jwt_secret=cfg.jwt_secret,
                 otp_secret=cfg.otp_secret, encryption_key=cfg.encryption_key, recaptcha_enabled=False)


@pytest.mark.parametrize('override', [
    {'recaptcha_site_key': '6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI'},
    {'recaptcha_public_origin': 'http://api.example.test'},
])
def test_production_rejects_public_test_keys_and_http(override):
    cfg = settings()
    values = {'environment': 'production', 'jwt_secret': cfg.jwt_secret, 'otp_secret': cfg.otp_secret,
        'encryption_key': cfg.encryption_key, 'otp_provider': 'smtp', 'smtp_host': 'smtp.example.test',
        'database_url': 'postgresql+psycopg://test:test@localhost/test', 'redis_url': 'redis://localhost:6379',
        'recaptcha_enabled': True, 'recaptcha_site_key': 'public-site-key-test-only',
        'recaptcha_secret_key': 'secret-test-only', 'recaptcha_public_origin': f'https://{HOST}',
        'recaptcha_allowed_hostnames': [HOST]}
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{**values, **override})
