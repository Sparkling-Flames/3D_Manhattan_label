#!/usr/bin/env python3
"""One entry point to replay the forward v2 study from frozen audited inputs.

Requires the repo snapshot and the independently produced root evidence table.
It reproduces statistical analysis, not the source-dependent collection audit.
Output into a NEW folder is recommended while downstream consumers read results.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    here=Path(__file__).resolve().parent
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--evidence',type=Path,required=True,
                    help='Root audit/person_evidence_62.csv; source for independent evidence join only')
    ap.add_argument('--verify-inputs-only',action='store_true')
    ap.add_argument('--resume',action='store_true',
                    help='Retain the same-input, same-code successful prefix recorded in an incomplete receipt')
    a=ap.parse_args();repo=a.repo.resolve();out=a.out.resolve();ev=a.evidence.resolve()
    inputs={
      'research/statistics/v2_evidence_audit_20261019/records.json.gz':'46ee9890a1a56264c8955538f47c650cbe893662e7cefc21e360a3e00eca9251',
      'research/statistics/v2_integrated_analysis_20261019/tables.json.gz':'1a288e826dace32daf9da91cb6abdd6cc7d9df776dd24c854889a2107872404b',
      'research/workers/pro_personnel_v2_20261019/analysis_context.json.gz':'95455b81cc0de947d704ee2e0935ee795f9c8e0e9de33bd9d1b93e554a6742a2'}
    for relative,expected in inputs.items():
        actual=sha(repo/relative)
        if actual!=expected:
            raise SystemExit(f'Frozen input mismatch: {relative}. Supply the declared commit; do not silently adopt changed evidence.')
    if not ev.exists():raise SystemExit(f'Independent evidence join input missing: {ev}')
    print('Frozen input hashes verified; external evidence',sha(ev),flush=True)
    if a.verify_inputs_only:return
    out.mkdir(parents=True,exist_ok=True)
    for filename in ['REGISTRATION.json','REGISTRATION_DTYPE_EXTENSION.json','VALIDATION_REVISIONS.json','FOLD_SCHEMA.json','WORDING_CLARIFICATIONS.json']:
        if (here/filename).resolve()!=(out/filename).resolve():shutil.copy2(here/filename,out/filename)
    env=os.environ.copy();env['OPENBLAS_NUM_THREADS']='1';env['OMP_NUM_THREADS']='1';env['PYTHONWARNINGS']='ignore'
    sequence=[
      ('run_profiles.py',['--repo',str(repo),'--out',str(out)]),
      ('augment_type_fines.py',['--out',str(out)]),
      ('build_nested_features.py',['--out',str(out)]),
      ('audit_profiles.py',['--repo',str(repo),'--out',str(out)]),
      ('diagnostics_and_tables.py',['--repo',str(repo),'--out',str(out),'--evidence',str(ev)]),
      ('diagnose_class_information.py',['--out',str(out)]),
      ('efficiency_within_person.py',['--out',str(out)]),
      ('room_weighting.py',['--repo',str(repo),'--out',str(out)]),
      ('build_forward_report.py',['--out',str(out)])]
    receipt={'source_commit':'82c6164b0d4630de5316199c92aa405930973168',
             'inputs_sha256':inputs,'independent_evidence_sha256':sha(ev),
             'exclusion_text_review_sha256':sha(ev.parent/'exclusion_text_review_25.csv')if (ev.parent/'exclusion_text_review_25.csv').exists()else None,
             'python':sys.version,'packages':{x:importlib.metadata.version(x)for x in ['numpy','pandas','scipy']},
             'steps':[],'collection_pipeline_independently_rebuilt':False}
    receipt_path=out/'REPRODUCE_FORWARD_RECEIPT.json'
    start=0
    if a.resume:
        if not receipt_path.exists():raise SystemExit('--resume requires an existing replay receipt')
        previous=json.loads(receipt_path.read_text())
        if previous.get('inputs_sha256')!=inputs or previous.get('independent_evidence_sha256')!=sha(ev):
            raise SystemExit('Cannot resume across changed inputs')
        for prior,(script,args)in zip(previous.get('steps',[]),sequence):
            if prior['exit_code']!=0:break
            if prior['script']!=script or prior['code_sha256']!=sha(here/script) or prior['arguments']!=args:
                raise SystemExit('Completed-prefix code or arguments changed; use a fresh output directory')
            receipt['steps'].append(prior);start+=1
        receipt['previous_incomplete_attempts']=previous.get('previous_incomplete_attempts',[])+[previous.get('steps',[])]
        for prior in previous.get('steps',[])[start:]:
            failed_log=out/prior['log']
            if failed_log.exists():shutil.copy2(failed_log,failed_log.with_suffix('.previous_attempt.log'))
        receipt['resumed_successful_prefix_steps']=start
        print('Resume retains',start,'successful steps with matching code and input hashes',flush=True)
    for index,(script,args)in enumerate(sequence,1):
        if index<=start:continue
        started=time.time();cmd=[sys.executable,str(here/script),*args];log=out/('replay_'+Path(script).stem+'.log')
        print(f'{index}/{len(sequence)} {script}',flush=True)
        with log.open('w')as sink:run=subprocess.run(cmd,env=env,stdout=sink,stderr=subprocess.STDOUT)
        receipt['steps'].append(dict(script=script,code_sha256=sha(here/script),arguments=args,
                                     exit_code=run.returncode,runtime_seconds=time.time()-started,log=log.name))
        receipt['completed']=run.returncode==0 and index==len(sequence)
        receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
        if run.returncode:raise SystemExit(f'{script} failed; see {log}')
    print('COMPLETE',out/'FORWARD_REPORT_ZH.html',flush=True)


if __name__=='__main__':main()
