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
    'User-Agent': 'Mozilla/5.0'
}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

with open('C:/Users/hfraijat/.gemini/antigravity/brain/696fb396-0dce-4ae5-a16f-7a3bb2cd2761/test_results_full.md', 'w', encoding='utf-8') as md:
    md.write('# Voice Search Full Filters Test\n\n')
    md.write('| Query | Intent | Category | Locations | Min Price | Max Price | Beds | Baths | Furnished | Floor | Tags |\n')
    md.write('|---|---|---|---|---|---|---|---|---|---|---|\n')
    
    for i, q in enumerate(queries):
        try:
            req = urllib.request.Request(url, data=json.dumps({'text': q}).encode('utf-8'), headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
                res = json.loads(r.read().decode('utf-8'))
                
            intent = res.get('intent', '-')
            filters = res.get('filters_applied', {})
            cat = filters.get('category_name', '-') or '-'
            locs = ', '.join(filters.get('location_names', [])) or '-'
            min_price = filters.get('min_price') or '-'
            max_price = filters.get('max_price') or '-'
            beds = filters.get('bedrooms') or '-'
            baths = filters.get('bathrooms') or '-'
            floor = filters.get('floor') or '-'
            furn = 'True' if filters.get('furnished') is True else ('False' if filters.get('furnished') is False else '-')
            tags = ', '.join(filters.get('tags', [])) or '-'
            
            md.write(f'| {q} | {intent} | {cat} | {locs} | {min_price} | {max_price} | {beds} | {baths} | {furn} | {floor} | {tags} |\n')
            md.flush()
        except Exception as e:
            md.write(f'| {q} | ERROR | ERROR | ERROR | ERROR | ERROR | ERROR | ERROR | ERROR | ERROR | ERROR |\n')
            md.flush()
