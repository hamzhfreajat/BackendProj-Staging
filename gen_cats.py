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

def generate_update():
    db = SessionLocal()
    categories = db.query(models.Category).all()
    
    # roots: 2 (Sale), 3 (Rent)
    tree_str = "Real Estate Category Tree:\n"
    mapping_code = "    mapping = {\n"
    
    def process_level(parent_id, depth, parent_name):
        nonlocal tree_str, mapping_code
        children = sorted([c for c in categories if c.parent_id == parent_id], key=lambda x: x.id)
        for child in children:
            indent = "  " * depth
            tree_str += f"{indent}- Level {depth+1}: {child.name}\n"
            
            # Check if this child has children
            sub_children = [c for c in categories if c.parent_id == child.id]
            if not sub_children:
                # It's a leaf node! Add to mapping
                mapping_code += f'        "{child.name}": {child.id},\n'
            else:
                process_level(child.id, depth + 1, child.name)

    tree_str += "- Level 1: عقارات للبيع\n"
    process_level(2, 1, "عقارات للبيع")
    
    tree_str += "- Level 1: عقارات للإيجار\n"
    process_level(3, 1, "عقارات للإيجار")
    
    mapping_code += "    }\n"
    
    with open("generated_update.txt", "w", encoding="utf-8") as f:
        f.write("=== PROMPT TREE ===\n")
        f.write(tree_str)
        f.write("\n=== MAPPING CODE ===\n")
        f.write(mapping_code)

generate_update()
