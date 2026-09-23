import asyncio
from smart_search_router import smart_voice_search, SmartSearchRequest
from database import SessionLocal

async def test():
    db = SessionLocal()
    req = SmartSearchRequest(text='بدي استوديو لبنتين قريب من مخابز الراية')
    res = await smart_voice_search(req, db)
    print(res)

asyncio.run(test())
