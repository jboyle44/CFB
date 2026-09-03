from scrape_cfbd_recruiting import get_recruiting_players, get_transfer_portal

print('=== Testing recruiting/players for Ohio State, 2025 class ===')
try:
    players = get_recruiting_players('Ohio State', 2025)
    print(f'Got {len(players)} players')
    for name, info in list(players.items())[:5]:
        print(' ', name, info)
except Exception as e:
    print('FAILED:', e)

print()
print('=== Testing player/portal for 2026 ===')
try:
    portal = get_transfer_portal(2026)
    print(f'Got {len(portal)} transfer portal entries')
    oh_state_transfers = [(n, i) for n, i in portal.items() if i.get('destination') == 'Ohio State']
    print(f'Of which {len(oh_state_transfers)} destined for Ohio State')
    for name, info in oh_state_transfers[:5]:
        print(' ', name, info)
except Exception as e:
    print('FAILED:', e)
