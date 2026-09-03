import json
import os
import requests

api_key = os.environ.get("CFBD_API_KEY")
headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

resp = requests.get("https://api.collegefootballdata.com/info/usage", headers=headers, timeout=20)
result = {"usage_status": resp.status_code, "usage_body": resp.text}

resp2 = requests.get("https://api.collegefootballdata.com/teams/fbs", headers=headers, timeout=20)
result['test_call_status'] = resp2.status_code
result['remaining_header'] = resp2.headers.get('X-CallLimit-Remaining')

with open('../usage_check2_result.json', 'w') as f:
    json.dump(result, f, indent=2)
