#!/usr/bin/env python3
"""Describe frozen nested OPPJOINT and TARGET_DSTRUCT labels; never refit/fuse."""
from pathlib import Path
import gzip,hashlib,json
import numpy as np
import pandas as pd
W=Path(__file__).resolve().parents[2];O=W/'stage07_adoption';O.mkdir(exist_ok=True)
C=W/'classification';METHODS=['OPPJOINT_K3','OPPJOINT_K4','TARGET_DSTRUCT_K3']
lab=pd.read_csv(C/'MAIN45_LABELS_ALL_LOBO.csv.gz',low_memory=False);lab=lab[lab.method.isin(METHODS)].copy()
hist=pd.read_csv(C/'HISTORY_FEATURES_ALL_LOBO.csv.gz',low_memory=False)
raw=pd.read_csv(C/'RAW_TARGET_RESPONSE_RECORDS.csv.gz',low_memory=False)
raw=raw[raw.history_eligible&raw.condition.eq('manual')].copy()
roles=pd.read_csv(C/'CLASS_ROLES_ALL_LOBO.csv.gz',low_memory=False);roles=roles[roles.method.isin(METHODS)].copy()
config=json.loads((C/'CANDIDATE_CONFIG_BEFORE_TEAM_RESULTS.json').read_text())
supports=['m_all_images','m_all_buildings','m_all_targets','m_all_records','m_timed_images','m_timed_buildings','m_timed_records','m_challenge_images','m_challenge_buildings','m_easy_images','m_easy_buildings','m_hard_images','m_hard_buildings','m_opportunity_variance','m_opportunity_levels']
explain=['m_all_B8L2','m_all_B8L2_p20','m_hard_B8L2','m_easy_B8L2','m_all_log_time','m_all_turn_n','m_challenge_turn_n','m_hard_turn_n','m_hard_minus_easy_turn_n','m_all_short_turn_edges','m_all_near_straight_nodes_5deg','m_all_unmatched_ref_9','m_all_matched_bottom_bias_deg','m_all_matched_top_bias_deg','m_all_log_area_ratio','m_all_log_height']
inputs=list(dict.fromkeys(x for family in ['OPPJOINT','TARGET_DSTRUCT']for domain in config['families'][family]['domains']for x in config['domains'][domain]))
hcols=list(dict.fromkeys(supports+explain+inputs))
labelcols=['worker_id','origin','heldout_building','method','class_id','known','missing_reason','input_conditions','evaluation_condition','history_scope','label_stage']
j=lab[labelcols].merge(hist[['worker_id','heldout_building']+hcols],on=['worker_id','heldout_building'],validate='many_to_one')
reason_map={'manual_all':'Manual历史不足12图或3楼','manual_time':'正时间历史不足12图或3楼，或时间对结构机会响应不可估','manual_opportunity':'可计算结构机会不足两级或历史变化不足','manual_difficulty':'正式简单/困难历史机会不足','manual_challenge':'复杂结构机会历史不足','missing_required_features':'至少一个必需特征缺失，未填零'}
def meaning(reason):return '；'.join(reason_map.get(a,a)for a in str(reason).split(';')if a and a!='nan')
j['missing_reason_zh']=j.missing_reason.map(meaning)
def save(d,name):
 p=O/name;b=d.to_csv(index=False).encode('utf-8-sig');b=gzip.compress(b,mtime=0)if name.endswith('.gz')else b
 temp=p.with_name(p.name+'.writing');temp.write_bytes(b);temp.replace(p)
save(j[j.heldout_building.ne('ALL')],'PERSONNEL_LOBO_LABELS_AND_SUPPORT.csv.gz')
allrows=hist[hist.heldout_building.eq('ALL')][['worker_id','origin']+hcols].copy()
for method in METHODS:
 x=j[j.heldout_building.eq('ALL')&j.method.eq(method)][['worker_id','class_id','known','missing_reason','missing_reason_zh']]
 allrows=allrows.merge(x.rename(columns={q:method+'_'+q for q in x if q!='worker_id'}),on='worker_id',validate='one_to_one')
