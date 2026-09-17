import os
import json
import logging
import urllib.request
import urllib.error
import difflib
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
import models
from database import get_db

from arabic_utils import normalize_arabic, convert_hindi_numerals, parse_price
from dialect_dictionary import FURNISHING_SYNONYMS, TRANSACTION_SYNONYMS, CATEGORY_SYNONYMS, ZONE_REGIONS

logger = logging.getLogger(__name__)

smart_search_router = APIRouter()

class SmartSearchRequest(BaseModel):
    text: str

class SmartSearchResponse(BaseModel):
    intent: str
    result_count: int
    filters_applied: dict
    suggestion: Optional[str] = None
    alternative_count: Optional[int] = None
    alternative_filters: Optional[dict] = None

def extract_raw_data_via_deepseek(text: str) -> dict:
    """
    Step 1: Uses DeepSeek to act purely as an NLP entity extractor.
    It does NOT attempt to match IDs or predefined lists. It just extracts raw Arabic words.
    """
    url = "https://api.deepseek.com/chat/completions"
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        logger.error("DEEPSEEK_API_KEY is not set.")
        raise HTTPException(status_code=500, detail="Search service configuration error.")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    system_prompt = """You are a helpful NLP assistant. Extract entities from Jordanian real estate search queries.
Do NOT guess or correct anything. Output exactly what the user said in the specified JSON fields.

Intent mapping:
- "search": Looking for properties
- "post_ad": Wants to sell or rent out their own property (e.g. "بدي ابيع شقتي")

Output JSON format:
{
  "intent": "search" | "post_ad",
  "raw_filters": {
    "property_type": "Extract property type (e.g. شقة, فيلا, بيت, ستوديو)",
    "transaction": "Extract transaction type if mentioned (e.g. للبيع, ايجار)",
    "locations": ["Array of location names. Remove prepositions like بـ or في. E.g. ['الياسمين', 'الذراع الغربي']"],
    "bedrooms_number": integer or null (ONLY count actual bedrooms, e.g. 'غرفتين نوم وصالون' -> 2),
    "bathrooms_number": integer or null,
    "furnishing_word": "Extract word indicating furniture if mentioned (e.g. معشية, مفروشة, فاضية, عظم)",
    "max_price_word": "Extract text indicating max price (e.g. 230, 50 الف, لحد 300)",
    "min_price_word": "Extract text indicating min price",
    "floor_word": "Extract floor mentioned (e.g. ارضي, تسوية, اول)"
  }
}"""

    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        "response_format": {"type": "json_object"}
    }

    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            return json.loads(content)
    except Exception as e:
        logger.error(f"Error calling DeepSeek API: {str(e)}")
        raise HTTPException(status_code=500, detail="Error communicating with AI service.")

def generate_fallback_suggestion(original_filters: dict, alternative_count: int, removed_filter: str) -> str:
    url = "https://api.deepseek.com/chat/completions"
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return "جرب تغيير بعض الفلاتر للحصول على نتائج."

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    prompt = f"""
المستخدم بحث عن عقار باستخدام هذه الفلاتر:
{json.dumps(original_filters, ensure_ascii=False)}

ولكن لم نجد أي نتائج. 
قمنا بإزالة الفلتر: {removed_filter} ووجدنا {alternative_count} إعلانات.

اكتب رسالة ودية قصيرة جداً باللهجة الأردنية تقترح على المستخدم تعديل هذا الفلتر بالذات (مثلاً إذا كان السعر، اقترح زيادة الميزانية، إذا كان المنطقة اقترح توسيع نطاق البحث) للحصول على {alternative_count} نتائج. لا تستخدم أي رموز Markdown.
    """

    data = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return "لا توجد نتائج مطابقة، جرب تغيير بعض الفلاتر للحصول على نتائج."

def map_category_smart(raw_prop: str, raw_trans: str) -> Optional[int]:
    """Combines property type and transaction to find the best category ID."""
    if not raw_prop:
        return None
        
    prop_norm = raw_prop.lower()
    trans_norm = raw_trans.lower() if raw_trans else ""
    
    # 1. Resolve Transaction (Sale vs Rent)
    is_rent = False
    for k, v in TRANSACTION_SYNONYMS.items():
        if k in trans_norm or k in prop_norm:
            if v == "rent":
                is_rent = True
                break
                
    # 2. Try combined match first
    combined = f"{prop_norm} للايجار" if is_rent else f"{prop_norm} للبيع"
    for k, v in CATEGORY_SYNONYMS.items():
        if k in combined:
            return v
            
    # 3. Fallback to direct mapping
    for k, v in CATEGORY_SYNONYMS.items():
        if k in prop_norm:
            # If it's a generic map (like 10301), and they want rent, force rent ID
            if is_rent and v == 10301: return 301 # apartments
            if is_rent and v == 10101: return 3101 # villas
            if is_rent and v == 10302: return 302 # studios
            if is_rent and v == 10853: return 303 # shops
            return v
            
    return None

