"""Check the specific old 4+20 random-number construction against saved orders.

This is a small design-level check needed for conditional Monte Carlo
aggregation; it does not recompute any fusion endpoint or re-audit outcomes.
"""
from pathlib import Path
import argparse,gzip,hashlib,json
import numpy as np
import pandas as pd


def run(repo,out):
    root=repo/'research/workers/personnel_population_curves_v2_20261023'
    with gzip.open(root/'inputs/INPUT_SNAPSHOT.json.gz','rt') as f:pools={p['pool_id']:p for p in json.load(f)['images']}
    orders=pd.read_csv(root/'design/EXACT_ORDER_DESIGN.csv.gz',keep_default_na=False,dtype={'seed':str})
    orders=orders[(orders.policy=='natural_random')&(orders.sample_kind=='MC')]
    records=[]
    for r in orders.to_dict('records'):
        p=pools[r['pool_id']];workers=sorted(x['worker_id'] for x in p['records']);rep=int(r['replicate'])
        if rep<4:
            payload=json.dumps([2026101901,'uniform_order',r['pool_id'],rep],sort_keys=True,ensure_ascii=False,separators=(',',':'))
            seed=int(hashlib.sha256(payload.encode()).hexdigest()[:16],16);batch='old4'
        else:
            payload=json.dumps(['v2-full-pool-prefix',20261023,r['condition'],r['image'],rep],ensure_ascii=True,separators=(',',':'))
            seed=int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8],'little');batch='added20'
        generated=np.random.default_rng(seed).permutation(workers).tolist()
        ok=generated==r['worker_order'].split('|');assert ok,r['path_id']
        records.append(dict(pool_id=r['pool_id'],image=r['image'],condition=r['condition'],layer=r['layer'],
            path_id=r['path_id'],replicate=rep,generation_batch=batch,derived_u64_seed=str(seed),
            exact_saved_order_match=ok,seed_contains_pool_identity=True))
    d=pd.DataFrame(records);out.mkdir(parents=True,exist_ok=True)
    d.to_csv(out/'OLD_4_PLUS_20_SEED_CHECK.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    identity=pd.DataFrame([dict(pool_id=p['pool_id'],image=p['meta']['image'],condition=p['meta']['condition']) for p in pools.values()])
    collision=d.derived_u64_seed.duplicated().sum();duplicate_pool_identity=identity.duplicated(['image','condition']).sum()
    assert not collision and not duplicate_pool_identity
    files=['research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/register_design.py',
           'research/workers/personnel_population_curves_v2_20261023/code/register_population_orders.py',
           'research/workers/personnel_population_curves_v2_20261023/code/order_policies.py']
    receipt=dict(checked_MC_paths=len(d),MC_pools=d.pool_id.nunique(),
        by_generation=d.groupby('generation_batch').size().to_dict(),all_saved_orders_reproduced=True,
        derived_seed_collisions=int(collision),duplicated_condition_image_pool_identities=int(duplicate_pool_identity),
        old4_key='[2026101901, uniform_order, pool_id, draw_id], canonical JSON SHA256 first16 hex as integer',
        added20_key='[v2-full-pool-prefix, 20261023, condition, image, replicate], SHA256 first8 bytes little-endian',
        interpretation='Pools do not share a deliberately reused random-order seed/base. Chance identical permutations remain legal, especially in small spaces; no such outcome is removed.',
        exact_small_pool_note='N<=4 exact permutation catalogues are excluded from this MC 4+20 check; they are not independent random draws.',
        source_hashes={f:hashlib.sha256((repo/f).read_bytes()).hexdigest() for f in files})
    (out/'OLD_ORDER_SEED_CHECK.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps(receipt,ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();run(a.repo,a.out)
