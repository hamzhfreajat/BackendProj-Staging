import re

with open('smart_search_router.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_query = '''def build_search_query(db: Session, filters: dict):
    from sqlalchemy import or_
    query = db.query(models.AdSearchIndex)
    joined_ad = False
    
    if filters.get("category_id"):
        query = query.filter(models.AdSearchIndex.category_id == filters["category_id"])
        
    if filters.get("city_id"):
        query = query.filter(models.AdSearchIndex.city_id == filters["city_id"])
        
    if filters.get("location_names"):
        query = query.join(models.Ad, models.AdSearchIndex.ad_id == models.Ad.id)
        joined_ad = True
        loc_conditions = [models.Ad.location.ilike(f"%{loc}%") for loc in filters["location_names"]]
        if filters.get("region_ids"):
            query = query.filter(or_(models.AdSearchIndex.region_id.in_(filters["region_ids"]), *loc_conditions))
        else:
            query = query.filter(or_(*loc_conditions))
    elif filters.get("region_ids"):
        query = query.filter(models.AdSearchIndex.region_id.in_(filters["region_ids"]))
        
    if filters.get("min_price"):
        query = query.filter(models.AdSearchIndex.price >= filters["min_price"])
        
    if filters.get("max_price"):
        query = query.filter(models.AdSearchIndex.price <= filters["max_price"])'''

start = code.find("def build_search_query")
end = code.find("if filters.get(\"max_price\")", start) + len("if filters.get(\"max_price\"):\n        query = query.filter(models.AdSearchIndex.price <= filters[\"max_price\"])")

code = code[:start] + new_query + code[end:]

with open('smart_search_router.py', 'w', encoding='utf-8') as f:
    f.write(code)
