"""Exact finite-pool opportunity counts versus the actually registered prefixes.

Permutation counts, distinct member sets and complete class vectors are different
units.  This analysis enumerates the registered sample; coefficients count the
much larger feasible spaces without claiming that their endpoints were computed.
"""
from __future__ import annotations
import argparse,json,math
from pathlib import Path
import pandas as pd
from run_prefix_endpoints import csv,save

VECTORS=['structure_coarse_vector','structure_fine_vector',
         'joint_coarse_vector','joint_fine_vector']

def vector_count(capacities,k):
    poly=[1]+[0]*k
    for c in capacities:
        nxt=[0]*(k+1)
        for degree,value in enumerate(poly):
            if value:
                for add in range(min(c,k-degree)+1):nxt[degree+add]+=value
        poly=nxt
    return poly[k]

def main():
    p=argparse.ArgumentParser();p.add_argument('--composition',required=True)
    p.add_argument('--results',required=True);p.add_argument('--out',required=True)
    p.add_argument('--inventory',help='Optional unchanged POOL_DIFFICULTY_SUPPORT.csv');a=p.parse_args()
    comp=Path(a.composition);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    orders=pd.read_csv(comp/'EXACT_ORDER_DESIGN.csv.gz',keep_default_na=False)
    links=pd.read_csv(Path(a.results)/'PREFIX_TEAM_LINKS.csv.gz')
    vectors=pd.read_csv(comp/'ENDPOINT_CLASS_VECTORS.csv.gz',keep_default_na=False).set_index('team_key')
    assert vectors.index.is_unique
    joins=links.merge(vectors[VECTORS],on='team_key',how='left',validate='many_to_one')
    assert joins[VECTORS].notna().all().all()
    metacols=['pool_id','image','condition','layer','difficulty','building','pool_n']
    meta=orders[metacols].drop_duplicates().set_index('pool_id')
    bypool={pid:g for pid,g in joins.groupby('pool_id',sort=False)}
    orderrows=[];prefixrows=[];vectorrows=[]
    for (pid,policy),og in orders.groupby(['pool_id','policy'],sort=False):
        m=meta.loc[pid].to_dict();m['pool_id']=pid;n=int(m['pool_n']);natural=policy=='natural_random'
        t=0 if natural else int(og.iloc[0].target_capacity)
        possible_orders=math.factorial(n) if natural else math.factorial(t)*math.factorial(n-t)
        unique_sequences=og.worker_order.nunique()
        orderrows.append(dict(m,policy=policy,target_capacity=t,registered_orders=len(og),
            unique_registered_orders=unique_sequences,feasible_orders_exact=str(possible_orders),
            uncomputed_orders_exact=str(possible_orders-unique_sequences),
            full_order_enumeration=unique_sequences==possible_orders,
            order_space='N!' if natural else 'T! (N-T)!',
            sampling='complete natural enumeration' if natural and n<=4 else 'uniform base permutation; stable role partition' if not natural else 'uniform without replacement within order'))
        pg=bypool[pid];pg=pg[pg.policy.eq(policy)]
        full=pg[pg.k.eq(n)].iloc[0]
        total_caps={v:json.loads(full[v]) for v in VECTORS}
        target_caps={v:json.loads(pg[pg.k.eq(t)].iloc[0][v]) for v in VECTORS} if not natural else {}
        for k,g in pg.groupby('k',sort=True):
            k=int(k);possible_sets=math.comb(n,k) if natural else (math.comb(t,k) if k<=t else math.comb(n-t,k-t))
            unique=g.team_key.nunique()
            prefixrows.append(dict(m,policy=policy,k=k,target_capacity=t,registered_paths=len(g),
                registered_member_sets=unique,feasible_member_sets=possible_sets,
                uncomputed_member_sets=possible_sets-unique,
                member_sets_completely_covered=unique==possible_sets,
                mechanical_singleton=possible_sets==1,full_pool_endpoint=k==n))
            for v in VECTORS:
                caps=total_caps[v]
                if natural:counts=list(caps.values());choose=k
                elif k<=t:counts=list(target_caps[v].values());choose=k
                else:counts=[caps[c]-target_caps[v].get(c,0) for c in caps];choose=k-t
                feasible_vectors=vector_count(counts,choose);observed=g[v].nunique()
                assert observed<=feasible_vectors
                vectorrows.append(dict(pool_id=pid,policy=policy,k=k,class_vector_field=v,
                    registered_class_vectors=observed,feasible_class_vectors=feasible_vectors,
                    unobserved_class_vectors=feasible_vectors-observed,
                    class_vectors_completely_covered=observed==feasible_vectors,
                    possible_space='unrestricted full-pool prefixes' if natural else 'role-priority constrained prefixes'))
    od=pd.DataFrame(orderrows);pr=pd.DataFrame(prefixrows);vr=pd.DataFrame(vectorrows)
    csv(out/'ORDER_SPACE_COVERAGE.csv',od);csv(out/'PREFIX_MEMBER_SPACE_COVERAGE.csv.gz',pr)
    csv(out/'PREFIX_CLASS_VECTOR_COVERAGE.csv.gz',vr)
    save(out/'SPACE_COVERAGE_RECEIPT.json',dict(orders=len(orders),registered_prefixes=len(links),
        unique_endpoint_sets=links.team_key.nunique(),pool_policy_groups=len(od),prefix_groups=len(pr),
        vector_groups=len(vr),exact_natural_order_pools=int(od[od.policy.eq('natural_random')].full_order_enumeration.sum()),
        counting_only_new_fusions=0,permutations_stored_as_decimal_strings=True,
        class_vectors_counted_by_capacity_polynomial=True,
        exhaustive_claim='Only rows with the corresponding complete_coverage flag; all other feasible counts are capacity, not computed results.'))
    if a.inventory:
        inventory=pd.read_csv(a.inventory);actual=pd.read_csv(comp/'ACTUAL_POOLS.csv')
        formal=actual[['pool_id','image_id','condition','pool_n']].drop_duplicates()
        z=inventory.merge(formal,on=['image_id','condition'],how='left',validate='one_to_one')
        def reason(r):
            if pd.notna(r.pool_id):return 'included_frozen_formal_pool'
            if r.image_layer=='OOS':return 'OOS_not_in_formal_population'
            if r.retained_nonOOS_pool_workers<3:return 'fewer_than_3_eligible_independent_workers'
            if r.quality_usable_pool_records<3:return 'fewer_than_3_formal_quality_records_reference_or_qualification'
            return 'quality_capacity_requires_investigation'
        z['coverage_reason']=z.apply(reason,axis=1)
        csv(out/'FORMAL_POOL_INVENTORY_COVERAGE.csv',z)
        save(out/'FORMAL_POOL_INVENTORY_RECEIPT.json',dict(inventory_condition_pools=len(z),
            count_by_reason=z.coverage_reason.value_counts().to_dict(),
            formal_count_mismatches=int((z.pool_id.notna()&z.quality_usable_pool_records.ne(z.pool_n)).sum()),
            newly_changed_eligibility=0))
    print(json.dumps(dict(pool_policy_groups=len(od),prefix_groups=len(pr),vector_groups=len(vr)),ensure_ascii=False))

if __name__=='__main__':main()
