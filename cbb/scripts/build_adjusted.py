"""Opponent-adjusted style profiles (KenPom-style iterative adjustment), no lookahead.

For each paired metric X (team offense o_X vs what a defense allows d_X):
    O[t] = mean over t's games of ( o_X  - (D[opp] - L) )
    D[t] = mean over t's games of ( d_X  - (O[opp] - L) )
iterated to convergence, where L = league average. Pace: P[t] = mean(pace - (P[opp] - L)).
Solved from scratch before every game date using only earlier games, so each game's
profile reflects exactly what was knowable at tip. Blocks/steals have no clean offense
pair and stay raw. Output has the same columns as build_dataset.py (pre_* z-scored).
"""
import gzip
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import build_dataset as bd  # noqa: E402

RAW = Path(sys.argv[1] if len(sys.argv) > 1 else "cbb/raw")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "/home/claude/cbb/work/games_adj.parquet")
MIN_PRIOR = int(os.environ.get("MIN_PRIOR", "5"))
PAIRS = ["3par", "ftr", "tov", "orb", "paint", "fb", "ast", "efg"]
ITERS = 12


def solve(ti, si, nteams, vals_o, vals_d, pace):
    """Return adjusted O (nteams x P), D (nteams x P), pace (nteams)."""
    cnt = np.bincount(ti, minlength=nteams).astype(float)
    cnt[cnt == 0] = np.nan
    L = vals_o.mean(0)
    O = np.vstack([np.bincount(ti, vals_o[:, j], nteams) for j in range(len(L))]).T / cnt[:, None]
    D = np.vstack([np.bincount(ti, vals_d[:, j], nteams) for j in range(len(L))]).T / cnt[:, None]
    Lp = pace.mean()
    Pc = np.bincount(ti, pace, nteams) / cnt
    for _ in range(ITERS):
        Dn = np.nan_to_num(D[si], nan=0) - np.where(np.isnan(D[si]), 0, L)   # opp defense deviation
        On = np.nan_to_num(O[si], nan=0) - np.where(np.isnan(O[si]), 0, L)
        O = np.vstack([np.bincount(ti, vals_o[:, j] - Dn[:, j], nteams) for j in range(len(L))]).T / cnt[:, None]
        D = np.vstack([np.bincount(ti, vals_d[:, j] - On[:, j], nteams) for j in range(len(L))]).T / cnt[:, None]
        Pn = np.nan_to_num(Pc[si] - Lp, nan=0)
        Pc = np.bincount(ti, pace - Pn, nteams) / cnt
    return O, D, Pc


def season_frame(season):
    bd.RAW = RAW
    df = bd.box_rows(season)
    df = df[df.d1 & df.opp_d1].copy()
    df["date"] = pd.to_datetime(df.date, utc=True)
    st = bd.per_game_style(df)
    df = pd.concat([df[["gameId", "season", "date", "teamId", "oppId"]], st], axis=1).dropna(subset=list(st.columns))
    df = df.sort_values(["date", "gameId"]).reset_index(drop=True)
    ids = pd.Index(sorted(set(df.teamId) | set(df.oppId)))
    df["ti"], df["si"] = ids.get_indexer(df.teamId), ids.get_indexer(df.oppId)
    day = df.date.dt.tz_convert("America/New_York").dt.date
    ocols = [f"o_{p}" for p in PAIRS]
    dcols = [f"d_{p}" for p in PAIRS]
    raw_extra = ["d_blk", "d_stl"]
    out = {c: np.full(len(df), np.nan) for c in ["pace"] + ocols + dcols + raw_extra}
    for d in sorted(day.unique()):
        before = (day < d).values
        today = (day == d).values
        if before.sum() < 200:
            continue
        sub = df[before]
        O, D, P = solve(sub.ti.values, sub.si.values, len(ids), sub[ocols].values, sub[dcols].values, sub.pace.values)
        t_idx = df.ti.values[today]
        for j, p in enumerate(PAIRS):
            out[f"o_{p}"][today] = O[t_idx, j]
            out[f"d_{p}"][today] = D[t_idx, j]
        out["pace"][today] = P[t_idx]
        for c in raw_extra:   # season-to-date raw mean
            m = sub.groupby("ti")[c].mean()
            out[c][today] = m.reindex(t_idx).values
    pre = pd.DataFrame({f"pre_{c}": v for c, v in out.items()})
    df = pd.concat([df[["gameId", "season", "date", "teamId"]], pre], axis=1)
    df["n_prior"] = df.groupby("teamId").cumcount()
    return df


def main():
    frames = [season_frame(s) for s in bd.SEASONS]
    tg = pd.concat(frames, ignore_index=True)
    pre_cols = [c for c in tg.columns if c.startswith("pre_")]
    tg[pre_cols] = tg.groupby("season")[pre_cols].transform(lambda x: (x - x.mean()) / x.std())
    # reuse the raw dataset's game rows (lines, scores, neutral) and swap in adjusted profiles
    base = pd.read_parquet("/home/claude/cbb/work/games_all.parquet")
    keep = ["gameId", "teamId", "n_prior"] + pre_cols
    h = tg[keep].add_prefix("h_").rename(columns={"h_gameId": "gameId", "h_teamId": "homeId"})
    a = tg[keep].add_prefix("a_").rename(columns={"a_gameId": "gameId", "a_teamId": "awayId"})
    drop = [c for c in base.columns if c.startswith(("h_pre_", "a_pre_", "h_n_prior", "a_n_prior"))]
    g = base.drop(columns=drop).merge(h, on=["gameId", "homeId"]).merge(a, on=["gameId", "awayId"])
    g = g[(g.h_n_prior >= MIN_PRIOR) & (g.a_n_prior >= MIN_PRIOR)].dropna(subset=[c for c in g.columns if c.startswith(("h_pre_", "a_pre_"))])
    g.to_parquet(OUT, index=False)
    print("adjusted games:", len(g))


if __name__ == "__main__":
    main()
