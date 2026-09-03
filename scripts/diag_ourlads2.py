import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.ourlads.com/ncaa-football-depth-charts/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
}

session = requests.Session()
session.headers.update(HEADERS)
# Warm up with homepage visit first
session.get("https://www.ourlads.com/ncaa-football-depth-charts/", timeout=20)

url = "https://www.ourlads.com/ncaa-football-depth-charts/depth-chart/ohio-state/91533"
resp = session.get(url, timeout=20)
soup = BeautifulSoup(resp.text, "html.parser")

output = [f"status_code: {resp.status_code}", f"content_length: {len(resp.text)}"]
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
            continue
        cell_texts = [c.get_text(" ", strip=True) for c in cells]
        pos = cell_texts[0] if cell_texts else "?"
        if pos in ("SS", "FS", "NB", "LCB", "RCB"):
            output.append(f"{pos}: {cell_texts}")

with open('../ourlads_diag2_result.txt', 'w') as f:
    f.write("\n".join(output))
