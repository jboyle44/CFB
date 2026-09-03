import json
import os
import requests

api_key = os.environ.get("CFBD_API_KEY")
headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

result = {}

# Check usage endpoint
resp = requests.get("https://api.collegefootballdata.com/info/usage", headers=headers, timeout=20)
result['usage_status'] = resp.status_code
result['usage_body'] = resp.text

# Also try a trivial real call and check headers
resp2 = requests.get("https://api.collegefootballdata.com/teams/fbs", headers=headers, timeout=20)
result['test_call_status'] = resp2.status_code
result['test_call_headers'] = dict(resp2.headers)
result['test_call_body_snippet'] = resp2.text[:300]

with open('../usage_check_result.json', 'w') as f:
    json.dump(result, f, indent=2)
