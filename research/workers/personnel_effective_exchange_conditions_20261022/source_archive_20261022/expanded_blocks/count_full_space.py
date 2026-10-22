#!/usr/bin/env python3
"""Exact class-vector / member / background denominators for frozen directions."""
from register_expanded import *

def count_vectors(classes,limits,left,prefix=None):
    prefix=prefix or {}
    if not classes:
        if left==0:yield dict(prefix)
        return
    c=classes[0]
    for k in range(min(limits[c],left)+1):
        yield from count_vectors(classes[1:],limits,left-k,dict(prefix,**{c:k}))

def main():
    maps,_=label_maps();pools=gs.pool_lookup()
    cap=pd.read_csv(HERE/'CAPACITY_ALL_ATTEMPTS.csv.gz',keep_default_na=False)
    panels=pd.read_csv(HERE/'REGISTERED_MEMBER_PANELS.csv.gz',keep_default_na=False)
    out=[];ledger=[]
    for r in cap[cap.status.eq('available')].to_dict('records'):
        labels,_=maps[(r['method_id'],r['tier'],r['condition'],r['building'])]
        ws=sorted({x['worker_id'] for x in pools[r['pool_id']]['records']}&labels.keys())
        counts=collections.Counter(labels[w] for w in ws);limits=dict(counts)
        s,t,m,n=r['source_class'],r['target_class'],int(r['m']),int(r['n'])
        limits[s]-=2*m;limits[t]-=m
        fullbg=fullabc=0;avec={};cvec={};configs=set()
        for bg in count_vectors(sorted(counts),limits,n-m):
            ways=math.prod(choose(counts[c],v) for c,v in bg.items())
            A=dict(bg);A[s]+=m;C=dict(bg);C[t]+=m
            aa=gs.canonical_counts(A);cc=gs.canonical_counts(C);bb=gs.canonical_counts(bg)
            a_n=math.prod(choose(counts[c],v) for c,v in A.items())
            c_n=math.prod(choose(counts[c],v) for c,v in C.items())
            abc=ways*choose(counts[s]-bg[s],m)*choose(counts[s]-bg[s]-m,m)*choose(counts[t]-bg[t],m)
            fullbg+=ways;fullabc+=abc;avec[aa]=a_n;cvec[cc]=c_n;configs.update([aa,cc])
            out.append(dict(cell_id=r['cell_id'],pool_id=r['pool_id'],method_id=r['method_id'],n=n,m=m,
                background_counts=bb,A_counts=aa,C_counts=cc,concrete_backgrounds=str(ways),
                concrete_A_teams=str(a_n),concrete_C_teams=str(c_n),oriented_ABC=str(abc)))
        g=panels[panels.cell_id.eq(r['cell_id'])]
        reg_abcs=int(g.registered_oriented_ABC.astype(int).sum())
        endpoints={**avec,**cvec}
        assert fullbg==int(r['possible_backgrounds'])
        ledger.append(dict(r,feasible_background_class_vectors=sum(x['cell_id']==r['cell_id'] for x in out),
            feasible_endpoint_class_vectors=len(configs),
            all_possible_member_endpoints=str(sum(endpoints.values())),
            all_possible_oriented_ABC=str(fullabc),registered_oriented_ABC=reg_abcs,
            unregistered_oriented_ABC=str(fullabc-reg_abcs),
            registered_unordered_complement_source_pairs=int(g.registered_source_blocks.astype(int).sum())//2,
            source_block_census_closed_under_complement=True,
            event_orientations_are_not_independent_replicates=True,
            orders_expanded=0))
    write_csv(HERE/'ALL_FEASIBLE_CLASS_CONFIGURATIONS.csv.gz',out)
    write_csv(HERE/'EXACT_FULL_SPACE_LEDGER.csv.gz',ledger)
    gs.save(HERE/'FULL_SPACE_COUNT_RECEIPT.json',dict(cells=len(ledger),class_background_vectors=len(out),
        all_feasible_class_vectors_enumerated=True,full_member_counts_exact=True,full_member_sets_not_all_computed=True,
        oriented_ABC_definition='Ordered source X and disjoint same-class Y, target Z from another class, common D; exchanging X/Y is counted as another orientation but not an independent experiment.',
        aggregation='panel then image then building equal weight; ordinary, doorway, special separate'))
    print(json.dumps(dict(cells=len(ledger),class_background_vectors=len(out))),flush=True)

if __name__=='__main__':main()
