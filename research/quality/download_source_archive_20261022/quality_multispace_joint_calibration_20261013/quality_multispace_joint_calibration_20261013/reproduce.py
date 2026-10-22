#!/usr/bin/env python3
"""Rebuild this study in a fresh workspace and compare complete scientific outputs.

Usage: python reproduce.py --out /absolute/path/to/new_replay_directory
No original large ZIP or network is required. Delivered frozen inputs are copied
unchanged; all routing, descriptor, control, calibration and integration outputs
are deleted in the working copy before their producing commands are executed.
"""
from __future__ import annotations
import argparse, concurrent.futures, gzip, hashlib, json, math, os, shutil, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
IGNORE_METADATA={'elapsed_seconds','elapsed_s','wall_seconds','wall_time_seconds','total_seconds','runtime_seconds','timing_seconds','seconds'}
PATH_METADATA={'baseline_argument'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def protected(root):
    return {str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*')) if p.is_file() and not any(t in p.parts for t in ['__pycache__','.git']) and not p.name.endswith(('.pyc','.log'))}
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();out=a.out.resolve()
    if out==ROOT or out.is_relative_to(ROOT):raise ValueError('Use a new directory outside the delivered package')
    if out.exists() and any(out.iterdir()):raise ValueError('Replay directory must be new or empty')
    out.mkdir(parents=True,exist_ok=True);logs=out/'logs';logs.mkdir();work=out/'workspace';start=time.monotonic();before=protected(ROOT)
    shutil.copytree(ROOT,work,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.log','*_standalone.html'))
    for module in ['experiments','calibration','routing','integration']:
        for name in ['results','figures','validation']:
            p=work/module/name
            if p.exists():shutil.rmtree(p)
    for p in (work/'review').iterdir():
        if p.is_file() and (p.suffix in ['.png','.json'] or p.suffix=='.html' and p.name!='review_template.html') and p.name!='original_image_manifest.json':p.unlink()
    steps=[];env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',MPLCONFIGDIR=str(out/'mpl_cache'))
    def run(label,args):
        ts=time.monotonic();log=logs/(label+'.log')
        with log.open('w') as f:r=subprocess.run(args,cwd=work,env=env,stdout=f,stderr=subprocess.STDOUT)
        row=dict(stage=label,command=args[1:] if args[0]==sys.executable else args,returncode=r.returncode,seconds=time.monotonic()-ts,log=str(log.relative_to(out)));steps.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
        if r.returncode:raise RuntimeError(label+' failed; see '+str(log))
    py=[sys.executable,'-B'];src=['--source','baseline']
    def experiment_stages():
        for name,args in [
            ('export_real_descriptors',src),
            ('axis_switch_and_joint_hinge',['--descriptors','experiments/results/real_direction_descriptors.json']),
            ('run_targeted_experiments',src),('verify_sampling',src),('projection_extreme_extension',src),
            ('verify_input_alignment',src+['--local-results','sources/main/research/quality_parallel_local_20261012/record_results.json']),
            ('validate_candidates',src+['--config','calibration/recommended_parameters.json']),
            ('summarize_analytic_diagnostics',src),('render_experiments',[])]:run('experiments_'+name,py+['experiments/'+name+'.py']+args)
    def routing_stages():
        for name in ['run_routing','verify_routing','numerical_spot_check']:run('routing_'+name,py+['routing/'+name+'.py','--baseline','baseline'])
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            jobs=[pool.submit(experiment_stages),pool.submit(routing_stages)]
            for job in jobs:job.result()
        for name in ['prepare_inputs','run_search','physical_controls','analyze_candidates','verify_calibration','render_calibration']:run('calibration_'+name,py+['calibration/'+name+'.py'])
        run('integration',py+['integration/run_impact.py']);run('w019_ledger',py+['integration/verify_w019.py'])
        for rid in ['R00397','R03197']:run('cli_'+rid,py+['assess.py','--record-id',rid,'--out','integration/results/cli_'+rid+'.json'])
        run('cli_interfaces',py+['verification/verify_interfaces.py'])
        run('review_build',py+['review/build_review.py'])
        node=os.environ.get('CODEX_PRIMARY_RUNTIME_NODE') or shutil.which('node');ui=bool(node)
        if node:run('review_dom_canvas',[node,'review/verify_review.mjs','review'])
        normalize_count={};numeric_count=0;max_difference=0.;failures=[];compared=[]
        def norm(x):
            if isinstance(x,dict):
                d={}
                for k,v in x.items():
                    if k in IGNORE_METADATA:normalize_count[k]=normalize_count.get(k,0)+1;continue
                    if k in PATH_METADATA:d[k]='<verified-baseline-directory>';continue
                    d[k]=norm(v)
                return d
            if isinstance(x,list):return [norm(v) for v in x]
            if isinstance(x,str):return x.replace(str(ROOT),'<PACKAGE>').replace(str(work),'<PACKAGE>')
            return x
        def compare(x,y,where):
            nonlocal numeric_count,max_difference
            if isinstance(x,bool) or isinstance(y,bool):
                if x!=y:failures.append(where+': boolean mismatch')
            elif isinstance(x,(int,float)) and isinstance(y,(int,float)):
                numeric_count+=1;delta=abs(x-y);max_difference=max(max_difference,delta)
                if not math.isclose(x,y,rel_tol=1e-11,abs_tol=1e-9):failures.append(where+f': numeric mismatch {x} != {y}')
            elif type(x)!=type(y):failures.append(where+': type mismatch')
            elif isinstance(x,dict):
                if x.keys()!=y.keys():failures.append(where+': keys differ '+str(x.keys()^y.keys()))
                for k in x.keys()&y.keys():compare(x[k],y[k],where+'/'+k)
            elif isinstance(x,list):
                if len(x)!=len(y):failures.append(where+': length differs')
                for i,(a,b) in enumerate(zip(x,y)):compare(a,b,where+'/'+str(i))
            elif x!=y:failures.append(where+': value differs '+repr(x)[:160]+' != '+repr(y)[:160])
        patterns=['experiments/results/*.json','calibration/results/*.json','calibration/results/*.json.gz','calibration/results/*.csv.gz','routing/results/*.json','routing/validation/*.json','integration/results/*.json','review/blind_data.json','review/diagnostic_data.json','review/build_verification.json','verification/CLI_VERIFICATION.json']
        for pat in patterns:
            for p in sorted(work.glob(pat)):
                rel=p.relative_to(work);old=ROOT/rel
                if not old.exists():raise RuntimeError('No delivered expected result for generated '+str(rel))
                textnew=gzip.decompress(p.read_bytes()).decode('utf-8-sig') if p.suffix=='.gz' else p.read_text(encoding='utf-8-sig')
                textold=gzip.decompress(old.read_bytes()).decode('utf-8-sig') if old.suffix=='.gz' else old.read_text(encoding='utf-8-sig')
                nf=len(failures)
                if '.csv' in p.name:
                    if textnew!=textold:failures.append(str(rel)+': CSV content differs')
                else:compare(norm(json.loads(textold)),norm(json.loads(textnew)),str(rel))
                compared.append(dict(file=str(rel),semantic_equal=len(failures)==nf))
        unchanged=before==protected(ROOT);assert unchanged,'Delivered source changed during replay'
        result=dict(schema='fresh_full_scientific_replay_v1',status='passed' if not failures else 'failed',steps=steps,compared=compared,scientific_files_compared=len(compared),numeric_values_compared=numeric_count,max_absolute_numeric_difference=max_difference,comparison_tolerance=dict(atol=1e-9,rtol=1e-11),metadata_exclusions=normalize_count,metadata_path_normalization=list(PATH_METADATA),failures=failures[:100],failure_count=len(failures),delivered_source_unchanged=unchanged,delivered_source_file_count=len(before),review_actual_dom_canvas_executed=ui,native_browser_layout_test=False,no_new_human_labels=True,total_seconds=time.monotonic()-start)
        dump(out/'REPLAY_VERIFICATION.json',result)
        print(json.dumps({k:v for k,v in result.items() if k not in ['steps','compared','failures']},ensure_ascii=False),flush=True)
        if failures:raise RuntimeError('Scientific output mismatches: '+str(len(failures)))
    except Exception as e:
        if not (out/'REPLAY_VERIFICATION.json').exists():dump(out/'REPLAY_VERIFICATION.json',dict(status='failed',steps=steps,error=str(e)))
        raise
if __name__=='__main__':main()
