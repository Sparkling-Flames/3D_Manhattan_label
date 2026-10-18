import json
from pathlib import Path
import pandas as pd,numpy as np
B=Path(__file__).resolve().parents[2]/'extracted/work_v2_20261019';O=Path(__file__).resolve().parent
D=pd.read_csv(B/'clusters/forward_swaps/labeled_events.csv.gz',low_memory=False);F=pd.read_csv(B/'profiles/fold_profiles.csv').set_index(['heldout_building','worker_id']);M=pd.read_csv(B/'fusion/POOL_MEMBERS.csv').set_index(['pool_id','worker_id'])
err={}
for end in ['a','b']:
 f=F.reindex(pd.MultiIndex.from_arrays([D.building_id,D['entrant_'+end]],names=F.index.names)).reset_index(drop=True)
 for label in ['Q2','QT','difficulty_type','fine_dtype_merged']:
  for metric in ['B8L2','D10']:
   c=label+'_'+metric;err[c+'_'+end]=int((D[c+'_'+end].fillna('unknown')!=f[c].fillna('unknown')).sum())
 for c,name in [('Q_effect_B8L2','beta'),('T_source_effect','source_T')]:D[name+'_'+end]=f[c].to_numpy()
 D['points_'+end]=M.reindex(pd.MultiIndex.from_arrays([D.pool_id,D['entrant_'+end]],names=M.index.names)).point_pairs.to_numpy()
err['point_count_flag']=int((D.equal_entrant_count!=D.points_a.eq(D.points_b)).sum())
d=D[D.common_known&D.equal_entrant_count&D.QT_B8L2_a.eq(D.QT_B8L2_b)].copy()
for name in ['beta','source_T']:d[name+'_mean']=(d[name+'_a']+d[name+'_b'])/2;d[name+'_absdiff']=abs(d[name+'_a']-d[name+'_b'])
d['stratum_id']=d.pool_id+'|'+d.k.astype(str)+'|'+d.background_id+'|'+d.points_a.astype(str)+'|'+d.QT_B8L2_a
published=pd.read_csv(B/'clusters/conditional_dtype/summary.csv');results=[]
for label in ['difficulty_type','fine_dtype_merged']:
 h=d[~d[label+'_B8L2_a'].str.contains('unknown')&~d[label+'_B8L2_b'].str.contains('unknown')].copy();h['cross_dtype']=h[label+'_B8L2_a'].ne(h[label+'_B8L2_b']).astype(float)
 for outcome in ['abs_B8L2_change','floor_jaccard_difference','joint_geometric_stable']:
  g=h.dropna(subset=[outcome,'beta_mean','beta_absdiff','source_T_mean','source_T_absdiff']).copy();s=g.groupby('stratum_id').cross_dtype.nunique();g=g[g.stratum_id.isin(s[s.eq(2)].index)].copy()
  ni=g[['pool_id','building_id']].drop_duplicates().groupby('building_id').size();nk=g[['pool_id','k']].drop_duplicates().groupby('pool_id').size();ns=g[['pool_id','k','stratum_id']].drop_duplicates().groupby(['pool_id','k']).size();nn=g.groupby('stratum_id').size()
  w=np.array([1/(len(ni)*ni[b]*nk[p]*ns[p,k]*nn[s]) for p,b,k,s in zip(g.pool_id,g.building_id,g.k,g.stratum_id)])
  for mod,cols in {'no_continuous_adjustment':['cross_dtype'],'continuous_Q':['cross_dtype','beta_mean','beta_absdiff'],'continuous_Q_T':['cross_dtype','beta_mean','beta_absdiff','source_T_mean','source_T_absdiff']}.items():
   z=g[cols+[outcome]].astype(float);z-=z.groupby(g.stratum_id).transform('mean');x=z[cols].to_numpy();y=z[outcome].to_numpy();coef=np.linalg.lstsq(x*np.sqrt(w[:,None]),y*np.sqrt(w),rcond=None)[0][0]
   ref=published[published.label.eq(label)&published.k.eq('all')&published.outcome.eq(outcome)&published.adjustment.eq(mod)].iloc[0]
   results.append(dict(label=label,outcome=outcome,adjustment=mod,coefficient=coef,published=ref.cross_dtype_coefficient,abs_difference=abs(coef-ref.cross_dtype_coefficient),pairs=len(g),images=g.image_id.nunique(),buildings=g.building_id.nunique()))
(O/'LABEL_ADJUSTMENT_AUDIT.json').write_text(json.dumps(dict(events=len(D),mismatches=err,recomputed_all_k_coefficients=results),indent=2));print(json.dumps(results,indent=2))
