import re

with open('smart_search_router.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_ai = '''    # STEP 1: AI Entity Extraction
    ai_response = extract_raw_data_via_deepseek(request.text, categories_str=categories_str)'''

new_ai = '''    # STEP 1: AI Entity Extraction
    print("CATEGORIES SENT TO AI:", categories_str)
    ai_response = extract_raw_data_via_deepseek(request.text, categories_str=categories_str)'''

code = code.replace(old_ai, new_ai)

with open('smart_search_router.py', 'w', encoding='utf-8') as f:
    f.write(code)
