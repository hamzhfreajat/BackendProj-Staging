import re

with open('smart_search_router.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_data = '''    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        "response_format": {"type": "json_object"}
    }'''

new_data = '''    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.0
    }'''

code = code.replace(old_data, new_data)

with open('smart_search_router.py', 'w', encoding='utf-8') as f:
    f.write(code)
