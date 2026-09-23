import sys; sys.stdout.reconfigure(encoding='utf-8')
from unittest.mock import MagicMock, patch
import smart_search_router
from smart_search_router import smart_voice_search, SmartSearchRequest
import models
db = MagicMock()
mock_query = MagicMock()
mock_query.count.return_value = 0
mock_query.filter.return_value = mock_query
db.query.return_value = mock_query
req = SmartSearchRequest(text='بدي شقه للايجار بمفروشه بعمان بين 250 و 300 دينار')
def mock_extract(text, valid_tags):
    return {'intent': 'search', 'raw_filters': {'property_type': 'شقة', 'transaction': 'rent', 'locations': ['عمان'], 'max_price_number': 300, 'bedrooms_number': 2}}
smart_search_router.extract_raw_data_via_deepseek = mock_extract
try: res = smart_voice_search(req, db); print(res.intent)
except Exception as e: print('ERROR:', type(e), e)
