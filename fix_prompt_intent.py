import re

with open('smart_search_router.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_intent = '''Intent mapping:
- search: Looking for properties
- post_ad: Wants to sell or rent out their own property'''

new_intent = '''Intent mapping:
- search: Looking for properties (e.g. "????? ??? ?????", "??? ??????", "?????")
- post_ad: Wants to sell or rent out their own property (e.g. "???? ??? ?????", "??? ???? ????")'''

code = code.replace(old_intent, new_intent)

with open('smart_search_router.py', 'w', encoding='utf-8') as f:
    f.write(code)
