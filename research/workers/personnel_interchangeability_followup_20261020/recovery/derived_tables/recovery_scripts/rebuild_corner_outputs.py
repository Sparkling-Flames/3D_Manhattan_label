"""Rebuild missing derived corner tables from frozen requests, no classification fitting."""
from pathlib import Path
import subprocess,sys,json,hashlib,time
R=Path(__file__).resolve().parent;P=R/'venv/bin/python';B=R/'unpacked';S=R/'audit_corner';A=R/'audit_learning';O=R/'recomputed';O.mkdir(exist_ok=True)
def run(args,log):
 with (O/log).open('w') as f:subprocess.run([str(P),*map(str,args)],stdout=f,stderr=subprocess.STDOUT,check=True,cwd=R)
for mode,req in [('history',A/'history_blocks/history_block_requests.json.gz'),('fresh',A/'fresh_blocks/fresh_block_requests.json.gz'),('core',B/'interchangeability_20261020/core_replay/CORE_REQUESTS.json.gz')]:
 native=R/'audit_replay'/('history_corner_blocks' if mode=='history' else 'fresh_corner_blocks' if mode=='fresh' else 'core_native')
 run([B/'analysis/composition/fusion_runner.py','--restored',R/'restored','--requests',req,'--out',native,'--jobs',3],mode+'_native.log')
 if mode in ['history','fresh']:
  out=O/('history_block_metrics' if mode=='history' else 'common_library')
  args=[S/'evaluate_common_library.py','--requests',req,'--native',native,'--out',out,'--jobs',2]
  if mode=='history':args+=['--pairs-only']
  run(args,mode+'_common.log')
 if mode in ['fresh','core']:
  out=O/('fresh_blocks' if mode=='fresh' else 'core')
  run([S/'evaluate_corner_extension.py','--bundle',B,'--native',native,'--requests',req,'--source','fresh_discovery_nominated_block_probe' if mode=='fresh' else 'core_native','--out',out],mode+'_corner.log')
 if mode=='fresh':
  for k in [2,3]:
   mid=f'B_direct_m2_composition_K{k}'
   run([S/'evaluate_common_library.py','--requests',req,'--native',native,'--reuse-pairs',O/'common_library/COMMON_ENDPOINT_PAIRS.csv.gz','--labels-json',S/'direct_block_assessment'/mid/'LABEL_OVERRIDE.json','--out',O/'direct_block_assessment'/mid,'--phase','full_prespecified_family_internal_outcome_check_no_reselection'],f'direct_K{k}.log')
 print('COMPLETED',mode,flush=True)
