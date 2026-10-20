"""Direct utility/variation of pure and mixed actual member compositions."""
from __future__ import annotations
import argparse,collections,itertools,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
from design_history_panel import read,write
from summarize_blocks import csv_write
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'analysis/composition'))
import summarize_grid as old

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--requests',type=Path,required=True)
 ap.add_argument('--native',type=Path,required=True);ap.add_argument('--snapshot',type=Path,required=True)
 ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 request=read(a.requests);pools={p['pool_id']:p for p in read(a.snapshot)['images']}
 by=collections.defaultdict(list)
 for e in request['events']:by[e['pool_id']].append(e)
 comps=[];teams_out=[];pairs_out=[]
 for pid,events in by.items():
  rows={t['team_key']:t for t in read(a.native/'pools'/(pid+'.json.gz'))['teams']}
  signatures={};ref=pools[pid]['reference']['floor_xz_h'];rcache={};cby=collections.defaultdict(list)
  for e in events:
   t=rows[e['team_key']];assert t['member_workers']==e['workers'] and t['k']==e['n']
   x={k:e[k] for k in ['event_id','composition_id','phase','method_id','domain','pool_id','image','building','difficulty','n','pure','replicate','team_key','sampling','concrete_population']}
   x['class_counts']=json.dumps(e['class_counts'],sort_keys=True,separators=(',',':'))
   for k in ['B8L2','D10','IoU3D100','omission','extension','nodes','complete_evaluable','score_status','source_time_known_n','source_time_total_seconds','target_time_known_n','target_time_total_seconds','ref_node_recall_9','ref_edge_recall_9']:
    x[k]=t.get(k)
   teams_out.append(x);cby[e['composition_id']].append((e,t))
   if t['team_key'] not in signatures:signatures[t['team_key']]=old.signature(t,ref,rcache)
  for cid,entries in cby.items():
   e0=entries[0][0];group=pd.DataFrame([x for x in teams_out[-len(events):] if x['composition_id']==cid])
   pair_values=[]
   for (ea,ta),(eb,tb) in itertools.combinations(entries,2):
    p=old.pair_metrics(ta,tb,signatures[ta['team_key']],signatures[tb['team_key']])
    for name,f,s in [('strict',.02,2),('main',.05,3),('wide',.1,5)]:
     p['geometry_noQ_'+name]=bool(p['both_complete'] and p['node_count_difference']==0 and p['floor_jaccard_difference'] is not None and p['floor_jaccard_difference']<=f and p['structure_bound_cyclic_deg'] is not None and p['structure_bound_cyclic_deg']<=s)
    z=dict(composition_id=cid,pool_id=pid,a_team_key=ta['team_key'],b_team_key=tb['team_key'])
    for k in ['turnover','both_complete','abs_B8L2_change','B8L2_change','floor_jaccard_difference','structure_bound_cyclic_deg','node_count_difference','mean_height_prism_pair_iou','joint_stable_strict','joint_stable_main','joint_stable_wide','geometry_noQ_main']:
     z[k]=p[k]
    pairs_out.append(z);pair_values.append(z)
   out={k:e0[k] for k in ['composition_id','phase','method_id','domain','pool_id','image','building','difficulty','n','pure','sampling','concrete_population']}
   out['class_counts']=json.dumps(e0['class_counts'],sort_keys=True,separators=(',',':'));out['actual_teams']=len(entries)
   out['member_pairs']=len(pair_values);out['complete_fraction']=float(group.complete_evaluable.mean())
   for k in ['B8L2','D10','IoU3D100','omission','extension','nodes','source_time_total_seconds','target_time_total_seconds','ref_node_recall_9','ref_edge_recall_9']:
    vals=pd.to_numeric(group[k],errors='coerce');out[k+'_mean']=float(vals.mean()) if vals.notna().any() else None
    out[k+'_available_n']=int(vals.notna().sum())
   q=pd.to_numeric(group.B8L2,errors='coerce');out['Q_min']=float(q.min()) if q.notna().any() else None
   out['Q_p10']=float(q.quantile(.1)) if q.notna().any() else None
   out['Q_sd']=float(q.std(ddof=1)) if q.notna().sum()>=2 else None
   for k in ['joint_stable_strict','joint_stable_main','joint_stable_wide','geometry_noQ_main','floor_jaccard_difference','abs_B8L2_change','turnover']:
    v=[z[k] for z in pair_values if z[k] is not None];out['within_'+k]=float(np.mean(v)) if v else None
   comps.append(out)
 frame=pd.DataFrame(comps);csv_write(frame,a.out/'composition_evidence.csv.gz')
 csv_write(pd.DataFrame(teams_out),a.out/'exact_team_metrics.csv.gz');csv_write(pd.DataFrame(pairs_out),a.out/'within_composition_pairs.csv.gz')
 contrasts=[]
 for (mid,dom,pid,n),g in frame.groupby(['method_id','domain','pool_id','n']):
  pure=g[g.pure];mixed=g[~g.pure]
  for _,mix in mixed.iterrows():
   counts=json.loads(mix.class_counts);needed=set(counts)
   comparators=pure[pure.class_counts.map(lambda x:set(json.loads(x))<=needed)]
   if len(comparators)!=len(needed):continue
   avail=comparators.B8L2_mean.notna().all() and pd.notna(mix.B8L2_mean)
   best=comparators.loc[comparators.B8L2_mean.idxmax()] if avail else None
   out={k:mix[k] for k in ['composition_id','method_id','domain','pool_id','image','building','difficulty','n','class_counts']}
   out.update(pure_comparator_ids='|'.join(sorted(comparators.composition_id)),
    all_arms_complete=bool(mix.complete_fraction==1 and (comparators.complete_fraction==1).all()),
    all_arms_at_least2_scored=bool(mix.B8L2_available_n>=2 and (comparators.B8L2_available_n>=2).all()),
    best_pure_composition_id=best.composition_id if best is not None else None,
    mixture_minus_best_pure_Q=mix.B8L2_mean-best.B8L2_mean if avail else None,
    mixture_min_minus_best_pure_min=mix.Q_min-best.Q_min if avail else None,
    mixture_source_time_over_best_pure=mix.source_time_total_seconds_mean/best.source_time_total_seconds_mean if avail and pd.notna(mix.source_time_total_seconds_mean) and pd.notna(best.source_time_total_seconds_mean) and best.source_time_total_seconds_mean>0 else None,
    mixture_complete_fraction=mix.complete_fraction,pure_min_complete_fraction=comparators.complete_fraction.min())
   contrasts.append(out)
 contrasts=pd.DataFrame(contrasts);csv_write(contrasts,a.out/'pure_mixture_contrasts.csv.gz')
 write(a.out/'SUMMARY_RECEIPT.json',dict(compositions=len(frame),team_rows=len(teams_out),unique_teams=len({x['team_key'] for x in teams_out}),
  within_composition_pairs=len(pairs_out),images=frame.image.nunique(),buildings=frame.building.nunique(),
  mixture_comparisons_with_all_constituent_pures=len(contrasts),
  inference='Finite resampling from exact supported personnel pools. Same n/reference for pure-mixture quality contrasts; highest observed pure mean is a descriptive discovery benchmark, not an oracle selection rule or held-out causal effect. Actual member pair turnover retained; no identical-m claim for this separate grid. Nulls/failures retained.'))
 print(dict(compositions=len(frame),contrasts=len(contrasts)))

if __name__=='__main__':main()
