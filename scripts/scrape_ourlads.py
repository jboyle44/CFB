"""
Scrapes a team's Ourlads depth chart page into a flat list of depth-chart rows.

NOTE ON RELIABILITY: this was written against Ourlads' rendered table structure
(Pos | No. | Player 1 | No | Player 2 | ... | Player 5, one table per unit:
Offense / Defense / Special Teams). If Ourlads changes their markup, the table
detection logic below (find_all('table')) should still work since it doesn't
depend on specific CSS class names -- but the column-count assumptions might
need adjusting. Test against a live page before trusting this in production.
"""
import re
import time
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

# Matches "Last, First SUFFIX CLASS[/TR]" e.g. "Henry Jr., Chris FR" or
# "Daniels, Phillip RS JR/TR" or "Little Jr., Earl RS SR/TR"
NAME_PATTERN = re.compile(
    r"^(?P<last>.+?),\s*(?P<first>.+?)\s+"
    r"(?P<class>(?:RS\s+)?(?:FR|SO|JR|SR|GR)(?:/TR)?)$"
)


def parse_player_cell(text):
    """Given raw cell text like 'Henry Jr., Chris FR', return (display_name, class_year, is_transfer)."""
    text = text.strip()
    if not text:
        return None
    m = NAME_PATTERN.match(text)
    if not m:
        # Fallback: couldn't parse class/transfer info, just use the raw text as the name
        return (text, "", False)
    last = m.group("last").strip()
    first = m.group("first").strip()
    cls = m.group("class").strip()
    is_transfer = cls.endswith("/TR")
    cls_clean = cls.replace("/TR", "").strip()
    display_name = f"{first} {last}"
    return (display_name, cls_clean, is_transfer)


def scrape_ourlads_depth_chart(ourlads_slug, ourlads_id, delay=1.5):
    """Returns (rows, schemes, reserves) where rows is a list of
    {position, player, jersey, class, isTransfer}, schemes is
    {"offense": "Spread Option"|None, "defense": "4-2-5"|None} pulled from
    each table's heading, and reserves is a list of
    {status, player, jersey, class, isTransfer} for Ourlads' "Reserves"
    list (players marked INJ/SUS) -- these don't have a real position in
    Ourlads' own data for this section, just name/jersey/class/status."""
    url = f"https://www.ourlads.com/ncaa-football-depth-charts/depth-chart/{ourlads_slug}/{ourlads_id}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    time.sleep(delay)  # be polite between requests

    soup = BeautifulSoup(resp.text, "html.parser")
    rows_out = []
    reserves_out = []
    schemes = {"offense": None, "defense": None}

    for table in soup.find_all("table"):
        header_cells = [th.get_text(strip=True) for th in table.find_all("th")]
        if not header_cells or not header_cells[0].lower().startswith("pos"):
            continue  # skip tables that aren't depth chart tables

        # Heading looks like "Offense Spread Option" or "Defense 4-2-5" --
        # the unit name is the first word, the scheme is whatever follows.
        heading = table.find_previous(["h1", "h2", "h3"])
        if heading:
            heading_text = heading.get_text(strip=True)
            lower = heading_text.lower()
            if lower.startswith("offense"):
                scheme = heading_text[len("offense"):].strip()
                schemes["offense"] = scheme or None
            elif lower.startswith("defense"):
                scheme = heading_text[len("defense"):].strip()
                schemes["defense"] = scheme or None

        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if not cells:
                continue
            position = cells[0].get_text(strip=True)
            if not position:
                continue
            # Ourlads includes an "Injured"/"Suspended" list ("Reserves"),
            # formatted with the exact same table structure (Pos | No |
            # Player...) as the real depth chart, just with "INJ"/"SUS" in
            # the position column instead of a real position code. These
            # aren't part of the active depth chart formation -- route them
            # into a separate reserves list instead of the main rows, since
            # "INJ"/"SUS" isn't a real field position and would silently
            # fail to render anywhere in the formation display.
            is_reserve = position in ("INJ", "SUS")
            status_label = "Injured" if position == "INJ" else "Suspended" if position == "SUS" else None

            # Remaining cells alternate: jersey_number, player_link, jersey_number, player_link, ...
            slot_cells = cells[1:]
            for i in range(0, len(slot_cells) - 1, 2):
                jersey = slot_cells[i].get_text(strip=True)
                player_cell = slot_cells[i + 1]
                player_link = player_cell.find("a")
                raw_text = (player_link.get_text(strip=True) if player_link
                            else player_cell.get_text(strip=True))
                if not raw_text:
                    continue
                parsed = parse_player_cell(raw_text)
                if not parsed:
                    continue
                name, cls, is_transfer = parsed
                if is_reserve:
                    reserves_out.append({
                        "status": status_label,
                        "player": name,
                        "jersey": jersey,
                        "class": cls,
                        "isTransfer": is_transfer,
                    })
                else:
                    rows_out.append({
                        "position": position,
                        "player": name,
                        "jersey": jersey,
                        "class": cls,
                        "isTransfer": is_transfer,
                    })

    return rows_out, schemes, reserves_out


if __name__ == "__main__":
    import json
    import sys
    slug = sys.argv[1] if len(sys.argv) > 1 else "ohio-state"
    tid = sys.argv[2] if len(sys.argv) > 2 else "91533"
    data, schemes, reserves = scrape_ourlads_depth_chart(slug, tid)
    print(json.dumps({"schemes": schemes, "rows": data, "reserves": reserves}, indent=2))
    print(f"\n{len(data)} depth chart rows, {len(reserves)} reserves scraped", file=sys.stderr)
