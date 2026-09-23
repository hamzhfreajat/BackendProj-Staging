import os
import re

for root, _, files in os.walk('d:/open/classifieds-app/frontend/lib'):
    for file in files:
        if file.endswith('.dart'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                try:
                    content = f.read()
                    if 'عمان الغربية' in content:
                        print("Found in", path)
                        # extract the map or list
                        idx = content.find('عمان الغربية')
                        print(content[max(0, idx-100):idx+500])
                except:
                    pass
