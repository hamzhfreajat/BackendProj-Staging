import re

with open('smart_search_router.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_return = '''    return SmartSearchResponse(
        intent=intent,
        result_count=result_count,
        filters_applied=filters,
        suggestion=suggestion,
        alternative_count=alternative_count,
        alternative_filters=alternative_filters,
        action_required=action_required
    )'''

new_return = '''    return SmartSearchResponse(
        intent=intent,
        result_count=result_count,
        filters_applied={"raw_ai": raw, **filters},
        suggestion=suggestion,
        alternative_count=alternative_count,
        alternative_filters=alternative_filters,
        action_required=action_required
    )'''

code = code.replace(old_return, new_return)

with open('smart_search_router.py', 'w', encoding='utf-8') as f:
    f.write(code)
