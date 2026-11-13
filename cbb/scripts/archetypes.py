"""Archetype matchup test ("styles make fights", Joe's framing).

1. Archetypes = k-means on team-season STYLE profiles (no efficiency / shooting %).
   Fit on training seasons only when validating; games are assigned by each team's
   PRE-GAME profile, so nothing from the future leaks in.
2. Matchup grid = how often archetype A covers vs archetype B. The spread is the
   talent adjustment. Also shown net of the Team Profile Model.
3. Validation = odd/even season stability + walk-forward betting of matchup cells.
"""
import itertools
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

sys.path.insert(0, str(Path(__file__).parent))
from analyze import MAIN, features, ridge_fit  # noqa: E402

warnings.filterwarnings("ignore")
G = pd.read_parquet(sys.argv[1] if len(sys.argv) > 1 else "/home/claude/cbb/work/games.parquet")
G = G[G.season != 2021].reset_index(drop=True)
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "/home/claude/cbb/work/results")
K = int(sys.argv[3]) if len(sys.argv) > 3 else 0
STY = ["pace", "o_3par", "o_ftr", "o_tov", "o_orb", "o_paint", "o_fb", "o_ast",
       "d_3par", "d_ftr", "d_tov", "d_orb", "d_paint", "d_fb", "d_ast", "d_blk", "d_stl"]
NAMES = {"pace": ("fast", "slow"), "o_3par": ("3PT-heavy", "few 3s"), "o_ftr": ("gets to line", "rarely FTs"),
         "o_tov": ("careless", "secure ball"), "o_orb": ("crashes O-glass", "gets back"),
         "o_paint": ("paint-scoring", "perimeter-scoring"), "o_fb": ("runs", "half-court"),
         "o_ast": ("ball-movement", "isolation"), "d_3par": ("concedes 3PA", "runs off 3s"),
         "d_ftr": ("fouls", "no-foul D"), "d_tov": ("forces TOs", "passive D"),
         "d_orb": ("weak D-glass", "strong D-glass"), "d_paint": ("soft paint D", "packs paint"),
         "d_fb": ("allows breaks", "transition D"), "d_ast": ("allows ball movement", "denies passing"),
         "d_blk": ("rim protector", "no rim protection"), "d_stl": ("gambles for steals", "no steals")}

H = G[[f"h_pre_{s}" for s in STY]].values
A = G[[f"a_pre_{s}" for s in STY]].values
X0 = features(G)
X0["spread"] = G.spread
BASE = [f"main_{m}" for m in MAIN] + ["neutral", "spread"]


def season_rows(mask):
    """Team-season profile = the team's last pre-game profile of the season (5+ games)."""
    h = G.loc[mask, ["season", "homeId", "date"]].assign(side="h").rename(columns={"homeId": "tid"})
    a = G.loc[mask, ["season", "awayId", "date"]].assign(side="a").rename(columns={"awayId": "tid"})
    h[STY] = H[mask.values]
    a[STY] = A[mask.values]
    allr = pd.concat([h, a]).sort_values("date")
    return allr.groupby(["season", "tid"])[STY].last().values


def label(c):
    order = np.argsort(-np.abs(c))[:3]
    return " / ".join(NAMES[STY[j]][0 if c[j] > 0 else 1] for j in order)


# ---- choose k ------------------------------------------------------------------------
allseason = season_rows(pd.Series(True, index=G.index))
if not K:
    sil = {}
    for k in range(4, 11):
        km = KMeans(n_clusters=k, n_init=20, random_state=0).fit(allseason)
        sil[k] = silhouette_score(allseason, km.labels_, sample_size=3000, random_state=0)
    print("silhouette by k:", {k: round(v, 3) for k, v in sil.items()})
    K = 6
km = KMeans(n_clusters=K, n_init=20, random_state=0).fit(allseason)
cent = km.cluster_centers_
labels = [f"A{i+1} {label(cent[i])}" for i in range(K)]
sizes = np.bincount(km.labels_, minlength=K)
lh, la = km.predict(H), km.predict(A)
print(f"\n{K} archetypes (team-seasons per type):")
for i in range(K):
    print(f"  {labels[i]}  ({sizes[i]} team-seasons, {((lh == i).sum() + (la == i).sum())} team-games)")

