"""Save new endpoint geometry once, all stage scalars, and exact reuse locators.

Prior global batches and the other-target panel already contain their geometry.
Historical cached geometry not archived this round remains reproducible from
exact team requests and the unchanged target-pool inputs, rather than copied.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,os,re,zipfile
from pathlib import Path
import pandas as pd

W=Path(__file__).resolve().parents[1]
TEAM=re.compile(r'"team_key"\s*:\s*"([^"\n]+)"')
COMMIT='a476461d7ede8db95da43de4139e612c05e618bc'

def jsave(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);b=json.dumps(value,ensure_ascii=False,indent=2).encode()
 if path.suffix=='.gz':b=gzip.compress(b,mtime=0)
 tmp=path.with_name(path.name+'.writing');tmp.write_bytes(b);tmp.replace(path)

def write_csv(path,rows,columns=None):
 path.parent.mkdir(parents=True,exist_ok=True);df=pd.DataFrame(rows,columns=columns);tmp=path.with_name(path.name+'.writing')
 df.to_csv(tmp,index=False,encoding='utf-8-sig',compression={'method':'gzip','mtime':0} if path.suffix=='.gz' else None);tmp.replace(path)

def scan_keys(root,archive,stage):
 for fn in sorted(root.rglob('part_*.jsonl.gz')):
  with gzip.open(fn,'rt',encoding='utf-8-sig') as f:
   for line in f:
    match=TEAM.search(line);assert match,fn
    yield dict(team_key=match.group(1),geometry_archive=archive,geometry_file=str(fn.relative_to(W)),geometry_source_stage=stage)

def prior_geometry_catalog():
 cache=W/'deliverables/BASE_SAVED_GEOMETRY_CATALOG.csv.gz'
 if cache.exists():return {r['team_key']:r for r in pd.read_csv(cache).to_dict('records')}
 rows=[]
 for fn in sorted((W/'deliverables').glob('GLOBAL_ENDPOINT_BATCH_*_RECEIPT.json')):
  d=json.loads(fn.read_text());archive=Path(d['file']);assert archive.exists()
  for pool in d['pools']:
   rows.extend(scan_keys(W/'experiment/global_screen_endpoints/pools'/pool['pool_id'],archive.name,'global_'+d['batch']))
 other=json.loads((W/'deliverables/STAGE03A_RECEIPT.json').read_text())
 archive=Path(other.get('file') or other.get('path') or W/'deliverables/HOHONET_v21_阶段03A_31合法新增空间完整配比与端点_20261029.zip')
 assert archive.exists()
 rows.extend(scan_keys(W/'composition/other_targets_endpoints/pools',archive.name,'other_targets_03A'))
 catalog={}
 for r in rows:catalog.setdefault(r['team_key'],r)
 write_csv(cache,list(catalog.values()));return catalog

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--stage',required=True);ap.add_argument('--repo',required=True);ap.add_argument('--previous-stages',nargs='*',default=[]);a=ap.parse_args()
 stage=a.stage;design=W/'experiment'/(stage+'_design');endpoints=W/'experiment'/(stage+'_endpoints');out=W/'endpoint_delivery'/stage;out.mkdir(parents=True,exist_ok=True)
 run=json.loads((endpoints/'RUN_RECEIPT.json').read_text());assert run['all_complete']
 requests=pd.read_csv(design/'REQUESTS.csv.gz');wanted=set(requests.team_key);assert len(wanted)==len(requests)
 scal=pd.read_csv(endpoints/'ENDPOINT_SCALARS.csv.gz',low_memory=False);assert set(scal.team_key)==wanted and len(scal)==len(wanted)
 catalog=prior_geometry_catalog()
 for previous in a.previous_stages:
  pc=W/'endpoint_delivery'/previous/'NEW_GEOMETRY_CATALOG.csv.gz'
  for r in pd.read_csv(pc).to_dict('records'):
   assert r['team_key'] not in catalog;catalog[r['team_key']]=r
 filename=f'HOHONET_v21_补充端点_{stage}_delta_20261029.zip';zip_path=W/'deliverables'/filename
 rows=[];newcatalog=[];newbuffer=[];files=[];seen=set();historical=[];part=0
 def flush():
  nonlocal part
  if not newbuffer:return
  part+=1;fn=out/'new_geometry'/f'part_{part:05d}.jsonl.gz';fn.parent.mkdir(parents=True,exist_ok=True)
  tmp=fn.with_name(fn.name+'.writing')
  with gzip.open(tmp,'wt',encoding='utf-8',compresslevel=4) as f:
   for r in newbuffer:f.write(json.dumps(r,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
  with tmp.open('rb') as f:os.fsync(f.fileno())
  tmp.replace(fn);files.append(fn)
  for r in newbuffer:
   locator=dict(team_key=r['team_key'],geometry_archive=filename,geometry_file=str(fn.relative_to(W)),geometry_source_stage=stage+'_delta')
   newcatalog.append(locator)
  newbuffer.clear()
 for fn in sorted((endpoints/'pools').glob('*/part_*.jsonl.gz')):
  with gzip.open(fn,'rt',encoding='utf-8-sig') as f:
   for line in f:
    r=json.loads(line);key=r['team_key'];assert key in wanted and key not in seen;seen.add(key)
    ws=r['member_workers'] if isinstance(r['member_workers'],list) else r['member_workers'].split('|')
    assert len(ws)==len(set(ws))==r['k']
    digest=hashlib.sha256(json.dumps(sorted(ws),sort_keys=True,separators=(',',':')).encode()).hexdigest()[:20]
    assert key==r['pool_id']+'__'+digest
    record=dict(team_key=key,pool_id=r['pool_id'],n=r['k'],member_workers='|'.join(sorted(ws)),reference_id=r['reference_id'],reference_version=r['reference_version'],
     current_stage=stage,endpoint_reused=bool(r.get('endpoint_reused',False)),cache_source=r.get('cache_source',''),endpoint_origin=r.get('endpoint_origin',''),
     input_pool_sha256=r.get('input_pool_sha256',''))
    if key in catalog:
     record.update(catalog[key]);record['geometry_resolution']='previous_saved_batch'
    elif not r.get('endpoint_reused',False):
     record.update(geometry_resolution='this_delta',geometry_archive=filename,geometry_source_stage=stage+'_delta')
     newbuffer.append(r)
     if len(newbuffer)>=500:flush()
    else:
     record.update(geometry_resolution='historical_cache_recompute_exact_request',geometry_archive='',geometry_file='',geometry_source_stage='historical_not_repacked')
     historical.append(key)
    rows.append(record)
 flush();assert seen==wanted
 newmap={r['team_key']:r for r in newcatalog};assert len(newmap)==len(newcatalog) and not(set(newmap)&set(catalog))
 for r in rows:
  if r['team_key'] in newmap:r.update(newmap[r['team_key']])
 write_csv(out/'TEAM_GEOMETRY_SOURCES.csv.gz',rows);write_csv(out/'NEW_GEOMETRY_CATALOG.csv.gz',newcatalog,columns=['team_key','geometry_archive','geometry_file','geometry_source_stage'])
 fallback=requests[requests.team_key.isin(historical)];write_csv(out/'RECOMPUTE_HISTORICAL_CACHE_REQUESTS.csv.gz',fallback.to_dict('records'),columns=list(requests.columns))
 needed_pools=set(fallback.pool_id);repo=Path(a.repo);poolfiles=[repo/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json',repo/'research/data/releases/v2.1/admitted_space_extension/pools/INPUT_SNAPSHOT.json']
 allpools={p['pool_id']:p for fn in poolfiles for p in json.loads(fn.read_text())['images']}
 jsave(out/'RECOMPUTE_INPUT_POOLS.json.gz',dict(data_release='v2.1',source_commit=COMMIT,images=[allpools[p] for p in sorted(needed_pools)],note='Whole unchanged pool objects for the historical cached teams omitted from geometry packaging; no target or record subset changes inside a pool.'))
 n_previous=sum(r['geometry_resolution']=='previous_saved_batch' for r in rows);assert len(newcatalog)+n_previous+len(historical)==len(requests)
 receipt=dict(stage=stage,data_release='v2.1',source_commit=COMMIT,all_request_scalars=len(scal),geometry_teams_in_this_package=len(newcatalog),previous_saved_geometry_teams=n_previous,
  historical_cache_geometry_not_repacked=len(historical),historical_recompute_pools=len(needed_pools),new_geometry_overlap_prior_packages=0,
  unique_member_team_checks_passed=True,new_geometry_files=len(files),Q_available=int(scal.B8L2.notna().sum()),Q_missing=int(scal.B8L2.isna().sum()),
  endpoint_native_count=int((~scal.endpoint_reused.astype(bool)).sum()),endpoint_reused_count=int(scal.endpoint_reused.astype(bool).sum()),
  requests_sha256=hashlib.sha256((design/'REQUESTS.csv.gz').read_bytes()).hexdigest(),scalars_sha256=hashlib.sha256((endpoints/'ENDPOINT_SCALARS.csv.gz').read_bytes()).hexdigest(),
  classification_modified=False,extra_fusion_during_packaging=0)
 jsave(out/'DELIVERY_RECEIPT.json',receipt)
 readme=f'''# {stage} 端点增量交付\n\n底层 v2.1，固定提交 `{COMMIT}`。本包有全部 {len(requests):,} 个请求的标量，新增完整几何 {len(newcatalog):,} 队；{n_previous:,} 队几何指向此前已保存的包，另 {len(historical):,} 队历史缓存仅保留精确复算入口。这里没有新增融合，也不重复打包旧大缓存。\n\n`TEAM_GEOMETRY_SOURCES.csv.gz` 按 team_key 给出全部请求的归属和准确包内几何文件。`NEW_GEOMETRY_CATALOG.csv.gz` 只列本包几何。原队伍请求和全部标量仍使用 `experiment/{stage}_design/REQUESTS.csv.gz` 与 `experiment/{stage}_endpoints/ENDPOINT_SCALARS.csv.gz` 的原格式。逐事件在对应主题交付，不重复几何。\n\n历史缓存没有打包的队伍，可用本包 `RECOMPUTE_HISTORICAL_CACHE_REQUESTS.csv.gz`、`RECOMPUTE_INPUT_POOLS.json.gz` 和原生 `experiment/run_registered.py` 重算；pool 对象完整保留，输入 hash 不变。命令（工作目录为解压后的研究包根目录，TASK_REPO 是固定提交的完整仓库）：\n\n```bash\npython experiment/run_registered.py --repo "$TASK_REPO" --pools endpoint_delivery/{stage}/RECOMPUTE_INPUT_POOLS.json.gz --requests endpoint_delivery/{stage}/RECOMPUTE_HISTORICAL_CACHE_REQUESTS.csv.gz --output restored_geometry/{stage} --jobs 6\n```\n\n若历史复算请求数为 0，无需运行该命令。Q 缺失保留为空和失败状态，不伪填零分。完整几何包含底面无效等失败队，不能只读取可评分队。\n'''
 (out/'README.md').write_text(readme)
 files += list(out.glob('*.gz'))+list(out.glob('*.json'))+[out/'README.md',endpoints/'ENDPOINT_SCALARS.csv.gz',endpoints/'RUN_RECEIPT.json',endpoints/'CACHE_COVERAGE.json',endpoints/'RUN_PLAN.json',design/'REQUESTS.csv.gz']
 if (endpoints/'CUMULATIVE_COMPLETION.json').exists():files.append(endpoints/'CUMULATIVE_COMPLETION.json')
 files += [W/'experiment'/name for name in ['run_registered.py','benchmark_engine.py','capacity_space.py','register_adaptive.py']]+[Path(__file__).resolve()]
 assert len(files)==len(set(files))
 tmp=zip_path.with_suffix('.writing')
 with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
  for fn in files:assert fn.exists();z.write(fn,str(fn.relative_to(W)))
 with tmp.open('rb') as f:os.fsync(f.fileno())
 tmp.replace(zip_path)
 archived_keys=set()
 with zipfile.ZipFile(zip_path) as z:
  assert z.testzip() is None
  for name in z.namelist():
   if '/new_geometry/' not in name:continue
   for line in gzip.decompress(z.read(name)).decode().splitlines():
    key=json.loads(line)['team_key'];assert key not in archived_keys;archived_keys.add(key)
 assert archived_keys==set(newmap)
 receipt.update(file=str(zip_path),bytes=zip_path.stat().st_size,sha256=hashlib.sha256(zip_path.read_bytes()).hexdigest(),zip_crc_passed=True,
  packaged_new_geometry_rows_read_back=len(archived_keys))
 jsave(W/'deliverables'/f'ENDPOINT_DELTA_{stage}_RECEIPT.json',receipt)
 print(json.dumps(receipt,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
