from database import SessionLocal
import models
from market_analysis_service import MarketAnalysisService

def main():
    db = SessionLocal()
    try:
        print('Fetching 50 active ads for a quick sample run over the tunnel...')
        ads = db.query(models.Ad).filter(models.Ad.is_published == True, models.Ad.price.isnot(None)).limit(50).all()
        
        below_market = 0
        no_data = 0
        normal = 0
        
        for ad in ads:
            MarketAnalysisService.calculate_and_save(ad.id, db)
            db.refresh(ad)
            status = ad.market_price_status
            if status == 'BELOW_MARKET':
                below_market += 1
                print(f"Ad {ad.id} (Price: {ad.price}) -> {status} (Dev: {ad.deviation_pct}, Comps: {ad.comparables_count}, Level: {ad.matching_level_used})")
            elif status == 'NO_DATA':
                no_data += 1
            else:
                normal += 1
                
        print(f"\nSample Results (50 ads): BELOW_MARKET: {below_market}, FAIR/ABOVE: {normal}, NO_DATA: {no_data}")
    finally:
        db.close()

if __name__ == '__main__':
    main()
