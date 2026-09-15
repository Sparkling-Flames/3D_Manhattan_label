"""Run the fixed nested grid with bounded CPU parallelism and resumable outputs."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1');os.environ.setdefault('MKL_NUM_THREADS','1')
import argparse,concurrent.futures,json,traceback
from pathlib import Path
import pandas as pd
from tools.thesis_main.analysis.image_portrait.pro_core import OUT,write_json,write_csv
from tools.thesis_main.analysis.image_portrait.pro_predict import evaluate_feature,baseline_predictions,summarize

def job(name,record,root):
    t=pd.read_csv(OUT/'human/image_outcomes.csv');t=t[(t.view=='reviewed')&t.condition.isin(['manual','semi'])]
    try:evaluate_feature(name,record,Path(root),t);return dict(feature=name,status='completed')
    except Exception:return dict(feature=name,status='failed',error=traceback.format_exc())

def main(workers=3,names=None):
    root=OUT/'features';registry=json.loads((root/'registry.json').read_text());t=pd.read_csv(OUT/'human/image_outcomes.csv');t=t[(t.view=='reviewed')&t.condition.isin(['manual','semi'])]
    if not (OUT/'prediction/baselines.csv.gz').exists():baseline_predictions(t,pd.read_csv(OUT/'A/interpretable_inputs.csv'))
    jobs=[(n,r)for n,r in registry.items() if not r.get('exact_duplicate_of') and (not names or n in names)]
    # A/B baselines start first; high-dimensional fixed candidates then start early.
    jobs.sort(key=lambda nr:(0 if nr[0] in ['A_all_traits','A_scene_doorway','B_feedback','AB_traits_feedback','ABC_traits_feedback_shared'] else 1,-nr[1]['dimensions']))
    status=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as ex:
        future={ex.submit(job,n,r,str(root)):n for n,r in jobs}
        for f in concurrent.futures.as_completed(future):
            s=f.result();status.append(s);print(json.dumps(s),flush=True);write_json(OUT/'prediction/run_status_incremental.json',status)
    # Exact numerical duplicates are reported individually with their own name;
    # reuse avoids repeated computation, not omitted candidates or layer selection.
    for n,r in registry.items():
        d=r.get('exact_duplicate_of')
        if not d or (names and n not in names):continue
        for suffix in ['.csv.gz','.inner.csv.gz','.coverage.csv']:
            source=OUT/'prediction'/(d+suffix)
            if source.exists():
                a=pd.read_csv(source);a['feature']=n;write_csv('prediction/'+n+suffix,a)
        status.append(dict(feature=n,status='exact_duplicate_reused',source=d))
    write_json(OUT/'prediction/run_status.json',status);summarize()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=3);ap.add_argument('--names',nargs='*');args=ap.parse_args();main(args.workers,args.names)
