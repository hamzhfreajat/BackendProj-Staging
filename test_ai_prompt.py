import json
import urllib.request
import os
from dotenv import load_dotenv

load_dotenv()

with open('smart_search_router.py', 'r', encoding='utf-8') as f:
    source = f.read()
    
# Extract system prompt from router
import re
prompt_match = re.search(r'system_prompt = """(.*?)"""', source, flags=re.DOTALL)
if prompt_match:
    system_prompt = prompt_match.group(1)
else:
    print("Could not find system prompt in file")
    exit(1)

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
    content = result["choices"][0]["message"]["content"]
    with open('ai_test_result.json', 'w', encoding='utf-8') as out:
        out.write(content)
