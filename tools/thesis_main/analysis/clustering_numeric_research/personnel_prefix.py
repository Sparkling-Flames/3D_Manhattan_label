"""Actual prefix re-clustering within FIXED, target-building-excluded historical subtypes.
Only the existing middle probe is used; broad historical 303 configuration inventory
and fixed-label sensitivity remain in personnel_effects.py.
"""
import json,gzip,csv,io,os,collections
import numpy as np,pandas as pd
from concurrent.futures import ProcessPoolExecutor
from common import *
from prefix_replay import PrefixEngine,STAT_NAMES,writer

def job_run(job):
    number,g,ix,orders=job;ids=[g['ids'][i] for i in ix];ws=[g['workers'][i] for i in ix];wi={w:i for i,w in enumerate(ws)}
    projected=[[wi[w] for w in row if w in wi] for row in orders]
    matrices={m:np.asarray(d)[np.ix_(ix,ix)] for m,d in g['matrices']['automatic'].items()}
    engine=PrefixEngine(matrices,ids,cuts=(9.,));ss,arrivals,events=engine.sample(projected)
    outdir=OUT/'personnel_prefix_parts';outdir.mkdir(exist_ok=True)
    path=outdir/f'{number:04d}.csv.gz';raw,txt,w=writer(path,['pool','method','mask','k','labels','representative_pool_indices',*STAT_NAMES])
    for mask,(stats,labels,reps) in sorted(engine.cache.items()):
        for m,(metric,kind,t) in enumerate(engine.methods):w.writerow([number,f'{metric}:{kind}:{t:g}',mask,mask.bit_count(),labels[m].tobytes().hex(),'|'.join(map(str,reps[m])),*['' if not np.isfinite(v) else f'{v:.12g}' for v in stats[m]]])
    txt.close();raw.close()
    meta=dict(pool=number,unit=g['unit'],key=g['key'],code=g['code'],condition=g['condition'],building=g['building'],N=len(ids),ids=ids,workers=ws)
    print('PERSONNEL PREFIX',number,g['code'],len(ids),len(engine.cache),flush=True)
    return dict(metadata=meta,summary=[dict(pool=number,**s) for s in ss],nodes=len(engine.cache)*4,path=str(path),arrival_steps=len(arrivals),churn_events=len(events))

def main():
    groups=load_groups();rows,raw=rawdata();rr=pd.read_csv(OUT/'personnel/refitted_lobo_rosters.csv');orders=json.loads((OUT/'global_worker_orders.json').read_text())
    if isinstance(orders,dict):orders=orders['orders']
    pools={};jobs=[];aliases=[]
    for key,g in groups.items():
        if g['N']<19:continue
        for (cfg,sub),z in rr[rr.heldout_building==g['building']].groupby(['config','subtype']):
            ws=set(z.worker);ix=tuple(i for i,w in enumerate(g['workers']) if w in ws and not raw[g['ids'][i]].get('imputed_point',False))
            if len(ix)<2:continue
            pk=(key,ix)
            if pk not in pools:pools[pk]=len(jobs);jobs.append((len(jobs),g,ix,orders))
            aliases.append(dict(pool=pools[pk],key=key,code=g['code'],building=g['building'],condition=g['condition'],config=cfg,subtype=sub,N=len(ix),roster_origin='fixed_lobo_roster',target_building_excluded=True,borrowed_removed=True))
    out=OUT/'personnel';out.mkdir(exist_ok=True)
    rawzip,txt,w=writer(out/'subtype_prefix_nodes.csv.gz',['pool','method','mask','k','labels','representative_pool_indices',*STAT_NAMES])
    metas=[];summ=[];nn=steps=events=0
    with ProcessPoolExecutor(max_workers=int(os.environ.get('CLUSTER_JOBS','4'))) as ex:
        for result in ex.map(job_run,jobs,chunksize=1):
            metas.append(result['metadata']);summ+=result['summary'];nn+=result['nodes'];steps+=result['arrival_steps'];events+=result['churn_events']
            path=Path(result['path'])
            with gzip.open(path,'rt',encoding='utf-8') as f:
                next(f)
                for block in iter(lambda:f.read(1024*1024),''):txt.write(block)
            path.unlink()
    txt.close();rawzip.close();(OUT/'personnel_prefix_parts').rmdir()
    ss=save('personnel/subtype_prefix_summary.csv.gz',summ);al=save('personnel/subtype_prefix_roster_aliases.csv',aliases);dump('personnel/subtype_prefix_pools.json',metas)
    # Each line retains its exact fixed subtype pool; small groups not padded to 20.
    merged=ss.merge(al,on='pool',validate='many_to_many')
    checkpoints=merged[merged.k.isin([3,5,8,12,16])].groupby(['condition','config','subtype','metric','partition','k']).agg(images=('key','nunique'),images_with_remaining_person=('remaining_pair_uncovered_mean','count'),min_pool_N=('N','min'),max_pool_N=('N','max'),prefix_K=('clusters_mean','mean'),prefix_singletons=('singletons_mean','mean'),fixed_K=('fixed_clusters_mean','mean'),pair_uncovered=('remaining_pair_uncovered_mean','mean'),largest_share=('largest_share_mean','mean'),old_relation_churn=('mean_old_pair_churn','mean')).reset_index()
    save('personnel/subtype_prefix_checkpoints.csv',checkpoints)
    dump('PERSONNEL_PREFIX_AUDIT.json',dict(unique_fixed_person_pools=len(metas),roster_aliases=len(al),method_prefix_nodes=nn,actual_arrival_steps=steps,churn_or_drop_events=events,global_orders=200,middle_probe_only=True,borrowed_points_removed=True,rosters_not_fitted_to_target=True,online_future_prediction=False,source_of_all_arrival_orders='global_worker_orders.json projected onto each pool workers; no additional randomization'))
if __name__=='__main__':main()
