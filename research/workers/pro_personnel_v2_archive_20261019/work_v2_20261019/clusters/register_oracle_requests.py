"""Freeze actual-cluster oracle teams and complete sequential prefix paths.

The selection sees local annotation geometry clusters, so it is retrospective.
No source Q, time, or fusion output is read. All IDs/order/seed are exported.
"""
from __future__ import annotations
import collections,gzip,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
SEED=2026101909

def read(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:return json.load(f)

def write(path,x):
    encoded=json.dumps(x,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    if str(path).endswith('.gz'):
        with gzip.open(path,'wt',encoding='utf-8') as f:f.write(encoded)
    else:Path(path).write_text(encoded+'\n',encoding='utf-8')

def rng_for(*parts):
    s=json.dumps([SEED,*parts],ensure_ascii=False,separators=(',',':'))
    seed=int.from_bytes(hashlib.sha256(s.encode()).digest()[:8],'little')
    return np.random.default_rng(seed),seed

def draw_order(groups,strategy,rng):
    groups=[list(np.asarray(g)[rng.permutation(len(g))]) for g in groups]
    if strategy in ('largest_cluster_first','pure_major_cluster'):
        return [str(x) for g in (groups[:1] if strategy=='pure_major_cluster' else groups) for x in g]
    assert strategy=='cluster_balanced'
    return [str(g[i]) for i in range(max(map(len,groups))) for g in groups if len(g)>i]

def main():
    doc=read(HERE/'CLUSTER_API.json.gz')
    requests=[];paths=[];coverage=[]
    for pool in doc['pools']:
        meta=pool['meta'];pid=meta['pool_id']
        if meta['layer']!='ordinary_manual':continue
        worker={r['object_id']:r['worker_id'] for r in pool['geometries']}
        for part in pool['partitions']:
            cut=int(part['threshold_deg'])
            groups=sorted([sorted(g) for g in part['affinity']],key=lambda g:(-len(g),tuple(g)))
            groupid={o:i+1 for i,g in enumerate(groups) for o in g}
            for strategy in ['largest_cluster_first','cluster_balanced','pure_major_cluster']:
                supported=sum(map(len,groups)) if strategy!='pure_major_cluster' else len(groups[0])
                for k in [8,12,16,24]:
                    if supported<k:
                        coverage.append(dict(pool_id=pid,image_code=meta['image_code'],building_id=meta['building_id'],
                            threshold=cut,strategy=strategy,k=k,supported=False,reason='largest_cluster_too_small' if strategy=='pure_major_cluster' else 'pool_too_small',pool_n=len(worker),largest_cluster_n=len(groups[0])))
                        continue
                    for draw in range(4):
                        rng,seed=rng_for(pid,cut,strategy,draw)
                        order=draw_order(groups,strategy,rng);oids=order[:k]
                        comp=collections.Counter(groupid[x] for x in oids)
                        composition=json.dumps(dict(sorted(comp.items())),separators=(',',':'))
                        request=dict(request_id=f'co_{pid}_t{cut}_{strategy}_k{k}_d{draw}',pool_id=pid,
                            request_family='cluster_oracle',strategy=strategy,threshold=cut,composition=composition,
                            draw_id=draw,k=k,worker_ids=[worker[o] for o in oids],ordered_object_ids=oids,
                            seed=seed,cluster_ids=[groupid[o] for o in oids],reference_id=meta['reference_id'],
                            reference_version=meta['reference_version'],explanatory_oracle=True)
                        requests.append(request)
                    coverage.append(dict(pool_id=pid,image_code=meta['image_code'],building_id=meta['building_id'],
                        threshold=cut,strategy=strategy,k=k,supported=True,reason='',pool_n=len(worker),largest_cluster_n=len(groups[0])))
            # Actual-person complete paths, with the same full-pool endpoint.
            for strategy in ['largest_cluster_first','cluster_balanced']:
                rng,seed=rng_for(pid,cut,strategy,'prefix')
                order=draw_order(groups,strategy,rng)
                path_id=f'cp_{pid}_t{cut}_{strategy}'
                path_requests=[]
                for k in range(1,len(order)+1):
                    oids=order[:k];comp=collections.Counter(groupid[x] for x in oids)
                    rid=f'{path_id}_k{k}'
                    requests.append(dict(request_id=rid,pool_id=pid,request_family='cluster_oracle_prefix',
                        strategy=strategy,threshold=cut,path_id=path_id,draw_id=0,k=k,
                        added_worker=worker[order[k-1]],worker_ids=[worker[o] for o in oids],
                        ordered_object_ids=oids,composition=json.dumps(dict(sorted(comp.items())),separators=(',',':')),
                        seed=seed,cluster_ids=[groupid[o] for o in oids],reference_id=meta['reference_id'],
                        reference_version=meta['reference_version'],explanatory_oracle=True))
                    path_requests.append(rid)
                paths.append(dict(path_id=path_id,pool_id=pid,strategy=strategy,threshold=cut,seed=seed,
                    worker_order=[worker[o] for o in order],object_order=order,request_ids=path_requests,
                    recompute_each_observed_prefix=True,full_pool_endpoint_order_invariant=True))
    assert len({r['request_id'] for r in requests})==len(requests)
    outfile=HERE/'ORACLE_REQUESTS.json.gz'
    payload=dict(schema='v2_registered_cluster_oracle_requests_20261019_r1',seed=SEED,
        cluster_input_sha256=hashlib.sha256((HERE/'CLUSTER_API.json.gz').read_bytes()).hexdigest(),
        design_sha256=hashlib.sha256((HERE/'DESIGN.json').read_bytes()).hexdigest(),
        role='explanatory target-answer geometry oracle; not prospective worker classification',requests=requests,paths=paths)
    write(outfile,payload);pd.DataFrame(coverage).to_csv(HERE/'oracle_coverage.csv',index=False)
    receipt=dict(requests=len(requests),teams=sum(r['request_family']=='cluster_oracle' for r in requests),
        prefix_requests=sum(r['request_family']=='cluster_oracle_prefix' for r in requests),paths=len(paths),
        pools=len({r['pool_id'] for r in requests}),ordinary_images=len({r['pool_id'] for r in requests}),
        unique_member_sets=len({(r['pool_id'],tuple(sorted(r['worker_ids']))) for r in requests}),
        sha256=hashlib.sha256(outfile.read_bytes()).hexdigest(),seed=SEED)
    write(HERE/'ORACLE_REGISTRATION_RECEIPT.json',receipt);print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
