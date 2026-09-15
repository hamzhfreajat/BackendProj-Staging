from market_analysis_service import MarketAnalysisService
from database import SessionLocal

def main():
    print('Starting market analysis batch for NATIVE (Organic) ads only...')
    db = SessionLocal()
    try:
        # Full scan (incremental=False), actual save (dry_run=False)
        MarketAnalysisService.run_batch(db, incremental=False, dry_run=False)
        print('Finished!')
    finally:
        db.close()

if __name__ == '__main__':
    main()
