import json
import ssl
import urllib.request
import sys

sys.stdout.reconfigure(encoding='utf-8')
API_KEY = 'sk-d70f1158a91947fa862264807089090a'

def extract(text):
    url = 'https://api.deepseek.com/chat/completions'
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {API_KEY}'}
    
    system_prompt = f"""You are a helpful NLP assistant. Extract entities from Jordanian real estate search queries.
Do NOT guess or correct anything. Output exactly what the user said in the specified JSON fields.

Intent mapping:
- "search": Looking for properties
- "post_ad": Wants to sell or rent out their own property

Output JSON format:
{{
  "intent": "search" | "post_ad",
  "raw_filters": {{
    "property_type": "Extract property type (e.g. شقة, فيلا)",
    "transaction": "Extract transaction type (e.g. للبيع, ايجار)",
    "locations": ["Array of location names"],
    "bedrooms_number": integer or null,
    "bathrooms_number": integer or null,
    "furnishing_word": "Extract word indicating furniture (e.g. معشية, فاضية)",
    "min_price_number": integer or null (e.g. extract numeric value for min price),
    "max_price_number": integer or null (e.g. extract numeric value for max price),
    "floor_word": "Extract floor mentioned (e.g. ارضي, تسوية)",
    "floor_number": integer or null (e.g. 0 for ground, 1 for first),
    "min_area_number": integer or null,
    "max_area_number": integer or null,
    "rent_period": "Extract rent period (e.g. سنوي, شهري, يومي)",
    "building_age": "Extract building age/status (e.g. جديد, شبه جديد, قديم)",
    "interface": "Extract interface/direction (e.g. شمالية, جنوبية)",
    "nearby_locations": ["Array of nearby landmarks/services (e.g. جامعة الأردنية, الدوار السابع, مدارس, ATM)"],
    "features": ["Extract extra features."]
  }}
}}"""

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.0
    }
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            res = json.loads(r.read().decode('utf-8'))
            return json.loads(res['choices'][0]['message']['content'])
    except Exception as e:
        return {"error": str(e)}

query = "بدي شقة ارضية بالياسمين ايجار سنوي شبه جديدة مع واجهة شمالية وقريبة من ال ATM وبسعر لحد 300"
res = extract(query)
with open('C:/Users/hfraijat/.gemini/antigravity/brain/696fb396-0dce-4ae5-a16f-7a3bb2cd2761/explicit_test.json', 'w', encoding='utf-8') as f:
    json.dump({"query": query, "res": res}, f, ensure_ascii=False, indent=2)
