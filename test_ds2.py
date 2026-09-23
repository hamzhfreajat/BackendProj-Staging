import os
os.environ['DEEPSEEK_API_KEY'] = 'sk-d70f1158a91947fa862264807089090a'
from smart_search_router import extract_raw_data_via_deepseek
try:
    import json
    res = extract_raw_data_via_deepseek("شقة للايجار في عمان الطابق الاول او الثاني")
    with open('test_ds.json', 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
except Exception as e:
    print(f"Error: {e}")
