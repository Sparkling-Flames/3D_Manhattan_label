#!/usr/bin/env python3
"""Separate all n20 class vectors from ABC-feasible vectors and actual sets.

Exact integer denominators are written as decimal strings; read those columns
as strings rather than spreadsheet floating-point numbers.
"""
import collections, json, math
import pandas as pd
from register_structure import HERE, gs, all_count_vectors, write, save, sha

def main():
    source=HERE/('ALL_EVENTS_REGISTERED.csv.gz' if (HERE/'ALL_EVENTS_REGISTERED.csv.gz').exists() else 'EVENTS_REGISTERED.csv.gz')
    E=pd.read_csv(source,keep_default_na=False);E=E[E.n.eq(20)]
    labels=pd.read_csv(HERE/'CLASS_LABELS_REUSED.csv.gz',keep_default_na=False)
    maps={b:dict(zip(g.worker_id,g.coarse_label)) for b,g in labels[labels.known.astype(str).str.lower().isin(['true','1'])].groupby('heldout_building')}
    pools=gs.pool_lookup();rows=[];summary=[]
    for (pid,domain),events in E.groupby(['pool_id','source_domain']):
        pool=pools[pid];meta=pool['meta'];lab=maps[meta['building']]
        ws=sorted({r['worker_id'] for r in pool['records'] if domain=='all_formal' or r['origin']=='new'}&lab.keys())
        cap=collections.Counter(lab[w] for w in ws);cats,vectors=all_count_vectors(cap,20)
        registered={}
        for arm in 'ABC':
            for key,workers in zip(events['team_'+arm],events[arm+'_member_workers']):registered[key]=workers.split('|')
        seen=collections.Counter(tuple(sum(lab[w]==c for w in ww) for c in cats) for ww in registered.values())
        group_rows=[]
        for vector in vectors:
            count=math.prod(math.comb(cap[c],k) for c,k in zip(cats,vector));have=seen[vector]
            r=dict(pool_id=pid,image=meta['image'],building=meta['building'],condition='manual',source_domain=domain,n=20,
                raw_class_counts='|'.join(f'{c}:{k}' for c,k in zip(cats,vector)),raw_class_capacities='|'.join(f'{c}:{cap[c]}' for c in cats),
                possible_concrete_teams=str(count),registered_unique_teams=have,unregistered_concrete_teams=str(count-have),
                count_vector_observed=bool(have),member_census_complete=have==count)
            group_rows.append(r);rows.append(r)
        assert sum(int(r['possible_concrete_teams']) for r in group_rows)==math.comb(len(ws),20)
        summary.append(dict(pool_id=pid,image=meta['image'],building=meta['building'],source_domain=domain,n=20,N=len(ws),
            all_feasible_n20_class_vectors=len(vectors),observed_n20_class_vectors=sum(r['count_vector_observed'] for r in group_rows),
            possible_concrete_teams=str(math.comb(len(ws),20)),registered_unique_teams=len(registered),
            unregistered_concrete_teams=str(math.comb(len(ws),20)-len(registered))))
    outputs=[write(HERE/'N20_FULL_CLASS_VECTOR_SPACE.csv.gz',rows),write(HERE/'N20_FULL_MEMBER_SPACE_BY_POOL.csv',summary)]
    totals=[]
    for domain in sorted({r['source_domain'] for r in summary}):
        rr=[r for r in summary if r['source_domain']==domain]
        totals.append(dict(source_domain=domain,pools=len(rr),all_feasible_n20_class_vectors=sum(r['all_feasible_n20_class_vectors'] for r in rr),
            observed_n20_class_vectors=sum(r['observed_n20_class_vectors'] for r in rr),
            possible_concrete_teams=str(sum(int(r['possible_concrete_teams']) for r in rr)),registered_unique_teams=sum(r['registered_unique_teams'] for r in rr),
            unregistered_concrete_teams=str(sum(int(r['unregistered_concrete_teams']) for r in rr))))
    outputs.append(write(HERE/'N20_FULL_SPACE_TOTALS.csv',totals))
    save(HERE/'FULL_SPACE_DESCRIPTION.json',dict(source_sha256=sha(source),outputs=outputs,
        domain='Only pool/source-domain combinations in this registered n20 experiment; unused fold families and unavailable pools separately inventoried.',
        distinction='All unconstrained n20 class vectors and all concrete teams differ from the smaller pure-block ABC-feasible background-vector population. The latter has a full vector census; neither implies a full census of actual member sets.',
        duplicates='Every team_key counted once within pool/domain. New-source teams may also belong to all-formal; domain totals must not be summed as a unique global set count.'))
    print(json.dumps(totals,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
