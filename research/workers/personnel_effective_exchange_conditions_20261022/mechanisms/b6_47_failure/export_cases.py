#!/usr/bin/env python3
"""Replay six already-computed native endpoints solely for exact vote states."""
import os
for v in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[v]='1'
import collections,gzip,hashlib,importlib.util,itertools,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
NEW=HERE.parents[1]
ROOT=NEW.parents[2]
OLD=ROOT/'research/workers/personnel_global_composition_20261021'
V3=ROOT/'research/workers/personnel_useful_taxonomy_v3_20261021'
sys.path[:0]=['/tmp/hohonet_deps',str(ROOT),str(OLD/'composition')]
import global_study as gs
from tools.thesis_main.analysis.consensus_delivery_20261008 import fuse,WORKING_GAP
from tools.thesis_main.analysis.wall_consensus_v1_process_20261017 import cached_matching
from tools.thesis_main.analysis.wall_consensus_population_20261014 import compact

SPECS=[dict(case_id='B6_47_invalid_floor_n20_m4',event_id='b9dd6bd002ac8d1aa20cc271',n=20),
 dict(case_id='B6_47_invalid_floor_n22_m4',event_id='bdfb5373fcacd0d5c9ec00eb',n=22)]

def atomic(path,data):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.partial')
 with tmp.open('wb') as h:h.write(data);h.flush();os.fsync(h.fileno())
 os.replace(tmp,path)
