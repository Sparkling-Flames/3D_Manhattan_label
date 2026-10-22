"""Explain seven new actual events; replay states only, never alter or rescore."""
from pathlib import Path
import collections,gzip,importlib.util,json,sys
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent;STUDY=HERE.parent;ROOT=HERE.parents[3]
sys.path.insert(0,str(STUDY));import run_native_closure as core
core.configure();gs=core.gs
SPECS=[
 ('manual_position','structure','f1aae22f42dbc5c89e5b1d44','同样角点数量：定位改善'),
 ('manual_structure','structure','f6893bb1710e29da5802f39c','同图结构补充：换入较多转折类别'),
 ('manual_threshold20','structure','657a556b4b2e3e316cf60198','固定成员块：20人团队'),
 ('manual_threshold21','structure','268b3f37b6543564e1677b19','固定成员块：21人团队'),
 ('manual_failure','structure','09b26209b5f3289de09fd298','同图反例：换类后的融合失败'),
 ('semi_position_gain','semi','b811ba12eb7033aa4cf18f8a','Semi：定位改善与记录时间收益'),
 ('semi_same_target_loss','semi','e5b0e465f554e1dd3b313418','Semi：同一个目标块的质量反例')]

def angular(a,b):
 def ray(p):
  p=np.asarray(p,float);u=2*np.pi*(p[:,0]/1024-.5);v=np.pi*(.5-p[:,1]/512)
  return np.c_[np.cos(v)*np.sin(u),np.sin(v),-np.cos(v)*np.cos(u)]
 return np.rad2deg(np.arccos(np.clip(ray(a)@ray(b).T,-1,1)))

def main():
 pools=gs.pool_lookup();fe,_,_,_=gs.setup_engine();labels=pd.read_csv(ROOT/'research/workers/personnel_useful_taxonomy_v3_20261021/taxonomy/ALL_METHOD_LABELS_LOBO.csv.gz',keep_default_na=False)
 requests={}
 for line in ['structure','semi']:
  path=STUDY/line/'EVENTS_COMPLETE.csv.gz';wanted={s[2] for s in SPECS if s[1]==line}
  for chunk in pd.read_csv(path,keep_default_na=False,chunksize=1000):
   requests.update((r['event_id'],r) for r in chunk[chunk.event_id.isin(wanted)].to_dict('records'))
 tables=collections.defaultdict(list);receipts=[]
 with fe.cached_matching():
  for cid,line,eid,title in SPECS:
   e=requests[eid];pool=pools[e['pool_id']];by={r['worker_id']:r for r in pool['records']};method='V3_BEHAVIOR' if line=='structure' else 'V3_JOINT_QT'
   ll=labels[(labels.condition==e['condition'])&(labels.heldout_building==e['building'])&(labels.method==method)];lm=ll.set_index('worker_id').coarse_label.to_dict();native={}
   for p in (STUDY/'native/runtime').glob('*'+('structure' if line=='structure' else 'semi')+'*'+'/'+e['pool_id']+'.json.gz'):
    native.update((t['team_key'],t) for t in gs.read(p)['teams'])
   colors={cl:['#3e78a4','#299678','#be5d63','#955f9a','#c88a3e'][i%5] for i,cl in enumerate(sorted(set(lm.values())))}
   case=dict(case_id=cid,title=title,n=int(e['n']),method_id=method,tier='coarse',event=e,pool_id=e['pool_id'],pool_meta=pool['meta'],image_id=pool['meta']['image_id'],reference=dict(pool['reference'],reference_id=pool['meta']['reference_id']),subtitle=f"{e['condition']} / n={e['n']} / m={e['m_AB']}",class_names={cl:cl for cl in colors},class_colors=colors,selection='Post-result explanatory case; not a separate effect estimator',underlying_data_version='v2',teams=[])
   union=set();ref=np.asarray(pool['reference']['points_1024x512']);bg=set(e['common_background'].split('|'))
   for arm in 'ABC':
    t=dict(native[e['team_'+arm]]);ws=t['member_workers'];union.update(ws)
    state=fe.clean(fe.compact(fe.fuse([by[w] for w in sorted(ws)],gap=fe.WORKING_GAP)['automatic']))
    assert gs.digest(state['candidate'])==gs.digest(t['geometry']),(cid,arm,'geometry mismatch')
    t.update(label=arm,counts=dict(collections.Counter(lm[w] for w in ws)),full_state=state);case['teams'].append(t)
    tables['ENDPOINT_METRICS'].append(dict(case_id=cid,arm=arm,**{k:v for k,v in t.items() if not isinstance(v,(list,dict))}))
    for g in state['identity_groups']:
     center=np.asarray(g['center']);dist=np.maximum(angular(center[:1],ref[::2]),angular(center[1:],ref[1::2]))[0];j=int(np.argmin(dist));mm=g['members']
     tables['GROUP_VOTES'].append(dict(case_id=cid,arm=arm,group=g['feature_id'],support=g['support'],threshold=t['minimum_support'],selected=g['selected'],nearest_reference_corner=j,paired_bound_distance_deg=float(dist[j]),background_votes=sum(m['worker'] in bg for m in mm),member_workers='|'.join(sorted(m['worker'] for m in mm)),class_votes=gs.canonical_counts(collections.Counter(lm[m['worker']] for m in mm)),top_x=center[0,0],top_y=center[0,1],bottom_x=center[1,0],bottom_y=center[1,1]))
     for m in mm:tables['OBSERVATION_ASSIGNMENTS'].append(dict(case_id=cid,arm=arm,group=g['feature_id'],worker=m['worker'],object_id=m['id'],pair_index=m['pair_index'],support=g['support'],selected=g['selected']))
    for ed in state['ring_diagnostics']['edges']:tables['EDGE_VOTES'].append(dict(case_id=cid,arm=arm,node_pair='|'.join(ed['feature_ids']),direct_support=ed['direct_support'],projected_support=ed['projected_support'],direct_workers='|'.join(ed['direct_workers']),projected_workers='|'.join(ed['projected_workers'])))
   case['members']=[dict(by[w],class_id=lm[w],coarse_class=lm[w],fine_class=lm[w]) for w in sorted(union)]
   case['raw_overlay_groups']=[dict(class_id=e['source_class'],workers=e['outgoing_block_X'].split('|'),label='原队源类块X'),dict(class_id=e['source_class'],workers=e['same_count_block_Y'].split('|'),label='同类替换块Y'),dict(class_id=e['target_class'],workers=e['changed_count_block_Z'].split('|'),label='跨类替换块Z')]
   for m in case['members']:tables['EXACT_MEMBERS'].append(dict(case_id=cid,worker_id=m['worker_id'],class_id=m['class_id'],object_id=m['object_id'],pair_count=len(m['points'])//2,in_background=m['worker_id'] in bg,arms='|'.join(t['label'] for t in case['teams'] if m['worker_id'] in t['member_workers'])))
   dest=HERE/'cases'/(cid+'.json.gz');gs.save(dest,case);tables['EXACT_EVENTS'].append(dict(case_id=cid,**e));receipts.append(dict(case_id=cid,event_id=eid,arms=3,geometry_equal_to_saved_endpoint=True,score_calls=0,state_replays=3,sha256=core.frozen.prior.sha(dest)));print(cid,flush=True)
 for name,rows in tables.items():core.frozen.write_csv(HERE/(name+'.csv.gz'),rows)
 gs.save(HERE/'CASE_EXPORT_RECEIPT.json',dict(cases=receipts,score_calls=0,total_state_replays=3*len(receipts),selection='post_result_explanation'))

if __name__=='__main__':main()
