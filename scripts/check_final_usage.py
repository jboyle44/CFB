import json, os, requests
api_key = os.environ.get("CFBD_API_KEY")
headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

resp = requests.get("https://api.collegefootballdata.com/teams/fbs", headers=headers, timeout=20)
remaining = resp.headers.get('X-CallLimit-Remaining')

usage_resp = requests.get("https://api.collegefootballdata.com/info/usage", headers=headers, timeout=20)

with open('../final_usage_check.json', 'w') as f:
    json.dump({"remaining": remaining, "usage_body": usage_resp.json()}, f, indent=2)
