"""Read-only adapters for the pinned 2026-09-21 handoff, plus explicit estimands."""
from pathlib import Path
import sys, json, gzip, hashlib, math, itertools, collections, os
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(os.environ.get('PANORAMA_SOURCE', str(ROOT/'source_work')))
SEED=20260921
CUT=25.6

def configure(source):
    global SOURCE
    SOURCE=Path(source).resolve()
    sys.path.insert(0,str(SOURCE))

def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
    if isinstance(x,(np.bool_,)):return bool(x)
    if isinstance(x,(np.integer,)):return int(x)
    if isinstance(x,(np.floating,float)):return float(x) if np.isfinite(x) else None
    return x

def save(name,data):
    p=ROOT/'results'/name;p.parent.mkdir(parents=True,exist_ok=True)
    if isinstance(data,pd.DataFrame):data.to_csv(p,index=False)
    else:p.write_text(json.dumps(clean(data),ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def read(path):return json.loads((SOURCE/path).read_text(encoding='utf-8-sig'))

def load():
    from tools.thesis_main.analysis import reviewed_manual_20260921 as rm
    from tools.thesis_main.analysis.paired_split_research import study
    path=SOURCE/'analysis_results/new_manual_reviewed_20260921/responses.jsonl.gz'
    rows=[json.loads(s) for s in gzip.open(path,'rt',encoding='utf8')]
    registry=read(rm.REGISTRY)
    meta={r['image_id']:r for r in registry['images']}
    audit=pd.DataFrame([{'id':r['canonical_annotation_id'],'code':f"{meta[r['image_id']]['building']}-{meta[r['image_id']]['number']:02d}"} for r in rows]).set_index('id')
    approved=study.accepted_map(rm.old.HIST,rows)
    for r in rows:
        if r.get('pairing_review'):approved[r['canonical_annotation_id']]=np.array(r['pairing_review']['pairs_1based'])-1
    records,eligibility=study.prepare(rows,audit,approved,'min_horizontal')
    selected=[r for r in rows if r['calculation_included'] and r['worker_id'] not in ['W019','W026'] and r['raw_condition'] in ['manual','oos']]
    bound=[r for r in selected if r['canonical_annotation_id'] in records and records[r['canonical_annotation_id']]['links'] is not None]
    prediction=[r for r in bound if not r['imputed_point']]
    assert len(selected)==2481 and len(bound)==2448 and len(prediction)==2444
    views={}
    for r in prediction:views.setdefault(r['image_id'],[]).append(r)
    for iid,rr in views.items():
        rr.sort(key=lambda r:r['canonical_annotation_id'])
        workers=[r['worker_id'] for r in rr];assert len(workers)==len(set(workers)),(iid,workers)
        n=len(rr);d=np.zeros((n,n));dd={}
        for a,b in itertools.combinations(range(n),2):
            ra,rb=[records[rr[j]['canonical_annotation_id']] for j in [a,b]]
            if len(ra['links'])!=len(rb['links']):v=1e6
            else:
                p,q=ra['p'][ra['links']],rb['p'][rb['links']]
                dx=abs((p[:,:,0]-q[:,:,0]+512)%1024-512);dy=abs(p[:,:,1]-q[:,:,1])
                v=np.hypot(dx,dy).max()
            d[a,b]=d[b,a]=v
        views[iid]=dict(image_id=iid,code=audit.loc[rr[0]['canonical_annotation_id'],'code'],building=rr[0]['building_id'],
            ids=[r['canonical_annotation_id'] for r in rr],workers=workers,rows=rr,d=d,N=n)
    assert len(views)==240
    return rows,records,views,registry,eligibility

def part(d,ids,kind='complete',cut=CUT):
    from tools.thesis_main.analysis.clustering_release.local_points import partition
    return partition(d,ids,cut,kind)

def next_uncovered(d,k,cut=CUT):
    n=len(d)
    if k<0 or k>=n:return np.nan
    degree=(np.round(d,8)<=cut).sum(1)-1
    den=math.comb(n-1,k)
    return np.mean([math.comb(n-1-int(z),k)/den if k<=n-1-z else 0. for z in degree])

def building_summary(df,value,replicates=5000,room=None):
    """Conditional resampling of fixed building summaries; NOT independent response pairs."""
    if not len(df):return {}
    if room and room in df:
        means=df.groupby(['building',room])[value].mean().groupby('building').mean()
    else:means=df.groupby('building')[value].mean()
    rng=np.random.default_rng(SEED)
    boot=rng.choice(means.to_numpy(),(replicates,len(means)),replace=True).mean(1)
    return dict(n_rows=len(df),buildings=len(means),mean=means.mean(),interval95=np.quantile(boot,[.025,.975]),per_building=means.to_dict())

def main_parser():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--source-root',default=str(SOURCE));return p
