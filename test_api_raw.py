import urllib.request, json, ssl

text = "محتاج شقة بمناطق عمان الغربية (خلدا السابع البنيات وما حولها ) او جبيهة وضاحية الرشيد لغاية ٥٥ الف والدفع كاش مستعجل للبيع"

payload = json.dumps({"text": text}).encode('utf-8')
req = urllib.request.Request(
    "https://staging.sooq-com.com/api/smart-voice-search", 
    data=payload, 
    headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

with urllib.request.urlopen(req, context=ctx) as r:
    response = json.loads(r.read().decode('utf-8'))
    print(json.dumps(response, indent=2, ensure_ascii=True))
