import json
import os
import requests

api_key = os.environ.get("CFBD_API_KEY")
headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

result = {}

# Search transfer portal broadly for any "Moore" destined for Ohio State, across years
result['portal_search'] = {}
for yr in [2023, 2024, 2025, 2026]:
    resp = requests.get("https://api.collegefootballdata.com/player/portal",
        headers=headers, params={"year": yr}, timeout=20)
    if resp.status_code == 200:
        matches = [p for p in resp.json() if 'moore' in (p.get('lastName') or '').lower()
                   and p.get('destination') == 'Ohio State']
        if matches:
            result['portal_search'][yr] = matches

# Search recruiting for "Terry Moore" or "Moore" across likely HS years
result['recruiting_search'] = {}
for yr in [2020, 2021, 2022, 2023]:
    resp = requests.get("https://api.collegefootballdata.com/recruiting/players",
        headers=headers, params={"year": yr}, timeout=20)
    if resp.status_code == 200:
        matches = [p for p in resp.json() if 'terry moore' in (p.get('name') or '').lower()]
        if matches:
            result['recruiting_search'][yr] = matches

with open('../test_terry_result.json', 'w') as f:
    json.dump(result, f, indent=2)
