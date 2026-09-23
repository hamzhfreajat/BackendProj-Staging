import sys
from database import SessionLocal
from market_analysis_service import MarketAnalysisService
import models

def main():
    db = SessionLocal()
    try:
        for ad_id in [27807, 44356]:
            print(f"Calculating specific ad {ad_id}...")
            sys.stdout.flush()
            MarketAnalysisService.calculate_and_save(ad_id, db)
            ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
            if ad:
                print(f"Result for {ad_id}: {ad.market_price_status}")
            sys.stdout.flush()
    finally:
        db.close()

if __name__ == '__main__':
    main()
