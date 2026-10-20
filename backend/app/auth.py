import secrets
import smtplib
from email.message import EmailMessage
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from .db import session
from .config import settings
from .models import User, Profile, OTP, Refresh, Preferences, now
from .schemas import Credentials, Destination, OTPInput, RefreshInput, PasswordInput
from .security import digest, hasher, seal, unseal, put, verify_password, tokens, current_user, sensitive_limit, limiter, audit
from .recaptcha import router as captcha_router, verify_recaptcha

router = APIRouter(prefix='/auth', tags=['Authentication'])
router.include_router(captcha_router)
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


def find_user(db, email):
    return db.scalar(select(User).where(User.email_hash == digest(email.strip().lower())))


def deliver_otp(email, code):
    cfg = settings()
    if cfg.otp_provider == 'console' and cfg.environment == 'development':
        # Explicit development-only output. Never enable this provider in production.
        print(f'[DEVELOPMENT OTP ONLY] {code}', flush=True)
        return
    if cfg.otp_provider != 'smtp' or not cfg.smtp_host:
        raise HTTPException(503, 'OTP delivery is not configured')
    message = EmailMessage()
    message['From'], message['To'], message['Subject'] = cfg.smtp_from, email, 'SehatBridge verification code'
    message.set_content(f'Your verification code is {code}. It expires in 10 minutes.')
    try:
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(cfg.smtp_username, cfg.smtp_password)
            smtp.send_message(message)
    except Exception:
        raise HTTPException(503, 'Unable to deliver verification code. Please retry.')


def challenge(db, user, purpose):
    latest = db.scalar(select(OTP).where(OTP.user_id == user.id, OTP.purpose == purpose).order_by(OTP.created.desc()).limit(1))
    if latest and latest.created > now() - 60:
        raise HTTPException(429, 'Wait 60 seconds before requesting a new code')
    db.execute(update(OTP).where(OTP.user_id == user.id, OTP.purpose == purpose).values(used=True))
    code = f'{secrets.randbelow(1000000):06d}'
    row = put(OTP(user_id=user.id, purpose=purpose, digest=digest(f'{user.id}:{purpose}:{code}'),
                  expires=int(now()) + 600, created=int(now())), {})
    db.add(row)
    deliver_otp(unseal(user.email, f'email:{user.id}'), code)


@router.post('/register', status_code=201)
def register(body: Credentials, request: Request, db=Depends(session)):
    sensitive_limit(request, digest(body.email.lower()), 'register', 5)
    verify_recaptcha(body.recaptcha_token)
    if find_user(db, body.email):
        raise HTTPException(409, 'Unable to register. Try signing in or recovering your account.')
    from .models import uid
    user = User(id=uid(), email_hash=digest(body.email.strip().lower()), password=hasher.hash(body.password))
    user.email = seal(body.email.strip().lower(), f'email:{user.id}')
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        raise HTTPException(409, 'Unable to register')
    db.add(put(Profile(user_id=user.id), {'name': '', 'language': 'en', 'timezone': 'Asia/Kolkata', 'chat_history': False}))
    db.add(put(Preferences(user_id=user.id), {'enabled': False, 'remote_enabled': False, 'quiet_start': None, 'quiet_end': None}))
    challenge(db, user, 'verify')
    audit(db, user.id, 'registered')
    return {'message': 'Verify your email using the code sent to you'}


@router.post('/otp/request')
def request_otp(body: Destination, request: Request, db=Depends(session)):
    sensitive_limit(request, digest(body.email.lower()), 'otp-request', 3)
    verify_recaptcha(body.recaptcha_token)
    user = find_user(db, body.email)
    if user:
        challenge(db, user, body.purpose)
    return {'message': 'If the account exists, a verification code has been sent'}


@router.post('/otp/verify')
def verify_otp(body: OTPInput, request: Request, db=Depends(session)):
    sensitive_limit(request, digest(body.email.lower()), 'otp-verify', 8)
    user = find_user(db, body.email)
    row = db.scalar(select(OTP).where(OTP.user_id == user.id, OTP.purpose == body.purpose, OTP.used.is_(False))
                    .order_by(OTP.created.desc()).with_for_update().limit(1)) if user else None
    if not row or row.expires < now() or row.attempts >= 5:
        raise HTTPException(400, 'Invalid or expired code')
    row.attempts += 1
    if not secrets.compare_digest(row.digest, digest(f'{user.id}:{body.purpose}:{body.code}')):
        db.commit()  # retain failed-attempt count even though response is an error
        raise HTTPException(400, 'Invalid or expired code')
    if body.purpose == 'reset':
        if not body.new_password:
            raise HTTPException(422, 'New password required')
        user.password = hasher.hash(body.new_password)
        user.token_version += 1
        db.execute(update(Refresh).where(Refresh.user_id == user.id).values(revoked=True))
    user.verified = True
    row.used = True
    audit(db, user.id, 'otp_verified')
    return tokens(db, user)


@router.post('/login')
def login(body: Credentials, request: Request, db=Depends(session)):
    sensitive_limit(request, digest(body.email.lower()), 'login', 8)
    verify_recaptcha(body.recaptcha_token)
    user = find_user(db, body.email)
    valid = verify_password(body.password, user.password if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(401, 'Incorrect email or password')
    if not user.verified:
        raise HTTPException(403, 'Verify your email first')
    return tokens(db, user)


@router.post('/refresh')
def refresh(body: RefreshInput, request: Request, db=Depends(session)):
    sensitive_limit(request, scope='refresh', limit=30)
    row = db.scalar(select(Refresh).where(Refresh.digest == digest(body.refresh_token)).with_for_update())
    if not row or row.expires < now():
        raise HTTPException(401, 'Session expired')
    user = db.get(User, row.user_id)
    if row.revoked:
        # Refresh replay revokes the account's entire session family.
        user.token_version += 1
        db.execute(update(Refresh).where(Refresh.user_id == user.id).values(revoked=True))
        db.commit()
        raise HTTPException(401, 'Session revoked')
    row.revoked = True
    return tokens(db, user)


@router.post('/logout')
def logout(user=Depends(current_user), db=Depends(session)):
    user.token_version += 1
    db.execute(update(Refresh).where(Refresh.user_id == user.id).values(revoked=True))
    return {'message': 'All sessions signed out'}


@router.post('/password')
def change_password(body: PasswordInput, user=Depends(current_user), db=Depends(session)):
    if not verify_password(body.old_password, user.password):
        raise HTTPException(400, 'Current password is incorrect')
    user.password = hasher.hash(body.new_password)
    user.token_version += 1
    db.execute(update(Refresh).where(Refresh.user_id == user.id).values(revoked=True))
    audit(db, user.id, 'password_changed')
    return {'message': 'Password changed. Please sign in again.'}
