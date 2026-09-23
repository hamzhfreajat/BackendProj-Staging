import json
import urllib.request
import ssl
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('test_queries.txt', 'r', encoding='utf-8') as f:
    queries = [line.strip() for line in f if line.strip()]

url = 'https://staging.sooq-com.com/api/smart-voice-search'
headers = {
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

with open('C:/Users/hfraijat/.gemini/antigravity/brain/696fb396-0dce-4ae5-a16f-7a3bb2cd2761/test_results.md', 'w', encoding='utf-8') as md:
    md.write('# نتائج الاختبار الشامل للمحرك الجديد\n\n')
    md.write('| النص (Query) | القسم | المنطقة | السعر الأقصى | غرف النوم | مفروش | الكلمات الدلالية (Tags) |\n')
    md.write('|---|---|---|---|---|---|---|\n')
    
    for i, q in enumerate(queries):
        try:
            req = urllib.request.Request(url, data=json.dumps({'text': q}).encode('utf-8'), headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
                res = json.loads(r.read().decode('utf-8'))
                
            filters = res.get('filters_applied', {})
            cat = filters.get('category_name', '-') or '-'
            locs = '، '.join(filters.get('location_names', [])) or '-'
            price = filters.get('max_price') or '-'
            beds = filters.get('bedrooms') or '-'
            furn = 'مفروش' if filters.get('furnished') is True else ('غير مفروش' if filters.get('furnished') is False else '-')
            tags = '، '.join(filters.get('tags', [])) or '-'
            
            md.write(f'| {q} | {cat} | {locs} | {price} | {beds} | {furn} | {tags} |\n')
            md.flush()
            print(f"[{i+1}/{len(queries)}] تم بنجاح")
        except Exception as e:
            md.write(f'| {q} | ERROR | ERROR | ERROR | ERROR | ERROR | ERROR |\n')
            md.flush()
            print(f"[{i+1}/{len(queries)}] خطأ: {e}")
