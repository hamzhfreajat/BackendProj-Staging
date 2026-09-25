import asyncio
from smart_search_router import extract_raw_data_via_deepseek
import json

raw = extract_raw_data_via_deepseek("بدي شقه في اربد")
print(json.dumps(raw, ensure_ascii=False, indent=2))
