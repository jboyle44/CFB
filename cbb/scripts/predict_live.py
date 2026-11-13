"""Live CBB picks from the style-profile model.

Trains the ridge model on all historical games (early-season profiles blended
toward last season, K=10, the variant validated on early-season games), builds
current team profiles from this season's games blended with last season, and
scores every upcoming D1-vs-D1 game. Output: cbb/live/picks.json
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
TRAIN = Path(sys.argv[1] if len(sys.argv) > 1 else "/home/claude/cbb/work/games_blend10.parquet")
RAW = Path("cbb/raw")
LIVE = json.load(open("cbb/live/live_raw.json"))
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


def team_profiles(season_rows, prior_means, league_prior):
    st = bd.per_game_style(season_rows)
    df = pd.concat([season_rows[["teamId", "team"]], st], axis=1)
    cur = df.groupby(["teamId", "team"])[bd.STYLE_COLS].mean().reset_index()
    cur["n"] = df.groupby(["teamId", "team"]).size().values
    cur = cur.merge(prior_means, on="teamId", how="left", suffixes=("", "_prior"))
    for c in bd.STYLE_COLS:
        pv = cur[f"{c}_prior"].fillna(league_prior[c])
        cur[c] = (cur.n * cur[c].fillna(0) + K * pv) / (cur.n + K)
    return cur


def main():
    # --- historical scale: season-2026 blended pre-game values (raw units) ----------------
    bd.RAW = RAW
    rows26 = bd.box_rows(2026)
    rows26 = rows26[rows26.d1 & rows26.opp_d1].copy()
    st26 = bd.per_game_style(rows26)
    bd.STYLE_COLS = list(st26.columns)
    rows25 = bd.box_rows(2025)
    rows25 = rows25[rows25.d1 & rows25.opp_d1]
    prior25 = pd.concat([rows25[["teamId"]], bd.per_game_style(rows25)], axis=1).groupby("teamId").mean().reset_index()
    d26 = pd.concat([rows26[["teamId", "date", "gameId"]], st26], axis=1).sort_values(["teamId", "date", "gameId"])
    d26 = d26.merge(prior25, on="teamId", how="left", suffixes=("", "_prior"))
    grp = d26.groupby("teamId")
    n = grp.cumcount().values
    scale = {}
    for c in bd.STYLE_COLS:
        pre = grp[c].transform(lambda x: x.shift(1).expanding().mean()).fillna(0).values
        pv = d26[f"{c}_prior"].fillna(d26[c].mean()).values
        scale[c] = np.nanstd((n * pre + K * pv) / (n + K))

    # --- current season profiles -----------------------------------------------------------
    tmp = Path(tempfile.mkdtemp())
    with gzip.open(tmp / f"team_box_{SEASON}.json.gz", "wt") as f:
        json.dump(LIVE["team_box"], f)
    bd.RAW = tmp
    live_rows = bd.box_rows(SEASON)
    live_rows = live_rows[live_rows.d1 & live_rows.opp_d1].copy()
    prior26 = pd.concat([rows26[["teamId"]], st26], axis=1).groupby("teamId").mean().reset_index()
    league26 = st26.mean()
    prof = team_profiles(live_rows, prior26, league26)
    # teams with no D1 games yet: last season only
    sched = pd.DataFrame(LIVE["schedule"])
    sched = sched[sched.homeConference.notna() & sched.awayConference.notna() & (sched.status == "scheduled")]
    known = set(prof.teamId)
    extra = []
    for tid, name in pd.concat([sched[["homeTeamId", "homeTeam"]].set_axis(["teamId", "team"], axis=1),
                                sched[["awayTeamId", "awayTeam"]].set_axis(["teamId", "team"], axis=1)]).drop_duplicates().values:
        if tid not in known:
            p = prior26[prior26.teamId == tid]
            row = {"teamId": tid, "team": name, "n": 0}
            row.update({c: (p[c].iloc[0] if len(p) else league26[c]) for c in bd.STYLE_COLS})
            extra.append(row)
    prof = pd.concat([prof, pd.DataFrame(extra)], ignore_index=True)
    center = prof[bd.STYLE_COLS].mean()
    z = prof[["teamId", "team", "n"]].copy()
    for c in bd.STYLE_COLS:
        z[c] = (prof[c] - center[c]) / scale[c]
    zt = z.set_index("teamId")

    # --- lines ---------------------------------------------------------------------------
    line = {}
    for g in LIVE["lines"]:
        book = {x["provider"]: x for x in g["lines"] if x.get("spread") is not None}
        pick = next((p for p in bd.PROVIDER_RANK if p in book), next(iter(book), None))
        if pick:
            line[g["gameId"]] = (float(book[pick]["spread"]), pick)

    # --- upcoming game feature rows (same layout as training) ------------------------------
    up = []
    for _, s in sched.iterrows():
        h, a = zt.loc[s.homeTeamId], zt.loc[s.awayTeamId]
        r = {"gameId": s.id, "date": s.startDate, "home": s.homeTeam, "away": s.awayTeam,
             "neutral": bool(s.neutralSite), "venue": s.venue, "h_n": int(h.n), "a_n": int(a.n),
             "spread": line.get(s.id, (np.nan, None))[0], "book": line.get(s.id, (np.nan, None))[1]}
        for c in bd.STYLE_COLS:
            r[f"h_pre_{c}"], r[f"a_pre_{c}"] = h[c], a[c]
        up.append(r)
    up = pd.DataFrame(up)

    # --- train ---------------------------------------------------------------------------
    g = pd.read_parquet(TRAIN)
    g = g[g.season != 2021].reset_index(drop=True)
    X = features(g)
    X["spread"] = g.spread
    cols = [f"main_{m}" for m in MAIN] + ["neutral", "spread"]
    Xt = X[cols].values
    mu, sd = Xt.mean(0), Xt.std(0) + 1e-9
    b = ridge_fit((Xt - mu) / sd, g.resid.values, LAM)

    Xu = pd.DataFrame({f"main_{m}": up[f"h_pre_{m}"] - up[f"a_pre_{m}"] for m in MAIN})
    Xu["neutral"] = up.neutral.astype(float)
    Xu["spread"] = up.spread
    has_line = up.spread.notna().values
    # no line yet: project one from the same profiles (closing spread ~ team profiles), flagged as projected
    sc = cols[:-1]
    A = np.column_stack([np.ones(len(g)), X[sc].values])
    w, *_ = np.linalg.lstsq(A, g.spread.values, rcond=None)
    fit = A @ w
    r2 = 1 - ((g.spread - fit) ** 2).sum() / ((g.spread - g.spread.mean()) ** 2).sum()
    print(f"projected-line model R^2 vs closing spreads: {r2:.3f}, MAE {np.abs(g.spread - fit).mean():.2f}")
    proj = np.column_stack([np.ones(len(Xu)), Xu[sc].values]) @ w
    up["proj_spread"] = np.round(proj * 2) / 2
    Xu.loc[~has_line, "spread"] = up.loc[~has_line, "proj_spread"]
    Zu = (Xu[cols].values - mu) / sd
    contrib = Zu * b[1:]
    up["lean_home"] = b[0] + contrib.sum(1)            # predicted home ATS margin vs the line
    up["style_only"] = contrib[:, :len(MAIN)].sum(1)

    ref_sp = up.spread.fillna(up.proj_spread)
    pace_gap = np.where(ref_sp < 0, up.h_pre_pace - up.a_pre_pace, up.a_pre_pace - up.h_pre_pace)
    up["tempo_flag"] = (pace_gap > 1) & (ref_sp.abs() >= 8.5)

    out = []
    for i, r in up.iterrows():
        side_home = r.lean_home > 0
        pick = r.home if side_home else r.away
        cs = contrib[i, :len(MAIN)] * (1 if side_home else -1)
        order = np.argsort(-cs)[:3]
        reasons = []
        for j in order:
            if cs[j] <= 0.05:
                continue
            m = MAIN[j]
            diff = r[f"h_pre_{m}"] - r[f"a_pre_{m}"]
            hi, lo = LABELS[m]
            better = r.home if diff > 0 else r.away
            reasons.append({"text": f"{better} {hi}", "pts": round(float(cs[j]), 2)})
        ref = r.spread if has_line[i] else r.proj_spread
        sp = ref if side_home else -ref
        pick_line = f"{pick} {sp:+.1f}".replace("+0.0", " PK")
        out.append({
            "gameId": int(r.gameId), "date": r.date, "home": r.home, "away": r.away, "neutral": bool(r.neutral),
            "venue": r.venue, "spread_home": None if np.isnan(r.spread) else float(r.spread), "book": r.book,
            "proj_spread_home": float(r.proj_spread),
            "pick": pick, "pick_line": pick_line, "edge": round(abs(float(r.lean_home)), 2),
            "tier": "strong" if abs(r.lean_home) >= 2 else "play" if abs(r.lean_home) >= 1 else "lean",
            "tempo_flag": bool(r.tempo_flag), "line_status": "posted" if has_line[i] else "projected", "games_played": [int(r.a_n), int(r.h_n)], "reasons": reasons,
        })
    json.dump({"generated": LIVE["fetched_at"], "games": out}, open("cbb/live/picks.json", "w"), indent=1)
    df = pd.DataFrame(out)
    print(len(df), "games;", df.spread_home.notna().sum(), "with lines")
    print(df.groupby(["tier", df.spread_home.notna()]).size())
    print(df[df.spread_home.notna()].sort_values("edge", ascending=False)[["date", "away", "home", "spread_home", "pick_line", "edge", "tempo_flag"]].head(15).to_string(index=False))
    shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
