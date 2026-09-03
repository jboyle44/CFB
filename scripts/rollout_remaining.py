import sys
import os
import time
import subprocess
import requests
sys.path.insert(0, '.')
from build_depth_chart import build
from teams_config import TEAMS

STOP_FLOOR = 25000  # generous sanity floor under the new 30k/month tier
SAFETY_BUFFER = 100  # stop at 2900 remaining, not right at 2800, to avoid overshooting
DELAY_BETWEEN_TEAMS_SECONDS = 3

final_10 = {"colorado", "houston", "iowa-state", "kansas", "kansas-state",
            "oklahoma-state", "tcu", "texas-tech", "utah", "west-virginia"}
remaining_teams = [t for t in TEAMS if t in final_10]

def check_remaining(max_retries=4):
    """A 429 here means we're transiently rate-limited, NOT that we're
    actually low on monthly budget -- retry with backoff instead of treating
    it as a stop signal. Only genuinely stop the rollout on a confirmed low
    X-CallLimit-Remaining reading from an actual successful response."""
    api_key = os.environ.get("CFBD_API_KEY")
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    for attempt in range(max_retries):
        resp = requests.get("https://api.collegefootballdata.com/teams/fbs", headers=headers, timeout=20)
        if resp.status_code == 429:
            backoff = 2 ** attempt * 3
            print(f"  budget check got 429, backing off {backoff}s", file=sys.stderr)
            time.sleep(backoff)
            continue
        return int(resp.headers.get("X-CallLimit-Remaining", -1))
    # Genuinely couldn't get a clean read after retries -- treat as unknown
    # and stop out of caution, but this is now a rare path since pacing is
    # applied to every real request too.
    return -1

def commit_and_push(team_key):
    """Commit after every team so progress survives even if the job fails
    or times out partway through a long rollout."""
    subprocess.run(["git", "config", "user.name", "rollout-bot"], cwd="..")
    subprocess.run(["git", "config", "user.email", "actions@github.com"], cwd="..")
    subprocess.run(["git", "add", f"depth_chart_data/{team_key}.json"], cwd="..")
    result = subprocess.run(["git", "commit", "-m", f"Rollout multi-hop fix: {team_key}"],
                             cwd="..", capture_output=True, text=True)
    if result.returncode != 0 and "nothing to commit" not in result.stdout:
        print(f"  commit warning: {result.stdout} {result.stderr}", file=sys.stderr)
        return
    for attempt in range(3):
        push = subprocess.run(["git", "push"], cwd="..", capture_output=True, text=True)
        if push.returncode == 0:
            return
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd="..")
    print(f"  WARNING: push failed after retries for {team_key}", file=sys.stderr)

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
        commit_and_push(team_key)
        completed.append(team_key)
    except Exception as e:
        print(f"  FAILED for {team_key}: {e}", file=sys.stderr)
        skipped.append(team_key)

    time.sleep(DELAY_BETWEEN_TEAMS_SECONDS)

final_remaining = check_remaining()
print(f"\n=== ROLLOUT SUMMARY ===", file=sys.stderr)
print(f"Completed: {len(completed)} teams: {completed}", file=sys.stderr)
print(f"Skipped/not reached: {len(skipped)} teams: {skipped}", file=sys.stderr)
print(f"Remaining calls: {final_remaining}", file=sys.stderr)
