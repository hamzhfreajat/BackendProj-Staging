from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import models

engine = create_engine('postgresql://postgres:postgres@localhost:5433/sooqcom_staging')
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

query = db.query(models.AdSearchIndex)
query = query.join(models.Ad, models.AdSearchIndex.ad_id == models.Ad.id)
print(query.statement)
