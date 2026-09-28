"""Compare completed runs, including cross-platform floating-point JSON output.
Use the received and recomputed result directories as the two positional arguments.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd

def digest(path:Path,decoded=False):
    h=hashlib.sha256()
    with (gzip.open(path,'rb') if decoded and path.suffix=='.gz' else path.open('rb')) as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def check_manifest(path:Path):
    doc=json.loads(path.read_text(encoding='utf-8'));bad=[]
    for filename,expected in doc.get('files',{}).items():
        f=path.parent/filename
        if not f.is_file() or digest(f)!=expected:bad.append(filename)
    return bad

def json_equivalent(a,b):
    """Only float values may round; identities, integer labels and structure are exact."""
    if type(a) is not type(b):return False,0.
    if isinstance(a,dict):
        if a.keys()!=b.keys():return False,0.
        children=[json_equivalent(a[k],b[k]) for k in a]
    elif isinstance(a,list):
        if len(a)!=len(b):return False,0.
        children=[json_equivalent(x,y) for x,y in zip(a,b)]
    elif isinstance(a,float):return bool(np.isclose(a,b,atol=1e-12,rtol=1e-12)),abs(a-b)
    else:return a==b,0.
    return all(x[0] for x in children),max((x[1] for x in children),default=0.)

def compare(a:Path,b:Path,output:Path):
    select=lambda f:f.is_file() and f.suffix in ('.csv','.json','.gz') and f.name!='RUN_EXECUTION.json'
    fa={p.relative_to(a).as_posix():p for p in a.rglob('*') if select(p)}
    fb={p.relative_to(b).as_posix():p for p in b.rglob('*') if select(p)}
    rows=[];manifests={}
    for name in sorted(fa.keys()|fb.keys()):
        x=fa.get(name);y=fb.get(name)
        row=dict(path=name,status='',maximum_absolute_difference=None,reference_payload_sha256=None,rerun_payload_sha256=None)
        if x is None or y is None:row['status']='missing';rows.append(row);continue
        hx=digest(x,True);hy=digest(y,True);row.update(reference_payload_sha256=hx,rerun_payload_sha256=hy)
        if hx==hy and name!='source_replay/EXPERIMENT_MANIFEST.json':row['status']='payload_identical'
        elif name.endswith('.csv') or name.endswith('.csv.gz'):
            da=pd.read_csv(x);db=pd.read_csv(y);ok=da.shape==db.shape and da.columns.tolist()==db.columns.tolist();maximum=0.
            if ok:
                for c in da:
                    if pd.api.types.is_numeric_dtype(da[c]) and pd.api.types.is_numeric_dtype(db[c]):
                        va=da[c].to_numpy(dtype=float);vb=db[c].to_numpy(dtype=float)
                        if not np.allclose(va,vb,atol=1e-12,rtol=1e-12,equal_nan=True):ok=False
                        finite=np.isfinite(va)&np.isfinite(vb)
                        if finite.any():maximum=max(maximum,float(np.max(np.abs(va[finite]-vb[finite]))))
                    elif not da[c].fillna('__MISSING__').equals(db[c].fillna('__MISSING__')):ok=False
            row.update(status='floating_point_equivalent' if ok else 'mismatch',maximum_absolute_difference=maximum)
        elif name=='source_replay/EXPERIMENT_MANIFEST.json':
            ja=json.loads(x.read_text());jb=json.loads(y.read_text());ha=ja.pop('files',{});hb=jb.pop('files',{})
            ok=ja==jb and ha.keys()==hb.keys() and not check_manifest(x) and not check_manifest(y)
            manifests[name]=[(Path(name).parent/key).as_posix() for key in ha]
            row['status']='pending_verified_payloads' if ok else 'mismatch'
        elif name.endswith('.json'):
            ok,maximum=json_equivalent(json.loads(x.read_text(encoding='utf8')),json.loads(y.read_text(encoding='utf8')))
            row.update(status='json_numeric_equivalent' if ok else 'mismatch',maximum_absolute_difference=maximum)
        else:row['status']='mismatch'
        rows.append(row)
    acceptable={'payload_identical','floating_point_equivalent','json_numeric_equivalent','manifest_and_payloads_verified'}
    byname={r['path']:r for r in rows}
    for name,refs in manifests.items():
        row=byname[name]
        if row['status']=='pending_verified_payloads':
            row['status']='manifest_and_payloads_verified' if all(byname.get(ref,{}).get('status') in acceptable for ref in refs) else 'mismatch'
    statuses=pd.Series([r['status'] for r in rows]).value_counts().to_dict()
    ok=all(r['status'] in acceptable for r in rows)
    output.mkdir(parents=True,exist_ok=True)
    with (output/'reproduction_comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    result=dict(passed=ok,reference_numerical_files=len(fa),rerun_numerical_files=len(fb),status_counts=statuses,
        absolute_tolerance=1e-12,relative_tolerance=1e-12,
        maximum_csv_difference=max((r['maximum_absolute_difference'] or 0 for r in rows if r['path'].endswith(('.csv','.csv.gz'))),default=0),
        maximum_json_difference=max((r['maximum_absolute_difference'] or 0 for r in rows if r['path'].endswith('.json')),default=0),
        interpretation='All files accounted for; float values tolerate rounding, identities and JSON integer labels are exact; each manifest binds its own verified payloads.',
        logs_and_RUN_EXECUTION_are_execution_metadata_not_numerical_results=True)
    (output/'ISOLATED_REPRODUCTION.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return ok
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('reference',type=Path);p.add_argument('rerun',type=Path);p.add_argument('--output',type=Path,default=Path('reproduction_check'));a=p.parse_args()
    raise SystemExit(0 if compare(a.reference,a.rerun,a.output) else 1)
