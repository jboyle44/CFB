import json, os, requests
api_key = os.environ.get("CFBD_API_KEY")
headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
resp = requests.get("https://api.collegefootballdata.com/venues", headers=headers, timeout=20)
data = resp.json()
with open('../venues_diag.txt', 'w') as f:
    f.write(f"status={resp.status_code} total={len(data)}\n")
    match = next((v for v in data if v.get('id') == 3861), None)
    f.write(json.dumps(match, indent=2))
