from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from .db import session
from .models import Preferences, Device, Dose, Delivery, Profile, now
from .schemas import PreferencesInput, DeviceInput
from .security import current_user, read, put, digest, owned, audit
from .scheduling import materialize, quiet_at
from .config import settings

router = APIRouter(prefix='/notifications', tags=['Notifications'])


@router.get('/preferences')
def preferences(user=Depends(current_user), db=Depends(session)):
    return read(db.scalar(select(Preferences).where(Preferences.user_id == user.id)))


@router.put('/preferences')
def set_preferences(body: PreferencesInput, user=Depends(current_user), db=Depends(session)):
    row = db.scalar(select(Preferences).where(Preferences.user_id == user.id).with_for_update())
    put(row, body.model_dump())
    audit(db, user.id, 'notification_preferences_updated')
    return read(row)


@router.get('/intent')
def intent(user=Depends(current_user), db=Depends(session)):
    materialize(db, user.id)
    prefs = read(db.scalar(select(Preferences).where(Preferences.user_id == user.id)))
    future = db.scalars(select(Dose).where(Dose.user_id == user.id, Dose.status == 'upcoming', Dose.due_at > now(),
                                         Dose.due_at < now() + 7 * 86400).order_by(Dose.due_at)).all()
    upcoming = [{'dose_id': d.id, 'due_at': d.due_at} for d in future
                if prefs['enabled'] and not quiet_at(d.due_at, prefs, read(d)['timezone'])][:48]
    return {'preferences': prefs, 'doses': upcoming, 'window_days': 7, 'max_notifications': 48,
            'remote_configured': bool(settings().firebase_credentials),
            'message': 'Keep the app open periodically to refresh the rolling reminder window.'}


@router.post('/devices')
def register_device(body: DeviceInput, user=Depends(current_user), db=Depends(session)):
    fingerprint = digest(body.token)
    row = db.scalar(select(Device).where(Device.token_hash == fingerprint).with_for_update())
    if row and row.user_id != user.id:
        db.delete(row)
        db.flush()
        row = None
    if not row:
        row = Device(user_id=user.id, token_hash=fingerprint)
        db.add(row)
    put(row, {'token': body.token, 'device_name': body.device_name, 'updated_at': now()})
    db.flush()
    return {'id': row.id}


@router.delete('/devices/{device_id}')
def deregister_device(device_id: str, user=Depends(current_user), db=Depends(session)):
    db.delete(owned(db, Device, device_id, user.id))
    return {'message': 'Device deregistered'}


def send_fcm(token, dose_id):
    if not settings().firebase_credentials:
        raise RuntimeError('FCM not configured')
    import firebase_admin
    from firebase_admin import credentials, messaging
    try:
        app = firebase_admin.get_app()
    except ValueError:
        app = firebase_admin.initialize_app(credentials.Certificate(settings().firebase_credentials))
    return messaging.send(messaging.Message(token=token,
        notification=messaging.Notification(title='SehatBridge AI', body='You have a scheduled health reminder.'),
        data={'dose_id': dose_id}, android=messaging.AndroidConfig(ttl=120, collapse_key=f'dose:{dose_id}')), app=app)


def deliver_due(db):
    # At-most-one attempt per device/dose avoids blind retries and duplicate alerts.
    if not settings().firebase_credentials:
        return
    for prefs_row in db.scalars(select(Preferences)):
        prefs = read(prefs_row)
        if not prefs.get('enabled') or not prefs.get('remote_enabled'):
            continue
        materialize(db, prefs_row.user_id)
        for dose in db.scalars(select(Dose).where(Dose.user_id == prefs_row.user_id, Dose.status == 'upcoming',
                              Dose.due_at <= now(), Dose.due_at > now() - 120)):
            if quiet_at(dose.due_at, prefs, read(dose)['timezone']):
                continue
            for device in db.scalars(select(Device).where(Device.user_id == prefs_row.user_id)):
                if db.scalar(select(Delivery.id).where(Delivery.dose_id == dose.id, Delivery.device_id == device.id)):
                    continue
                delivery = put(Delivery(user_id=dose.user_id, dose_id=dose.id, device_id=device.id, status='attempting'), {'at': now()})
                db.add(delivery)
                db.commit()  # persist claim before network send; never log payload/token
                try:
                    send_fcm(read(device)['token'], dose.id)
                    delivery.status = 'sent'
                except Exception:
                    delivery.status = 'failed'
                    put(delivery, {'at': now(), 'error': 'provider_delivery_failed'})
                db.commit()
