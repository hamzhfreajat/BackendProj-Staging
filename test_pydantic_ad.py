from database import SessionLocal
from models import Ad as ModelAd
from schemas import Ad as SchemaAd

db = SessionLocal()
ad = db.query(ModelAd).filter(ModelAd.id == 27807).first()

if ad:
    try:
        schema_ad = SchemaAd.from_orm(ad) # or model_validate for v2
        print(schema_ad.dict())
    except Exception as e:
        print("Error during serialization:")
        print(e)
else:
    print("Ad not found")
