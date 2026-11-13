"""Broader test of "styles make fights": does the MATCHUP of styles beat the spread
beyond what each team's own profile (the Team Profile Model) already predicts?

Test A - archetypes: k-means style types (fit on training seasons only), symmetric
         type-vs-type matchup terms added to the profile model, walk-forward.
Test B - all cross-pairings: every offensive trait of one side x every defensive trait
         of the other (symmetric), ridge, walk-forward, several penalty strengths.
Both are judged on whether they IMPROVE the profile model out of sample.
"""
import itertools
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

sys.path.insert(0, str(Path(__file__).parent))
from analyze import MAIN, features, ridge_fit  # noqa: E402

warnings.filterwarnings("ignore")
G = pd.read_parquet(sys.argv[1] if len(sys.argv) > 1 else "/home/claude/cbb/work/games.parquet")
G = G[G.season != 2021].reset_index(drop=True)
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "/home/claude/cbb/work/results")
STY = ["pace", "o_3par", "o_ftr", "o_tov", "o_orb", "o_paint", "o_fb", "o_ast",
       "d_3par", "d_ftr", "d_tov", "d_orb", "d_paint", "d_fb", "d_ast", "d_blk", "d_stl"]
OFF = [s for s in STY if s.startswith("o_")]
DEF = [s for s in STY if s.startswith("d_")]
NAMES = {"pace": "tempo", "o_3par": "3PA volume", "o_ftr": "gets to line", "o_tov": "turnover-prone",
         "o_orb": "off. glass", "o_paint": "paint scoring", "o_fb": "transition O", "o_ast": "assist-heavy",
         "d_3par": "allows 3PA", "d_ftr": "fouls", "d_tov": "forces TOs", "d_orb": "allows O-boards",
         "d_paint": "allows paint", "d_fb": "allows transition", "d_ast": "allows assisted",
         "d_blk": "rim protection", "d_stl": "steals"}

X0 = features(G)
X0["spread"] = G.spread
BASE = [f"main_{m}" for m in MAIN] + ["neutral", "spread"]
H = G[[f"h_pre_{s}" for s in STY]].values
A = G[[f"a_pre_{s}" for s in STY]].values


def evaluate(preds, mask=None):
    ok = preds.notna() if mask is None else (preds.notna() & mask)
    y, p = G.resid[ok], preds[ok]
    res = {"oos_r2": 1 - ((y - p) ** 2).sum() / (y ** 2).sum()}
    for th in (1, 2):
        s = (p.abs() >= th) & (y != 0)
        res[f"bets_{th}"] = int(s.sum())
        res[f"win_{th}"] = float((np.sign(p[s]) == np.sign(y[s])).mean())
    return res


def walk(build, lam):
    """build(train_idx, test_idx) -> (Xtrain, Xtest) arrays."""
    preds = pd.Series(np.nan, index=G.index)
    for t in sorted(G.season.unique()):
        if t < 2017:
            continue
        tr, te = (G.season < t).values, (G.season == t).values
        Xtr, Xte = build(tr, te)
        mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
        b = ridge_fit((Xtr - mu) / sd, G.resid.values[tr], lam)
        preds[te] = b[0] + ((Xte - mu) / sd) @ b[1:]
    return preds


base_build = lambda tr, te: (X0.loc[tr, BASE].values, X0.loc[te, BASE].values)
p_base = walk(base_build, 500.0)
rows = [{"model": "Team Profile Model (baseline)", **evaluate(p_base)}]


# ---------------- Test A: archetypes ----------------------------------------------------
def arche_build(k):
    def build(tr, te):
        team_rows = np.vstack([H[tr], A[tr]])
        km = KMeans(n_clusters=k, n_init=10, random_state=0).fit(team_rows)
        lh, la = km.predict(H), km.predict(A)
        pairs = list(itertools.combinations(range(k), 2))
        M = np.zeros((len(G), len(pairs)))
        for j, (a, b) in enumerate(pairs):
            M[:, j] = ((lh == a) & (la == b)).astype(float) - ((lh == b) & (la == a)).astype(float)
        full = np.column_stack([X0[BASE].values, M])
        return full[tr], full[te]
    return build


