import sys
import os
import requests
sys.path.insert(0, '.')
from build_depth_chart import build
from teams_config import TEAMS

STOP_FLOOR = 2800
SAFETY_BUFFER = 100  # stop at 2900 remaining, not right at 2800, to avoid overshooting

already_done = {"ohio-state", "oregon", "texas", "indiana"}
remaining_teams = [t for t in TEAMS if t not in already_done]

def check_remaining():
    api_key = os.environ.get("CFBD_API_KEY")
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    resp = requests.get("https://api.collegefootballdata.com/teams/fbs", headers=headers, timeout=20)
    return int(resp.headers.get("X-CallLimit-Remaining", -1))

completed = []
skipped = []

start_remaining = check_remaining()
print(f"Starting remaining: {start_remaining}", file=sys.stderr)

for i, team_key in enumerate(remaining_teams):
    remaining = check_remaining()
    print(f"[{i+1}/{len(remaining_teams)}] {team_key} -- remaining before: {remaining}", file=sys.stderr)

    if remaining <= STOP_FLOOR + SAFETY_BUFFER:
        print(f"STOPPING: remaining ({remaining}) at or below safety threshold "
              f"({STOP_FLOOR + SAFETY_BUFFER}). Halting rollout to protect the {STOP_FLOOR} floor.",
              file=sys.stderr)
        skipped = remaining_teams[i:]
        break

    try:
        build(team_key, f"../depth_chart_data/{team_key}.json")
        completed.append(team_key)
    except Exception as e:
        print(f"  FAILED for {team_key}: {e}", file=sys.stderr)
        skipped.append(team_key)

final_remaining = check_remaining()
print(f"\n=== ROLLOUT SUMMARY ===", file=sys.stderr)
print(f"Completed: {len(completed)} teams: {completed}", file=sys.stderr)
print(f"Skipped/not reached: {len(skipped)} teams: {skipped}", file=sys.stderr)
print(f"Remaining calls: {final_remaining}", file=sys.stderr)
