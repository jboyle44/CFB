import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

url = "https://www.teamcrafters.net/rosters/CFB27/freshmen-update-v2/701"
resp = requests.get(url, headers=HEADERS, timeout=20)
soup = BeautifulSoup(resp.text, "html.parser")

output = []
table = soup.find("table")
rows = table.find_all("tr")
for row in rows[1:4]:
    cells = row.find_all("td")
    if not cells:
        continue
    link = cells[0].find("a")
    output.append(f"FULL CELL HTML: {str(cells[0])[:500]}")
    output.append(f"LINK TEXT ONLY: {link.get_text(' ', strip=True) if link else 'NO LINK'}")
    output.append("---")

with open('../cfb27_html_diag.txt', 'w') as f:
    f.write("\n".join(output))
