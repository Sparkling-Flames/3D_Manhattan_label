#!/usr/bin/env python3
"""Freeze selected case identities, source membership, full scores and vote/ring tables."""
from pathlib import Path
import json,gzip,hashlib
import pandas as pd
W=Path(__file__).resolve().parents[2];O=W/'stage06_cases'
specs=[
 ('01_position','cd27d16376d979fbd3e9b1fe','traces','same_node_position_improvement','主文：OPPGEOM同节点下定位改善；中等效果，非最大增益',True,'普通走廊目标；完整四角位置可与RGB和参考并列'),
 ('02_structure','ae9bc0bdaf9a5f2119cea910','traces_semantic','structure_recovered','主文：同一目标补回RGB支持的短折返，两端跨过实际票门槛',True,'RGB可见顶部/侧壁短折返；底部被浴缸/帘/洁具遮挡，精确底点沿用已确认参考'),
 ('03_size_lower','164f7e24305914ffb1d8c116','traces','nested_size_reversal','主文：固定XYZ、嵌套D的较小团队，补充结构保留',True,'与02同图不同实验，不作为独立建筑重复支持'),
 ('03_size_higher','bbd4c6e7e49cced53ce71301','traces','nested_size_reversal','主文：增加同一D路径后8票组未增加，门槛7→9而失选',True,'原始观察组完全保留，不以跨端点节点编号作为对应依据'),
 ('04_failure','bac6397542c7a06a9d811694','traces','cross_failed','主文：五组分别过票但没有整份原答环覆盖，C连接失败',True,'不补连边、不将失败记为Q=0；节点数是入选组数'),
 ('05_joint','b8370e9f1447f415c2c4ce0c','traces','joint_n20m5','主文：OPPJOINT n20/m5，结构相同而质量改善；时间相对B略减、相对A增加',True,'同目标的四角房间参考；大窗外空间不混入本队'),
 ('06_joint_focus','2fa2eea81fbc17d689ffb72f','traces_focus','joint_n12m6','主文：OPPJOINT n12/m6，接近该条件事件中位净收益，并呈现记录时间代价',True,'原图为餐厅内部目标；右侧开口后的其它空间不加入同一团队，三队都表达本目标四个转折'),
 ('S1_semantic_not_main','e505c9246f7c405989d8d315','traces','structure_recovered','补充：真实统计效应保留；不选为必要结构的主RGB证据',False,'新增点接近ERP接缝且自遮挡，单张RGB不足清楚展示两个底角；未因此改动总体结果'),
]
rows=[];blocks=[];arms=[];votes=[];rings=[];raw=[];keys=set();events=[];pools={}
for cid,eid,folder,pool,reason,main,semantic in specs:
 path=O/folder/(eid+'.json.gz');d=json.load(gzip.open(path,'rt'));e=d['event'];p=d['pool'];keys.add(eid)
 events.append(e);pools[p['pool_id']]=p
 stage='focused' if folder=='traces_focus' else 'global_screen'
 row=dict(case_id=cid,event_id=eid,source_stage=stage,main_case=main,case_type=pool,selection_reason=reason,semantic_review=semantic,trace_file=str(path.relative_to(O)),trace_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),original_file='cases/originals/'+p['meta']['image']+'.png',figure_directory='figures/'+eid)
 row.update({k:e[k]for k in ['pool_id','image','building','method','heldout_building','source_class','target_class','n','m','D','X','Y','Z','A_members','B_members','C_members','A_class_vector','B_class_vector','C_class_vector','background_source_n','background_target_n']})
 for arm in 'ABC':
  r=d['arms'][arm];row[arm+'_Q']=r.get('B8L2');row[arm+'_D10']=r.get('D10');row[arm+'_nodes']=r.get('nodes');row[arm+'_failed']=r.get('B8L2')is None
  rec=dict(case_id=cid,event_id=eid,arm=arm);rec.update({k:v for k,v in r.items()if not isinstance(v,(dict,list))});arms.append(rec)
  for g in (r.get('full_state')or{}).get('identity_groups',[]):
   selected=set(w['worker']for w in g['members']);D=set(e['D'].split('|'))
   votes.append(dict(case_id=cid,event_id=eid,arm=arm,feature_id=g['feature_id'],support=g['support'],selected=g['selected'],threshold=r['minimum_support'],D_support=len(selected&D),block_support=len(selected-D),workers='|'.join(sorted(selected)),center_json=json.dumps(g['center'],separators=(',',':')),observations='|'.join(sorted(str(m['id'])+':'+str(m['source_pair_index'])for m in g['members']))))
  selected={g['feature_id']for g in (r.get('full_state')or{}).get('identity_groups',[])if g['selected']}
  for a in (r.get('full_state')or{}).get('assignments',[]):
   rings.append(dict(case_id=cid,event_id=eid,arm=arm,worker=a['worker'],object_id=a['id'],selected_groups='|'.join(sorted(selected)),source_groups='|'.join(a['feature_ids']),selected_group_n=len(selected),selected_hits=len(selected&set(a['feature_ids'])),covers_all_selected=selected<=set(a['feature_ids'])))
 for dest in ['BA','CA','CB']:
  ra,rb=d['arms'][dest[0]],d['arms'][dest[1]]
  row['Q_'+dest]=(ra['B8L2']-rb['B8L2'])if ra.get('B8L2')is not None and rb.get('B8L2')is not None else None
 rows.append(row)
 owner={r['worker_id']:r for r in p['records']}
 for block in ['D','X','Y','Z']:
  for worker in filter(None,e[block].split('|')):
   r=owner[worker]
   blocks.append(dict(case_id=cid,event_id=eid,block=block,worker=worker,object_id=r['object_id'],source_time_seconds=r.get('source_time_seconds'),time_source_kind=r.get('time_source_kind'),B8L2=r.get('B8L2'),D10=r.get('D10'),bottom_point_n=len(r['points'])//2))
   raw.append(dict(case_id=cid,event_id=eid,block=block,worker=worker,object_id=r['object_id'],points_json=json.dumps(r['points'],separators=(',',':')),order_status=r.get('order_status'),ring_confirmed=r.get('ring_confirmed')))
def save(name,data):
 p=O/name;q=p.with_name(p.name+'.writing');data.to_csv(q,index=False,encoding='utf-8-sig',compression='gzip'if name.endswith('.gz')else None);q.replace(p)
case=pd.DataFrame(rows);save('CASE_SELECTION_TABLE.csv',case);save('CASE_EXACT_MEMBERS_AND_BLOCKS.csv',pd.DataFrame(blocks));save('CASE_COMPLETE_RAW_ANSWERS.csv.gz',pd.DataFrame(raw));save('CASE_ENDPOINT_SCALARS.csv',pd.DataFrame(arms));save('CASE_VOTE_GROUPS.csv',pd.DataFrame(votes));save('CASE_SOURCE_RING_COVERAGE.csv',pd.DataFrame(rings))
save('CASE_EVENTS_EXACT.csv.gz',pd.DataFrame(events))
(O/'CASE_POOL_INPUTS.json.gz').write_bytes(gzip.compress(json.dumps({'images':list(pools.values()),'data_release':'v2.1','repository_commit':'a476461d7ede8db95da43de4139e612c05e618bc','scope':'only six exact legal-target pools required for these cases'},ensure_ascii=False,allow_nan=False,separators=(',',':')).encode(),mtime=0))
metrics=[]
for stage in case.source_stage.unique():
 stagekeys=set(case.loc[case.source_stage==stage,'event_id'])
 metricpath=W/f'analysis/{stage}/EVENT_METRICS.csv.gz'
 if not metricpath.exists():metricpath=O/'CASE_FULL_EVENT_METRICS.csv.gz'
 for chunk in pd.read_csv(metricpath,chunksize=10000,low_memory=False):
  part=chunk[chunk.event_id.isin(stagekeys)].copy()
  if len(part):
   part['case_source_stage']=stage;metrics.append(part)
metrics=pd.concat(metrics,ignore_index=True);assert set(metrics.event_id)==keys;save('CASE_FULL_EVENT_METRICS.csv.gz',metrics)
rolepath=W/'classification/CLASS_ROLES_ALL_LOBO.csv.gz'
if not rolepath.exists():rolepath=O/'CASE_USED_LOBO_CLASS_DEFINITIONS.csv'
roles=pd.read_csv(rolepath);rolekeys=set((r.method,r.heldout_building)for r in case.itertuples())
roles=roles[[((r.method,r.heldout_building)in rolekeys)for r in roles.itertuples()]];save('CASE_USED_LOBO_CLASS_DEFINITIONS.csv',roles)
labelpath=W/'classification/MAIN45_LABELS_ALL_LOBO.csv.gz'
if not labelpath.exists():labelpath=O/'CASE_USED_LOBO_LABELS.csv'
labels=pd.read_csv(labelpath,low_memory=False)
labels=labels[[((r.method,r.heldout_building)in rolekeys)for r in labels.itertuples()]]
save('CASE_USED_LOBO_LABELS.csv',labels)
index=[]
for r in case.itertuples():
 p=O/'figures'/r.event_id
 for f in ['ERP_BEV.png','3D_VOTES.png']:
  assert (p/f).is_file(),p/f
 index.append(dict(event_id=r.event_id,case_id=r.case_id,main_case=r.main_case,image=r.image,method=r.method,n=r.n,m=r.m,ERP_BEV=str((p/'ERP_BEV.png').relative_to(W)),**{'3D_VOTES':str((p/'3D_VOTES.png').relative_to(W))}))
save('figures/CASE_FIGURE_INDEX.csv',pd.DataFrame(index))
checks=[]
for folder in ['traces','traces_semantic','traces_focus']:
 checks+=json.loads((O/folder/'TRACE_SCALAR_PARITY.json').read_text())
receipt={'case_events':len(case),'main_events':int(case.main_case.sum()),'main_case_topics':6,'main_images':case[case.main_case].image.nunique(),'trace_replayed_endpoints':len(checks),'maximum_cached_scalar_difference':max(r['maximum_scalar_difference']for r in checks),'new_independent_team_endpoints':0,'source':'complete 69485-event frozen global screen plus focused OPPJOINT n12/m6 condition','data_release':'v2.1','classification_labels_unchanged':True,'failure_Q_imputed_zero':False,'rgb_reviewed':True,'actual_figures_exist':True,'only_trace_refusion':True}
(O/'CASE_COMPLETION.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));print(json.dumps(receipt,ensure_ascii=False))
