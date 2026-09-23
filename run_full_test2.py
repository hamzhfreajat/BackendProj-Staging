import json
import ssl
import urllib.request
import concurrent.futures
import sys

sys.stdout.reconfigure(encoding='utf-8')
API_KEY = 'sk-d70f1158a91947fa862264807089090a'

with open('final_queries_complex.txt', 'r', encoding='utf-8') as f:
    queries = [line.strip() for line in f if line.strip() and not line.startswith('let us')]

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
    "min_price_number": integer or null,
    "max_price_number": integer or null,
    "floor_word": "MUST be exactly one of: [تسوية, ارضي, اول, ثاني, ثالث, رابع, خامس, سادس, روف] or null",
    "floor_number": integer or null (e.g. -1 for تسوية, 0 for ارضي, 1 for اول),
    "min_area_number": integer or null,
    "max_area_number": integer or null,
    "rent_period": "MUST be exactly one of: [يومي, أسبوعي, شهري, كل 3 أشهر, كل أربع أشهر, كل 5 أشهر, كل 6 أشهر, سنوي] or null",
    "building_age": "MUST be exactly one of: [0 - 11 شهر, 1 - 5 سنوات, 6 - 9 سنوات, 10 - 19 سنوات, +20 سنة] or null (map 'جديد' to '0 - 11 شهر', 'قديم' to '+20 سنة')",
    "interface": "MUST be exactly one of: [شمالية, جنوبية, شرقية, غربية, شمالية شرقية, شمالية غربية, جنوبية شرقية, جنوبية غربية] or null",
    "nearby_locations": ["Subset of EXACT strings: [بنك / صراف آلي, دراي كلين, سوبر ماركت, صالة رياضية / جيم, صيدلية, محطة باصات, مدرسة, مستشفى, مسجد, مطعم]"],
    "main_features": ["Subset of EXACT strings: [تكييف مركزي, تدفئة, شرفة / بلكونة, غرفة خادمة, غرفة غسيل, خزائن حائط, مسبح خاص, سخان شمسي, زجاج شبابيك مزدوج]"],
    "extra_features": ["Subset of EXACT strings: [يوجد مصعد, موقف سيارات, حارس / أمن وحماية, نظام كهرباء احتياطي للطوارئ, انتركم, حديقة, كراج تفك, منطقة شواء, بركة سباحة]"]
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
            res_raw = json.loads(r.read().decode('utf-8'))
            usage = res_raw.get('usage', {})
            content = json.loads(res_raw['choices'][0]['message']['content'])
            return {"content": content, "usage": usage}
    except Exception as e:
        return {"error": str(e)}

results = []
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(lambda q: (q, extract(q)), q) for q in queries]
    for future in concurrent.futures.as_completed(futures):
        results.append(future.result())

xls_path = 'C:/Users/hfraijat/.gemini/antigravity/brain/696fb396-0dce-4ae5-a16f-7a3bb2cd2761/full_test_results_2.xls'

html = '''<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns="http://www.w3.org/TR/REC-html40">
<head><meta http-equiv="Content-type" content="text/html;charset=utf-8" /></head><body><table border="1">'''

headers = ["Query", "Intent", "Property", "Transaction", "Locations", "Min Price", "Max Price", "Min Area", "Max Area", "Beds", "Baths", "Furnished", "Floor Word", "Floor Num", "Rent Period", "Building Age", "Interface", "Nearby", "Main Features", "Extra Features", "Prompt Tokens", "Completion Tokens", "Total Tokens"]

html += "<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>\n"

for q, res in results:
    if "error" in res:
        row = [q, "ERROR"] + ["-"] * (len(headers) - 2)
    else:
        c = res.get('content', {})
        u = res.get('usage', {})
        f = c.get('raw_filters', {})
        
        row = [
            q,
            c.get('intent', '-'),
            f.get('property_type') or '-',
            f.get('transaction') or '-',
            ', '.join(f.get('locations', [])) if f.get('locations') else '-',
            f.get('min_price_number') or '-',
            f.get('max_price_number') or '-',
            f.get('min_area_number') or '-',
            f.get('max_area_number') or '-',
            f.get('bedrooms_number') or '-',
            f.get('bathrooms_number') or '-',
            f.get('furnishing_word') or '-',
            f.get('floor_word') or '-',
            f.get('floor_number') if f.get('floor_number') is not None else '-',
            f.get('rent_period') or '-',
            f.get('building_age') or '-',
            f.get('interface') or '-',
            ', '.join(f.get('nearby_locations', [])) if f.get('nearby_locations') else '-',
            ', '.join(f.get('main_features', [])) if f.get('main_features') else '-',
            ', '.join(f.get('extra_features', [])) if f.get('extra_features') else '-',
            u.get('prompt_tokens', '-'),
            u.get('completion_tokens', '-'),
            u.get('total_tokens', '-')
        ]
    html += "<tr>" + "".join(f"<td>{col}</td>" for col in row) + "</tr>\n"

html += "</table></body></html>"

with open(xls_path, 'w', encoding='utf-8') as file:
    file.write(html)
    
print("Tokens info:")
total_prompt = sum([res.get('usage', {}).get('prompt_tokens', 0) for q, res in results if "error" not in res])
total_completion = sum([res.get('usage', {}).get('completion_tokens', 0) for q, res in results if "error" not in res])
count = len([res for q, res in results if "error" not in res])
print(f"Total queries: {count}")
print(f"Avg prompt tokens: {total_prompt / count if count else 0}")
print(f"Avg completion tokens: {total_completion / count if count else 0}")
print(f"Avg total tokens: {(total_prompt + total_completion) / count if count else 0}")
