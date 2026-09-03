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

# Reserves/IR entries use a different format: the trailing token is their
# real position (optionally with a trailing "^" marker) instead of an
# acquisition code -- e.g. "Moore, Devin CB^", "Hennessy, Matt C".
RESERVE_NAME_PATTERN = re.compile(r"^(?P<last>.+?),\s*(?P<first>.+?)\s+(?P<position>[A-Z]{1,3})\^?$")

# Letter-prefix before a slash followed by letters (team abbreviation) means an
# inter-team move: traded (T/), waived-and-claimed (U/ or W/), cut-claimed (CC/),
# etc. Pure "YY/R" (draft year/round, both numeric) or "SF##"/"CF##" (street/college
# free agent, original signing) are NOT inter-team moves.
ACQUIRED_PATTERN = re.compile(r"^[A-Za-z]{1,2}/[A-Za-z]")

SKIP_TABLE_TITLES = {"practice squad"}


ROMAN_NUMERAL_SUFFIXES = {"ii", "iii", "iv", "v", "vi", "vii"}


def _smart_case(s):
    """Title-case only if the source was ALL CAPS -- leaves already-correct
    mixed case (CeeDee, DeMarvion, DaRon, etc.) untouched. Roman numeral
    suffixes (II, III, IV...) need special handling afterward, since
    Python's .title() treats them as ordinary words and produces "Ii"/"Iii"
    instead of preserving the numeral -- confirmed real case: "MINSHEW II"
    became "Minshew Ii" instead of "Minshew II"."""
    if not s.isupper():
        return s
    titled = s.title()
    words = titled.split()
    fixed = [w.upper() if w.lower() in ROMAN_NUMERAL_SUFFIXES else w for w in words]
    return " ".join(fixed)


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


def parse_reserve_cell(text):
    """Given raw cell text like 'Moore, Devin CB^', return (display_name, position)."""
    text = text.strip()
    if not text:
        return None
    m = RESERVE_NAME_PATTERN.match(text)
    if not m:
        return (_smart_case(text), None)
    last = _smart_case(m.group("last").strip())
    first = _smart_case(m.group("first").strip())
    position = m.group("position").strip()
    display_name = f"{first} {last}"
    return (display_name, position)


def scrape_ourlads_nfl_depth_chart(team_abbr, delay=1.5):
    """Returns (rows, schemes, reserves) where rows is a list of dicts:
    {position, player, jersey, code, isAcquired}, schemes is
    {"offense": "11 - One RB, One TE (66%)"|None, "defense": "Base 3-4"|None}
    pulled from each table's heading, and reserves is a list of
    {status, player, jersey, position} for Ourlads' "Reserves" (IR) list --
    unlike the CFB version, these DO have a real position embedded in the
    name text (e.g. "Moore, Devin CB^"), just in a different cell format
    than active roster entries. Practice Squad is still skipped entirely --
    a different roster category, not injury-related."""
    url = f"https://www.ourlads.com/nfldepthcharts/depthchart/{team_abbr}"
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
            continue

        # Determine which section this table belongs to by looking at the nearest
        # preceding heading, so Practice Squad can be skipped and Reserves (IR)
        # can be routed to the separate reserves list with its different format.
        heading = table.find_previous(["h2", "h3"])
        heading_text = heading.get_text(strip=True) if heading else ""
        heading_lower = heading_text.lower()
        if any(skip in heading_lower for skip in SKIP_TABLE_TITLES):
            continue
        is_reserves_table = "reserves" in heading_lower

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
            status_or_position = cells[0].get_text(strip=True)
            if not status_or_position:
                continue

            slot_cells = cells[1:]

            if is_reserves_table:
                # Reserves rows: first cell is a status code (IR, PUP, etc),
                # and the real position is embedded in the name cell itself
                # (e.g. "Moore, Devin CB^") rather than a separate column.
                for i in range(0, len(slot_cells) - 1, 2):
                    jersey = slot_cells[i].get_text(strip=True)
                    player_cell = slot_cells[i + 1]
                    player_link = player_cell.find("a")
                    raw_text = (player_link.get_text(strip=True) if player_link
                                else player_cell.get_text(strip=True))
                    if not raw_text:
                        continue
                    parsed = parse_reserve_cell(raw_text)
                    if not parsed:
                        continue
                    name, position = parsed
                    reserves_out.append({
                        "status": status_or_position,
                        "player": name,
                        "jersey": jersey,
                        "position": position,
                    })
                continue

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
                    "position": status_or_position,
                    "player": name,
                    "jersey": jersey,
                    "code": code,
                    "isAcquired": is_acquired,
                })

    return rows_out, schemes, reserves_out


if __name__ == "__main__":
    import json
    import sys
    abbr = sys.argv[1] if len(sys.argv) > 1 else "DAL"
    data, schemes, reserves = scrape_ourlads_nfl_depth_chart(abbr)
    print(json.dumps({"schemes": schemes, "rows": data, "reserves": reserves}, indent=2))
    print(f"\n{len(data)} depth chart rows, {len(reserves)} reserves scraped", file=sys.stderr)
