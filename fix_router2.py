import re

with open('smart_search_router.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Remove the transaction check
old_trans = '''    # 1. Require Transaction Type
    if raw.get("transaction") is None:
        return SmartSearchResponse(
            intent=intent,
            result_count=0,
            filters_applied={},
            suggestion="?? ???? ?? ??? ?? ??????",
            action_required="ask_transaction"
        )
        
    # Category
    category_id = map_category_smart(raw.get("property_type"), raw.get("transaction"))'''

new_trans = '''    # Category
    category_id = raw.get("category_id")'''

code = code.replace(old_trans, new_trans)

with open('smart_search_router.py', 'w', encoding='utf-8') as f:
    f.write(code)
