"""One-off check: rebuild teams with recruiting data stripped, using the
national per-year recruiting pull, and compare to the committed per-school
results. Reports via GitHub annotations (no commit)."""
import json, os, shutil, subprocess, sys, tempfile
teams = sys.argv[1:]
tmp = tempfile.mkdtemp()
totals = dict(rows=0, same=0, diff=0, new_found=0, lost=0)
diffs = []
for t in teams:
    src = f"../depth_chart_data/{t}.json"
    d = json.load(open(src))
    for r in d["rows"]:
        r["compositeScore"] = None; r["hsNationalRank"] = None; r["recruitLookedUp"] = None
    out = os.path.join(tmp, f"{t}.json")
    json.dump(d, open(out, "w"))
    subprocess.run([sys.executable, "build_depth_chart.py", t, out], check=True)
    ref = {r["player"]: r for r in json.load(open(src))["rows"]}
    for r in json.load(open(out))["rows"]:
        if r["player"] not in ref: continue
        a, b = ref[r["player"]]["compositeScore"], r["compositeScore"]
        totals["rows"] += 1
        if a == b: totals["same"] += 1
        elif a is None: totals["new_found"] += 1
        elif b is None: totals["lost"] += 1; diffs.append(f"{t}:{r['player']} {a}->None")
        else: totals["diff"] += 1; diffs.append(f"{t}:{r['player']} {a}->{b}")
print(f"::notice title=national-recruiting-verify::{json.dumps(totals)}")
print(f"::notice title=national-recruiting-diffs::{'; '.join(diffs[:40]) or 'none'}")
