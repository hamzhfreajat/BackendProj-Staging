import re

def remove_organic_filter(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the block where ORGANIC_USER is used
    target = """        query = db.query(Ad).join(AdSearchIndex, Ad.id == AdSearchIndex.ad_id).filter(
            Ad.is_published == True,
            Ad.is_paused == False,
            Ad.is_sold == False,
            Ad.is_rejected == False,
            Ad.price.isnot(None),
            Ad.source_type == SourceType.ORGANIC_USER
        )"""

    replacement = """        query = db.query(Ad).join(AdSearchIndex, Ad.id == AdSearchIndex.ad_id).filter(
            Ad.is_published == True,
            Ad.is_paused == False,
            Ad.is_sold == False,
            Ad.is_rejected == False,
            Ad.price.isnot(None)
        )"""

    if target in content:
        content = content.replace(target, replacement)
    else:
        # Fallback regex in case of slight whitespace differences
        pattern = re.compile(r"Ad\.price\.isnot\(None\),\s*Ad\.source_type\s*==\s*SourceType\.ORGANIC_USER")
        content = pattern.sub(r"Ad.price.isnot(None)", content)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Removed ORGANIC_USER filter in {filepath}")

remove_organic_filter('D:/open/classifieds-app-staging-backend/market_analysis_service.py')
remove_organic_filter('D:/open/classifieds-app/backend/market_analysis_service.py')
