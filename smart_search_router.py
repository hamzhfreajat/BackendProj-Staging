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
    action_required: Optional[str] = None

def extract_raw_data_via_deepseek(text: str, categories_str: str = "") -> dict:
    """
    Step 1: Uses DeepSeek to act purely as an NLP entity extractor.
    """
    url = "https://api.deepseek.com/chat/completions"
    import os
    from fastapi import HTTPException
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Search service configuration error.")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    system_prompt = f"""You are a helpful NLP assistant. Extract entities from Jordanian real estate search queries.
Do NOT guess or correct anything, except for category_id which must be selected from the provided list.
You MUST choose the most specific end-level category from the list. Do NOT choose broad/parent categories.

Intent mapping:
- search: Looking for properties (e.g. "شقة للايجار", "بدي استأجر", "عقارات")
- post_ad: Wants to sell or rent out their own property (e.g. "عندي شقة للبيع", "بدي انزل اعلان")

Available Categories (End-level only):
{categories_str}

Output JSON format:
{{
  "intent": "search" | "post_ad",
  "raw_filters": {{
    "category_id": integer ID of the best matching category from the list above, or null if unknown,
    "property_type": "Extract the property type mentioned (e.g. شقة, فيلا, سيارة), or null",
    "locations": ["Extract ALL location names, regions, or cities mentioned in the text as a list of strings"],
    "nearby_locations": ["Choose from: بنك / صراف آلي, دراي كلين, سوبر ماركت, صالة رياضية / جيم, صيدلية, محطة باصات, مدرسة, مستشفى, مسجد, مطعم. If not mentioned, return empty list."],
    "furnishing_word": "Choose ONE from: مفروشة, غير مفروشة, مفروش جزئياً. If not mentioned, return null.",
    "max_price_word": "Extract text indicating max price",
    "min_price_word": "Extract text indicating min price",
    "min_area_number": "Extract the integer minimum area in square meters mentioned, or null",
    "max_area_number": "Extract the integer maximum area in square meters mentioned, or null",
    "floor_words": ["Choose from: طابق التسوية, طابق شبه أرضي, الطابق الأرضي, طابق أخير, روف, طابق أخير مع روف. If not mentioned, return empty list."],
    "floor_numbers": ["Extract all floor integer numbers mentioned as a list of ints"],
    "bedrooms_number": "Extract the integer number of bedrooms mentioned, or null if not mentioned",
    "bathrooms_number": "Extract the integer number of bathrooms mentioned, or null if not mentioned",
    "rent_period": "Choose ONE from: يومي, أسبوعي, شهري, كل 3 أشهر, كل أربع أشهر, كل 5 أشهر, كل 6 أشهر, سنوي. If not mentioned, return null.",
    "building_age": "Choose ONE from: 0 - 11 شهر, 1 - 5 سنوات, 6 - 9 سنوات, 10 - 19 سنوات, +20 سنة. If not mentioned, return null.",
    "interface": "Choose ONE from: شمالية, جنوبية, شرقية, غربية, شمالية شرقية, شمالية غربية, جنوبية شرقية, جنوبية غربية. If not mentioned, return null.",
    "main_features": ["Choose from: تكييف مركزي, تدفئة, شرفة / بلكونة, غرفة خادمة, غرفة غسيل, خزائن حائط, مسبح خاص, سخان شمسي, زجاج شبابيك مزدوج. If not mentioned, return empty list."],
    "extra_features": ["Choose from: يوجد مصعد, موقف سيارات, حارس / أمن وحماية, نظام كهرباء احتياطي للطوارئ, انتركم, حديقة, كراج تفك, منطقة شواء, بركة سباحة. If not mentioned, return empty list."]
  }}
}}"""

    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.0
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
        return "جرب تغيير بعض ال�?لاتر للحصول على نتائج."

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    prompt = f"""
المستخدم بحث عن عقار باستخدام هذه ال�?لاتر:
{json.dumps(original_filters, ensure_ascii=False)}

ولكن لم نجد أي نتائج. 
قمنا بإزالة ال�?لتر: {removed_filter} ووجدنا {alternative_count} إعلانات.

