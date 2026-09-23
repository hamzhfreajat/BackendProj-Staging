import json
import ssl
import urllib.request
import concurrent.futures
import sys

sys.stdout.reconfigure(encoding='utf-8')
API_KEY = 'sk-d70f1158a91947fa862264807089090a'
valid_tags = ["ايجار سنوي", "حديقة", "واجهة شمالية", "كراج", "مطبخ راكب", "بلكونة", "مفروشة", "مصعد", "روف", "من المالك", "بدون عمولة", "غرفة خادمة", "غرفة غسيل", "مستودع", "تراس", "دوبلكس", "مكيف", "مسبح"]

with open('test_queries.txt', 'r', encoding='utf-8') as f:
    queries = [line.strip() for line in f if line.strip()]

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
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(lambda q: (q, extract(q)), q) for q in queries]
    for future in concurrent.futures.as_completed(futures):
        results.append(future.result())

with open('C:/Users/hfraijat/.gemini/antigravity/brain/696fb396-0dce-4ae5-a16f-7a3bb2cd2761/ai_batch_md.md', 'w', encoding='utf-8') as md:
    md.write('| Query | Intent | Property | Transaction | Locations | Area (Min-Max) | Beds | Baths | Furnished | Floor | Features |\n')
    md.write('|---|---|---|---|---|---|---|---|---|---|---|\n')
    
    for q, res in results:
        if "error" in res:
            md.write(f'| {q} | ERROR | - | - | - | - | - | - | - | - | - |\n')
            continue
            
        f = res.get('raw_filters', {})
        intent = res.get('intent', '-')
        
        prop = f.get('property_type') or '-'
        tran = f.get('transaction') or '-'
        locs = ', '.join(f.get('locations', [])) if f.get('locations') else '-'
        
        min_a = f.get('min_area_number') or '-'
        max_a = f.get('max_area_number') or '-'
        area = f"{min_a} - {max_a}"
        
        beds = f.get('bedrooms_number') or '-'
        baths = f.get('bathrooms_number') or '-'
        furn = f.get('furnishing_word') or '-'
        floor = f.get('floor_word') or '-'
        
        tags = ', '.join(f.get('features', [])) if f.get('features') else '-'
        
        md.write(f'| {q} | {intent} | {prop} | {tran} | {locs} | {area} | {beds} | {baths} | {furn} | {floor} | {tags} |\n')
