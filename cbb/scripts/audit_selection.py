"""Audit test: model-selection (hindsight) bias.

Seven variants were compared during development. Nested check: for each test season,
pick the variant with the best record on the OTHER seasons, then score only the pick on
the held-out season. If the nested result is close to the hybrid's reported result,
choosing it after the fact did not inflate it much.
"""
import sys, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent))
from analyze import MAIN, features, ridge_fit
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
    return g[["gameId", "season", "resid"]].assign(p=p.values)
ld = lambda f: (lambda g: g[g.season != 2021].reset_index(drop=True))(pd.read_parquet(W + f))
raw, adj, b10, b5 = wf(ld("games.parquet")), wf(ld("games_adj.parquet")), wf(ld("games_blend10.parquet")), wf(ld("games_blend.parquet"))
nb = ld("games_blend10.parquet")[["gameId", "h_n_prior", "a_n_prior"]]
base = b10.merge(nb, on="gameId").merge(raw[["gameId", "p"]].rename(columns={"p": "pr"}), on="gameId", how="left") \
          .merge(adj[["gameId", "p"]].rename(columns={"p": "pa"}), on="gameId", how="left")
est = (np.minimum(base.h_n_prior, base.a_n_prior) >= 5) & base.pr.notna()
hyb_r = base.assign(p=np.where(est, base.pr, base.p))
hyb_ra = base.assign(p=np.where(est & base.pa.notna(), (base.pr + base.pa.fillna(base.pr)) / 2, np.where(est, base.pr, base.p)))
ens = raw.merge(adj[["gameId", "p"]], on="gameId", suffixes=("", "_a")); ens["p"] = (ens.p + ens.p_a) / 2
V = {"raw": raw, "adjusted": adj, "raw+adj avg": ens, "blended K10": b10, "blended K5": b5, "hybrid raw": hyb_r, "hybrid raw+adj": hyb_ra}
def season_stats(d, th=1.0):
    d = d[d.p.notna() & (d.resid != 0) & (d.p.abs() >= th)]
    w = np.sign(d.p) == np.sign(d.resid)
    return d.assign(w=w).groupby("season").w.agg(["sum", "count"])
for th in (1.0, 2.0):
    S = {k: season_stats(v, th) for k, v in V.items()}
    seasons = sorted(set().union(*[s.index for s in S.values()]))
    tot = {k: (s["sum"].sum() / s["count"].sum()) for k, s in S.items()}
    print(f"\n=== {th:.0f}+ pt edge ===")
    for k in V: print(f"  {k:16s} {tot[k]*100:5.1f}% ({int(S[k]['count'].sum())})")
    W_, N_, picks = 0, 0, []
    for t in seasons:
        others = {k: (s.drop(t, errors="ignore")["sum"] * (100/110) - (s.drop(t, errors="ignore")["count"] - s.drop(t, errors="ignore")["sum"])).sum() for k, s in S.items()}
        best = max(others, key=others.get); picks.append(best)
        if t in S[best].index: W_ += S[best].loc[t, "sum"]; N_ += S[best].loc[t, "count"]
    print(f"  NESTED (variant chosen on other seasons by units, scored on held-out season): {W_/N_*100:.1f}% ({N_})  choices: {pd.Series(picks).value_counts().to_dict()}")
    print(f"  average of all 7 variants: {np.mean(list(tot.values()))*100:.1f}%   worst: {min(tot.values())*100:.1f}%")