اكتب رسالة ودية قصيرة جداً باللهجة الأردنية تقترح على المستخدم تعديل هذا ال�?لتر بالذات (مثلاً إذا كان السعر، اقترح زيادة الميزانية، إذا كان المنطقة اقترح توسيع نطاق البحث) للحصول على {alternative_count} نتائج. لا تستخدم أي رموز Markdown.
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
        return "لا توجد نتائج مطابقة، جرب تغيير بعض ال�?لاتر للحصول على نتائج."


        
    prop_norm = raw_prop.lower()
    
    # 1. Resolve Transaction (Sale vs Rent)
    is_rent = (raw_trans == "rent") if raw_trans else False
                
    # 2. Try combined match first
    combined = f"{prop_norm} للإيجار" if is_rent else f"{prop_norm} للبيع"
    for k, v in CATEGORY_SYNONYMS.items():
        if k in combined:
            return v
            
    # 3. Fallback to direct mapping
    for k, v in CATEGORY_SYNONYMS.items():
        if k in prop_norm:
            # If it's a generic map (like 201), and they want rent, force rent ID
            if is_rent and v == 201: return 301 # apartments
            if is_rent and v == 2015: return 3015
            if is_rent and v == 2016: return 302 # studios
            if is_rent and v == 202: return 313 # land
            if is_rent and v == 2031: return 316 # villas to rural? (approx fallback)
            if is_rent and v == 204: return 303 # shops
            if is_rent and v == 2051: return 314 # farms
            if is_rent and v == 2052: return 315 # chalets
            if is_rent and v == 2061: return 316 # houses
            return v
            
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

