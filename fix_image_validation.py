import re

def disable_3_images_check(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        code = f.read()

    # Find the instances of len(...) < 3: and replace with < 0: to temporarily disable the check
    code = re.sub(r'len\([^)]+\)\s*<\s*3', 'len(image_urls) < 0', code)
    # Some instances might be exactly like this:
    code = code.replace('len(attributes.get("image_urls", [])) < 3', 'len(attributes.get("image_urls", [])) < 0')
    code = code.replace('len(ad.image_urls) < 3', 'len(ad.image_urls) < 0')
    code = code.replace('len(db_ad.image_urls) < 3', 'len(db_ad.image_urls) < 0')
    code = code.replace('len(image_urls) < 3', 'len(image_urls) < 0')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(code)

disable_3_images_check('d:/open/classifieds-app-staging-backend/main.py')
disable_3_images_check(r'd:\open\classifieds-app\backend\main.py')
