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
        # Fetch the most recent 50 ORGANIC_USER ads + the two specific ones they showed!
        print('Fetching recent 20 native ads + the 2 specific ones...')
        
        specific_ads = db.query(models.Ad).filter(models.Ad.id.in_([27807, 44356])).all()
        recent_ads = db.query(models.Ad).filter(
            models.Ad.is_published == True, 
            models.Ad.price.isnot(None),
            models.Ad.source_type == models.SourceType.ORGANIC_USER
        ).order_by(models.Ad.id.desc()).limit(20).all()
        
        ads = specific_ads + recent_ads
        
        print(f"Calculating market analysis for {len(ads)} ads...")
        
        count = 0
        for ad in ads:
            MarketAnalysisService.calculate_and_save(ad.id, db)
            count += 1
            print(f"Processed Ad {ad.id} (Status: {ad.market_price_status})")
            sys.stdout.flush()
                
        print('Finished processing small batch! The user can now refresh the dashboard.')
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == '__main__':
    main()
