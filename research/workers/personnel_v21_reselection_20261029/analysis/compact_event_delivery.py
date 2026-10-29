"""Lossless relational delivery: all events, all arm component deltas, endpoint
reference diagnostics, and all arm-pair geometry. Repeated arm scalar values are
already in the deduplicated endpoint table; algebraic absolute/gap columns can
be reconstructed from BA/CA/CB with the recorded all-arm validity mask.
"""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
import pandas as pd
from measure_registered_events import METRICS,save,jsave

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--measured',required=True);ap.add_argument('--events',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
 root=Path(a.measured);out=Path(a.out);out.mkdir(parents=True,exist_ok=True);es=[];ds=[];gs=[];rds=[]
 diagnostics=['matched_ref_top_abs_deg','matched_ref_bottom_abs_deg','matched_ref_horizontal_abs_deg','matched_ref_pair_fraction','reference_node_shortfall','reference_node_excess']
 for p in sorted((root/'metric_shards').glob('*.csv.gz')):
  d=pd.read_csv(p,low_memory=False)
  keep=[c for c in ['event_id','pool_id','image','building','condition','layer','scope','method','heldout_building','source_class','target_class','n','m','pool_n','selection_phase','background_id','block_id','background_target_n','background_source_n','replacement_fraction','source_candidate_fraction','target_candidate_fraction','A_team_key','B_team_key','C_team_key','official_difficulty','geometric_challenge'] if c in d]
  derived=[c for c in d if (c.endswith(('_BA','_CA','_CB')) and not c.startswith(('A_','B_','C_'))) or c in ['ABC_scored','A_failed','B_failed','C_failed','A_incomplete','B_incomplete','C_incomplete','time_comparable_ABC'] or c.startswith(('record_time_','time_source_signature_'))]
  for m in ['B8L2','D10']:
   derived += [m+s for s in ['_within','_cross','_gap','_AC_absolute','_AC_gap'] if m+s in d]
  cols=list(dict.fromkeys(keep+derived));compact=d[cols].copy()
  compact['source_seats_A']=d.background_source_n+d.m;compact['fraction_of_source_seats_replaced']=d.m/compact.source_seats_A
  compact['target_seats_A']=d.background_target_n;compact['target_seats_C']=d.background_target_n+d.m
  save(out/'event_shards'/p.name,compact);es.append(compact)
  for arm in 'ABC':
   cols=[c for c in diagnostics if arm+'_'+c in d]
   z=d[[arm+'_team_key']+[arm+'_'+c for c in cols]].rename(columns={arm+'_team_key':'team_key',**{arm+'_'+c:c for c in cols}});rds.append(z.drop_duplicates('team_key'))
  pairs=[]
  for aa,bb in [('A','B'),('A','C'),('B','C')]:
   metrics=[c for c in d if c.startswith('geometry_') and c.endswith('_'+aa+bb)]
   z=d[['event_id',aa+'_team_key',bb+'_team_key']+metrics].copy();z['arm_pair']=aa+bb
   z=z.rename(columns={aa+'_team_key':'team_1',bb+'_team_key':'team_2',**{c:c[:-3] for c in metrics}})
   pairids=[];t1=[];t2=[]
   for x,y in zip(z.team_1,z.team_2):
    xx,yy=sorted([x,y]);t1.append(xx);t2.append(yy);pairids.append(hashlib.sha256((xx+'\n'+yy).encode()).hexdigest()[:24])
   z['team_1']=t1;z['team_2']=t2;z['pair_id']=pairids
   pairs.append(z)
  g=pd.concat(pairs,ignore_index=True);ds.append(g[['event_id','arm_pair','pair_id']]);gs.append(g.drop(columns=['event_id','arm_pair']).drop_duplicates('pair_id'))
  print(p.stem,len(d),flush=True)
 e=pd.concat(es,ignore_index=True);original=pd.read_csv(a.events,usecols=['event_id'])
 assert e.event_id.is_unique and set(e.event_id)==set(original.event_id),'Do not publish an incomplete ledger as complete.'
 save(out/'EVENT_EFFECTS_COMPLETE.csv.gz',e)
 pair=pd.concat(gs,ignore_index=True).drop_duplicates('pair_id');links=pd.concat(ds,ignore_index=True);refs=pd.concat(rds,ignore_index=True).drop_duplicates('team_key')
 save(out/'PAIR_GEOMETRY.csv.gz',pair);save(out/'EVENT_PAIR_LINKS.csv.gz',links);save(out/'ENDPOINT_REFERENCE_DIAGNOSTICS.csv.gz',refs)
 valid=[c for c in METRICS if c+'_BA' in e]
 jsave(out/'COMPLETE.json',dict(events=len(e),original_events=len(original),component_metrics_with_all_three_signed_deltas=valid,
  pair_rows=len(pair),event_pair_links=len(links),reference_diagnostics=len(refs),full_event_row_coverage=True,
  score_reconstruction='endpoint scalars + unique endpoint reference diagnostics; all pairwise signed component differences retained',
  amplitude_reconstruction='valid where A,B,C component all known; within=abs(BA), symmetric_cross=(abs(CA)+abs(CB))/2; gap=cross-within',
  source_events=a.events,wide_metric_source=a.measured,geometries_in_separate_batches=True))
 print(json.dumps(dict(events=len(e),components=len(valid),pairs=len(pair))),flush=True)
if __name__=='__main__':main()
