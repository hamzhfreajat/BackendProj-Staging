from database import SessionLocal
import models
from sqlalchemy import func

def main():
    db = SessionLocal()
    try:
        counts = db.query(models.Ad.market_price_status, func.count(models.Ad.id)) \
                   .group_by(models.Ad.market_price_status).all()
        for status, count in counts:
            print(f"{status}: {count}")
    finally:
        db.close()

if __name__ == '__main__':
    main()