def save(path,data):
 raw=json.dumps(gs.clean(data),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
 atomic(path,gzip.compress(raw,mtime=0) if str(path).endswith('.gz') else raw)
def csv(name,d):
 path=HERE/name;raw=d.to_csv(index=False).encode('utf-8-sig')
 atomic(path,gzip.compress(raw,mtime=0) if str(path).endswith('.gz') else raw)
 assert pd.read_csv(path).shape==d.shape
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def counts(s):return {c:int(n) for c,n in [x.split(':') for x in s.split('|')]}

def main():
 source=NEW/'joint_exchange/NATIVE_MANUAL_EVENTS_COMPLETE.csv.gz'
 events=pd.read_csv(source,keep_default_na=False,low_memory=False);events=events[events.event_id.isin([s['event_id'] for s in SPECS])]
 assert len(events)==2;csv('EXACT_EVENTS.csv',events)
 labels_path=V3/'taxonomy/JOINT_LABELS_LOBO.csv.gz';labels=pd.read_csv(labels_path)
 labels=labels[labels.condition.eq('manual')&labels.heldout_building.eq('B6ByNegPMKs')&labels.known]
 csv('TARGET_BUILDING_EXCLUDED_LABELS.csv',labels)
 fields=['q_history','q_downside','t_history','turn_history','short_history','redundancy_history','area_history','height_history','simple_turn_history','complex_turn_history','complex_short_history']
 centers=labels.groupby('coarse_label').agg(members=('worker_id','size'),**{v:(v,'mean') for v in fields}).reset_index();csv('TARGET_BUILDING_EXCLUDED_CENTERS.csv',centers)
 save(HERE/'EXPORT_PROGRESS.json',dict(stage='events_and_labels_saved',score_calls=0,new_endpoints=0))
 pools=gs.pool_lookup();ll=labels.set_index('worker_id');bylabel=ll.coarse_label.to_dict();cases=[];receipts=[];replay_cache={}
 for path in (HERE/'cases').glob('*.json.gz'):
  c=gs.read(path)
  for t in c['teams']:
   assert gs.digest(t['full_state']['candidate'])==gs.digest(t['geometry']);replay_cache[t['team_key']]=t['full_state']
 with cached_matching():
  for spec in SPECS:
   event=events[events.event_id.eq(spec['event_id'])].iloc[0].to_dict();pool=pools[event['pool_id']];byworker={r['worker_id']:r for r in pool['records']}
   native_path=NEW/'expanded_blocks/runtime/joint_001'/(event['pool_id']+'.json.gz');native=gs.read(native_path)
   assert native['pool_input_sha256']==gs.digest(pool);native={t['team_key']:t for t in native['teams']}
   case=dict(spec,title='B6-47：更高历史Q且更快的四席替换产生无效底面',subtitle=f"Manual n={spec['n']} / 同背景、同m=4；失败保留",
    method_id=event['method_id'],tier=event['tier'],event=event,pool_id=event['pool_id'],pool_meta=pool['meta'],image_id=pool['meta']['image_id'],
    reference=dict(pool['reference'],reference_id=pool['meta']['reference_id']),
    class_names={str(r.coarse_label):str(r.coarse_label)+(' 较高Q、较多困难转折' if r.coarse_label=='J5' else ('常规QT/转折' if r.coarse_label=='J2' else '楼外联合类')) for r in centers.itertuples()},
    class_colors={'J1':'#8f4c96','J2':'#2678b5','J3':'#8c6d31','J4':'#b1752c','J5':'#218264'},
    selection='post_result_failure_explanation; original V3 own-Manual joint taxonomy; not new M+S family',
    label_scope='target_B6_building_excluded_V3_JOINT_QT_manual',teams=[])
   union=set();rr=[]
   for arm in 'ABC':
    t=dict(native[event['team_'+arm]]);assert '|'.join(sorted(t['member_workers']))==event[arm+'_member_workers'];assert t['k']==spec['n']
    union.update(t['member_workers']);key=t['team_key'];reuse=key in replay_cache
    if not reuse:replay_cache[key]=gs.clean(compact(fuse([byworker[w] for w in sorted(t['member_workers'])],gap=WORKING_GAP)['automatic']))
    state=replay_cache[key];assert gs.digest(state['candidate'])==gs.digest(t['geometry']),(key,'geometry mismatch')
    assert state['n']==t['k'] and state['minimum_support']==t['minimum_support'] and len(state['node_consensus']['nodes'])==t['nodes']
    expected=counts(event[arm+'_counts']);actual=collections.Counter(bylabel[w] for w in t['member_workers'])
    assert all(actual.get(c,0)==n for c,n in expected.items()) and sum(expected.values())==t['k']
    t.update(label=arm,counts=expected,full_state=state);case['teams'].append(t)
    rr.append(dict(arm=arm,team_key=key,state_reused=reuse,geometry_sha256=gs.digest(t['geometry']),replay_candidate_sha256=gs.digest(state['candidate'])))
   for a,b in itertools.combinations(case['teams'],2):assert len(set(a['member_workers'])-set(b['member_workers']))==4
   case['members']=[dict(byworker[w],class_id=bylabel[w],coarse_class=ll.loc[w,'coarse_label'],fine_class=ll.loc[w,'fine_label']) for w in sorted(union)]
   path=HERE/'cases'/(spec['case_id']+'.json.gz');save(path,case);cases.append(case)
   receipts.append(dict(case_id=spec['case_id'],event_id=spec['event_id'],event_source=str(source.relative_to(ROOT)),event_source_sha256=sha(source),
    native_source=str(native_path.relative_to(ROOT)),native_source_sha256=sha(native_path),pool_sha256=gs.digest(pool),label_sha256=sha(labels_path),replays=rr,output_sha256=sha(path)))
   save(HERE/'CASE_EXPORT_RECEIPT.json',dict(cases=receipts,full_state_replays=len(replay_cache),new_teams=0,score_calls=0,all_native_geometry_exact=True))
   print('saved',spec['case_id'],[(t['label'],t['B8L2'],t['nodes'],t['minimum_support'],t['score_status']) for t in case['teams']],flush=True)
 spec=importlib.util.spec_from_file_location('frozen_vote_transitions',OLD/'evidence/analyze_vote_transitions.py');trans=importlib.util.module_from_spec(spec);spec.loader.exec_module(trans)
 votes=[];metrics=[];members=[];tr=[];links=[]
 for case in cases:
  for t in case['teams']:
   metrics.append(dict(case_id=case['case_id'],arm=t['label'],composition=gs.canonical_counts(t['counts']),**{k:v for k,v in t.items() if not isinstance(v,(dict,list))}))
   for g in t['full_state']['identity_groups']:
    votes.append(dict(case_id=case['case_id'],arm=t['label'],feature_id=g['feature_id'],support=g['support'],threshold=t['minimum_support'],selected=g['selected'],
     top_x=g['center'][0][0],top_y=g['center'][0][1],bottom_x=g['center'][1][0],bottom_y=g['center'][1][1],
     class_votes=gs.canonical_counts(collections.Counter(bylabel[m['worker']] for m in g['members'])),members='|'.join(sorted(m['worker'] for m in g['members'])),
     observations='|'.join(f'{a}:{b}' for a,b in sorted(trans.obs(g)))))
  for m in case['members']:
   members.append(dict(case_id=case['case_id'],worker_id=m['worker_id'],object_id=m['id'],class_id=m['class_id'],origin=m['origin'],target_B8L2=m.get('B8L2'),target_D10=m.get('D10'),
    point_pairs=len(m['points'])//2,source_time_seconds=m.get('source_time_seconds'),time_source_kind=m.get('time_source_kind'),arms='|'.join(t['label'] for t in case['teams'] if m['worker_id'] in t['member_workers'])))
  for a,b in itertools.combinations(case['teams'],2):
   safe=[]
   for t in [a,b]:
    q=dict(t)
    for k in ['B8L2','D10','iou_2d','dir']:
     if q.get(k) is None:q[k]=float('nan')
    safe.append(q)
   trans.analyze_pair(case,*safe,tr,links)
 for fn,rr in [('CASE_ENDPOINT_METRICS.csv',metrics),('EXACT_CASE_MEMBERS.csv',members),('GROUP_CLASS_VOTES.csv',votes),('OBSERVATION_TRANSITIONS.csv',tr),('GROUP_OVERLAP_LINKS.csv',links)]:csv(fn,pd.DataFrame(rr))
 save(HERE/'EXPORT_PROGRESS.json',dict(stage='six_exact_native_states_and_vote_ledgers_complete',full_state_replays=len(replay_cache),new_endpoints=0,score_calls=0))
if __name__=='__main__':main()
