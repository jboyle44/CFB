import sys
sys.path.insert(0, '.')
from build_depth_chart import build

big_ten = ["illinois","indiana","iowa","maryland","michigan","michigan-state","minnesota",
    "nebraska","northwestern","ohio-state","oregon","penn-state","purdue","rutgers",
    "ucla","usc","washington","wisconsin"]

for team_key in big_ten:
    print(f"=== Building {team_key} ===")
    build(team_key, f'../depth_chart_data/{team_key}.json')
