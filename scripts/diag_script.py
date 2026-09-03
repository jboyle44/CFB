import json
import os
import requests

api_key = os.environ.get("CFBD_API_KEY")
headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

result = {}

# Trey Reddick - check Maryland recruiting across several years
result['reddick_search'] = {}
for yr in [2022, 2023, 2024, 2025]:
    resp = requests.get("https://api.collegefootballdata.com/recruiting/players",
        headers=headers, params={"year": yr, "team": "Maryland"}, timeout=20)
    if resp.status_code == 200:
        matches = [p for p in resp.json() if 'reddick' in (p.get('name') or '').lower()]
        result['reddick_search'][yr] = matches

# EJ Moore Jr - search transfer portal broadly by last name across years
result['moore_search'] = {}
for yr in [2024, 2025, 2026]:
    resp = requests.get("https://api.collegefootballdata.com/player/portal",
        headers=headers, params={"year": yr}, timeout=20)
    if resp.status_code == 200:
        matches = [p for p in resp.json() if 'moore' in (p.get('lastName') or '').lower()
                   and p.get('destination') == 'Maryland']
        result['moore_search'][yr] = matches

with open('../test_diag_result.json', 'w') as f:
    json.dump(result, f, indent=2)
