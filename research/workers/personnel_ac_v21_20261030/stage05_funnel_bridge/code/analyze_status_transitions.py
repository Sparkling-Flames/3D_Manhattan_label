"""Retain exact output-state transitions instead of only missing-Q risk deltas.

All registered data domains are reported separately. Method events, links,
physical endpoint pairs and unique teams have explicit, distinct denominators.
"""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,gzip,json,time
import pandas as pd

OUT=Path(__file__).resolve().parents[1];BASE=OUT.parent
FLAGS=['Q_missing','fusion_execution_exception','fusion_structural_failure','output_invalid_geometry',
       'fusion_failure_observed','measurement_exception','reference_floor_only','output_not_complete']

def truth(x):return str(x).lower() in ['true','1','1.0']
def status(v):return '<missing_raw_status>' if pd.isna(v) or str(v)=='' else str(v)
def label(v):
 return {'complete_conditional':'可评分的条件完整输出','below_four':'入选节点少于四个',
  'no_connection':'未形成可用点序列（legacy no_connection）',
  'invalid_floor':'底面几何无效','invalid_full_geometry':'完整几何无效',
  'measurement_exception':'指标测量异常','floor_only_reference':'仅底面参考',
  'fusion_exception':'融合执行异常','two_person_deferred':'两人队延后评价'}.get(v,v)
def save(records,path):
 data=pd.DataFrame(records);path.parent.mkdir(parents=True,exist_ok=True)
 with (gzip.open(path,'wt',encoding='utf-8-sig',newline='') if path.name.endswith('.gz') else open(path,'w',encoding='utf-8-sig',newline='')) as f:data.to_csv(f,index=False)
def pattern(a,c):
 aq,cq=a[2],c[2]
 if not aq and not cq:return 'both_Q_present'
 if not aq and cq:return 'Q_missing_introduced'
 if aq and not cq:return 'Q_missing_resolved'
 return 'both_Q_missing_same_output_state' if a[0]==c[0] else 'both_Q_missing_different_output_states'

