from pathlib import Path
import json,numpy as np,pandas as pd
P=Path(__file__).parent
D=json.load(open(P/'DESIGN.json'));X=pd.DataFrame(D['experiments']); C=pd.read_csv(P/'curves.csv');C=C.merge(X[['experiment_id','context']],on='experiment_id',validate='many_to_one')
counts=X.groupby(['pool_id','context']).method.nunique();common=set(counts[counts.eq(3)].index)
C['common_context']=[(p,c) in common for p,c in zip(C.pool_id,C.context)]
fold=pd.read_csv(P.parents[1]/'extracted/work_v2_20261019/profiles/fold_profiles.csv').set_index(['heldout_building','worker_id'])
within={}
for e in D['experiments']:
 labels=[fold.loc[(e['building'],e[w]),'QT_B8L2'] for w in ('a','b','c')]
 within[e['experiment_id']]=len(set(labels))==1
C['all_same_QT']=C.experiment_id.map(within)
rows=[]
for scope,z in [('all',C),('common_contexts',C[C.common_context]),('QTD_within_QT',C[C.method.eq('QTD') & C.all_same_QT])]+[(str(d),C[C.difficulty.eq(d)]) for d in sorted(C.difficulty.unique())]:
 for method,g in z.groupby('method'):
  for metric in ['curve_stable','curve_strict','curve_wide','all_complete','max_abs_Q','mean_abs_Q']:
   gm=g
   if metric in ['max_abs_Q','mean_abs_Q']:
    ok=g.groupby('experiment_id').all_q.all();gm=g[g.experiment_id.isin(ok[ok].index)]
   if gm.empty:continue
   im=gm.groupby(['building','pool_id','arm'])[metric].mean().unstack('arm');b=im.groupby('building').mean();delta=(b.cross_or_far-b.same_or_near).dropna();rng=np.random.default_rng(20261018)
   ix=rng.integers(len(b),size=(10000,len(b)));near=b.same_or_near.to_numpy()[ix].mean(axis=1);far=b.cross_or_far.to_numpy()[ix].mean(axis=1)
   rows.append(dict(scope=scope,method=method,metric=metric,experiments=g.experiment_id.nunique(),comparable_experiments=gm.experiment_id.nunique(),buildings=len(b),images=gm.pool_id.nunique(),same_or_near=b.same_or_near.mean(),near_low=np.quantile(near,.025),near_high=np.quantile(near,.975),cross_or_far=b.cross_or_far.mean(),cross_minus_same=delta.mean(),low=np.quantile(far-near,.025),high=np.quantile(far-near,.975)))
pd.DataFrame(rows).to_csv(P/'SUPPLEMENT_SUMMARY.csv',index=False)
# Training balance and selected history information; no outcome tuning.
X['Q_replacement_gap']=(X.q_b-X.q_c).abs();X['history_p_gap']=X.p_ab-X.p_ac
X.groupby('method')[['Q_replacement_gap','p_ab','p_ac','history_p_gap']].agg(['count','mean','median','min','max']).to_csv(P/'TRAINING_BALANCE.csv')
receipts=json.load(open(P/'RUN_RECEIPTS.json'))
json.dump(dict(requests=len(D['requests']),experiments=len(X),pools=len(receipts),actual_new_fusions=sum(r['new_fusions'] for r in receipts),exceptions=sum(len(r['exceptions']) for r in receipts),score_available=sum(r['score_available'] for r in receipts),common_contexts=len(common),common_images=C[C.common_context].pool_id.nunique(),common_buildings=C[C.common_context].building.nunique()),open(P/'FINAL_RECEIPT.json','w'),indent=2)
print(pd.DataFrame(rows).query("scope=='all' and metric in ['curve_stable','max_abs_Q']").to_string(index=False));print(json.load(open(P/'FINAL_RECEIPT.json')))
