with open('D:/open/classifieds-app/backend/schemas.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

out = []
for line in lines:
    out.append(line)
    if "original_created_at: Optional[datetime] = None" in line:
        out.append("    market_price_status: Optional[str] = None\n")
        out.append("    market_average_price: Optional[float] = None\n")
        out.append("    deviation_pct: Optional[float] = None\n")
        out.append("    comparables_count: Optional[int] = None\n")
        out.append("    confidence_level: Optional[str] = None\n")
        out.append("    matching_level_used: Optional[int] = None\n")
        out.append("    calculated_at: Optional[datetime] = None\n")

with open('D:/open/classifieds-app/backend/schemas.py', 'w', encoding='utf-8') as f:
    f.writelines(out)
