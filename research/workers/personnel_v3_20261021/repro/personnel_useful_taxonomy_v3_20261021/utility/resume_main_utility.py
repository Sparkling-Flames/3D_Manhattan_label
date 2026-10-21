"""Wait for atomic native batches, then run one condition sequentially.

This optional orchestration never computes fusion or changes the frozen panel.
Each family still checkpoints its own selected teams and evaluated outcomes.
"""
from pathlib import Path
import argparse,json,subprocess,sys,time
import pandas as pd
from prepare_training import HERE,atomic_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--condition',choices=['manual','semi'],required=True)
    p.add_argument('--wait',action='store_true');a=p.parse_args()
    comp=HERE.parent/'composition'
    plan=pd.read_csv(comp/'BATCH_PLAN.csv');batches=list(plan.loc[plan.condition.eq(a.condition),'batch_id'])
    status=HERE/('MAIN_RUN_'+a.condition.upper()+'.json');last=None
    while True:
        missing=[b for b in batches if not (comp/'batches'/b/'COMPLETION.json').exists()]
        if missing!=last:
            print('WAIT_NATIVE',a.condition,missing,flush=True)
            atomic_json(dict(condition=a.condition,state='waiting_native' if missing else 'native_ready',
                required_batches=batches,missing_batches=missing),status);last=missing
        if not missing:break
        if not a.wait:raise SystemExit('Required native batches not complete')
        time.sleep(5)
    jobs=[('select','cross_panel_LOBO'),('evaluate','cross_panel_LOBO'),('evaluate','historical_only')]
    for phase,regime in jobs:
        atomic_json(dict(condition=a.condition,state='running',phase=phase,regime=regime),status)
        cmd=[sys.executable,str(HERE/'run_policy_batch.py'),phase,'--regime',regime,'--conditions',a.condition]
        print('RUN',cmd,flush=True);subprocess.run(cmd,check=True)
    atomic_json(dict(condition=a.condition,state='complete',jobs=jobs),status)

if __name__=='__main__':main()
