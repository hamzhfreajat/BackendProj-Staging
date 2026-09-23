import json
import urllib.request
import ssl
import sys

# Force UTF-8 stdout
sys.stdout.reconfigure(encoding='utf-8')

url = 'https://staging.sooq-com.com/api/smart-voice-search'
headers = {'Content-Type': 'application/json'}
q = "بدي شقه ايجار بالياسمين غرفتين لحد 250"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

try:
    req = urllib.request.Request(url, data=json.dumps({'text': q}).encode('utf-8'), headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
        print(r.read().decode('utf-8'))
except Exception as e:
    print(f"HTTP ERROR: {e}")
    if hasattr(e, 'read'):
        print(e.read().decode('utf-8'))
