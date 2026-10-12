"""One-off: dump raw Ourlads NFL player cells to see the current markup."""
import requests, json
from bs4 import BeautifulSoup
from scrape_ourlads_nfl import HEADERS
r = requests.get("https://www.ourlads.com/nfldepthcharts/depthchart/PHI", headers=HEADERS, timeout=20)
soup = BeautifulSoup(r.text, "html.parser")
out = []
for table in soup.find_all("table"):
    h = table.find_previous(["h2", "h3"])
    ht = h.get_text(strip=True) if h else ""
    n = 0
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 3: continue
        out.append({"heading": ht[:30], "cells": [str(td)[:400] for td in tds[:3]]})
        n += 1
        if n >= 3: break
for o in out[:12]:
    print(f"::notice title=cell {o['heading']}::" + json.dumps(o["cells"])[:1800].replace("\n"," "))
