import re

with open('blacklist_router.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_query = '''        # PostgreSQL specific syntax for JSONB
        ads_to_delete = db.query(models.Ad).filter(
            text("attributes->>'phone_number' = :phone").bindparams(phone=phone)
        ).all()'''

new_query = '''        # PostgreSQL specific syntax for JSONB
        # Only delete scraped ads, leave organic ads alone
        ads_to_delete = db.query(models.Ad).filter(
            text("attributes->>'phone_number' = :phone").bindparams(phone=phone),
            models.Ad.source_type != models.SourceType.ORGANIC_USER
        ).all()'''

code = code.replace(old_query, new_query)

# Wait, there's another check needed. What if the phone is in the user's table (models.User.mobile_number)?
# The original code only checks attributes->>'phone_number'.
# I'll leave it at that, or maybe enhance it since I'm fixing it.
# The user's request is exactly: "In the dashboad when add phone to block list dont remove the organic ads for this blocked user just remove the ads scraped from the bot"
# So the current behavior deletes their ads, wait, does the current behavior delete organic ads?
# The current query is: text("attributes->>'phone_number' = :phone")
# Scraper bots put the phone in the JSON attributes. Organic users probably don't have it there! But just in case, I will add the condition.

with open('blacklist_router.py', 'w', encoding='utf-8') as f:
    f.write(code)
