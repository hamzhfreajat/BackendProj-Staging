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

old_resolve = '''def resolve_regions_smart(db: Session, locations: list[str]):'''

new_resolve = zones + '''

def resolve_regions_smart(db: Session, locations: list[str]):
    # Expand zone names to actual regions
    expanded_locations = []
    for loc in locations:
        loc_clean = loc.strip()
        matched_zone = False
        for zone_name, zone_regions in ZONE_REGIONS.items():
            if zone_name in loc_clean or loc_clean in zone_name:
                expanded_locations.extend(zone_regions)
                matched_zone = True
                break
        if not matched_zone:
            expanded_locations.append(loc_clean)
            
    locations = list(set(expanded_locations))
'''

code = code.replace(old_resolve, new_resolve)

with open('smart_search_router.py', 'w', encoding='utf-8') as f:
    f.write(code)
