"""Audit test: does the LIVE feature pipeline reproduce the BACKTEST?

Replays predict_live.py's profile code "as of" past dates in the 2025-26 season
(using only box scores before each date, last season's means as the prior, and
history-based scaling exactly as live does), scores those games with models trained
only on seasons before 2026, and compares to the backtest's walk-forward predictions
for the same games.
"""
import contextlib
import io
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent))
import build_dataset as bd  # noqa: E402
from analyze import MAIN, features, ridge_fit  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    sys.argv = ["x"]
    import make_trends as MT  # backtest hybrid predictions (MT.g: gameId, p, p_blend, p_raw)
    import predict_live as PL  # live helper functions

S = 2026
bd.RAW = Path("cbb/raw")
COLS = PL.COLS


def train(path):
    g = pd.read_parquet(path)
    g = g[(g.season != 2021) & (g.season < S)].reset_index(drop=True)
    X = features(g).fillna(0)
    X["spread"] = g.spread
    Xt = X[COLS].values
    mu, sd = Xt.mean(0), Xt.std(0) + 1e-9
    return {"mu": mu, "sd": sd, "b": ridge_fit((Xt - mu) / sd, g.resid.values, 500.0)}


MB, MR = train("/home/claude/cbb/work/games_blend10.parquet"), train("/home/claude/cbb/work/games.parquet")

prev = bd.box_rows(S - 1)
prev = prev[prev.d1 & prev.opp_d1].copy()
st_prev = bd.per_game_style(prev)
bd.STYLE_COLS = list(st_prev.columns)
prev2 = bd.box_rows(S - 2)
prev2 = prev2[prev2.d1 & prev2.opp_d1]
prior_prev2 = pd.concat([prev2[["teamId"]], bd.per_game_style(prev2)], axis=1).groupby("teamId").mean().reset_index()
scale_b = PL.history_scale(prev, st_prev, prior_prev2, PL.K)
scale_r = PL.history_scale(prev, st_prev, prior_prev2, 0)
prior_prev = pd.concat([prev[["teamId"]], st_prev], axis=1).groupby("teamId").mean().reset_index()
league_prev = st_prev.mean()

cur = bd.box_rows(S)
cur = cur[cur.d1 & cur.opp_d1].copy()
cur["dt"] = pd.to_datetime(cur.date, utc=True).dt.tz_convert("America/New_York")
bt = pd.read_parquet("/home/claude/cbb/work/games_all.parquet")
bt = bt[bt.season == S]
bt["et_day"] = bt.date.dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
neutral = {r["gameId"]: bool(r.get("neutralSite")) for r in
           __import__("json").load(__import__("gzip").open(bd.RAW / f"team_box_{S}.json.gz"))}

rows = []
for day in ["2025-11-14", "2025-11-21", "2025-12-06", "2025-12-20", "2026-01-10", "2026-01-24", "2026-02-07", "2026-02-21", "2026-03-04"]:
    cutoff = pd.Timestamp(day, tz="America/New_York")
    live_rows = cur[cur.dt < cutoff].drop(columns=["dt"]).copy()
    games = bt[bt.et_day == day]
    sched = games.rename(columns={"gameId": "id", "home": "homeTeam", "away": "awayTeam"})[["id", "homeId", "awayId", "homeTeam", "awayTeam"]]
    sched = sched.rename(columns={"homeId": "homeTeamId", "awayId": "awayTeamId"})
    zb, _ = PL.zscore(PL.team_profiles(live_rows, prior_prev, league_prev, sched, PL.K), scale_b)
    zr, _ = PL.zscore(PL.team_profiles(live_rows, prior_prev, league_prev, sched, 0), scale_r)
    for _, gm in games.iterrows():
        try:
            nh, na = int(zb.loc[gm.homeId].n), int(zb.loc[gm.awayId].n)
        except KeyError:
            continue
        est = nh >= 5 and na >= 5
        Z, M = (zr, MR) if est else (zb, MB)
        x = [Z.loc[gm.homeId][m] - Z.loc[gm.awayId][m] for m in MAIN] + [float(neutral.get(gm.gameId, False)), gm.spread]
        p_live = M["b"][0] + ((np.array(x) - M["mu"]) / M["sd"]) @ M["b"][1:]
        rows.append({"day": day, "gameId": gm.gameId, "est": est, "p_live": p_live, "resid": gm.resid})

L = pd.DataFrame(rows).merge(MT.g[["gameId", "p"]], on="gameId", how="inner")
L = L[L.resid != 0]
print(f"{len(L)} games replayed across {L.day.nunique()} dates ({int(L.est.sum())} on the established model)")
print(f"correlation live vs backtest prediction: {np.corrcoef(L.p_live, L.p)[0, 1]:.3f}")
print(f"same side: {(np.sign(L.p_live) == np.sign(L.p)).mean() * 100:.1f}%   mean |diff|: {(L.p_live - L.p).abs().mean():.2f} pts   "
      f"mean |edge| live {L.p_live.abs().mean():.2f} vs backtest {L.p.abs().mean():.2f}")
for th in (1, 2):
    a = L[L.p_live.abs() >= th]
    b = L[L.p.abs() >= th]
    agree = len(set(a.gameId) & set(b.gameId)) / max(1, len(set(a.gameId) | set(b.gameId)))
    print(f"{th}+ pt bets: live {len(a)} ({(np.sign(a.p_live) == np.sign(a.resid)).mean() * 100:.1f}%) | backtest {len(b)} "
          f"({(np.sign(b.p) == np.sign(b.resid)).mean() * 100:.1f}%) | overlap {agree * 100:.0f}%")
for e, d in L.groupby("est"):
    print(f"  {'established' if e else 'early'}: n={len(d)} corr {np.corrcoef(d.p_live, d.p)[0, 1]:.3f}, "
          f"same side {(np.sign(d.p_live) == np.sign(d.p)).mean() * 100:.1f}%, mean|edge| live {d.p_live.abs().mean():.2f} vs bt {d.p.abs().mean():.2f}")
