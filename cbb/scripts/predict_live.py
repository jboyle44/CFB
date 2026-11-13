"""Live CBB picks from the style-profile model (hybrid).

Hybrid rule (backtest 2017-2026: 54.1% at 1+ pt, 58.1% at 2+):
  - Early: if either team has fewer than 5 D1 games, use the BLENDED model
    (profiles blended toward last season, K=10).
  - Established: once both teams have 5+ games, use the UNBLENDED model
    (this season's games only).
Each model is trained on its own historical dataset. Output: cbb/live/picks.json

Usage: python predict_live.py [games_blend10.parquet] [games.parquet]
"""
import gzip
import json
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import build_dataset as bd  # noqa: E402
from analyze import MAIN, features, ridge_fit  # noqa: E402

K = 10.0
LAM = 500.0
SEASON = 2027
MIN_EST = 5
TRAIN_BLEND = Path(sys.argv[1] if len(sys.argv) > 1 else "/home/claude/cbb/work/games_blend10.parquet")
TRAIN_RAW = Path(sys.argv[2] if len(sys.argv) > 2 else "/home/claude/cbb/work/games.parquet")
RAW = Path("cbb/raw")
LIVE = json.load(open("cbb/live/live_raw.json"))
# label, display kind, group
TRAIT_META = {
    "pace": ("Tempo (possessions per game)", "num", "Tempo"),
    "o_3par": ("3-point attempt rate", "pct", "Offense"), "o_ftr": ("Free-throw rate (FTA/FGA)", "pct", "Offense"),
    "o_tov": ("Turnover rate", "pct", "Offense"), "o_orb": ("Offensive rebound %", "pct", "Offense"),
    "o_paint": ("Paint share of points", "pct", "Offense"), "o_fb": ("Transition share of points", "pct", "Offense"),
    "o_ast": ("Assist rate (assisted FGM)", "pct", "Offense"), "o_efg": ("eFG% (shooting results)", "pct", "Offense"),
    "d_3par": ("Opp. 3-point attempt rate allowed", "pct", "Defense"), "d_ftr": ("Opp. free-throw rate allowed", "pct", "Defense"),
    "d_tov": ("Turnovers forced (per poss.)", "pct", "Defense"), "d_orb": ("Opp. offensive rebound % allowed", "pct", "Defense"),
    "d_paint": ("Opp. paint share allowed", "pct", "Defense"), "d_fb": ("Opp. transition share allowed", "pct", "Defense"),
    "d_ast": ("Opp. assist rate allowed", "pct", "Defense"), "d_efg": ("Opp. eFG% allowed (shooting results)", "pct", "Defense"),
    "d_blk": ("Block rate (per opp. 2PA)", "pct", "Defense"), "d_stl": ("Steal rate (per poss.)", "pct", "Defense"),
}
LABELS = {
    "pace": ("plays faster", "plays slower"),
    "o_3par": ("takes more 3s", "takes fewer 3s"), "o_ftr": ("gets to the line more", "gets to the line less"),
    "o_tov": ("turns it over more", "protects the ball better"), "o_orb": ("crashes the offensive glass harder", "rebounds fewer of its misses"),
    "o_paint": ("scores more in the paint", "scores less in the paint"), "o_fb": ("runs more in transition", "runs less in transition"),
    "o_ast": ("moves the ball better (assist rate)", "assists less"), "o_efg": ("has shot better so far", "has shot worse so far"),
    "d_3par": ("allows more 3PA", "limits 3PA"), "d_ftr": ("fouls more", "fouls less"),
    "d_tov": ("forces more turnovers", "forces fewer turnovers"), "d_orb": ("gives up more offensive boards", "limits offensive boards"),
    "d_paint": ("gives up more paint points", "limits paint points"), "d_fb": ("gives up more transition", "limits transition"),
    "d_ast": ("allows more assisted looks", "limits assisted looks"), "d_efg": ("has seen opponents shoot better", "has seen opponents shoot worse"),
    "d_blk": ("protects the rim better", "protects the rim less"), "d_stl": ("gets more steals", "gets fewer steals"),
}
COLS = [f"main_{m}" for m in MAIN] + ["neutral", "spread"]


def history_scale(rows26, st26, prior25, k):
    """Std of season-2026 pre-game profile values (raw units), blended with weight k (0 = unblended)."""
    d = pd.concat([rows26[["teamId", "date", "gameId"]], st26], axis=1).sort_values(["teamId", "date", "gameId"])
    d = d.merge(prior25, on="teamId", how="left", suffixes=("", "_prior"))
    grp = d.groupby("teamId")
    n = grp.cumcount().values.astype(float)
    out = {}
    for c in bd.STYLE_COLS:
        pre = grp[c].transform(lambda x: x.shift(1).expanding().mean()).values
        if k > 0:
            pv = d[f"{c}_prior"].fillna(d[c].mean()).values
            vals = (n * np.nan_to_num(pre) + k * pv) / (n + k)
        else:
            vals = pre
        out[c] = np.nanstd(vals)
    return out


