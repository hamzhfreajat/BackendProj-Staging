import json
import urllib.request
import ssl

queries = [
    "شقة طابق اول للايجار في الياسمين",
    "بدور على شقة مفروشة غرفتين نوم وحمامين في عبدون او دير غبار لحد ٦٠٠",
    "بدي شقة ارضي للايجار مع حديقة غرفتين نوم في الرابية او ام السماق"
]

url = 'https://staging.sooq-com.com/api/smart-voice-search'
headers = {'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

results = []
for q in queries:
    req = urllib.request.Request(url, data=json.dumps({'text': q}).encode('utf-8'), headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
        res = json.loads(r.read().decode('utf-8'))
        results.append({
            "query": q,
            "filters": res.get("filters_applied", {})
        })

with open('C:/Users/hfraijat/.gemini/antigravity/brain/696fb396-0dce-4ae5-a16f-7a3bb2cd2761/sample_results.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
