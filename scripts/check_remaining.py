import os, requests
api_key = os.environ.get("CFBD_API_KEY")
headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
resp = requests.get("https://api.collegefootballdata.com/teams/fbs", headers=headers, timeout=20)
with open('../remaining_result.txt', 'w') as f:
    f.write(f"Remaining: {resp.headers.get('X-CallLimit-Remaining')}")