def team_profiles(live_rows, prior26, league26, sched, k):
    st = bd.per_game_style(live_rows)
    df = pd.concat([live_rows[["teamId", "team"]], st], axis=1)
    cur = df.groupby(["teamId", "team"])[bd.STYLE_COLS].mean().reset_index()
    cur["n"] = df.groupby(["teamId", "team"]).size().values
    cur = cur.merge(prior26, on="teamId", how="left", suffixes=("", "_prior"))
    for c in bd.STYLE_COLS:
        pv = cur[f"{c}_prior"].fillna(league26[c])
        cur[c] = (cur.n * cur[c].fillna(0) + k * pv) / (cur.n + k) if k > 0 else cur[c]
    known = set(cur.teamId)
    extra = []
    teams = pd.concat([sched[["homeTeamId", "homeTeam"]].set_axis(["teamId", "team"], axis=1),
                       sched[["awayTeamId", "awayTeam"]].set_axis(["teamId", "team"], axis=1)]).drop_duplicates()
    for tid, name in teams.values:
        if tid not in known:   # no D1 games yet: last season only
            p = prior26[prior26.teamId == tid]
            row = {"teamId": tid, "team": name, "n": 0}
            row.update({c: (p[c].iloc[0] if len(p) else league26[c]) for c in bd.STYLE_COLS})
            extra.append(row)
    return pd.concat([cur, pd.DataFrame(extra)], ignore_index=True)


def zscore(prof, scale):
    center = prof[prof.n > 0][bd.STYLE_COLS].mean() if (prof.n > 0).any() else prof[bd.STYLE_COLS].mean()
    z = prof[["teamId", "team", "n"]].copy()
    for c in bd.STYLE_COLS:
        z[c] = (prof[c] - center[c]) / scale[c]
    return z.set_index("teamId"), prof.set_index("teamId")


def train(path):
    g = pd.read_parquet(path)
    g = g[g.season != 2021].reset_index(drop=True)
    X = features(g).fillna(0)
    X["spread"] = g.spread
    Xt = X[COLS].values
    mu, sd = Xt.mean(0), Xt.std(0) + 1e-9
    b = ridge_fit((Xt - mu) / sd, g.resid.values, LAM)
    return {"g": g, "X": X, "mu": mu, "sd": sd, "b": b}


