"""Run bounded reporting analyses once their complete upstream tables exist."""
from pathlib import Path
import argparse,json,subprocess,sys,time,os


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True)
    args=ap.parse_args();base=args.base.resolve();out=base/'analysis_reporting26';out.mkdir(exist_ok=True)
    jobs=[
      ('policy_named_blocks',base/'analysis_policy26/results/RECEIPT.json',
       [sys.executable,str(base/'analysis_policy26/restore_named_loss_components.py'),'--base',str(base)]),
      ('policy_presentation',base/'analysis_policy26/results/RECEIPT.json',
       [sys.executable,str(base/'analysis_policy26/report_policy_precision.py'),'--base',str(base)]),
      ('mean_precision_budget',base/'analysis_precision26/results_stage2/NATURAL_FINALIZATION_COMPLETE.json',
       [sys.executable,str(base/'analysis_reporting26/precision_budget_tables.py'),'--base',str(base)]),
      ('fixed_thresholds',base/'analysis_precision26/results_stage2/NATURAL_FINALIZATION_COMPLETE.json',
       [sys.executable,str(base/'analysis_reporting26/fixed_threshold_attainment.py'),'--base',str(base)]),
      ('adjacent_parity',base/'analysis_precision26/results_stage2/NATURAL_FINALIZATION_COMPLETE.json',
       [sys.executable,str(base/'analysis_shape26/adjacent_and_parity.py'),'--base',str(base)])]
    while True:
        for name,dependency,command in jobs:
            target=out/(name+'_COMPLETE.json')
            if target.exists() or not dependency.exists():continue
            started=time.time()
            r=subprocess.run(command,capture_output=True,text=True)
            receipt=dict(job=name,complete=r.returncode==0,dependency=str(dependency),command=command,
                seconds=time.time()-started,returncode=r.returncode,stdout_tail=r.stdout[-6000:],stderr_tail=r.stderr[-6000:])
            path=target if r.returncode==0 else out/(name+'_FAILED.json')
            tmp=path.with_suffix('.writing');tmp.write_text(json.dumps(receipt,ensure_ascii=False,indent=2));tmp.replace(path)
            if r.returncode:raise SystemExit(r.returncode)
        if all((out/(name+'_COMPLETE.json')).exists() for name,_,_ in jobs):break
        time.sleep(30)
    (out/'ROOT_ANALYSES_COMPLETE.json').write_text(json.dumps(dict(complete=True,jobs=[x[0] for x in jobs],
        new_endpoints=0,new_orders=0),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
