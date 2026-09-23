with open('smart_search_router.py', 'r', encoding='utf-8') as f: code = f.read()
code = code.replace('if k in raw[\"furnishing_word\"]:', 'if k in str(raw[\"furnishing_word\"]):')
with open('smart_search_router.py', 'w', encoding='utf-8') as f: f.write(code)
