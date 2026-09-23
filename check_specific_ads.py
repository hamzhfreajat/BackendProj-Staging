from database import SessionLocal
import models
db = SessionLocal()
try:
    for ad_id in [27807, 44356]:
        ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
        if ad:
            print(f"Ad {ad_id}: status={ad.market_price_status}, comps={ad.comparables_count}")
        else:
            print(f"Ad {ad_id} not found")
finally:
    db.close()
