import json
import urllib.request
import ssl
import sys

sys.stdout.reconfigure(encoding='utf-8')
API_KEY = 'sk-d70f1158a91947fa862264807089090a'

queries = [
    "بدي شقة مفروشة غرفتين للايجار سنوي مساحتها من 100 ل 150 متر مع حديقة وواجهة شمالية",
    "بدي شقه ايجار بالياسمين غرفتين لحد 250",
    "بدي شقه بالياسمين غرفتين وصالون وكراج",
    "بدي شقة ارضي للايجار مع حديقة غرفتين نوم في الرابية او ام السماق",
    "شقه غرفتين وصالون بالياسمين او الذراع الغربي لحد 230",
    "بدي بيت للايجار ب صويلح حي الفضيله",
    "بدور على شقة مفروشة غرفتين نوم وحمامين في عبدون او دير غبار لحد ٦٠٠",
    "بدي شقه للعيلة بالياسمين ٣ غرف نوم وصالون ومطبخ واسع مع كراج",
    "شقة للبيع بأي منطقة من غرب عمان غرفتين او ٣ غرف مساحتها فوق الـ ١٢٠ متر",
    "بدي شقة ارضية بالياسمين او ضاحية الياسمين ٣ غرف ومطبخ راكب مع حديقة او بلكونة"
]

valid_tags = ["ايجار سنوي", "حديقة", "واجهة شمالية", "كراج", "مطبخ راكب", "بلكونة", "مفروشة"]

def extract(text):
    url = 'https://api.deepseek.com/chat/completions'
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {API_KEY}'}
    
    tags_instruction = f"For 'features', ONLY pick terms that closely match this valid list: [{', '.join(valid_tags)}]\n"
    system_prompt = f"""You are a helpful NLP assistant. Extract entities from Jordanian real estate search queries.
Do NOT guess or correct anything. Output exactly what the user said in the specified JSON fields.

Intent mapping:
- "search": Looking for properties
- "post_ad": Wants to sell or rent out their own property

{tags_instruction}

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
    "max_price_word": "Extract text indicating max price",
    "min_price_word": "Extract text indicating min price",
    "floor_word": "Extract floor mentioned (e.g. ارضي, تسوية)",
    "min_area_number": integer or null (e.g. from 'فوق 120 متر' -> 120),
    "max_area_number": integer or null,
    "features": ["Extract extra features. ONLY select features that exist in the valid tags list above."]
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

results = []
for q in queries:
    res = extract(q)
    results.append({"query": q, "extracted": res})

with open('C:/Users/hfraijat/.gemini/antigravity/brain/696fb396-0dce-4ae5-a16f-7a3bb2cd2761/ai_extraction_test.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
