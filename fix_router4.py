import re

with open('smart_search_router.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace('category_id = raw.get("category_id"), raw.get("transaction"))', 'category_id = raw.get("category_id")')

with open('smart_search_router.py', 'w', encoding='utf-8') as f:
    f.write(code)
