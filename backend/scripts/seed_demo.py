from app.db import SessionLocal
from app.demo import seed

with SessionLocal() as db:
    seed(db)
    db.commit()
print('Synthetic demonstration catalogue seeded')