for k in (4, 6, 8):
    for lam in (500.0, 5000.0):
        rows.append({"model": f"Profile + archetype matchups (k={k}, ridge {int(lam)})", **evaluate(walk(arche_build(k), lam))})

# ---------------- Test B: every offense x defense cross-pairing --------------------------
cross = {}
for o in OFF:
    for d in DEF:
        io, idd = STY.index(o), STY.index(d)
        cross[f"{o}|{d}"] = H[:, io] * A[:, idd] - A[:, io] * H[:, idd]
ip = STY.index("pace")
cross["tempo_gap_fav"] = np.abs(H[:, ip] - A[:, ip]) * np.sign(-G.spread.values)
cross["fav_faster"] = (H[:, ip] - A[:, ip]) * np.sign(-G.spread.values)
C = pd.DataFrame(cross)
cross_build = lambda tr, te: (np.column_stack([X0[BASE].values, C.values])[tr], np.column_stack([X0[BASE].values, C.values])[te])
for lam in (500.0, 5000.0, 20000.0):
    rows.append({"model": f"Profile + all {C.shape[1]} cross-pairings (ridge {int(lam)})", **evaluate(walk(cross_build, lam))})

res = pd.DataFrame(rows)
print(res.round(4).to_string(index=False))
res.to_csv(OUT / "style_matchup_walkforward.csv", index=False)

# ---------------- Descriptive: archetype matchup table (full sample) ----------------------
K = 6
km = KMeans(n_clusters=K, n_init=10, random_state=0).fit(np.vstack([H, A]))
cent = pd.DataFrame(km.cluster_centers_, columns=STY)
labels = []
for i in range(K):
    c = cent.loc[i].sort_values()
    hi = [NAMES[x] for x in c.index[::-1][:2]]
    lo = [NAMES[x] for x in c.index[:1]]
    labels.append(f"T{i+1}: +{hi[0]}, +{hi[1]}, -{lo[0]}")
lh, la = km.predict(H), km.predict(A)
# residual after the profile model (full-sample fit) so cells measure the matchup only
Xb = np.column_stack([np.ones(len(G)), X0[BASE].values])
bb, *_ = np.linalg.lstsq(Xb, G.resid.values, rcond=None)
adj = G.resid.values - Xb @ bb
cells = []
for a, b in itertools.combinations(range(K), 2):
    r = np.concatenate([adj[(lh == a) & (la == b)], -adj[(lh == b) & (la == a)]])
    raw = np.concatenate([G.resid.values[(lh == a) & (la == b)], -G.resid.values[(lh == b) & (la == a)]])
    seas = np.concatenate([G.season.values[(lh == a) & (la == b)], G.season.values[(lh == b) & (la == a)]])
    nz = raw != 0
    odd = r[(seas % 2 == 1)].mean() if (seas % 2 == 1).any() else np.nan
    even = r[(seas % 2 == 0)].mean() if (seas % 2 == 0).any() else np.nan
    cells.append({"type_A": labels[a], "type_B": labels[b], "games": len(r),
                  "A_cover_pct": (raw[nz] > 0).mean(), "A_edge_after_profile": r.mean(),
                  "t": r.mean() / (r.std() / np.sqrt(len(r))), "odd_seasons": odd, "even_seasons": even})
cells = pd.DataFrame(cells).sort_values("t", key=abs, ascending=False)
print("\nArchetypes (centroid traits, z):")
print(cent.round(2).assign(label=labels)[["label"]].to_string())
print(f"\nType-vs-type matchups ({len(cells)} pairs), edge in pts after the profile model; Bonferroni t* = {abs(np.percentile(np.random.default_rng(0).standard_normal(10**6), 100*(1-0.025/len(cells)))):.2f}")
print(cells.round(3).to_string(index=False))
print("split-half stability corr(odd, even seasons):", round(np.corrcoef(cells.odd_seasons, cells.even_seasons)[0, 1], 3))
cells.to_csv(OUT / "archetype_matchups.csv", index=False)
cent.assign(label=labels).to_csv(OUT / "archetype_centroids.csv")
