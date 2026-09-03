import json, os, requests, time
api_key = os.environ.get("CFBD_API_KEY")
headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
resp = requests.get("https://api.collegefootballdata.com/teams/fbs", headers=headers, timeout=20)
with open('../real_remaining.txt', 'w') as f:
    f.write(f"status={resp.status_code} remaining={resp.headers.get('X-CallLimit-Remaining')}")
