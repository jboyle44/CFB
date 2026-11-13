"""Audit test: leakage canary and lag test on the unblended model.

1. Canary: add the game's OWN eFG% difference (a post-game stat) as a feature. A
   correctly built walk-forward must turn that into a huge edge, proving the harness
   would expose leakage if it existed.
2. Lag: rebuild every pre-game profile using only games played 7+ days before tip.
   A real edge should mostly survive; a leak through same-day/adjacent games would vanish.
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import build_dataset as bd  # noqa: E402
from analyze import MAIN, features, ridge_fit  # noqa: E402

warnings.filterwarnings("ignore")
bd.RAW = Path("cbb/raw")
SEASONS = [s for s in range(2014, 2027) if s != 2021]
base = pd.read_parquet("/home/claude/cbb/work/games.parquet")
base = base[base.season != 2021].reset_index(drop=True)


def team_games(season):
    df = bd.box_rows(season)
    df = df[df.d1 & df.opp_d1].copy()
    df["date"] = pd.to_datetime(df.date, utc=True)
    st = bd.per_game_style(df)
    bd.STYLE = list(st.columns)
    return pd.concat([df[["gameId", "season", "date", "teamId"]], st], axis=1)


def lagged_profiles(tg, days):
    """Mean of each style metric over the team's games played >= `days` days before this game."""
    cols = bd.STYLE
    out = []
    for (tid, _s), d in tg.sort_values("date").groupby(["teamId", "season"]):
        d = d.reset_index(drop=True)
        t = d.date.values
        csum = np.vstack([np.zeros(len(cols)), np.nancumsum(d[cols].values, axis=0)])
        ccnt = np.vstack([np.zeros(len(cols)), np.cumsum(~np.isnan(d[cols].values), axis=0)])
        cut = np.searchsorted(t, t - np.timedelta64(days, "D"), side="right")
        with np.errstate(invalid="ignore", divide="ignore"):
            m = csum[cut] / ccnt[cut]
        r = pd.DataFrame(m, columns=[f"pre_{c}" for c in cols])
        r["gameId"], r["teamId"], r["season"], r["n_lag"] = d.gameId.values, tid, d.season.values, cut
        out.append(r)
    return pd.concat(out, ignore_index=True)


def walk(g, extra=None, lam=500.0):
    X = features(g).fillna(0)
    X["spread"] = g.spread
    cols = [f"main_{m}" for m in MAIN] + ["neutral", "spread"]
    if extra is not None:
        X["canary"] = extra
        cols = cols + ["canary"]
    p = pd.Series(np.nan, index=g.index)
    for t in sorted(g.season.unique()):
        if t < 2017:
            continue
        tr, te = (g.season < t).values, (g.season == t).values
        Xt = X.loc[tr, cols].values
        mu, sd = Xt.mean(0), Xt.std(0) + 1e-9
        b = ridge_fit((Xt - mu) / sd, g.resid.values[tr], lam)
        p[te] = b[0] + ((X.loc[te, cols].values - mu) / sd) @ b[1:]
    return p


def score(g, p, label):
    out = []
    for th in (1, 2):
        s = p.notna() & (p.abs() >= th) & (g.resid != 0)
        out.append(f"{th}+: {(np.sign(p[s]) == np.sign(g.resid[s])).mean() * 100:.1f}% ({int(s.sum())})")
    print(f"{label:58s} " + " | ".join(out))


tgs = pd.concat([team_games(s) for s in SEASONS], ignore_index=True)

# baseline
score(base, walk(base), "Baseline unblended model")

# canary: the game's own eFG% (home minus away), known only after the game
own = tgs.set_index(["gameId", "teamId"]).o_efg
h_own = base.set_index(["gameId", "homeId"]).index.map(own.to_dict().get)
a_own = base.set_index(["gameId", "awayId"]).index.map(own.to_dict().get)
canary = pd.Series(np.array(h_own, float) - np.array(a_own, float), index=base.index).fillna(0)
score(base, walk(base, extra=canary), "Canary: + the game's own eFG% (post-game, should explode)")

# lag test: profiles from games 7+ days before tip, same games, same z-scoring
for days in (1, 7):
    lp = lagged_profiles(tgs, days)
    pc = [c for c in lp.columns if c.startswith("pre_")]
    lp[pc] = lp.groupby("season")[pc].transform(lambda x: (x - x.mean()) / x.std())
    h = lp.rename(columns={c: "h_" + c for c in pc}).rename(columns={"teamId": "homeId", "n_lag": "h_lag"}).drop(columns="season")
    a = lp.rename(columns={c: "a_" + c for c in pc}).rename(columns={"teamId": "awayId", "n_lag": "a_lag"}).drop(columns="season")
    keep = [c for c in base.columns if not c.startswith(("h_pre_", "a_pre_"))]
    g2 = base[keep].merge(h, on=["gameId", "homeId"]).merge(a, on=["gameId", "awayId"])
    g2 = g2[(g2.h_lag >= 3) & (g2.a_lag >= 3)].dropna(subset=[c for c in g2.columns if c.startswith(("h_pre_", "a_pre_"))]).reset_index(drop=True)
    score(g2, walk(g2), f"Profiles from games {days}+ days before tip ({len(g2)} games)")
