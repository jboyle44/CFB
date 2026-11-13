"""Walk-forward win rates by month for every Team Profile Model variant backtested."""
import sys, warnings
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from analyze import MAIN, features, ridge_fit
warnings.filterwarnings("ignore")
W = "/home/claude/cbb/work/"
def wf(g, lam=500.0):
    X = features(g).fillna(0); X["spread"] = g.spread
    cols = [f"main_{m}" for m in MAIN] + ["neutral", "spread"]
    p = pd.Series(np.nan, index=g.index)
    for t in sorted(g.season.unique()):
        if t < 2017: continue
        tr, te = (g.season < t).values, (g.season == t).values
        Xt = X.loc[tr, cols].values; mu, sd = Xt.mean(0), Xt.std(0) + 1e-9
        b = ridge_fit((Xt - mu) / sd, g.resid.values[tr], lam)
        p[te] = b[0] + ((X.loc[te, cols].values - mu) / sd) @ b[1:]
    return p
def load(f):
    g = pd.read_parquet(W + f); return g[g.season != 2021].reset_index(drop=True)
raw, adj, bl = load("games.parquet"), load("games_adj.parquet"), load("games_blend10.parquet")
p_raw, p_adj, p_bl = wf(raw), wf(adj), wf(bl)
raw["p"] = p_raw; adj["p"] = p_adj; bl["p"] = p_bl
ens = raw[["gameId", "p", "resid", "date", "season"]].merge(adj[["gameId", "p"]], on="gameId", suffixes=("_r", "_a"))
ens["p"] = (ens.p_r + ens.p_a) / 2
models = {"Raw (5+ games)": raw, "Opp-adjusted (5+ games)": adj, "Raw+adj average (5+ games)": ens,
          "Blended w/ last season (all games, = live board)": bl}
MON = {11: "Nov", 12: "Dec", 1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr"}
rows = []
for name, g in models.items():
    g = g[g.p.notna() & (g.resid != 0)].copy()
    g["mon"] = g.date.dt.tz_convert("America/New_York").dt.month.map(MON)
    for th in (1, 2):
        s = g[g.p.abs() >= th]
        s = s.assign(win=(np.sign(s.p) == np.sign(s.resid)))
        for mon in list(MON.values()) + ["All"]:
            ss = s if mon == "All" else s[s.mon == mon]
            if len(ss) == 0: continue
            w = ss.win.sum(); n = len(ss)
            rows.append({"model": name, "edge": f"{th}+", "month": mon, "bets": n, "win_pct": round(w / n * 100, 1),
                         "units": round(w * 100 / 110 - (n - w), 1),
                         "seasons_above_52.4": f"{(ss.groupby('season').win.mean() > 0.5238).sum()}/{ss.season.nunique()}"})
R = pd.DataFrame(rows)
R.to_csv("cbb/results/walkforward_by_month.csv", index=False)
pd.set_option("display.width", 200)
for (m, e), d in R.groupby(["model", "edge"], sort=False):
    print(f"\n{m} | edge {e}")
    print(d[["month", "bets", "win_pct", "units", "seasons_above_52.4"]].to_string(index=False))
