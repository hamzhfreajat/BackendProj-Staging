with open('smart_search_router.py', 'r', encoding='utf-8') as f: code = f.read()
code = code.replace('raw = ai_response.get(\"raw_filters\", {})', 'raw = ai_response.get(\"raw_filters\") or {}')
with open('smart_search_router.py', 'w', encoding='utf-8') as f: f.write(code)
