"""Evaluate every frozen ratio on all supported images; retain pure comparators."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
from design_history_panel import read,write
from summarize_blocks import csv_write

def mean_summary(df,keys,metrics):
 if df.empty:return pd.DataFrame()
 out=[]
 for key,g in df.groupby(keys,dropna=False):
  key=key if isinstance(key,tuple) else (key,);row=dict(zip(keys,key))
  image=g.groupby(['building','image'])[metrics].mean();building=image.groupby('building').mean()
  row.update(building.mean().to_dict());row.update(images=g.image.nunique(),pools=g.pool_id.nunique(),buildings=g.building.nunique(),comparisons=len(g))
  for metric in metrics:
   valid=image[metric].dropna();bv=building[metric].dropna()
   row[metric+'_images_known']=len(valid);row[metric+'_buildings_known']=len(bv)
   row[metric+'_positive_images']=int((valid>0).sum());row[metric+'_positive_buildings']=int((bv>0).sum())
   row[metric+'_image_p10']=valid.quantile(.1) if len(valid) else np.nan
  out.append(row)
 return pd.DataFrame(out)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
 a=ap.parse_args();spec=read(a.root/'RATIO_REPLICATION_FREEZE.json');a.out.mkdir(parents=True,exist_ok=True)
 rows=[];pure_rows=[];team_support=[];capacities=[]
 for phase in ['discovery','replication','assessment']:
  requests=read(a.root/(phase+'_requests.json.gz'));folder=a.root/(phase+'_metrics')
  comps=pd.read_csv(folder/'composition_evidence.csv.gz');contrasts=pd.read_csv(folder/'pure_mixture_contrasts.csv.gz')
  comp_lookup=comps.set_index('composition_id')
  if phase=='discovery':
   links=[]
   for rule in spec['rules']:
    g=comps[(comps.method_id==rule['method_id'])&(comps.domain==rule['domain'])&(comps.n==rule['n'])]
    mix=g[g.class_counts.map(lambda v:json.loads(v)==rule['mixture'])]
    for _,m in mix.iterrows():
     pg=g[(g.pool_id==m.pool_id)&g.pure&g.class_counts.map(lambda v:set(json.loads(v))<=set(rule['mixture']))]
     if len(pg)!=len(rule['mixture']):continue
     links.append(dict(rule_id=rule['rule_id'],mixture_composition_id=m.composition_id,pure_composition_ids=pg.composition_id.tolist()))
  else:
   links=requests['rule_links'];capacities.extend(dict(x,phase=phase) for x in requests['ledger'])
  bymix=contrasts.set_index('composition_id')
  for link in links:
   cid=link['mixture_composition_id']
   if cid not in comp_lookup.index:continue
   mix=comp_lookup.loc[cid]
   if cid in bymix.index:
    z=bymix.loc[cid].to_dict();z.update(rule_id=link['rule_id'],phase=phase,
     within_joint_stable_main=mix.within_joint_stable_main,within_geometry_noQ_main=mix.within_geometry_noQ_main,
     within_abs_B8L2_change=mix.within_abs_B8L2_change,within_floor_jaccard_difference=mix.within_floor_jaccard_difference,
     mixture_Q=mix.B8L2_mean,mixture_D=mix.D10_mean,mixture_Q_min=mix.Q_min,mixture_Q_p10=mix.Q_p10,
     mixture_teams=int(mix.actual_teams),mixture_scored_teams=int(mix.B8L2_available_n))
    rows.append(z)
   for pcid in link['pure_composition_ids']:
    if pcid not in comp_lookup.index:continue
    p=comp_lookup.loc[pcid]
    z=dict(rule_id=link['rule_id'],phase=phase,pool_id=mix.pool_id,image=mix.image,building=mix.building,
     mixture_composition_id=cid,pure_composition_id=pcid,mixture_counts=mix.class_counts,pure_counts=p.class_counts,
     n=int(mix.n),pure_teams=int(p.actual_teams),mixture_teams=int(mix.actual_teams),
     mixture_minus_pure_Q=mix.B8L2_mean-p.B8L2_mean,mixture_minus_pure_D=mix.D10_mean-p.D10_mean,
     mixture_minus_pure_min_Q=mix.Q_min-p.Q_min,mixture_minus_pure_p10_Q=mix.Q_p10-p.Q_p10,
     mixture_complete_fraction=mix.complete_fraction,pure_complete_fraction=p.complete_fraction,
     all_arms_complete=mix.complete_fraction==1 and p.complete_fraction==1,
     within_main_mixture=mix.within_joint_stable_main,within_main_pure=p.within_joint_stable_main,
     within_noQ_mixture=mix.within_geometry_noQ_main,within_noQ_pure=p.within_geometry_noQ_main)
    pure_rows.append(z)
  events=requests['events']
  for rule in spec['rules']:
   matched=[e for e in events if e['method_id']==rule['method_id'] and e['domain']==rule['domain'] and e['n']==rule['n'] and
    (e['class_counts']==rule['mixture'] or (len(e['class_counts'])==1 and set(e['class_counts'])<=set(rule['mixture'])))]
   team_support.append(dict(phase=phase,rule_id=rule['rule_id'],team_rows=len(matched),unique_teams=len({e['team_key'] for e in matched}),
    workers=len({w for e in matched for w in e['workers']}),images=len({e['image'] for e in matched}),pools=len({e['pool_id'] for e in matched}),buildings=len({e['building'] for e in matched})))
 frame=pd.DataFrame(rows);pures=pd.DataFrame(pure_rows)
 csv_write(frame,a.out/'all_frozen_ratio_image_results.csv.gz');csv_write(pures,a.out/'each_pure_comparator.csv.gz')
 csv_write(pd.DataFrame(team_support),a.out/'actual_team_support.csv');csv_write(pd.DataFrame(capacities),a.out/'capacity_ledger.csv.gz')
 metrics=['mixture_minus_best_pure_Q','mixture_complete_fraction','pure_min_complete_fraction','mixture_min_minus_best_pure_min',
  'within_joint_stable_main','within_geometry_noQ_main','within_abs_B8L2_change','within_floor_jaccard_difference','mixture_Q','mixture_D']
 summaries=[]
 for band,g in [('all_available',frame),('all_arms_complete',frame[frame.all_arms_complete])]:
  t=mean_summary(g,['phase','rule_id'],metrics);t['evaluation_band']=band;summaries.append(t)
 csv_write(pd.concat(summaries,ignore_index=True),a.out/'frozen_ratio_summary.csv')
 csv_write(mean_summary(pures,['phase','rule_id','pure_counts'],['mixture_minus_pure_Q','mixture_minus_pure_D','mixture_minus_pure_min_Q','mixture_complete_fraction','pure_complete_fraction']),a.out/'pure_direction_summary.csv')
 pivot=frame.pivot(index=['rule_id','image','building','pool_id'],columns='phase',values='mixture_minus_best_pure_Q').reset_index()
 csv_write(pivot,a.out/'same_image_new_member_replication.csv')
 oldwinners=frame[frame.phase=='discovery'].sort_values('mixture_minus_best_pure_Q',ascending=False).groupby('rule_id').head(1)
 tracking=oldwinners[['rule_id','image','building','pool_id']].merge(pivot,on=['rule_id','image','building','pool_id'],how='left')
 csv_write(tracking,a.out/'discovery_winners_followed_without_reselection.csv')
 write(a.out/'ANALYSIS_RECEIPT.json',dict(rules=len(spec['rules']),all_rule_image_comparisons=len(frame),pure_direction_comparisons=len(pures),
  weighting='Within image, then images equally within building, then equal buildings. No missing score replaced by zero. Complete-only sensitivity shown next to all available conditional scores; failures retained separately.',
  evidence='All five frozen hypotheses and all supporting images retained. Best observed pure mean is a descriptive competitor benchmark, not an oracle personnel selector. New member draws on old images are not new independent images.',
  within_metric='Ratio panel uses frozen legacy strict/main/wide and no-Q node-count rule, continuous floor difference and height-prism proxy; the revised shape rule is evaluated separately on the equal-m ABC and mixed challenges.'))
 print(frame.groupby(['phase','rule_id']).size().to_dict())

if __name__=='__main__':main()
