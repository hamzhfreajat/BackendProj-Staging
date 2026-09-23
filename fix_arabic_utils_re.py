import re

with open('arabic_utils.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_price = '''def parse_price(price_val) -> int:
    if not price_val: return None
    text = convert_hindi_numerals(str(price_val)).lower()
    match = re.search(r'\\d+', text)
    if not match: return None
    base_num = int(match.group(0))
    if 'الف' in text or 'ألف' in text or 'k' in text: base_num *= 1000
    elif 'مليون' in text or 'm' in text: base_num *= 1000000
    return base_num'''

code = re.sub(r'def parse_price.*?return base_num', lambda m: new_price, code, flags=re.DOTALL)

with open('arabic_utils.py', 'w', encoding='utf-8') as f:
    f.write(code)
