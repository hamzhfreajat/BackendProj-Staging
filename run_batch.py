import logging
logging.basicConfig(level=logging.INFO)
from market_analysis_service import MarketAnalysisService
from database import SessionLocal

def main():
    print('Starting full market analysis batch...')
    db = SessionLocal()
    try:
        MarketAnalysisService.run_batch(db, incremental=False, dry_run=False)
        print('Finished!')
    finally:
        db.close()

if __name__ == '__main__':
    main()
