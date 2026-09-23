from database import SessionLocal
from models import Ad
db = SessionLocal()
ad = db.query(Ad).filter(Ad.id == 27807).first()
if ad:
    print(f"Ad {ad.id}:")
    print(f"market_price_status: {ad.market_price_status}")
    print(f"comparables_count: {ad.comparables_count}")
    print(f"deviation_pct: {ad.deviation_pct}")
else:
    print("Ad not found")
