"""
Scrapes Tankathon's NFL Draft Big Board (college prospect rankings) into a
flat list of {rank, name, position, school, height, weight}.

The page repeats player rows multiple times: once in the main "Overall
Rank" list, again in a "(next year) NFL DRAFT (ALPHABETICAL)" section for
early-eligible underclassmen not yet in the main ranking, and again in
per-school breakdown sections further down the page that just re-list
players already shown above. To get a single clean ranked list:
  - Dedupe by player URL slug, keeping only the FIRST occurrence (the main
    ranked list appears first in the page, before the redundant sections).
  - Skip any row whose "pick number" isn't a plain integer -- the
    alphabetical next-year section uses the draft year itself (e.g. "2028")
    as a placeholder label instead of a real rank, which is not part of
    this year's ranking.
"""
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


def scrape_big_board(url="https://www.tankathon.com/nfl/big-board"):
    """Returns a list of dicts: {rank, name, position, school, height, weight, slug},
    sorted by rank, one entry per unique player."""
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    seen_slugs = set()
    players = []

    for row in soup.find_all(class_="mock-row"):
        pick_el = row.find(class_="mock-row-pick-number")
        if not pick_el:
            continue
        pick_text = pick_el.get_text(strip=True)
        if not pick_text.isdigit():
            continue  # skips the "2028"-style next-year placeholder rows
        rank = int(pick_text)

        player_link = row.find(class_="mock-row-player")
        if not player_link:
            continue
        link_tag = player_link.find("a")
        href = link_tag.get("href", "") if link_tag else ""
        slug = href.rstrip("/").split("/")[-1] if href else None
        if not slug or slug in seen_slugs:
            continue  # duplicate from a later per-school breakdown section
        seen_slugs.add(slug)

        name_el = row.find(class_="mock-row-name")
        name = name_el.get_text(strip=True) if name_el else None
        if not name:
            continue

        position = row.get("data-pos", "").strip()

        logo_img = row.find(class_="mock-row-logo")
        school = None
        if logo_img:
            img_tag = logo_img.find("img")
            if img_tag:
                school = img_tag.get("alt", "").strip()

        height = None
        weight = None
        measurements = row.find(class_="mock-row-measurements")
        if measurements:
            hw = measurements.find(class_="height-weight")
            if hw:
                divs = hw.find_all("div", recursive=False)
                if len(divs) >= 1:
                    height = divs[0].get_text(strip=True)
                if len(divs) >= 2:
                    weight_text = divs[1].get_text(" ", strip=True)
                    weight_match = re.search(r"\d+", weight_text)
                    weight = int(weight_match.group()) if weight_match else None

        players.append({
            "rank": rank,
            "name": name,
            "position": position or None,
            "school": school,
            "height": height,
            "weight": weight,
            "slug": slug,
        })

    players.sort(key=lambda p: p["rank"])
    return players


if __name__ == "__main__":
    import json
    import sys
    data = scrape_big_board()
    print(json.dumps(data[:10], indent=2))
    print(f"\n{len(data)} unique prospects scraped", file=sys.stderr)
