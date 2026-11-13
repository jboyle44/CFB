import sys,gzip,json; sys.path.insert(0,'cbb/scripts')
import warnings; warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from analyze import features, walk_forward
rows=[]
for s in (2025,2026):
    for gm in json.load(gzip.open(f'cbb/raw/lines_{s}.json.gz')):
        for x in gm['lines']:
            if x.get('spread') is not None and x.get('spreadOpen') is not None:
                rows.append({'gameId':gm['gameId'],'prov':x['provider'],'close':x['spread'],'open':x['spreadOpen']})
mv=pd.DataFrame(rows); mv['move']=mv.close-mv.open
print(mv.groupby('prov').agg(n=('move','size'),pct_moved=('move',lambda m:(m!=0).mean()),mean_abs_move=('move',lambda m:m.abs().mean())).round(3))
g=pd.read_parquet('/home/claude/cbb/work/games.parquet'); g=g[g.season!=2021].reset_index(drop=True)
X=features(g); X['spread']=g.spread
mains=[c for c in X if c.startswith('main_')]+['neutral','spread']
r,p=walk_forward(g,X,mains)
g['pred']=p
m1=mv.groupby('gameId').move.mean()
d=g[g.gameId.isin(m1.index)&g.pred.notna()].copy(); d['move']=d.gameId.map(m1)
# model pred>0 = home covers more than spread implies; market moving toward home = spread decreasing (move<0)
d=d[d.move!=0]
print('games with movement:',len(d),' corr(pred, -move)=',round(np.corrcoef(d.pred,-d.move)[0,1],3),
      ' share where model side = steam side:',round((np.sign(d.pred)==np.sign(-d.move)).mean(),3))