# ---- matchup grid ------------------------------------------------------------------------
Xb = np.column_stack([np.ones(len(G)), X0[BASE].values])
bb, *_ = np.linalg.lstsq(Xb, G.resid.values, rcond=None)
net = G.resid.values - Xb @ bb
cells = []
for a, b in itertools.combinations(range(K), 2):
    m1, m2 = (lh == a) & (la == b), (lh == b) & (la == a)
    raw = np.concatenate([G.resid.values[m1], -G.resid.values[m2]])
    adj = np.concatenate([net[m1], -net[m2]])
    seas = np.concatenate([G.season.values[m1], G.season.values[m2]])
    nz = raw != 0
    n = int(nz.sum())
    cov = (raw[nz] > 0).mean()
    cells.append({"A": labels[a], "B": labels[b], "games": n, "A_cover_pct": cov,
                  "z_cover": (cov - 0.5) / np.sqrt(0.25 / n), "A_pts_vs_spread": raw.mean(),
                  "A_pts_net_profile": adj.mean(), "t_net": adj.mean() / (adj.std() / np.sqrt(len(adj))),
                  "odd_cover": (raw[nz & (seas % 2 == 1)] > 0).mean(), "even_cover": (raw[nz & (seas % 2 == 0)] > 0).mean()})
cells = pd.DataFrame(cells).sort_values("z_cover", key=abs, ascending=False)
tcrit = 2.0 + 0.0  # reported alongside Bonferroni below
bonf = float(pd.Series(np.random.default_rng(0).standard_normal(2_000_000)).abs().quantile(1 - 0.05 / len(cells)))
print(f"\nMatchup grid: {len(cells)} pairs. Bonferroni |z| needed: {bonf:.2f}")
print(cells.round(3).to_string(index=False))
big = cells[cells.games >= 300]
print("odd/even season stability (cells with 300+ games):",
      round(np.corrcoef(big.odd_cover, big.even_cover)[0, 1], 3), f"over {len(big)} cells")


# ---- walk-forward: learn cell effects from past seasons, bet them next season ----------
def walk_cells(shrink=200, th=0.53, net_of_profile=False):
    bets = []
    for t in sorted(G.season.unique()):
        if t < 2017:
            continue
        tr, te = (G.season < t).values, (G.season == t).values
        kmt = KMeans(n_clusters=K, n_init=10, random_state=0).fit(season_rows(pd.Series(tr, index=G.index)))
        h, a = kmt.predict(H), kmt.predict(A)
        target = G.resid.values.copy()
        if net_of_profile:
            Xtr = X0.loc[tr, BASE].values
            mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
            b = ridge_fit((Xtr - mu) / sd, target[tr], 500.0)
            target = target - (b[0] + ((X0[BASE].values - mu) / sd) @ b[1:])
        cov = {}
        for x, y in itertools.permutations(range(K), 2):
            r = np.concatenate([G.resid.values[tr & (h == x) & (a == y)], -G.resid.values[tr & (h == y) & (a == x)]])
            r = r[r != 0]
            cov[(x, y)] = (np.sum(r > 0) + 0.5 * shrink) / (len(r) + shrink)   # shrunk toward 50%
        for i in np.where(te & (h != a))[0]:
            p = cov[(h[i], a[i])]                     # prob home-archetype covers
            if p >= th or p <= 1 - th:
                if G.resid.values[i] == 0:
                    continue
                win = (G.resid.values[i] > 0) == (p >= th)
                bets.append({"season": t, "win": win})
    b = pd.DataFrame(bets)
    return (len(b), b.win.mean() if len(b) else np.nan,
            b.groupby("season").win.mean().round(3).to_dict() if len(b) else {})


print("\nWalk-forward: bet the archetype-side whenever its past cover rate (shrunk) clears the threshold")
for th in (0.51, 0.52, 0.53):
    n, w, by = walk_cells(th=th)
    print(f"  threshold {th:.2f}: {n} bets, {w:.4f} win  by season {by}")

cells.to_csv(OUT / f"archetype_grid_k{K}.csv", index=False)
pd.DataFrame(cent, columns=STY).assign(label=labels, team_seasons=sizes).to_csv(OUT / f"archetype_centroids_k{K}.csv", index=False)
