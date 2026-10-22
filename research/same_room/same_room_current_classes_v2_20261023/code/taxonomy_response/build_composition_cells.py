"""Primary finite-composition cells, with member spread and honest denominators."""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd
from analyze_response import annotate_budget,analysis_layer,write_csv,hierarchy,moments,derive_pooled,numeric_indicators

p=argparse.ArgumentParser();p.add_argument('--responses',type=Path,required=True);p.add_argument('--design',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
a.out.mkdir(parents=True,exist_ok=True)
panels=annotate_budget(pd.read_csv(a.design/'PANELS.csv'));panels=panels[panels.is_primary_budget].copy();panels['analysis_layer']=panels.apply(analysis_layer,axis=1)
g=pd.read_csv(a.responses,low_memory=False);g=g[g.panel_id.isin(panels.panel_id)]
meta=panels.set_index('panel_id');cells=[]
metrics=['B8L2','D10','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n','S_bottom_deg','dir','Hmean','omission','extension','failure','log_recorded_time']
for pid,z in g.groupby('panel_id',sort=False):
 for scheme,col in [('structure','structure_vector'),('joint','joint_vector')]:
  zz=z if scheme=='structure' else z[z.joint_all_known.astype(bool)]
  for vector,c in zz.groupby(col,sort=True):
   base={k:meta.loc[pid,k] for k in ['pair_key','building','groups','image_a','image_b','pool_id_a','pool_id_b','reference_id_a','reference_id_b','n','k_selected','analysis_layer']}
   r=base|dict(panel_id=pid,scheme=scheme,full_class_vector=vector,n_requested_teams=len(c),n_joint_finite_Q=int((c.B8L2_a.notna()&c.B8L2_b.notna()).sum()),
      n_distinct_actual_teams=c.member_set_key.nunique(),member_sets_lookup='PAIRED_TEAM_RESPONSES_PRIMARY.csv.gz: panel_id + '+col,
      mean_replaced_workers_between_random_distinct_cell_teams=np.nan)
   sets=[set(x.split('|')) for x in c.member_set_key]
   if len(sets)>1:r['mean_replaced_workers_between_random_distinct_cell_teams']=np.mean([meta.loc[pid,'n']-len(x&y) for i,x in enumerate(sets) for y in sets[i+1:]])
   for v in ['a','b']:
    for metric in metrics:
     q=pd.to_numeric(c[metric+'_'+v],errors='coerce').dropna();tag=metric+'_'+v
     r[tag+'_n']=len(q);r[tag+'_mean']=q.mean();r[tag+'_sd']=q.std(ddof=0)
     if metric in ['B8L2','D10']:
      r[tag+'_min']=q.min();r[tag+'_p10']=q.quantile(.1);r[tag+'_p90']=q.quantile(.9);r[tag+'_max']=q.max();r[tag+'_p90_minus_p10']=q.quantile(.9)-q.quantile(.1)
      r[tag+'_below60_n']=int((q<60).sum());r[tag+'_below60_fraction']=(q<60).mean() if len(q) else np.nan
   cells.append(r)
d=pd.DataFrame(cells);write_csv(a.out/'COMPOSITION_CELLS_PRIMARY.csv.gz',d)
# At least two actual teams, then cells equally within each panel, panels within
# pair, pairs within declared group, groups within building. Full panel moments
# use actual-team weights; this cell-spread diagnostic has its own explicit unit.
s=d[d.n_distinct_actual_teams>=2]
fields=['n_requested_teams','n_joint_finite_Q','mean_replaced_workers_between_random_distinct_cell_teams']
fields += [c for c in d if any(c.endswith(x) for x in ['_sd','_p90_minus_p10','_below60_fraction'])]
panel=s.groupby(['panel_id','pair_key','building','groups','analysis_layer','scheme'],dropna=False)[fields].mean().reset_index()
for name,z in zip(['PAIR','GROUP','BUILDING','SUMMARY'],hierarchy(panel,['analysis_layer','scheme'],fields)):
 write_csv(a.out/('SAME_COMPOSITION_MEMBER_SPREAD_'+name+'.csv'),z)
print({'primary_composition_cells':len(d),'cells_with_multiple_actual_teams':len(s),'panels':d.panel_id.nunique()},flush=True)

# Compare Q and time on the identical eligible actual teams, so time recording
# coverage is not mistaken for a substantive difference in repeatability.
ordinary=panels[panels.ordinary_comparable].set_index('panel_id',drop=False);rows=[]
for pid,z in g[g.panel_id.isin(ordinary.index)].groupby('panel_id',sort=False):
 z=z[np.isfinite(z[['B8L2_a','B8L2_b','log_recorded_time_a','log_recorded_time_b']]).all(axis=1)]
 if len(z)<2:continue
 m=ordinary.loc[pid,['panel_id','pair_key','building','groups']].to_dict()
 for metric in ['B8L2','log_recorded_time','fusion_turn_n']:rows.append(m|moments(z,metric,'structure'))
c=numeric_indicators(pd.DataFrame(rows));write_csv(a.out/'TIME_QUALITY_COMMON_SUPPORT_PANEL.csv',c)
num=[x for x in c if pd.api.types.is_numeric_dtype(c[x])]
for name,z in zip(['PAIR','GROUP','BUILDING','SUMMARY'],hierarchy(c,['metric','scheme'],num)):
 write_csv(a.out/('TIME_QUALITY_COMMON_SUPPORT_'+name+'.csv'),derive_pooled(z))
