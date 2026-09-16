import os
import json
import logging
import urllib.request
import urllib.error
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
import models
from database import get_db

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

def get_deepseek_intent_and_filters(text: str) -> dict:
    url = "https://api.deepseek.com/chat/completions"
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        logger.error("DEEPSEEK_API_KEY is not set.")
        raise HTTPException(status_code=500, detail="Search service configuration error.")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    system_prompt = """أنت مساعد ذكي لتطبيق عقارات أردني اسمه "سوق كوم". المستخدم سيتحدث بالعامية الأردنية أو بالعربي أو بالإنجليزي أو بمزيج منهم.

مهمتك:
1. فهم نية المستخدم (intent):
   - "search": يريد البحث عن عقار (الحالة الافتراضية)
   - "post_ad": يريد نشر/بيع/تأجير عقار (مثل: "بدي أبيع شقتي", "بدي أنزل إعلان")
   - "my_ads": يريد رؤية إعلاناته (مثل: "وين إعلاناتي", "أعرض إعلاناتي")
   - "help": يطلب مساعدة (مثل: "كيف أستخدم التطبيق")

2. إذا كانت النية "search"، استخرج الفلاتر التالية من كلامه:
   - category: اسم الفئة الفرعية الدقيقة (المستوى الثالث دائماً). القيم المسموحة فقط:
     للبيع: "شقق للبيع" | "ستوديوهات للبيع" | "فلل ومنازل" | "بيوت مستقلة للبيع" | "تاون هاوس للبيع" | "دوبلكس / بنتهاوس" | "ملحق / شف" | "محلات ومراكز للبيع" | "مكاتب للبيع" | "عمارة كاملة للبيع"
     للإيجار: "شقق للإيجار" | "فلل للإيجار" | "ستوديو للإيجار" | "غرفة للإيجار" | "محلات للإيجار" | "مكاتب للإيجار" | "مستودعات ومخازن" | "صالات ومراكز" | "عمارة كاملة للإيجار"
     أراضي: "أراضي سكنية" | "أراضي تجارية" | "أراضي زراعية"
     مزارع وشاليهات: "مزرعة" | "شاليه" | "مزرعة وشاليه"
     ملاحظة مهمة جداً: لا تستخدم أبداً فئة عامة مثل "عقارات للبيع" أو "عقارات للإيجار" أو "سكني" أو "أراضي". دائماً استخدم الفئة الأكثر تحديداً. مثلاً إذا قال المستخدم "شقة" فالفئة هي "شقق للبيع" أو "شقق للإيجار" حسب السياق. إذا قال "أرض" بدون تحديد استخدم "أراضي سكنية".
   - city: اسم المدينة (عمان، إربد، الزرقاء، العقبة، مادبا، جرش، عجلون، الكرك، الطفيلة، معان، المفرق، البلقاء، السلط)
   - region: اسم المنطقة/الحي (خلدا، عبدون، الرابية، دابوق، الشميساني، تلاع العلي، الجبيهة، صويلح، ماركا، الهاشمي، أبو نصير، طبربور، الجاردنز، الصويفية، أم أذينة، الدوار السابع، اليادودة، شفا بدران، الأردن، ضاحية الرشيد، خريبة السوق، الزهور)
   - min_price: الحد الأدنى للسعر (رقم)
   - max_price: الحد الأعلى للسعر (رقم)
   - bedrooms: عدد غرف النوم (رقم)
   - bathrooms: عدد الحمامات (رقم)
   - min_area: الحد الأدنى للمساحة بالمتر المربع (رقم)
   - max_area: الحد الأعلى للمساحة (رقم)
   - furnished: مفروشة (true/false)
   - floor: رقم الطابق (رقم)
   - rent_duration: مدة الإيجار (شهري/سنوي/يومي) - فقط للإيجار

ملاحظات مهمة:
- "ألف" = 1000، "80 ألف" = 80000
- إذا قال "ما يزيد عن" أو "أقل من" أو "بحدود" → ضعها في max_price
- إذا قال "فوق" أو "أكثر من" → ضعها في min_price
- إذا لم يذكر فلتر معين، اجعل قيمته null
- إذا قال "غرفتين" = 2، "ثلاث غرف" = 3

أجب بصيغة JSON فقط بدون أي نص إضافي:
{
  "intent": "search" | "post_ad" | "my_ads" | "help",
  "filters": {
    "category": string | null,
    "city": string | null,
    "region": string | null,
    "min_price": number | null,
    "max_price": number | null,
    "bedrooms": number | null,
    "bathrooms": number | null,
    "min_area": number | null,
    "max_area": number | null,
    "furnished": boolean | null,
    "floor": number | null,
    "rent_duration": string | null
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
        with urllib.request.urlopen(req, timeout=20) as response:
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
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Error calling DeepSeek for suggestion: {str(e)}")
        return "لا توجد نتائج مطابقة، جرب تغيير بعض الفلاتر للحصول على نتائج."

def map_category(category_name: str, intent_filters: dict) -> Optional[int]:
    if not category_name:
        return None
        
    # LEAF-LEVEL ONLY mapping - never use parent categories (2, 3, 10313)
    mapping = {
        # للبيع
        "شقق للبيع": 10301,
        "ستوديوهات للبيع": 10302,
        "فلل ومنازل": 10101,
        "بيوت مستقلة للبيع": 10102,
        "تاون هاوس للبيع": 10104,
        "دوبلكس / بنتهاوس": 10103,
        "دوبلكس": 10103,
        "بنتهاوس": 10103,
        "ملحق / شف": 10105,
        "محلات ومراكز للبيع": 10303,
        "مكاتب للبيع": 10876,
        "عمارة كاملة للبيع": 10878,
        # للإيجار
        "شقق للإيجار": 301,
        "فلل للإيجار": 302,
        "ستوديو للإيجار": 10015,
        "غرفة للإيجار": 10999,
        "محلات للإيجار": 10853,
        "مكاتب للإيجار": 10874,
        "مستودعات ومخازن": 10875,
        "صالات ومراكز": 10872,
        "عمارة كاملة للإيجار": 10878,
        # أراضي (leaf level)
        "أراضي سكنية": 19000,
        "أراضي تجارية": 19010,
        "أراضي زراعية": 19040,
        # مزارع وشاليهات
        "مزرعة": 18001,
        "شاليه": 18002,
        "مزرعة وشاليه": 18003,
    }
    
    # Exact match first
    if category_name in mapping:
        return mapping[category_name]
    
    # Fuzzy match
    cat_str = category_name.lower()
    for key, val in mapping.items():
        if key in cat_str or cat_str in key:
            return val
            
    # Keyword-based matching - ALWAYS resolve to leaf subcategory
    if "إيجار" in cat_str or "ايجار" in cat_str:
        if "ستوديو" in cat_str:
            return 10015
        if "فلل" in cat_str or "فيلا" in cat_str:
            return 302
        if "محل" in cat_str:
            return 10853
        if "مكتب" in cat_str:
            return 10874
        if "غرف" in cat_str:
            return 10999
        if "مستودع" in cat_str or "مخزن" in cat_str:
            return 10875
        # Default rental = شقق للإيجار (leaf)
        return 301
        
    if "بيع" in cat_str:
        if "ستوديو" in cat_str:
            return 10302
        if "أرض" in cat_str or "اراضي" in cat_str or "ارض" in cat_str:
            return 19000  # أراضي سكنية as default
        if "فلل" in cat_str or "فيلا" in cat_str:
            return 10101
        if "بيت" in cat_str or "بيوت" in cat_str:
            return 10102
        if "محل" in cat_str:
            return 10303
        if "مكتب" in cat_str:
            return 10876
        if "عمار" in cat_str:
            return 10878
        # Default sale = شقق للبيع (leaf)
        return 10301

    # General keywords
    if "شقة" in cat_str or "شقق" in cat_str:
        return 10301  # شقق للبيع as default
    if "فيلا" in cat_str or "فلل" in cat_str:
        return 10101
    if "أرض" in cat_str or "ارض" in cat_str or "اراضي" in cat_str:
        return 19000
    if "مزرعة" in cat_str or "مزارع" in cat_str:
        return 18001
    if "شاليه" in cat_str:
        return 18002

    return None

def build_search_query(db: Session, filters: dict):
    q = db.query(models.Ad).join(models.AdSearchIndex, models.Ad.id == models.AdSearchIndex.ad_id)
    
    q = q.filter(
        models.Ad.is_published == True,
        models.Ad.is_paused == False,
        models.Ad.is_sold == False,
        models.Ad.is_rejected == False
    )

    if filters.get("category_id"):
        # For simplicity, assuming exact match or you might want to handle parent/child matching
        q = q.filter(models.AdSearchIndex.category_id == filters["category_id"])
        
    if filters.get("city_id"):
        q = q.filter(models.AdSearchIndex.city_id == filters["city_id"])
        
    if filters.get("region_id"):
        q = q.filter(models.AdSearchIndex.region_id == filters["region_id"])
        
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
        
    # Build area would require min_area/max_area support in AdSearchIndex
    if filters.get("min_area") is not None and hasattr(models.AdSearchIndex, 'build_area'):
        q = q.filter(models.AdSearchIndex.build_area >= filters["min_area"])
        
    if filters.get("max_area") is not None and hasattr(models.AdSearchIndex, 'build_area'):
        q = q.filter(models.AdSearchIndex.build_area <= filters["max_area"])
        
    return q

@smart_search_router.post("/api/smart-voice-search", response_model=SmartSearchResponse)
def smart_voice_search(request: SmartSearchRequest, db: Session = Depends(get_db)):
    ai_response = get_deepseek_intent_and_filters(request.text)
    
    intent = ai_response.get("intent", "search")
    if intent != "search":
        return SmartSearchResponse(
            intent=intent,
            result_count=0,
            filters_applied={}
        )
        
    ai_filters = ai_response.get("filters", {})
    
    # Map category
    category_id = map_category(ai_filters.get("category"), ai_filters)
    
    # Map city
    city_id = None
    if ai_filters.get("city"):
        city_name = ai_filters["city"]
        city = db.query(models.City).filter(
            or_(
                models.City.name_ar.ilike(f"%{city_name}%"),
                models.City.name_en.ilike(f"%{city_name}%")
            )
        ).first()
        if city:
            city_id = city.id
            
    # Map region
    region_id = None
    if ai_filters.get("region"):
        region_name = ai_filters["region"]
        region_query = db.query(models.Region).filter(
            or_(
                models.Region.name_ar.ilike(f"%{region_name}%"),
                models.Region.name_en.ilike(f"%{region_name}%")
            )
        )
        if city_id:
            region_query = region_query.filter(models.Region.city_id == city_id)
            
        region = region_query.first()
        if not region:
            # Check aliases
            alias_query = db.query(models.RegionAlias).join(models.Region).filter(
                models.RegionAlias.alias_name.ilike(f"%{region_name}%")
            )
            if city_id:
                alias_query = alias_query.filter(models.Region.city_id == city_id)
            alias = alias_query.first()
            if alias:
                region_id = alias.region_id
        else:
            region_id = region.id

    applied_filters = {
        "category_id": category_id,
        "city_id": city_id,
        "region_id": region_id,
        "min_price": ai_filters.get("min_price"),
        "max_price": ai_filters.get("max_price"),
        "bedrooms": ai_filters.get("bedrooms"),
        "bathrooms": ai_filters.get("bathrooms"),
        "furnished": ai_filters.get("furnished"),
        "floor": ai_filters.get("floor"),
        "min_area": ai_filters.get("min_area"),
        "max_area": ai_filters.get("max_area"),
        "category_name": ai_filters.get("category"),
        "city_name": ai_filters.get("city"),
        "region_name": ai_filters.get("region")
    }
    
    query = build_search_query(db, applied_filters)
    count = query.count()
    
    if count > 0:
        return SmartSearchResponse(
            intent=intent,
            result_count=count,
            filters_applied=applied_filters
        )
        
    # Fallback system
    fallback_order = [
        "max_price", "min_price", "region_id", "bedrooms", 
        "bathrooms", "furnished", "floor", "min_area", "max_area"
    ]
    
    alternative_filters = applied_filters.copy()
    alternative_count = 0
    removed_filter_name = ""
    
    for filter_key in fallback_order:
        if alternative_filters.get(filter_key) is not None:
            temp_val = alternative_filters[filter_key]
            alternative_filters[filter_key] = None
            
            fallback_query = build_search_query(db, alternative_filters)
            alternative_count = fallback_query.count()
            
            if alternative_count > 0:
                removed_filter_name = filter_key
                break
                
    if alternative_count > 0:
        suggestion = generate_fallback_suggestion(applied_filters, alternative_count, removed_filter_name)
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