ZONE_REGIONS = {
    "عمان الغربية": [
        'ابو نصير', 'الجبيهة', 'الدوار الثالث', 'الدوار الرابع', 'الدوار الخامس', 'الدوار السادس', 
        'الدوار السابع', 'الدوار الثامن', 'الروابي', 'الصويفية', 'العبدلي', 'المدينة الرياضية', 
        'ام اذينة', 'ام اذينة الشرقي', 'ام اذينة الغربي', 'ام السماق', 'تلاع العلي', 
        'تلاع العلي الشمالي', 'تلاع العلي الشرقي', 'دير غبار', 'شارع المدينة', 
        'شارع المدينة المنورة', 'شارع مكة', 'شارع الجامعة', 'ضاحية الامير راشد', 
        'ضاحية الرشيد', 'ضاحية الحسين', 'ضاحية النخيل', 'ضاحية الروضة', 'وادي صقرة', 
        'دوار الداخلية', 'دوار الواحة', 'دوار الكيلو', 'بزنس بارك', 'طلوع نيفين', 
        'البحاث', 'البيادر', 'الجاردنز', 'الجندويل', 'الحمر', 'الديار', 'الرابية', 
        'الرضوان', 'الرونق', 'السهل', 'الصناعة', 'الظهير', 'الكرسي', 'الكمالية', 
        'أم الأسود', 'بدر الجديدة', 'خلدا', 'دابوق', 'شفا بدران', 'شميساني', 
        'صويلح', 'طريق المطار', 'طريق المطار - جسر ديونز', 'عبدون', 'عبدون الجنوبي', 
        'عبدون الشمالي', 'عراق الامير', 'مرج الحمام', 'وادي السير', 'حي البركة', 
        'حي الخالدين', 'حي الرحمانية', 'حي الصالحين', 'حي الصحابة', 'رجم عميش'
    ],
    "غرب عمان": [
        'ابو نصير', 'الجبيهة', 'الدوار الثالث', 'الدوار الرابع', 'الدوار الخامس', 'الدوار السادس', 
        'الدوار السابع', 'الدوار الثامن', 'الروابي', 'الصويفية', 'العبدلي', 'المدينة الرياضية', 
        'ام اذينة', 'ام اذينة الشرقي', 'ام اذينة الغربي', 'ام السماق', 'تلاع العلي', 
        'تلاع العلي الشمالي', 'تلاع العلي الشرقي', 'دير غبار', 'شارع المدينة', 
        'شارع المدينة المنورة', 'شارع مكة', 'شارع الجامعة', 'ضاحية الامير راشد', 
        'ضاحية الرشيد', 'ضاحية الحسين', 'ضاحية النخيل', 'ضاحية الروضة', 'وادي صقرة', 
        'دوار الداخلية', 'دوار الواحة', 'دوار الكيلو', 'بزنس بارك', 'طلوع نيفين', 
        'البحاث', 'البيادر', 'الجاردنز', 'الجندويل', 'الحمر', 'الديار', 'الرابية', 
        'الرضوان', 'الرونق', 'السهل', 'الصناعة', 'الظهير', 'الكرسي', 'الكمالية', 
        'أم الأسود', 'بدر الجديدة', 'خلدا', 'دابوق', 'شفا بدران', 'شميساني', 
        'صويلح', 'طريق المطار', 'طريق المطار - جسر ديونز', 'عبدون', 'عبدون الجنوبي', 
        'عبدون الشمالي', 'عراق الامير', 'مرج الحمام', 'وادي السير', 'حي البركة', 
        'حي الخالدين', 'حي الرحمانية', 'حي الصالحين', 'حي الصحابة', 'رجم عميش'
    ],
    "عمان الشرقية": [
        'ابو علندا', 'البنيات', 'المناره', 'ضاحية الامير حسن', 'ضاحية الحاج حسن', 
        'ضاحية الاستقلال', 'ضاحية الاقصى', 'وادي السرور', 'وادي الرمم', 'وادي الحدادة', 
        'وادي العش', 'أم الحيران', 'النويجيس', 'جبل القلعة', 'جبل الأشرفية', 'جبل التاج', 
        'جبل الجوفة', 'جبل الحسين', 'جبل الزهور', 'جبل المريخ', 'جبل النزهة', 'جبل النصر', 
        'جبل النظيف', 'جبل عمان', 'دوار المشاغل', 'شارع الحزام', 'عين غزال', 'البيضاء', 
        'الجويدة', 'الحرّيّة', 'الخزنة', 'الخشافية', 'الدوار الأول', 'الدوار الثاني', 
        'الذراع', 'الربوة', 'الرجيب', 'الرقيم', 'القصور', 'القويسمة', 'الماضونة', 
        'المحطة', 'المستندة', 'المقابلين', 'الموقر', 'المغيرات', 'الهاشمي الجنوبي', 
        'الهاشمي الشمالي', 'الوحدات', 'اليادودة', 'الياسمين', 'اليرموك', 'ام نوارة', 
        'أم قصير', 'بدر', 'بسمان', 'جاوا', 'حطين', 'حي نزال', 'حي عدن', 'خربة السوق', 
        'راس العين', 'سحاب', 'صالحية العابد', 'طبربور', 'طلوع المصدار', 'عرجان', 
        'ماركا', 'ماركا الشمالية', 'ماركا الجنوبية', 'وسط البلد', 'ياجوز', 'الكوم الشرقي'
    ],
    "شرق عمان": [
        'ابو علندا', 'البنيات', 'المناره', 'ضاحية الامير حسن', 'ضاحية الحاج حسن', 
        'ضاحية الاستقلال', 'ضاحية الاقصى', 'وادي السرور', 'وادي الرمم', 'وادي الحدادة', 
        'وادي العش', 'أم الحيران', 'النويجيس', 'جبل القلعة', 'جبل الأشرفية', 'جبل التاج', 
        'جبل الجوفة', 'جبل الحسين', 'جبل الزهور', 'جبل المريخ', 'جبل النزهة', 'جبل النصر', 
        'جبل النظيف', 'جبل عمان', 'دوار المشاغل', 'شارع الحزام', 'عين غزال', 'البيضاء', 
        'الجويدة', 'الحرّيّة', 'الخزنة', 'الخشافية', 'الدوار الأول', 'الدوار الثاني', 
        'الذراع', 'الربوة', 'الرجيب', 'الرقيم', 'القصور', 'القويسمة', 'الماضونة', 
        'المحطة', 'المستندة', 'المقابلين', 'الموقر', 'المغيرات', 'الهاشمي الجنوبي', 
        'الهاشمي الشمالي', 'الوحدات', 'اليادودة', 'الياسمين', 'اليرموك', 'ام نوارة', 
        'أم قصير', 'بدر', 'بسمان', 'جاوا', 'حطين', 'حي نزال', 'حي عدن', 'خربة السوق', 
        'راس العين', 'سحاب', 'صالحية العابد', 'طبربور', 'طلوع المصدار', 'عرجان', 
        'ماركا', 'ماركا الشمالية', 'ماركا الجنوبية', 'وسط البلد', 'ياجوز', 'الكوم الشرقي'
    ]
}

