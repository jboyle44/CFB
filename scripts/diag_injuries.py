import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

url = "https://www.ourlads.com/ncaa-football-depth-charts/depth-chart/iowa/90751"
resp = requests.get(url, headers=HEADERS, timeout=20)
soup = BeautifulSoup(resp.text, "html.parser")

output = []
for table in soup.find_all("table"):
    header_cells = [th.get_text(strip=True) for th in table.find_all("th")]
    if not header_cells:
        continue
    output.append(f"=== TABLE HEADERS: {header_cells} ===")
    heading = table.find_previous(["h1", "h2", "h3"])
    heading_text = heading.get_text(strip=True) if heading else "?"
    output.append(f"Preceding heading: {heading_text}")
    for tr in table.find_all("tr")[:6]:
        cells = tr.find_all("td")
        if not cells:
            continue
        cell_texts = [c.get_text(" ", strip=True) for c in cells]
        output.append(f"ROW: {cell_texts}")

with open('../injuries_diag.txt', 'w') as f:
    f.write("\n".join(output))
