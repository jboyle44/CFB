"""One-off: list CFB27 roster versions on teamcrafters and compare the
hard-coded version with the newest dated one. Reports via annotations."""
import re, json, requests
from scrape_teamcrafters import HEADERS, _scrape_team_page
def note(t, m): print(f"::notice title={t}::{m}")
versions = set()
for url in ("https://www.teamcrafters.net/rosters/CFB27/09-04-26/top",
            "https://www.teamcrafters.net/rosters/CFB27",
            "https://www.teamcrafters.net/rosters/CFB27/09-04-26/625"):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        found = set(re.findall(r"/rosters/CFB27/([A-Za-z0-9._-]+)/", r.text))
        versions |= found
        note("fetch", f"{url} -> {r.status_code}, {len(r.text)} bytes, versions linked: {sorted(found)}")
    except Exception as e:
        note("fetch", f"{url} -> error {e}")
note("all-versions", json.dumps(sorted(versions)))
for team, tid in (("alabama", 625), ("ohio-state", 701)):
    old = _scrape_team_page(f"https://www.teamcrafters.net/rosters/CFB27/freshmen-update-v2/{tid}")
    new = _scrape_team_page(f"https://www.teamcrafters.net/rosters/CFB27/09-04-26/{tid}")
    both = set(old) & set(new)
    changed = [n for n in both if old[n]["ovr"] != new[n]["ovr"] or old[n]["dev"] != new[n]["dev"]]
    ex = "; ".join(f"{n} {old[n]['ovr']}->{new[n]['ovr']}" for n in sorted(changed)[:6])
    note(f"compare-{team}", f"v2={len(old)} players, 09-04-26={len(new)}, shared={len(both)}, changed={len(changed)}, only-new={len(set(new)-set(old))}. e.g. {ex}")
