import re

with open('smart_search_router.py', 'r', encoding='utf-8') as f:
    code = f.read()

endpoint = '''
@router.get("/api/debug-cats")
def debug_cats(db: Session = Depends(get_db)):
    try:
        all_cats = db.query(models.Category).all()
        
        descendants = []
        current_parents = [2, 3] # Real Estate Sale & Rent
        
        while current_parents:
            children = [c for c in all_cats if c.parent_id in current_parents]
            descendants.extend(children)
            current_parents = [c.id for c in children]
            
        parent_ids = {c.parent_id for c in all_cats if c.parent_id is not None}
        leaf_cats = [c for c in descendants if c.id not in parent_ids]
        
        cat_mapping = [f"ID: {c.id}, Name: {c.name}" for c in leaf_cats]
        categories_str = "\\n".join(cat_mapping)
        return {"cats": categories_str}
    except Exception as e:
        return {"error": str(e)}
'''

if 'debug_cats' not in code:
    code += endpoint

with open('smart_search_router.py', 'w', encoding='utf-8') as f:
    f.write(code)
