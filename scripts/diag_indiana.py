import json, os, requests

api_key = os.environ.get("CFBD_API_KEY")
headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

resp = requests.get("https://api.collegefootballdata.com/player/portal",
    headers=headers, params={"year": 2026}, timeout=20)
entries = resp.json()

destinations = set(e.get('destination') for e in entries if e.get('destination') and 'indiana' in e.get('destination','').lower())
result = {"indiana_like_destinations": list(destinations)}

with open('../indiana_diag_result.json', 'w') as f:
    json.dump(result, f, indent=2)
