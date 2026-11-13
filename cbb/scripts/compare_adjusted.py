"""Raw vs opponent-adjusted team profiles: walk-forward on identical games."""
import sys, warnings
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from analyze import MAIN, features, ridge_fit
warnings.filterwarnings("ignore")
raw = pd.read_parquet("/home/claude/cbb/work/games.parquet")
adj = pd.read_parquet("/home/claude/cbb/work/games_adj.parquet")
ids = sorted(set(raw.gameId) & set(adj.gameId))
raw = raw.set_index("gameId").loc[ids].reset_index()
adj = adj.set_index("gameId").loc[ids].reset_index()
keep = raw.season != 2021
raw, adj = raw[keep].reset_index(drop=True), adj[keep].reset_index(drop=True)
Xr, Xa = features(raw), features(adj)
M = [f"main_{m}" for m in MAIN]
base = pd.DataFrame({"neutral": raw.neutral.astype(float), "spread": raw.spread})
sets = {
    "Raw factors (current model)": pd.concat([Xr[M], base], axis=1),
    "Opponent-adjusted factors": pd.concat([Xa[M], base], axis=1),
    "Raw + adjusted": pd.concat([Xr[M], Xa[M].add_suffix("_adj"), base], axis=1),
}
y = raw.resid.values
def walk(X, lam=500.0):
    p = pd.Series(np.nan, index=raw.index)
    for t in sorted(raw.season.unique()):
        if t < 2017: continue
        tr, te = (raw.season < t).values, (raw.season == t).values
        Xt = X.values[tr]; mu, sd = Xt.mean(0), Xt.std(0) + 1e-9
        b = ridge_fit((Xt - mu) / sd, y[tr], lam)
        p[te] = b[0] + ((X.values[te] - mu) / sd) @ b[1:]
    return p
def topn(p, n):
    ok = p.notna() & (raw.resid != 0); q = p[ok]; idx = q.abs().sort_values(ascending=False).index[:n]
    return (np.sign(p[idx]) == np.sign(raw.resid[idx])).mean()
rows = []; preds = {}
for k, X in sets.items():
    p = walk(X); preds[k] = p
    ok = p.notna(); yy, pp = raw.resid[ok], p[ok]
    r = {"model": k, "oos_r2": 1 - ((yy - pp) ** 2).sum() / (yy ** 2).sum()}
    for th in (1, 2):
        s = ok & (p.abs() >= th) & (raw.resid != 0)
        r[f"bets_{th}"] = int(s.sum()); r[f"win_{th}"] = (np.sign(p[s]) == np.sign(raw.resid[s])).mean()
    for n in (1000, 3000, 10000): r[f"top{n}"] = topn(p, n)
    late = ok & (raw.date.dt.month.isin([1, 2, 3, 4])) & (p.abs() >= 1) & (raw.resid != 0)
    r["conf_season_bets_1"] = int(late.sum()); r["conf_season_win_1"] = (np.sign(p[late]) == np.sign(raw.resid[late])).mean()
    by = []
    for t in sorted(raw.season.unique()):
        s = ok & (raw.season == t) & (p.abs() >= 1) & (raw.resid != 0)
        if s.sum(): by.append(round((np.sign(p[s]) == np.sign(raw.resid[s])).mean(), 3))
    r["seasons>52.4"] = f"{sum(b > 0.5238 for b in by)}/{len(by)}"; r["by_season"] = by
    rows.append(r)
res = pd.DataFrame(rows)
pd.set_option("display.width", 250)
print(res.drop(columns="by_season").round(4).to_string(index=False))
for r in rows: print(r["model"], r["by_season"])
res.to_csv("/home/claude/cbb/work/results/raw_vs_adjusted.csv", index=False)
# how different are adjusted profiles from raw?
for m in ["o_orb", "o_tov", "o_efg", "d_efg", "d_paint", "pace"]:
    print(m, "corr raw vs adj:", round(np.corrcoef(raw[f"h_pre_{m}"], adj[f"h_pre_{m}"])[0, 1], 3))
# ensemble: average the raw and adjusted predictions
p = (preds["Raw factors (current model)"] + preds["Opponent-adjusted factors"]) / 2
ok = p.notna(); yy, pp = raw.resid[ok], p[ok]
out = {"oos_r2": round(1 - ((yy - pp) ** 2).sum() / (yy ** 2).sum(), 4)}
for th in (1, 2):
    s = ok & (p.abs() >= th) & (raw.resid != 0)
    out[f"bets_{th}"] = int(s.sum()); out[f"win_{th}"] = round((np.sign(p[s]) == np.sign(raw.resid[s])).mean(), 4)
for n in (1000, 3000, 10000): out[f"top{n}"] = round(topn(p, n), 4)
by = [round((np.sign(p[s]) == np.sign(raw.resid[s])).mean(), 3) for t in sorted(raw.season.unique())
      for s in [ok & (raw.season == t) & (p.abs() >= 1) & (raw.resid != 0)] if s.sum()]
out["seasons>52.4"] = f"{sum(b > 0.5238 for b in by)}/{len(by)}"
print("Ensemble (avg of raw + adjusted):", out, by)
agree = ok & (np.sign(preds["Raw factors (current model)"]) == np.sign(preds["Opponent-adjusted factors"]))
print("models pick the same side in", round(agree[ok].mean(), 3), "of games")
