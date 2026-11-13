"""Backtest trends for the board's How-it-works tab -> cbb/results/trends.json.

Model = the live board model (style profiles blended with last season, K=10), walk-forward:
each season predicted by a model trained only on earlier seasons (2017-2026, 2021 excluded).
"""
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from analyze import MAIN, features, ridge_fit  # noqa: E402

warnings.filterwarnings("ignore")
SRC = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/cbb/work/games_blend10.parquet"
g = pd.read_parquet(SRC)
g = g[g.season != 2021].reset_index(drop=True)
X = features(g).fillna(0)
X["spread"] = g.spread
cols = [f"main_{m}" for m in MAIN] + ["neutral", "spread"]
p = pd.Series(np.nan, index=g.index)
for t in sorted(g.season.unique()):
    if t < 2017:
        continue
    tr, te = (g.season < t).values, (g.season == t).values
    Xt = X.loc[tr, cols].values
    mu, sd = Xt.mean(0), Xt.std(0) + 1e-9
    b = ridge_fit((Xt - mu) / sd, g.resid.values[tr], 500.0)
    p[te] = b[0] + ((X.loc[te, cols].values - mu) / sd) @ b[1:]
g["p"] = p
g = g[g.p.notna() & (g.resid != 0)].copy()
g["win"] = np.sign(g.p) == np.sign(g.resid)
g["edge"] = g.p.abs()
g["mon"] = g.date.dt.tz_convert("America/New_York").dt.month


def summ(d):
    n = len(d)
    w = int(d.win.sum())
    return {"bets": n, "wins": w, "losses": n - w, "win_pct": round(100 * w / n, 1) if n else None,
            "units": round(w * 100 / 110 - (n - w), 1)}


plays = g[g.edge >= 1]
strong = g[g.edge >= 2]
out = {"model": "Live board model: team style profiles blended with last season, walk-forward 2017-2026 (2021 excluded)",
       "overall": {"plays_1plus": summ(plays), "strong_2plus": summ(strong)}}
MON = [(11, "Nov"), (12, "Dec"), (1, "Jan"), (2, "Feb"), (3, "Mar")]
out["by_month"] = [{"month": name, "plays": summ(plays[plays.mon == m]), "strong": summ(strong[strong.mon == m])} for m, name in MON]
out["by_season"] = [{"season": f"{int(s) - 1}-{str(int(s))[2:]}", "plays": summ(plays[plays.season == s]), "strong": summ(strong[strong.season == s])}
                    for s in sorted(g.season.unique())]
bins = [(0, 0.5, "Under 0.5"), (0.5, 1, "0.5 to 1"), (1, 1.5, "1 to 1.5"), (1.5, 2, "1.5 to 2"), (2, 3, "2 to 3"), (3, 99, "3+")]
out["by_edge"] = [{"edge": lab, **summ(g[(g.edge >= lo) & (g.edge < hi)])} for lo, hi, lab in bins]
# dog vs favorite picks, and tempo-flag
fav_pick = (np.sign(g.p) > 0) == (g.spread < 0)
out["by_side"] = [{"side": "Underdog picks", **summ(plays[~fav_pick[plays.index]])},
                  {"side": "Favorite picks", **summ(plays[fav_pick[plays.index]])}]
# cumulative units by date for plays (1+), for a chart
c = plays.sort_values("date")
c["u"] = np.where(c.win, 100 / 110, -1.0)
c["cum"] = c.u.cumsum()
step = max(1, len(c) // 300)
out["cumulative"] = [{"date": d.strftime("%Y-%m-%d"), "units": round(float(u), 1)} for d, u in zip(c.date.iloc[::step], c.cum.iloc[::step])]
json.dump(out, open("cbb/results/trends.json", "w"), indent=1)
print(json.dumps(out["overall"]), "\n", [(m["month"], m["plays"]["win_pct"], m["strong"]["win_pct"]) for m in out["by_month"]])
print([(e["edge"], e["bets"], e["win_pct"]) for e in out["by_edge"]])
print(out["by_side"])
