import re

with open("smart_search_router.py", "r", encoding="utf-8") as f:
    source = f.read()

replacement = """- city: City name in Arabic. You MUST choose ONLY from the valid cities list below.
- region: Neighborhood/area name in Arabic. You MUST choose ONLY from the valid regions list below. If the user mentions a region with prefixes like 'بـ' or 'في' (e.g., "بالجاردنز", "في عبدون"), you MUST extract the exact region name from the list without prefixes (e.g., "الجاردنز", "عبدون")."""

new_source = re.sub(r'- city: City name in Arabic.*?If the user mentions a region, you can infer the city from the list below\.', replacement, source, flags=re.DOTALL)

with open("smart_search_router.py", "w", encoding="utf-8") as f:
    f.write(new_source)
