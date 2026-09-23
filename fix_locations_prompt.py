import re

with open('smart_search_router.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_loc = '''    "locations": ["Extract ALL specific location names mentioned exactly as written (e.g. ????, ??????, ???????, ?????)"],'''
new_loc = '''    "locations": ["Extract ALL location names, regions, or cities mentioned in the text as a list of strings"],'''

code = code.replace(old_loc, new_loc)

with open('smart_search_router.py', 'w', encoding='utf-8') as f:
    f.write(code)
