import re

def patch_main(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if "def process_new_ad_background" in content:
        print(f"Already patched {filepath}")
        return
        
    wrapper_code = """
def process_new_ad_background(ad_id: int):
    from database import SessionLocal
    from duplicate_detection_router import check_duplicates
    from market_analysis_service import MarketAnalysisService
    import logging
    logger = logging.getLogger(__name__)
    
    db = SessionLocal()
    try:
        # 1. Check duplicates
        try:
            check_duplicates(ad_id, db)
            db.commit()
        except Exception as e:
            logger.error(f"Error checking duplicates for ad {ad_id}: {e}")
            
        # 2. Market Analysis
        try:
            MarketAnalysisService.calculate_and_save(ad_id, db)
            db.commit()
        except Exception as e:
            logger.error(f"Error analyzing market for ad {ad_id}: {e}")
    finally:
        db.close()
"""
    # Insert the wrapper function at the top level, e.g. before create_ad
    # Look for @app.post("/api/ads", response_model=schemas.Ad)
    target = '@app.post("/api/ads", response_model=schemas.Ad)'
    
    if target in content:
        content = content.replace(target, wrapper_code + "\n" + target)
    else:
        print("Could not find insertion point!")
        return
        
    # Now patch create_ad to call it
    target2 = 'background_tasks.add_task(\n        send_personal_notification,'
    # wait, send_personal_notification is added at the end of create_ad
    # Let's just find `db.refresh(db_ad)` at the end of create_ad and insert our call right after it.
    
    # Actually, in create_ad there are two db.refresh(db_ad) if re_detail_data is present.
    # We should search for the return statement of create_ad.
    # Let's find:
    #     if re_detail_data:
    #         new_re_detail = models.AdRealEstateDetail(ad_id=db_ad.id, **re_detail_data)
    #         db.add(new_re_detail)
    #         db.commit()
    #         db.refresh(db_ad)
    #     background_tasks.add_task( ...
    
    target_return = 'background_tasks.add_task(\n        send_personal_notification,'
    if target_return in content:
        replacement = 'background_tasks.add_task(process_new_ad_background, db_ad.id)\n    ' + target_return
        content = content.replace(target_return, replacement)
    else:
        # Fallback to search using regex for the end of create_ad
        pass
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print(f"Patched {filepath}")

patch_main('D:/open/classifieds-app-staging-backend/main.py')
patch_main('D:/open/classifieds-app/backend/main.py')
