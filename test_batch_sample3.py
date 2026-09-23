import sys
from database import SessionLocal
import models
from market_analysis_service import MarketAnalysisService
import logging

logger = logging.getLogger('market_analysis_service')
logger.setLevel(logging.CRITICAL)

def main():
    db = SessionLocal()
    try:
        ads = db.query(models.Ad).filter(models.Ad.is_published == True, models.Ad.price.isnot(None), models.Ad.price > 1000).order_by(models.Ad.id.desc()).limit(10).all()
        
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
