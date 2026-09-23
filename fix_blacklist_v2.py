import re

with open('blacklist_router.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_query = '''    from sqlalchemy import text
    try:
        # PostgreSQL specific syntax for JSONB
        # Only delete scraped ads, leave organic ads alone
        ads_to_delete = db.query(models.Ad).filter(
            text("attributes->>'phone_number' = :phone").bindparams(phone=phone),
            models.Ad.source_type != models.SourceType.ORGANIC_USER
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

with open('blacklist_router.py', 'w', encoding='utf-8') as f:
    f.write(code)
