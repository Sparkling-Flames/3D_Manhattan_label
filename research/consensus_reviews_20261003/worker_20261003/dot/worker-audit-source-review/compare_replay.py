"""Compare immutable upstream B-line artifacts with a fresh full-panel replay."""
from pathlib import Path
import csv, hashlib, json, sys
import numpy as np

ROOT=Path(__file__).resolve().parent.parent
original=ROOT/'worker-audit-original/analysis_results/worker_profiles_20261003'
replay=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'worker-audit-source-review/replay-original-stack'
out=Path(sys.argv[2]) if len(sys.argv)>2 else ROOT/'worker-audit-source-review/replay-comparison.json'
result={'original':str(original),'replay':str(replay),'csv':[],'arrays':[],'json':[]}
for p in sorted(original.glob('*.csv')):
    q=replay/p.name
    a=list(csv.DictReader(p.open(encoding='utf-8-sig',newline='')))
    b=list(csv.DictReader(q.open(encoding='utf-8-sig',newline='')))
    textdiff=[]; numeric=[]
    for i,(x,y) in enumerate(zip(a,b)):
        for key in x:
            if x[key]==y.get(key):continue
            try:
                xx,yy=float(x[key]),float(y[key])
                numeric.append({'row':i,'field':key,'original':xx,'replay':yy,'abs_delta':abs(xx-yy)})
            except (TypeError,ValueError):textdiff.append({'row':i,'field':key,'original':x[key],'replay':y.get(key)})
    result['csv'].append(dict(file=p.name,original_rows=len(a),replay_rows=len(b),columns_equal=list(a[0])==list(b[0]),byte_equal=p.read_bytes()==q.read_bytes(),nonnumeric_differences=textdiff,numeric_difference_count=len(numeric),max_abs_delta=max([x['abs_delta'] for x in numeric],default=0),largest_differences=sorted(numeric,key=lambda x:-x['abs_delta'])[:3]))
a=np.load(original/'subsets.npz');b=np.load(replay/'subsets.npz')
result['npz_keys_equal']=a.files==b.files
for key in a.files:
    x,y=a[key],b[key]
    result['arrays'].append(dict(key=key,shape=list(x.shape),dtype=str(x.dtype),all_finite=bool(np.isfinite(y).all()),exact=bool(np.array_equal(x,y)),max_abs_delta=float(np.max(np.abs(x.astype(float)-y.astype(float)))),different_elements=int(np.count_nonzero(x!=y))))
for p in sorted(original.glob('*.json')):
    q=replay/p.name
    if q.exists():result['json'].append(dict(file=p.name,byte_equal=p.read_bytes()==q.read_bytes(),parsed_equal=json.loads(p.read_text())==json.loads(q.read_text())))
result['summary']=dict(csv_files=len(result['csv']),csv_byte_equal=sum(x['byte_equal'] for x in result['csv']),csv_nonnumeric_differences=sum(len(x['nonnumeric_differences']) for x in result['csv']),csv_max_abs_delta=max(x['max_abs_delta'] for x in result['csv']),npz_arrays=len(result['arrays']),npz_exact=sum(x['exact'] for x in result['arrays']),npz_max_abs_delta=max(x['max_abs_delta'] for x in result['arrays']))
out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps(result['summary'],indent=2))
