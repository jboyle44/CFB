"""Styles-make-fights backtest.

Question: after the closing spread, do play-style CLASHES (attacker's offensive
tendency x defender's allowance of that same thing) predict who covers?

Every clash feature is symmetric:  home_attack x away_defense  -  away_attack x home_defense
so beta > 0 means "the side whose offensive style meets a defense that gives up that
style beats the spread". Main effects (home minus away style) are included as controls
so a clash coefficient measures the interaction only.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

GAMES = Path(sys.argv[1] if len(sys.argv) > 1 else "/home/claude/cbb/work/games.parquet")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "/home/claude/cbb/work/results")
EXCLUDE = [2021]          # COVID season, mirrors BRR precedent
BREAKEVEN = 110 / 210     # 52.38% at -110

CLASHES = {  # name: (offense metric of attacker, defense metric of defender, plain-English)
    "3pt_volume":   ("o_3par", "d_3par", "3-heavy offense vs defense that allows lots of 3PA"),
    "foul_drawing": ("o_ftr", "d_ftr", "foul-drawing offense vs foul-prone defense"),
    "turnovers":    ("o_tov", "d_tov", "turnover-prone offense vs defense that forces TOs"),
    "off_glass":    ("o_orb", "d_orb", "offensive-rebounding team vs defense that allows boards"),
    "paint":        ("o_paint", "d_paint", "paint-scoring offense vs defense that allows paint points"),
    "transition":   ("o_fb", "d_fb", "transition offense vs defense that allows fast breaks"),
    "ball_movement": ("o_ast", "d_ast", "assist-heavy offense vs defense that allows assisted looks"),
    "shooting":     ("o_efg", "d_efg", "efficient-shooting offense vs defense that allows high eFG"),
    "paint_vs_rim": ("o_paint", "d_blk", "paint-scoring offense vs shot-blocking defense"),
    "tov_vs_steals": ("o_tov", "d_stl", "turnover-prone offense vs high-steal defense"),
    "3pt_vs_3d":    ("o_3par", "d_efg", "3-heavy offense vs defense that allows high eFG"),
}
MAIN = ["pace", "o_3par", "o_ftr", "o_tov", "o_orb", "o_paint", "o_fb", "o_ast", "o_efg",
        "d_3par", "d_ftr", "d_tov", "d_orb", "d_paint", "d_fb", "d_ast", "d_efg", "d_blk", "d_stl"]


def features(g):
    X = pd.DataFrame(index=g.index)
    for k, (o, d, _) in CLASHES.items():
        X[f"clash_{k}"] = g[f"h_pre_{o}"] * g[f"a_pre_{d}"] - g[f"a_pre_{o}"] * g[f"h_pre_{d}"]
    # tempo: do favorites cover more in fast games, and does the faster team cover more?
    pace = (g.h_pre_pace + g.a_pre_pace) / 2
    X["clash_tempo_fav"] = -g.spread * pace / 10            # home-favorite size x expected pace
    X["clash_tempo_gap"] = np.abs(g.h_pre_pace - g.a_pre_pace) * np.sign(-g.spread)
    for m in MAIN:
        X[f"main_{m}"] = g[f"h_pre_{m}"] - g[f"a_pre_{m}"]
    X["neutral"] = g.neutral.astype(float)
    X["spread"] = g.spread                                  # controls for favorite/underdog bias
    return X


def season_fe(g):
    return pd.get_dummies(g.season, prefix="s", drop_first=True, dtype=float)


def full_sample(g, X):
    Xf = sm.add_constant(pd.concat([X, season_fe(g)], axis=1))
    m = sm.OLS(g.resid, Xf).fit(cov_type="cluster", cov_kwds={"groups": g.date.dt.date.astype(str)})
    clash = [c for c in X.columns if c.startswith("clash_")]
    tab = pd.DataFrame({"coef": m.params[clash], "se": m.bse[clash], "t": m.tvalues[clash], "p": m.pvalues[clash]})
    tab["p_bonferroni"] = np.minimum(tab.p * len(clash), 1)
    # joint test: do all clash terms together add anything?
    r = np.zeros((len(clash), len(Xf.columns)))
    for i, c in enumerate(clash):
        r[i, list(Xf.columns).index(c)] = 1
    joint = m.f_test(r)
    main = [c for c in X.columns if c.startswith("main_")]
    rm = np.zeros((len(main), len(Xf.columns)))
    for i, c in enumerate(main):
        rm[i, list(Xf.columns).index(c)] = 1
    joint_main = m.f_test(rm)
    return m, tab, float(joint.pvalue), float(joint_main.pvalue)


def ridge_fit(X, y, lam):
    Xc = np.column_stack([np.ones(len(X)), X])
    pen = lam * np.eye(Xc.shape[1]); pen[0, 0] = 0
    return np.linalg.solve(Xc.T @ Xc + pen, Xc.T @ y)


def walk_forward(g, X, cols, lam=500.0, thresholds=(0.5, 1, 1.5, 2, 3)):
    """Train on all prior seasons, predict the next. Market baseline predicts 0."""
    preds = pd.Series(np.nan, index=g.index)
    for t in sorted(g.season.unique()):
        if t < 2017:
            continue
        tr, te = g.season < t, g.season == t
        Xt = X.loc[tr, cols].values
        mu, sd = Xt.mean(0), Xt.std(0) + 1e-9
        b = ridge_fit((Xt - mu) / sd, g.loc[tr, "resid"].values, lam)
        preds[te] = b[0] + ((X.loc[te, cols].values - mu) / sd) @ b[1:]
    ok = preds.notna()
    y, p = g.loc[ok, "resid"], preds[ok]
    sse_model, sse_zero = ((y - p) ** 2).sum(), (y ** 2).sum()
    rows = []
    for th in thresholds:
        sel = (p.abs() >= th) & (y != 0)
        win = (np.sign(p[sel]) == np.sign(y[sel]))
        n, w = int(sel.sum()), int(win.sum())
        rows.append({"threshold_pts": th, "bets": n, "wins": w, "win_pct": w / n if n else np.nan,
                     "units_at_-110": w * (100 / 110) - (n - w) if n else 0.0})
    by_season = []
    for t in sorted(g.loc[ok, "season"].unique()):
        s = ok & (g.season == t) & (preds.abs() >= 1) & (g.resid != 0)
        if s.sum():
            by_season.append({"season": int(t), "bets": int(s.sum()),
                              "win_pct": float((np.sign(preds[s]) == np.sign(g.resid[s])).mean())})
    return {"oos_r2_vs_market": 1 - sse_model / sse_zero, "corr": float(np.corrcoef(y, p)[0, 1]),
            "n_games": int(ok.sum()), "thresholds": rows, "by_season": by_season}, preds


def bucket_table(g):
    """Plain-English check: when one side has a strong clash edge, how often does it cover?"""
    rows = []
    for k, (o, d, _) in CLASHES.items():
        h = g[f"h_pre_{o}"] * g[f"a_pre_{d}"]
        a = g[f"a_pre_{o}"] * g[f"h_pre_{d}"]
        # attacker must be above average at the style AND defender above average at allowing it
        hs = (g[f"h_pre_{o}"] > 0.75) & (g[f"a_pre_{d}"] > 0.75)
        as_ = (g[f"a_pre_{o}"] > 0.75) & (g[f"h_pre_{d}"] > 0.75)
        cov = pd.concat([g.resid[hs & ~as_] > 0, g.resid[as_ & ~hs] < 0])
        push = pd.concat([g.resid[hs & ~as_] == 0, g.resid[as_ & ~hs] == 0])
        c = cov[~push.values]
        n = len(c)
        rows.append({"clash": k, "description": CLASHES[k][2], "games": n,
                     "attacker_cover_pct": c.mean() if n else np.nan,
                     "z_vs_50": (c.mean() - 0.5) / np.sqrt(0.25 / n) if n else np.nan})
    return pd.DataFrame(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    g = pd.read_parquet(GAMES)
    g = g[~g.season.isin(EXCLUDE)].reset_index(drop=True)
    X = features(g)
    clash = [c for c in X.columns if c.startswith("clash_")]
    main_ = [c for c in X.columns if c.startswith("main_")] + ["neutral", "spread"]

    m, tab, p_joint, p_joint_main = full_sample(g, X)
    print(f"Full sample n={len(g)}  joint p(clash)={p_joint:.4f}  joint p(main styles)={p_joint_main:.4f}")
    print(tab.round(4).to_string())

    wf_clash, pred_clash = walk_forward(g, X, clash + main_)
    wf_main, _ = walk_forward(g, X, main_)
    rng = np.random.default_rng(7)
    null_wins = []
    for _ in range(200):  # permutation null: shuffle residuals within season, rerun walk-forward
        gp = g.copy()
        gp["resid"] = gp.groupby("season").resid.transform(lambda r: r.sample(frac=1, random_state=int(rng.integers(1e9))).values)
        res, _ = walk_forward(gp, X, clash + main_, thresholds=(1,))
        null_wins.append(res["thresholds"][0]["win_pct"])
    obs = next(r for r in wf_clash["thresholds"] if r["threshold_pts"] == 1)["win_pct"]
    p_perm = float((np.array(null_wins) >= obs).mean())
    print("walk-forward clash+main:", json.dumps({k: v for k, v in wf_clash.items() if k != "by_season"}, default=float, indent=1))
    print("walk-forward main only:", round(wf_main["oos_r2_vs_market"], 5), wf_main["thresholds"][1])
    print(f"permutation p (win% at >=1pt): {p_perm:.3f}  null mean {np.mean(null_wins):.4f}  null 95th {np.percentile(null_wins, 95):.4f}")

    buckets = bucket_table(g)
    print(buckets.round(3).to_string())

    tab.to_csv(OUT / "clash_coefficients.csv")
    buckets.to_csv(OUT / "clash_buckets.csv", index=False)
    pd.DataFrame(wf_clash["thresholds"]).to_csv(OUT / "walkforward_thresholds.csv", index=False)
    pd.DataFrame(wf_clash["by_season"]).to_csv(OUT / "walkforward_by_season.csv", index=False)
    json.dump({"n_games": len(g), "seasons": sorted(int(s) for s in g.season.unique()),
               "p_joint_clash": p_joint, "p_joint_main": p_joint_main,
               "wf_clash": wf_clash, "wf_main": wf_main, "perm_p": p_perm,
               "perm_null_mean": float(np.mean(null_wins)), "perm_null_p95": float(np.percentile(null_wins, 95))},
              open(OUT / "summary.json", "w"), default=float, indent=1)


if __name__ == "__main__":
    main()
