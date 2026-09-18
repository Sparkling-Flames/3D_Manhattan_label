"""Run unchanged recovered numerical code in a NEW directory; never overwrite delivered results."""
from pathlib import Path
import argparse,json,os,shutil,subprocess,sys

def main()->None:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    source=Path(__file__).resolve().parent/'full_study_20260918';out=a.output.expanduser().resolve()
    if out.exists():raise FileExistsError(f'Choose a new output directory: {out}')
    out.mkdir(parents=True)
    for name in ['code','inputs','model_snapshot','snapshot']:shutil.copytree(source/name,out/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.nbc','*.nbi'))
    (out/'results').mkdir();env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    for script in ['full_corpus.py','pointset_and_versions.py','model_linkage.py','model_prediction_check.py','source_validation.py','supplement_checks.py']:
        command=[sys.executable,'-u',str(out/'code'/script)]
        if script in ['full_corpus.py','pointset_and_versions.py']:command+=['--root',str(out)]
        print('Running',script,flush=True)
        with (out/'results'/(script+'.log')).open('w',encoding='utf-8')as log:subprocess.run(command,check=True,env=env,stdout=log,stderr=subprocess.STDOUT)
    import pandas as pd
    compared=[]
    for f in sorted((out/'results').glob('*.csv')):
        g=source/'results'/f.name
        if not g.exists():continue
        x=pd.read_csv(f);y=pd.read_csv(g);cols=sorted(x.columns)
        if set(cols)!=set(y.columns):raise AssertionError(f'Column mismatch: {f.name}')
        x=x[cols].sort_values(cols,kind='stable',na_position='last').reset_index(drop=True);y=y[cols].sort_values(cols,kind='stable',na_position='last').reset_index(drop=True)
        pd.testing.assert_frame_equal(x,y,check_exact=False,atol=1e-9,rtol=1e-9)
        compared.append({'file':f.name,'rows':len(x),'match':True})
    result={'status':'passed','tables':len(compared),'checks':compared,'atol':1e-9,'rtol':1e-9,'semantic_validation':False}
    (out/'REPRODUCTION_COMPARISON.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
