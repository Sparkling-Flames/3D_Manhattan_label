"""Target-separated feasible replacement space; no scores are read for selection.

Intervals encode all feasible n for every m/class direction. A compact adaptive
global grid is exported separately, with its coverage kept distinct from exact
member/event counts. Missing class history remains an unknown background role.
"""
from __future__ import annotations
import argparse,collections,csv,gzip,hashlib,itertools,json,math,os
from pathlib import Path

def read_json(path):
    p=Path(path)
    with (gzip.open(p,'rt',encoding='utf-8-sig') if p.suffix=='.gz' else p.open(encoding='utf-8-sig')) as f:return json.load(f)

def read_labels(path):
    p=Path(path)
    with (gzip.open(p,'rt',encoding='utf-8-sig') if p.suffix=='.gz' else p.open(encoding='utf-8-sig')) as f:
        return list(csv.DictReader(f))

def truth(x):return str(x).strip().lower() in ('true','1','1.0')

def canonical_hash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def capacities(pool,labels):
    ids={r['worker_id'] for r in pool['records']}
    known={r['worker_id']:r['class_id'] for r in labels if truth(r.get('known',True)) and r['class_id'] not in ('','nan','None','unknown')}
    groups=collections.defaultdict(list)
    for w in sorted(ids):groups[known.get(w,'unknown')].append(w)
    return dict(groups)

def intervals(N,S,T,min_n=3):
    """Every class-direction/m feasibility interval, including all smaller m."""
    for m in range(1,min(S,T)+1):
        lo=max(min_n,m)
        abc_hi=N-2*m if S>=2*m else -1
        ac_hi=N-m
        yield dict(m=m,n_min=lo,strict_ABC_n_max=abc_hi if abc_hi>=lo else None,
                   direct_AC_n_max=ac_hi if ac_hi>=lo else None,
                   source_capacity=S,target_capacity=T,pool_n=N)

