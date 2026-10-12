"""One-off: dump every Madden27 team roster from teamcrafters for alias review."""
import json
from madden27_team_ids import MADDEN27_TEAM_IDS
from scrape_teamcrafters import get_madden27_ratings
out = {t: get_madden27_ratings(i) for t, i in MADDEN27_TEAM_IDS.items()}
json.dump(out, open("../madden_roster_dump.json", "w"), indent=1)
print({t: len(v) for t, v in out.items()})
