import json, os, requests

api_key = os.environ.get("CFBD_API_KEY")
headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

result = {}

# Jordan Faison - SR -> inferred year 2023, search Notre Dame
resp = requests.get("https://api.collegefootballdata.com/recruiting/players",
    headers=headers, params={"year": 2023, "team": "Notre Dame"}, timeout=20)
if resp.status_code == 200:
    result['faison_nd_2023'] = [p for p in resp.json() if 'faison' in (p.get('name') or '').lower()]

# Broad search for Faison across years, no team filter
result['faison_broad'] = {}
for yr in [2021, 2022, 2023, 2024]:
    resp = requests.get("https://api.collegefootballdata.com/recruiting/players",
        headers=headers, params={"year": yr}, timeout=20)
    if resp.status_code == 200:
        matches = [p for p in resp.json() if 'faison' in (p.get('name') or '').lower()]
        if matches:
            result['faison_broad'][yr] = matches

# Jason Onye - RS SR -> inferred year 2022, search Notre Dame
resp = requests.get("https://api.collegefootballdata.com/recruiting/players",
    headers=headers, params={"year": 2022, "team": "Notre Dame"}, timeout=20)
if resp.status_code == 200:
    result['onye_nd_2022'] = [p for p in resp.json() if 'onye' in (p.get('name') or '').lower()]

result['onye_broad'] = {}
for yr in [2020, 2021, 2022, 2023]:
    resp = requests.get("https://api.collegefootballdata.com/recruiting/players",
        headers=headers, params={"year": yr}, timeout=20)
    if resp.status_code == 200:
        matches = [p for p in resp.json() if 'onye' in (p.get('name') or '').lower()]
        if matches:
            result['onye_broad'][yr] = matches

with open('../faison_onye_diag.json', 'w') as f:
    json.dump(result, f, indent=2)
