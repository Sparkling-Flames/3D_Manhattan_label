"""Finite member census for the one retained P05 same-image mechanism.

This is an outcome-motivated mechanism investigation, not another validation set.
All teams are fused; the much larger mixed-team pair space is sampled explicitly.
"""
from __future__ import annotations
import argparse,collections,datetime,hashlib,itertools,math,random,sys
from pathlib import Path
from design_history_panel import read,write,digest,team_key
from design_blocks import labels_from,counts
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'interchangeability_20261020/independent'))
import pair_diagnostics

def design(a):
 spec=read(a.freeze);rule=next(r for r in spec['rules'] if r['rule_id']=='P05')
 pool=next(p for p in read(a.snapshot)['images'] if p['pool_id']==a.pool)
 mapping=labels_from(a.labels)[rule['method_id'],rule['domain']]
 workers=sorted(r['worker_id'] for r in pool['records'] if r['worker_id'] in mapping and r['origin']=='new')
 groups={c:[w for w in workers if mapping[w]==c] for c in sorted(set(mapping.values()))}
 events=[];requests={};ledger=[]
 for vector in [rule['mixture']]+[{c:rule['n']} for c in sorted(rule['mixture'])]:
  v=sorted(vector.items());cid='LC20_'+digest([a.pool,rule['method_id'],v])[:22]
  pop=math.prod(math.comb(len(groups[c]),n) for c,n in v)
  for i,parts in enumerate(itertools.product(*[itertools.combinations(groups[c],n) for c,n in v])):
   ws=sorted(sum((list(x) for x in parts),[]));tk=team_key(a.pool,ws)
   assert counts(ws,mapping)==vector
   requests[tk]=dict(request_id=tk,pool_id=a.pool,k=rule['n'],worker_ids=ws)
   events.append(dict(event_id=cid+'_'+str(i),composition_id=cid,phase='outcome_motivated_finite_census',method_id=rule['method_id'],domain=rule['domain'],
    pool_id=a.pool,image=pool['meta']['image'],building=pool['meta']['building'],difficulty=pool['meta']['difficulty'],reference_id=pool['meta']['reference_id'],
    n=rule['n'],class_counts=vector,pure=len(v)==1,replicate=i,team_key=tk,workers=ws,concrete_population=str(pop),sampling='all_concrete_teams'))
  ledger.append(dict(composition_id=cid,class_counts=vector,population=pop,teams_enumerated=pop,
   pair_population=math.comb(pop,2),pair_evaluation='all_pairs_if_le2000_else_seeded_2000_distinct_pairs',pair_seed=2026102033))
 registration=dict(frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),rule=rule,pool_id=a.pool,
  purpose='P05 remained positive in a second set of 16 concrete teams on jtcx-03. Check the entire finite population for this one mechanism; do not call outcome-driven expansion independent confirmation.',
  reference_fusion_score_unchanged=True,known_class_capacities={c:len(ws) for c,ws in groups.items()},
  pair_seed=2026102033,pair_limit=2000,complete_team_enumeration=True,
  rule_freeze_sha256=hashlib.sha256(a.freeze.read_bytes()).hexdigest())
 write(a.out,dict(spec=registration,requests=list(requests.values()),events=events,ledger=ledger))
 print(dict(teams=len(requests),compositions=len(ledger),ledger=ledger))

