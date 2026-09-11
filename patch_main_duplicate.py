import re

with open('d:/open/classifieds-app-staging-backend/main.py', 'r', encoding='utf-8') as f:
    code = f.read()

import_statement = "from routers import users_admin_router"
new_import = "from duplicate_detection_router import router as duplicate_router\nfrom routers import users_admin_router"

include_statement = "app.include_router(users_admin_router.router)"
new_include = "app.include_router(users_admin_router.router)\napp.include_router(duplicate_router)"

if import_statement in code:
    code = code.replace(import_statement, new_import)
    code = code.replace(include_statement, new_include)
    
    with open('d:/open/classifieds-app-staging-backend/main.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print("Main patched in staging!")
else:
    print("Could not find import statement in main.py")
