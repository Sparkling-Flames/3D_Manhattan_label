"""Secondary transport check; Manual corner-count trait -> C1 Semi.
This is not an assistance effect. No randomization and no quality inference.
Uses the archived RQ1 calculation-valid definition (104 Semi rows), which is
not identical to the newer broad audit's geometry-processable definition.
"""
from pathlib import Path
import pandas as pd,numpy as np
R=Path(__file__).parent
source=(R/'fit_exploratory_profiles.py').read_text().split('summary=[];profile=[];cv=[];stability=[];cluster=[]')[0]
ns={'__file__':str(R/'fit_exploratory_profiles.py')};exec(source,ns)
manual=ns['D'];fit=ns['fit'];g=pd.read_csv(R/'inputs/legacy_rq1/c1_geometry_repair_audit.csv')
results=[]
seen_manual=set(map(tuple,g.loc[g.condition.eq('manual'),['base_task_id','worker_id']].to_numpy()))
semi_valid=g[g.condition.eq('semi')&g.calculation_valid].copy()
no_cross=semi_valid[~semi_valid[['base_task_id','worker_id']].apply(tuple,axis=1).isin(seen_manual)].copy()
for variant,semi in {'calculation_valid_104':semi_valid,'raw_valid_103':g[g.condition.eq('semi')&g.raw_valid].copy(),'no_same_image_cross_condition_record':no_cross}.items():
 semi['corner_pair_count']=(semi.raw_point_count-semi.repair_applied.astype(int))/2
 semi['building_id']=semi.base_task_id.str.split('_').str[0]
 predictions=[]
 for b in sorted(semi.building_id.unique()):
  c,_,_=fit(manual[manual.building_id!=b],'corner_pair_count')
  te=semi[semi.building_id.eq(b)&semi.worker_id.isin(c.index)].copy()
  te['pred']=te.worker_id.map(c)
  te['pred']-=te.groupby('base_task_id').pred.transform('mean')
  te['target']=te.corner_pair_count-te.groupby('base_task_id').corner_pair_count.transform('mean')
  predictions.append(te)
 p=pd.concat(predictions);sse=((p.target-p.pred)**2).sum();baseline=(p.target**2).sum()
 results.append({'variant':variant,'n_semi_rows':len(p),'images':p.base_task_id.nunique(),'workers':p.worker_id.nunique(),'buildings':p.building_id.nunique(),'transport_within_task_R2':1-sse/baseline,'assumption':'unscaled Manual worker effect transported to Semi; exploratory only'})
pd.DataFrame(results).to_csv(R/'manual_to_semi_corner_transport.csv',index=False)
print(pd.DataFrame(results).to_string(index=False))
