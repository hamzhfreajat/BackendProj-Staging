import re

def patch_update_ad(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # We want to insert `background_tasks.add_task(process_new_ad_background, db_ad.id)` right before `return db_ad` inside `update_ad`.
    # Let's find the exact block at the end of update_ad.
    target_return = """    # Notify: Ad submitted confirmation to the owner if transitioned from unpublished to published
    if was_unpublished and is_now_published:
        background_tasks.add_task(
            send_personal_notification,
            target_user_id=db_ad.user_id,
            title="OU. U+O'O OO1U,O U+U O"U+OO O- o.",
            body=f"OO1U,O U+U '{db_ad.title[:50]}' OU. U+O'OU O"U+OO O- U^OOO"O- U.OO O-O U< U,U,OU.USO1.",
            notification_type="ad_created",
            reference_id=db_ad.id
        )
    
    return db_ad"""

    # Because string literals might differ, let's use a simpler replace target
    target_simple = "    return db_ad\n\n@app.post(\"/api/ads/{ad_id}/bid\""
    
    if target_simple in content:
        replacement = "    background_tasks.add_task(process_new_ad_background, db_ad.id)\n    return db_ad\n\n@app.post(\"/api/ads/{ad_id}/bid\""
        content = content.replace(target_simple, replacement)
    else:
        # try regex for return db_ad just before @app.post("/api/ads/{ad_id}/bid"
        pattern = re.compile(r"(\s+)(return db_ad\s*@app\.post\(\"/api/ads/\{ad_id\}/bid\")")
        content = pattern.sub(r"\1background_tasks.add_task(process_new_ad_background, db_ad.id)\1\2", content)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print(f"Patched update_ad in {filepath}")

patch_update_ad('D:/open/classifieds-app-staging-backend/main.py')
patch_update_ad('D:/open/classifieds-app/backend/main.py')
