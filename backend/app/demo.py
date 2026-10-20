import json
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .db import session
from .models import Provider, Slot, Booking, Inventory, Order, OrderItem, now
from .security import current_user, owned, put, read, sensitive_limit
from .schemas import BookingInput, OrderInput
from .config import settings

router = APIRouter(prefix='/demo', tags=['Synthetic demonstrations'])
LABEL = 'Demonstration only — no real appointment, laboratory booking or pharmacy order has been made.'


def enabled():
    if not settings().demo_enabled:
        raise HTTPException(404, 'Demonstrations disabled')


def seed(db):
    if db.scalar(select(Provider.id).limit(1)):
        return
    for kind, name, data in [
        ('doctor', 'Dr. Asha Example', {'specialty': 'General physician', 'languages': ['Hindi', 'English'], 'fee_paise': 50000}),
        ('doctor', 'Dr. Ravi Example', {'specialty': 'Internal medicine', 'languages': ['English'], 'fee_paise': 60000}),
        ('laboratory', 'SampleCare Demonstration Lab', {'tests': ['CBC demonstration', 'HbA1c demonstration'], 'languages': ['Hindi', 'English']}),
        ('pharmacy', 'SampleCare Demonstration Pharmacy', {'address': 'Synthetic location', 'languages': ['Hindi', 'English']})]:
        provider = Provider(kind=kind, name=name, data=json.dumps(data))
        db.add(provider)
        db.flush()
        if kind in ('doctor', 'laboratory'):
            for day in (1, 2, 3):
                for hour in (9, 11, 14):
                    start = (datetime.now(timezone.utc) + timedelta(days=day)).replace(hour=hour, minute=0, second=0, microsecond=0)
                    db.add(Slot(provider_id=provider.id, starts=start.isoformat()))
        else:
            for name, price in [('Synthetic medicine A (demo only)', 3500), ('Synthetic medicine B (demo only)', 2800)]:
                db.add(Inventory(provider_id=provider.id, name=name, price_paise=price))


@router.get('/providers', dependencies=[Depends(enabled)])
def providers(kind: str | None = None, specialty: str | None = None, language: str | None = None,
              user=Depends(current_user), db=Depends(session)):
    result = []
    for p in db.scalars(select(Provider)):
        data = json.loads(p.data)
        if kind and p.kind != kind or specialty and data.get('specialty') != specialty or language and language not in data.get('languages', []):
            continue
        result.append({'id': p.id, 'kind': p.kind, 'name': p.name, **data, 'label': LABEL})
    return result


@router.get('/providers/{provider_id}', dependencies=[Depends(enabled)])
def provider(provider_id: str, user=Depends(current_user), db=Depends(session)):
    p = db.get(Provider, provider_id)
    if not p:
        raise HTTPException(404, 'Demo provider not found')
    return {'id': p.id, 'kind': p.kind, 'name': p.name, **json.loads(p.data), 'label': LABEL}


@router.get('/providers/{provider_id}/slots', dependencies=[Depends(enabled)])
def slots(provider_id: str, user=Depends(current_user), db=Depends(session)):
    reserved = select(Booking.slot_id).where(Booking.slot_id.is_not(None))
    return [{'id': s.id, 'starts': s.starts} for s in db.scalars(select(Slot).where(Slot.provider_id == provider_id,
                Slot.id.not_in(reserved), Slot.starts > datetime.now(timezone.utc).isoformat()))]


@router.post('/bookings', status_code=201, dependencies=[Depends(enabled)])
def book(body: BookingInput, request: Request, user=Depends(current_user), db=Depends(session)):
    sensitive_limit(request, user.id, 'booking', 10)
    slot = db.scalar(select(Slot).where(Slot.id == body.slot_id).with_for_update())
    if not slot or slot.starts < datetime.now(timezone.utc).isoformat():
        raise HTTPException(422, 'Select an upcoming demonstration slot')
    p = db.get(Provider, slot.provider_id)
    booking = put(Booking(user_id=user.id, slot_id=slot.id), {'provider': p.name, 'kind': p.kind, 'starts': slot.starts, 'label': LABEL})
    db.add(booking)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'This demonstration slot has already been booked')
    return {'id': booking.id, 'status': booking.status, **read(booking)}


@router.get('/bookings', dependencies=[Depends(enabled)])
def bookings(user=Depends(current_user), db=Depends(session)):
    return [{'id': b.id, 'status': b.status, **read(b)} for b in db.scalars(select(Booking).where(Booking.user_id == user.id))]


@router.delete('/bookings/{booking_id}', dependencies=[Depends(enabled)])
def cancel(booking_id: str, user=Depends(current_user), db=Depends(session)):
    b = owned(db, Booking, booking_id, user.id, lock=True)
    b.status, b.slot_id = 'cancelled', None
    return {'status': b.status, 'label': LABEL}


@router.get('/inventory', dependencies=[Depends(enabled)])
def inventory(search: str = '', user=Depends(current_user), db=Depends(session)):
    return [{'id': i.id, 'provider_id': i.provider_id, 'name': i.name, 'price_paise': i.price_paise, 'label': LABEL}
            for i in db.scalars(select(Inventory)) if search.lower() in i.name.lower()]


@router.post('/orders', status_code=201, dependencies=[Depends(enabled)])
def order(body: OrderInput, request: Request, user=Depends(current_user), db=Depends(session)):
    sensitive_limit(request, user.id, 'order', 10)
    ids = [line.inventory_id for line in body.items]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, 'Duplicate cart line')
    items, total = [], 0
    for line in body.items:
        item = db.get(Inventory, line.inventory_id)
        if not item:
            raise HTTPException(422, 'Unknown synthetic inventory item')
        total += item.price_paise * line.quantity
        items.append({'name': item.name, 'quantity': line.quantity, 'unit_price_paise': item.price_paise})
    o = put(Order(user_id=user.id), {'items': items, 'total_paise': total, 'label': LABEL, 'created_at': now()})
    db.add(o)
    db.flush()
    for item in items:
        db.add(put(OrderItem(user_id=user.id, order_id=o.id), item))
    return {'id': o.id, 'status': o.status, **read(o)}


@router.get('/orders', dependencies=[Depends(enabled)])
def orders(user=Depends(current_user), db=Depends(session)):
    return [{'id': o.id, 'status': o.status, **read(o)} for o in db.scalars(select(Order).where(Order.user_id == user.id))]
