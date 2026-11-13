import sys; sys.path.insert(0,'cbb/scripts')
import warnings; warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, statsmodels.api as sm
from analyze import features, season_fe, walk_forward
g=pd.read_parquet('/home/claude/cbb/work/games.parquet'); g=g[g.season!=2021].reset_index(drop=True)
X=features(g); X['spread']=g.spread
cl={'groups':g.date.dt.date.astype(str)}
Xf=sm.add_constant(pd.concat([X,season_fe(g)],axis=1)); m=sm.OLS(g.resid,Xf).fit(cov_type='cluster',cov_kwds=cl)
nt=[c for c in X if c.startswith('clash_') and 'tempo' not in c]
R=np.zeros((len(nt),Xf.shape[1]))
for i,c in enumerate(nt): R[i,list(Xf.columns).index(c)]=1
print('joint p, 11 non-tempo clashes (with spread control):', float(m.f_test(R).pvalue))
mains=[c for c in X if c.startswith('main_')]+['neutral','spread']
sets={'market only (spread)':['spread','neutral'],
      'main styles':mains,
      'main + tempo':mains+['clash_tempo_gap','clash_tempo_fav'],
      'main + all clashes':mains+[c for c in X if c.startswith('clash_')],
      'shooting-regression only (o_efg,d_efg)':['main_o_efg','main_d_efg','spread','neutral'],
      'tempo only':['clash_tempo_gap','clash_tempo_fav','spread','neutral']}
rows=[]
for k,cols in sets.items():
    r,p=walk_forward(g,X,cols)
    t1=[x for x in r['thresholds'] if x['threshold_pts']==1][0]
    t2=[x for x in r['thresholds'] if x['threshold_pts']==2][0]
    modern=(g.season>=2023)&p.notna()&(p.abs()>=1)&(g.resid!=0)
    rows.append({'model':k,'oos_r2':r['oos_r2_vs_market'],'bets>=1':t1['bets'],'win>=1':t1['win_pct'],'bets>=2':t2['bets'],'win>=2':t2['win_pct'],
                 'modern_2023_26_bets':int(modern.sum()),'modern_win':(np.sign(p[modern])==np.sign(g.resid[modern])).mean(),
                 'seasons_above_52.4': sum(s['win_pct']>0.5238 for s in r['by_season']),'n_seasons':len(r['by_season'])})
print(pd.DataFrame(rows).round(4).to_string())
