import re

def update_market_analysis(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if "t_rent_duration =" in content:
        print(f"Already updated {filepath}")
        return

    # Find the target area
    target1 = "t_price = float(ad.price)"
    replacement1 = """t_price = float(ad.price)
            t_rent_duration = ad.attributes.get('dynamic_data', {}).get('rent_duration') if ad.attributes and isinstance(ad.attributes, dict) else None"""
    
    content = content.replace(target1, replacement1)
    
    target2 = "if reg_match and c_reg != idx.region_id: continue"
    replacement2 = """if reg_match and c_reg != idx.region_id: continue
                    
                    if t_rent_duration is not None:
                        c_rent = c_attrs.get('dynamic_data', {}).get('rent_duration') if c_attrs and isinstance(c_attrs, dict) else None
                        if c_rent != t_rent_duration: continue"""
    
    content = content.replace(target2, replacement2)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Updated {filepath}")

update_market_analysis('D:/open/classifieds-app-staging-backend/market_analysis_service.py')
update_market_analysis('D:/open/classifieds-app/backend/market_analysis_service.py')