def resolve_regions_smart(db: Session, raw_locations: list, city_id: int = None) -> tuple:
    """
    Step 2: Python Matcher Engine.
    Uses fuzzy matching against normalized DB values to find regions.
    Returns: (list of matching region IDs, list of unfound raw region names, inferred city_id)
    """
    if not raw_locations:
        return [], [], city_id
        
    # Fetch all regions to memory for matching (small enough to be very fast)
    all_regions = db.query(models.Region).all()
    # Pre-calculate normalized names
    db_candidates = {r.id: {"norm": normalize_arabic(r.name_ar), "obj": r} for r in all_regions}
    
    found_region_ids = []
    not_found_names = []
    inferred_city = city_id
    
    for raw_loc in raw_locations:
        norm_loc = normalize_arabic(raw_loc)
        if not norm_loc: continue
        
        # 1. Check Zone Dictionary first (e.g. "عمان الغربية")
        zone_matched = False
        for zone_key, zone_areas in ZONE_REGIONS.items():
            if norm_loc == normalize_arabic(zone_key):
                zone_matched = True
                # Match all areas in this zone
                for area in zone_areas:
                    norm_area = normalize_arabic(area)
                    # Find exact match in DB
                    for r_id, r_data in db_candidates.items():
                        if r_data["norm"] == norm_area:
                            found_region_ids.append(r_id)
                            if not inferred_city: inferred_city = r_data["obj"].city_id
                break
        
        if zone_matched:
            continue
            
        # 2. Fuzzy Matching for specific region
        best_match_id = None
        best_score = 0.0
        
        for r_id, r_data in db_candidates.items():
            db_norm = r_data["norm"]
            # Fast exact match
            if norm_loc == db_norm:
                best_match_id = r_id
                best_score = 1.0
                break
            
            # SequenceMatcher provides ratio 0.0 to 1.0
            score = difflib.SequenceMatcher(None, norm_loc, db_norm).ratio()
            if score > best_score:
                best_score = score
                best_match_id = r_id
                
        # Acceptance Threshold (e.g. 75%)
        if best_score > 0.75 and best_match_id:
            found_region_ids.append(best_match_id)
            if not inferred_city:
                inferred_city = db_candidates[best_match_id]["obj"].city_id
        else:
            # 3. Fallback to Alias check
            alias = db.query(models.RegionAlias).filter(
                models.RegionAlias.alias_name.ilike(f"%{raw_loc}%")
            ).first()
            if alias:
                found_region_ids.append(alias.region_id)
                if not inferred_city:
                    region = db.query(models.Region).filter(models.Region.id == alias.region_id).first()
                    if region: inferred_city = region.city_id
            else:
                not_found_names.append(raw_loc)
                
    return list(set(found_region_ids)), not_found_names, inferred_city

def build_search_query(db: Session, filters: dict):
    q = db.query(models.Ad).join(models.AdSearchIndex, models.Ad.id == models.AdSearchIndex.ad_id)
    
    q = q.filter(
        models.Ad.is_published == True,
        models.Ad.is_paused == False,
        models.Ad.is_sold == False,
        models.Ad.is_rejected == False
    )

    if filters.get("category_id"):
        q = q.filter(models.AdSearchIndex.category_id == filters["category_id"])
        
    if filters.get("city_id"):
        q = q.filter(models.AdSearchIndex.city_id == filters["city_id"])
        
    region_ids = filters.get("region_ids", [])
    if region_ids:
        if len(region_ids) == 1:
            q = q.filter(models.AdSearchIndex.region_id == region_ids[0])
        else:
            q = q.filter(models.AdSearchIndex.region_id.in_(region_ids))
            
    if filters.get("min_price"):
        q = q.filter(models.AdSearchIndex.price >= filters["min_price"])
    if filters.get("max_price"):
        q = q.filter(models.AdSearchIndex.price <= filters["max_price"])
    if filters.get("bedrooms") is not None:
        q = q.filter(models.AdSearchIndex.bedrooms == filters["bedrooms"])
    if filters.get("bathrooms") is not None:
        q = q.filter(models.AdSearchIndex.bathrooms == filters["bathrooms"])
    if filters.get("furnished") is not None:
        q = q.filter(models.AdSearchIndex.furnished == filters["furnished"])
    if filters.get("floor") is not None:
        q = q.filter(models.AdSearchIndex.floor_number == filters["floor"])
        
    return q

