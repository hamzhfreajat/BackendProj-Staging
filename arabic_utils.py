import re

def normalize_arabic(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r'[\u064B-\u065F]', '', text)
    text = re.sub(r'[أإآ]', 'ا', text)
    text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'ى', 'ي', text)
    words = text.split()
    normalized_words = []
    for w in words:
        if w.startswith("بال"): w = w[3:]
        elif w.startswith("ب") and len(w) > 3: w = w[1:]
        if w.startswith("ال"): w = w[2:]
        normalized_words.append(w)
    text = " ".join(normalized_words)
    text = text.replace("في ", "")
    return text.strip()

def convert_hindi_numerals(text: str) -> str:
    if not text: return text
    mapping = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
    return str(text).translate(mapping)

def parse_price(price_val) -> int:
    if not price_val: return None
    text = convert_hindi_numerals(str(price_val)).lower()
    match = re.search(r'\d+', text)
    if not match: return None
    base_num = int(match.group(0))
    if 'الف' in text or 'ألف' in text or 'k' in text: base_num *= 1000
    elif 'مليون' in text or 'm' in text: base_num *= 1000000
    return base_num