save(allrows,'PERSONNEL_ALL_MEMBERS.csv')
save(j[~j.known],'PERSONNEL_MISSING_HISTORY_ALL_LOBO.csv')
# True K3 -> K4 relation from actual identical worker sets, no class-ID alignment assumption.
k3=lab[lab.method.eq('OPPJOINT_K3')][['worker_id','heldout_building','class_id','known']].rename(columns={'class_id':'coarse_class','known':'known3'})
k4=lab[lab.method.eq('OPPJOINT_K4')][['worker_id','heldout_building','class_id','known']].rename(columns={'class_id':'fine_class','known':'known4'})
pairs=k3.merge(k4,on=['worker_id','heldout_building'],validate='one_to_one');assert pairs.known3.equals(pairs.known4)
pairs=pairs[pairs.known3];assert pairs.groupby(['heldout_building','fine_class']).coarse_class.nunique().eq(1).all()
relation=pairs.groupby(['heldout_building','coarse_class','fine_class']).agg(workers=('worker_id','size'),members=('worker_id',lambda x:'|'.join(sorted(x)))).reset_index()
coarses=roles[roles.method.eq('OPPJOINT_K3')][['heldout_building','class_id','workers','m_all_B8L2','m_all_log_time','m_challenge_turn_n']].rename(columns={'class_id':'coarse_class',**{q:'coarse_'+q for q in ['workers','m_all_B8L2','m_all_log_time','m_challenge_turn_n']}})
fines=roles[roles.method.eq('OPPJOINT_K4')][['heldout_building','class_id','m_all_B8L2','m_all_log_time','m_challenge_turn_n']].rename(columns={'class_id':'fine_class',**{q:'fine_'+q for q in ['m_all_B8L2','m_all_log_time','m_challenge_turn_n']}})
relation=relation.merge(coarses,on=['heldout_building','coarse_class']).merge(fines,on=['heldout_building','fine_class']);relation['parent_child_n']=relation.groupby(['heldout_building','coarse_class']).fine_class.transform('size');relation['exact_nested']=True
save(relation[relation.heldout_building.eq('ALL')],'PERSONNEL_K3_K4_RELATION_ALL.csv')
save(relation[relation.heldout_building.ne('ALL')],'PERSONNEL_K3_K4_RELATION_LOBO.csv')
fold=[]
for f,g in relation.groupby('heldout_building'):
 split=g[g.parent_child_n.gt(1)];slow=g.loc[g.fine_m_all_log_time.idxmax()];hi=g.loc[g.fine_m_all_B8L2.idxmax()]
 fold.append(dict(heldout_building=f,known_workers=int(g.workers.sum()),coarse_sizes='|'.join(f'{c}:{int(x.coarse_workers.iloc[0])}'for c,x in g.groupby('coarse_class')),fine_sizes='|'.join(f'{r.fine_class}:{r.workers}'for r in g.sort_values('fine_class').itertuples()),split_parent=split.coarse_class.iloc[0],split_children='|'.join(sorted(split.fine_class)),slowest_fine_class=slow.fine_class,slowest_members=slow.members,slowest_workers=int(slow.workers),slowest_log_time=slow.fine_m_all_log_time,slowest_is_new_split=slow.fine_class in set(split.fine_class),highest_Q_fine_class=hi.fine_class,highest_Q_members=hi.members,highest_Q_workers=int(hi.workers),strictly_nested=True))
fold=pd.DataFrame(fold);save(fold,'PERSONNEL_HIERARCHY_BY_FOLD.csv')
# Class support: union historical targets/images/buildings; person-level support ranges.
summary=[]
for (method,f,cl),g in j[j.known].groupby(['method','heldout_building','class_id']):
 rr=raw[raw.worker_id.isin(g.worker_id)]
 if f!='ALL':rr=rr[rr.building.ne(f)]
 r=dict(method=method,heldout_building=f,class_id=cl,workers=len(g),members='|'.join(sorted(g.worker_id)),v1_workers=int(g.origin.eq('v1').sum()),new_workers=int(g.origin.eq('new').sum()),history_records=len(rr),history_images=int(rr.image_id.nunique()),history_targets=int(rr.reference_id.nunique()),history_buildings=int(rr.building.nunique()),historical_quality_rows=int(rr.B8L2.notna().sum()),positive_time_rows=int(rr.source_active_time_seconds.gt(0).sum()),input_conditions='manual',evaluation_condition='manual primary; semi separately if evaluated',weights='worker-target -> image -> building equal; class center equally averages eligible workers')
 for q in hcols:
  r[q+'_mean']=g[q].mean();r[q+'_known_workers']=int(g[q].notna().sum())
  if q in supports:r[q+'_min']=g[q].min();r[q+'_median']=g[q].median();r[q+'_max']=g[q].max()
 summary.append(r)
summary=pd.DataFrame(summary);save(summary[summary.heldout_building.eq('ALL')],'PERSONNEL_CLASS_SUMMARY_ALL.csv');save(summary[summary.heldout_building.ne('ALL')],'PERSONNEL_CLASS_SUMMARY_LOBO.csv.gz')
# Exact per-person bridge to already accepted original-answer/fusion cases.
case=pd.read_csv(W/'stage06_cases/CASE_EXACT_MEMBERS_AND_BLOCKS.csv');sel=pd.read_csv(W/'stage06_cases/CASE_SELECTION_TABLE.csv')
case=case.merge(sel[['event_id','image','building','method','source_stage','main_case']],on='event_id',validate='many_to_one')
for method in METHODS:
 use=lab[lab.method.eq(method)][['worker_id','heldout_building','class_id','known']]
 case=case.merge(use.rename(columns={'worker_id':'worker','heldout_building':'building','class_id':method+'_LOBO','known':method+'_LOBO_known'}),on=['worker','building'],how='left',validate='many_to_one')
 use=use[use.heldout_building.eq('ALL')][['worker_id','class_id']]
 case=case.merge(use.rename(columns={'worker_id':'worker','class_id':method+'_ALL'}),on='worker',how='left',validate='many_to_one')
