import json
from scrape_cfbd_recruiting import get_transfer_portal

result = {}
for yr in [2024, 2025, 2026]:
    try:
        portal = get_transfer_portal(yr)
        result[f'year_{yr}_count'] = len(portal)
        if len(portal) > 0:
            result[f'year_{yr}_sample'] = dict(list(portal.items())[:3])
    except Exception as e:
        result[f'year_{yr}_error'] = str(e)

with open('../test_cfbd_result.json', 'w') as f:
    json.dump(result, f, indent=2)
