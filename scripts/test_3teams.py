import sys
sys.path.insert(0, '.')
from build_depth_chart import build
for team_key in ['ohio-state', 'oregon', 'texas']:
    print(f"=== Building {team_key} ===")
    build(team_key, f'../depth_chart_data/{team_key}.json')
