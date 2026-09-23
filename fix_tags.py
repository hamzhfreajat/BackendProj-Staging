import re

with open('smart_search_router.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_search = '''def smart_voice_search(request: SmartSearchRequest, db: Session = Depends(get_db)):
    # Fetch ONLY leaf categories under real estate (IDs 2 and 3)
    try:'''

new_search = '''def smart_voice_search(request: SmartSearchRequest, db: Session = Depends(get_db)):
    # Fetch valid tags
    try:
        valid_tags_objs = db.query(models.Tag).all()
        valid_tags = [t.name for t in valid_tags_objs if t.name]
    except Exception:
        valid_tags = []

    # Fetch ONLY leaf categories under real estate (IDs 2 and 3)
    try:'''

code = code.replace(old_search, new_search)

with open('smart_search_router.py', 'w', encoding='utf-8') as f:
    f.write(code)
