import json, os, requests

api_key = os.environ.get("CFBD_API_KEY")
headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

result = {}

# Rolijah Hardy - non-transfer, JR -> should be 2024 Indiana recruit
resp = requests.get("https://api.collegefootballdata.com/recruiting/players",
    headers=headers, params={"year": 2024, "team": "Indiana"}, timeout=20)
if resp.status_code == 200:
    matches = [p for p in resp.json() if 'hardy' in (p.get('name') or '').lower()]
    result['hardy_indiana_2024'] = matches

# Broader search for "Hardy" across years, no team filter, to find him wherever he is
result['hardy_broad'] = {}
for yr in [2022, 2023, 2024, 2025]:
    resp = requests.get("https://api.collegefootballdata.com/recruiting/players",
        headers=headers, params={"year": yr}, timeout=20)
    if resp.status_code == 200:
        matches = [p for p in resp.json() if 'rolijah' in (p.get('name') or '').lower()
                   or 'hardy' in (p.get('name') or '').lower() and 'roli' in (p.get('name') or '').lower()]
        if matches:
            result['hardy_broad'][yr] = matches

# Quan Sanks - transfer, check portal for destination=Indiana with "Sanks" lastName
result['sanks_portal'] = {}
for yr in [2023, 2024, 2025, 2026]:
    resp = requests.get("https://api.collegefootballdata.com/player/portal",
        headers=headers, params={"year": yr}, timeout=20)
    if resp.status_code == 200:
        matches = [p for p in resp.json() if 'sanks' in (p.get('lastName') or '').lower()]
        if matches:
            result['sanks_portal'][yr] = matches

with open('../starks_hardy_diag.json', 'w') as f:
    json.dump(result, f, indent=2)
