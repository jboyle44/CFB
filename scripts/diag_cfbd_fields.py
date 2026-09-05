import json, os, requests
api_key = os.environ.get("CFBD_API_KEY")
headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
resp = requests.get("https://api.collegefootballdata.com/games",
    params={"year": 2026, "week": 1, "seasonType": "regular", "team": "Ohio State"},
    headers=headers, timeout=20)
data = resp.json()
with open('../cfbd_fields_diag.txt', 'w') as f:
    f.write(f"status={resp.status_code}\n")
    if data:
        f.write(json.dumps(data[0], indent=2))
