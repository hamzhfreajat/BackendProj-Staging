from database import SessionLocal
import models

db = SessionLocal()
users = db.query(models.User).filter(
    (models.User.mobile_number.like('%782001546%')) |
    (models.User.phone.like('%782001546%'))
).all()

for u in users:
    print(f"ID: {u.id}, Mobile: {u.mobile_number}, Phone: {u.phone}")