def resolve_regions_smart(db: Session, raw_locations: list, city_id: int = None) -> tuple:
    if raw_locations:
        expanded = []
        for loc in raw_locations:
            loc_clean = loc.strip()
            matched = False
            for zname, zregs in ZONE_REGIONS.items():
                if zname in loc_clean or loc_clean in zname:
                    expanded.extend(zregs)
                    matched = True
                    break
            if not matched:
                expanded.append(loc_clean)
        raw_locations = list(set(expanded))

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
        query = query.filter(models.AdSearchIndex.price <= filters["max_price"])
        
    if filters.get("bedrooms") is not None:
        query = query.filter(models.AdSearchIndex.bedrooms >= filters["bedrooms"])
        
    if filters.get("bathrooms") is not None:
        query = query.filter(models.AdSearchIndex.bathrooms >= filters["bathrooms"])
        
    if filters.get("furnished") is not None:
        query = query.filter(models.AdSearchIndex.furnished == filters["furnished"])
        
    if filters.get("floor_numbers"):
        query = query.filter(models.AdSearchIndex.floor_number.in_(filters["floor_numbers"]))
        
    if filters.get("min_area"):
        query = query.filter(models.AdSearchIndex.build_area >= filters["min_area"])
        
    if filters.get("max_area"):
        query = query.filter(models.AdSearchIndex.build_area <= filters["max_area"])
        
    if filters.get("features_list"):
        for feat in filters["features_list"]:
            if feat:
                query = query.filter(models.AdSearchIndex.search_text.ilike(f"%{feat}%"))

    return query

def parse_floor(floor_word: str):
    if not floor_word:
        return None
    w = floor_word.lower()
    if "ارضي" in w or "أرضي" in w or "حديقة" in w:
        return -1
    if "تسوية" in w:
        return -2
    if "اول" in w or "أول" in w: return 1
    if "ثاني" in w: return 2
    if "ثالث" in w: return 3
    if "رابع" in w: return 4
    if "خامس" in w: return 5
    if "سادس" in w: return 6
    if "اخير" in w or "أخير" in w or "رو�?" in w: return 100 # usually top floor
    return None

