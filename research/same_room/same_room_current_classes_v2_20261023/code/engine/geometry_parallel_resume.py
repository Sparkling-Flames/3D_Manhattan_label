"""Resume remaining pair summaries after native CPU slots become available."""
from __future__ import annotations
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[k]='1'
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
import time
import pandas as pd
from summarize_geometry_transfer import PoolCache,prepare,panel_compute,aggregate,gs,save

_CACHE=None


def work(payload):
    global _CACHE
    pair,metas,links,native,out=payload
    if _CACHE is None:_CACHE=PoolCache(Path(native)/'pools',4)
    ra=_CACHE.get(metas[0]['pool_id_a']);rb=_CACHE.get(metas[0]['pool_id_b'])
    assert ra is not None and rb is not None
    need_a={x['team_key_a'] for m in metas for x in links[m['panel_id']]}
    need_b={x['team_key_b'] for m in metas for x in links[m['panel_id']]}
    assert need_a<=ra.keys() and need_b<=rb.keys()
    pa={k:prepare(ra[k]) for k in need_a};pb={k:prepare(rb[k]) for k in need_b}
    path=Path(out)/'checkpoints'/(gs.digest(pair)[:20]+'.json.gz')
    prior=gs.read(path)['panels'] if path.exists() else []
    old={x['panel_id'] for x in prior}
    started=time.monotonic();new=[]
    for m in metas:
        if m['panel_id'] in old:continue
        new.append(panel_compute(m,links[m['panel_id']],ra,rb,pa,pb))
    save(path,dict(pair_key=pair,panels=prior+new))
    return dict(pair=pair,new_panels=len(new),attempted=sum(x['attempted'] for x in new),elapsed_seconds=time.monotonic()-started)


def main():
    p=argparse.ArgumentParser();p.add_argument('--design',required=True);p.add_argument('--native',required=True);p.add_argument('--output',required=True);p.add_argument('--jobs',type=int,default=4);p.add_argument('--watch',action='store_true');a=p.parse_args()
    design,native,out=map(Path,[a.design,a.native,a.output]);out.mkdir(exist_ok=True);(out/'checkpoints').mkdir(exist_ok=True)
    panels=pd.read_csv(design/'PANELS.csv',keep_default_na=False)
    links=pd.read_csv(design/'PANEL_TEAM_LINKS.csv.gz',keep_default_na=False)
    lm={k:g.to_dict('records') for k,g in links.groupby('panel_id',sort=False)}
    start=time.monotonic();new_attempted=0
    with ProcessPoolExecutor(max_workers=a.jobs) as ex:
        while True:
            done,receipt=aggregate(out,len(panels))
            if len(done)==len(panels):break
            completed={x['pool_id'] for x in gs.read(native/'PROGRESS.json')['pools']}
            todo=[]
            for pair,g in panels.groupby('pair_key',sort=True):
                rr=[r for r in g.to_dict('records') if r['panel_id'] not in done]
                if not rr or not {rr[0]['pool_id_a'],rr[0]['pool_id_b']}<=completed:continue
                todo.append((pair,rr,{r['panel_id']:lm[r['panel_id']] for r in rr},str(native),str(out)))
            fs=[ex.submit(work,payload) for payload in todo]
            for i,f in enumerate(as_completed(fs),1):
                r=f.result();new_attempted+=r['attempted'];print(json.dumps(r),flush=True)
                if i%10==0:aggregate(out,len(panels))
            done,receipt=aggregate(out,len(panels));print(json.dumps(receipt),flush=True)
            if len(done)==len(panels) or not a.watch:break
            if not todo:time.sleep(10)
    save(out/'PARALLEL_RESUME_EXECUTION.json',dict(wall_seconds=time.monotonic()-start,jobs=a.jobs,new_attempted=new_attempted,**receipt))


if __name__=='__main__':main()
