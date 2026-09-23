import os
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker
import models
from dotenv import load_dotenv

load_dotenv()

db_host = os.getenv('DB_HOST', 'localhost')
db_port = os.getenv('DB_PORT', '5433')
db_name = os.getenv('DB_NAME', 'cmnynjgg90003aumlerff4j9q')
db_user = os.getenv('DB_USER', 'cmnynjgg70001aumle0zkfovm')
db_password = os.getenv('DB_PASSWORD', 'p2j9ggm6cWLAhhVTsbNzYFqKHamzaFraijat')

DATABASE_URL = f'postgresql+psycopg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

region_name = "الجاردنز"

region = db.query(models.Region).filter(
    or_(
        models.Region.name_ar.ilike(f"%{region_name}%"),
        models.Region.name_en.ilike(f"%{region_name}%")
    )
).first()

if region:
    print("Found region:", region.name_ar, region.id)
    city = db.query(models.City).filter(models.City.id == region.city_id).first()
    if city:
        print("City:", city.name_ar, city.id)
else:
    print("Region not found in DB!")
