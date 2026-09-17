from market_analysis_service import MarketAnalysisService
from database import SessionLocal
import models

def main():
    print('Connecting to database via tunnel...')
    db = SessionLocal()
    try:
        # Check connection
        test = db.query(models.Ad).first()
        if not test:
            print("DB Connected but no ads found.")
            return
            
        print('Connection successful! Starting market analysis batch for NATIVE (Organic) ads only...')
        MarketAnalysisService.run_batch(db, incremental=False, dry_run=False)
        print('Finished!')
    except Exception as e:
        print(f"Error connecting: {e}")
    finally:
        db.close()

if __name__ == '__main__':
    main()
