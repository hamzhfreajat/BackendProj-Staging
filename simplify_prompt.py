import re

with open("smart_search_router.py", "r", encoding="utf-8") as f:
    source = f.read()

# I will replace the massive Cities and Regions list with a simpler one,
# BUT I will keep the Category Tree because it's only ~80 lines and very structured.

pattern = re.compile(r'- city: City name in Arabic.*?Cities and Regions \(Use ONLY these exact names\):.*?(?=\n\nNote: If the user says)', re.DOTALL)

replacement = """- city: City name in Arabic (e.g. عمان، إربد، الزرقاء، العقبة، مادبا، جرش، عجلون، الكرك، الطفيلة، معان، المفرق، البلقاء).
- region: Neighborhood/area name in Arabic (e.g. الجاردنز، خلدا، عبدون، الحصن، الصريح)."""

new_source = pattern.sub(replacement, source)

with open("smart_search_router.py", "w", encoding="utf-8") as f:
    f.write(new_source)