def adaptive_grid(N,S,T,min_n=3):
    """Input-only wide grid: actual class capacity, half/quarter/high replacement.

    Maximum m must itself permit n>=m and n>=min_n. The n grid is generated
    after m; no preferred n20 or n18/m7 cell enters the candidate definition.
    Old public anchors are retained for a matched historical comparison.
    """
    max_m=min(S//2,T,N//3,(N-min_n)//2)
    if max_m<1:return []
    ms={1 if max_m==1 else 2,math.ceil(max_m/2),max_m}
    ms.update(m for m in (4,6,7) if m<=max_m)
    if N<=8:ms.update(range(1,max_m+1))
    cells=set()
    for m in sorted(ms):
        ns={max(min_n,m),math.ceil(1.35*m),2*m,4*m,N-2*m,12,18,20,24}
        if N<=8:ns.update(range(max(min_n,m),N-2*m+1))
        for n in ns:
            if min_n<=n and m<=n and n+2*m<=N:cells.add((n,m))
    legacy={(10,7),(12,8),(12,10),(14,9),(16,8),(17,9),(18,7),(20,6),(24,5),(8,4),(12,4),(20,4)}
    cells.update((n,m) for n,m in legacy if n>=min_n and m<=n and S>=2*m and T>=m and N>=n+2*m)
    return sorted(cells)

def exact_counts(N,S,T,n,m):
    strict=S>=2*m and T>=m and m<=n and N>=n+2*m
    direct=S>=m and T>=m and m<=n and N>=n+m
    xyz=math.comb(S,m)*math.comb(S-m,m)*math.comb(T,m)//2 if strict else 0
    xz=math.comb(S,m)*math.comb(T,m) if direct else 0
    return dict(strict_ABC=bool(strict),direct_AC=bool(direct),
                xyz_unordered_AB_count=str(xyz),strict_ABC_member_background_count=str(xyz*math.comb(N-3*m,n-m) if strict else 0),
                direct_AC_member_background_count=str(xz*math.comb(N-2*m,n-m) if direct else 0))

def count_vectors(caps,n):
    a=[1]+[0]*n
    for c in caps:
        b=[0]*(n+1)
        for i,v in enumerate(a):
            if v:
                for j in range(min(c,n-i)+1):b[i+j]+=v
        a=b
    return a[n]

def write_csv(path,rows):
    rows=list(rows);p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    fields=list(dict.fromkeys(k for r in rows for k in r))
    temp=p.with_name(p.name+'.writing')
    with (gzip.open(temp,'wt',encoding='utf-8-sig',newline='') if p.suffix=='.gz' else temp.open('w',encoding='utf-8-sig',newline='')) as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    with temp.open('rb') as f:os.fsync(f.fileno())
    temp.replace(p)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pools',nargs='+',required=True);ap.add_argument('--labels',required=True)
    ap.add_argument('--output',required=True);ap.add_argument('--condition',default='manual');ap.add_argument('--min-n',type=int,default=3)
    ap.add_argument('--intervals-only',action='store_true')
    a=ap.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    pools=[p for name in a.pools for p in read_json(name)['images'] if p['meta']['condition']==a.condition]
    assert len({p['pool_id'] for p in pools})==len(pools)
    labels=read_labels(a.labels);lookup=collections.defaultdict(list)
    for r in labels:
        if r.get('heldout_building')=='ALL':continue
        if r.get('condition',a.condition) not in (a.condition,'joint','both',''):continue
        lookup[r['method'],r['heldout_building']].append(r)
    inventory=[];spaces=[];grid=[]
    for p in pools:
        meta=p['meta'];pid=p['pool_id'];N=len(p['records'])
        for (method,b),ll in sorted(lookup.items()):
            if b!=meta['building']:continue
            groups=capacities(p,ll);g={c:ws for c,ws in groups.items() if c!='unknown'}
            base=dict(pool_id=pid,image=meta['image'],building=b,reference_id=meta['reference_id'],reference_version=meta['reference_version'],
                      condition=meta['condition'],layer=meta['layer'],difficulty=meta.get('difficulty'),method=method,pool_n=N,
                      labelled_n=sum(map(len,g.values())),unknown_n=len(groups.get('unknown',[])),class_capacities=json.dumps({c:len(ws) for c,ws in groups.items()},sort_keys=True))
            inventory.append(base)
            for s,t in itertools.permutations(sorted(g),2):
                S,T=len(g[s]),len(g[t]);ident=dict(base,source_class=s,target_class=t)
                for rr in intervals(N,S,T,a.min_n):spaces.append(dict(ident,**rr))
                for n,m in ([] if a.intervals_only else adaptive_grid(N,S,T,a.min_n)):
                    counts=exact_counts(N,S,T,n,m)
                    d=n-m;rest=N-3*m;target_remaining=T-m
                    lo=max(0,d-(rest-target_remaining));hi=min(d,target_remaining)
                    levels=sorted({lo,(lo+hi)//2,hi})
                    remcaps=[len(ws)-(2*m if c==s else m if c==t else 0) for c,ws in groups.items()]
                    grid.append(dict(ident,n=n,m=m,replacement_fraction=m/n,source_candidate_fraction=m/S,
                                     target_candidate_fraction=m/T,D_target_min=lo,D_target_max=hi,
                                     D_class_vector_count=count_vectors(remcaps,d),D_target_levels='|'.join(map(str,levels)),
                                     budget_1XYZ_1D_per_level=len(levels),budget_2XYZ_1D_per_level=2*len(levels),**counts))
    write_csv(out/'POOL_METHOD_CAPACITY.csv.gz',inventory)
    write_csv(out/'ALL_FEASIBLE_M_N_INTERVALS.csv.gz',spaces)
    if not a.intervals_only:write_csv(out/'ADAPTIVE_GRID_CAPACITY.csv.gz',grid)
    receipt=dict(labels_sha256=hashlib.sha256(Path(a.labels).read_bytes()).hexdigest(),source_pools=a.pools,
        pools=len(pools),methods=len({r['method'] for r in inventory}),pool_method_rows=len(inventory),all_m_intervals=len(spaces),
        proposed_grid_cells=len(grid),proposed_1XYZ_events=sum(r['budget_1XYZ_1D_per_level'] for r in grid),
        proposed_2XYZ_events=sum(r['budget_2XYZ_1D_per_level'] for r in grid),
        naive_endpoint_upper_bound_1XYZ=3*sum(r['budget_1XYZ_1D_per_level'] for r in grid),
        note='Input-only exact capacity inventory; no experiment or endpoint claimed computed. Every interval represents all integer n in its bounds; n<3 and actual two-person analysis separate. Endpoint upper bound precedes exact-set and candidate-partition deduplication.')
    (out/'CAPACITY_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
