import json
import os
import requests

api_key = os.environ.get("CFBD_API_KEY")
resp = requests.get(
    "https://api.collegefootballdata.com/player/portal",
    headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
    params={"year": 2025},
    timeout=20,
)

result = {
    "status_code": resp.status_code,
    "response_type": str(type(resp.json())),
    "raw_text_first_500": resp.text[:500],
}

with open('../test_cfbd_result.json', 'w') as f:
    json.dump(result, f, indent=2)
