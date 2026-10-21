"""Append deterministic feasible events for the 21 unfilled capacity maxima.

The original 12,932 events, their failed draws and all configuration samples
are preserved. This script reads only metadata, labels and exact member lists;
it never reads scores, geometries, timing or outcome-based selections.

Preparation deliberately does not mutate the request file consumed by an
already-running native process. Apply only after that process has finished.
"""
from __future__ import annotations
import argparse,collections
from global_study import *
from prepare_design import capable_extra_classes,meta


def prepare():
    old_events=pd.read_csv(OUT/'ABC_EVENTS.csv.gz',keep_default_na=False)
    opportunities=pd.read_csv(OUT/'ABC_OPPORTUNITY_LEDGER.csv')
    event_group=['pool_id','method_id','tier','n','event_mode']
    maxima=opportunities.loc[opportunities.requested_by.str.contains('max_ABC_for_mode',na=False)&opportunities.changed_count_ABC_possible].copy()
    actual=old_events.groupby(event_group).m_AB.max().rename('maximum_registered_m').reset_index()
    maxima=maxima.merge(actual,on=event_group,how='left',validate='1:1')
    missing=maxima.loc[maxima.maximum_registered_m.fillna(0)<maxima.exact_max_m_ABC].copy()
    csv(OUT/'MAXIMUM_TURNOVER_MISSING_PRE_V3.csv',missing)
    if len(missing)!=21:raise ValueError(('unexpected scope',len(missing)))
    pools=pool_lookup();maps=method_maps();labels=method_rows()
    parents={(r.method_id,r.condition,r.heldout_building,r.worker_id):r.parent_class for r in labels.itertuples() if r.tier=='fine'}
    old_requests=read(OUT/'ENDPOINT_REQUESTS.json.gz')['requests'];old_keys={r['team_key'] for r in old_requests}
    requests={};events=[];ledger=[]
    for r in missing.sort_values(event_group).to_dict('records'):
        pool=pools[r['pool_id']];method=r['method_id'];tier=r['tier'];condition=r['condition'];building=r['building'];n=int(r['n']);m=int(r['exact_max_m_ABC']);mode=r['event_mode']
        if tier!='fine' or mode!='within_coarse_fine_change':raise ValueError('unapproved capacity scope')
        mapping=maps[method,tier,condition,building];formal={r['worker_id'] for r in pool['records']};eligible=formal&mapping.keys()
        groups={c:sorted(w for w in eligible if mapping[w]==c) for c in sorted(set(mapping[w] for w in eligible))};cap={c:len(v) for c,v in groups.items()};U=sum(cap.values())
        parent={c:parents[method,condition,building,groups[c][0]] for c in cap}
        allx=list(count_vectors({c:v//2 for c,v in cap.items()},m));valid=[x for x in allx if capable_extra_classes(x,cap,parent)]
        if n+m>=U or not valid:raise ValueError('metadata maximum has no constructive witness')
        seed=['capacity_completion_v3',method,tier,pool['pool_id'],n,m,mode];random=rng(seed)
        x=min(valid,key=lambda x:digest([seed,'block',x]));X=[];Y=[]
        for c in sorted(cap):
            picked=random.choice(groups[c],2*x[c],replace=False).tolist();X.extend(picked[:x[c]]);Y.extend(picked[x[c]:])
        rest=sorted(eligible-set(X)-set(Y));possible_extra=capable_extra_classes(x,cap,parent)
        reserved=min([w for w in rest if mapping[w] in possible_extra],key=lambda w:digest([seed,'reserve',w]));rest.remove(reserved)
        S=random.choice(rest,n-m,replace=False).tolist();A=set(S+X);B=set(S+Y);outside=sorted(eligible-A)
        outcap=collections.Counter(mapping[w] for w in outside)
        def parentcount(v):
            result=collections.Counter()
            for c,k in v.items():result[parent[c]]+=k
            return result
        zchoices=[z for z in count_vectors({c:outcap[c] for c in cap},m) if z!=x and parentcount(z)==parentcount(x)]
        distance=lambda z:sum(abs(z[c]-x[c]) for c in cap)//2
        z=min(zchoices,key=lambda z:(-distance(z),digest([seed,'alternative',z])))
        Z=[]
        for c in sorted(cap):Z.extend(random.choice([w for w in outside if mapping[w]==c],z[c],replace=False).tolist())
        C=set(S+Z)
        assert A&B==A&C==set(S) and len(A-B)==len(A-C)==m and len(A)==len(B)==len(C)==n
        counts=[{c:sum(mapping[w]==c for w in team) for c in cap} for team in (A,B,C)]
        assert counts[0]==counts[1] and counts[0]!=counts[2] and parentcount(counts[0])==parentcount(counts[2])
        keys=[]
        for team in (A,B,C):
            key=team_key(pool['pool_id'],team);keys.append(key)
            if key not in old_keys:requests[key]=dict(team_key=key,pool_id=pool['pool_id'],member_workers=sorted(team),n=n,stages=['capacity_completion_v3'])
        common=dict(meta(pool),method_id=method,tier=tier,labelled_pool_n=U,formal_pool_n=len(formal),class_capacities=canonical_counts(cap))
        event_id=digest([method,tier,mode,pool['pool_id'],n,m,sorted(S),sorted(X),sorted(Y),sorted(Z)])[:24]
        events.append(dict(common,event_id=event_id,event_mode=mode,registration_stage='capacity_completion_v3',n=n,m_AB=m,m_AC=m,m_BC=len(B-C),
            overlap_AB=len(A&B),overlap_AC=len(A&C),overlap_BC=len(B&C),new_block_YZ_overlap=len(set(Y)&set(Z)),composition_turnover_AC=distance(z),
            team_A=keys[0],team_B=keys[1],team_C=keys[2],composition_A=canonical_counts(counts[0]),composition_B=canonical_counts(counts[1]),composition_C=canonical_counts(counts[2]),
            common_background='|'.join(sorted(S)),outgoing_block_X='|'.join(sorted(X)),same_count_block_Y='|'.join(sorted(Y)),changed_count_block_Z='|'.join(sorted(Z)),
            ABC_sampling='One metadata-only constructive witness for a previously unfilled exact maximum m; not exhaustive event triplets'))
        possible_ab=sum(math.prod(math.comb(cap[c],v[c])*math.comb(cap[c]-v[c],v[c]) for c in cap)*math.comb(U-2*m,n-m) for v in allx)
        ledger.append(dict(common,n=n,m=m,event_mode=mode,feasible_equal_count_block_vectors=len(allx),sampled_equal_count_block_vectors=1,
            all_possible_ordered_AB_pairs=str(possible_ab),ABC_triplets_exact_count='not_enumerated',attempts=1,registered_events=1,failed_attempts=0,
            failure_reasons='{}',exhaustive_events=False,registration_stage='capacity_completion_v3',exact_max_m_AB=r['exact_max_m_AB'],exact_max_m_ABC_within_coarse=m))
    assert not set(old_events.event_id)&{e['event_id'] for e in events}
    save(OUT/'CAPACITY_V3_REQUESTS.json.gz',dict(seed=SEED,stage='capacity_completion_v3',requests=list(requests.values())))
    csv(OUT/'ABC_EVENTS_CAPACITY_V3.csv.gz',pd.DataFrame(events));csv(OUT/'ABC_EVENT_COVERAGE_CAPACITY_V3.csv',pd.DataFrame(ledger))
    files=['ENDPOINT_REQUESTS.json.gz','ABC_EVENTS.csv.gz','ABC_EVENT_COVERAGE.csv','CONFIG_MEMBERSHIP.csv.gz','DESIGN_FREEZE.json']
    receipt=dict(previous_endpoints=len(old_keys),previous_events=len(old_events),added_events=len(events),added_unique_endpoint_sets=len(requests),
        final_endpoints=len(old_keys)+len(requests),final_events=len(old_events)+len(events),
        metadata_maxima_opportunities=len(maxima),previously_unfilled_maxima=len(missing),
        all_original_events_and_failed_attempts_preserved=True,configuration_samples_unchanged=True,
        selection='Only labels, capacities, worker IDs, n and m. Deterministic feasible X/Y, a reserved outside worker, then Z maximizes class-count change under unchanged parents.',
        knowledge_boundary='Local mechanism previews had already been inspected. This correction was triggered exclusively by the metadata capacity ledger; no quality or geometry was read by this script.',
        pre_apply_sha256={name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in files},applied=False)
    save(OUT/'DESIGN_CAPACITY_AMENDMENT_V3.json',receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True)


def apply():
    receipt=read(OUT/'DESIGN_CAPACITY_AMENDMENT_V3.json')
    if receipt['applied']:raise ValueError('already applied')
    for name,expected in receipt['pre_apply_sha256'].items():
        if hashlib.sha256((OUT/name).read_bytes()).hexdigest()!=expected:raise ValueError(('changed pre-amendment input',name))
    backup=OUT/'runtime/capacity_pre_v3';backup.mkdir(parents=True,exist_ok=True)
    for name in ('ENDPOINT_REQUESTS.json.gz','ABC_EVENTS.csv.gz','ABC_EVENT_COVERAGE.csv','DESIGN_FREEZE.json'):(backup/name).write_bytes((OUT/name).read_bytes())
    requests=read(OUT/'ENDPOINT_REQUESTS.json.gz');requests['requests'].extend(read(OUT/'CAPACITY_V3_REQUESTS.json.gz')['requests']);save(OUT/'ENDPOINT_REQUESTS.json.gz',requests)
    for dest,extra in [('ABC_EVENTS.csv.gz','ABC_EVENTS_CAPACITY_V3.csv.gz'),('ABC_EVENT_COVERAGE.csv','ABC_EVENT_COVERAGE_CAPACITY_V3.csv')]:
        old=pd.read_csv(OUT/dest,keep_default_na=False,dtype={'all_possible_ordered_AB_pairs':str});new=pd.read_csv(OUT/extra,keep_default_na=False,dtype={'all_possible_ordered_AB_pairs':str})
        csv(OUT/dest,pd.concat([old,new],ignore_index=True))
    freeze=read(OUT/'DESIGN_FREEZE.json');freeze['all_requested_unique_sets']=receipt['final_endpoints'];freeze['additional_unique_sets']=receipt['final_endpoints']-freeze['complete_near_census_sets'];freeze['matched_ABC_events']=receipt['final_events']
    freeze['capacity_completion_v3']=dict(added_events=receipt['added_events'],added_endpoint_sets=receipt['added_unique_endpoint_sets'],scope='21 previously unfilled mode-specific exact maxima; append-only metadata construction')
    for path in list(freeze['frozen_inputs_outputs_sha256']):freeze['frozen_inputs_outputs_sha256'][path]=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
    save(OUT/'DESIGN_FREEZE.json',freeze)
    receipt['applied']=True;receipt['post_apply_sha256']={name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in receipt['pre_apply_sha256']};save(OUT/'DESIGN_CAPACITY_AMENDMENT_V3.json',receipt)
    print(json.dumps(dict(final_endpoints=receipt['final_endpoints'],final_events=receipt['final_events'],applied=True)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args()
    apply() if a.apply else prepare()
