import sys
import logging
logging.basicConfig(level=logging.DEBUG)

from database import SessionLocal
from duplicate_detection_router import check_duplicates

db = SessionLocal()
try:
    print("Testing check_duplicates...")
    results = check_duplicates(27807, db)
    print(f"Found {len(results)} duplicates")
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    db.close()
