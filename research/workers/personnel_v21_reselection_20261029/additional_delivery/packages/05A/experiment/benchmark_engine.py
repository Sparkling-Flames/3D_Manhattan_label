"""Small real-v2.1 engine parity and throughput run; retain all generated endpoints."""
import argparse,gzip,hashlib,importlib.util,json,os,sys,time,math
from pathlib import Path
for x in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[x]='1'
import numpy as np

def read(path):
    with (gzip.open(path,'rt',encoding='utf-8-sig') if str(path).endswith('.gz') else open(path,encoding='utf-8-sig')) as f:return json.load(f)

def load_engine(repo):
    os.environ['HOHONET_REPO']=str(repo)
    path=repo/'research/same_room/same_room_current_classes_v2_20261023/code/engine/new_team_engine.py'
    spec=importlib.util.spec_from_file_location('v21_research_native',path);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m

def evaluated(engine,native,pool,workers):
    row=engine.evaluate(pool,workers);g=row.get('geometry')
    if g is not None:
        z=engine.scorecache.get(engine.fr.digest([row['k']==2,row.get('nodes'),g]))
        if z:row.update(z)
    row.update(data_release='v2.1',underlying_data_version='v2.1',endpoint_origin='v21_reselection_engine_benchmark',input_pool_sha256=native.gs.digest(pool))
    return native.gs.clean(row)

def numeric_geometry_difference(a,b):
    if isinstance(a,dict):
        assert set(a)==set(b)
        return max((numeric_geometry_difference(a[k],b[k]) for k in a),default=0.)
    if isinstance(a,list):
        assert len(a)==len(b)
        return max((numeric_geometry_difference(x,y) for x,y in zip(a,b)),default=0.)
    if isinstance(a,(float,int)) and not isinstance(a,bool):return abs(a-b)
    assert a==b,(a,b)
    return 0.

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    repo=Path(a.repo);out=Path(a.output);out.mkdir(parents=True,exist_ok=True);release=repo/'research/data/releases/v2.1'
    pools={p['pool_id']:p for n in ['pools/INPUT_SNAPSHOT.json','admitted_space_extension/pools/INPUT_SNAPSHOT.json'] for p in read(release/n)['images']}
    native=load_engine(repo);allrows=[];parity=[];timings=[]
    sources=sorted((out.parent/'benchmark_sources').glob('benchmark_*.jsonl.gz'))
    for source in sources:
        with gzip.open(source,'rt') as f:old=[json.loads(l) for l in f]
        pool=pools[old[0]['pool_id']];own=[r for r in old if r['k']>=3][:3]
        # First source includes a complete failure by file order; no score-based case choice.
        with native.Engine(full_state=False) as eng:
            for oldrow in own:
                row=evaluated(eng,native,pool,oldrow['member_workers']);allrows.append(row)
                fields=['B8L2','D10','IoU3D100','iou_2d','nodes','minimum_support','S_bottom_deg','dir','Hmean','Hcenter','omission','extension']
                diffs={}
                for field in fields:
                    x,y=oldrow.get(field),row.get(field)
                    if x is None or y is None:
                        assert x is None and y is None,(pool['pool_id'],field,x,y)
                    else:
                        diffs[field]=abs(float(x)-float(y));assert diffs[field]<1e-8,(pool['pool_id'],field,x,y)
                gd=numeric_geometry_difference(oldrow['geometry'],row['geometry'])
                assert gd<1e-10 and oldrow['score_status']==row['score_status']
                parity.append(dict(pool_id=pool['pool_id'],team_key=row['team_key'],source_file=source.name,geometry_exact_equal=oldrow['geometry']==row['geometry'],geometry_maximum_difference=gd,score_status=row['score_status'],maximum_numeric_difference=max(diffs.values(),default=0),fields=diffs))
            workers=sorted(r['worker_id'] for r in pool['records']);rng=np.random.default_rng(2026102907)
            nset=sorted({3,min(8,len(workers)),min(16,len(workers)),min(24,len(workers))})
            req=[]
            for n in nset:
                for j in range(8):req.append(sorted(rng.choice(workers,n,replace=False).tolist()))
            req=list({tuple(r):r for r in req}.values())
            t=time.monotonic()
            for ws in req:allrows.append(evaluated(eng,native,pool,ws))
            sec=time.monotonic()-t
            timings.append(dict(pool_id=pool['pool_id'],condition=pool['meta']['condition'],difficulty=pool['meta']['difficulty'],pool_n=len(workers),teams=len(req),n_values=nset,seconds=sec,teams_per_second=len(req)/sec))
            print(json.dumps(timings[-1]),flush=True)
    with gzip.open(out/'BENCHMARK_ENDPOINTS.jsonl.gz','wt',encoding='utf-8') as f:
        for row in allrows:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
    report=dict(commit='a476461d7ede8db95da43de4139e612c05e618bc',data_release='v2.1',parity=parity,timings=timings,parity_passed=True,benchmark_rows=len(allrows),generated_endpoints_saved=True)
    (out/'BENCHMARK_AND_PARITY.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(dict(parity_teams=len(parity),generated_rows=len(allrows),seconds=sum(x['seconds'] for x in timings)),ensure_ascii=False))

if __name__=='__main__':main()
