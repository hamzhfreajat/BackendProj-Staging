from database import SessionLocal
import models

def run():
    db = SessionLocal()
    try:
        # Mark 45 ads in Amman as BELOW_MARKET
        ads_amman = db.query(models.Ad).filter(models.Ad.location.ilike('????%')).limit(45).all()
        for ad in ads_amman:
            ad.market_price_status = 'BELOW_MARKET'
            
        # Mark 20 ads in Irbid
        ads_irbid = db.query(models.Ad).filter(models.Ad.location.ilike('????%')).limit(20).all()
        for ad in ads_irbid:
            ad.market_price_status = 'BELOW_MARKET'
            
        # Mark 12 in Zarqa
        ads_zarqa = db.query(models.Ad).filter(models.Ad.location.ilike('???????%')).limit(12).all()
        for ad in ads_zarqa:
            ad.market_price_status = 'BELOW_MARKET'
            
        db.commit()
        print(f"Updated {len(ads_amman)} in Amman, {len(ads_irbid)} in Irbid, {len(ads_zarqa)} in Zarqa.")
    except Exception as e:
        db.rollback()
        print("Error:", e)
    finally:
        db.close()

if __name__ == '__main__':
    run()
