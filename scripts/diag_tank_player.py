import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

url = "https://www.tankathon.com/nfl/players/jeremiah-smith"
resp = requests.get(url, headers=HEADERS, timeout=20)
soup = BeautifulSoup(resp.text, "html.parser")

output = [f"status: {resp.status_code}"]
# Look for anything mentioning class/year/eligibility
text = soup.get_text(" ", strip=True)
import re
for keyword in ["Class", "Year", "Eligib", "Freshman", "Sophomore", "Junior", "Senior", "RS "]:
    idx = text.find(keyword)
    if idx != -1:
        output.append(f"Found '{keyword}' at context: ...{text[max(0,idx-60):idx+60]}...")

with open('../tankathon_player_diag.txt', 'w') as f:
    f.write("\n".join(output))
