import re

with open('smart_search_router.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Fix the deepseek prompt to include the categories argument
new_prompt = '''def extract_raw_data_via_deepseek(text: str, categories_str: str = "") -> dict:
    """
    Step 1: Uses DeepSeek to act purely as an NLP entity extractor.
    """
    url = "https://api.deepseek.com/chat/completions"
    import os
    from fastapi import HTTPException
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Search service configuration error.")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    system_prompt = f"""You are a helpful NLP assistant. Extract entities from Jordanian real estate search queries.
Do NOT guess or correct anything, except for category_id which must be selected from the provided list.
You MUST choose the most specific end-level category from the list. Do NOT choose broad/parent categories.

Intent mapping:
- search: Looking for properties
- post_ad: Wants to sell or rent out their own property

Available Categories (End-level only):
{categories_str}

Output JSON format:
{{
  "intent": "search" | "post_ad",
  "raw_filters": {{
    "category_id": integer ID of the best matching category from the list above, or null if unknown,
    "locations": ["Array of location names"],
    "bedrooms_number": integer or null,
    "bathrooms_number": integer or null,
    "furnishing_word": "Extract word indicating furniture",
    "max_price_word": "Extract text indicating max price",
    "min_price_word": "Extract text indicating min price",
    "floor_word": "Extract floor mentioned",
    "min_area_number": integer or null,
    "max_area_number": integer or null,
    "features": ["Extract any extra features/amenities as a list of strings"]
  }}
}}"""'''

code = re.sub(r'def extract_raw_data_via_deepseek.*?\}\"\"\"', new_prompt, code, flags=re.DOTALL)

# 2. Rewrite the first part of smart_voice_search
old_search_logic = '''def smart_voice_search(request: SmartSearchRequest, db: Session = Depends(get_db)):
    # Fetch valid tags from DB for real estate (cats 2 and 3, and maybe others, but we'll fetch all or just rely on a subset)
    # Fetching all tags is usually fast if there aren't thousands.
    try:
        valid_tags_objs = db.query(models.Tag).all()
        valid_tags = [t.name for t in valid_tags_objs if t.name]
    except Exception:
        valid_tags = []

    # STEP 1: AI Entity Extraction
    ai_response = extract_raw_data_via_deepseek(request.text, valid_tags=valid_tags)'''

new_search_logic = '''def smart_voice_search(request: SmartSearchRequest, db: Session = Depends(get_db)):
    # Fetch ONLY leaf categories under real estate (IDs 2 and 3)
    try:
        all_cats = db.query(models.Category).all()
        
        descendants = []
        current_parents = [2, 3]
        while current_parents:
            children = [c for c in all_cats if c.parent_id in current_parents]
            descendants.extend(children)
            current_parents = [c.id for c in children]
            
        parent_ids = {c.parent_id for c in all_cats if c.parent_id is not None}
        leaf_cats = [c for c in descendants if c.id not in parent_ids]
        
        cat_mapping = [f"ID: {c.id}, Name: {c.name}" for c in leaf_cats]
        categories_str = "\\n".join(cat_mapping)
    except Exception:
        categories_str = ""

    # STEP 1: AI Entity Extraction
    ai_response = extract_raw_data_via_deepseek(request.text, categories_str=categories_str)'''

code = code.replace(old_search_logic, new_search_logic)

with open('smart_search_router.py', 'w', encoding='utf-8') as f:
    f.write(code)
