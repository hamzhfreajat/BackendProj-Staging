import json
import sys
sys.stdout.reconfigure(encoding='utf-8')
from sqlalchemy.orm import Session
from database import SessionLocal
import smart_search_router
from smart_search_router import SmartSearchRequest

db = SessionLocal()

with open('test_queries.txt', 'r', encoding='utf-8') as f:
    queries = [line.strip() for line in f if line.strip()]

with open('C:/Users/hfraijat/.gemini/antigravity/brain/696fb396-0dce-4ae5-a16f-7a3bb2cd2761/local_batch_test.md', 'w', encoding='utf-8') as md:
    md.write('# Voice Search Full Filters Test (Local Evaluation)\n\n')
    md.write('| Query | Intent | Category | Locations | Min Area | Max Area | Price (Max) | Beds | Baths | Furnished | Floor | Tags/Features |\n')
    md.write('|---|---|---|---|---|---|---|---|---|---|---|---|\n')
    
    for i, q in enumerate(queries):
        try:
            req = SmartSearchRequest(text=q)
            res = smart_search_router.smart_voice_search(req, db)
            
            intent = res.intent
            filters = res.filters_applied or {}
            
            cat = filters.get('category_name', '-') or '-'
            locs = ', '.join(filters.get('location_names', [])) or '-'
            min_a = filters.get('min_area') or '-'
            max_a = filters.get('max_area') or '-'
            price = filters.get('max_price') or '-'
            beds = filters.get('bedrooms') or '-'
            baths = filters.get('bathrooms') or '-'
            furn = 'Yes' if filters.get('furnished') is True else ('No' if filters.get('furnished') is False else '-')
            floor = filters.get('floor') if filters.get('floor') is not None else '-'
            tags = ', '.join(filters.get('tags', [])) or '-'
            
            md.write(f'| {q} | {intent} | {cat} | {locs} | {min_a} | {max_a} | {price} | {beds} | {baths} | {furn} | {floor} | {tags} |\n')
            md.flush()
            print(f"[{i+1}/{len(queries)}] Done")
        except Exception as e:
            md.write(f'| {q} | ERROR | ERROR | ERROR | ERROR | ERROR | ERROR | ERROR | ERROR | ERROR | ERROR | ERROR |\n')
            md.flush()
            print(f"[{i+1}/{len(queries)}] Error: {e}")
