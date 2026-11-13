"""Build the game-level matchup dataset for the styles-make-fights backtest.

One row per D1-vs-D1 game with a closing spread. Every style feature is a
season-to-date average from games played BEFORE tip (no lookahead), then
z-scored within season.
"""
import gzip
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path(sys.argv[1] if len(sys.argv) > 1 else "cbb/raw")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "cbb/work/games.parquet")
SEASONS = range(2014, 2027)
MIN_PRIOR = 5
PROVIDER_RANK = ["consensus", "ESPN BET", "Draft Kings", "Bovada", "teamrankings", "numberfire"]


def sdiv(a, b):
    return np.where(b > 0, a / np.where(b > 0, b, 1), np.nan)


def box_rows(season):
    rows = []
    for r in json.load(gzip.open(RAW / f"team_box_{season}.json.gz")):
        t, o = r.get("teamStats") or {}, r.get("opponentStats") or {}
        if not t or not o or not t.get("possessions"):
            continue

        def g(d, *path):
            for p in path:
                d = (d or {}).get(p)
            return d

        rows.append({
            "gameId": r["gameId"], "season": season, "date": r["startDate"], "team": r["team"],
            "teamId": r["teamId"], "opp": r["opponent"], "oppId": r["opponentId"],
            "d1": r.get("conference") is not None, "opp_d1": r.get("opponentConference") is not None,
            "poss": t["possessions"],
            # offense (what this team does)
            "o_fga": g(t, "fieldGoals", "attempted"), "o_fgm": g(t, "fieldGoals", "made"),
            "o_3pa": g(t, "threePointFieldGoals", "attempted"), "o_3pm": g(t, "threePointFieldGoals", "made"),
            "o_fta": g(t, "freeThrows", "attempted"), "o_pts": g(t, "points", "total"),
            "o_paint": g(t, "points", "inPaint"), "o_fb": g(t, "points", "fastBreak"),
            "o_tov": g(t, "turnovers", "total"), "o_orb": g(t, "rebounds", "offensive"),
            "o_drb": g(t, "rebounds", "defensive"), "o_ast": t.get("assists"),
            "o_stl": t.get("steals"), "o_blk": t.get("blocks"),
            # what the opponent did against this team (defense profile)
            "d_fga": g(o, "fieldGoals", "attempted"), "d_fgm": g(o, "fieldGoals", "made"),
            "d_3pa": g(o, "threePointFieldGoals", "attempted"), "d_3pm": g(o, "threePointFieldGoals", "made"),
            "d_2pa": g(o, "twoPointFieldGoals", "attempted"),
            "d_fta": g(o, "freeThrows", "attempted"), "d_pts": g(o, "points", "total"),
            "d_paint": g(o, "points", "inPaint"), "d_fb": g(o, "points", "fastBreak"),
            "d_tov": g(o, "turnovers", "total"), "d_orb": g(o, "rebounds", "offensive"),
            "d_drb": g(o, "rebounds", "defensive"), "d_ast": o.get("assists"),
            "o_2pa": g(t, "twoPointFieldGoals", "attempted"),
        })
    df = pd.DataFrame(rows)
    num = [c for c in df.columns if c[:2] in ("o_", "d_")] + ["poss"]
    df[num] = df[num].apply(pd.to_numeric, errors="coerce").astype(float)
    return df


def per_game_style(df):
    """Per-game style metrics. Offense = team tendency; defense = what it allows/forces."""
    s = pd.DataFrame(index=df.index)
    s["pace"] = df.poss
    for side, opp in (("o", "d"), ("d", "o")):
        s[f"{side}_3par"] = sdiv(df[f"{side}_3pa"], df[f"{side}_fga"])           # three-point attempt rate
        s[f"{side}_ftr"] = sdiv(df[f"{side}_fta"], df[f"{side}_fga"])            # free-throw rate
        s[f"{side}_tov"] = sdiv(df[f"{side}_tov"], df.poss)                      # turnover rate
        s[f"{side}_orb"] = sdiv(df[f"{side}_orb"], df[f"{side}_orb"] + df[f"{opp}_drb"])  # offensive rebound %
        s[f"{side}_paint"] = sdiv(df[f"{side}_paint"], df[f"{side}_pts"])        # paint share of points
        s[f"{side}_fb"] = sdiv(df[f"{side}_fb"], df[f"{side}_pts"])              # transition share of points
        s[f"{side}_ast"] = sdiv(df[f"{side}_ast"], df[f"{side}_fgm"])            # assisted share of makes
        s[f"{side}_efg"] = sdiv(df[f"{side}_fgm"] + 0.5 * df[f"{side}_3pm"], df[f"{side}_fga"])
    s["d_blk"] = sdiv(df.o_blk, df.d_2pa)      # rim protection: blocks per opp 2PA
    s["d_stl"] = sdiv(df.o_stl, df.poss)       # ball pressure: steals per possession
    return s


