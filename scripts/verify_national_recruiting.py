"""One-off head-to-head: build the same teams (recruiting data stripped) with
the national per-year pull and with the legacy per-school query, and compare.
Reports via GitHub annotations (no commit)."""
import json, os, sys, tempfile, copy
import build_depth_chart as b
import scrape_cfbd_recruiting as c

def legacy_get_recruiting_players(team_display_name, year):
    def fetch():
        resp = c._paced_get(f"{c.BASE_URL}/recruiting/players", headers=c._auth_headers(),
                            params={"year": year, "team": team_display_name}, timeout=20)
        resp.raise_for_status()
        return resp.json()
    players = c._cached(f"legacy_{team_display_name}_{year}", fetch)
    by_full, cands = {}, {}
    for r in players:
        name = (r.get("name") or "").strip().lower()
        if not name: continue
        info = {k: r.get(k) for k in ("stars", "rating", "ranking", "position")}
        by_full[name] = info
        last = name.split()[-1] if name.split() else None
        if last: cands.setdefault(last, []).append(info)
    return by_full, {l: v[0] for l, v in cands.items() if len(v) == 1}

national_fn = b.get_recruiting_players
real_scrape = b.scrape_ourlads_depth_chart
scrape_cache = {}
def cached_scrape(slug, oid):   # same roster for both builds
    if slug not in scrape_cache: scrape_cache[slug] = real_scrape(slug, oid)
    return copy.deepcopy(scrape_cache[slug])
b.scrape_ourlads_depth_chart = cached_scrape

tmp = tempfile.mkdtemp()
tot = dict(rows=0, same=0, diff=0)
diffs = []
for t in sys.argv[1:]:
    d = json.load(open(f"../depth_chart_data/{t}.json"))
    for r in d["rows"]:
        r["compositeScore"] = r["hsNationalRank"] = r["recruitLookedUp"] = None
    results = {}
    for label, fn in (("national", national_fn), ("legacy", legacy_get_recruiting_players)):
        out = os.path.join(tmp, f"{t}.{label}.json")
        json.dump(d, open(out, "w"))
        b.get_recruiting_players = fn
        b.build(t, out)
        results[label] = {(r["player"], r["position"]): r["compositeScore"] for r in json.load(open(out))["rows"]}
    for k, a in results["legacy"].items():
        n = results["national"].get(k)
        tot["rows"] += 1
        if a == n: tot["same"] += 1
        else: tot["diff"] += 1; diffs.append(f"{t}:{k[0]} legacy={a} national={n}")
print(f"::notice title=head-to-head::{json.dumps(tot)}")
print(f"::notice title=head-to-head-diffs::{'; '.join(diffs[:40]) or 'none'}")
legacy_calls = len([f for f in os.listdir(c.CACHE_DIR) if f.startswith('legacy_')])
national_calls = len([f for f in os.listdir(c.CACHE_DIR) if f.startswith('recruiting_')])
portal_calls = len([f for f in os.listdir(c.CACHE_DIR) if f.startswith('portal_')])
print(f"::notice title=call-counts::national={national_calls} legacy={legacy_calls} portal={portal_calls}")
