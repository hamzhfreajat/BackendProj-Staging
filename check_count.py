from database import SessionLocal
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
        print(f"Total matching ads in query: {query.count()}")
    finally:
        db.close()

if __name__ == '__main__':
    main()
