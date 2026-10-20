import os
import base64
import secrets
import tempfile
from pathlib import Path
import pytest

TEST_ROOT = Path(__file__).resolve().parents[1] / '.test-data'
TEST_ROOT.mkdir(exist_ok=True)
os.environ.update(DATABASE_URL=f'sqlite:///{(TEST_ROOT / "test.db").as_posix()}',
    JWT_SECRET=secrets.token_urlsafe(48), OTP_SECRET=secrets.token_urlsafe(48),
    ENCRYPTION_KEY=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
    STORAGE_PATH=str(TEST_ROOT / 'storage'), ENVIRONMENT='development', REDIS_URL='', GEMINI_API_KEY='', GEMINI_MODEL='', RECAPTCHA_ENABLED='false')

from fastapi.testclient import TestClient
from app.main import app
from app.db import Base, engine, SessionLocal
from app.security import limiter
from app import auth, demo


@pytest.fixture(autouse=True)
def clean_database(monkeypatch):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    limiter.buckets.clear()
    with SessionLocal() as db:
        demo.seed(db)
        db.commit()


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture
def patient(client, monkeypatch):
    codes = {}
    monkeypatch.setattr(auth, 'deliver_otp', lambda email, code: codes.update({email: code}))
    def make(email='patient@example.test'):
        password = 'SyntheticPassword123!'
        result = client.post('/api/v1/auth/register', json={'email': email, 'password': password})
        assert result.status_code == 201, result.text
        result = client.post('/api/v1/auth/otp/verify', json={'email': email, 'code': codes[email], 'purpose': 'verify'})
        assert result.status_code == 200, result.text
        tokens = result.json()
        return {'Authorization': 'Bearer ' + tokens['access_token']}, tokens, codes
    return make


@pytest.fixture
def extraction():
    return {
        'document_type': 'prescription', 'summary': 'Synthetic patient document for software testing only.',
        'medicines': [{'name': 'SYNTHETIC MEDICINE A', 'strength': '10 test units', 'dose': '1', 'dose_unit': 'test tablet',
            'frequency': 'once daily', 'source': {'page': 1, 'excerpt': 'SYNTHETIC MEDICINE A: 1 test tablet once daily'},
            'confidence': 'high', 'clarification_required': False}],
        'tests': [{'name': 'Synthetic laboratory investigation', 'date': '2099-01-01', 'source': {'page': 1, 'excerpt': 'Synthetic laboratory investigation on 2099-01-01'}}]
    }
