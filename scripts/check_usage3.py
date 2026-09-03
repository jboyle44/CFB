import json
import os
import requests

api_key = os.environ.get("CFBD_API_KEY")
headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
resp = requests.get("https://api.collegefootballdata.com/info/usage", headers=headers, timeout=20)
with open('../usage_check3_result.json', 'w') as f:
    f.write(resp.text)
