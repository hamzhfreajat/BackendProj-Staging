import os
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import models
from dotenv import load_dotenv

load_dotenv()

db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "5433")
db_name = os.getenv("DB_NAME", "cmnynjgg90003aumlerff4j9q")
db_user = os.getenv("DB_USER", "cmnynjgg70001aumle0zkfovm")
db_password = os.getenv("DB_PASSWORD", "p2j9ggm6cWLAhhVTsbNzYFqKHamzaFraijat")

DATABASE_URL = f"postgresql+psycopg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_tree():
    db = SessionLocal()
    categories = db.query(models.Category).all()
    
    def build_tree(parent_id, depth=1):
        tree = {}
        children = [c for c in categories if c.parent_id == parent_id]
        for child in children:
            sub = build_tree(child.id, depth + 1)
            tree[child.name] = sub if sub else None
        return tree

    final_tree = {
        "عقارات للبيع": build_tree(2, 1),
        "عقارات للإيجار": build_tree(3, 1),
    }
    
    with open('tree.json', 'w', encoding='utf-8') as f:
        json.dump(final_tree, f, ensure_ascii=False, indent=2)

get_tree()
