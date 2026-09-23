import json
import urllib.request
import ssl
import sys

url = 'https://staging.sooq-com.com/api/smart-voice-search'
headers = {'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(url, data=json.dumps({'text': "شقة غرفتين وصالون وحمامين مع حديقة بالياسمين"}).encode('utf-8'), headers=headers, method='POST')
try:
    with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
        res = json.loads(r.read().decode('utf-8'))
        print(json.dumps(res, ensure_ascii=False))
except Exception as e:
    print(f"Error: {e}")
