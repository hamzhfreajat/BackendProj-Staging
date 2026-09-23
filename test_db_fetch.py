from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import models

engine = create_engine('postgresql://postgres:postgres@localhost:5433/sooqcom_staging')
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

all_cats = db.query(models.Category).all()

descendants = []
current_parents = [2, 3]
while current_parents:
    children = [c for c in all_cats if c.parent_id in current_parents]
    descendants.extend(children)
    current_parents = [c.id for c in children]
    
parent_ids = {c.parent_id for c in all_cats if c.parent_id is not None}
leaf_cats = [c for c in descendants if c.id not in parent_ids]

cat_mapping = [f"ID: {c.id}, Name: {c.name}" for c in leaf_cats]
categories_str = "\n".join(cat_mapping)
print(categories_str[:200])
