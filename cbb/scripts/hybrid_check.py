"""Compare live-board blended model vs hybrid (blend until both teams have 5 games, then raw+adjusted average)."""
import sys, warnings
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from analyze import MAIN, features, ridge_fit
warnings.filterwarnings("ignore")
W = "/home/claude/cbb/work/"
def wf(g):
    X = features(g).fillna(0); X["spread"] = g.spread
    cols = [f"main_{m}" for m in MAIN] + ["neutral", "spread"]
    p = pd.Series(np.nan, index=g.index)
    for t in sorted(g.season.unique()):
        if t < 2017: continue
        tr, te = (g.season < t).values, (g.season == t).values
        Xt = X.loc[tr, cols].values; mu, sd = Xt.mean(0), Xt.std(0) + 1e-9
        b = ridge_fit((Xt - mu) / sd, g.resid.values[tr], 500.0)
        p[te] = b[0] + ((X.loc[te, cols].values - mu) / sd) @ b[1:]
    return g.assign(p=p)[["gameId", "p"]]
ld = lambda f: (lambda g: g[g.season != 2021].reset_index(drop=True))(pd.read_parquet(W + f))
bl, raw, adj = ld("games_blend10.parquet"), ld("games.parquet"), ld("games_adj.parquet")
pb, pr, pa = wf(bl), wf(raw), wf(adj)
g = bl[["gameId", "season", "date", "resid", "h_n_prior", "a_n_prior"]].merge(pb, on="gameId")
g = g.merge(pr.rename(columns={"p": "pr"}), on="gameId", how="left").merge(pa.rename(columns={"p": "pa"}), on="gameId", how="left")
late = (np.minimum(g.h_n_prior, g.a_n_prior) >= 5) & g.pr.notna() & g.pa.notna()
g["hyb"] = np.where(late, (g.pr + g.pa) / 2, g.p)
g = g[g.p.notna() & (g.resid != 0)]
g["mon"] = g.date.dt.tz_convert("America/New_York").dt.month
def wr(col, d, th):
    s = d[d[col].abs() >= th]; w = (np.sign(s[col]) == np.sign(s.resid)); return f"{w.mean()*100:.1f}% ({len(s)})"
for th in (1, 2):
    print(f"\n=== edge {th}+ ===  overall: blended {wr('p', g, th)} | hybrid {wr('hyb', g, th)}")
    print("season   blended        hybrid")
    for s in sorted(g.season.unique()):
        d = g[g.season == s]; print(s, wr("p", d, th).ljust(14), wr("hyb", d, th))
    print("month    blended        hybrid")
    for m, n in [(11, "Nov"), (12, "Dec"), (1, "Jan"), (2, "Feb"), (3, "Mar")]:
        d = g[g.mon == m]; print(n.ljust(8), wr("p", d, th).ljust(14), wr("hyb", d, th))
