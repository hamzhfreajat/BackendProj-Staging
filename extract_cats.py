import os
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import models

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Use staging DB URL
    DATABASE_URL = "postgresql+psycopg://postgres:admin123@localhost:5432/classifieds_db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_tree():
    db = SessionLocal()
    categories = db.query(models.Category).all()
    
    # Real estate roots: 2 (Sale), 3 (Rent), 1 (Cars, skip)
    # Actually let's just get 2 and 3 and maybe lands (10313 under 2)
    
    cat_map = {c.id: c for c in categories}
    
    def build_tree(parent_id, depth=1):
        tree_str = ""
        children = [c for c in categories if c.parent_id == parent_id]
        for child in children:
            indent = "  " * depth
            tree_str += f"{indent}- {child.name} (Level {depth+1})\n"
            tree_str += build_tree(child.id, depth + 1)
        return tree_str

    final_str = "عقارات للبيع (Level 1)\n"
    final_str += build_tree(2, 1)
    final_str += "\nعقارات للإيجار (Level 1)\n"
    final_str += build_tree(3, 1)
    
    return final_str

print(get_tree())