@smart_search_router.post("/api/smart-voice-search", response_model=SmartSearchResponse)
def smart_voice_search(request: SmartSearchRequest, db: Session = Depends(get_db)):
    # Fetch valid tags
    try:
        valid_tags_objs = db.query(models.Tag).all()
        valid_tags = [t.name for t in valid_tags_objs if t.name]
    except Exception:
        valid_tags = []

    # Fetch ONLY leaf categories under real estate (IDs 2 and 3)
    try:
        all_cats = db.query(models.Category).all()
        
        descendants = []
        current_parents = [2, 3]
        while current_parents:
            children = [c for c in all_cats if c.parent_id in current_parents]
            descendants.extend(children)
            current_parents = [c.id for c in children]
            
        parent_ids = {c.parent_id for c in all_cats if c.parent_id is not None}
        leaf_cats = [c for c in descendants if c.id not in parent_ids]
        
        cat_mapping = [f"ID: {c.id}, Name: {c.name}" for c in leaf_cats]
        categories_str = "\n".join(cat_mapping)
    except Exception:
        categories_str = ""

    # STEP 1: AI Entity Extraction
    print("CATEGORIES SENT TO AI:", categories_str)
    ai_response = extract_raw_data_via_deepseek(request.text, categories_str=categories_str)
    
    intent = ai_response.get("intent", "search")
    if intent != "search":
        return SmartSearchResponse(intent=intent, result_count=0, filters_applied={})
        
    raw = ai_response.get("raw_filters") or {}
    
    # STEP 2: Python Engine Smart Matching
    
    category_id = raw.get("category_id")
    raw_locations = raw.get("locations") or []
    
    WEST_AMMAN_REGIONS = [
        'ابو نصير', 'الجبيهة', 'الدوار الثالث', 'الدوار الرابع', 'الدوار الخامس', 'الدوار السادس', 
        'الدوار السابع', 'الدوار الثامن', 'الروابي', 'الصويفية', 'العبدلي', 'المدينة الرياضية', 
        'ام اذينة', 'ام اذينة الشرقي', 'ام اذينة الغربي', 'ام السماق', 'تلاع العلي', 
        'تلاع العلي الشمالي', 'تلاع العلي الشرقي', 'دير غبار', 'شارع المدينة', 
        'شارع المدينة المنورة', 'شارع مكة', 'شارع الجامعة', 'ضاحية الامير راشد', 
        'ضاحية الرشيد', 'ضاحية الحسين', 'ضاحية النخيل', 'ضاحية الروضة', 'وادي صقرة', 
        'دوار الداخلية', 'دوار الواحة', 'دوار الكيلو', 'بزنس بارك', 'طلوع نيفين', 
        'البحاث', 'البيادر', 'الجاردنز', 'الجندويل', 'الحمر', 'الديار', 'الرابية', 
        'الرضوان', 'الرونق', 'السهل', 'الصناعة', 'الظهير', 'الكرسي', 'الكمالية', 
        'أم الأسود', 'بدر الجديدة', 'خلدا', 'دابوق', 'شفا بدران', 'شميساني', 
        'صويلح', 'طريق المطار', 'طريق المطار - جسر ديونز', 'عبدون', 'عبدون الجنوبي', 
        'عبدون الشمالي', 'عراق الامير', 'مرج الحمام', 'وادي السير', 'حي البركة', 
        'حي الخالدين', 'حي الرحمانية', 'حي الصالحين', 'حي الصحابة', 'رجم عميش'
    ]

    EAST_AMMAN_REGIONS = [
        'ابو علندا', 'البنيات', 'المناره', 'ضاحية الامير حسن', 'ضاحية الحاج حسن', 
        'ضاحية الاستقلال', 'ضاحية الاقصى', 'وادي السرور', 'وادي الرمم', 'وادي الحدادة', 
        'وادي العش', 'أم الحيران', 'النويجيس', 'جبل القلعة', 'جبل الأشرفية', 'جبل التاج', 
        'جبل الجوفة', 'جبل الحسين', 'جبل الزهور', 'جبل المريخ', 'جبل النزهة', 'جبل النصر', 
        'جبل النظيف', 'جبل عمان', 'دوار المشاغل', 'شارع الحزام', 'عين غزال', 'البيضاء', 
        'الجويدة', 'الحرّيّة', 'الخزنة', 'الخشافية', 'الدوار الأول', 'الدوار الثاني', 
        'الذراع', 'الربوة', 'الرجيب', 'الرقيم', 'القصور', 'القويسمة', 'الماضونة', 
        'المحطة', 'المستندة', 'المقابلين', 'الموقر', 'المغيرات', 'الهاشمي الجنوبي', 
        'الهاشمي الشمالي', 'الوحدات', 'اليادودة', 'الياسمين', 'اليرموك', 'ام نوارة', 
        'أم قصير', 'بدر', 'بسمان', 'جاوا', 'حطين', 'حي نزال', 'حي عدن', 'خربة السوق', 
        'راس العين', 'سحاب', 'صالحية العابد', 'طبربور', 'طلوع المصدار', 'عرجان', 
        'ماركا', 'ماركا الشمالية', 'ماركا الجنوبية', 'وسط البلد', 'ياجوز', 'الكوم الشرقي'
    ]
    
    expanded_locations = []
    for loc in raw_locations:
        loc_clean = loc.replace('ة', 'ه').replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا').strip()
        if loc_clean in ["عمان الغربيه", "غرب عمان", "عمان غربيه", "عمان الغربية", "عمان غربية"]:
            expanded_locations.extend(WEST_AMMAN_REGIONS)
        elif loc_clean in ["عمان الشرقيه", "شرق عمان", "عمان شرقيه", "عمان الشرقية", "عمان شرقية"]:
            expanded_locations.extend(EAST_AMMAN_REGIONS)
        else:
            expanded_locations.append(loc)
            
    raw["locations"] = list(dict.fromkeys(expanded_locations)) # remove duplicates
    
    # Locations
    region_ids, not_found_regions, city_id = resolve_regions_smart(db, raw["locations"])
    
    # Price
    min_price = parse_price(raw.get("min_price_word"))
    max_price = parse_price(raw.get("max_price_word"))
    
    # Furnishing
    furnished = None
    if raw.get("furnishing_word"):
        for k, v in FURNISHING_SYNONYMS.items():
            if k in str(raw["furnishing_word"]):
                furnished = v
                break
                
    # Floor handling
    floor_words = raw.get("floor_words") or []
    if isinstance(floor_words, str): floor_words = [floor_words]
    # Fallback for old schema
    if raw.get("floor_word") and raw.get("floor_word") not in floor_words:
        floor_words.append(raw.get("floor_word"))
        
    floor_numbers = raw.get("floor_numbers") or []
    if isinstance(floor_numbers, int): floor_numbers = [floor_numbers]
    if raw.get("floor_number") is not None and raw.get("floor_number") not in floor_numbers:
        floor_numbers.append(raw.get("floor_number"))
        
    for fw in floor_words:
        parsed = parse_floor(fw)
        if parsed is not None and parsed not in floor_numbers:
            floor_numbers.append(parsed)
            
    # Area
    min_area = raw.get("min_area_number")
    max_area = raw.get("max_area_number")
    
    # New Fields
    rent_period = raw.get("rent_period")
    building_age = raw.get("building_age")
    interface = raw.get("interface")
    
    nearby_locations = raw.get("nearby_locations") or []
    if isinstance(nearby_locations, str):
        nearby_locations = [nearby_locations]
        
    main_features = raw.get("main_features") or []
    if isinstance(main_features, str):
        main_features = [main_features]
        
    extra_features = raw.get("extra_features") or []
    if isinstance(extra_features, str):
        extra_features = [extra_features]
    
    # Extra Features fallback
    features_list = raw.get("features") or []
    if isinstance(features_list, str):
        features_list = [features_list]
        
    # Inject new text fields into features_list for full text search fallback
    for item in [rent_period, building_age, interface] + nearby_locations + main_features + extra_features + floor_words:
        if item and item not in features_list:
            features_list.append(item)
            
    # Build Display Data for Frontend
    location_names = raw.get("locations") or []
    
    tags = []
    
    if raw.get("bedrooms_number") is not None:
        tags.append(f"bedrooms:{raw['bedrooms_number']}")
    
    if raw.get("bathrooms_number") is not None:
        tags.append(f"bathrooms:{raw['bathrooms_number']}")
        
    if furnished is not None:
        val = "نعم" if furnished else "لا"
        tags.append(f"furnished:{val}")
        
    if rent_period:
        tags.append(f"rent_duration:{rent_period}")
        
    for fw in floor_words:
        tags.append(f"floor:{fw}")
        
    if building_age:
        tags.append(f"age:{building_age}")
        
    if interface:
        tags.append(f"facade:{interface}")
        
    for nb in nearby_locations:
        tags.append(f"nearby:{nb}")
        
    for mf in main_features:
        tags.append(f"main_features:{mf}")
        
    for ef in extra_features:
        tags.append(f"extra_features:{ef}")
        
    if min_area:
        tags.append(f"min_area:{min_area}")
    if max_area:
        tags.append(f"max_area:{max_area}")
        
    # Resolve actual category name from DB
    resolved_category_name = raw.get("property_type")
    if category_id is not None:
        try:
            cat_obj = db.query(models.Category).filter(models.Category.id == category_id).first()
            if cat_obj and cat_obj.name:
                resolved_category_name = cat_obj.name
        except Exception:
            pass
            
    if not resolved_category_name:
        resolved_category_name = "نتائج البحث"

    applied_filters = {
        "category_id": category_id,
        "city_id": city_id,
        "region_ids": region_ids,
        "min_price": min_price,
        "max_price": max_price,
        "bedrooms": raw.get("bedrooms_number"),
        "bathrooms": raw.get("bathrooms_number"),
        "furnished": furnished,
        "floor_numbers": floor_numbers,
        "min_area": min_area,
        "max_area": max_area,
        "rent_period": rent_period,
        "building_age": building_age,
        "interface": interface,
        "nearby_locations": nearby_locations,
        "features_list": features_list,
        "category_name": resolved_category_name,
        "location_names": location_names,
        "tags": tags,
        "not_found_regions": not_found_regions
    }
    
    query = build_search_query(db, applied_filters)
    count = query.count()
    
    suggestion = None
    if not_found_regions:
        names = " أو ".join(not_found_regions)
        suggestion = f"ملاحظة: منطقة '{names}' غير مسجلة، تم عرض نتائج تقريبية."
        
    if count > 0:
        return SmartSearchResponse(
            intent=intent,
            result_count=count,
            filters_applied=applied_filters,
            suggestion=suggestion
        )
        
    # Fallback progressively if 0 results
    # 1. Remove features
    if features_list:
        applied_filters["features_list"] = []
        applied_filters["tags"] = [t for t in tags if t not in features_list]
        query = build_search_query(db, applied_filters)
        count = query.count()
        if count > 0:
            return SmartSearchResponse(intent=intent, result_count=count, filters_applied=applied_filters, suggestion="لم نجد نتائج بكل الميزات الإضافية المطلوبة، تم تجاهلها لعرض نتائج أقرب.")

    # 2. Remove floor
    if applied_filters.get("floor_numbers"):
        applied_filters["floor_numbers"] = []
        query = build_search_query(db, applied_filters)
        count = query.count()
        if count > 0:
            return SmartSearchResponse(intent=intent, result_count=count, filters_applied=applied_filters, suggestion="لم نجد نتائج في نفس الطابق المطلوب، تم تجاهل الطابق.")
            
    # 3. Remove area
    if min_area is not None or max_area is not None:
        applied_filters["min_area"] = None
        applied_filters["max_area"] = None
        query = build_search_query(db, applied_filters)
        count = query.count()
        if count > 0:
            return SmartSearchResponse(intent=intent, result_count=count, filters_applied=applied_filters, suggestion="لم نجد نتائج بنفس المساحة، تم تجاهل المساحة.")

    # 4. Expand Price
    if max_price:
        applied_filters["max_price"] = int(max_price * 1.25)
        query = build_search_query(db, applied_filters)
        count = query.count()
        if count > 0:
            return SmartSearchResponse(intent=intent, result_count=count, filters_applied=applied_filters, suggestion=f"لم نجد نتائج بسعر {max_price}، فقمنا برفع الميزانية لغاية {applied_filters['max_price']}")
            
    # 5. Remove Bedrooms
    if applied_filters.get("bedrooms") is not None:
        applied_filters["bedrooms"] = None
        applied_filters["tags"] = [t for t in applied_filters["tags"] if not t.startswith("bedrooms")]
        query = build_search_query(db, applied_filters)
        count = query.count()
        if count > 0:
            return SmartSearchResponse(intent=intent, result_count=count, filters_applied=applied_filters, suggestion="لم نجد نتائج بنفس عدد الغرف، تم توسيع البحث.")
            
    # 6. Fallback to just City + Category
    if region_ids:
        applied_filters["region_ids"] = []
        applied_filters["location_names"] = [n for n in location_names if n == "عمان"]
        query = build_search_query(db, applied_filters)
        count = query.count()
        if count > 0:
            return SmartSearchResponse(intent=intent, result_count=count, filters_applied=applied_filters, suggestion="لم نجد نتائج في هذه المنطقة تحديداً، تم عرض نتائج المدينة كاملة.")
            
    return SmartSearchResponse(
        intent=intent,
        result_count=0,
        filters_applied=applied_filters,
        suggestion="نعتذر، لا يوجد أي عقارات مطابقة لبحثك حالياً."
    )




















@smart_search_router.get("/api/debug-cats")
def debug_cats(db: Session = Depends(get_db)):
    try:
        all_cats = db.query(models.Category).all()
        
        descendants = []
        current_parents = [2, 3] # Real Estate Sale & Rent
        
        while current_parents:
            children = [c for c in all_cats if c.parent_id in current_parents]
            descendants.extend(children)
            current_parents = [c.id for c in children]
            
        parent_ids = {c.parent_id for c in all_cats if c.parent_id is not None}
        leaf_cats = [c for c in descendants if c.id not in parent_ids]
        
        cat_mapping = [f"ID: {c.id}, Name: {c.name}" for c in leaf_cats]
        categories_str = "\n".join(cat_mapping)
        return {"cats": categories_str}
    except Exception as e:
        return {"error": str(e)}
