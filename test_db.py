from database import SessionLocal
import models
db = SessionLocal()
try:
    c = db.query(models.Ad).filter(models.Ad.market_price_status == 'BELOW_MARKET').count()
    print('Below market count:', c)
except Exception as e:
    print('Error:', e)
