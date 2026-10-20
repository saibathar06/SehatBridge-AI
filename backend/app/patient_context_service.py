from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select
from .models import Treatment, Dose, Profile
from .security import read
from .scheduling import materialize


def patient_context(db, user_id):
    materialize(db, user_id)
    profile = read(db.scalar(select(Profile).where(Profile.user_id == user_id)))
    zone = ZoneInfo(profile['timezone'])
    midnight = datetime.now(zone).replace(hour=0, minute=0, second=0, microsecond=0)
    plans = db.scalars(select(Treatment).where(Treatment.user_id == user_id, Treatment.status == 'active')).all()
    doses = db.scalars(select(Dose).where(Dose.user_id == user_id, Dose.due_at >= midnight.timestamp(),
                          Dose.due_at < (midnight + timedelta(days=1)).timestamp(), Dose.status != 'cancelled').order_by(Dose.due_at)).all()
    return {'profile': profile, 'plans': [{'id': t.id, 'document_id': t.document_id, **read(t)} for t in plans],
            'doses': [{'id': d.id, 'due_at': d.due_at, 'status': d.status, **read(d)} for d in doses]}
