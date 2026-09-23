import re

with open('smart_search_router.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Update smart_voice_search to fetch categories
old_func = '''def smart_voice_search(request: SmartSearchRequest, db: Session = Depends(get_db)):
    try:
        # 1. Extract raw data
        raw = extract_raw_data_via_deepseek(request.text)'''

new_func = '''def smart_voice_search(request: SmartSearchRequest, db: Session = Depends(get_db)):
    try:
        import models
        # Fetch real estate categories
        cats = db.query(models.Category).filter(models.Category.parent_id.in_([2, 3])).all()
        cat_mapping = [f"ID: {c.id}, Name: {c.name}" for c in cats]
        categories_str = "\\n".join(cat_mapping)
        
        # 1. Extract raw data
        raw = extract_raw_data_via_deepseek(request.text, categories_str=categories_str)'''

code = code.replace(old_func, new_func)

# 2. Update smart_voice_search to use extracted category_id and remove map_category_smart
old_map = '''        category_id = map_category_smart(
            raw_filters.get("property_type"), 
            raw_filters.get("transaction")
        )'''

new_map = '''        category_id = raw_filters.get("category_id")'''

code = code.replace(old_map, new_map)

with open('smart_search_router.py', 'w', encoding='utf-8') as f:
    f.write(code)
