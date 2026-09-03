import json
import os
import requests

api_key = os.environ.get("CFBD_API_KEY")
headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

result = {}

# HS recruiting search under Alabama, 2022 class
resp = requests.get("https://api.collegefootballdata.com/recruiting/players",
    headers=headers, params={"year": 2022, "team": "Alabama"}, timeout=20)
if resp.status_code == 200:
    matches = [p for p in resp.json() if 'little' in (p.get('name') or '').lower()]
    result['alabama_2022_little'] = matches

# Transfer portal - check a few years for destination Ohio State AND origin FSU/Alabama
result['portal_search'] = {}
for yr in [2023, 2024, 2025, 2026]:
    resp = requests.get("https://api.collegefootballdata.com/player/portal",
        headers=headers, params={"year": yr}, timeout=20)
    if resp.status_code == 200:
        matches = [p for p in resp.json() if 'little' in (p.get('lastName') or '').lower()]
        if matches:
            result['portal_search'][yr] = matches

with open('../little_diag_result.json', 'w') as f:
    json.dump(result, f, indent=2)
