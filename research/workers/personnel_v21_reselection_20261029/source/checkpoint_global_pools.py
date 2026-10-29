from pathlib import Path
import argparse,gzip,json,hashlib,zipfile,os,csv
W=Path('/workspace/scratch/fe955c3c772c/personnel_v21_research_20261029')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--batch',required=True);ap.add_argument('--max-pools',type=int);a=ap.parse_args();out=W/'deliverables';root=W/'experiment/global_screen_endpoints'
 prior={}
 for p in out.glob('GLOBAL_ENDPOINT_BATCH_*_RECEIPT.json'):
  old=json.loads(p.read_text())
  if not old.get('file') or not Path(old['file']).exists():continue
  assert not (set(prior)&{r['pool_id'] for r in old['pools']}),'A prior complete pool appears in multiple saved batches.'
  prior.update({r['pool_id']:r for r in old['pools']})
 picked=[p for p in sorted((root/'pools').iterdir()) if (p/'CHECKS.json').exists() and p.name not in prior]
 if a.max_pools:picked=picked[:a.max_pools]
 rows=[];files=[];global_keys=set()
 for p in picked:
  ck=json.loads((p/'CHECKS.json').read_text());assert ck['complete'];n=valid=new=0;keys=set()
  for f in sorted(p.glob('part_*.jsonl.gz')):
   with gzip.open(f,'rt') as st:
    for ln in st:
     r=json.loads(ln);assert r['pool_id']==p.name;assert r['team_key'] not in keys and r['team_key'] not in global_keys;keys.add(r['team_key']);global_keys.add(r['team_key'])
     ws=r['member_workers'] if isinstance(r['member_workers'],list) else r['member_workers'].split('|');assert len(ws)==len(set(ws))==r['k']
     expected=p.name+'__'+hashlib.sha256(json.dumps(sorted(ws),sort_keys=True,separators=(',',':')).encode()).hexdigest()[:20];assert r['team_key']==expected
     n+=1;valid+=r.get('B8L2') is not None;new+=not r.get('endpoint_reused',False)
  assert n==ck['total'];rows.append({'pool_id':p.name,'teams':n,'Q_available':valid,'new_fusion':new,'prior_cache_reuse':n-new})
  files += [f for f in p.iterdir() if f.is_file() and f.suffix in ['.gz','.json']]
  files.append(root/'scalar_shards'/(p.name+'.csv.gz'))
 assert rows,'no new complete pools'
 receipt={'batch':a.batch,'complete_for_listed_pools_only':True,'global_requests':142270,'global_registered_events':69485,'source_commit':'a476461d7ede8db95da43de4139e612c05e618bc','data_release':'v2.1','pools':rows,'teams':sum(r['teams'] for r in rows),'prior_saved_pools':len(prior),'pool_overlap_with_prior_batches':0,'unique_actual_member_endpoints':len(global_keys),'max_pools_requested':a.max_pools}
 rec=out/f'GLOBAL_ENDPOINT_BATCH_{a.batch}_RECEIPT.json';rec.write_text(json.dumps(receipt,ensure_ascii=False,indent=2));files.append(rec)
 name=out/f'HOHONET_v21_广筛端点_批次{a.batch}_20261029.zip';tmp=name.with_suffix('.writing')
 with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
  for f in files:z.write(f,str(f.relative_to(W)))
 with tmp.open('rb') as f:os.fsync(f.fileno())
 tmp.replace(name)
 with zipfile.ZipFile(name) as z:assert z.testzip() is None
 receipt.update(file=str(name),bytes=name.stat().st_size,sha256=hashlib.sha256(name.read_bytes()).hexdigest());rec.write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
 request={'uploads':[{'local_path':str(name),'purpose':'create_library_file','library_artifact_type':'other'}]}
 (out/f'UPLOAD_GLOBAL_BATCH_{a.batch}.json').write_text(json.dumps(request,ensure_ascii=False));print(json.dumps({k:v for k,v in receipt.items() if k!='pools'},ensure_ascii=False))
if __name__=='__main__':main()
