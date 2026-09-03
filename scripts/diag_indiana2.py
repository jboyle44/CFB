import json, os, requests

api_key = os.environ.get("CFBD_API_KEY")
headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

resp = requests.get("https://api.collegefootballdata.com/player/portal",
    headers=headers, params={"year": 2026}, timeout=20)
entries = resp.json()

indiana_transfers = [e for e in entries if e.get('destination') == 'Indiana']
result = {"count": len(indiana_transfers), "sample": indiana_transfers[:10]}

with open('../indiana_diag2_result.json', 'w') as f:
    json.dump(result, f, indent=2)
