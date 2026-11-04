"""Exact first-passage and sustained-target probabilities on existing K4 subset endpoints.
Uses the existing random-within-priority-group policies. Dynamic programming
preserves cross-prefix dependence, and validates every stored marginal. No new
teams, fusion, scoring, labels, or priority schemes are produced.
"""
from pathlib import Path
import json,gzip,hashlib
from math import comb
import pandas as pd
import numpy as np
from analyze_existing_natural_paths import save,summarize,truth
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[3]
BASE=ROOT/'research/workers/personnel_v21_reselection_20261029/composition/exact_small_pool_policies_OPPJOINT_K4'
END=ROOT/'research/workers/personnel_v21_reselection_20261029/additional_delivery/packages/03A/composition/other_targets_endpoints/ENDPOINT_SCALARS.csv.gz'
PATCH=ROOT/'research/fusion/manual_order_impact_20261104/endpoints/ENDPOINT_SCORES.csv'
RAW=ROOT/'research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz'

def weighted_quant(x,w,p):
    valid=np.isfinite(x)&(w>0);x=x[valid];w=w[valid]
    if not len(x):return np.nan
    assert np.max(w)-np.min(w)<1e-10
    return float(np.quantile(x,p))

def main():
    links=pd.read_csv(BASE/'POLICY_PREFIX_ENDPOINT_LINKS.csv.gz');groups=pd.read_csv(BASE/'HISTORICAL_ROLE_PRIORITY_GROUPS.csv.gz')
    e=pd.read_csv(END,low_memory=False);e=e[e.team_key.isin(links.team_key)].copy();assert len(e)==1081 and e.team_key.nunique()==1081
    patch=pd.read_csv(PATCH,low_memory=False);hits=patch[patch.team_key.isin(e.team_key)].copy();assert len(hits)==2
    old=e.set_index('team_key');new=old.copy();checks=[]
    for r in hits.itertuples():
        a=old.loc[r.team_key]
        fields=['pool_id','reference_id','reference_version']
        for f in fields:assert str(a[f])==str(getattr(r,f)),(r.team_key,f,a[f],getattr(r,f))
        for f in ['member_workers','member_object_ids']:assert set(str(a[f]).split('|'))==set(str(getattr(r,f)).split('|')),(r.team_key,f)
        assert pd.isna(a.B8L2) and pd.isna(r.automatic_B8L2)
        # Shared score/geometry columns replaced, identity and original labor untouched.
        patchfields=[c for c in hits.columns if c in old.columns and c not in ['team_key','pool_id','image','image_id','building','condition','k','reference_id','reference_version','data_release','member_workers','member_object_ids','source_time_total_seconds']]
        for f in patchfields:new.at[r.team_key,f]=getattr(r,f)
        checks.append(dict(team_key=r.team_key,pool_id=r.pool_id,reference_id=r.reference_id,reference_version=r.reference_version,
            member_workers=r.member_workers,member_object_ids=r.member_object_ids,automatic_Q=a.B8L2,assisted_Q=r.B8L2,
            automatic_D10=a.D10,assisted_D10=r.D10,original_support=bool(np.isfinite(a.B8L2)),expanded_support=bool(np.isfinite(r.B8L2)),
            source=str(PATCH.relative_to(ROOT)),identity_verified=True))
    save('K4_SMALL_POOL_ASSISTED_ENDPOINT_MATCHES.csv',pd.DataFrame(checks))
    raw=pd.read_csv(RAW,low_memory=False)
    od=raw[['object_id','source_active_time_seconds','time_source']].drop_duplicates()
    assert not od.duplicated('object_id').any()
    objtime=od.set_index('object_id').source_active_time_seconds.to_dict();objsource=od.set_index('object_id').time_source.to_dict()
    rows=[];process=[];support=[];marginalmax=0;endpointout=[]
    for pool,g in old.groupby('pool_id'):
        N=int(g.k.max());full=g[g.k.eq(N)];assert len(full)==1
        workers=str(full.member_workers.iloc[0]).split('|');assert len(workers)==N
        wi={w:i for i,w in enumerate(workers)};count=1<<N;bits=np.array([i.bit_count() for i in range(count)])
        stateof=lambda x:sum(1<<wi[w] for w in str(x).split('|'))
        masks=np.array([stateof(x) for x in g.member_workers]);assert len(set(masks))==sum(comb(N,n) for n in range(3,N+1))
        keys=dict(zip(masks,g.index));Qversions={}
        for version,tab in [('automatic',old),('manual_order_assisted',new)]:
            q=np.full(count,np.nan);d=np.full(count,np.nan)
            for s,key in keys.items():q[s]=tab.at[key,'B8L2'];d[s]=tab.at[key,'D10']
            Qversions[version]=(q,d)
        pg=groups[groups.pool_id.eq(pool)];meta0=pg.iloc[0]
        meta=dict(pool_id=pool,image=meta0.image,building=meta0.building,pool_n=N,reference_id=meta0.reference_id,scope=meta0.scope,
                  official_difficulty=meta0.official_difficulty,geometric_challenge=meta0.geometric_challenge)
        fullids=str(full.member_object_ids.iloc[0]).split('|');ww=str(full.member_workers.iloc[0]).split('|')
        # Derive individual times by matching original response worker within this pool/target, not string order.
        rr=raw[raw.pool_id.eq(pool)]
        worker_time=dict(zip(rr.worker_id,rr.source_active_time_seconds));sources=rr.time_source.dropna().unique()
        legal_time=len(rr)==N and rr.worker_id.nunique()==N and len(sources)==1 and rr.source_active_time_seconds.notna().all() and rr.source_active_time_seconds.gt(0).all()
        if legal_time:
            T=np.array([sum(worker_time[w] for w,i in wi.items() if s&(1<<i)) for s in range(count)])
            for s,key in keys.items():assert abs(T[s]-old.at[key,'recorded_time_total_seconds'])<1e-6,(key,'time mismatch')
            time_source=str(sources[0])
        else:T=np.full(count,np.nan);time_source='not_same_source_complete_pool'
        meta['time_source']=time_source
        support.append(dict(meta,endpoint_count=len(g),legal_time=legal_time,assisted_endpoint_hits=int(g.index.isin(hits.team_key).sum()),early_prefixes=max(N-3,0)))
        for policy in ['natural','more_turn_first','higher_Q_first','fast_first']:
            if policy=='natural':tiers=[workers]
            else:tiers=pg[pg.policy.eq(policy)].sort_values('priority_level').workers.str.split('|').tolist()
            assert sorted(sum(tiers,[]))==sorted(workers)
            tm=[sum(1<<wi[w] for w in tier) for tier in tiers]
            transitions={}
            for s in range(count-1):
                avail=next(mask&~s for mask in tm if mask&~s)
                choices=[s|(1<<i) for i in range(N) if avail&(1<<i)]
                transitions[s]=[(x,1/len(choices)) for x in choices]
            p=np.zeros(count);p[0]=1
            for s in range(count-1):
                for nxt,w in transitions[s]:p[nxt]+=p[s]*w
            assert abs(p[-1]-1)<1e-10
            ll=links[(links.pool_id.eq(pool))&links.policy.eq(policy)].set_index('team_key')
            for s,key in keys.items():
                expected=float(ll.at[key,'probability']) if key in ll.index else 0
                err=abs(p[s]-expected);marginalmax=max(marginalmax,err);assert err<1e-10,(pool,policy,key,p[s],expected)
            for version,(q,d) in Qversions.items():
                for k in range(3,N+1):
                    take=bits==k;pp=p[take];qq=q[take];dd=d[take];valid=np.isfinite(qq)
                    mass=float(pp[valid].sum())
                    vals={'Q':float(np.dot(pp[valid],qq[valid])/mass) if mass else np.nan,
                          'D10':float(np.dot(pp[np.isfinite(dd)],dd[np.isfinite(dd)])/pp[np.isfinite(dd)].sum()) if pp[np.isfinite(dd)].sum() else np.nan,
                          'score_available':mass,'failure':1-mass,'Q_p10':weighted_quant(qq,pp,.1)}
                    if legal_time:vals['recorded_seconds']=float(np.dot(pp,T[take]))
                    for th in (80,90):vals[f'Q_ge{th}']=float(pp[qq>=th].sum())
                    rows.extend(dict(meta,policy=policy,version=version,n=k,metric=m,value=v) for m,v in vals.items())
                for th in (80,90):
                    good=np.isfinite(q)&(q>=th)&(bits>=3)
                    never=np.zeros(count);never[0]=1;first=np.zeros(count)
                    for s in range(count):
                        if good[s]:first[s]=never[s];continue
                        if s<count-1:
                            for nxt,w in transitions[s]:never[nxt]+=never[s]*w
                    sust=np.zeros(count);sust[-1]=float(good[-1])
                    for s in range(count-2,-1,-1):
                        sust[s]=float(good[s])*sum(w*sust[nxt] for nxt,w in transitions[s])
                    for k in range(3,N+1):
                        evermass=float(first[bits<=k].sum());sustmass=float(np.dot(p[bits==k],sust[bits==k]))
                        rows.append(dict(meta,policy=policy,version=version,n=k,metric=f'ever_Q{th}',value=evermass))
                        rows.append(dict(meta,policy=policy,version=version,n=k,metric=f'sustained_Q{th}_through_fullN',value=sustmass))
                    reach=float(first.sum());earlyreach=float(first[bits<N].sum());base=dict(meta,policy=policy,version=version,threshold=th)
                    process.append(dict(base,metric='reach_by_fullN_probability',value=reach))
                    process.append(dict(base,metric='reach_before_fullN_probability',value=earlyreach))
                    process.append(dict(base,metric='first_hit_n_given_reached',value=float(np.dot(first,bits)/reach) if reach else np.nan))
                    process.append(dict(base,metric='first_hit_n_given_reached_before_fullN',value=float(np.dot(first[bits<N],bits[bits<N])/earlyreach) if earlyreach else np.nan))
                    if legal_time:
                        process.append(dict(base,metric='first_hit_recorded_seconds_given_reached',value=float(np.dot(first,T)/reach) if reach else np.nan))
                        for frac in (.25,.5,.75):
                            process.append(dict(base,metric=f'reach_by_{int(frac*100)}pct_full_recorded_labor',value=float(first[T<=T[-1]*frac].sum())))
        for version,tab in [('automatic',old),('manual_order_assisted',new)]:
            ee=tab.loc[g.index].copy();ee['version']=version;endpointout.append(ee.reset_index())
    save('K4_SMALL_POOL_ENDPOINTS_BOTH_VERSIONS.csv.gz',pd.concat(endpointout,ignore_index=True))
    save('K4_SMALL_POOL_SUPPORT.csv',pd.DataFrame(support))
    rr=pd.DataFrame(rows);save('K4_EXACT_PREFIX_CURVES.csv.gz',rr);pr=pd.DataFrame(process);save('K4_EXACT_FIRST_PASSAGE.csv',pr)
    keys=['pool_id','image','building','pool_n','reference_id','scope','official_difficulty','geometric_challenge','time_source','version','n','metric']
    nat=rr[rr.policy.eq('natural')][keys+['value']].rename(columns={'value':'natural_value'})
    diff=rr[rr.policy.ne('natural')].merge(nat,on=keys,validate='many_to_one');diff['effect']=diff.value-diff.natural_value
    save('K4_EXACT_PREFIX_PAIRED_EFFECTS.csv.gz',diff)
    assert diff[diff.n.eq(diff.pool_n)&~diff.metric.str.startswith('ever_')].effect.dropna().abs().max()<1e-10
    # Excludes n=N: exact same scope as the pre-existing policy table.
    early=diff[diff.n.lt(diff.pool_n)]
    pool=early.groupby(['policy','version','pool_id','image','building','time_source','metric'],dropna=False).effect.mean().reset_index()
    save('K4_EARLY_CURVE_POOL_EFFECTS.csv',pool)
    summarize(pool,['policy','version','time_source'],name='K4_EARLY_CURVE_SUMMARY.csv')
    pk=['pool_id','image','building','pool_n','reference_id','scope','official_difficulty','geometric_challenge','time_source','version','threshold','metric']
    pn=pr[pr.policy.eq('natural')][pk+['value']].rename(columns={'value':'natural_value'})
    pe=pr[pr.policy.ne('natural')].merge(pn,on=pk,validate='many_to_one');pe['effect']=pe.value-pe.natural_value
    save('K4_FIRST_PASSAGE_POOL_EFFECTS.csv',pe)
    summarize(pe[pe.pool_n.gt(3)],['policy','version','threshold','time_source'],name='K4_FIRST_PASSAGE_SUMMARY.csv')
    # Non-time quality aggregate includes all valid image supports, not time strata.
    summarize(pool[~pool.metric.eq('recorded_seconds')],['policy','version'],name='K4_EARLY_QUALITY_ALL_SUPPORT_SUMMARY.csv')
    summarize(pe[pe.pool_n.gt(3)&~pe.metric.str.contains('recorded')],['policy','version','threshold'],name='K4_FIRST_PASSAGE_QUALITY_ALL_SUPPORT_SUMMARY.csv')
    # Preserve common original quality support and isolate added endpoint support.
    change=[]
    for key,g in rr.groupby(['pool_id','policy','n','metric'],dropna=False):
        if len(g)!=2:continue
        z=g.set_index('version');a=z.loc['automatic'];b=z.loc['manual_order_assisted']
        change.append(dict(pool_id=key[0],image=a.image,building=a.building,policy=key[1],n=key[2],metric=key[3],
            automatic=a.value,assisted=b.value,delta=b.value-a.value))
    save('K4_MANUAL_ASSISTED_CONSUMER_CHANGES.csv',pd.DataFrame(change))
    receipt=dict(source_commit='48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b',method='OPPJOINT_K4',pools=20,
        existing_endpoints=1081,early_curve_pools=15,assisted_endpoint_hits=2,new_fusions=0,new_scores=0,
        dynamic_program='subset lattice; uniform next member within first remaining priority group',
        saved_marginal_parity_max_abs_error=marginalmax,fullN_endpoint_policy_equality=True,ever_hit_history_can_differ_at_fullN=True,p10_definition='linear finite-uniform quantile, matching original distribution tables',
        missingQ='never assigned numeric Q; cannot certify target passage',time_pool_homogeneity_required=True,
        official_thresholds=False,descriptive_thresholds=[80,90],current_adopted_reference_preserved=True)
    (OUT/'K4_EXACT_PROCESS_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));print(json.dumps(receipt,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
