import re

with open("generated_update.txt", "r", encoding="utf-8") as f:
    content = f.read()

parts = content.split("=== MAPPING CODE ===\n")
tree = parts[0].replace("=== PROMPT TREE ===\n", "").strip()
mapping = parts[1].strip()

with open("smart_search_router.py", "r", encoding="utf-8") as f:
    source = f.read()

# Replace Tree in prompt
source = re.sub(r'Real Estate Category Tree:.*?Note: If the user says', f"{tree}\n\nNote: If the user says", source, flags=re.DOTALL)

# Replace mapping
source = re.sub(r'mapping = \{.*?\n    \}', mapping, source, flags=re.DOTALL)

with open("smart_search_router.py", "w", encoding="utf-8") as f:
    f.write(source)
