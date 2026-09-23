import re

with open('smart_search_router.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_map = '''def map_category_smart(raw_prop: str, raw_trans: str) -> Optional[int]:
    if not raw_prop: return None
    prop_norm = raw_prop.lower()
    is_rent = (raw_trans == 'rent') if raw_trans else False
    base_v = None
    for k, v in CATEGORY_SYNONYMS.items():
        if k in prop_norm:
            base_v = v
            break
    if base_v is None: return None
    if is_rent:
        if base_v == 201: return 301
        if base_v == 2015: return 3015
        if base_v == 2016: return 302
        if base_v == 202: return 313
        if base_v == 2031: return 316
        if base_v == 204: return 303
        if base_v == 2051: return 314
        if base_v == 2052: return 315
        if base_v == 2061: return 316
    return base_v'''

start = code.find("def map_category_smart")
end = code.find("prop_norm = raw_prop.lower()", start + 100)
end = code.find("return None", end) + len("return None")

code = code[:start] + new_map + code[end:]

with open('smart_search_router.py', 'w', encoding='utf-8') as f:
    f.write(code)