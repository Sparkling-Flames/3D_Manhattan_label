#!/usr/bin/env python3
"""Disjoint-fold orchestration; one writer per fold, no concurrent consolidation."""
import argparse,json,pathlib,subprocess,sys,time,hashlib
HERE=pathlib.Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--events',default=str(HERE.parent/'events/common_events.csv.gz'));p.add_argument('--jobs',type=int,default=3);p.add_argument('--force',action='store_true');p.add_argument('--implementation',choices=['original','fast'],default='fast');a=p.parse_args()
splits=json.loads((HERE/'FROZEN_BUILDING_SPLITS.json').read_text())['folds'];folds=list(splits)
groups=[folds[j::a.jobs] for j in range(a.jobs)]
logdir=HERE/'logs';logdir.mkdir(exist_ok=True)
procs=[];start=time.time()
for j,fs in enumerate(groups):
    if not fs:continue
    cmd=[sys.executable,str(HERE/('discover_reverse_types_fast.py' if a.implementation=='fast' else 'discover_reverse_types.py')),'--stage','discover','--events',a.events,'--folds',','.join(fs)]
    if a.force:cmd+=['--force']
    logpath=logdir/f'discovery_{a.implementation}_batch_{j}.log';f=logpath.open('w')
    child=subprocess.Popen(cmd,stdout=f,stderr=subprocess.STDOUT)
    procs.append((child,f,cmd,logpath))
results=[]
for child,f,cmd,path in procs:
    code=child.wait();f.close();results.append({'command':cmd,'exit_code':code,'log':str(path)})
receipt={'seconds':time.time()-start,'implementation':a.implementation,'jobs':a.jobs,'disjoint_fold_groups':groups,'results':results,
         'script_sha256':hashlib.sha256((HERE/'discover_reverse_types.py').read_bytes()).hexdigest(),
         'event_sha256':hashlib.sha256(pathlib.Path(a.events).read_bytes()).hexdigest()}
(HERE/f'BATCH_RUN_RECEIPT_{a.implementation}.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'seconds':receipt['seconds'],'exit_codes':[r['exit_code'] for r in results]},indent=2))
if any(r['exit_code'] for r in results):sys.exit(1)
