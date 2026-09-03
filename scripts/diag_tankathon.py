import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

url = "https://www.tankathon.com/nfl/big-board"
resp = requests.get(url, headers=HEADERS, timeout=20)
soup = BeautifulSoup(resp.text, "html.parser")

output = []
rows = soup.find_all(class_="mock-row")
output.append(f"Total mock-row elements: {len(rows)}")

for row in rows[:4]:
    output.append("=== ROW ===")
    output.append(str(row.prettify())[:2500])

with open('../tankathon_diag2.txt', 'w') as f:
    f.write("\n".join(output))
