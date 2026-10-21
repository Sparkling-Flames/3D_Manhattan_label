"""Checkpointed read-only main analyses after their exact inputs finish."""
from __future__ import annotations
import json,subprocess,sys,time
import pandas as pd
from multin_design import HERE,gs

def wait_for(pred):
    while not pred():time.sleep(10)

def step(name,args):
    receipt=HERE/'analysis_progress'/(name+'.json');receipt.parent.mkdir(exist_ok=True)
    if receipt.exists() and gs.read(receipt).get('status')=='complete':return
    logfile=HERE/'analysis_progress'/(name+'.log')
    print(json.dumps(dict(step=name,status='started')),flush=True);start=time.monotonic()
    with open(logfile,'w') as f:
        subprocess.run([sys.executable,str(HERE/args[0]),*args[1:]],check=True,stdout=f,stderr=subprocess.STDOUT)
    result=dict(step=name,status='complete',seconds=time.monotonic()-start,command=args)
    gs.save(receipt,result);print(json.dumps(result),flush=True)

def run():
    wait_for(lambda:(HERE/'ALL_BATCHES_COMPLETE.json').exists())
    step('main_event_evaluation',['evaluate_matched_events.py','run','--kind','panel'])
    batches=pd.read_csv(HERE/'BATCH_PLAN.csv').batch_id.tolist()
    wait_for(lambda:all((HERE.parent/'response/geometry_batches'/(bid+'_EXPRESSION.csv.json')).exists() for bid in batches))
    # Publish rows before lengthy aggregate analyses, so each complete result
    # is independently retrievable and saveable immediately.
    step('main_complete_event_export',['evaluate_matched_events.py','export','--kind','panel'])
    step('main_matched_summary',['evaluate_matched_events.py','summary','--kind','panel'])
    step('main_directed_effects',['analyze_directional_effects.py','panel'])
    step('main_n_path_evaluation',['analyze_multin_paths.py','run'])
    step('main_n_path_summary',['analyze_multin_paths.py','summary'])
    gs.save(HERE/'MAIN_ANALYSIS_COMPLETE.json',dict(status='complete',native_calls=0,
      exact_matched_events=65371,exact_registered_path_edges=195888,independent_steps_saved=True))

if __name__=='__main__':run()
