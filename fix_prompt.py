import re

with open('smart_search_router.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_prompt = r'"transaction": "Extract transaction type \(e\.g\..*?\)",'
new_prompt = r'"transaction": "MUST be \'sale\' if buying/selling, \'rent\' if renting, or null if the user did not specify.",'

content = re.sub(old_prompt, new_prompt, content)

with open('smart_search_router.py', 'w', encoding='utf-8') as f:
    f.write(content)
