from fastapi.testclient import TestClient
from main import app
import sys

client = TestClient(app)
try:
    response = client.post("/api/smart-voice-search", json={"text": "??? ?????"})
    print(response.status_code)
    print(response.json())
except Exception as e:
    import traceback
    traceback.print_exc()