save(case,'PERSONNEL_CASE_LABEL_CONNECTIONS.csv')
example_id='164f7e24305914ffb1d8c116'
examples=case[case.event_id.eq(example_id)&case.worker.isin(['W103','W113','W108','W121','W122','W102'])].copy()
votes=pd.read_csv(W/f'stage06_cases/figures/{example_id}/VOTE_GROUPS_WITH_BLOCKS.csv')
for node in [2,3]:
 values=[]
 for r in examples.itertuples():
  arm={'D':'A','X':'A','Y':'B','Z':'C'}[r.block]
  v=votes[votes.arm.eq(arm)&votes.nearest_reference_node_1based.eq(node)&votes.nearest_reference_azimuth_deg.le(9)]
  values.append(any(r.worker in str(q.workers).split('|')for q in v.itertuples()))
 examples[f'observed_support_near_ref_r{node}']=values
examples['use']='same-image complete original-answer explanation; this event remains OPPGEOM, not relabeled as OPPJOINT exchange'
save(examples,'PERSONNEL_SAME_IMAGE_MARKING_EXAMPLES.csv')
vector=[]
for (eid,block),g in case.groupby(['event_id','block']):
 r={'event_id':eid,'image':g.image.iloc[0],'case_method':g.method.iloc[0],'block':block,'people':len(g)}
 for method in METHODS:
  r[method+'_LOBO_vector']='|'.join(f'{cl}:{n}'for cl,n in g[method+'_LOBO'].fillna('unknown').value_counts().sort_index().items())
 vector.append(r)
save(pd.DataFrame(vector),'PERSONNEL_CASE_BLOCK_ROLE_VECTORS.csv')
overlap=allrows.groupby(['OPPJOINT_K4_class_id','TARGET_DSTRUCT_K3_class_id'],dropna=False).agg(workers=('worker_id','size'),members=('worker_id',lambda x:'|'.join(sorted(x)))).reset_index();save(overlap,'PERSONNEL_JOINT_STRUCTURE_OVERLAP_ALL.csv')
# Attach true parent roles to the already saved exact focused condition; no outcome recomputation.
events=pd.read_csv(W/'stage06_cases/FOCUS_OPPJOINT_N12M6_ALL_EVENTS.csv.gz',usecols=['event_id','image','building','method','source_class','target_class','n','m'],low_memory=False)
mp={(r.heldout_building,r.fine_class):r.coarse_class for r in relation.itertuples()}
events['source_K3_parent']=[mp[(r.building,r.source_class)]for r in events.itertuples()];events['target_K3_parent']=[mp[(r.building,r.target_class)]for r in events.itertuples()];events['cross_K3_parent']=events.source_K3_parent.ne(events.target_K3_parent)
save(events,'PERSONNEL_FOCUS_N12M6_PARENT_RELATIONS.csv')
sources=[C/'MAIN45_LABELS_ALL_LOBO.csv.gz',C/'HISTORY_FEATURES_ALL_LOBO.csv.gz',C/'CLASS_ROLES_ALL_LOBO.csv.gz',C/'RAW_TARGET_RESPONSE_RECORDS.csv.gz',C/'CANDIDATE_CONFIG_BEFORE_TEAM_RESULTS.json',C/'code/build_target_aware_candidates.py',W/'stage06_cases/FOCUS_OPPJOINT_N12M6_ALL_EVENTS.csv.gz']
manifest=[dict(path=str(p.relative_to(W)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())for p in sources]
receipt=dict(source_commit='a476461d7ede8db95da43de4139e612c05e618bc',data_release='v2.1',labels_unchanged=True,new_fits=0,new_fusions=0,ALL_roster=len(allrows),joint_known_workers=56,structure_known_workers=int(allrows.TARGET_DSTRUCT_K3_known.sum()),LOBO_folds=22,all_fold_and_ALL_nested_relations=len(relation),all_strictly_nested=True,focused_n12m6_events=len(events),focused_n12m6_cross_K3_events=int(events.cross_K3_parent.sum()),sources=manifest)
(O/'PERSONNEL_ROLES_PROVENANCE.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in receipt.items()if k!='sources'},ensure_ascii=False))
print(summary[summary.heldout_building.eq('ALL')][['method','class_id','workers','history_images','history_buildings','history_records','m_all_images_min','m_all_images_median','m_all_images_max','m_all_buildings_min','m_all_buildings_median','m_all_buildings_max','m_all_B8L2_mean','m_all_log_time_mean','m_challenge_turn_n_mean','m_all_log_area_ratio_mean']].to_string(index=False))
