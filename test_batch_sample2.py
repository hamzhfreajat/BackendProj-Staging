import sys
from database import SessionLocal
import models
from market_analysis_service import MarketAnalysisService
import logging

# Disable logger output so we only see our prints
logger = logging.getLogger('market_analysis_service')
logger.setLevel(logging.CRITICAL)

def main():
    db = SessionLocal()
    try:
        print('Fetching some active ads (Real Estate category) from the DB...')
        # category_id 1 is usually Real Estate
        ads = db.query(models.Ad).filter(models.Ad.is_published == True, models.Ad.price.isnot(None), models.Ad.category_id == 1).order_by(models.Ad.id.desc()).limit(15).all()
        
        for ad in ads:
            MarketAnalysisService.calculate_and_save(ad.id, db)
            db.refresh(ad)
            print(f"Ad #{ad.id} (Price {ad.price}): -> {ad.market_price_status} " +
                  f"(Lvl: {ad.matching_level_used}, Conf: {ad.confidence_level}, Comps: {ad.comparables_count}, Median: {ad.market_average_price})")
            sys.stdout.flush()
            
    finally:
        db.close()

if __name__ == '__main__':
    main()