def summarize(a):
 sys.path.insert(0,str(Path(__file__).parent));from summarize_blocks import csv_write
 data=read(a.requests);a.out.mkdir(parents=True,exist_ok=True);pid=data['spec']['pool_id'];native=read(a.native/'pools'/(pid+'.json.gz'))
 bykey={t['team_key']:t for t in native['teams']};groups=collections.defaultdict(list);teams=[];summaries=[];pairs=[];cache={}
 for e in data['events']:
  t=bykey[e['team_key']];assert t['member_workers']==e['workers']
  groups[e['composition_id']].append((e,t))
  teams.append(dict(event_id=e['event_id'],composition_id=e['composition_id'],team_key=e['team_key'],workers='|'.join(e['workers']),
   **{k:t.get(k) for k in ['B8L2','D10','IoU3D100','nodes','omission','extension','complete_evaluable','score_status','ref_node_recall_9','ref_edge_recall_9','source_time_total_seconds']}))
 for cid,entries in groups.items():
  num=len(entries);population=math.comb(num,2);target=min(2000,population)
  if population<=2000:indices=list(itertools.combinations(range(num),2))
  else:
   rng=random.Random(int(digest([data['spec']['pair_seed'],cid])[:16],16));seen=set()
   while len(seen)<target:seen.add(tuple(sorted(rng.sample(range(num),2))))
   indices=sorted(seen)
  qp=[]
  for i,j in indices:
   left,right=entries[i][1],entries[j][1]
   if len(cache)>850:cache.clear()
   p=pair_diagnostics.pair_metrics(left,right,cache=cache)
   z=dict(composition_id=cid,a_team_key=left['team_key'],b_team_key=right['team_key'],pair_population=population,actual_pairs_evaluated=target)
   for k in ['both_complete','turnover','B8L2_change','abs_B8L2_change','joint_stable_main','geometry_noQ_main','geometry_shape_main','floor_jaccard_difference','bottom_y_absdiff_deg_p95','top_y_absdiff_deg_p95','mean_height_prism_pair_iou']:
    z[k]=p.get(k)
   pairs.append(z);qp.append(z)
  f=pd.DataFrame([x for x in teams if x['composition_id']==cid]);q=pd.to_numeric(f.B8L2,errors='coerce');pq=pd.DataFrame(qp)
  row=dict(composition_id=cid,class_counts=entries[0][0]['class_counts'],all_concrete_teams=num,all_scored_teams=int(q.notna().sum()),
   complete_fraction=float(f.complete_evaluable.mean()),B8L2_mean=q.mean(),D10_mean=pd.to_numeric(f.D10,errors='coerce').mean(),
   Q_min=q.min(),Q_p10=q.quantile(.1),Q_p90=q.quantile(.9),Q_population_sd=q.std(ddof=0),pair_population=population,pairs_evaluated=target)
  for k in ['joint_stable_main','geometry_noQ_main','geometry_shape_main','abs_B8L2_change','floor_jaccard_difference','bottom_y_absdiff_deg_p95','top_y_absdiff_deg_p95']:
   row['within_'+k]=pd.to_numeric(pq[k],errors='coerce').mean()
  summaries.append(row)
 csv_write(pd.DataFrame(teams),a.out/'finite_team_evidence.csv.gz');csv_write(pd.DataFrame(summaries),a.out/'finite_population_summary.csv')
 frame=pd.DataFrame(pairs);csv_write(frame,a.out/'declared_pair_sample.csv.gz')
 cols=['joint_stable_main','geometry_noQ_main','geometry_shape_main','abs_B8L2_change','floor_jaccard_difference']
 csv_write(frame.groupby(['composition_id','turnover'])[cols].agg(['size','mean']).reset_index(),a.out/'within_by_actual_turnover.csv')
 write(a.out/'CENSUS_RECEIPT.json',dict(exact_teams=len(teams),images=1,buildings=1,workers=len({w for e in data['events'] for w in e['workers']}),
  complete_team_population=True,pairs_evaluated=len(pairs),pair_sampling='Each pure population enumerated; mixed population sampled to 2000 distinct seeded pairs. Pair counts are not independent images.',
  request_sha256=hashlib.sha256(a.requests.read_bytes()).hexdigest(),native_sha256=hashlib.sha256((a.native/'pools'/(pid+'.json.gz')).read_bytes()).hexdigest()))
 print(pd.DataFrame(summaries).to_string(index=False))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['design','summarize']);ap.add_argument('--snapshot',type=Path);ap.add_argument('--freeze',type=Path)
 ap.add_argument('--labels',type=Path,action='append');ap.add_argument('--pool');ap.add_argument('--requests',type=Path);ap.add_argument('--native',type=Path);ap.add_argument('--out',type=Path,required=True)
 a=ap.parse_args();design(a) if a.mode=='design' else summarize(a)
if __name__=='__main__':main()
