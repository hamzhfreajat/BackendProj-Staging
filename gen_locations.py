import os
import re
from sqlalchemy import create_engine
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

def update_prompt():
    db = SessionLocal()
    cities = db.query(models.City).all()
    
    locations_str = "Cities and Regions (Use ONLY these exact names):\n"
    for city in cities:
        regions = db.query(models.Region).filter(models.Region.city_id == city.id).all()
        region_names = [r.name_ar for r in regions if r.name_ar]
        locations_str += f"- City: {city.name_ar} | Regions: {', '.join(region_names)}\n"
        
    # Read the router file
    with open("smart_search_router.py", "r", encoding="utf-8") as f:
        source = f.read()
        
    # Replace the city and region part
    old_city_region = r"- city: City name in Arabic \(عمان، إربد، الزرقاء، العقبة، مادبا، جرش، عجلون، الكرك، الطفيلة، معان، المفرق، البلقاء، السلط\)\n- region: Neighborhood/area name in Arabic \(e\.g\., الجاردنز، خلدا، عبدون\)"
    
    new_city_region = f"""- city: City name in Arabic. You MUST choose ONLY from the valid cities list below.
- region: Neighborhood/area name in Arabic. You MUST choose ONLY from the valid regions list below. If the user mentions a region, you can infer the city from the list below.

{locations_str}"""

    # we might need to be careful with regex replacement if it was slightly modified
    # let's find a reliable anchor
    
    anchor_start = "- category: The exact 3rd-level Arabic category name from the list above.\n"
    anchor_end = "\n- min_price: Number"
    
    pattern = re.compile(re.escape(anchor_start) + r"(.*?)" + re.escape(anchor_end), re.DOTALL)
    
    replacement = anchor_start + new_city_region + anchor_end
    
    new_source = pattern.sub(replacement.replace('\\', r'\\'), source)
    
    with open("smart_search_router.py", "w", encoding="utf-8") as f:
        f.write(new_source)

update_prompt()
