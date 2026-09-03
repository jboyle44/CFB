import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

url = "https://www.ourlads.com/nfldepthcharts/depthchart/DAL"
resp = requests.get(url, headers=HEADERS, timeout=20)
soup = BeautifulSoup(resp.text, "html.parser")

output = []
for table in soup.find_all("table"):
    header_cells = [th.get_text(strip=True) for th in table.find_all("th")]
    if not header_cells or not header_cells[0].lower().startswith("pos"):
        continue
    heading = table.find_previous(["h1", "h2", "h3"])
    heading_text = heading.get_text(strip=True) if heading else "(no heading found)"
    output.append(f"TABLE HEADING: {heading_text!r}")

with open('../nfl_scheme_diag.txt', 'w') as f:
    f.write("\n".join(output))
