"""
Scrapes player ratings (OVR, dev trait) from teamcrafters.net's CFB27 and
Madden27 team pages -- both are plain server-rendered HTML (unlike EA's own
ratings pages, which are client-side JS rendered and inaccessible to a
simple scraper). No auth or API key needed.
"""
import re
import time
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _scrape_team_page(url, delay=1.0):
    """
    Returns {player_name_lower: {"ovr": int, "dev": str, "position": str}}
    Parses the "All Players" table: each row has player name (as a link),
    position, OVR, and Dev columns.
    """
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    time.sleep(delay)

    soup = BeautifulSoup(resp.text, "html.parser")
    out = {}

    table = soup.find("table")
    if table is None:
        return out

    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        # First cell contains the player link + position/class/archetype text.
        # get_text needs a separator, or names split across nested tags in
        # the markup collapse together with no space (e.g. "JeremiahSmith").
        link = cells[0].find("a")
        if not link:
            continue
        name = link.get_text(" ", strip=True)
        name = re.sub(r"\s+", " ", name).strip()
        if not name:
            continue

        try:
            ovr = int(cells[1].get_text(strip=True))
        except (ValueError, IndexError):
            continue
        dev = cells[2].get_text(strip=True) if len(cells) > 2 else None

        norm_name = name.replace("*", "").strip().lower()
        out[norm_name] = {"ovr": ovr, "dev": dev}

    return out


def get_cfb27_ratings(team_id, version="freshmen-update-v2"):
    url = f"https://www.teamcrafters.net/rosters/CFB27/{version}/{team_id}"
    return _scrape_team_page(url)


def get_madden27_ratings(team_id, version="082726"):
    url = f"https://www.teamcrafters.net/rosters/MADDEN27/{version}/{team_id}"
    return _scrape_team_page(url)
