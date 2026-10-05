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
from auth import redis_client
from smart_search_locations import resolve_locations, match_city

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
    import re
    # Fix common typos before processing
    text = re.sub(r'\bعرف\b', 'غرف', text)
    text = re.sub(r'\bعرفه\b', 'غرفه', text)
    text = re.sub(r'\bعرفة\b', 'غرفة', text)
    text = re.sub(r'\bمعنا\b', 'برفقتنا', text)
    text = re.sub(r'\bمعي\b', 'برفقتي', text)
    
    # Specific landmark intercepts
    text = re.sub(r'\bاشارة النسيم\b', 'دوار النسيم', text)
    text = re.sub(r'\bإشارة النسيم\b', 'دوار النسيم', text)
    text = re.sub(r'\bاشاره النسيم\b', 'دوار النسيم', text)
    text = re.sub(r'\bإشاره النسيم\b', 'دوار النسيم', text)
    
    # Normalize Rent words so AI doesn't get confused by Hamza
    text = text.replace('إيجار', 'ايجار').replace('الإيجار', 'الايجار').replace('للإيجار', 'للايجار')
    text = text.replace('أجار', 'اجار').replace('الأجار', 'الاجار').replace('للأجار', 'للاجار')
    
    # Jordanian Slang ordinals
    text = re.sub(r'\bتالت\b', 'ثالث', text)
    text = re.sub(r'\bالتالت\b', 'الثالث', text)
    text = re.sub(r'\bتالتة\b', 'ثالثة', text)
    text = re.sub(r'\bتالتّه\b', 'ثالثه', text)
    text = re.sub(r'\bالتالتة\b', 'الثالثة', text)
    text = re.sub(r'\bالتالته\b', 'الثالثه', text)
    
    text = re.sub(r'\bتامن\b', 'ثامن', text)
    text = re.sub(r'\bالتامن\b', 'الثامن', text)
    text = re.sub(r'\bتامنة\b', 'ثامنة', text)
    text = re.sub(r'\bتامنه\b', 'ثامنه', text)
    text = re.sub(r'\bالتامنة\b', 'الثامنة', text)
    text = re.sub(r'\bالتامنه\b', 'الثامنه', text)
    
    text = re.sub(r'\bتاني\b', 'ثاني', text)
    text = re.sub(r'\bالتاني\b', 'الثاني', text)
    text = re.sub(r'\bتانية\b', 'ثانية', text)
    text = re.sub(r'\bتانيه\b', 'ثانيه', text)
    text = re.sub(r'\bالتانية\b', 'الثانية', text)
    text = re.sub(r'\bالتانيه\b', 'الثانيه', text)
    
    # Bump the version whenever the prompt or output format changes
    cache_key = f"smart_search_ai:v2:{text}"
    if redis_client:
        try:
            cached_result = redis_client.get(cache_key)
            if cached_result:
                return json.loads(cached_result)
        except Exception as e:
            logger.error(f"Smart search cache read failed: {e}")

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
You MUST choose the most specific end-level category from the list. 
CRITICAL RULE: If the user DOES NOT explicitly mention whether they want to RENT (ايجار) or BUY/SALE (بيع / شراء), you MUST set category_id to null so the search can span across both. Do not guess the category if rent/sale intent is ambiguous.
CRITICAL RULE: If the user explicitly negates a feature or location (e.g. 'ما بتناسبنا التاسعة', 'مش بالزرقاء', 'مش طابق ارضي', 'بدون فرش', 'غير مفروش'), DO NOT extract it. Locations or features mentioned negatively MUST be completely ignored.
CRITICAL RULE: If the user uses relative sizes for an apartment:
- 'صغيرة' (small): set max_area_number to 90 (unless a specific number is provided).
- 'كبيرة' (large) or 'واسعة': set min_area_number to 150 (unless a specific number is provided).

Intent mapping:
- search: Looking for properties (e.g. "شقة للايجار", "بدي استأجر", "عقارات")
- post_ad: Wants to sell or rent out their own property (e.g. "عندي شقة للبيع", "بدي انزل اعلان")

CRITICAL RULE: Words like (الثالثه, الرابعه, الخامسه, السادسه, السابعه, الثامنه, التاسعه, العاشره) are OFTEN regions in Aqaba. DO NOT extract them as floor numbers (floor_numbers) UNLESS the user explicitly says "طابق" (floor) before them. You MUST extract the exact word (e.g. "الثامنه") into the `locations` array!

Available Categories (End-level only):
{categories_str}

