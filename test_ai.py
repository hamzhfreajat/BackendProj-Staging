import json
import urllib.request
import urllib.error
import os
from dotenv import load_dotenv

load_dotenv()

system_prompt = """أنت مساعد ذكي لتطبيق عقارات أردني اسمه "سوق كوم".
مهمتك استخراج الفلاتر:
- category: اسم الفئة (شقق للإيجار، ستوديو للإيجار، الخ)
- city: اسم المدينة (عمان، إربد، الزرقاء، الخ)
- region: الحي (الجاردنز، خلدا، عبدون، الخ)
- max_price: السعر الأعلى

أجب بـ JSON:
{
  "filters": { "category": string, "city": string, "region": string, "max_price": number }
}"""

data = {
    "model": "deepseek-chat",
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "بدي شقه للايجار بالجاردنز اقل من 300 دينار"}
    ],
    "response_format": {"type": "json_object"}
}

req = urllib.request.Request("https://api.deepseek.com/chat/completions", data=json.dumps(data).encode("utf-8"), headers={
    "Content-Type": "application/json",
    "Authorization": f"Bearer {os.getenv('DEEPSEEK_API_KEY')}"
}, method="POST")

with urllib.request.urlopen(req) as response:
    result = json.loads(response.read().decode("utf-8"))
    print(result["choices"][0]["message"]["content"])
