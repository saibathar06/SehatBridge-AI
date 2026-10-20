from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select, delete
from .models import Schedule, Dose, Medicine, User, now
from .security import put, read


def local_instants(day, clock, zone):
    """Skip nonexistent DST wall times; use only first occurrence of a repeated time."""
    naive = datetime.fromisoformat(f'{day.isoformat()}T{clock}')
    local = naive.replace(tzinfo=zone, fold=0)
    utc = local.astimezone(timezone.utc)
    if utc.astimezone(zone).replace(tzinfo=None) == naive:
        return int(utc.timestamp())
    return None


def materialize(db, user_id, horizon=7):
    db.scalar(select(User.id).where(User.id == user_id).with_for_update())
    timestamp = int(now())
    schedules = db.scalars(select(Schedule).where(Schedule.user_id == user_id, Schedule.active.is_(True))).all()
    for row in schedules:
        spec = read(row)
        zone = ZoneInfo(spec['timezone'])
        today = datetime.fromtimestamp(timestamp, zone).date()
        start = max(datetime.fromisoformat(spec['start_date']).date(), today - timedelta(days=1))
        end = min(datetime.fromisoformat(spec['end_date']).date(), today + timedelta(days=horizon))
        existing = set(db.scalars(select(Dose.due_at).where(Dose.schedule_id == row.id)).all())
        medicine = read(db.get(Medicine, row.medicine_id))
        while start <= end:
            for clock in spec['times']:
                due = local_instants(start, clock, zone)
                if due is not None and due not in existing and due >= spec['activated_at']:
                    db.add(put(Dose(user_id=user_id, schedule_id=row.id, due_at=due,
                                    status='missed' if due < timestamp - 7200 else 'upcoming'),
                               {'medicine': medicine, 'timezone': spec['timezone'], 'treatment_id': row.treatment_id}))
                    existing.add(due)
            start += timedelta(days=1)
    # Missed status is conservative, without treatment advice.
    for d in db.scalars(select(Dose).where(Dose.user_id == user_id, Dose.status == 'upcoming', Dose.due_at < timestamp - 7200)):
        d.status = 'missed'
    db.flush()


def quiet_at(timestamp, prefs, zone):
    if not prefs.get('quiet_start') or not prefs.get('quiet_end'):
        return False
    clock = datetime.fromtimestamp(timestamp, ZoneInfo(zone)).strftime('%H:%M')
    start, end = prefs['quiet_start'], prefs['quiet_end']
    return start <= clock < end if start < end else clock >= start or clock < end


def deactivate_schedules(db, treatment_id):
    for s in db.scalars(select(Schedule).where(Schedule.treatment_id == treatment_id, Schedule.active.is_(True))):
        s.active = False
        # Keep every past dose and correction event. Future queue entries are cancelled.
        for dose in db.scalars(select(Dose).where(Dose.schedule_id == s.id, Dose.due_at > now(), Dose.status == 'upcoming')):
            dose.status = 'cancelled'
