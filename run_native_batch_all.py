import sys
from database import SessionLocal
import models
from market_analysis_service import MarketAnalysisService
from models import Ad, AdSearchIndex, SourceType

def main():
    db = SessionLocal()
    try:
        query = db.query(Ad).join(AdSearchIndex, Ad.id == AdSearchIndex.ad_id).filter(
            Ad.is_published == True,
            Ad.is_paused == False,
            Ad.is_sold == False,
            Ad.is_rejected == False,
            Ad.price.isnot(None),
            Ad.source_type == SourceType.ORGANIC_USER
        )
        ads = query.all()
        print(f"Starting batch analysis for all {len(ads)} active native ads...")
        sys.stdout.flush()
        
        below = 0
        normal = 0
        nodata = 0
        
        for idx, ad in enumerate(ads):
            MarketAnalysisService.calculate_and_save(ad.id, db)
            db.refresh(ad)
            
            if ad.market_price_status == 'BELOW_MARKET': below += 1
            elif ad.market_price_status == 'NO_DATA': nodata += 1
            else: normal += 1
            
            if (idx + 1) % 10 == 0 or (idx + 1) == len(ads):
                print(f"Processed {idx + 1}/{len(ads)} ads...")
                sys.stdout.flush()
                
        print(f"Finished! Total: {len(ads)} | Below Market: {below} | Normal: {normal} | No Data: {nodata}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == '__main__':
    main()
