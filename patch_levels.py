import re

def patch_backend(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the tuple containing reg_match=False
    if 'reg_match=False' in content:
        content = content.replace(
            '(3, "low", dict(city_match=True, reg_match=False, floor_diff=None, age_diff=None, area_pct=0.15)),',
            '(3, "low", dict(city_match=True, reg_match=True, floor_diff=None, age_diff=None, area_pct=0.25)),'
        )
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Patched {filepath}!")
    else:
        print(f"reg_match=False not found in {filepath}!")

patch_backend('D:/open/classifieds-app-staging-backend/market_analysis_service.py')
patch_backend('D:/open/classifieds-app/backend/market_analysis_service.py')
