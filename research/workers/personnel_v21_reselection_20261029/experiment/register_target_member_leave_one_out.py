"""All six target-member deletions from one score-blind focus anchor per pool.

The original n12 A remains exactly fixed. Returning one source worker into D
creates a valid m5 design with one fixed same-class B5 and six C5 alternatives.
It is not a new m6 same-class experiment and does not change anyone's label.
"""
from __future__ import annotations
import argparse,collections,hashlib,json
from pathlib import Path
import pandas as pd
from capacity_space import read_json,read_labels,capacities,canonical_hash,write_csv
from register_adaptive import members,key,make_event,write_json

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--events',required=True);ap.add_argument('--labels',required=True);ap.add_argument('--pools',nargs='+',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
 out=Path(a.output);out.mkdir(parents=True,exist_ok=True);old=pd.read_csv(a.events,low_memory=False)
 g=old[(old.method=='OPPJOINT_K4')&(old.n==12)&(old.m==6)&(old.design=='strict_disjoint_ABC')]
 anchors=g.sort_values('event_id').drop_duplicates('pool_id');assert len(anchors)==56
 pools={p['pool_id']:p for fn in a.pools for p in read_json(fn)['images']};L=collections.defaultdict(list)
 for r in read_labels(a.labels):L[r['method'],r['heldout_building']].append(r)
 frozen=dict(selection_phase='post_focus_target_member_leave_one_out_m5',anchor_selection='minimum lexical event_id within each actually supported focus OPPJOINT_K4 n12/m6 pool; no outcome input',
  original_events_sha256=hashlib.sha256(Path(a.events).read_bytes()).hexdigest(),labels_sha256=hashlib.sha256(Path(a.labels).read_bytes()).hexdigest(),
  data_release='v2.1',source_commit='a476461d7ede8db95da43de4139e612c05e618bc',n=12,m=5,old_anchor_m=6,all_six_target_deletions_exhausted=True,labels_changed=False)
 write_json(out/'FROZEN_DESIGN.json',frozen);events=[];requests={};links=[];arows=[]
 for anchor in anchors.to_dict('records'):
  pid=anchor['pool_id'];p=pools[pid];groups=capacities(p,L[anchor['method'],anchor['heldout_building']])
  D,X,Y,Z=[members(anchor[q]) for q in ['D','X','Y','Z']];assert len(X)==len(Y)==len(Z)==6 and len(D)==6
  returned=X[-1];omitted_Y=Y[-1];d=sorted(D+[returned]);x=X[:-1];y=Y[:-1]
  fixedB=key(pid,sorted(d+y));arows.append(dict(anchor_event_id=anchor['event_id'],pool_id=pid,image=anchor['image'],building=anchor['building'],
   method=anchor['method'],source_class=anchor['source_class'],target_class=anchor['target_class'],n=12,old_m=6,new_m=5,
   A_team_key=anchor['A_team_key'],old_B6_team_key=anchor['B_team_key'],old_C6_team_key=anchor['C_team_key'],B5_team_key=fixedB,
   source_returned_to_D=returned,source_omitted_from_Y=omitted_Y,old_D='|'.join(D),old_X6='|'.join(X),old_Y6='|'.join(Y),old_Z6='|'.join(Z),
   D5='|'.join(d),X5='|'.join(x),Y5='|'.join(y)))
  for omitted in Z:
   z=[w for w in Z if w!=omitted];cell=dict(anchor,m=5,selection_phase=frozen['selection_phase'])
   ev,teams=make_event(p,cell,groups,x,y,z,d,0,0,'fixed_anchor_target_leave_one_out',anchor['event_id'],design='strict_disjoint_ABC_target_member_leave_one_out_m5')
   assert ev['A_team_key']==anchor['A_team_key'] and ev['B_team_key']==fixedB
   ev.update(anchor_m6_event_id=anchor['event_id'],omitted_target_worker=omitted,source_returned_to_D=returned,source_omitted_from_Y=omitted_Y)
   events.append(ev);links.append(dict(event_id=ev['event_id'],anchor_event_id=anchor['event_id'],pool_id=pid,omitted_target_worker=omitted,old_C6_team_key=anchor['C_team_key'],
    new_C5_team_key=ev['C_team_key'],A_team_key=ev['A_team_key'],B5_team_key=fixedB,actual_m=5,original_m=6))
   for arm,ws in teams.items():
    tk=ev[arm+'_team_key'];requests[tk]=dict(team_key=tk,pool_id=pid,n=12,member_workers='|'.join(ws),input_pool_sha256=canonical_hash(p))
 assert len(events)==336 and len({e['event_id'] for e in events})==336
 write_csv(out/'EVENTS_EXACT.csv.gz',events);write_csv(out/'REQUESTS.csv.gz',requests.values());write_csv(out/'ANCHORS_EXACT.csv.gz',arows);write_csv(out/'TARGET_LEAVE_ONE_OUT_LINKS.csv.gz',links)
 write_json(out/'DESIGN.json',dict(frozen,pools=len(anchors),events=len(events),unique_teams=len(requests),same_A_and_B5_across_six_choices=True,
   interpretation='Within the selected direction, target-block membership sensitivity at m5; comparison with old C6 also changes returned-source membership and must be described as such.'))
 print(json.dumps(dict(pools=len(anchors),events=len(events),unique_teams=len(requests))),flush=True)
if __name__=='__main__':main()
