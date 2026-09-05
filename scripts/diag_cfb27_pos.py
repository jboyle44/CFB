import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

url = "https://www.teamcrafters.net/rosters/CFB27/freshmen-update-v2/701"
resp = requests.get(url, headers=HEADERS, timeout=20)
soup = BeautifulSoup(resp.text, "html.parser")

output = [f"status: {resp.status_code}"]
tables = soup.find_all("table")
output.append(f"tables found: {len(tables)}")
for table in tables[:1]:
    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    output.append(f"headers: {headers}")
    rows = table.find_all("tr")
    for tr in rows[1:8]:
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        output.append(f"row: {cells}")

with open('../cfb27_pos_diag.txt', 'w') as f:
    f.write("\n".join(output))
