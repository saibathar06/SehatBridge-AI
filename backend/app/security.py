import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from .config import settings
from .db import session
from .models import User, Refresh, now, Audit

hasher = PasswordHasher()  # Argon2id
bearer = HTTPBearer(auto_error=False)


def digest(value):
    return hmac.new(settings().otp_secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def seal(value, context):
    nonce = secrets.token_bytes(12)
    key = base64.urlsafe_b64decode(settings().encryption_key)
    raw = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()
    return base64.urlsafe_b64encode(nonce + AESGCM(key).encrypt(nonce, raw, context.encode())).decode()


def unseal(value, context):
    raw = base64.urlsafe_b64decode(value)
    return json.loads(AESGCM(base64.urlsafe_b64decode(settings().encryption_key)).decrypt(raw[:12], raw[12:], context.encode()))


def put(row, data):
    row.data = seal(data, f'{row.__tablename__}:{row.user_id}')
    return row


def read(row):
    return unseal(row.data, f'{row.__tablename__}:{row.user_id}')


def audit(db, user_id, action, resource_id=''):
    db.add(put(Audit(user_id=user_id), {'action': action, 'resource_id': resource_id, 'at': now()}))


def verify_password(password, encoded):
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def tokens(db, user):
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings().access_minutes)
    access = jwt.encode({'sub': user.id, 'ver': user.token_version, 'exp': expires, 'iat': datetime.now(timezone.utc),
                         'iss': 'sehatbridge', 'aud': 'sehatbridge-mobile'}, settings().jwt_secret, algorithm='HS256')
    refresh = secrets.token_urlsafe(48)
    db.add(put(Refresh(user_id=user.id, digest=digest(refresh), expires=int(now()) + settings().refresh_days * 86400), {}))
    return {'access_token': access, 'refresh_token': refresh, 'token_type': 'bearer'}


def current_user(auth: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(session)):
    try:
        if not auth:
            raise ValueError()
        payload = jwt.decode(auth.credentials, settings().jwt_secret, algorithms=['HS256'],
                             issuer='sehatbridge', audience='sehatbridge-mobile', options={'require': ['exp', 'sub', 'ver']})
        user = db.get(User, payload['sub'])
        if not user or not user.verified or user.token_version != payload['ver']:
            raise ValueError()
        return user
    except (jwt.InvalidTokenError, ValueError, KeyError):
        raise HTTPException(401, 'Please sign in again', headers={'WWW-Authenticate': 'Bearer'})


def owned(db, cls, resource_id, user_id, lock=False):
    query = select(cls).where(cls.id == resource_id, cls.user_id == user_id)
    if lock:
        query = query.with_for_update()
    row = db.scalar(query)
    if not row:
        raise HTTPException(404, 'Record not found')
    return row


class RateLimiter:
    def __init__(self):
        self.buckets = defaultdict(list)
        self.lock = threading.Lock()
        self.redis = None
        if settings().redis_url:
            from redis import Redis
            self.redis = Redis.from_url(settings().redis_url, socket_timeout=2)

    def check(self, key, limit, window=60):
        safe_key = 'sb:limit:' + digest(key)
        if self.redis:
            try:
                # Increment + expiry are atomic; avoid immortal counters after worker crashes.
                count = self.redis.eval("local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n", 1, safe_key, window)
                if count > limit:
                    raise HTTPException(429, 'Too many requests. Please try again later.', headers={'Retry-After': str(window)})
                return
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(503, 'Request limiter temporarily unavailable')
        with self.lock:
            timestamp = time.monotonic()
            self.buckets[safe_key] = [v for v in self.buckets[safe_key] if v > timestamp - window]
            if len(self.buckets[safe_key]) >= limit:
                raise HTTPException(429, 'Too many requests. Please try again later.', headers={'Retry-After': str(window)})
            self.buckets[safe_key].append(timestamp)
            if len(self.buckets) > 10000:
                for old in list(self.buckets):
                    if not self.buckets[old] or self.buckets[old][-1] < timestamp - window:
                        self.buckets.pop(old, None)


limiter = RateLimiter()


def sensitive_limit(request: Request, user_id='', scope='sensitive', limit=10):
    limiter.check(f'{scope}:ip:{request.client.host if request.client else "unknown"}', limit)
    if user_id:
        limiter.check(f'{scope}:account:{user_id}', limit)
