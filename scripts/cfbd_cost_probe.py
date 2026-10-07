"""One-off probe: does /recruiting/players with year only return the full
national class, and what does each call cost? Writes cfbd_cost_probe.json."""
import json, os, requests
B = "https://api.collegefootballdata.com"
H = {"Authorization": f"Bearer {os.environ['CFBD_API_KEY']}", "Accept": "application/json"}
out = {"calls": []}
def get(path, **params):
    r = requests.get(B + path, headers=H, params=params, timeout=60)
    out["calls"].append({"path": path, "params": params, "status": r.status_code,
                         "remaining_header": r.headers.get("X-CallLimit-Remaining"),
                         "bytes": len(r.content)})
    return r.json() if r.ok else None
used_before = get("/info")["usedCalls"]
national = {}
for yr in (2022, 2024):
    national[yr] = get("/recruiting/players", year=yr)
team = {}
for school in ("Alabama", "SMU", "Vanderbilt"):
    team[school] = get("/recruiting/players", year=2024, team=school)
used_after = get("/info")["usedCalls"]
summary = {"used_before": used_before, "used_after": used_after}
for yr, rows in national.items():
    summary[f"national_{yr}_rows"] = len(rows)
    summary[f"national_{yr}_classifications"] = sorted({r.get("recruitType") for r in rows if r.get("recruitType")})
    summary[f"national_{yr}_with_committedTo"] = sum(1 for r in rows if r.get("committedTo"))
    summary[f"national_{yr}_fields"] = sorted(rows[0].keys()) if rows else []
nat24 = {(r.get("name"), r.get("committedTo")) for r in national[2024]}
for school, rows in team.items():
    ids = {(r.get("name"), r.get("committedTo")) for r in rows}
    summary[f"team_{school}_2024_rows"] = len(rows)
    summary[f"team_{school}_2024_missing_from_national"] = sorted(n for n, _ in ids - nat24)
    summary[f"national_2024_filtered_{school}"] = sum(1 for r in national[2024] if r.get("committedTo") == school)
out["summary"] = summary
json.dump(out, open("cfbd_cost_probe.json", "w"), indent=2)
print(json.dumps(summary, indent=2))
