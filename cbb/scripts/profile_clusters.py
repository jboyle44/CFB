"""Joe's archetype spec: cluster teams on Four Factors (O+D) + tempo + scoring mix (O+allowed),
then test archetype-vs-archetype matchups against the spread, walk-forward.

FEATS=points : scoring mix = share of points from 3s, FTs, paint, mid-range (box score)
FEATS=shots  : scoring mix = share of FGA at rim / mid-range jumper / 3 (play-by-play) + FT points share

No lookahead: every game uses each team's profile from games BEFORE it. Clusters for test
season t are fit only on seasons < t. Matchup cover rates are learned from seasons < t,
then bet and graded on season t.
"""
import gzip
import itertools
import json
import os
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
RAW = Path("cbb/raw")
FEATS = os.environ.get("FEATS", "points")
KS = [int(k) for k in os.environ.get("KS", "4,5,6").split(",")]
MIN_PRIOR = 5
SEASONS = [s for s in range(2014, 2027) if s != 2021]
OUT = Path("/home/claude/cbb/work/results")
OUT.mkdir(parents=True, exist_ok=True)

FF = ["o_efg", "o_tov", "o_orb", "o_ftr", "d_efg", "d_tov", "d_orb", "d_ftr"]
MIX = {"points": ["o_p3", "o_pft", "o_ppaint", "o_pmid", "d_p3", "d_pft", "d_ppaint", "d_pmid"],
       "shots": ["o_s3", "o_srim", "o_smid", "o_pft", "d_s3", "d_srim", "d_smid", "d_pft"]}[FEATS]
DROP = [c for c in os.environ.get("DROP", "").split(",") if c]
MIX = [c for c in MIX if c not in DROP]
COLS = FF + ["pace"] + MIX
NICE = {"o_efg": ("shoots well", "shoots poorly"), "o_tov": ("careless", "secure"), "o_orb": ("crashes O-glass", "gets back"),
        "o_ftr": ("gets to line", "rarely FTs"), "d_efg": ("allows good shooting", "tough shooting D"),
        "d_tov": ("forces TOs", "passive D"), "d_orb": ("weak D-glass", "strong D-glass"), "d_ftr": ("fouls", "no-foul D"),
        "pace": ("fast", "slow"), "o_p3": ("3PT-reliant", "few 3PT pts"), "o_pft": ("FT-reliant", "few FT pts"),
        "o_ppaint": ("paint-reliant", "little paint scoring"), "o_pmid": ("mid-range-reliant", "no mid-range"),
        "d_p3": ("allows 3PT pts", "takes away 3s"), "d_pft": ("allows FT pts", "few FTs allowed"),
        "d_ppaint": ("allows paint pts", "protects paint"), "d_pmid": ("allows mid-range", "takes away mid-range"),
        "o_s3": ("3PT-heavy shot mix", "few 3PA"), "o_srim": ("rim-attacking", "few rim shots"),
        "o_smid": ("mid-range-heavy", "no mid-range"), "d_s3": ("allows 3PA", "runs off 3s"),
        "d_srim": ("allows rim shots", "walls off rim"), "d_smid": ("allows mid-range", "forces into mid-range? no")}
NICE["d_smid"] = ("concedes mid-range", "denies mid-range")