@smart_search_router.post("/api/smart-voice-search", response_model=SmartSearchResponse)
def smart_voice_search(request: SmartSearchRequest, db: Session = Depends(get_db)):
    # STEP 1: AI Entity Extraction
    ai_response = extract_raw_data_via_deepseek(request.text)
    
    intent = ai_response.get("intent", "search")
    if intent != "search":
        return SmartSearchResponse(intent=intent, result_count=0, filters_applied={})
        
    raw = ai_response.get("raw_filters", {})
    
    # STEP 2: Python Engine Smart Matching
    
    # Category
    category_id = map_category_smart(raw.get("property_type"), raw.get("transaction"))
    
    # Locations
    region_ids, not_found_regions, city_id = resolve_regions_smart(db, raw.get("locations", []))
    
    # If city not inferred from region, try direct extraction (rare but possible)
    # (Assuming we might add city parsing later if needed)
    
    # Price
    min_price = parse_price(raw.get("min_price_word"))
    max_price = parse_price(raw.get("max_price_word"))
    
    # Furnishing
    furnished = None
    if raw.get("furnishing_word"):
        for k, v in FURNISHING_SYNONYMS.items():
            if k in raw["furnishing_word"]:
                furnished = v
                break
                
    # Build Display Data for Frontend
    location_names = []
    if city_id:
        city = db.query(models.City).filter(models.City.id == city_id).first()
        if city: location_names.append(city.name_ar)
        
    if region_ids:
        regions = db.query(models.Region).filter(models.Region.id.in_(region_ids)).all()
        for r in regions: location_names.append(r.name_ar)
        
    tags = []
    bedrooms = raw.get("bedrooms_number")
    if bedrooms is not None: tags.append(f"bedrooms:{bedrooms}")
    if furnished is True: tags.append("furnished:مفروشة")
    elif furnished is False: tags.append("furnished:غير مفروشة")

    applied_filters = {
        "category_id": category_id,
        "city_id": city_id,
        "region_ids": region_ids,
        "min_price": min_price,
        "max_price": max_price,
        "bedrooms": bedrooms,
        "bathrooms": raw.get("bathrooms_number"),
        "furnished": furnished,
        "category_name": raw.get("property_type"),
        "location_names": location_names,
        "tags": tags,
        "not_found_regions": not_found_regions # Pass this for UI feedback
    }
    
    query = build_search_query(db, applied_filters)
    count = query.count()
    
    suggestion = None
    if not_found_regions:
        names = " أو ".join(not_found_regions)
        suggestion = f"ملاحظة: منطقة '{names}' غير مسجلة لدينا، تم عرض نتائج تقريبية ضمن المدينة."
        
    if count > 0:
        return SmartSearchResponse(
            intent=intent,
            result_count=count,
            filters_applied=applied_filters,
            suggestion=suggestion
        )
        
    # STEP 3: Fallback system
    fallback_order = ["max_price", "min_price", "region_ids", "bedrooms", "furnished"]
    alternative_filters = applied_filters.copy()
    alternative_count = 0
    removed_filter_name = ""
    
    for filter_key in fallback_order:
        current_val = alternative_filters.get(filter_key)
        if current_val:
            temp_val = alternative_filters[filter_key]
            alternative_filters[filter_key] = [] if filter_key == "region_ids" else None
            
            fallback_query = build_search_query(db, alternative_filters)
            alternative_count = fallback_query.count()
            
            if alternative_count > 0:
                removed_filter_name = filter_key
                break
            alternative_filters[filter_key] = temp_val
                
    if alternative_count > 0:
        sugg = generate_fallback_suggestion(applied_filters, alternative_count, removed_filter_name)
        if suggestion: sugg = suggestion + "\n\n" + sugg
        suggestion = sugg
    else:
        suggestion = "عذراً، لم نتمكن من العثور على أي عقار مطابق. جرب تغيير فئة العقار أو المدينة."
        
    return SmartSearchResponse(
        intent=intent,
        result_count=0,
        filters_applied=applied_filters,
        suggestion=suggestion,
        alternative_count=alternative_count,
        alternative_filters=alternative_filters
    )
