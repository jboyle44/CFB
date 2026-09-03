import sys
sys.path.insert(0, '.')
import json
from scrape_cfbd_recruiting import get_transfer_portal

result = {}
portal = get_transfer_portal(2026)
result['total_2026_entries'] = len(portal)
# Look for our guy specifically
result['earl_entry'] = portal.get('earl little jr.')

# Also check how many have destination == "Ohio State"
oh_state = {k: v for k, v in portal.items() if v.get('destination') == 'Ohio State'}
result['ohio_state_count'] = len(oh_state)
result['ohio_state_names'] = list(oh_state.keys())

with open('../little_diag2_result.json', 'w') as f:
    json.dump(result, f, indent=2)
