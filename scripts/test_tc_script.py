import json
from cfb27_team_ids import CFB27_TEAM_IDS
from madden27_team_ids import MADDEN27_TEAM_IDS
from scrape_teamcrafters import get_cfb27_ratings, get_madden27_ratings

result = {}

try:
    cfb = get_cfb27_ratings(CFB27_TEAM_IDS["ohio-state"])
    result["cfb27_ohio_state_count"] = len(cfb)
    result["cfb27_sample"] = dict(list(cfb.items())[:5])
    result["cfb27_jeremiah_smith"] = cfb.get("jeremiah smith")
except Exception as e:
    result["cfb27_error"] = str(e)

try:
    madden = get_madden27_ratings(MADDEN27_TEAM_IDS["dal"])
    result["madden27_dallas_count"] = len(madden)
    result["madden27_sample"] = dict(list(madden.items())[:5])
except Exception as e:
    result["madden27_error"] = str(e)

with open('../test_tc_result.json', 'w') as f:
    json.dump(result, f, indent=2)
