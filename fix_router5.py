import re

with open('smart_search_router.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = re.sub(r'def map_category_smart\(.*?\n\s+return base_v', '', code, flags=re.DOTALL)

with open('smart_search_router.py', 'w', encoding='utf-8') as f:
    f.write(code)
