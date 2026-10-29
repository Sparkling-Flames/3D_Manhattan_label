#!/usr/bin/env python3
"""Package selected actual mechanisms, then decode and rebuild from the ZIP alone."""
from pathlib import Path
import csv,gzip,hashlib,io,json,os,re,subprocess,sys,tempfile,zipfile
import pandas as pd
from PIL import Image
W=Path(__file__).resolve().parents[1];S=W/'stage06_cases';D=W/'deliverables';D.mkdir(exist_ok=True)
REPO=W.parent/'HOHONET_v21_20261029';COMMIT='a476461d7ede8db95da43de4139e612c05e618bc'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for block in iter(lambda:f.read(2**20),b''):h.update(block)
 return h.hexdigest()
sources=[]
for p,purpose in [
 (W/'analysis/global_screen/EVENT_METRICS.csv.gz','All frozen global-screen measurements; selected exact rows included'),
 (W/'analysis/focused/EVENT_METRICS.csv.gz','All focused measurements; selected n12/m6 rows included'),
 (W/'experiment/global_screen_design/EVENTS_EXACT.csv.gz','Original exact global event registration'),
 (W/'experiment/focused_design/EVENTS_EXACT.csv.gz','Original exact focused event registration'),
 (W/'experiment/global_screen_endpoints/ENDPOINT_SCALARS.csv.gz','Global endpoint scalar source; selected24 included'),
 (W/'experiment/focused_endpoints/ENDPOINT_SCALARS.csv.gz','Focused endpoint scalar source'),
 (W/'experiment/global_screen_size_paths/EXACT_NESTED_SIZE_LINKS.csv.gz','All fixedXYZ nestedD scale links'),
 (W/'classification/MAIN45_LABELS_ALL_LOBO.csv.gz','Frozen45-method labels; used folds included'),
 (W/'classification/CLASS_ROLES_ALL_LOBO.csv.gz','Full semantic historical centers; used folds included'),
 (REPO/'research/same_room/same_room_current_classes_v2_20261023/code/engine/new_team_engine.py','Pinned current native engine dependency'),
]:
 assert p.exists(),p
 inrepo=p.is_relative_to(REPO)
 sources.append(dict(path=str(p.relative_to(REPO if inrepo else W)),base='pinned_github_repository'if inrepo else 'main_research_work',bytes=p.stat().st_size,sha256=sha(p),purpose=purpose,repository_commit=COMMIT))
pd.DataFrame(sources).to_csv(S/'INPUT_SOURCE_REFERENCES.csv',index=False,encoding='utf-8-sig')
(S/'FIELD_DICTIONARY.md').write_text('''# 案例字段与路径

- `event_id`：冻结精确事件身份。`source_stage` / `case_source_stage` 区分全局广筛与 focused；不把新增机制选择当成新建类。
- `pool_id` / `reference_id`：合法目标身份；同一原图不同目标不能按 image 合并为一个融合池。
- `A/B/C_members` 与 `D/X/Y/Z`：实际人员编号，用竖线连接；A=D+X、B=D+Y、C=D+Z，各块不重叠。
- `A/B/C_class_vector`：实际对应折内完整类别人数，包括 unknown。类编号不跨折拼接。
- `m` / `actual_m_AB/AC/BC`：换出的具体成员数。`seat_net_change_l1` 是两类席位人数变化的 L1 和，等于2m，不误作换人数。
- `B8L2` / `Q`、`D10`：当前冻结评分。失败Q缺失，不用0填补。
- `nodes`：入选对应组数；只有 `connection_available` 且完整评分资格成立时才有完整融合环，失败时不可据 nodes 宣称完整输出。
- `support`：对应组的独立标注者票数；`D_support` 和 `block_support` / `replacement_support` 是共同背景与换入块的贡献。
- `observations`：对象ID:原答点对索引，跨端点追踪原观察，不依赖 feature_id 同名。
- `IoU3D100`：既定三维代理IoU乘100；BEV `iou_2d` 为0—1。3D绘图空间以相机高h归一化，非实测米制尺寸。
- `source_time_total_seconds`：历史来源库存记录的秒数和；不同于目标专用 `recorded_time_total_seconds`。缺少目标专用时间保留缺失。
- `record_time_*_pct_source_matched`：两个队伍来源种类及人数一致时的百分比；C−B和C−A分别计算，不互相替代。
- `time_comparable_ABC`：三队时间来源人数构成都匹配；某一对匹配不要求另外一对也匹配。
- `trace_file` / `figure_directory`：相对 stage06_cases/；`original_file` 和 CASE_FIGURE_INDEX 的图路径相对分包解压根目录。
- 图中的完整原答：正式输入的全部上下点对，保留其原来点序与资格；仅为绘制跨ERP接缝的连续边界作断开，不移动/补造角点。
- `m_all_B8L2` / `m_all_log_time` /结构历史中心：沿候选原方法采用的图内中心化历史特征，不能直接读成原始质量分或秒数。
''',encoding='utf-8')
files=sorted(p for p in S.rglob('*')if p.is_file()and p.name!='FILE_MANIFEST.csv'and '__pycache__'not in p.parts)
files+=sorted((W/'cases/code').glob('*.py'))
files+=sorted((W/'cases/originals').glob('*'))
files+=[W/n for n in ['cases/source/release_IMAGE_INDEX.csv','cases/source/ZIP_MEMBER_INDEX.csv','cases/source/FONT_SOURCE.json','experiment/export_event_mechanism.py','experiment/benchmark_engine.py','experiment/capacity_space.py','experiment/register_adaptive.py','experiment/ENVIRONMENT.json','source/save_stage06.py']]
files=sorted(set(files));manifest=[]
for p in files:
 assert p.is_file(),p
 manifest.append(dict(path=str(p.relative_to(W)),bytes=p.stat().st_size,sha256=sha(p)))
