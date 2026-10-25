"""Read the fixed population-study inputs and record actual usable support.

No fusion, scoring, classification or endpoint selection is performed here.
Usage: python inspect_existing_population.py --repo ../repo --out .
"""
from __future__ import annotations
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd


def file_sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    b = repo / 'research/workers/personnel_population_curves_v2_20261023'
    commit = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD']).decode().strip()
    p = pd.read_csv(b / 'design/ACTUAL_POOLS.csv')
    orders = pd.read_csv(b / 'design/EXACT_ORDER_DESIGN.csv.gz', low_memory=False, dtype={'seed':str})
    natural = orders[orders.policy.eq('natural_random')].copy()
    compact = pd.read_csv(b / 'stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz', low_memory=False)
    links = pd.read_csv(b / 'results/PREFIX_TEAM_LINKS.csv.gz', low_memory=False)
    ann = pd.read_csv(b / 'inputs/IMAGE_DIFFICULTY_OPPORTUNITIES.csv', low_memory=False)
    assert not p.pool_id.duplicated().any()
    assert not orders.path_id.duplicated().any()
    assert not links.duplicated(['path_id','k']).any()
    assert len(compact) == len(links)
    assert compact[['path_id','k','team_key']].equals(links[['path_id','k','team_key']])
    assert set(links.path_id) == set(orders.path_id)
    assert links.groupby('path_id').size().sort_index().equals(orders.set_index('path_id').pool_n.sort_index())
    natural_counts = natural.groupby('pool_id').size()
    p['natural_paths'] = p.pool_id.map(natural_counts)
    p['natural_sample_kind'] = p.pool_id.map(natural.groupby('pool_id').sample_kind.first())
    p['uniform_new_paths_20261023'] = p.pool_id.map(natural[natural.generation.eq('new_uniform_path')].groupby('pool_id').size()).fillna(0).astype(int)
    p['uniform_retained_paths_20261019'] = p.pool_id.map(natural[natural.generation.eq('reused_existing_uniform_path')].groupby('pool_id').size()).fillna(0).astype(int)
    p.to_csv(out / 'EXISTING_POOL_SUPPORT.csv', index=False)
    cohorts=[]
    cohort_images=[]
    for layer in p.layer.unique():
        base=p[p.layer.eq(layer)]
        limits=[0,20,30,35] if layer=='ordinary_manual' else [0,20,30]
        for lower in limits:
            d=base[base.pool_n.ge(lower)]
            if d.empty: continue
            cohort=f'{layer}__N_ge_{lower}'
            for difficulty in ['ALL', *sorted(d.difficulty.dropna().unique())]:
                q=d if difficulty=='ALL' else d[d.difficulty.eq(difficulty)]
                cohorts.append(dict(cohort=cohort, layer=layer, minimum_pool_n=lower,
                    difficulty=difficulty, images=q.image.nunique(), pools=q.pool_id.nunique(),
                    buildings=q.building.nunique(), actual_n_min=q.pool_n.min(), actual_n_max=q.pool_n.max(),
                    natural_paths=q.natural_paths.sum()))
            for r in d.to_dict('records'):
                cohort_images.append(dict(cohort=cohort, **{c:r[c] for c in ['pool_id','image','image_id','building','condition','difficulty','layer','pool_n','natural_paths','reference_id','reference_version']}))
    pd.DataFrame(cohorts).to_csv(out/'EXISTING_COHORT_COUNTS.csv',index=False)
    pd.DataFrame(cohort_images).to_csv(out/'EXISTING_COHORT_IMAGES.csv',index=False)
    policy_summary=orders.groupby(['layer','condition','policy']).agg(pools=('pool_id','nunique'),images=('image','nunique'),buildings=('building','nunique'),paths=('path_id','size'),prefixes=('pool_n','sum')).reset_index()
    policy_summary.to_csv(out/'EXISTING_POLICY_COVERAGE.csv',index=False)
    sys.path.insert(0,str(b/'code'))
    from order_policies import stable_seed
    checked_new=0
    for r in natural[natural.generation.eq('new_uniform_path')].to_dict('records'):
        s=stable_seed('v2-full-pool-prefix',int(r['master_seed']),r['condition'],r['image'],int(r['replicate']))
        assert str(s)==r['seed']
        ws=sorted(r['worker_order'].split('|'))
        actual=np.random.default_rng(s).permutation(ws).tolist()
        assert '|'.join(actual)==r['worker_order']
        checked_new+=1
    initial=json.load(gzip.open(b/'inputs/REQUESTS_INITIAL.json.gz','rt'))
    old={r['path_id']:r for r in initial['paths']}
    checked_old=0
    for r in natural[natural.generation.eq('reused_existing_uniform_path')].to_dict('records'):
        assert '|'.join(old[r['path_id']]['worker_order'])==r['worker_order']
        checked_old+=1
    small=[]
    for pid,g in natural[natural.sample_kind.eq('exact_permutation')].groupby('pool_id'):
        import math
        size=int(g.pool_n.iloc[0])
        assert len(g)==math.factorial(size)==g.worker_order.nunique()
        small.append(dict(pool_id=pid,pool_n=size,paths=len(g),condition=g.condition.iloc[0]))
    pd.DataFrame(small).to_csv(out/'EXACT_SMALL_POOLS.csv',index=False)
    scalar_keys=set(); status=collections.Counter(); scalar_count=0
    for d in pd.read_csv(b/'results/ENDPOINT_SCALARS.csv.gz', usecols=['team_key','pool_id','score_available','score_failure_nonpolicy','policy_deferred'], chunksize=25000):
        for r in d.itertuples(index=False):
            assert r.team_key not in scalar_keys
            scalar_keys.add(r.team_key)
            status[(bool(r.score_available),bool(r.score_failure_nonpolicy),bool(r.policy_deferred))]+=1
        scalar_count += len(d)
    assert set(links.team_key)==scalar_keys
    statuses=[dict(score_available=k[0],score_failure_nonpolicy=k[1],policy_deferred=k[2],endpoints=v) for k,v in status.items()]
    pd.DataFrame(statuses).to_csv(out/'EXISTING_ENDPOINT_STATUS_COUNTS.csv',index=False)
    # Reading the gzip stream through EOF checks decompression/CRC without a
    # second in-memory copy of all saved geometry. Endpoint join was checked above.
    geometry_bytes=0
    with gzip.open(b/'results/ENDPOINT_GEOMETRY.json.gz','rb') as f:
        for block in iter(lambda:f.read(4<<20),b''):
            geometry_bytes+=len(block)
    manifest=[]
    needed=['README.md','REPRODUCE.md','LARGE_TABLE_STORAGE.json','design/ACTUAL_POOLS.csv','design/EXACT_ORDER_DESIGN.csv.gz','inputs/INPUT_SNAPSHOT.json.gz','inputs/REQUESTS_INITIAL.json.gz','inputs/ALL_METHOD_LABELS_LOBO.csv.gz','inputs/FOLD_CLASS_DEFINITIONS.csv','inputs/IMAGE_DIFFICULTY_OPPORTUNITIES.csv','results/ENDPOINT_SCALARS.csv.gz','results/ENDPOINT_GEOMETRY.json.gz','results/PREFIX_TEAM_LINKS.csv.gz','results/PREFIX_GEOMETRY_VARIATION.csv.gz','stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz','code/register_population_orders.py','code/order_policies.py','code/run_prefix_endpoints.py']
    for rel in needed:
        f=b/rel
        manifest.append(dict(source_commit=commit,repository_path=str(f.relative_to(repo)),bytes=f.stat().st_size,sha256=file_sha(f),local_status='restored_existing_main'))
    pd.DataFrame(manifest).to_csv(out/'NECESSARY_SOURCE_FILES.csv',index=False)
    receipt=dict(source_commit=commit, pools=len(p), images=p.image.nunique(),orders=len(orders),natural_orders=len(natural),prefix_rows=len(links),unique_endpoints=scalar_count,natural_new_seed_sequences_verified=checked_new,natural_old_saved_sequences_verified=checked_old,small_exact_pools=len(small),small_exact_paths=sum(r['paths'] for r in small),scalar_read_to_eof=True,geometry_gzip_read_to_eof=True,geometry_uncompressed_bytes=geometry_bytes,missing_endpoint_links=0,extra_unlinked_endpoints=0,new_fusions=0,new_scoring=0,new_classification=0)
    (out/'EXISTING_INPUT_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps(receipt,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
