import re

with open('smart_search_router.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_locations = '''    "locations": ["Array of location names"],'''
new_locations = '''    "locations": ["Extract ALL specific location names mentioned exactly as written (e.g. ????, ??????, ???????, ?????)"],'''

code = code.replace(old_locations, new_locations)

old_features = '''    "features": ["Extract any extra features/amenities as a list of strings"]'''
new_features = '''    "features": ["Extract EXACTLY the features mentioned in the text. Do NOT guess or infer features that are not explicitly stated."]'''

code = code.replace(old_features, new_features)

with open('smart_search_router.py', 'w', encoding='utf-8') as f:
    f.write(code)
