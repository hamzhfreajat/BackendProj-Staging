import re

path = r'd:\open\classifieds-app\backend\blacklist_router.py'
with open(path, 'r', encoding='utf-8') as f:
    code = f.read()

old_query = '''    from sqlalchemy import text
    try:
        # Search for the phone number anywhere in the ad text fields
        # This catches phone numbers embedded in descriptions or stored in any attribute
        ads_to_delete = db.query(models.Ad).filter(
            text("ads::text LIKE :phone").bindparams(phone=f"%{phone}%")
        ).all()'''

new_query = '''    from sqlalchemy import cast, String
    try:
        # Delete scraped ads where the phone is in attributes OR description
        # Leave organic ads alone!
        ads_to_delete = db.query(models.Ad).filter(
            (
                cast(models.Ad.attributes, String).ilike(f'%{phone}%') |
                models.Ad.description.ilike(f'%{phone}%') |
                models.Ad.raw_description.ilike(f'%{phone}%')
            ),
            models.Ad.source_type != models.SourceType.ORGANIC_USER
        ).all()'''

code = code.replace(old_query, new_query)

with open(path, 'w', encoding='utf-8') as f:
    f.write(code)
