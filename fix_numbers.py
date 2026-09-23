import re

with open('smart_search_router.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Remove max_price_number and min_price_number from deepseek prompt
code = re.sub(r'\s*"min_price_number": integer or null,', '', code)
code = re.sub(r'\s*"max_price_number": integer or null,', '', code)
code = re.sub(r'\s*"bedrooms_number": integer or null,', '', code)
code = re.sub(r'\s*"bathrooms_number": integer or null,', '', code)
code = re.sub(r'\s*"min_area_number": integer or null,', '', code)
code = re.sub(r'\s*"max_area_number": integer or null,', '', code)

# Remove the python logic that overwrites it
old_price = '''    min_price = parse_price(raw.get("min_price_word"))
    if raw.get("min_price_number") is not None:
        min_price = raw.get("min_price_number")
        
    max_price = parse_price(raw.get("max_price_word"))
    if raw.get("max_price_number") is not None:
        max_price = raw.get("max_price_number")'''

new_price = '''    min_price = parse_price(raw.get("min_price_word"))
    max_price = parse_price(raw.get("max_price_word"))'''

code = code.replace(old_price, new_price)

with open('smart_search_router.py', 'w', encoding='utf-8') as f:
    f.write(code)
