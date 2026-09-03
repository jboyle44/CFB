"""
Scrapes an NFL team's Ourlads depth chart page into a flat list of rows.

NFL differs from the NCAA version in two structural ways:
  1. URL uses a bare team abbreviation, no numeric id:
     https://www.ourlads.com/nfldepthcharts/depthchart/{ABBR}
  2. The name cell suffix is an acquisition/status code, not a class year --
     e.g. "Pickens, George T/Pit" (traded from Pittsburgh), "Lamb, CeeDee 20/1"
     (2020 draft, round 1), "TURPIN, KAVONTAE SF22" (street free agent, 2022),
     "MILLER, VON U/Was" (waived, picked up from Washington).

Only the Offense / Defense / Special Teams tables are scraped -- Practice
Squad and Reserves/IR are skipped since they aren't part of the active
depth chart display.
"""
import re
import time
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

# "Last, First CODE" -- code is always a single whitespace-delimited token
NAME_PATTERN = re.compile(r"^(?P<last>.+?),\s*(?P<first>.+?)\s+(?P<code>\S+)$")

# Letter-prefix before a slash followed by letters (team abbreviation) means an
# inter-team move: traded (T/), waived-and-claimed (U/ or W/), cut-claimed (CC/),
# etc. Pure "YY/R" (draft year/round, both numeric) or "SF##"/"CF##" (street/college
# free agent, original signing) are NOT inter-team moves.
ACQUIRED_PATTERN = re.compile(r"^[A-Za-z]{1,2}/[A-Za-z]")

SKIP_TABLE_TITLES = {"practice squad", "reserves"}


def _smart_case(s):
    """Title-case only if the source was ALL CAPS -- leaves already-correct
    mixed case (CeeDee, DeMarvion, DaRon, etc.) untouched."""
    return s.title() if s.isupper() else s


def parse_player_cell(text):
    """Given raw cell text like 'Pickens, George T/Pit', return (display_name, code, is_acquired)."""
    text = text.strip()
    if not text:
        return None
    m = NAME_PATTERN.match(text)
    if not m:
        return (_smart_case(text), "", False)
    last = _smart_case(m.group("last").strip())
    first = _smart_case(m.group("first").strip())
    code = m.group("code").strip()
    is_acquired = bool(ACQUIRED_PATTERN.match(code))
    display_name = f"{first} {last}"
    return (display_name, code, is_acquired)


def scrape_ourlads_nfl_depth_chart(team_abbr, delay=1.5):
    """Returns (rows, schemes) where rows is a list of dicts:
    {position, player, jersey, code, isAcquired} and schemes is
    {"offense": "11 - One RB, One TE (66%)"|None, "defense": "Base 3-4"|None}
    pulled from each table's heading, same pattern as the NCAA version."""
    url = f"https://www.ourlads.com/nfldepthcharts/depthchart/{team_abbr}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    time.sleep(delay)  # be polite between requests

    soup = BeautifulSoup(resp.text, "html.parser")
    rows_out = []
    schemes = {"offense": None, "defense": None}

    for table in soup.find_all("table"):
        header_cells = [th.get_text(strip=True) for th in table.find_all("th")]
        if not header_cells or not header_cells[0].lower().startswith("pos"):
            continue

        # Determine which section this table belongs to by looking at the nearest
        # preceding heading, so Practice Squad / Reserves tables can be skipped.
        heading = table.find_previous(["h2", "h3"])
        heading_text = heading.get_text(strip=True) if heading else ""
        heading_lower = heading_text.lower()
        if any(skip in heading_lower for skip in SKIP_TABLE_TITLES):
            continue

        # Heading looks like "Offense11 - One RB, One TE (66%)" or
        # "DefenseBase 3-4" -- the unit name is the first word, the scheme
        # is whatever follows.
        if heading_lower.startswith("offense"):
            scheme = heading_text[len("offense"):].strip()
            schemes["offense"] = scheme or None
        elif heading_lower.startswith("defense"):
            scheme = heading_text[len("defense"):].strip()
            schemes["defense"] = scheme or None

        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if not cells:
                continue
            position = cells[0].get_text(strip=True)
            if not position:
                continue

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
                name, code, is_acquired = parsed
                rows_out.append({
                    "position": position,
                    "player": name,
                    "jersey": jersey,
                    "code": code,
                    "isAcquired": is_acquired,
                })

    return rows_out, schemes


if __name__ == "__main__":
    import json
    import sys
    abbr = sys.argv[1] if len(sys.argv) > 1 else "DAL"
    data, schemes = scrape_ourlads_nfl_depth_chart(abbr)
    print(json.dumps({"schemes": schemes, "rows": data}, indent=2))
    print(f"\n{len(data)} depth chart rows scraped", file=sys.stderr)
