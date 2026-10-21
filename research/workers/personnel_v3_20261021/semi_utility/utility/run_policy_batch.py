"""Sequential, checkpointed policy jobs; no concurrent mutable outputs."""
from pathlib import Path
import argparse,json,subprocess,sys,time
from prepare_training import atomic_json,HERE

def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['select','evaluate'])
    p.add_argument('--regime',choices=['historical_only','cross_panel_LOBO'],required=True)
    p.add_argument('--families',default='old_structure,new_behavior,new_joint,old_multivariate')
    p.add_argument('--conditions',default='manual,semi');p.add_argument('--skip-complete',action='store_true')
    a=p.parse_args();logdir=HERE/'logs';logdir.mkdir(exist_ok=True)
    for family in a.families.split(','):
        for condition in a.conditions.split(','):
            receipt=HERE/a.regime/condition/family/('SELECTION_RECEIPT.json' if a.phase=='select' else 'EVALUATION_RECEIPT.json')
            if a.skip_complete and receipt.exists():
                print('EXISTS',a.phase,a.regime,condition,family,flush=True);continue
            slug='__'.join([a.phase,a.regime,condition,family]);start=time.time()
            cmd=[sys.executable,str(HERE/'policy_study.py'),a.phase,'--regime',a.regime,'--condition',condition,'--family',family]
            print('START',slug,flush=True)
            with (logdir/(slug+'.log')).open('w') as f:
                r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
            atomic_json(dict(command=cmd,returncode=r.returncode,elapsed_seconds=time.time()-start,
                receipt=str(receipt),complete=receipt.exists() and r.returncode==0),logdir/(slug+'.json'))
            print('FINISHED',slug,'code',r.returncode,'seconds',round(time.time()-start,2),flush=True)
            if r.returncode:raise SystemExit(r.returncode)

if __name__=='__main__':main()
