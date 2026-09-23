import json

with open('smart_search_router.py', 'r', encoding='utf-8') as f:
    content = f.read()
    
with open('res.txt', 'w', encoding='utf-8') as f:
    f.write(str("الجاردنز" in content))
