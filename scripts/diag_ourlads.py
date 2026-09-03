import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

url = "https://www.ourlads.com/ncaa-football-depth-charts/depth-chart/ohio-state/91533"
resp = requests.get(url, headers=HEADERS, timeout=20)
soup = BeautifulSoup(resp.text, "html.parser")

output = []
for table in soup.find_all("table"):
    header_cells = [th.get_text(strip=True) for th in table.find_all("th")]
    if not header_cells or not header_cells[0].lower().startswith("pos"):
        continue
    heading = table.find_previous(["h1", "h2", "h3"])
    heading_text = heading.get_text(strip=True) if heading else "?"
    if "defense" not in heading_text.lower():
        continue

    output.append(f"=== TABLE: {heading_text} ===")
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if not cells:
            output.append("(no td cells - probably header row)")
            continue
        cell_texts = [c.get_text(" ", strip=True) for c in cells]
        output.append(f"ROW ({len(cells)} cells): {cell_texts}")

with open('../ourlads_diag_result.txt', 'w') as f:
    f.write("\n".join(output))
