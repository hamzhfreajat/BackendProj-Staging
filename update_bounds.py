import re

def update_bounds(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    target = """PRICE_SANITY_BOUNDS = {
    1: (1000.0, 10_000_000.0),
    'default': (10.0, 1_000_000_000.0)
}"""
    
    # If the target doesn't match exactly because of formatting, we can use regex
    
    replacement = """PRICE_SANITY_BOUNDS = {
    1: (1000.0, 10_000_000.0), # Generic Real Estate
    2: (3000.0, 10_000_000.0), # Real estate for sale
    10301: (5000.0, 10_000_000.0), # Apartments for sale
    10302: (5000.0, 10_000_000.0), # Studios for sale
    10102: (5000.0, 10_000_000.0), # Houses for sale
    10104: (5000.0, 10_000_000.0), # Whole floors for sale
    101: (300.0, 500_000.0),       # Cars for sale
    'default': (10.0, 1_000_000_000.0)
}"""

    # Replace using regex to handle potential whitespace differences
    pattern = re.compile(r"PRICE_SANITY_BOUNDS\s*=\s*\{[^\}]+\}")
    content = pattern.sub(replacement, content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Updated bounds in {filepath}")

update_bounds('D:/open/classifieds-app-staging-backend/market_analysis_service.py')
update_bounds('D:/open/classifieds-app/backend/market_analysis_service.py')
