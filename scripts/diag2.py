import json
import os
import requests

api_key = os.environ.get("CFBD_API_KEY")
headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

result = {}
for yr in [2022, 2023, 2024, 2025]:
    resp = requests.get("https://api.collegefootballdata.com/recruiting/players",
        headers=headers, params={"year": yr, "team": "Maryland"}, timeout=20)
    if resp.status_code == 200:
        matches = [p for p in resp.json() if 'moore' in (p.get('name') or '').lower()]
        if matches:
            result[yr] = matches

with open('../test_diag2_result.json', 'w') as f:
    json.dump(result, f, indent=2)
