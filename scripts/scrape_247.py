"""
Scrapes 247Sports for:
  1. A team roster page -> {player_name: {profile_url, composite_score}}
  2. Individual player profile pages -> HS recruiting rank + transfer portal rank
     (only needed for players flagged as transfers by Ourlads)

NOTE ON RELIABILITY: written against 247Sports' rendered page structure observed
via manual inspection (roster table with Name/Jersey/POS/.../Rating columns;
player pages with "### 247Sports" (HS) and "### 247Sports Transfer Rankings"
sections). 247Sports' actual DOM likely has specific CSS classes for these
elements that would make this more robust -- inspect a live page's source and
tighten the selectors before relying on this at scale. The regex-based profile
parser is a reasonable fallback since it keys off stable display text rather
than markup, but it's not as robust as a proper CSS-selector-based scrape.
"""
import re
import time
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://247sports.com/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "DNT": "1",
}

# A single shared session so cookies picked up from the homepage (session ID,
# any bot-check clearance cookie, etc.) carry over to the roster request --
# hitting a deep URL cold, with no prior visit to the site, is itself a common
# bot-detection signal.
_session = requests.Session()
_session.headers.update(HEADERS)
_warmed_up = False

def _warm_up_session():
    global _warmed_up
    if _warmed_up:
        return
    try:
        _session.get("https://247sports.com/", timeout=20)
        time.sleep(1.0)
    except requests.RequestException:
        pass
    _warmed_up = True

RANK_PAIR_PATTERN = re.compile(r"\*\*([A-Za-z.]{2,5})\*\*\s*\[\*\*(\d+)\*\*\]")
SCORE_YEAR_PATTERN = re.compile(r"(\d{2,3})\s*\((\d{4})\)")


def scrape_247_roster(sports247_slug, delay=1.5):
    """Returns {player_name: {"profileUrl": str|None, "compositeScore": int|None}}"""
    _warm_up_session()
    url = f"https://247sports.com/team/{sports247_slug}/Roster/"
    resp = _session.get(url, timeout=20)
    resp.raise_for_status()
    time.sleep(delay)

    soup = BeautifulSoup(resp.text, "html.parser")
    out = {}

    tables = soup.find_all("table")
    if not tables:
        return out

    # Roster page may render as one table or two (name list + stats list) depending
    # on markup; handle both by zipping name rows against rating rows if separate.
    name_rows, rating_rows = [], []
    for table in tables:
        headers_txt = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if "name" in headers_txt and len(headers_txt) <= 2:
            name_rows = table.find_all("tr")
        elif "rating" in headers_txt or "jersey" in headers_txt:
            rating_rows = table.find_all("tr")
        elif "name" in headers_txt and "rating" in headers_txt:
            # single combined table
            for tr in table.find_all("tr")[1:]:
                cells = tr.find_all("td")
                if len(cells) < 2:
                    continue
                link = cells[0].find("a")
                name = (link.get_text(strip=True) if link else cells[0].get_text(strip=True))
                profile_url = link["href"] if link else None
                rating_text = cells[-1].get_text(strip=True)
                score = int(rating_text) if rating_text.isdigit() else None
                if name:
                    out[name] = {"profileUrl": profile_url, "compositeScore": score}
            return out

    # Two-table case: zip by row order
    for name_tr, rating_tr in zip(name_rows[1:], rating_rows[1:]):
        name_cells = name_tr.find_all("td")
        if not name_cells:
            continue
        link = name_cells[0].find("a")
        name = (link.get_text(strip=True) if link else name_cells[0].get_text(strip=True))
        profile_url = link["href"] if link else None
        rating_cells = rating_tr.find_all("td")
        rating_text = rating_cells[-1].get_text(strip=True) if rating_cells else ""
        score = int(rating_text) if rating_text.isdigit() else None
        if name:
            out[name] = {"profileUrl": profile_url, "compositeScore": score}

    return out


def scrape_247_player_profile(profile_url, delay=1.5):
    """
    Returns {
      "hsNationalRank": int|None, "hsPositionRank": int|None, "hsStateRank": int|None,
      "transferRank": int|None, "transferPosRank": int|None
    }
    """
    _warm_up_session()
    resp = _session.get(profile_url, timeout=20)
    resp.raise_for_status()
    time.sleep(delay)

    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text(separator="\n")

    result = {
        "hsNationalRank": None, "hsPositionRank": None, "hsStateRank": None,
        "transferRank": None, "transferPosRank": None,
    }

    # --- Transfer Rankings section ---
    transfer_idx = text.find("247Sports Transfer Rankings")
    if transfer_idx != -1:
        block = text[transfer_idx:transfer_idx + 400]
        pairs = RANK_PAIR_PATTERN.findall(block)
        for label, value in pairs:
            if label.upper() == "OVR":
                result["transferRank"] = int(value)
            else:
                # first non-OVR label found is the position rank
                if result["transferPosRank"] is None:
                    result["transferPosRank"] = int(value)

    # --- HS Prospect section (heading is "247Sports" without "Transfer Rankings" after it) ---
    for m in re.finditer(r"247Sports\n", text):
        idx = m.start()
        if text[idx:idx + 30].find("Transfer") != -1:
            continue  # this is the transfer heading, skip
        block = text[idx:idx + 400]
        pairs = RANK_PAIR_PATTERN.findall(block)
        if not pairs:
            continue
        # Order on the page is always [Natl.] then Position then State -- never guess
        # by label text length, since 2-letter position codes (QB, DE, RB...) collide
        # with real state abbreviations (e.g. DE = Delaware AND Defensive End).
        remaining = []
        for label, value in pairs:
            if label.upper().startswith("NATL"):
                result["hsNationalRank"] = int(value)
            else:
                remaining.append(int(value))
        if len(remaining) >= 2:
            result["hsPositionRank"], result["hsStateRank"] = remaining[0], remaining[-1]
        elif len(remaining) == 1:
            result["hsPositionRank"] = remaining[0]
        break  # only need the first HS prospect section found

    return result


if __name__ == "__main__":
    import json
    import sys
    slug = sys.argv[1] if len(sys.argv) > 1 else "ohio-state-buckeyes-football-79"
    roster = scrape_247_roster(slug)
    print(json.dumps(roster, indent=2)[:2000])
    print(f"\n{len(roster)} players scraped from roster", file=sys.stderr)
