"""Reproduce the bounded warmed-cache timing study used for execution budget."""
from pathlib import Path
import argparse,resource,statistics,time
import execute_extension as e

def run(base):
    native=e.init_native(base);pools=native.gs.pool_lookup()
    prior=base/'prior_recovered/research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025/engine/benchmark'
    ids={r['pool_id'] for r in e.readcsv(prior/'REQUESTS.csv.gz')};by={p:[] for p in ids}
    for r in e.readcsv(base/'inputs_cache26/ENDPOINT_SCALARS_20261023.csv.gz'):
        pid=r['pool_id']
        if pid in by and 3<=int(float(r['k']))<=len(pools[pid]['records'])-2:by[pid].append(r)
    rows=[];summary=[];t=time.monotonic()
    with native.FrozenNativeEngine(full_state=False) as engine:
        for pid,old in sorted(by.items()):
            engine.reset_pool();old=sorted(old,key=lambda r:r['team_key'])[:160];tt=time.monotonic()
            for i,x in enumerate(old):
                r=engine.evaluate(pools[pid],x['member_workers'].split('|'))
                rows.append(dict(pool_id=pid,team_key=r['team_key'],k=r['k'],sequence=i,
                    native_seconds=r['native_evaluation_wall_seconds'],fusion_seconds=r['fusion_seconds'],
                    score_seconds=r.get('score_seconds'),warmup=i<32))
            warm=[r['native_seconds'] for r in rows if r['pool_id']==pid and not r['warmup']]
            summary.append(dict(pool_id=pid,teams=len(old),pool_seconds=time.monotonic()-tt,first32_warmup=True,
                warm_mean_seconds=statistics.mean(warm),warm_median_seconds=statistics.median(warm),
                max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
    out=base/'engine26/benchmark26';e.save_csv(out/'WARM_CACHE_TIMINGS.csv.gz',rows)
    result=dict(pools=summary,seconds=time.monotonic()-t,
        selection='For the four inherited timing pools, first160 canonical keys at k3..N-2; first32 treated as pair cache warmup. Selection never reads Q. Cached endpoints recomputed for timing only.')
    e.savejson(out/'WARM_CACHE_RECEIPT.json',result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);a=p.parse_args();print(run(a.base.resolve()))