def sdiv(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return np.where(b > 0, a / np.where(b > 0, b, 1), np.nan)


def team_games(season):
    rows = []
    for r in json.load(gzip.open(RAW / f"team_box_{season}.json.gz")):
        t, o = r.get("teamStats") or {}, r.get("opponentStats") or {}
        if not t or not o or not t.get("possessions") or r.get("conference") is None or r.get("opponentConference") is None:
            continue
        rows.append({"gameId": r["gameId"], "teamId": r["teamId"], "oppId": r["opponentId"], "date": r["startDate"],
                     "poss": t["possessions"],
                     **{f"{s}_{k}": _dig(d, p) for s, d in (("t", t), ("o", o)) for k, p in {
                         "fga": ("fieldGoals", "attempted"), "fgm": ("fieldGoals", "made"),
                         "tpa": ("threePointFieldGoals", "attempted"), "tpm": ("threePointFieldGoals", "made"),
                         "twm": ("twoPointFieldGoals", "made"), "fta": ("freeThrows", "attempted"),
                         "ftm": ("freeThrows", "made"), "pts": ("points", "total"), "paint": ("points", "inPaint"),
                         "tov": ("turnovers", "total"), "orb": ("rebounds", "offensive"), "drb": ("rebounds", "defensive")}.items()}})
    df = pd.DataFrame(rows)
    num = [c for c in df.columns if c[:2] in ("t_", "o_")] + ["poss"]
    df[num] = df[num].apply(pd.to_numeric, errors="coerce").astype(float)
    return df


def _dig(d, path):
    for p in path:
        d = (d or {}).get(p)
    return d


def per_game(df, shots=None):
    m = pd.DataFrame(index=df.index)
    m["pace"] = df.poss
    for side, me, opp in (("o", "t", "o"), ("d", "o", "t")):
        m[f"{side}_efg"] = sdiv(df[f"{me}_fgm"] + 0.5 * df[f"{me}_tpm"], df[f"{me}_fga"])
        m[f"{side}_tov"] = sdiv(df[f"{me}_tov"], df.poss)
        m[f"{side}_orb"] = sdiv(df[f"{me}_orb"], df[f"{me}_orb"] + df[f"{opp}_drb"])
        m[f"{side}_ftr"] = sdiv(df[f"{me}_fta"], df[f"{me}_fga"])
        pts = df[f"{me}_pts"]
        m[f"{side}_p3"] = sdiv(3 * df[f"{me}_tpm"], pts)
        m[f"{side}_pft"] = sdiv(df[f"{me}_ftm"], pts)
        m[f"{side}_ppaint"] = sdiv(df[f"{me}_paint"], pts)
        m[f"{side}_pmid"] = sdiv(np.clip(2 * df[f"{me}_twm"] - df[f"{me}_paint"], 0, None), pts)
    if shots is not None:
        s = df[["gameId", "teamId", "oppId"]].merge(shots, on=["gameId", "teamId"], how="left")
        so = df[["gameId", "oppId"]].merge(shots.rename(columns={"teamId": "oppId"}), on=["gameId", "oppId"], how="left")
        for side, src in (("o", s), ("d", so)):
            tot = src[["rim", "jumper", "three_pointer"]].sum(1).values
            m[f"{side}_s3"] = sdiv(src.three_pointer.values, tot)
            m[f"{side}_srim"] = sdiv(src.rim.values, tot)
            m[f"{side}_smid"] = sdiv(src.jumper.values, tot)
            box_fga = df["t_fga"].values if side == "o" else df["o_fga"].values
            bad = (tot < 0.9 * box_fga) | (tot > 1.1 * box_fga)                        # incomplete PBP
            m.loc[bad, [f"{side}_s3", f"{side}_srim", f"{side}_smid"]] = np.nan
    return m


def load_shots(season):
    fp = RAW / f"shots_{season}.json.gz"
    if not fp.exists():
        return None
    rows = [{"gameId": r["gameId"], "teamId": r["teamId"],
             **{k: r["shots"].get(k, [0, 0])[0] for k in ("rim", "jumper", "three_pointer")}}
            for r in json.load(gzip.open(fp))]
    return pd.DataFrame(rows)


def build():
    frames = []
    for season in SEASONS:
        df = team_games(season)
        sh = load_shots(season) if FEATS == "shots" else None
        if FEATS == "shots" and sh is None:
            continue
        m = per_game(df, sh)
        d = pd.concat([df[["gameId", "teamId", "date"]], m[COLS]], axis=1)
        d["season"] = season
        d["date"] = pd.to_datetime(d.date, utc=True)
        d = d.sort_values(["teamId", "date", "gameId"])
        g = d.groupby("teamId")
        pre = g[COLS].transform(lambda x: x.shift(1).expanding().mean())
        d[[f"pre_{c}" for c in COLS]] = pre.values
        d["n_prior"] = g.cumcount()
        d[[f"full_{c}" for c in COLS]] = g[COLS].transform("mean").values   # end-of-season identity (training only)
        frames.append(d)
    tg = pd.concat(frames, ignore_index=True)
    for p in ("pre_", "full_"):
        cs = [f"{p}{c}" for c in COLS]
        tg[cs] = tg.groupby("season")[cs].transform(lambda x: (x - x.mean()) / x.std())
    return tg


def main():
    tg = build()
    games = pd.read_parquet("/home/claude/cbb/work/games_all.parquet")
    games = games[games.season.isin(tg.season.unique())]
    pre = [f"pre_{c}" for c in COLS]
    h = tg[["gameId", "teamId", "n_prior"] + pre].rename(columns={"teamId": "homeId", "n_prior": "hn", **{c: "h" + c for c in pre}})
    a = tg[["gameId", "teamId", "n_prior"] + pre].rename(columns={"teamId": "awayId", "n_prior": "an", **{c: "a" + c for c in pre}})
    G = games.merge(h, on=["gameId", "homeId"]).merge(a, on=["gameId", "awayId"])
    G = G[(G.hn >= MIN_PRIOR) & (G.an >= MIN_PRIOR)].dropna(subset=["h" + c for c in pre] + ["a" + c for c in pre]).reset_index(drop=True)
    H, A = G[["h" + c for c in pre]].values, G[["a" + c for c in pre]].values
    team_season = tg.groupby(["season", "teamId"])[[f"full_{c}" for c in COLS]].first().dropna().reset_index()
    print(f"FEATS={FEATS}: {len(G)} games, seasons {sorted(G.season.unique())}, {len(team_season)} team-seasons, {len(COLS)} metrics")

    # profile model (existing Team Profile Model) predictions for the 'net of profile' comparison
    X0 = features(G).fillna(0) if all(f"h_pre_{m}" in G for m in MAIN) else None
    y = G.resid.values

    # silhouette (fit quality) across k
    ts = team_season[[f"full_{c}" for c in COLS]].values
    sil = {k: round(silhouette_score(ts, KMeans(k, n_init=20, random_state=0).fit_predict(ts), sample_size=3000, random_state=0), 3)
           for k in range(3, 11)}
    print("silhouette by k:", sil)

    summary = []
    for K in KS:
        # ---- full-sample descriptive grid ------------------------------------------------
        km = KMeans(K, n_init=20, random_state=0).fit(ts)
        lab = []
        for c in km.cluster_centers_:
            order = np.argsort(-np.abs(c))[:3]
            lab.append(" / ".join(NICE[COLS[j]][0 if c[j] > 0 else 1] for j in order))
        lab = [f"T{i+1} {l}" for i, l in enumerate(lab)]
        lh, la = km.predict(H), km.predict(A)
        sizes = np.bincount(km.labels_, minlength=K)
        print(f"\n===== k={K} =====")
        for i in range(K):
            print(f"  {lab[i]}  ({sizes[i]} team-seasons)")
        cells = []
        for x, z in itertools.combinations(range(K), 2):
            m1, m2 = (lh == x) & (la == z), (lh == z) & (la == x)
            r = np.concatenate([y[m1], -y[m2]])
            se = np.concatenate([G.season.values[m1], G.season.values[m2]])
            nz = r != 0
            n = int(nz.sum())
            cov = (r[nz] > 0).mean()
            cells.append({"A": lab[x], "B": lab[z], "games": n, "A_cover": round(cov, 3), "z": round((cov - .5) / np.sqrt(.25 / n), 2),
                          "odd": round((r[nz & (se % 2 == 1)] > 0).mean(), 3), "even": round((r[nz & (se % 2 == 0)] > 0).mean(), 3)})
        cells = pd.DataFrame(cells).sort_values("z", key=abs, ascending=False)
        from scipy.stats import norm
        zcrit = norm.ppf(1 - 0.025 / len(cells))
        print(f"  matchup grid ({len(cells)} pairs; significance needs |z| > {zcrit:.2f}):")
        print(cells.to_string(index=False))
        big = cells[cells.games >= 300]
        stab = np.corrcoef(big.odd, big.even)[0, 1] if len(big) > 2 else np.nan
        print(f"  odd/even-season stability: {stab:.2f}")
        cells.to_csv(OUT / f"clusters_{FEATS}{'_dedup' if DROP else ''}_k{K}_grid.csv", index=False)

        # ---- walk-forward ----------------------------------------------------------------
        bets = []
        prof_preds = pd.Series(np.nan, index=G.index)
        comb_preds = pd.Series(np.nan, index=G.index)
        for t in sorted(G.season.unique()):
            if t < 2017:
                continue
            tr_ts = team_season[team_season.season < t][[f"full_{c}" for c in COLS]].values
            if len(tr_ts) < 500:
                continue
            kmt = KMeans(K, n_init=10, random_state=0).fit(tr_ts)
            h, a = kmt.predict(H), kmt.predict(A)
            tr, te = (G.season < t).values, (G.season == t).values
            # (1) pure archetype betting, spread as the talent adjustment
            for x, z in itertools.permutations(range(K), 2):
                r = np.concatenate([y[tr & (h == x) & (a == z)], -y[tr & (h == z) & (a == x)]])
                r = r[r != 0]
                p = (np.sum(r > 0) + 100) / (len(r) + 200)               # shrunk toward 50%
                sel = te & (h == x) & (a == z) & (y != 0)
                for th in (0.51, 0.52, 0.53):
                    if p >= th or p <= 1 - th:
                        side_home = p >= th
                        for i in np.where(sel)[0]:
                            bets.append({"th": th, "season": t, "win": (y[i] > 0) == side_home})
            # (2) does adding archetype matchups improve the Team Profile Model?
            if X0 is not None:
                pairs = list(itertools.combinations(range(K), 2))
                M = np.column_stack([((h == x) & (a == z)).astype(float) - ((h == z) & (a == x)).astype(float) for x, z in pairs])
                base = X0[[f"main_{m}" for m in MAIN] + ["neutral"]].assign(spread=G.spread).values
                for store, Xf in ((prof_preds, base), (comb_preds, np.column_stack([base, M]))):
                    mu, sd = Xf[tr].mean(0), Xf[tr].std(0) + 1e-9
                    b = ridge_fit((Xf[tr] - mu) / sd, y[tr], 500.0)
                    store[te] = b[0] + ((Xf[te] - mu) / sd) @ b[1:]
        B = pd.DataFrame(bets)
        print("  WALK-FORWARD (learned from prior seasons, graded on the next):")
        for th in (0.51, 0.52, 0.53):
            s = B[B.th == th]
            if len(s):
                by = s.groupby("season").win.mean().round(3).to_dict()
                print(f"    bet matchups with past cover >= {th:.0%}: {len(s)} bets, {s.win.mean():.4f} win | by season {by}")
                summary.append({"feats": FEATS, "k": K, "threshold": th, "bets": len(s), "win": s.win.mean(),
                                "seasons_above_52.4": int((s.groupby('season').win.mean() > 0.5238).sum()), "n_seasons": s.season.nunique()})
            else:
                print(f"    threshold {th:.0%}: no matchup qualified")
        if X0 is not None:
            for name, p in (("profile model", prof_preds), ("profile + archetype matchups", comb_preds)):
                s = p.notna() & (p.abs() >= 1) & (G.resid != 0)
                s2 = p.notna() & (p.abs() >= 2) & (G.resid != 0)
                print(f"    {name}: 1+pt {int(s.sum())} bets {(np.sign(p[s]) == np.sign(G.resid[s])).mean():.4f} | "
                      f"2+pt {int(s2.sum())} bets {(np.sign(p[s2]) == np.sign(G.resid[s2])).mean():.4f}")
    pd.DataFrame(summary).to_csv(OUT / f"clusters_{FEATS}{'_dedup' if DROP else ''}_walkforward.csv", index=False)


if __name__ == "__main__":
    main()
