from database import SessionLocal
import models
import json

db = SessionLocal()

phone = "0782001546"

# Let's search inside description or attributes
ads = db.query(models.Ad).filter(
    (models.Ad.description.like(f'%{phone}%')) |
    (models.Ad.raw_description.like(f'%{phone}%')) |
    (models.Ad.attributes.cast(models.String).like(f'%{phone}%'))
).limit(10).all()

print(f"Found {len(ads)} ads matching phone number.")

for ad in ads:
    print(f"Ad ID: {ad.id}, Source: {ad.source_type}, User ID: {ad.user_id}")