def main():
    bd.RAW = RAW
    rows26 = bd.box_rows(2026)
    rows26 = rows26[rows26.d1 & rows26.opp_d1].copy()
    st26 = bd.per_game_style(rows26)
    bd.STYLE_COLS = list(st26.columns)
    rows25 = bd.box_rows(2025)
    rows25 = rows25[rows25.d1 & rows25.opp_d1]
    prior25 = pd.concat([rows25[["teamId"]], bd.per_game_style(rows25)], axis=1).groupby("teamId").mean().reset_index()
    scale_b = history_scale(rows26, st26, prior25, K)
    scale_r = history_scale(rows26, st26, prior25, 0)

    tmp = Path(tempfile.mkdtemp())
    with gzip.open(tmp / f"team_box_{SEASON}.json.gz", "wt") as f:
        json.dump(LIVE["team_box"], f)
    bd.RAW = tmp
    live_rows = bd.box_rows(SEASON)
    live_rows = live_rows[live_rows.d1 & live_rows.opp_d1].copy()
    prior26 = pd.concat([rows26[["teamId"]], st26], axis=1).groupby("teamId").mean().reset_index()
    league26 = st26.mean()
    sched = pd.DataFrame(LIVE["schedule"])
    sched = sched[sched.homeConference.notna() & sched.awayConference.notna() & (sched.status == "scheduled")]
    zb, rb = zscore(team_profiles(live_rows, prior26, league26, sched, K), scale_b)
    zr, rr = zscore(team_profiles(live_rows, prior26, league26, sched, 0), scale_r)

    line = {}
    for g in LIVE["lines"]:
        book = {x["provider"]: x for x in g["lines"] if x.get("spread") is not None}
        vals = [float(x["spread"]) for x in book.values()]
        if len(vals) >= 2 and max(vals) - min(vals) >= bd.LINE_DISAGREE:
            continue   # books disagree badly: treat as no posted line (never graded)
        pick = next((p for p in bd.PROVIDER_RANK if p in book), next(iter(book), None))
        if pick:
            line[g["gameId"]] = (float(book[pick]["spread"]), pick)

    MB, MR = train(TRAIN_BLEND), train(TRAIN_RAW)
    # projected line for unposted games: closing spread ~ blended profiles
    gb, Xb = MB["g"], MB["X"]
    A = np.column_stack([np.ones(len(gb)), Xb[COLS[:-1]].values])
    w, *_ = np.linalg.lstsq(A, gb.spread.values, rcond=None)
    print(f"projected-line model MAE {np.abs(gb.spread - A @ w).mean():.2f}")

    out = []
    for _, s in sched.iterrows():
        n_h, n_a = int(zb.loc[s.homeTeamId].n), int(zb.loc[s.awayTeamId].n)
        est = n_h >= MIN_EST and n_a >= MIN_EST
        Z, R, M = (zr, rr, MR) if est else (zb, rb, MB)
        h, a = Z.loc[s.homeTeamId], Z.loc[s.awayTeamId]
        x = {f"main_{m}": h[m] - a[m] for m in MAIN}
        x["neutral"] = float(bool(s.neutralSite))
        xb = {f"main_{m}": zb.loc[s.homeTeamId][m] - zb.loc[s.awayTeamId][m] for m in MAIN}
        xb["neutral"] = x["neutral"]
        proj = float(np.round((np.r_[1.0, [xb[c] for c in COLS[:-1]]] @ w) * 2) / 2)
        spread, book = line.get(s.id, (np.nan, None))
        posted = not np.isnan(spread)
        x["spread"] = spread if posted else proj
        zv = (np.array([x[c] for c in COLS]) - M["mu"]) / M["sd"]
        contrib = zv * M["b"][1:]
        lean = M["b"][0] + contrib.sum()
        side_home = lean > 0
        sgn = 1 if side_home else -1
        pick = s.homeTeam if side_home else s.awayTeam
        cs = contrib[:len(MAIN)] * sgn
        reasons = []
        for j in np.argsort(-cs)[:3]:
            if cs[j] <= 0.05:
                continue
            m = MAIN[j]
            better = s.homeTeam if h[m] - a[m] > 0 else s.awayTeam
            reasons.append({"text": f"{better} {LABELS[m][0]}", "pts": round(float(cs[j]), 2)})
        traits = []
        for j, m in enumerate(MAIN):
            lab, kind, grp = TRAIT_META[m]
            f = (lambda v: round(float(v) * 100, 1)) if kind == "pct" else (lambda v: round(float(v), 1))
            traits.append({"key": m, "label": lab, "group": grp, "kind": kind, "away": f(R.loc[s.awayTeamId][m]),
                           "home": f(R.loc[s.homeTeamId][m]), "pts": round(float(contrib[j]) * sgn, 2)})
        terms = [{"label": "Underdog / favorite adjustment", "pts": round(float(contrib[COLS.index("spread")]) * sgn, 2)},
                 {"label": "Neutral-site adjustment", "pts": round(float(contrib[COLS.index("neutral")]) * sgn, 2)},
                 {"label": "Baseline (home/away)", "pts": round(float(M["b"][0]) * sgn, 2)}]
        ref = x["spread"]
        sp = ref if side_home else -ref
        fav_home = ref < 0
        pace_gap = (zb.loc[s.homeTeamId].pace - zb.loc[s.awayTeamId].pace) * (1 if fav_home else -1)
        out.append({
            "gameId": int(s.id), "date": s.startDate, "home": s.homeTeam, "away": s.awayTeam, "neutral": bool(s.neutralSite),
            "venue": s.venue, "spread_home": float(spread) if posted else None, "book": book, "proj_spread_home": proj,
            "pick": pick, "pick_line": f"{pick} {sp:+.1f}".replace("+0.0", " PK"), "edge": round(abs(float(lean)), 2),
            "tier": "strong" if abs(lean) >= 2 else "play" if abs(lean) >= 1 else "lean",
            "tempo_flag": bool(pace_gap > 1 and abs(ref) >= 8.5), "line_status": "posted" if posted else "projected",
            "model": "established" if est else "early", "games_played": [n_a, n_h], "reasons": reasons,
            "traits": traits, "terms": terms,
        })

    def wts(M):
        r = [{"key": m, "label": TRAIT_META[m][0], "group": TRAIT_META[m][2], "pts_per_sd": round(float(M["b"][1 + j]), 3)} for j, m in enumerate(MAIN)]
        r.append({"key": "spread", "label": "Underdog adjustment (per SD of spread)", "group": "Market", "pts_per_sd": round(float(M["b"][1 + COLS.index("spread")]), 3)})
        return r
    json.dump({"generated": LIVE["fetched_at"], "games": out, "weights": wts(MB), "weights_established": wts(MR)},
              open("cbb/live/picks.json", "w"), indent=1)
    df = pd.DataFrame(out)
    print(len(df), "games;", int(df.spread_home.notna().sum()), "with lines;", int((df.model == "established").sum()), "on the established model")
    print(df.groupby(["tier", "line_status"]).size().to_string())
    shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
