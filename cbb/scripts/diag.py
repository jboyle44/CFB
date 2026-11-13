import sys; sys.path.insert(0,'cbb/scripts')
import warnings; warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, statsmodels.api as sm
from analyze import features, season_fe
g=pd.read_parquet('/home/claude/cbb/work/games.parquet'); g=g[g.season!=2021].reset_index(drop=True)
X=features(g)
cl=lambda: {'groups':g.date.dt.date.astype(str)}
def fit(Xx):
    Xf=sm.add_constant(pd.concat([Xx,season_fe(g)],axis=1)); return sm.OLS(g.resid,Xf).fit(cov_type='cluster',cov_kwds=cl())
m=fit(X)
mains=[c for c in X if c.startswith('main_')]+['neutral']
print(pd.DataFrame({'coef':m.params[mains],'t':m.tvalues[mains]}).round(3).to_string())
# controls for favorite bias
X2=X.copy(); X2['spread']=g.spread; X2['abs_spread']=g.spread.abs(); X2['fav_sq']=-g.spread*g.spread.abs()/10
m2=fit(X2)
print('\nwith spread controls:'); print(pd.DataFrame({'coef':m2.params[['clash_tempo_gap','clash_tempo_fav','spread','abs_spread','fav_sq']],'t':m2.tvalues[['clash_tempo_gap','clash_tempo_fav','spread','abs_spread','fav_sq']]}).round(3))
# direction: favorite faster vs slower
fav_home=g.spread<0
fav_pace=np.where(fav_home,g.h_pre_pace,g.a_pre_pace); dog_pace=np.where(fav_home,g.a_pre_pace,g.h_pre_pace)
fav_resid=np.where(fav_home,g.resid,-g.resid)
d=pd.DataFrame({'gap':fav_pace-dog_pace,'fr':fav_resid,'sp':g.spread.abs(),'season':g.season})
d=d[(g.spread!=0)]
d['bin']=pd.cut(d.gap,[-9,-1.5,-1,-0.5,0.5,1,1.5,9])
t=d[d.fr!=0].groupby('bin').agg(n=('fr','size'),fav_cover=('fr',lambda r:(r>0).mean()),mean_resid=('fr','mean'),avg_spread=('sp','mean'))
print('\nfavorite pace minus underdog pace (z units):'); print(t.round(3))
# within spread bands
d['absgap']=d.gap.abs()
d['gapq']=pd.qcut(d.absgap,4,labels=['Q1 similar','Q2','Q3','Q4 clash'])
d['spb']=pd.cut(d.sp,[0,4,8,13,40],labels=['0-4','4.5-8','8.5-13','13+'])
print('\nfavorite cover% by tempo-gap quartile x spread band:')
print(d[d.fr!=0].pivot_table(index='gapq',columns='spb',values='fr',aggfunc=lambda r:(r>0).mean()).round(3))
print(d[d.fr!=0].pivot_table(index='gapq',columns='spb',values='fr',aggfunc='size'))
print('\nby season Q4 vs Q1 fav cover:')
print(d[d.fr!=0].pivot_table(index='season',columns='gapq',values='fr',aggfunc=lambda r:(r>0).mean()).round(3))
