import re

with open('smart_search_router.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Replace category fetch logic
new_fetch = '''        # Fetch ONLY leaf categories under real estate (IDs 2 and 3)
        all_cats = db.query(models.Category).all()
        
        descendants = []
        current_parents = [2, 3]
        while current_parents:
            children = [c for c in all_cats if c.parent_id in current_parents]
            descendants.extend(children)
            current_parents = [c.id for c in children]
            
        parent_ids = {c.parent_id for c in all_cats if c.parent_id is not None}
        leaf_cats = [c for c in descendants if c.id not in parent_ids]
        
        cat_mapping = [f"ID: {c.id}, Name: {c.name}" for c in leaf_cats]
        categories_str = "\\n".join(cat_mapping)'''

code = re.sub(r'# Fetch real estate categories.*?categories_str = "\\\n"\.join\(cat_mapping\)', new_fetch, code, flags=re.DOTALL)

# Replace prompt
new_prompt = '''Do NOT guess or correct anything, except for category_id which must be selected from the provided list.
You MUST choose the most specific end-level category from the list. Do NOT choose broad/parent categories.

Intent mapping:'''

code = re.sub(r'Do NOT guess or correct anything, except for category_id which must be selected from the provided list\.\n\nIntent mapping:', new_prompt, code, flags=re.DOTALL)

with open('smart_search_router.py', 'w', encoding='utf-8') as f:
    f.write(code)
