import re

with open('smart_search_router.py', 'r', encoding='utf-8') as f:
    code = f.read()

zones = '''ZONE_REGIONS = {
    "عمان الغربية": ["خلدا", "عبدون", "الصويفية", "دير غبار", "ام اذينة", "تلاع العلي", "الشميساني", "الرابية", "دابوق", "ام السماق", "الجبيهة"],
    "غرب عمان": ["خلدا", "عبدون", "الصويفية", "دير غبار", "ام اذينة", "تلاع العلي", "الشميساني", "الرابية", "دابوق", "ام السماق", "الجبيهة"],
    "عمان الشرقية": ["ماركا", "الأشرفية", "جبل التاج", "الوحدات", "القويسمة", "أبو علندا", "جبل النصر", "الهاشمي", "جبل الجوفة", "النزهة", "ضاحية الأقصى"],
    "شرق عمان": ["ماركا", "الأشرفية", "جبل التاج", "الوحدات", "القويسمة", "أبو علندا", "جبل النصر", "الهاشمي", "جبل الجوفة", "النزهة", "ضاحية الأقصى"],
    "شمال عمان": ["ابو نصير", "شفا بدران", "الجبيهة", "طارق", "صويلح", "ياجوز"],
    "جنوب عمان": ["خريبة السوق", "جاوا", "اليادودة", "مرج الحمام", "ناعور"],
}'''

old_resolve = '''def resolve_regions_smart(db: Session, raw_locations: list, city_id: int = None) -> tuple:'''

new_resolve = zones + '''

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
'''

code = code.replace(old_resolve, new_resolve)

with open('smart_search_router.py', 'w', encoding='utf-8') as f:
    f.write(code)
