import os
os.environ['DEEPSEEK_API_KEY'] = 'sk-d70f1158a91947fa862264807089090a'
from smart_search_router import extract_raw_data_via_deepseek
try:
    print(extract_raw_data_via_deepseek("بدي شقة للبيع في خلدا"))
except Exception as e:
    print(f"Error: {e}")