pd.DataFrame(manifest).to_csv(S/'FILE_MANIFEST.csv',index=False,encoding='utf-8-sig');files.append(S/'FILE_MANIFEST.csv')
archive=D/'HOHONET_v21_阶段06_真实原答投票融合机制案例_20261029.zip';tmp=archive.with_name(archive.name+'.writing')
with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True)as z:
 for p in sorted(files):z.write(p,str(p.relative_to(W)),compress_type=zipfile.ZIP_STORED if p.suffix in ['.png','.gz','.pdf']else zipfile.ZIP_DEFLATED)
with tmp.open('rb')as f:os.fsync(f.fileno())
tmp.replace(archive)
reads=[];links=[]
with zipfile.ZipFile(archive)as z:
 assert z.testzip()is None
 names=set(z.namelist())
 for row in manifest:
  b=z.read(row['path']);assert len(b)==row['bytes'];assert hashlib.sha256(b).hexdigest()==row['sha256']
  name=row['path'];decoded=gzip.decompress(b)if name.endswith('.gz')else b
  if name.endswith(('.csv','.csv.gz')):
   text=io.StringIO(decoded.decode('utf-8-sig'));reader=csv.reader(text);header=next(reader);n=sum(1 for _ in reader);reads.append(dict(path=name,type='csv',rows=n,columns=len(header)))
  elif name.endswith(('.json','.json.gz')):
   value=json.loads(decoded);reads.append(dict(path=name,type='json',items=len(value)))
  elif name.endswith('.png'):
   with Image.open(io.BytesIO(b))as im:im.verify()
  elif name.endswith('.pdf'):assert b.startswith(b'%PDF-')
  elif name.endswith('.md'):
   for target in re.findall(r'\]\(([^)]+)\)',decoded.decode('utf-8')):
    if '://'in target or target.startswith('#'):continue
    dest=(Path(name).parent/target.split('#')[0]).as_posix()
    assert dest in names,(name,target,dest)
    links.append(dict(document=name,link=target,exists_in_zip=True))
 with tempfile.TemporaryDirectory(prefix='hohonet_case_package_read_')as td:
  temp=Path(td);z.extractall(temp)
  # Standalone rebuild uses included exact traces/selected metrics/usedLOBO labels.
  run=subprocess.run([sys.executable,str(temp/'cases/code/build_case_tables.py')],cwd=temp,text=True,capture_output=True,timeout=60)
  assert run.returncode==0,(run.stdout,run.stderr)
  rebuilt=json.loads((temp/'stage06_cases/CASE_COMPLETION.json').read_text())
  assert rebuilt['case_events']==8 and rebuilt['trace_replayed_endpoints']==24
  rr=pd.read_csv(temp/'stage06_cases/CASE_ENDPOINT_SCALARS.csv');assert rr.team_key.nunique()==24
  assert len(json.loads(gzip.decompress((temp/'stage06_cases/CASE_POOL_INPUTS.json.gz').read_bytes()))['images'])==6
receipt=dict(file=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),files=len(files),zip_crc_pass=True,all_manifest_sha256_pass=True,actual_decoded_reads=reads,markdown_links_checked=len(links),all_markdown_links_exist_in_zip=True,png_decode_verified=True,pdf_headers_verified=True,standalone_rebuild_from_extracted_zip=True,exact_events=8,unique_endpoints=24,legal_target_pools=6,only_six_original_images=True,no_upload_performed=True)
(D/'STAGE06_CASES_READ_CHECK.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
independent=[('完整机制案例包',archive),('中文机制说明',S/'CASE_MECHANISMS_ZH.md'),('案例总表',S/'CASE_MECHANISM_SUMMARY.csv'),('精确ABC成员事件',S/'CASE_EVENTS_EXACT.csv.gz'),('端点全部标量',S/'CASE_ENDPOINT_SCALARS.csv'),('逐人员DXYZ',S/'CASE_EXACT_MEMBERS_AND_BLOCKS.csv'),('完整原答点序列',S/'CASE_COMPLETE_RAW_ANSWERS.csv.gz'),('实际楼外人员标签',S/'CASE_USED_LOBO_LABELS.csv'),('实际楼外定义与中心',S/'CASE_USED_LOBO_CLASS_DEFINITIONS.csv'),('真实短折返与门槛图',S/'local/STRUCTURE_AND_THRESHOLD_RGB_DETAIL.png'),('失败来源环图',S/'local/FAILURE_SOURCE_RING_MATRIX.png'),('联合n12m6原答与融合',S/'figures/2fa2eea81fbc17d689ffb72f/ERP_BEV.png'),('完整案例图索引',S/'figures/CASE_FIGURE_INDEX.csv'),('实际解压重聚合回执',D/'STAGE06_CASES_READ_CHECK.json')]
pd.DataFrame([dict(description=n,local_path=str(p),bytes=p.stat().st_size,exists=p.exists())for n,p in independent]).to_csv(D/'STAGE06_INDEPENDENT_DOWNLOADS.csv',index=False,encoding='utf-8-sig')
print(json.dumps(dict(archive=str(archive),bytes=archive.stat().st_size,files=len(files),decoded_tables_and_json=len(reads),markdown_links=len(links),standalone_rebuild=True),ensure_ascii=False),flush=True)