Output JSON format:
{{
  "intent": "search" | "post_ad",
  "raw_filters": {{
    "category_id": integer ID of the best matching category from the list above, or null if unknown,
    "property_type": "Extract the property type mentioned (e.g. شقة, فيلا, سيارة), or null",
    "city": "The Jordanian city or governorate the user explicitly mentions (e.g. عمان, اربد, الزرقاء, العقبة), written without prefixes like بـ or في. null if no city is mentioned. Do NOT guess the city from a region name.",
    "locations": ["Extract ALL regions / neighbourhoods mentioned (e.g. خلدا, الزهور, الوحدات الشرقية). Do NOT put the city here and do NOT put landmarks here."],
    "landmarks": [{{"name": "A landmark the user mentions that is not itself a neighbourhood: a circle (دوار), signal (اشارة), mall, university, hospital, mosque, street, bridge, etc. (e.g. دوار هيا)", "region": "From your knowledge of Jordan, the neighbourhood this landmark is located in, or null if you are not sure", "city": "The city this landmark is located in (must equal the city above when the user stated one), or null if you are not sure"}}],
    "nearby_locations": ["Choose from: بنك / صراف آلي, دراي كلين, سوبر ماركت, صالة رياضية / جيم, صيدلية, محطة باصات, مدرسة, مستشفى, مسجد, مطعم. If not mentioned, return empty list."],
    "furnishing_word": "Choose ONE from: مفروشة, غير مفروشة, مفروش جزئياً. If not mentioned, return null.",
    "payment_method": "Choose ONE from: كاش, أقساط. If not mentioned, return null.",
    "max_price_word": "Extract text indicating max price",
    "min_price_word": "Extract text indicating min price",
    "min_area_number": "Extract the integer minimum area in square meters mentioned, or null",
    "max_area_number": "Extract the integer maximum area in square meters mentioned, or null",
    "floor_words": ["Choose from: طابق التسوية, طابق شبه أرضي, الطابق الأرضي, طابق أخير, روف, طابق أخير مع روف. If not mentioned, return empty list."],
    "floor_numbers": ["Extract floor numbers ONLY if explicitly preceded by words like 'طابق' (e.g. طابق 3). DO NOT extract bedroom counts here!"],
    "bedrooms_number": "Extract the integer number of bedrooms mentioned, or null if not mentioned",
    "bathrooms_number": "Extract the integer number of bathrooms mentioned, or null if not mentioned",
    "rent_period": "Choose ONE from: يومي, أسبوعي, شهري, كل 3 أشهر, كل أربع أشهر, كل 5 أشهر, كل 6 أشهر, سنوي. If not mentioned, return null.",
    "building_age": "Choose ONE from: 0 - 11 شهر, 1 - 5 سنوات, 6 - 9 سنوات, 10 - 19 سنوات, +20 سنة. If not mentioned, return null.",
    "interface": "Choose ONE from: شمالية, جنوبية, شرقية, غربية, شمالية شرقية, شمالية غربية, جنوبية شرقية, جنوبية غربية. If not mentioned, return null.",
    "main_features": ["Choose from: تكييف مركزي, تدفئة, شرفة / بلكونة, غرفة خادمة, غرفة غسيل, خزائن حائط, مسبح خاص, سخان شمسي, زجاج شبابيك مزدوج, مناسبة لعرسان, كراج, سوبر ديلوكس. If not mentioned, return empty list."],
    "extra_features": ["Choose from: يوجد مصعد, موقف سيارات, حارس / أمن وحماية, نظام كهرباء احتياطي للطوارئ, انتركم, حديقة, منطقة شواء, بركة سباحة. If not mentioned, return empty list."]
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
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            parsed_json = json.loads(content)
            if redis_client:
                try:
                    redis_client.setex(cache_key, 86400, json.dumps(parsed_json))
                except Exception as e:
                    logger.error(f"Smart search cache write failed: {e}")
            return parsed_json
    except urllib.error.HTTPError as e:
        logger.error(f"HTTPError calling DeepSeek API: {str(e)}")
        return {"intent": "error", "message": "عذراً، هنالك ضغط كبير على محرك البحث الذكي حالياً. يرجى المحاولة مرة أخرى أو استخدام الفلاتر اليدوية."}
    except Exception as e:
        logger.error(f"Error calling DeepSeek API: {str(e)}")
        return {"intent": "error", "message": "عذراً، هنالك ضغط كبير على محرك البحث الذكي حالياً. يرجى المحاولة مرة أخرى أو استخدام الفلاتر اليدوية."}

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

def _load_location_data(db: Session):
    cities = [(c.id, c.name_ar) for c in db.query(models.City).all()]
    regions = [(r.id, r.city_id, r.name_ar) for r in db.query(models.Region).all()]
    aliases = [(a.alias_name, a.region_id) for a in db.query(models.RegionAlias).all()]
    return cities, regions, aliases

_ORDINALS = ["ثالث", "رابع", "خامس", "سادس", "سابع", "ثامن", "تاسع", "عاشر"]
# Aqaba residential areas are known by feminine ordinals: "الثالثة" -> "السكنية 3 (الثالثة)"
AQABA_ORDINAL_REGIONS = {f"{o}ه": f"السكنية {i} (ال{o}ة)" for i, o in enumerate(_ORDINALS, start=3)}
# Amman circles are known by masculine ordinals: "السابع" -> "الدوار السابع"
AMMAN_ORDINAL_REGIONS = {o: f"الدوار ال{o}" for o in ["اول", "ثاني"] + _ORDINALS[:-1]}

def map_ordinal_region(name: str, allow_aqaba: bool, allow_amman: bool):
    """Turns a bare ordinal into the region it means. Returns None when the ordinal
    belongs to a city other than the one the user stated."""
    norm = normalize_arabic(name)
    if norm.startswith("دوار "):
        if norm[len("دوار "):] in AMMAN_ORDINAL_REGIONS:
            return AMMAN_ORDINAL_REGIONS[norm[len("دوار "):]] if allow_amman else None
        return name
    if norm in AQABA_ORDINAL_REGIONS:
        return AQABA_ORDINAL_REGIONS[norm] if allow_aqaba else None
    if norm in AMMAN_ORDINAL_REGIONS:
        return AMMAN_ORDINAL_REGIONS[norm] if allow_amman else None
    return name

def build_search_query(db: Session, filters: dict):
    from sqlalchemy import or_
    query = db.query(models.AdSearchIndex)
    joined_ad = False
    
    if filters.get("category_id"):
        query = query.filter(models.AdSearchIndex.category_id == filters["category_id"])
        
    if filters.get("city_id"):
        query = query.filter(models.AdSearchIndex.city_id == filters["city_id"])
        
    # region_names never contains the city: the city is enforced by city_id above
    if filters.get("region_names"):
        query = query.join(models.Ad, models.AdSearchIndex.ad_id == models.Ad.id)
        joined_ad = True
        loc_conditions = [models.Ad.location.ilike(f"%{loc}%") for loc in filters["region_names"]]
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
        query = query.filter(models.AdSearchIndex.bedrooms == filters["bedrooms"])
        
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
    if "اخير" in w or "أخير" in w or "روف" in w: return 100 # usually top floor
    return None

@smart_search_router.post("/api/smart-voice-search", response_model=SmartSearchResponse)
def smart_voice_search(request: SmartSearchRequest, db: Session = Depends(get_db)):
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
    ai_response = extract_raw_data_via_deepseek(request.text, categories_str=categories_str)
    
    intent = ai_response.get("intent", "search")
    if intent == "error":
        return SmartSearchResponse(intent="search", result_count=0, filters_applied={}, action_required=ai_response.get("message"))
    if intent == "error":
        return SmartSearchResponse(intent="search", result_count=0, filters_applied={}, action_required=ai_response.get("message", "عذراً، النظام تحت ضغط عالي. يرجى الانتظار."))
    if intent != "search":
        return SmartSearchResponse(intent=intent, result_count=0, filters_applied={})
        
    raw = ai_response.get("raw_filters") or {}
    
    # STEP 2: Python Engine Smart Matching
    
    category_id = raw.get("category_id")
    
    # INTERCEPT: "بيت للايجار" -> "شقق للايجار" (301) unless "مستقل" is mentioned
    text_clean = request.text.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا').replace('ة', 'ه').lower()

    # Dynamic Validation using Dialect Dictionary
    from dialect_dictionary import TRANSACTION_SYNONYMS, CATEGORY_SYNONYMS

    # 1. Check for multiple property types dynamically
    found_props = []
    mapped_categories = set()
    
    # Sort keys by length descending to match longest first (e.g. "شقة فندقية" before "شقة")
    sorted_cat_keys = sorted(CATEGORY_SYNONYMS.keys(), key=len, reverse=True)
    
    for k in sorted_cat_keys:
        if k in text_clean:
            # Prevent substring matching (e.g. finding "شقة" inside "شقة فندقية")
            if not any(k in found_larger for found_larger in found_props):
                found_props.append(k)
                mapped_categories.add(CATEGORY_SYNONYMS[k])

    if False:
        props_str = " أو ".join(found_props[:2])
        return SmartSearchResponse(
            intent="search",
            result_count=0,
            filters_applied={},
            action_required=f"يرجى تحديد نوع عقار واحد فقط للبحث (مثلاً: {props_str})."
        )
        
    # 2. Check for rent/sale intent dynamically
    has_rent = False
    has_sale = False
    for k, v in TRANSACTION_SYNONYMS.items():
        if k in text_clean:
            if v == "rent":
                has_rent = True
            elif v == "sale":
                has_sale = True
                
    if not has_rent and not has_sale:
        return SmartSearchResponse(
            intent="search",
            result_count=0,
            filters_applied={},
            action_required="يرجى التحديد: هل تبحث عن عقار للإيجار أم للبيع؟"
        )

    if "بيت" in text_clean and ("ايجار" in text_clean or "اجار" in text_clean):
        if "مستقل" not in text_clean:
            category_id = 301  # شقق للايجار
            
    # Fallback: if DeepSeek failed to extract category, use Python mapped categories
    if category_id is None and len(mapped_categories) == 1:
        category_id = list(mapped_categories)[0]
    raw_locations = [str(l) for l in (raw.get("locations") or []) if l]
    raw_landmarks = raw.get("landmarks") or []
    if not isinstance(raw_landmarks, list):
        raw_landmarks = []
    stated_cities = [str(raw["city"])] if raw.get("city") else []

    cities, regions, aliases = _load_location_data(db)

    # The city the user stated decides which ordinals are meaningful
    stated_city_id = next(
        (c for c in (match_city(n, cities) for n in stated_cities + raw_locations) if c is not None), None
    )
    allow_aqaba_ordinals = stated_city_id is None or stated_city_id == match_city("العقبة", cities)
    allow_amman_ordinals = stated_city_id is None or stated_city_id == match_city("عمان", cities)

    # MANUAL INTERCEPT: DeepSeek struggles to extract Arabic ordinals as locations
    if allow_aqaba_ordinals:
        for aq_ord in ["ثالثه", "رابعه", "خامسه", "سادسه", "سابعه", "ثامنه", "تاسعه", "عاشره"]:
            if aq_ord in text_clean and aq_ord not in [normalize_arabic(l) for l in raw_locations]:
                raw_locations.append(aq_ord)

    import re
    if allow_amman_ordinals:
        for am_ord in ["اول", "ثاني", "ثالث", "رابع", "خامس", "سادس", "سابع", "ثامن", "تاسع"]:
            # Only extract if it's 'دوار', or preceded by spaces or commas and NOT preceded by 'طابق' or 'دوار'
            if f"دوار {am_ord}" in text_clean or f"دوار ال{am_ord}" in text_clean:
                raw_locations.append(f"دوار {am_ord}")
            else:
                # Check for isolated ordinals like "الثاني", "الرابع" which mean circles in Amman context
                pattern = r'(?<!طابق )\bال' + am_ord + r'\b'
                if re.search(pattern, text_clean):
                    raw_locations.append(f"دوار {am_ord}")

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
    
    WEST_TERMS = ["عمان الغربيه", "غرب عمان", "عمان غربيه", "عمان الغربية", "عمان غربية"]
    EAST_TERMS = ["عمان الشرقيه", "شرق عمان", "عمان شرقيه", "عمان الشرقية", "عمان شرقية"]
    BROAD_TERMS = WEST_TERMS + EAST_TERMS + ["عمان", "الاردن", "الأردن"]
    
    locs_clean = [loc.replace('ة', 'ه').replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا').strip() for loc in raw_locations]
    
    specific_locations = [loc for loc, lc in zip(raw_locations, locs_clean) if lc not in BROAD_TERMS]
    
    has_west = any(l in WEST_TERMS for l in locs_clean)
    has_east = any(l in EAST_TERMS for l in locs_clean)

    # West/East Amman only expand to their regions when no specific region was given
    zone_locations = []
    if not specific_locations:
        if has_west:
            zone_locations.extend(WEST_AMMAN_REGIONS)
        if has_east:
            zone_locations.extend(EAST_AMMAN_REGIONS)
    if has_west or has_east or any(l == "عمان" for l in locs_clean):
        stated_cities.append("عمان")

    mapped = [map_ordinal_region(l, allow_aqaba_ordinals, allow_amman_ordinals) for l in specific_locations]
    raw["locations"] = list(dict.fromkeys(m for m in mapped if m))

    # Locations: city first, then regions and landmarks inside that city only
    resolution = resolve_locations(
        cities, regions, aliases,
        city_names=stated_cities,
        region_names=raw["locations"],
        landmarks=raw_landmarks,
        soft_region_names=zone_locations,
    )
    city_name_by_id = dict(cities)

    if resolution.ambiguous:
        parts = [
            f"'{name}' ({'، '.join(city_name_by_id[c] for c in c_ids)})"
            for name, c_ids in resolution.ambiguous.items()
        ]
        return SmartSearchResponse(
            intent="search",
            result_count=0,
            filters_applied={},
            action_required=f"منطقة {' و'.join(parts)} موجودة في أكثر من مدينة. يرجى كتابة اسم المدينة مع المنطقة."
        )

    region_ids, not_found_regions, city_id = resolution.region_ids, resolution.not_found, resolution.city_id

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
            
    # Reverse map numbers to words for UI chips if missing
    floor_mapping = {
        -1: "الطابق الأرضي", -2: "طابق التسوية",
        1: "الطابق الأول", 2: "الطابق الثاني", 3: "الطابق الثالث", 4: "الطابق الرابع",
        5: "الطابق الخامس", 6: "الطابق السادس", 100: "طابق أخير"
    }
    for fn in floor_numbers:
        if fn in floor_mapping:
            if floor_mapping[fn] not in floor_words:
                floor_words.append(floor_mapping[fn])
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
    city_name = city_name_by_id.get(city_id) if city_id else None
    region_name_by_id = {r_id: name for r_id, _, name in regions}
    region_names = [region_name_by_id[r_id] for r_id in region_ids]
    # City first: /api/ads treats a leading city as the scope of the regions after it,
    # so a region name shared with another city can't leak into the results.
    location_names = ([city_name] if city_name else []) + region_names

    tags = []
    
    if "من المالك" in text_clean or "من مالك" in text_clean:
        tags.append("من المالك مباشرة")
    
    if raw.get("bedrooms_number") is not None:
        tags.append(f"bedrooms:{raw['bedrooms_number']}")
    
    if raw.get("bathrooms_number") is not None:
        tags.append(f"bathrooms:{raw['bathrooms_number']}")
        
    fw = raw.get("furnishing_word")
    if fw in ["مفروشة", "غير مفروشة", "مفروش جزئياً"]:
        tags.append(f"furnished:{fw}")
        
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
        "region_names": region_names,
        "tags": tags,
        "not_found_regions": not_found_regions
    }
    
    query = build_search_query(db, applied_filters)
    count = query.count()
    
    suggestion = None
    if not_found_regions:
        names = " أو ".join(not_found_regions)
        if city_name and region_ids:
            suggestion = f"ملاحظة: لم نجد '{names}' في {city_name}، تم عرض باقي المناطق المطلوبة."
        elif city_name:
            suggestion = f"ملاحظة: لم نجد '{names}' في {city_name}، تم عرض نتائج {city_name} كاملة."
        else:
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
        applied_filters["tags"] = tags = [t for t in tags if t.split(":", 1)[-1] not in features_list]
        query = build_search_query(db, applied_filters)
        count = query.count()
        if count > 0:
            return SmartSearchResponse(intent=intent, result_count=count, filters_applied=applied_filters, suggestion="لم نجد نتائج بكل الميزات الإضافية المطلوبة، تم تجاهلها لعرض نتائج أقرب.")

    # 2. Remove floor
    if applied_filters.get("floor_numbers"):
        applied_filters["floor_numbers"] = []
        applied_filters["tags"] = tags = [t for t in tags if not t.startswith("floor:")]
        query = build_search_query(db, applied_filters)
        count = query.count()
        if count > 0:
            return SmartSearchResponse(intent=intent, result_count=count, filters_applied=applied_filters, suggestion="لم نجد نتائج في نفس الطابق المطلوب، تم تجاهل الطابق.")
            
    # 3. Remove area
    if min_area is not None or max_area is not None:
        applied_filters["min_area"] = None
        applied_filters["max_area"] = None
        applied_filters["tags"] = tags = [t for t in tags if not t.startswith(("min_area:", "max_area:"))]
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
            
    # 5. Remove Bedrooms (Skipped to strictly enforce bedroom requirements)
    # Bedrooms are a strict requirement for most users, dropping them leads to irrelevant results (e.g. 2 bedrooms when 4 are requested).
    pass
            
    # 6. Fallback to just City + Category
    if region_ids:
        applied_filters["region_ids"] = []
        applied_filters["region_names"] = []
        applied_filters["location_names"] = [city_name] if city_name else []
        query = build_search_query(db, applied_filters)
        count = query.count()
        
    try:
        from models import SearchQueryLog
        query_log = SearchQueryLog(
            query_text=request.text[:500],
            results_count=count,
            extracted_tags=json.dumps(ai_response)[:500]
        )
        db.add(query_log)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log search query: {e}")
        
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
