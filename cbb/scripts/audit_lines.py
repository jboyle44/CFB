"""Audit test: hybrid backtest results by line provider, and sportsbook-only results."""
import contextlib, io, sys, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent))
with contextlib.redirect_stdout(io.StringIO()):
    sys.argv = ["x"]
    import make_trends as M          # hybrid walk-forward predictions in M.g
g = M.g
def row(d, lab):
    out = [lab.ljust(34)]
    for th in (1, 2):
        s = d[d.edge >= th]
        out.append(f"{th}+: {s.win.mean()*100:5.1f}% ({len(s):5d})" if len(s) else f"{th}+:   n/a")
    print(" | ".join(out))
print("Hybrid model by line provider (provider chosen per game by priority: consensus > ESPN BET > Draft Kings > Bovada > teamrankings > numberfire)")
row(g, "All")
for p, d in g.groupby("provider"):
    row(d, f"{p} [{d.season.min()}-{d.season.max()}]")
books = g[g.provider.isin(["ESPN BET", "Draft Kings", "Bovada"])]
row(books, "Sportsbooks only (ESPN BET/DK/Bovada)")
row(g[g.provider.isin(["consensus"])], "Consensus only")
row(g[~g.provider.isin(["numberfire", "teamrankings"])], "Excluding numberfire + teamrankings")
row(g[g.season >= 2023], "2023-2026 (modern lines)")
