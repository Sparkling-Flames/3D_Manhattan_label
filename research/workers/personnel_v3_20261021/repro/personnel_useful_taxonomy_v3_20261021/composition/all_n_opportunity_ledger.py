"""All n=1..U opportunity denominators, without enumerating unregistered vectors.

Polynomial coefficients count feasible class-count vectors. Binomial counts
count actual member sets. Existing and newly completed endpoint keys are read
once; no fusion or new configuration search runs here.
"""
from __future__ import annotations
import collections,math,json
import pandas as pd
from multin_design import HERE,gs,h,sha,write_csv,existing_scalar_paths
from design_matched_events import label_maps
from consolidate_deliverables import rows as csv_rows

def run():
    flags=['ALL_BATCHES_COMPLETE.json','LARGE_BLOCK_BATCHES_COMPLETE.json',
           'PURE_BLOCK_BATCHES_COMPLETE.json','F01_CAPACITY_BATCHES_COMPLETE.json']
    if not all((HERE/f).exists() for f in flags):raise RuntimeError('All registered endpoint stages must finish before actual endpoint accounting')
    out=HERE/'configuration_union';domains=pd.read_csv(out/'CANONICAL_DOMAIN_COVERAGE.csv.gz',keep_default_na=False)
    maps,_=label_maps();spaces={};listed={}
    for r in domains.to_dict('records'):
        key=(r['method_id'],r['tier'],r['pool_id'],r['known_domain_workers'])
        did=h('all-n-known-personnel-domain',key)[:24]
        if did not in spaces:
            spaces[did]=dict(r,all_n_domain_id=did,workers=r['known_domain_workers'].split('|') if r['known_domain_workers'] else [],aliases=set(),stages=set())
        spaces[did]['aliases'].update(tuple(v) for v in json.loads(r['domain_aliases']))
        spaces[did]['stages'].update(r['stage_identities'].split('|'))
        listed[did,int(r['n'])]=int(r['feasible_configurations'])
    main_panels=pd.read_csv(HERE/'PANELS.csv',keep_default_na=False)
    formal={r.pool_id:r for r in main_panels[main_panels.source_domain.eq('all_formal')].itertuples()}
    universe=sorted({w for r in spaces.values() for w in r['workers']}|{w for r in formal.values() for w in r.domain_workers.split('|')});wi={w:i for i,w in enumerate(universe)}
    def mask(ws):
        val=0
        for w in ws:
            if w not in wi:return None
            val|=1<<wi[w]
        return val
    pools={r['pool_id'] for r in spaces.values()};endpoints=collections.defaultdict(dict)
    for path in existing_scalar_paths():
        for d in pd.read_csv(path,usecols=['team_key','pool_id','k','member_workers'],chunksize=40000):
            for r in d[d.pool_id.isin(pools)&d.k.ge(1)].itertuples():
                mm=mask(r.member_workers.split('|'))
                if mm is not None:endpoints[(r.pool_id,int(r.k))][r.team_key]=(mm,True,False)
    for plan in ['BATCH_PLAN.csv','LARGE_BLOCK_BATCH_PLAN.csv','PURE_BATCH_PLAN.csv','F01_BATCH_PLAN.csv']:
        for bid in pd.read_csv(HERE/plan).batch_id:
            for r in csv_rows(HERE/'batches'/bid/'ENDPOINT_SCALARS.csv.gz'):
                mm=mask(r['member_workers'].split('|'))
                if mm is None:continue
                key=(r['pool_id'],int(r['k']));old=endpoints[key].get(r['team_key'])
                if old is not None and old[0]!=mm:raise ValueError('actual endpoint key/member conflict')
                endpoints[key][r['team_key']]=(mm,old[1] if old else False,True)
    result=[];empty=[]
    for did,r in sorted(spaces.items()):
        mapping,_=maps[(r['method_id'],r['tier'],r['condition'],r['building'])]
        capacities=collections.Counter(mapping[w] for w in r['workers']);coeff=gs.vector_coefficients(list(capacities.values()))
        u=len(r['workers']);dm=mask(r['workers'])
        if u<1:
            empty.append(dict(all_n_domain_id=did,method_id=r['method_id'],tier=r['tier'],pool_id=r['pool_id'],condition=r['condition'],building=r['building'],known_domain_n=u,reason='no_known_members'))
            continue
        for n in range(1,u+1):
            old=new=both=0
            for mm,prior,v3 in endpoints[(r['pool_id'],n)].values():
                if mm&~dm:continue
                old+=prior;new+=v3;both+=1
            listed_count=listed.get((did,n));complete_list=listed_count is not None
            if complete_list and listed_count!=coeff[n]:raise ValueError('DP count differs from actual full vector list')
            total=math.comb(u,n)
            if both>total:raise ValueError('endpoint coverage exceeds all-n member universe')
            result.append(dict(all_n_domain_id=did,method_id=r['method_id'],tier=r['tier'],pool_id=r['pool_id'],image=r['image'],building=r['building'],condition=r['condition'],difficulty=r['difficulty'],
              known_domain_n=u,known_domain_workers='|'.join(r['workers']),domain_aliases=json.dumps(sorted(r['aliases']),ensure_ascii=False,separators=(',',':')),
              n=n,class_capacity=gs.canonical_counts(dict(capacities)),all_feasible_configurations=str(coeff[n]),all_possible_member_sets=str(total),
              all_ordered_member_prefixes=str(math.perm(u,n)),orders_per_unordered_endpoint=str(math.factorial(n)),
              complete_class_vector_list_available=complete_list,listed_class_vectors=listed_count if complete_list else 0,
              not_individually_listed_class_vectors=0 if complete_list else str(coeff[n]),
              prior_cached_member_sets=old,v3_completed_member_sets=new,union_computed_member_sets=both,
              uncomputed_member_sets=str(total-both),any_real_endpoint=both>0,exhaustive_members=both==total,
              current_round_actual_n_has_endpoint=new>0,
              small_n_not_registered_this_round=n<4,
              endpoint_vertex_validity_does_not_set_team_size=True,
              full_set_n_equals_U=n==u,member_variation_estimable=both>=2 and total>1,
              full_set_zero_variation_is_evidence=False,ordered_processes_not_expanded=True))
    write_csv(out/'ALL_N_OPPORTUNITY_LEDGER.csv.gz',pd.DataFrame(result))
    write_csv(out/'ALL_N_EMPTY_DOMAIN_OPPORTUNITIES.csv',pd.DataFrame(empty,columns=['all_n_domain_id','method_id','tier','pool_id','condition','building','known_domain_n','reason']))
    # Class-independent full formal pool space is a disjoint global universe
    # across pool,n. It is safe to sum these counts; method/domain ledgers are not.
    formal_rows=[]
    for pid,r in sorted(formal.items()):
        u=len(r.domain_workers.split('|'))
        for n in range(1,u+1):
            observed=endpoints[(pid,n)];total=math.comb(u,n)
            formal_rows.append(dict(pool_id=pid,image=r.image,building=r.building,condition=r.condition,
              difficulty=r.difficulty,formal_pool_n=u,n=n,all_member_sets=str(total),
              all_ordered_member_prefixes=str(math.perm(u,n)),orders_per_unordered_endpoint=str(math.factorial(n)),
              prior_cached_members=sum(v[1] for v in observed.values()),v3_completed_members=sum(v[2] for v in observed.values()),
              computed_union_members=len(observed),uncomputed_members=str(total-len(observed)),
              complete_member_census=len(observed)==total,full_set_n_equals_pool_n=n==u,
              small_n_not_registered_this_round=n<4,
              member_variation_estimable=len(observed)>1 and total>1))
    write_csv(out/'SELECTED_FORMAL_POOLS_ALL_N_MEMBER_SPACE.csv',pd.DataFrame(formal_rows))
    receipt=dict(status='complete',known_worker_domains=len(spaces),domain_n_rows=len(result),empty_domain_rows=len(empty),
      minimum_n=1,maximum_n=max(r['n'] for r in result),small_n_one_to_three_rows=sum(r['n']<4 for r in result),n_with_full_class_vector_list=sum(r['complete_class_vector_list_available'] for r in result),
      n_with_real_endpoint=sum(r['any_real_endpoint'] for r in result),full_set_singleton_rows=sum(r['full_set_n_equals_U'] for r in result),
      dynamic_programming_used_instead_of_unregistered_vector_enumeration=True,native_calls=0,
      member_variation_estimable_definition='At least two distinct computed member sets in a non-singleton member universe; quality and geometry still require their own valid-outcome support. Failures remain endpoints.',
      current_stages_complete=True,source_and_method_universes_overlap=True,
      selected_formal_pools=len(formal),formal_pool_n_strata=len(formal_rows),
      all_n_formal_disjoint_member_universe=str(sum(int(r['all_member_sets']) for r in formal_rows)),
      all_n_formal_computed_union_members=sum(r['computed_union_members'] for r in formal_rows),files=[
       dict(path=str((out/f).relative_to(HERE)),bytes=(out/f).stat().st_size,sha256=sha(out/f))
       for f in ['ALL_N_OPPORTUNITY_LEDGER.csv.gz','ALL_N_EMPTY_DOMAIN_OPPORTUNITIES.csv','SELECTED_FORMAL_POOLS_ALL_N_MEMBER_SPACE.csv']])
    gs.save(out/'ALL_N_LEDGER_COMPLETE.json',receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':run()
