import json
import urllib.request
import ssl

url = 'https://staging.sooq-com.com/api/smart-voice-search'
headers = {'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(url, data=json.dumps({'text': "بدي شقة مفروشة غرفتين للايجار سنوي مساحتها من 100 ل 150 متر مع حديقة وواجهة شمالية"}).encode('utf-8'), headers=headers, method='POST')
try:
    with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
        res = json.loads(r.read().decode('utf-8'))
        with open('C:/Users/hfraijat/.gemini/antigravity/brain/696fb396-0dce-4ae5-a16f-7a3bb2cd2761/api_test_out.json', 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
except Exception as e:
    with open('C:/Users/hfraijat/.gemini/antigravity/brain/696fb396-0dce-4ae5-a16f-7a3bb2cd2761/api_test_out.json', 'w', encoding='utf-8') as f:
        f.write(str(e))
