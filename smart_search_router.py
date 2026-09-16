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

    system_prompt = """You are an advanced AI assistant for a Jordanian real estate classifieds app named "Sooq Com".
The user will speak in Jordanian Arabic dialect, MSA (Fusha), English, or a mix.

Your task is to:
1. Detect the user's intent:
   - "search": Wants to find/search for a property (Default)
   - "post_ad": Wants to publish/sell/rent out a property (e.g., "بدي أبيع شقتي")
   - "my_ads": Wants to view their own ads (e.g., "وين إعلاناتي")
   - "help": Asking for help/instructions

2. If intent is "search", extract the following filters.
CRITICAL: For 'category', you MUST choose ONLY from the deepest level category (leaf nodes without any children) in the following Real Estate Category Tree. Never output parent categories.

Real Estate Category Tree:
- Level 1: عقارات للبيع
  - Level 2: سكني
    - Level 3: فلل وقصور
    - Level 3: بيوت مستقلة للبيع
    - Level 3: دوبلكس / بنتهاوس
    - Level 3: طابق كامل للبيع
    - Level 3: ملحق / روف
    - Level 3: شقق للبيع
    - Level 3: ستوديوهات للبيع
    - Level 3: أخرى
    - Level 3: عمارات سكنية
  - Level 2: تجاري
    - Level 3: محلات ومعارض للبيع
      - Level 4: محلات تجارية عامة
      - Level 4: كشك / بسطة / مساحة مفتوحة
      - Level 4: محل مغلق
      - Level 4: بسطة / مساحة مفتوحة
    - Level 3: مكاتب للبيع
      - Level 4: مقر مستقل
      - Level 4: مكتب
      - Level 4: مقر شركة
      - Level 4: مبنى إداري
    - Level 3: معارض تجارية متخصصة
      - Level 4: معارض سيارات
      - Level 4: معرض مستقل
      - Level 4: معارض أجهزة كهربائية وإلكترونيات
      - Level 4: معارض ملابس وأحذية
    - Level 3: صالونات ومراكز تجميل
      - Level 4: صالون حلاقة رجالي
      - Level 4: صالون تجميل نسائي / سبا
    - Level 3: مطاعم ومقاهي
      - Level 4: مطعم
      - Level 4: كافيه / مقهى
      - Level 4: مطعم وكافيه
    - Level 3: مخازن ومستودعات
      - Level 4: مخزن متصل بمحل
      - Level 4: مخزن خلفي
      - Level 4: مستودع مستقل
      - Level 4: مخزن
    - Level 3: عيادات ومراكز طبية
      - Level 4: عيادة
      - Level 4: مركز طبي
      - Level 4: مختبر
      - Level 4: صيدلية
    - Level 3: مراكز تعليمية
      - Level 4: مدرسة
      - Level 4: روضة
      - Level 4: مركز تدريب
      - Level 4: معهد
    - Level 3: صالات ومرافق
      - Level 4: صالة رياضية
      - Level 4: صالة أفراح
      - Level 4: صالة عرض
      - Level 4: نادي
    - Level 3: فنادق وسياحة
      - Level 4: فندق
      - Level 4: بيت ضيافة
      - Level 4: نزل
    - Level 3: أراضي تجارية
      - Level 4: أرض تجارية
      - Level 4: أرض صناعية
      - Level 4: أرض استثمارية
    - Level 3: مباني تجارية كاملة
      - Level 4: عمارة تجارية
      - Level 4: مجمع تجاري
      - Level 4: مول
      - Level 4: مبنى متعدد الاستخدام
    - Level 3: أخرى
  - Level 2: أراضي
    - Level 3: أراضي سكنية
    - Level 3: أراضي تجارية
    - Level 3: أراضي صناعية
    - Level 3: أراضي زراعية
    - Level 3: أراضي سياحية
    - Level 3: أراضي متعددة الاستخدام
      - Level 4: أرض تنظيم خاص
      - Level 4: أرض استثمار
      - Level 4: أرض استعمال مختلط
      - Level 4: أرض مشروع
    - Level 3: أراضي حكومية / تنظيم خاص
      - Level 4: أرض أملاك دولة
      - Level 4: أرض وقف
      - Level 4: أرض تنظيم حكومي
    - Level 3: أراضي بدون تنظيم
      - Level 4: أرض خارج التنظيم
      - Level 4: أرض بادية
      - Level 4: أرض فضاء
      - Level 4: أرض غير مصنفة
  - Level 2: مزارع
    - Level 3: مزارع زراعية
      - Level 4: مزرعة خضار
      - Level 4: مزرعة فواكه
      - Level 4: مزرعة زيتون
      - Level 4: مزرعة حمضيات
      - Level 4: مزرعة محاصيل
      - Level 4: مزرعة أشجار
    - Level 3: مزارع تربية حيوانات
      - Level 4: مزرعة أغنام
      - Level 4: مزرعة أبقار
      - Level 4: مزرعة دواجن
      - Level 4: مزرعة خيول
      - Level 4: مزرعة أسماك
      - Level 4: مزرعة نحل
    - Level 3: مزارع استثمارية
      - Level 4: مزرعة استثمارية
      - Level 4: مزرعة منتجة
      - Level 4: مزرعة مشروع
      - Level 4: مزرعة تجارية
    - Level 3: مزارع مع سكن
      - Level 4: مزرعة مع بيت
      - Level 4: مزرعة مع فيلا
      - Level 4: مزرعة مع استراحة
      - Level 4: مزرعة مع شاليه
    - Level 3: مزارع سياحية / ترفيهية
      - Level 4: مزرعة سياحية
      - Level 4: مزرعة رحلات
      - Level 4: مزرعة منتجع
      - Level 4: مزرعة فعاليات
    - Level 3: مزارع مجهزة بالبنية التحتية
      - Level 4: مزرعة مع بئر
      - Level 4: مزرعة مع كهرباء
      - Level 4: مزرعة مع بيت بلاستيك
      - Level 4: مزرعة مع مستودعات
    - Level 3: مزارع صناعية / إنتاجية
      - Level 4: مزرعة أعلاف
      - Level 4: مزرعة ألبان
      - Level 4: مزرعة دواجن تجارية
      - Level 4: مزرعة إنتاج غذائي
    - Level 3: مزارع غير مستغلة
      - Level 4: مزرعة غير مزروعة
      - Level 4: مزرعة أرض فقط
      - Level 4: مزرعة بحاجة تأهيل
      - Level 4: مزرعة غير مستثمرة
    - Level 3: أخرى
  - Level 2: شاليهات / منتجعات / بيوت ريفية
    - Level 3: شاليهات
      - Level 4: شاليه مستقل
      - Level 4: شاليه ضمن مجمع
      - Level 4: شاليه مع مسبح
      - Level 4: شاليه مع حديقة
      - Level 4: شاليه مع إطلالة
    - Level 3: منتجعات
      - Level 4: منتجع سياحي
      - Level 4: منتجع عائلي
      - Level 4: منتجع علاجي
      - Level 4: منتجع جبلي
      - Level 4: منتجع بحري
    - Level 3: استراحات ومزارع ترفيهية
      - Level 4: استراحة
      - Level 4: استراحة عائلية
      - Level 4: مزرعة ترفيهية
      - Level 4: مزرعة مع مسبح
    - Level 3: شقق فندقية
      - Level 4: شقة فندقية
      - Level 4: جناح فندقي
      - Level 4: فيلا فندقية
    - Level 3: فلل سياحية
      - Level 4: فيلا سياحية
      - Level 4: فيلا ضمن منتجع
      - Level 4: فيلا عطلات
    - Level 3: مواقع تخييم ورحلات
      - Level 4: موقع تخييم
      - Level 4: مخيم سياحي
      - Level 4: مخيم صحراوي
      - Level 4: موقع كرفانات
    - Level 3: بيوت ضيافة
      - Level 4: بيت ضيافة
      - Level 4: نُزل
      - Level 4: نُزل ريفي
      - Level 4: بيت تراثي سياحي
    - Level 3: مشاريع سياحية
      - Level 4: مشروع منتجع
      - Level 4: مشروع شاليهات
      - Level 4: أرض مشروع سياحي
      - Level 4: مجمع سياحي
    - Level 3: بيوت ريفية
      - Level 4: بيت ريفي
      - Level 4: بيت ريفي سياحي
      - Level 4: بيت تراثي
      - Level 4: بيت طيني
    - Level 3: أخرى
- Level 1: عقارات للإيجار
  - Level 2: سكن مشترك
    - Level 3: سكن طلاب (ذكور)
    - Level 3: سكن طالبات (إناث)
    - Level 3: سكن موظفين
    - Level 3: سكن موظفات
    - Level 3: غرفة برايفت للإيجار
    - Level 3: سرير في غرفة مشتركة
  - Level 2: سكني
    - Level 3: شقق للإيجار
    - Level 3: ستوديوهات للإيجار
    - Level 3: فلل وقصور
    - Level 3: بيوت مستقلة للإيجار
    - Level 3: دوبلكس / بنتهاوس
    - Level 3: طابق كامل للإيجار
    - Level 3: ملحق / روف
  - Level 2: تجاري
    - Level 3: محلات ومعارض للإيجار
    - Level 3: مكاتب للإيجار
    - Level 3: معارض تجارية متخصصة
    - Level 3: صالونات ومراكز تجميل
    - Level 3: مطاعم ومقاهي
    - Level 3: مخازن ومستودعات
    - Level 3: مراكز تعليمية
    - Level 3: أراضي تجارية
    - Level 3: مباني تجارية كاملة
    - Level 3: أخرى
    - Level 3: عيادات ومراكز طبية
    - Level 3: صالات ومرافق
    - Level 3: فنادق وسياحة
  - Level 2: مزارع
  - Level 2: شاليهات / منتجعات
  - Level 2: بيوت ريفية

Note: If the user says "شقة" (apartment) without specifying, default to "شقق للبيع". If they say "استوديو للايجار" output "ستوديو للإيجار".

Extract these fields:
- category: The exact 3rd-level Arabic category name from the list above.
- city: City name in Arabic. You MUST choose ONLY from the valid cities list below.
- region: Neighborhood/area name in Arabic. You MUST choose ONLY from the valid regions list below. If the user mentions a region with prefixes like 'بـ' or 'في' (e.g., "بالجاردنز", "في عبدون"), you MUST extract the exact region name from the list without prefixes (e.g., "الجاردنز", "عبدون").

Cities and Regions (Use ONLY these exact names):
- City: عمان | Regions: ابو السوس, ابو النعير, ابو علندا, ابو نصير, ارينبه الغربية, البقعه, البنيات, الجبيهة, الدمينه, الدوار الرابع, الدوار الثامن, الذهيبه الشرقيه, الروابي, الصويفية, العبدلي, العبدلية, اللبّن, المدينة الرياضية, المناره, ام اذينة الشرقي, ام البساتين, ام الدنانير, ام السماق, أم العمد, ام زويتينة, تلاع العلي الشمالي, حوارة, دير غبار, زويزا, أخرى, شارع المدينة, ضاحية الامير حسن, ضاحية الامير راشد, ضاحية الحاج حسن, ضاحية الرشيد, وادي السرور, وادي صقرة, دوار الداخلية, دوار الواحة, شارع المدينة المنورة, أم الحيران, إسكان المالية والزراعة, إسكان الملكية, النويجيس, بزنس بارك, جبل القلعة, دوار الكيلو, دوار المشاغل, شارع الحزام, شارع مادبا, ضاحية الأميرة إيمان, طلوع نيفين, عين غزال, وادي الرمم, البحاث, البصة, البيضاء, الجاردنز, الجويدة, الجيزة, الحرّيّة, الحسنية, الحمر, الحمرانية, الخريم, الخزنة, الدوار الأول, الدوار الثاني, الدوار الثالث, الدوار السابع, الديار, الذراع, الذهيبة, الرابية, الربوة, الرجوم, الرجيب, الرضوان, الرقيم, الرونق, الزهراء, الزيتونة, السهل, الصناعة, الضياء, الطنيب, الظهير, العال, العدلية, العروبة, العودة, الفروسية, الفيصل, القسطل, القصبات, القويسمة, الكرسي, الكمالية, الماضونة, المحطة, المشقر, المعادي, المقابلين, الموقر, النهارية, ضاحية الأرز, الهاشمي الجنوبي, الوحدات, اليادودة, الياسمين, اليرموك, ام اذينة, ام اذينة الغربي, أم الأسود, ارينبه الشرقية, أم رمانة, أم شطيرات, أم قصير, ام نوارة, بدر, بسمان, بلال, بيرين, تلاع العلي, جاوا, جبل الأشرفية, جبل التاج, جبل اللويبدة, جبل المريخ, جبل النزهة, جبل النصر, جبل عمان, جلول, حسبان, حطين, حي نزال, خان الزبيب, خربة السوق, راس العين, رجم الشامي, سالم, سحاب, شارع الأردن, شارع الجامعة, شارع مكة, شفا بدران, شميساني, صافوط, صويلح, ضاحية الأمير علي, ضاحية النخيل, ضبعه, طبربور, طريق المطار, عبدون, عبدون الجنوبي, عبدون الشمالي, عراق الامير, عيون الذيب, قعفور, ماحص, ماركا, ماركا الشمالية, مرج الحمام, مرج الفرس, موبص, وادي الحدادة, وادي السير, وادي الطي, تلاع العلي الشرقي, ياجوز, وادي العش, الأمير حمزة, الايمان, البيادر, الجميل, الجندويل, الخشافية, الخضراء, الدوار الخامس, الرجيلة, الزعفران, الفحيص, القصور, الكوم الشرقي, الكوم الغربي, المشتى, المنصور, الهاشمي الشمالي, ام الرصاص, أم الكندم, بدر الجديدة, جبل الجوفة, جبل الحسين, جبل النظيف, خلدا, دابوق, زبود, زينب, صالحية العابد, ضاحية الحسين, عرجان, عين رباط, ماركا الجنوبية, ناعور, وسط البلد, الجبل الأخضر, الدمينا, الدوار السادس, الذهيبة الغربيه, الزميلة, السرو, القنيطره, الكتيفه, المرقب, المستندة, المغيرات, النقيرة, جبل الزهور, حجار النوابلسة, حي البركة, حي الخالدين, حي الرحمانية, حي الصالحين, حي الصحابة, حي عدن, رجم الشوف, رجم عميش, زملة العليا, زينات الربوع, شارع المية, صوفا, ضاحية الاستقلال, ضاحية الاقصى, ضاحية الروضة, طريق المطار - جسر ديونز, طريق المطار - جسر مادبا, طلوع المصدار
- City: إربد | Regions: الراهبات, أخرى, إشارة بردى, اسكان المهندسين, الحي الشمالي, الرمثا, الهابي لاند, ايدون, بيت راس, جامعة اليرموك, حديقة تونس, حي التركمان, دوار الاتصالات, دوار الجامعة, شارع أبو راشد, شارع البتراء, شارع السلام, قرية SOS, كازية السلام, كازية عاشور, كرم حجازي, كفر يوبا, كفرعان, مثلث الإسكان, مجمع عمان الجديد, مستشفى اربد التخصصي, مستشفى بديعة وبسمة, ناطفة, وادي النمل, ابان, اشارة الاسكان, الأشرفية, الباقورة, البلد, التل, الحصن, الحي الشرقي, الحي الغربي, الخراج, الزمالية, السنبلة, السوق, الشجرة, الشيخ حسين, الصريح, العدسية, المدينة الصناعية, المغير, الملعب البلدي, المنشية, النعيمة, ام الجدايل, ام قيس, بشرى, بصيلة, بيت يافا, جامعة العلوم والتكنولوجيا, ججين, جحفية, حبراص, حبكا, حريما, حكما, حور, حوفا, حي الأبرار, حي الزهور, حي القصيلة, خرجا, دوار الثقافة, دوار القبة, دير أبي سعيد, دير السعنة, دير يوسف, زبدة, زهر, سال, سحم, اربد مول, سوم, شارع البارحة, شارع القدس, شارع الهاشمي, شارع حكما, شارع فلسطين, صالة الشرق, صما, صمد, صيدور, طبقة فحل, علعال, عنبة, فوعرا, قرية صمد, قم, قميم, كتم, كفر ابيل, كفر أسد, كفر الماء, كفر سوم, لواء الطيبة, مخربا, مرو, مستشفى الأميرة بسمة, مستشفى الملك عبدالله, ملكا, مندح, هام, وادي الريان, وقاص, يبلا, سيل الحمة, شارع الثلاثين, شارع فوعرة, غرفة التجارة, أبو سيدو, ارحابا, اسكان الضباط, الأندلس, البارحة, الحي الجنوبي, الروضة, الشونة الشمالية, المزار الشمالي, النزهة, برشتا, تقبل, جديتا, جمحا, حنينا, حي الأفراح, حي المنارة, حي الورود, زوبيا, سما الروسان, سمر, سموع, شارع الحصن, شطنا, قرية حاتم, كريمة, كفر جايز, كفر راكب, مجمع الأغوار الجديد, مسجد حسن التل, اسكان الأطباء, اسكان العاملين, اشارة الدراوشة, اشارة الملكة نور, الحسبة المركزية, المخيبة التحتة, المدرسة الشاملة, المشارع, بيت أديس, تبنه, جيفين, حدائق الملك عبدالله, حرثا, حي التلول, حي طوال, حي عالية, خربة البرز, خربة قاسم, دوار البياضة, دوار الدرة, دوار العيادات, دوار اللوازم, دوار النسيم, دوار سال, دوار شركة الكهرباء, دوار صحارى, دوقرا, ضاحية الأمير راشد, قراقوش, كفرعوان, كلية بنات اربد, مجمع الشيخ خليل, مستشفى ايدون العسكري, خلف السيفوي
- City: الزرقاء | Regions: أخرى, الحلابات الغربي, حي ابن سينا, حي الرشاد, حي شبيب, شارع صلاح الدين, ضاحية الأميرة سلمى, مخيم الزرقاء, مدينة المجد, أبو الزيغان, الأزرق, الحاووز, الرحيل, الرصيفة, الزرقاء الجديدة, السخنة, الضليل, الغباوي, المشيرفة, المنطقة الحرة, النصر, جامعة الزرقاء الخاصة, جبل الاميرة رحمة, جبل طارق, جناعة, حي النزهة, حي رمزي, دوقرة, رجم الشوك, شارع الجيش, صروت, ضاحية المدينة المنورة, عوجان, حي الأمير محمد, مخيم حطين, وادي الحجر, حي الجندي, حي جعفر الطيار, أم صليح, البستان, التطوير الحضري, الزواهرة, القنية, الهاشمية, جبل الأبيض, جبل الأمير حسن, حي الحسين, حي الرشيد-الرصيفة, حي شاكر, حي معصوم, خو, شارع السعادة, شومر, مدينة الشرق, حي الأمير عبدالله, اتوستراد, اسكان البتراوي, اسكان طلال-الرصيفة, التطوير الحضري-الرصيفة, الثوره العربية الكبرى, الرصيفة الجنوبي, العالوك, الغويرية, القادسية-الرصيفة, جبل الأمير حمزة, جبل الأمير فيصل, جبل الشمالي-الرصيفة, جبل المغير, جريبا, حي الاسكان, شارع المصفاة, ضاحية الأميرة هيا, ضاحية مكة المكرمة, غريسا, قصر الحلابات الشرقي
- City: السلط | Regions: أخرى, أرميمين, أم جوزة, اسكان المهندسين, البحيرة, البقعان, البقيع, الصافح, الميسة, بطنا, شارع الستين, عرقوب الخاخة, البلقاء, الجادور, الجدعة, الخندق, الزهور, السلالم, دير علا, زي, سويمة, سيحان, شفا العامرية, الخضر, السليحي, الشونه الجنوبيه, الصبيحي, الصوارفة, العيزرية, القلعة, المغاريب, الميدان, النقب, أم الدنانير, جلعد, حي الخرابشة, علان, عيرا, عين الباشا, كفرهودا, نقب الدبور, وادي شعيب, يرقا
- City: مادبا | Regions: أخرى, الجامعة الألمانية, الخطابية, النديم, دليلة المطيرات, الامام العزالي, الجبيل, الفيحاء, الفيصلية, جرينة, حنينا الغربيه, دليله الحمايده, ذيبان, لب, ماعين, مخيم مادبا, مكاور, منجا, وسط مادبا
- City: العقبة | Regions: أخرى, الحرفية, السكنية 5, السكنية 6, السكنية 7, السكنية 8, السكنية 9, الشاطئ الجنوبي, المحدود الغربي, حي قابوس, دوار البحرية, شارع البيتزا, حي النخيل, الأطباء, البلد القديمة, الرمال, السكنية 10, السكنية 3, الشامية, الشعبية, الشلالة, العالمية, القويرة, الكرامة, المحدود الشرقي, المحدود الوسط, المركزية, الملقان, ايلة, تالا باي, سكن الأسمدة, ملقان الجنوبي, ملقان الشمالي, وادي رم
- City: المفرق | Regions: أخرى, الفحيلية, بريقا, تل ارماح, جابر السرحان, حمامة العليمات, حي الفدين, حي المقام, خشاع القن, روضة الأمير علي, ضاحية الملك عبدالله الثاني, طريق بغداد الدولي, منشية خليفة, منيفة, ارحاب, البادية الشمالية, البادية الشمالية الغربية, الباعج, الحمراء, الحي الهاشمي, الخالدية, الخربة السمرا, الدجنية, الدفيانة, الدقسمة, الرشادة, الرفاعيات, الزعتري, الزنية, الصالحية, الصفاوي, الغدير الأبيض, المبروكة, المراجم, المزة, المنصورة, النظامية, أم الجمال, أم القطين, أم اللولو, أم النعام الشرقية, أم النعام الغربي, أم بطيمة, أم صويوينة, بلعما, بويضة الحوامدة, بويضة العليمات, ثغرة الجب, حوشا, حي الضباط, حي نوارة, حيان الرويبض, حيان المشرف, دحل, دير الكهف, رحبة ركاد, رويشيد, زملة الأمير غازي, سما السرحان, صبحا, ضاحية الجامعة, طيب اسم, عين والمعمرية, فاع, كوم الأحمر, مغير السرحان, منشية بني حسن, نادرة, نايفه, هويشان
- City: جرش | Regions: أخرى, أم قنطرة, البركتين, الحديب, الشواهد, النبي هود, بليلا, جامعة جرش, جبة, جبل الشيخ مصلح, دوار المستشفى, شارع جرش المفرق, عنيبة, عين النبي, مقبلة, كفر خل, كفير, مرصع, قرية نحلة, الحدادة, الرشايدة, الكته, المجدل, المصطبة, النسيم, برما, تل الرمان, دبين, ساكب, سلحوب, سوف, عمامه, قفقفا
- City: الكرك | Regions: أخرى, أدر, الثنية, الربة, السميكية, العدنانية, القصر, القطرانة, المرج, المزار الجنوبي, ذات راس, زحوم, عي, غور الصافي, فقوع, قصور بشير, مؤتة, منشية أبو حمور
- City: عجلون | Regions: أخرى, أم الينابيع, اشتفينا, الوهادنة, راس منيف, راسون, سامتا, شارع القلعة, قلعة عجلون, منطقة السوس, برقش, صخرة, عبين, عفنة, عنجرة, عين جنا, كفرنجا
- City: معان | Regions: أخرى, البتراء, البيضا, الجاية, الجفر, الحسينية, الشوبك, المريغة, أم صيحون, أيل, راس النقب, سطح معان, شماخ, قصبة معان, نجل, وادي موسى
- City: الطفيلة | Regions: أخرى, عابور, وادي زيد, الحسا, الرشادية, العيص, القادسية, بصيرة, جرف الدراويش, ضانا

- min_price: Number (e.g., "أكثر من 50 ألف" -> 50000)
- max_price: Number (e.g., "أقل من 300 دينار" -> 300)
- bedrooms: Number (e.g., "غرفتين" -> 2)
- bathrooms: Number
- min_area: Number (in sqm)
- max_area: Number
- furnished: boolean (true/false)
- floor: Number
- rent_duration: string (شهري/سنوي/يومي)

Output ONLY a valid JSON object:
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
        "فلل وقصور": 10101,
        "بيوت مستقلة للبيع": 10102,
        "دوبلكس / بنتهاوس": 10103,
        "طابق كامل للبيع": 10104,
        "ملحق / روف": 10105,
        "شقق للبيع": 10301,
        "ستوديوهات للبيع": 10302,
        "أخرى": 10999,
        "عمارات سكنية": 5050717,
        "محلات تجارية عامة": 10853,
        "كشك / بسطة / مساحة مفتوحة": 10872,
        "محل مغلق": 10874,
        "بسطة / مساحة مفتوحة": 10875,
        "مقر مستقل": 16945,
        "مكتب": 18004,
        "مقر شركة": 18005,
        "مبنى إداري": 18006,
        "معارض سيارات": 10877,
        "معرض مستقل": 10878,
        "معارض أجهزة كهربائية وإلكترونيات": 10883,
        "معارض ملابس وأحذية": 10886,
        "صالون حلاقة رجالي": 10890,
        "صالون تجميل نسائي / سبا": 10893,
        "مطعم": 18001,
        "كافيه / مقهى": 18002,
        "مطعم وكافيه": 18003,
        "مخزن متصل بمحل": 10913,
        "مخزن خلفي": 10915,
        "مستودع مستقل": 10919,
        "مخزن": 18007,
        "عيادة": 18009,
        "مركز طبي": 18010,
        "مختبر": 18011,
        "صيدلية": 18012,
        "مدرسة": 18014,
        "روضة": 18015,
        "مركز تدريب": 18016,
        "معهد": 18017,
        "صالة رياضية": 18019,
        "صالة أفراح": 18020,
        "صالة عرض": 18021,
        "نادي": 18022,
        "فندق": 18024,
        "بيت ضيافة": 18026,
        "نزل": 18027,
        "أرض تجارية": 18029,
        "أرض صناعية": 18030,
        "أرض استثمارية": 18031,
        "عمارة تجارية": 18033,
        "مجمع تجاري": 18034,
        "مول": 18035,
        "مبنى متعدد الاستخدام": 18036,
        "أخرى": 18037,
        "أراضي سكنية": 19000,
        "أراضي تجارية": 19010,
        "أراضي صناعية": 19020,
        "أراضي زراعية": 19030,
        "أراضي سياحية": 19040,
        "أرض تنظيم خاص": 19051,
        "أرض استثمار": 19052,
        "أرض استعمال مختلط": 19053,
        "أرض مشروع": 19054,
        "أرض أملاك دولة": 19061,
        "أرض وقف": 19062,
        "أرض تنظيم حكومي": 19063,
        "أرض خارج التنظيم": 19071,
        "أرض بادية": 19072,
        "أرض فضاء": 19073,
        "أرض غير مصنفة": 19074,
        "مزرعة خضار": 19201,
        "مزرعة فواكه": 19202,
        "مزرعة زيتون": 19203,
        "مزرعة حمضيات": 19204,
        "مزرعة محاصيل": 19205,
        "مزرعة أشجار": 19206,
        "مزرعة أغنام": 19211,
        "مزرعة أبقار": 19212,
        "مزرعة دواجن": 19213,
        "مزرعة خيول": 19214,
        "مزرعة أسماك": 19215,
        "مزرعة نحل": 19216,
        "مزرعة استثمارية": 19221,
        "مزرعة منتجة": 19222,
        "مزرعة مشروع": 19223,
        "مزرعة تجارية": 19224,
        "مزرعة مع بيت": 19231,
        "مزرعة مع فيلا": 19232,
        "مزرعة مع استراحة": 19233,
        "مزرعة مع شاليه": 19234,
        "مزرعة سياحية": 19241,
        "مزرعة رحلات": 19242,
        "مزرعة منتجع": 19243,
        "مزرعة فعاليات": 19244,
        "مزرعة مع بئر": 19251,
        "مزرعة مع كهرباء": 19252,
        "مزرعة مع بيت بلاستيك": 19253,
        "مزرعة مع مستودعات": 19254,
        "مزرعة أعلاف": 19261,
        "مزرعة ألبان": 19262,
        "مزرعة دواجن تجارية": 19263,
        "مزرعة إنتاج غذائي": 19264,
        "مزرعة غير مزروعة": 19271,
        "مزرعة أرض فقط": 19272,
        "مزرعة بحاجة تأهيل": 19273,
        "مزرعة غير مستثمرة": 19274,
        "أخرى": 19280,
        "شاليه مستقل": 19301,
        "شاليه ضمن مجمع": 19302,
        "شاليه مع مسبح": 19303,
        "شاليه مع حديقة": 19304,
        "شاليه مع إطلالة": 19305,
        "منتجع سياحي": 19311,
        "منتجع عائلي": 19312,
        "منتجع علاجي": 19313,
        "منتجع جبلي": 19314,
        "منتجع بحري": 19315,
        "استراحة": 19321,
        "استراحة عائلية": 19322,
        "مزرعة ترفيهية": 19323,
        "مزرعة مع مسبح": 19324,
        "شقة فندقية": 19331,
        "جناح فندقي": 19332,
        "فيلا فندقية": 19333,
        "فيلا سياحية": 19341,
        "فيلا ضمن منتجع": 19342,
        "فيلا عطلات": 19343,
        "موقع تخييم": 19351,
        "مخيم سياحي": 19352,
        "مخيم صحراوي": 19353,
        "موقع كرفانات": 19354,
        "بيت ضيافة": 19361,
        "نُزل": 19362,
        "نُزل ريفي": 19363,
        "بيت تراثي سياحي": 19364,
        "مشروع منتجع": 19371,
        "مشروع شاليهات": 19372,
        "أرض مشروع سياحي": 19373,
        "مجمع سياحي": 19374,
        "بيت ريفي": 19381,
        "بيت ريفي سياحي": 19382,
        "بيت تراثي": 19383,
        "بيت طيني": 19384,
        "أخرى": 19390,
        "سكن طلاب (ذكور)": 3061,
        "سكن طالبات (إناث)": 3062,
        "سكن موظفين": 3063,
        "سكن موظفات": 3064,
        "غرفة برايفت للإيجار": 3065,
        "سرير في غرفة مشتركة": 3066,
        "شقق للإيجار": 301,
        "ستوديوهات للإيجار": 302,
        "فلل وقصور": 3101,
        "بيوت مستقلة للإيجار": 3102,
        "دوبلكس / بنتهاوس": 3103,
        "طابق كامل للإيجار": 3104,
        "ملحق / روف": 3105,
        "محلات ومعارض للإيجار": 303,
        "مكاتب للإيجار": 304,
        "معارض تجارية متخصصة": 1203020507,
        "صالونات ومراكز تجميل": 1203020508,
        "مطاعم ومقاهي": 1203020509,
        "مخازن ومستودعات": 1203020510,
        "مراكز تعليمية": 1203020511,
        "أراضي تجارية": 1203020512,
        "مباني تجارية كاملة": 1203020513,
        "أخرى": 1203020514,
        "عيادات ومراكز طبية": 1203020515,
        "صالات ومرافق": 1203020516,
        "فنادق وسياحة": 1203020517,
        "مزارع": 314,
        "شاليهات / منتجعات": 315,
        "بيوت ريفية": 316,
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
