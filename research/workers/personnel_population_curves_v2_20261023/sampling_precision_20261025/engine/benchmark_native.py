"""Small timed run with frozen-v2 native methods and saved-endpoint checks.

The pool choice is deterministic within difficulty and independent of Q.
These are timing requests, not an extra random-path study population.
"""
from pathlib import Path
import argparse, gzip, hashlib, json, sys, time
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import native_population_runner as nr


def run(repo=None):
    repo=HERE.parent/'repo' if repo is None else repo
    population = repo / 'research/workers/personnel_population_curves_v2_20261023'
    pools = {p['pool_id']: p for p in nr.read_json(population/'inputs/INPUT_SNAPSHOT.json.gz')['images']}
    # Independently fixed hash selects one representative pool per primary layer.
    chosen = []
    for layer, difficulty in [('ordinary_manual','简单'), ('ordinary_manual','中等'),
                              ('ordinary_manual','困难'), ('doorway_manual','单列')]:
        ps = [p for p in pools.values() if p['meta']['layer']==layer and
              p['meta']['difficulty']==difficulty and len(p['records'])>=30]
        chosen.append(min(ps, key=lambda p: hashlib.sha256(('precision-native-timing|'+p['pool_id']).encode()).hexdigest()))
    selected = {p['pool_id'] for p in chosen}
    expected = []
    cols = ['team_key','pool_id','member_workers','k','B8L2','D10','nodes','score_status']
    for chunk in pd.read_csv(population/'results/ENDPOINT_SCALARS.csv.gz',usecols=cols,chunksize=50000):
        expected += chunk[chunk.pool_id.isin(selected)].to_dict('records')
    ex = pd.DataFrame(expected)
    requests, check = [], []
    for p in chosen:
        pid=p['pool_id']; ws=sorted(r['worker_id'] for r in p['records']); N=len(ws)
        candidates=ex[(ex.pool_id==pid)&(ex.k==min(10,N))].sort_values('team_key')
        old=candidates.iloc[0].to_dict(); check.append(old)
        requests.append(dict(pool_id=pid,team_key=old['team_key'],member_workers=old['member_workers'],n=int(old['k']),purpose='saved_endpoint_compatibility'))
        seed=int.from_bytes(hashlib.sha256(('precision-native-timing-order|'+pid).encode()).digest()[:8],'little')
        order=np.random.default_rng(seed).permutation(ws).tolist()
        for k in sorted({1,2,3,5,10,20,N-1,N}):
            own=sorted(order[:k]);key=nr.gs.team_key(pid,own)
            if key not in {r['team_key'] for r in requests}:
                requests.append(dict(pool_id=pid,team_key=key,member_workers='|'.join(own),n=k,purpose='runtime',seed=str(seed)))
    out=HERE/'benchmark'
    nr.save_csv(out/'REQUESTS.csv.gz',requests)
    nr.save_csv(out/'EXPECTED_OLD_ENDPOINTS.csv.gz',check)
    ps,by=nr.prepare_requests(out/'REQUESTS.csv.gz')
    done=[];start=time.monotonic()
    for pid,rs in by.items():
        r=nr.compute_pool((ps[pid],rs,str(out),20,True));done.append(r)
        print(json.dumps(r),flush=True)
    nr.consolidate(out,ps,by)
    got=pd.read_csv(out/'ENDPOINT_SCALARS.csv.gz')
    comparisons=[]
    for r in check:
        actual=got[got.team_key==r['team_key']].iloc[0]
        z={'team_key':r['team_key'],'pool_id':r['pool_id']}
        for key in ['B8L2','D10','nodes']:
            a,b=r[key],actual[key]
            z[key+'_old']=a;z[key+'_new']=b
            z[key+'_same']=bool(pd.isna(a) and pd.isna(b) or np.isclose(a,b,atol=1e-7,rtol=1e-10))
            assert z[key+'_same'],z
        comparisons.append(z)
    nr.save_csv(out/'COMPATIBILITY_COMPARISONS.csv.gz',comparisons)
    n=got.native_evaluation_wall_seconds
    receipt=dict(endpoints=len(got),pools=len(chosen),saved_comparisons=len(check),
        elapsed_seconds=time.monotonic()-start,native_seconds=float(n.sum()),
        native_mean_seconds=float(n.mean()),native_median_seconds=float(n.median()),native_p90_seconds=float(n.quantile(.9)),
        all_saved_B8L2_D10_nodes_agree=True,full_state_retained=True,
        note='A small deterministic timing sample; not an estimator sample for population curves.')
    nr.save_json(out/'BENCHMARK_RECEIPT.json',receipt)
    print(json.dumps(receipt),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path)
    a=p.parse_args();run(a.repo)
