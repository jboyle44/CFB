import json
from scrape_cfbd_recruiting import get_recruiting_players, get_transfer_portal

result = {}

try:
    players = get_recruiting_players('Ohio State', 2025)
    result['recruiting_players_count'] = len(players)
    result['recruiting_sample'] = dict(list(players.items())[:5])
except Exception as e:
    result['recruiting_error'] = str(e)

try:
    portal = get_transfer_portal(2026)
    result['portal_total_count'] = len(portal)
    oh_state_transfers = {n: i for n, i in portal.items() if i.get('destination') == 'Ohio State'}
    result['ohio_state_transfer_count'] = len(oh_state_transfers)
    result['ohio_state_transfer_sample'] = dict(list(oh_state_transfers.items())[:5])
except Exception as e:
    result['portal_error'] = str(e)

with open('../test_cfbd_result.json', 'w') as f:
    json.dump(result, f, indent=2)