def main(args):
 start=time.monotonic();dest=OUT/args.output_subdir if args.output_subdir else OUT
 dest.mkdir(parents=True,exist_ok=True)
 registered=BASE/'stage01_registered/AC_EVENTS.csv.gz'
 index=pd.read_csv(registered,usecols=['event_id','pool_id'],low_memory=False)
 expected={pid:set(g.event_id) for pid,g in index.groupby('pool_id')}
 links=pd.read_csv(BASE/'stage01_registered/DESIGN_LINKS.csv.gz',usecols=['event_id','design_family','input_orientation_sign'],low_memory=False).drop_duplicates()
 assert links.input_orientation_sign.isin([-1,1]).all()
 linkmap=defaultdict(list)
 for r in links.itertuples(index=False):linkmap[r.event_id].append((r.design_family,int(r.input_orientation_sign)))
 del links,index
 by_cell=Counter();by_family=Counter();examples={};endpoint_seen={};physical_seen={};poolmeta={};pending=[];events=0;family_occurrences=0;raw_codes=set()
 cell_keys=['pool_id','method','source_class','target_class','n_A','n_C','m_X','m_Z','D_n','A_output_state','C_output_state','A_score_status','C_score_status',
            *['A_'+f for f in FLAGS],*['C_'+f for f in FLAGS],'missing_Q_transition_pattern']
 family_keys=['pool_id','method','design_family','input_source_class','input_target_class','input_n_A','input_n_C','input_m_X','input_m_Z','D_n',
              'A_output_state','C_output_state','A_score_status','C_score_status',*['A_'+f for f in FLAGS],*['C_'+f for f in FLAGS],'missing_Q_transition_pattern']
 cols=['event_id','physical_pair_id','pool_id','image','building','scope','condition','layer','method','source_class','target_class',
       'A_team_key','C_team_key','n_A_actual','n_C_actual','X_n_actual','Z_n_actual','D_n_actual',
       'A_output_state','C_output_state','A_score_status','C_score_status',*[arm+'_'+f for arm in ['A','C'] for f in FLAGS]]
 for i,(pid,ids) in enumerate(sorted(expected.items())):
  path=BASE/'stage04_metrics/metric_shards'/(pid+'.csv.gz')
  if not path.exists():pending.append(pid);continue
  frame=pd.read_csv(path,usecols=cols,low_memory=False)
  assert len(frame)==len(ids) and set(frame.event_id)==ids
  for r in frame.to_dict('records'):
   events+=1;assert r['pool_id']==pid
   meta={k:r[k] for k in ['pool_id','image','building','scope','condition','layer']}
   if pid in poolmeta:assert poolmeta[pid]==meta
   else:poolmeta[pid]=meta
   a=(status(r['A_output_state']),status(r['A_score_status']),*[truth(r['A_'+f]) for f in FLAGS])
   c=(status(r['C_output_state']),status(r['C_score_status']),*[truth(r['C_'+f]) for f in FLAGS])
   raw_codes.update([a[1],c[1]])
   for arm,ss in [('A',a),('C',c)]:
    key=r[arm+'_team_key'];value=(pid,ss)
    if key in endpoint_seen:assert endpoint_seen[key]==value,(key,'inconsistent_endpoint_state')
    else:endpoint_seen[key]=value
   lo,hi=sorted([r['A_team_key'],r['C_team_key']]);physical=(pid,lo,hi)
   if r['physical_pair_id'] in physical_seen:assert physical_seen[r['physical_pair_id']]==physical
   else:physical_seen[r['physical_pair_id']]=physical
   nA,nC,xn,zn,dn=[int(r[k]) for k in ['n_A_actual','n_C_actual','X_n_actual','Z_n_actual','D_n_actual']]
   assert nA==xn+dn and nC==zn+dn
   state_fields=(a[0],c[0],a[1],c[1],*a[2:],*c[2:],pattern(a,c))
   key=(pid,r['method'],str(r['source_class']) if pd.notna(r['source_class']) else '',str(r['target_class']) if pd.notna(r['target_class']) else '',nA,nC,xn,zn,dn,*state_fields)
   by_cell[key]+=1;examples.setdefault(('cell',key),r['event_id'])
   assert r['event_id'] in linkmap,(r['event_id'],'missing_design_link')
   for family,sign in linkmap[r['event_id']]:
    family_occurrences+=1
    aa,cc=(a,c) if sign==1 else (c,a)
    s,t=(key[2],key[3]) if sign==1 else (key[3],key[2])
    nnA,nnC,xx,zz=(nA,nC,xn,zn) if sign==1 else (nC,nA,zn,xn)
    state=(aa[0],cc[0],aa[1],cc[1],*aa[2:],*cc[2:],pattern(aa,cc))
    fk=(pid,r['method'],family,s,t,nnA,nnC,xx,zz,dn,*state)
    by_family[fk]+=1;examples.setdefault(('family',fk),r['event_id'])
  if i%30==0:print(json.dumps({'phase':'state_transitions','pools':len(poolmeta),'method_events':events,'physical_pairs':len(physical_seen)}),flush=True)
 if pending and not args.partial:raise RuntimeError(f'{len(pending)} pools pending; no final status summary written')
 cell_rows=[]
 for key,count in by_cell.items():
  row=dict(zip(cell_keys,key));row.update(poolmeta[key[0]],method_events=count,example_event_id=examples['cell',key],orientation='canonical_event_A_to_C')
  row['both_Q_missing_despite_zero_Q_missing_risk_change']=row['A_Q_missing'] and row['C_Q_missing']
  row['both_observed_fusion_failures']=row['A_fusion_failure_observed'] and row['C_fusion_failure_observed']
  row['A_output_state_label_zh']=label(row['A_output_state']);row['C_output_state_label_zh']=label(row['C_output_state'])
  cell_rows.append(row)
 save(cell_rows,dest/'OUTPUT_STATE_TRANSITIONS_BY_POOL_METHOD_NM.csv.gz')
 family_rows=[]
 for key,count in by_family.items():
  row=dict(zip(family_keys,key));row.update(poolmeta[key[0]],distinct_method_event_orientation_occurrences=count,
       example_event_id=examples['family',key],orientation='original_design_link_input_A_to_C')
  row['both_Q_missing_despite_zero_Q_missing_risk_change']=row['A_Q_missing'] and row['C_Q_missing']
  row['A_output_state_label_zh']=label(row['A_output_state']);row['C_output_state_label_zh']=label(row['C_output_state'])
  family_rows.append(row)
 save(family_rows,dest/'OUTPUT_STATE_TRANSITIONS_BY_DESIGN_FAMILY_INPUT_DIRECTION.csv.gz')
 # Physical pair orientation uses lexicographic native team-key order solely
 # for identity consistency; it must not be called a treatment direction.
 global_counts=Counter();global_pools=defaultdict(set);global_buildings=defaultdict(set);global_examples={}
 for physical_id,(pid,lo,hi) in physical_seen.items():
  a=endpoint_seen[lo][1];c=endpoint_seen[hi][1];meta=poolmeta[pid]
  key=(meta['condition'],meta['layer'],meta['scope'],a[0],c[0],a[1],c[1],*a[2:],*c[2:],pattern(a,c))
  global_counts[key]+=1;global_pools[key].add(pid);global_buildings[key].add(meta['building']);global_examples.setdefault(key,(physical_id,lo,hi))
 gkeys=['condition','layer','scope','low_key_output_state','high_key_output_state','low_key_score_status','high_key_score_status',
        *['low_key_'+f for f in FLAGS],*['high_key_'+f for f in FLAGS],'missing_Q_transition_pattern_in_key_order']
 global_rows=[]
 for key,count in global_counts.items():
  row=dict(zip(gkeys,key));example=global_examples[key]
  row.update(unique_physical_pairs=count,target_pools=len(global_pools[key]),buildings=len(global_buildings[key]),
    low_key_output_state_label_zh=label(row['low_key_output_state']),high_key_output_state_label_zh=label(row['high_key_output_state']),
    unordered_output_states=' | '.join(sorted([row['low_key_output_state'],row['high_key_output_state']])),
    both_Q_missing_despite_zero_Q_missing_risk_change=row['low_key_Q_missing'] and row['high_key_Q_missing'],
    both_observed_fusion_failures=row['low_key_fusion_failure_observed'] and row['high_key_fusion_failure_observed'],
    example_physical_pair_id=example[0],example_low_team_key=example[1],example_high_team_key=example[2],
    orientation='native_team_key_order_only_not_class_or_treatment_direction')
  global_rows.append(row)
 save(global_rows,dest/'GLOBAL_DEDUPLICATED_PHYSICAL_PAIR_OUTPUT_STATES.csv')
 team_counts=Counter();team_pools=defaultdict(set);team_examples={}
 for tk,(pid,state) in endpoint_seen.items():
  meta=poolmeta[pid];key=(meta['condition'],meta['layer'],meta['scope'],*state)
  team_counts[key]+=1;team_pools[key].add(pid);team_examples.setdefault(key,tk)
 tkeys=['condition','layer','scope','output_state','score_status',*FLAGS]
 team_rows=[dict(zip(tkeys,key),unique_requested_teams=count,target_pools=len(team_pools[key]),example_team_key=team_examples[key],output_state_label_zh=label(key[3])) for key,count in team_counts.items()]
 save(team_rows,dest/'UNIQUE_REQUESTED_TEAM_OUTPUT_STATE_COUNTS.csv')
 method_both_missing=sum(count for key,count in by_cell.items() if key[-1].startswith('both_Q_missing'))
 physical_both_missing=sum(r['unique_physical_pairs'] for r in global_rows if r['both_Q_missing_despite_zero_Q_missing_risk_change'])
 physical_different_missing=sum(r['unique_physical_pairs'] for r in global_rows if r['missing_Q_transition_pattern_in_key_order']=='both_Q_missing_different_output_states')
 receipt={'complete':not pending,'pending_pools':pending,'measured_target_pools':len(poolmeta),'method_events':events,
   'physical_pairs':len(physical_seen),'unique_teams':len(endpoint_seen),'design_family_event_orientation_occurrences':family_occurrences,
   'pool_method_n_m_state_cells':len(cell_rows),'family_input_direction_state_cells':len(family_rows),'global_physical_state_cells':len(global_rows),
   'both_Q_missing_method_events':method_both_missing,'both_Q_missing_physical_pairs':physical_both_missing,
   'both_Q_missing_different_output_states_physical_pairs':physical_different_missing,'raw_score_status_codes':sorted(raw_codes),
   'physical_and_team_state_identity_consistency_passed':True,'no_Q_imputation':True,'new_fusions':0,'new_scores':0,
   'legacy_no_connection_means_no_usable_candidate_points_not_proof_of_pure_connection_failure':True,
   'denominator_notes':['Pool/method table counts canonical method events.',
    'Design-family table deduplicates event/family/input-sign links, restores the design input orientation, and is not additive across families.',
    'Global table counts each unordered physical endpoint pair once; its low/high key order has no treatment meaning.',
    'Unique-team table counts each requested native endpoint once; pairs sharing that endpoint are not independent teams.',
    'Two missing-Q arms can have zero risk change, including distinct failure or reference/measurement states; raw output-state combinations remain explicit.'],
   'seconds':time.monotonic()-start}
 (dest/'OUTPUT_STATE_TRANSITION_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in receipt.items() if k not in ['pending_pools','denominator_notes']},ensure_ascii=False,indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--partial',action='store_true');p.add_argument('--output-subdir');main(p.parse_args())
