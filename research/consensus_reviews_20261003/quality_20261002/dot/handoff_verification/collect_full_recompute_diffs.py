"""Run unchanged handoff calculations and collect strict comparator failures.
This diagnostic does not turn the official verifier failure into a pass.
"""
import sys, json, math, contextlib, io, time, argparse
from pathlib import Path
from collections import Counter
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root',type=Path,required=True,help='Pristine bounded handoff directory')
parser.add_argument('--out',type=Path,required=True,help='Diagnostic output directory outside the handoff')
args=parser.parse_args()
ROOT=args.root.resolve(); OUT=args.out.resolve(); OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT))
import verify
diffs=[]
counts=Counter()
maxima={}
def compare(expected, actual, path):
    if isinstance(expected,dict):
        if not isinstance(actual,dict) or expected.keys()!=actual.keys():
            diffs.append(dict(path=path,kind='fields'));return
        for k,v in expected.items():compare(v,actual[k],path+'.'+k)
    elif isinstance(expected,list):
        if not isinstance(actual,list) or len(expected)!=len(actual):
            diffs.append(dict(path=path,kind='list'));return
        for i,(a,b) in enumerate(zip(expected,actual)):compare(a,b,f'{path}[{i}]')
    elif isinstance(expected,float):
        counts['float_leaves']+=1
        group=next((k for k in ('direction_','model_volume','height','bev','boundary','column') if k in path),'other')
        delta=abs(expected-actual) if type(actual) in (int,float) else float('inf')
        if delta>maxima.get(group,{}).get('abs_difference',-1):maxima[group]=dict(abs_difference=delta,path=path,saved=expected,recomputed=actual)
        if type(actual) not in (int,float) or not math.isfinite(expected) or not math.isfinite(actual) or not math.isclose(expected,actual,rel_tol=1e-9,abs_tol=1e-10):
            diffs.append(dict(path=path,kind='float',saved=expected,recomputed=actual,abs_difference=abs(expected-actual),rel_difference=abs(expected-actual)/max(abs(expected),1e-300)))
    else:
        counts['other_leaves']+=1
        if type(expected) is not type(actual) or expected!=actual:diffs.append(dict(path=path,kind='value',saved=expected,recomputed=actual))
verify._compare=compare
t=time.time()
with contextlib.redirect_stdout(io.StringIO()) as stream:verify.main()
out=dict(scope='Same official calculations, strict mismatches collected rather than failing fast; no source edits, original verifier did fail',seconds=time.time()-t,official_summary=json.loads(stream.getvalue()),compared=dict(counts),max_absolute_differences=maxima,difference_count=len(diffs),differences=diffs)
(OUT/'full_recompute_differences.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='differences'},indent=2))
print('maximum_float_difference',max((x['abs_difference'] for x in diffs if x['kind']=='float'),default=0))
