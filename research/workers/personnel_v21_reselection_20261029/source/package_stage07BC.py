#!/usr/bin/env python3
"""Package the completed focused/scale experiments; no fusion, no label mutation."""
from pathlib import Path
import csv, gzip, hashlib, io, json, os, zipfile
from datetime import datetime, timezone
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
COMMIT='a476461d7ede8db95da43de4139e612c05e618bc'
DEL=ROOT/'deliverables'; DEL.mkdir(exist_ok=True)

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def dump(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')

def mainfiles(d):
 p=ROOT/d
 assert p.is_dir(),p
 return [x.relative_to(ROOT).as_posix() for x in p.iterdir() if x.is_file() and not any(s in x.name for s in ['.writing','.tmp','.log']) and x.name not in ['PROGRESS.json','REGISTRATION_PROGRESS.json']]

# Lossless textual subsets of the single completed refinement endpoint table.
ref_path=ROOT/'experiment/refinement_endpoints/ENDPOINT_SCALARS.csv.gz'
ref=pd.read_csv(ref_path,dtype=str,keep_default_na=False)
for component in ['refinement_baseline','refinement_m','refinement_AC']:
 req_path=ROOT/f'experiment/{component}_design/REQUESTS.csv.gz'
 keys=set(pd.read_csv(req_path,usecols=['team_key']).team_key)
 sub=ref[ref.team_key.isin(keys)].copy()
 assert len(sub)==len(keys) and sub.team_key.is_unique
 out=ROOT/f'experiment/{component}_endpoints';out.mkdir(exist_ok=True)
 target=out/'ENDPOINT_SCALARS.csv.gz'
 sub.to_csv(target,index=False,compression={'method':'gzip','mtime':0})
 dump(out/'SUBSET_PROVENANCE.json',{
   'operation':'lossless textual row subset; no new calculations', 'data_release':'v2.1',
   'source_file':ref_path.relative_to(ROOT).as_posix(),'source_sha256':sha(ref_path),
   'request_file':req_path.relative_to(ROOT).as_posix(),'request_sha256':sha(req_path),
   'rows':len(sub),'requested_team_keys':len(keys),'missing':0,
   'endpoint_scalars_sha256':sha(target)})

stage_dirs={
 '07B':[
  'experiment/focused_capacity','experiment/focused_design','experiment/focused_selection',
  'experiment/focused_refinement_selection','analysis/focused_compact','analysis/focused_summary',
  'analysis/focused_contexts','analysis/focused_failures','analysis/joint_baseline_comparison',
  'experiment/refinement_baseline_capacity','experiment/refinement_baseline_design',
  'experiment/refinement_baseline_endpoints','analysis/refinement_baseline','analysis/refinement_baseline_summary',
  'experiment/member_sensitivity_design','analysis/member_sensitivity'],
 '07C':[
  'analysis/scale_background_summary','experiment/fixed_A_m_capacity','experiment/fixed_A_m_design',
  'experiment/direct_AC_capacity','experiment/direct_AC_design','analysis/direct_AC',
  'analysis/direct_AC_combined_summary','experiment/refinement_m_capacity','experiment/refinement_m_design',
  'experiment/refinement_m_endpoints','experiment/refinement_AC_capacity','experiment/refinement_AC_design',
  'experiment/refinement_AC_endpoints','analysis/refinement_AC','experiment/focused_selection',
  'experiment/focused_refinement_selection']}
stage_specs={
 '07B': [('focused','focused'),('refinement_baseline','refinement_baseline'),('member_sensitivity','member_sensitivity')],
 '07C': [('fixed_A_m','fixed_A_m'),('refinement_m','refinement_m'),('direct_AC','direct_AC'),('refinement_AC','refinement_AC')]}

stage_add={
 '07B':['analysis/focused/MEASUREMENT_RECEIPT.json'],
 '07C':['analysis/fixed_A_m_paths/MEASUREMENT_RECEIPT.json','analysis/refinement_m_paths/MEASUREMENT_RECEIPT.json']}
for st,endpoint_stages in [('07B',['focused','member_sensitivity']),('07C',['fixed_A_m','direct_AC'])]:
 for x in endpoint_stages:
  for f in ['ENDPOINT_SCALARS.csv.gz','RUN_RECEIPT.json','CUMULATIVE_COMPLETION.json']:
   p=Path(f'experiment/{x}_endpoints/{f}')
   if p.exists():stage_add[st].append(str(p))
 for x in endpoint_stages+['refinement']:
  for f in ['TEAM_GEOMETRY_SOURCES.csv.gz','DELIVERY_RECEIPT.json','RECOMPUTE_HISTORICAL_CACHE_REQUESTS.csv.gz']:
   stage_add[st].append(f'endpoint_delivery/{x}/{f}')

all_receipts=[]
for stage in ['07B','07C']:
 files=set(stage_add[stage])
 for d in stage_dirs[stage]:files.update(mainfiles(d))
 # All measured event columns for focus are in normalized compact tables; the 41 MB repeated wide table is not duplicated.
 assert not any('shards/' in p or '/pools/' in p or 'new_geometry' in p or '.writing' in p for p in files)
 folder=ROOT/f'stage_delivery/stage{stage}';folder.mkdir(parents=True,exist_ok=True)
 datasets=[]; event_frames=[];scalar_keys=set();all_requested=set()
 for design,ep in stage_specs[stage]:
  epath=f'experiment/{design}_design/EVENTS_EXACT.csv.gz'
  rpath=f'experiment/{design}_design/REQUESTS.csv.gz'
  spath=f'experiment/{ep}_endpoints/ENDPOINT_SCALARS.csv.gz'
  e=pd.read_csv(epath);r=pd.read_csv(rpath,usecols=['team_key']);s=pd.read_csv(spath,usecols=['team_key','B8L2'])
  arms=[c for c in ['A_team_key','B_team_key','C_team_key'] if c in e]
  need=set(e[arms].to_numpy().ravel());need.discard(float('nan'))
  needed={x for x in need if isinstance(x,str) and x}
  req=set(r.team_key);sk=set(s.team_key)
  assert req==sk and needed.issubset(sk),(design,len(req-sk),len(needed-sk))
  assert r.team_key.is_unique and s.team_key.is_unique and e.event_id.is_unique,design
  item={'dataset':design,'design_file':epath,'requests_file':rpath,'endpoint_scalars_file':spath,
    'events':len(e),'unique_event_ids':e.event_id.nunique(),'pools':e.pool_id.nunique(),
    'images':e.image.nunique(),'buildings':e.building.nunique(),'team_requests':len(r),
    'scalar_rows':len(s),'scorable_B8L2':int(s.B8L2.notna().sum()),'unscorable_B8L2':int(s.B8L2.isna().sum()),
    'event_arm_team_keys':len(needed),'missing_requests':0,'missing_event_arm_scalars':0,
    'design_type':'strict_ABC' if 'B_team_key' in arms else 'direct_AC_no_B'}
  datasets.append(item);event_frames.append(e.assign(dataset=design));scalar_keys.update(sk);all_requested.update(req)
 all_events=pd.concat(event_frames,ignore_index=True)
 coverage={'stage':stage,'data_release':'v2.1','commit':COMMIT,'datasets':datasets,
  'event_stage_rows':int(sum(x['events'] for x in datasets)),
  'distinct_method_event_ids':int(all_events.event_id.nunique()),
  'distinct_requested_team_keys':len(all_requested),'distinct_scalar_team_keys':len(scalar_keys),
  'pools':int(all_events.pool_id.nunique()),'images':int(all_events.image.nunique()),'buildings':int(all_events.building.nunique()),
  'new_fusions_in_packaging':0,'geometry_payload_files':0,
  'labels_sha256':sha(ROOT/'classification/MAIN45_LABELS_ALL_LOBO.csv.gz'),
  'note':'Event rows count registered comparisons, not independent people/images. Same deterministic endpoint is referenced by team_key.'}
 if stage=='07B':
  compact=pd.read_csv('analysis/focused_compact/EVENT_EFFECTS_COMPLETE.csv.gz',usecols=['event_id'])
  focused_ids=set(event_frames[0].event_id)
  assert set(compact.event_id)==focused_ids and len(compact)==len(focused_ids)
  links=pd.read_csv('analysis/focused_compact/EVENT_PAIR_LINKS.csv.gz')
  pairs=pd.read_csv('analysis/focused_compact/PAIR_GEOMETRY.csv.gz',usecols=['pair_id'])
  assert set(links.event_id)==focused_ids and set(links.pair_id)<=set(pairs.pair_id)
  coverage['compact']={'event_effect_rows':len(compact),'pair_link_rows':len(links),'pair_geometry_rows':len(pairs),
    'missing_event_effects':0,'missing_pair_geometry':0,
    'wide_EVENT_METRICS_omitted_reason':'Duplicate denormalized copy; complete effects, endpoint diagnostics and pair geometry provided in focused_compact.'}
 else:
  inc=pd.read_csv('analysis/scale_background_summary/FIXED_A_ALL_M_INCREMENT_METRICS.csv.gz',usecols=['path_id','event_small','event_large','A_team_key','B_small','B_large','C_small','C_large'])
  evkeys=set(all_events.event_id)
  assert set(inc.event_small)<=evkeys and set(inc.event_large)<=evkeys
  pathteams=set(inc[['A_team_key','B_small','B_large','C_small','C_large']].to_numpy().ravel())
  assert pathteams<=scalar_keys
  cap=pd.read_csv('analysis/scale_background_summary/MIN_TO_ACTUAL_CAPACITY_EXACT_LINKS.csv.gz')
  coverage['fixed_A_path_increments']={'complete_increment_rows':len(inc),'distinct_paths':inc.path_id.nunique(),
   'min_to_actual_max_path_rows':len(cap),'missing_path_event_links':0,'missing_path_scalar_links':0,
   'original_batches':[{'dataset':'fixed_A_m','pairs':7397,'paths':1380},{'dataset':'refinement_m','pairs':2787,'paths':567}],
   'original_duplicate_increment_files_omitted':True}
 dump(folder/'COVERAGE.json',coverage)

 refs=[]
 reference_names=['classification/MAIN45_LABELS_ALL_LOBO.csv.gz','source/run_registered.py','analysis/summarize_scale_background.py','analysis/build_scale_background_reading_tables.py']
 if stage=='07C':reference_names+=['analysis/focused_contexts/FIXED_XYZ_BACKGROUND_CONTRASTS.csv.gz','analysis/global_size_paths/SIZE_PATH_RESULTS.csv.gz']
 for p in reference_names:
  pp=ROOT/p
  if pp.exists():refs.append({'path':p,'bytes':pp.stat().st_size,'sha256':sha(pp),'included_in_this_package':p in files,'reason':'Core labels/code or earlier-stage source; archives overlay at WORK root.'})
 dump(folder/'EXTERNAL_REFERENCES.json',refs)
 descr='重点扩展、共同支持基线及目标成员敏感性' if stage=='07B' else '固定原队替换规模、同图背景解释及大团队直接 AC'
 lines=[f'# 阶段 {stage}：{descr}','',f'真实数据 v2.1；仓库提交 `{COMMIT}`。所有路径以研究 WORK 根目录为基准，和其他阶段包叠加解压。','',
 '本包只整理已完成结果；不训练新标签、不新增融合，不复制几何缓存。精确成员见 `experiment/*_design/EVENTS_EXACT.csv.gz`，请求通过 `team_key` 关联去重端点标量。','',
 '## 实际覆盖','', '| 数据集 | 精确事件 | 去重请求/标量 | 图片 | 建筑 |', '|---|---:|---:|---:|---:|']
 for d in datasets:lines.append(f"| {d['dataset']} | {d['events']} | {d['team_requests']} | {d['images']} | {d['buildings']} |")
 lines+=['',f"合计 {coverage['event_stage_rows']} 条阶段事件，{coverage['distinct_method_event_ids']} 个不同方法事件 ID，{len(scalar_keys)} 个不同实际团队端点。全部事件臂都能关联到本包标量。事件数不是独立统计分母。",'',
 '## 文件与来源','',
 '- `SOURCE_FILE_INDEX.csv`：本包实际载荷的相对路径、字节数与 SHA-256；清单自身不自引用。',
 '- `COVERAGE.json`：逐数据集、逐事件臂的请求—标量完整性和可评分分母。',
 '- `EXTERNAL_REFERENCES.json`：核心标签、代码及前阶段依赖的哈希；避免重复输入和全代码。',
 '- `endpoint_delivery/*/TEAM_GEOMETRY_SOURCES.csv.gz`：按实际 team_key 定位已交付 delta 几何或旧缓存确定性复算来源。几何包另交。',
 '- `experiment/refinement_*_endpoints/SUBSET_PROVENANCE.json`：从共享 refinement 标量逐行提取的精确子表，无新增融合。','']
 if stage=='07B':lines += ['`analysis/focused_compact/` 四张全量主表保留全部 10,980 事件效果、端点参考诊断及去重团队对几何；不重复收入 41 MB 的展开宽表和分片。成员敏感性是 n12/m5 六种目标块留一，不冒称原 m6 实验。','']
 else:lines += ['固定 A 的 7,397＋2,787 条增量在 `analysis/scale_background_summary/FIXED_A_ALL_M_INCREMENT_METRICS.csv.gz` 合并为 10,184 条，保留 1,947 条真实路径；不再重复收两张原增量宽表。实际 mmax 逐路径保存。ΔC、ΔB、净差使用匹配四个 B/C 端点支持，另留较宽分母；净差增加不全部等于 C 队升质。', '', '直接 AC 两批共 1,966 条事件没有同类 B，不能混进同/跨幅度判断；合并结果见 `analysis/direct_AC_combined_summary/`。同图目标背景对照依赖阶段 07B，固定 XYZ 变 n 路径依赖前阶段全局结果；本包摘要严格区分三个设计。','']
 (folder/'README.md').write_text('\n'.join(lines)+'\n')
 files.update(str((folder/x).relative_to(ROOT)) for x in ['README.md','COVERAGE.json','EXTERNAL_REFERENCES.json'])
 manifest=[]
 for p in sorted(files):
  pp=ROOT/p;assert pp.is_file(),pp
  manifest.append({'path':p,'bytes':pp.stat().st_size,'sha256':sha(pp)})
 pd.DataFrame(manifest).to_csv(folder/'SOURCE_FILE_INDEX.csv',index=False)
 files.add(str((folder/'SOURCE_FILE_INDEX.csv').relative_to(ROOT)))
 suffix='重点扩展与匹配验证完整数据' if stage=='07B' else '固定A规模背景与大队AC完整数据'
 zpath=DEL/f'HOHONET_v21_阶段{stage}_{suffix}_20261029.zip';tmp=zpath.with_suffix('.zip.writing')
 with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
  for p in sorted(files):z.write(ROOT/p,arcname=p)
 os.replace(tmp,zpath)
 print('SAVED',stage,zpath.stat().st_size,'bytes',flush=True)

 # Read the actual ZIP, verify every source hash and all essential association rows.
 checks={'crc_ok':False,'payload_hashes_verified':0,'datasets':[]}
 with zipfile.ZipFile(zpath) as z:
  assert z.testzip() is None;checks['crc_ok']=True
  for row in manifest:
   h=hashlib.sha256()
   with z.open(row['path']) as f:
    for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
   assert h.hexdigest()==row['sha256'],row['path']
   checks['payload_hashes_verified']+=1
  def zcsv(p,usecols=None):
   b=io.BytesIO(z.read(p))
   return pd.read_csv(b,compression='gzip' if p.endswith('.gz') else None,usecols=usecols)
  for d in datasets:
   e=zcsv(d['design_file'],usecols=lambda c:c in ['event_id','A_team_key','B_team_key','C_team_key'])
   r=zcsv(d['requests_file'],['team_key']);s=zcsv(d['endpoint_scalars_file'],['team_key','B8L2'])
   sk=set(s.team_key)
   assert len(e)==d['events'] and len(r)==d['team_requests'] and set(r.team_key)==sk
   for c in ['A_team_key','B_team_key','C_team_key']:
    if c in e:assert set(e[c].dropna())<=sk
   checks['datasets'].append({'dataset':d['dataset'],'event_rows_read':len(e),'request_rows_read':len(r),'scalar_rows_read':len(s),'missing_event_arm_keys':0})
  if stage=='07B':
   effects=zcsv('analysis/focused_compact/EVENT_EFFECTS_COMPLETE.csv.gz',['event_id'])
   assert len(effects)==10980
   checks['compact_events_read']=len(effects)
  else:
   inc=zcsv('analysis/scale_background_summary/FIXED_A_ALL_M_INCREMENT_METRICS.csv.gz',['path_id','event_small','event_large'])
   assert len(inc)==10184 and inc.path_id.nunique()==1947
   checks['merged_increment_rows_read']=len(inc);checks['merged_paths_read']=inc.path_id.nunique()
 receipt={'stage':stage,'archive':zpath.relative_to(ROOT).as_posix(),'bytes':zpath.stat().st_size,'sha256':sha(zpath),
  'payload_files':len(files),'coverage':coverage,'readback':checks,'uploaded':False,
  'finished_utc':datetime.now(timezone.utc).isoformat()}
 dump(DEL/f'STAGE{stage}_COMPLETE_DATA_RECEIPT.json',receipt)
 dump(folder/'ZIP_READBACK_RECEIPT.json',receipt)
 all_receipts.append(receipt)
 print('VERIFIED',stage,json.dumps({'files':len(files),'bytes':receipt['bytes'],'sha256':receipt['sha256'],'events':coverage['event_stage_rows'],'teams':len(scalar_keys),'CRC':True},ensure_ascii=False),flush=True)
dump(DEL/'STAGE07BC_COMPLETE_DATA_RECEIPTS.json',all_receipts)