STYLE = None


def main():
    global STYLE
    frames = []
    for season in SEASONS:
        df = box_rows(season)
        df = df[df.d1 & df.opp_d1].copy()
        df["date"] = pd.to_datetime(df.date, utc=True)
        st = per_game_style(df)
        STYLE = list(st.columns)
        df = pd.concat([df[["gameId", "season", "date", "team", "teamId", "opp", "oppId"]], st], axis=1)
        df = df.sort_values(["teamId", "date", "gameId"])
        grp = df.groupby("teamId")
        pre = grp[STYLE].transform(lambda x: x.shift(1).expanding().mean())
        pre.columns = [f"pre_{c}" for c in STYLE]
        df = pd.concat([df, pre], axis=1)
        df["n_prior"] = grp.cumcount()
        frames.append(df)
    tg = pd.concat(frames, ignore_index=True)

    # z-score pre-game style within season
    pre_cols = [f"pre_{c}" for c in STYLE]
    tg[pre_cols] = tg.groupby("season")[pre_cols].transform(lambda x: (x - x.mean()) / x.std())

    # lines -> one closing home spread per game
    lrows = []
    for season in SEASONS:
        for g in json.load(gzip.open(RAW / f"lines_{season}.json.gz")):
            book = {x["provider"]: x for x in g["lines"] if x.get("spread") is not None}
            pick = next((p for p in PROVIDER_RANK if p in book), None)
            if pick is None or g.get("homeScore") is None or g.get("awayScore") is None:
                continue
            lrows.append({"gameId": g["gameId"], "homeId": g["homeTeamId"], "awayId": g["awayTeamId"],
                          "home": g["homeTeam"], "away": g["awayTeam"], "homeScore": g["homeScore"],
                          "awayScore": g["awayScore"], "spread": float(book[pick]["spread"]),
                          "total": book[pick].get("overUnder"), "provider": pick,
                          "seasonType": g.get("seasonType")})
    lines = pd.DataFrame(lrows)

    keep = ["gameId", "teamId", "n_prior", "season", "date"] + pre_cols
    h = tg[keep].add_prefix("h_").rename(columns={"h_gameId": "gameId", "h_teamId": "homeId", "h_season": "season", "h_date": "date"})
    a = tg[keep].add_prefix("a_").drop(columns=["a_season", "a_date"]).rename(columns={"a_gameId": "gameId", "a_teamId": "awayId"})
    games = lines.merge(h, on=["gameId", "homeId"]).merge(a, on=["gameId", "awayId"])

    # neutral flag from box score data
    neutral = {}
    for season in SEASONS:
        for r in json.load(gzip.open(RAW / f"team_box_{season}.json.gz")):
            neutral[r["gameId"]] = bool(r.get("neutralSite"))
    games["neutral"] = games.gameId.map(neutral).fillna(False)

    games["margin"] = games.homeScore - games.awayScore
    games["resid"] = games.margin + games.spread            # >0 means home covered
    games = games[(games.h_n_prior >= MIN_PRIOR) & (games.a_n_prior >= MIN_PRIOR)]
    games = games.dropna(subset=[c for c in games.columns if c.startswith(("h_pre_", "a_pre_"))])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    games.to_parquet(OUT, index=False)
    print(f"games: {len(games)}  seasons: {games.season.nunique()}  style metrics: {len(STYLE)}")
    print(games.groupby("season").agg(n=("gameId", "size"), cover=("resid", lambda r: (r > 0).mean()),
                                      push=("resid", lambda r: (r == 0).mean())).round(3).T.to_string())
    print("corr(spread, margin) =", round(np.corrcoef(games.spread, games.margin)[0, 1], 3),
          " mean resid =", round(games.resid.mean(), 2), " sd resid =", round(games.resid.std(), 2))


if __name__ == "__main__":
    main()
