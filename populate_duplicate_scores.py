import sys
import logging
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Ad
from duplicate_detection_router import check_duplicates
from fastapi import HTTPException

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def run():
    db = SessionLocal()
    try:
        last_id = 0
        total_processed = 0
        
        while True:
            db = SessionLocal()
            try:
                # Fetch a batch of 500 ads
                batch_ids = [r[0] for r in db.query(Ad.id).filter(
                    Ad.id > last_id,
                    Ad.duplicate_status.is_(None)
                ).order_by(Ad.id.asc()).limit(500).all()]
            except Exception as e:
                logger.error(f"Error fetching batch: {e}")
                db.close()
                break
                
            db.close()
            
            if not batch_ids:
                break
                
            for ad_id in batch_ids:
                db = SessionLocal()
                try:
                    check_duplicates(ad_id, db)
                    total_processed += 1
                    if total_processed % 50 == 0:
                        logger.info(f"Processed {total_processed} ads so far...")
                except HTTPException as e:
                    logger.warning(f"Ad #{ad_id} skipped: {e.detail}")
                except Exception as e:
                    logger.error(f"Error processing Ad #{ad_id}: {e}")
                finally:
                    db.close()
            
            last_id = batch_ids[-1]
            
        logger.info(f"Done processing all ads. Total processed: {total_processed}")
    except Exception as e:
        logger.error(f"Script failed: {e}")

if __name__ == "__main__":
    run()
