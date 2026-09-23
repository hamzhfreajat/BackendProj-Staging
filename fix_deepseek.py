import re

with open('smart_search_router.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_prompt = '''def extract_raw_data_via_deepseek(text: str, categories_str: str = "") -> dict:
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

Intent mapping:
- search: Looking for properties
- post_ad: Wants to sell or rent out their own property

Available Categories:
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

with open('smart_search_router.py', 'w', encoding='utf-8') as f:
    f.write(code)
