import re

with open('smart_search_router.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = re.sub(r'# 1\. Require Transaction Type.*?category_id = map_category_smart\(.*?\)', 'category_id = raw.get("category_id")', code, flags=re.DOTALL)

with open('smart_search_router.py', 'w', encoding='utf-8') as f:
    f.write(code)
