"""Replay frozen requests without reselecting members or regenerating source data.

From the delivery root:
  python work_v2_20261019/fusion/run_reproduction.py --jobs 3
To rebuild only the descriptive tables after a completed run:
  python work_v2_20261019/fusion/run_reproduction.py --stage summaries
"""
from __future__ import annotations
import argparse
import subprocess
import sys
import time
from pool_io import OUT, ROOT, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--jobs',type=int,default=3)
    p.add_argument('--stage',choices=['all','initial','extension','verification','comparisons','summaries'],default='all')
    a=p.parse_args()
    steps={
        'initial':[['fusion_engine.py','--requests',str(OUT/'REQUESTS_INITIAL.json.gz'),'--jobs',str(a.jobs)]],
        'extension':[['fusion_engine.py','--requests',str(OUT/'REQUESTS_EXTENSION.json.gz'),'--jobs',str(a.jobs)]],
        'verification':[['verify_engine.py']],
        'comparisons':[['compare_fusions.py','--jobs',str(a.jobs)],['verify_comparison_files.py']],
        'summaries':[['analyze_fusion.py'],['analyze_policies.py'],['audit_output_status.py'],['select_forward_cases.py']],
    }
    receipt=dict(request_sha256={name:sha(OUT/name) for name in ['REQUESTS_INITIAL.json.gz','REQUESTS_EXTENSION.json.gz']},
        definitions='Replay exact saved members/orders; this does not recreate original source collection or image acquisition.',steps=[])
    for stage in steps if a.stage=='all' else [a.stage]:
        for args in steps[stage]:
            start=time.monotonic();cmd=[sys.executable,str(OUT/args[0]),*args[1:]]
            print('Running',stage,args[0],flush=True)
            completed=subprocess.run(cmd,cwd=ROOT,check=False)
            receipt['steps'].append(dict(stage=stage,script=args[0],args=args[1:],returncode=completed.returncode,seconds=time.monotonic()-start))
            save(OUT/'REPRODUCTION_RECEIPT.json',receipt)
            if completed.returncode:raise SystemExit(completed.returncode)
    print('Frozen-request replay complete.',flush=True)


if __name__=='__main__':main()
