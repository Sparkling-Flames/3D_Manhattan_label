import json,pathlib,gzip,math,hashlib
import argparse
ap=argparse.ArgumentParser(description='Compare a completed Pro replay, treating only the source-identity inventory as path-keyed.');ap.add_argument('--source',type=pathlib.Path,required=True);ap.add_argument('--replay',type=pathlib.Path,required=True);ap.add_argument('--out',type=pathlib.Path,required=True);args=ap.parse_args();src=args.source.resolve();dst=args.replay.resolve()/'workspace';raw=json.load(open(args.replay/'REPLAY_VERIFICATION.json'))
ignore={'elapsed_seconds','elapsed_s','wall_seconds','wall_time_seconds','total_seconds','runtime_seconds','timing_seconds','seconds'}
def norm(x):
 if isinstance(x,dict):return {k:('<verified-baseline-directory>' if k=='baseline_argument' else norm(v)) for k,v in x.items() if k not in ignore}
 if isinstance(x,list):return [norm(v) for v in x]
 if isinstance(x,str):return x.replace(str(src),'<PACKAGE>').replace(str(dst),'<PACKAGE>')
 return x
counts={'numbers':0,'max_numeric_difference':0};fail=[]
def compare(a,b,loc):
 if isinstance(a,bool) or isinstance(b,bool):
  if a!=b:fail.append(loc)
 elif isinstance(a,(int,float)) and isinstance(b,(int,float)):
  counts['numbers']+=1;d=abs(a-b);counts['max_numeric_difference']=max(counts['max_numeric_difference'],d)
  if not math.isclose(a,b,rel_tol=1e-11,abs_tol=1e-9):fail.append(loc)
 elif type(a)!=type(b):fail.append(loc)
 elif isinstance(a,dict):
  if a.keys()!=b.keys():fail.append(loc)
  for k in a.keys()&b.keys():compare(a[k],b[k],loc+'/'+k)
 elif isinstance(a,list):
  if len(a)!=len(b):fail.append(loc)
  for i,(x,y) in enumerate(zip(a,b)):compare(x,y,loc+'/'+str(i))
 elif a!=b:fail.append(loc)
for rec in raw['compared']:
 f=rec['file']
 def read(p):return gzip.decompress(p.read_bytes()).decode('utf-8-sig') if p.suffix=='.gz' else p.read_text(encoding='utf-8-sig')
 a,b=read(src/f),read(dst/f)
 if '.csv' in f:
  if a!=b:fail.append(f)
 else:
  a,b=norm(json.loads(a)),norm(json.loads(b))
  if f=='routing/validation/source_git_blob_verification.json':
   assert len({r['path'] for r in a})==len(a)==16
   assert len({r['path'] for r in b})==len(b)==16
   a={r['path']:r for r in a};b={r['path']:r for r in b}
  compare(a,b,f)
out={'status':'passed_after_path_keyed_source_manifest_comparison' if not fail else 'failed','steps_executed':len(raw['steps']),'all_step_returncodes_zero':all(s['returncode']==0 for s in raw['steps']),'scientific_files':len(raw['compared']),**counts,'failures':fail,'original_wrapper_status':raw['status'],'original_wrapper_mismatches':raw['failure_count'],'fix_scope':'Only source_git_blob_verification.json is a path-keyed identity inventory; list ordering is not semantic. All 16 paths and hashes compared exactly. Geometry and routing lists NOT sorted or omitted. Runtime/path normalization same as supplied runner.','source_unchanged_during_replay':raw['delivered_source_unchanged'],'native_browser_test':False}
args.out.write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False,indent=2))
