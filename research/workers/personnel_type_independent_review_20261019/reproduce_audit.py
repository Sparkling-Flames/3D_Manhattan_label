#!/usr/bin/env python3
"""Run preserved audit scripts against a restored Part A tree in a NEW workspace.
Only relocate absolute paths; no changes to statistical or fusion calculations.
"""
import argparse,pathlib,json,hashlib,subprocess,sys,os
ap=argparse.ArgumentParser();ap.add_argument('--source',required=True,type=pathlib.Path);ap.add_argument('--output',required=True,type=pathlib.Path);ap.add_argument('--stage',choices=['metrics','partitions','diagnostics','fresh','all'],default='diagnostics');ap.add_argument('--execute',action='store_true');a=ap.parse_args()
source=a.source.resolve();out=a.output.resolve();here=pathlib.Path(__file__).resolve().parent
if not (source/'ANALYSIS_MANIFEST.json').is_file(): raise SystemExit('Expected restored work_personnel_typing_A_20261019 source directory')
if out.exists(): raise SystemExit('Output must be a NEW directory; refusing to overwrite existing audit results')
scripts={'metrics':['independent/recompute_metrics.py','independent/check_origin_and_contrasts.py'],'partitions':['independent/replay_partitions.py'],'diagnostics':['independent/recompute_scientific_diagnostics.py'],'fresh':['fresh_sample_audit.py','compare_fresh_states.py']}
selected=sum(scripts.values(),[]) if a.stage=='all' else scripts[a.stage]
plan={'source':str(source),'output':str(out),'stage':a.stage,'execute':a.execute,'scripts':selected,'archive_crc_rechecked':False,'scope':'Preserved bounded audit, not full Pro reproduction. Original ZIP verification receipts are historical; unpacked repository restoration cannot independently redo ZIP CRC.'}
print(json.dumps(plan,ensure_ascii=False,indent=2))
if not a.execute: raise SystemExit(0)
out.mkdir(parents=True);(out/'independent').mkdir();(out/'extracted').mkdir();(out/'extracted/work_personnel_typing_A_20261019').symlink_to(source,target_is_directory=True);(out/'adapted_scripts').mkdir()
receipt=[]
for name in selected:
 f=here/name;s=f.read_text();original_hash=hashlib.sha256(f.read_bytes()).hexdigest()
 s=s.replace('/workspace/shared/personnel_partA_audit_20261019',str(out)).replace("'/workspace/shared/pro_inventory_20261019/runtime_deps',",'')
 target=out/'adapted_scripts'/f.name;target.write_text(s)
 cmd=[sys.executable,str(target)]
 if f.name=='recompute_scientific_diagnostics.py': cmd += [str(source),'--output',str(out/'independent/SCIENTIFIC_DIAGNOSTICS.json')]
 env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
 p=subprocess.run(cmd,env=env,capture_output=True,text=True)
 (out/'adapted_scripts'/f'{f.stem}.log').write_text(p.stdout+'\n'+p.stderr)
 receipt.append({'script':name,'original_sha256':original_hash,'adapted_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'returncode':p.returncode})
 (out/'RUN_RECEIPT.json').write_text(json.dumps(dict(plan=plan,runs=receipt),ensure_ascii=False,indent=2)+'\n')
 if p.returncode: raise SystemExit(f'Failed: {name}; see logs; earlier results preserved')
