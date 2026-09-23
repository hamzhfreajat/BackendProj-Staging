import os
os.environ['DEEPSEEK_API_KEY'] = 'sk-d70f1158a91947fa862264807089090a'
from smart_search_router import smart_voice_search, SmartSearchRequest
from database import SessionLocal
import json

db = SessionLocal()
req = SmartSearchRequest(text="بدي شقة للبيع في خلدا")
try:
    res = smart_voice_search(req, db)
    # Output json safely
    with open('ds_output.json', 'w', encoding='utf-8') as f:
        f.write(res.json())
    print("Success")
except Exception as e:
    print(f"Error: {e}")
