with open('smart_search_router.py', 'r', encoding='utf-8') as f: code = f.read()
code = code.replace('if bedrooms:', 'if applied_filters.get(\"bedrooms\") is not None:')
with open('smart_search_router.py', 'w', encoding='utf-8') as f: f.write(code)
