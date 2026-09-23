import urllib.request, json, ssl

text = "??? ??????? ?? ????"

payload = json.dumps({"text": text}).encode('utf-8')
req = urllib.request.Request(
    "https://staging.sooq-com.com/api/smart-voice-search", 
    data=payload, 
    headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

try:
    with urllib.request.urlopen(req, context=ctx) as r:
        response = json.loads(r.read().decode('utf-8'))
        print(json.dumps(response, indent=2, ensure_ascii=True))
except urllib.error.HTTPError as e:
    print(f"HTTPError: {e.code}")
    print(e.read().decode('utf-8'))
except Exception as e:
    print(e)
