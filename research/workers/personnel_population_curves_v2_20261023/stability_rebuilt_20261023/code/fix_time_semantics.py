#!/usr/bin/env python3
"""Targeted correction of QT support; quality/path/fusion results stay fixed.

Each team must have all k recorded times, a positive total and one known time
semantics. A pair must use the same semantics on both sides. Summaries retain
the source kind; mixed teams remain observable but ineligible for QT claims.
"""
from pathlib import Path
import argparse,gzip,json,hashlib
import numpy as np
import pandas as pd
from rebuild_path_stability import aggregate,seed_for,save,asnum

MET=['QT_Q_delta_same_semantics','QT_log_time_ratio_same_semantics','QT_seconds_delta_same_semantics','QT_arithmetic_time_ratio_same_semantics','QT_Q_loss_gt5_rate_same_semantics','QT_valid_pair_fraction','time_valid_pair_fraction']
M=['pool_id','image','building','condition','layer','difficulty','pool_n']

def make_record_index(snapshot,path):
    s=json.load(gzip.open(snapshot,'rt'));rows=[]
    for pool in s['images']:
        for r in pool['records']:
            rows.append(dict(pool_id=pool['pool_id'],image=pool['meta']['image'],worker_id=r['worker_id'],object_id=r['object_id'],origin=r.get('origin'),time_source_kind=r.get('time_source_kind'),source_time_seconds=r.get('source_time_seconds')))
    d=pd.DataFrame(rows);assert not d.duplicated(['pool_id','worker_id']).any();save(d,path)
    return dict(path=str(snapshot),sha256=hashlib.sha256(Path(snapshot).read_bytes()).hexdigest(),records=len(d),pools=d.pool_id.nunique())

def metrics(n,p,allowed,ix):
    nq=n['B8L2'][ix];pq=p['B8L2'][ix];nt=n['time'][ix];pt=p['time'][ix];t=allowed[ix];q=t&np.isfinite(nq)&np.isfinite(pq)
    with np.errstate(divide='ignore',invalid='ignore'):
        ratio=pt/nt;log=np.log(ratio);dq=pq-nq
    cols=[np.nanmean(np.where(q,dq,np.nan),axis=1),np.nanmean(np.where(q,log,np.nan),axis=1),np.nanmean(np.where(q,pt-nt,np.nan),axis=1),np.nanmean(np.where(q,ratio,np.nan),axis=1),np.nanmean(np.where(q,dq< -5,np.nan),axis=1),np.mean(q,axis=1),np.mean(t,axis=1)]
    return np.stack(cols,axis=-1)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--snapshot',type=Path);ap.add_argument('--replicates',type=int,default=2000);ap.add_argument('--seed',type=int,default=2026102307);a=ap.parse_args();out=a.root/'results/time_semantics';out.mkdir(parents=True,exist_ok=True)
    record_path=a.root/'inputs/RECORD_TIME_SOURCE_INDEX.csv.gz';snapshot_receipt=make_record_index(a.snapshot,record_path) if a.snapshot else {'path':'inputs/RECORD_TIME_SOURCE_INDEX.csv.gz','source':'saved_exact_snapshot_projection'}
    rec=pd.read_csv(record_path,low_memory=False);lookup={(r.pool_id,r.worker_id):(r.source_time_seconds,r.time_source_kind) for r in rec.itertuples()}
    orders=pd.read_csv(a.root/'inputs/EXACT_ORDER_DESIGN.csv.gz',low_memory=False);d=pd.read_csv(a.root/'inputs/PREFIX_VALUES_COMPACT.csv.gz',low_memory=False)
    rows=[]
    for r in orders.itertuples():
        known=0;total=0.;kinds=set()
        for k,w in enumerate(r.worker_order.split('|'),1):
            t,kind=lookup[r.pool_id,w]
            if pd.notna(t) and np.isfinite(t):known+=1;total+=float(t);kinds.add(str(kind))
            kindstring='|'.join(sorted(kinds));eligible=known==k and total>0 and len(kinds)==1 and kindstring not in ['','nan','unknown','None']
            rows.append(dict(path_id=r.path_id,k=k,time_source_kinds=kindstring,recorded_time_eligible_same_semantics=eligible,known_n_rederived=known,total_seconds_rederived=total if known==k else np.nan))
    sem=pd.DataFrame(rows);assert len(sem)==404082 and not sem.duplicated(['path_id','k']).any();d=d.merge(sem,on=['path_id','k'],validate='one_to_one');assert (d.source_time_known_n==d.known_n_rederived).all()
    good=d.source_time_known_n.eq(d.k);err=np.abs(d.loc[good,'source_time_total_seconds']-d.loc[good,'total_seconds_rederived']);assert err.max()<1e-7
    save(d[['pool_id','path_id','base_path_id','policy','k','team_key','time_source_kinds','recorded_time_eligible_same_semantics','known_n_rederived','total_seconds_rederived']],a.root/'inputs/PREFIX_TIME_SEMANTICS.csv.gz')
    coverage=d.groupby(['condition','layer','policy'],dropna=False).agg(prefixes=('team_key','size'),known_full=('source_time_known_n',lambda x:0)).reset_index().drop(columns='known_full')
    c=d.assign(known_full=good,mixed_kind=d.time_source_kinds.str.contains(r'\|'),single_eligible=d.recorded_time_eligible_same_semantics).groupby(['condition','layer','policy'],dropna=False)[['known_full','mixed_kind','single_eligible']].sum().reset_index();coverage=coverage.merge(c,validate='one_to_one');save(coverage,out/'PREFIX_SEMANTICS_COVERAGE.csv')
    meta=d[M].drop_duplicates('pool_id');meta=meta[meta.pool_n>=20];d=d[d.pool_id.isin(meta.pool_id)]
    actual_kinds=sorted(rec.time_source_kind.dropna().unique());kinds=['all_pairs_matched_within_kind']+actual_kinds
    point={};boot={};pm={};imrows=[];countrows=[];eventrows=[]
    for pool,group in d.groupby('pool_id',sort=True):
        N=int(group.pool_n.iloc[0]);ks=np.arange(1,N+1);early=(ks>=3)&(ks<=N//2);nat=group[group.policy.eq('natural_random')];bases=sorted(group[group.policy.ne('natural_random')].base_path_id.unique());assert len(bases)==8
        ix=np.random.default_rng(seed_for(a.seed,'paired_base_path',pool)).integers(8,size=(a.replicates,8));one=np.arange(8)[None]
        def matrix(g,col):return g.pivot(index='path_id',columns='k',values=col).reindex(index=bases,columns=ks).to_numpy()
        nd={c:matrix(nat,col) for c,col in [('B8L2','B8L2'),('time','source_time_total_seconds'),('eligible','recorded_time_eligible_same_semantics'),('kind','time_source_kinds')]}
        r=group[M].iloc[0].to_dict()
        for policy,gg in group[group.policy.ne('natural_random')].groupby('policy'):
            pg=gg.drop(columns='path_id').rename(columns={'base_path_id':'path_id'});pdct={c:matrix(pg,col) for c,col in [('B8L2','B8L2'),('time','source_time_total_seconds'),('eligible','recorded_time_eligible_same_semantics'),('kind','time_source_kinds')]}
            allowed=nd['eligible'].astype(bool)&pdct['eligible'].astype(bool)&(nd['kind']==pdct['kind'])
            old=(nd['time']>0)&(pdct['time']>0);qgood=np.isfinite(nd['B8L2'])&np.isfinite(pdct['B8L2'])
            countrows.append({**r,'policy':policy,'phase':'k3_to_floor_N_over_2','prefix_attempts':int(old[:,early].size),'legacy_known_only_time_pairs':int(old[:,early].sum()),'legacy_known_only_QT_pairs':int((old[:,early]&qgood[:,early]).sum()),'same_semantics_time_pairs':int(allowed[:,early].sum()),'same_semantics_QT_pairs':int((allowed[:,early]&qgood[:,early]).sum()),'removed_mixed_or_unmatched_time_pairs':int((old[:,early]&~allowed[:,early]).sum())})
            for kind in kinds:
                mask=allowed if kind=='all_pairs_matched_within_kind' else allowed&(nd['kind']==kind)
                key=(policy,kind);p=metrics(nd,pdct,mask,one)[0];z=metrics(nd,pdct,mask,ix)
                pval=np.nanmean(p[early],axis=0);bval=np.nanmean(z[:,early],axis=1).astype(np.float32)
                point.setdefault(key,{})[pool]=pval[None];boot.setdefault(key,{})[pool]=bval[:,None];pm.setdefault(key,[]).append(r)
                valid=mask&qgood;imrows.append({**r,'policy':policy,'time_source_kind':kind,'phase':'k3_to_floor_N_over_2','from_k':3,'to_k':N//2,'attempted_prefixes':int(mask[:,early].size),'time_valid_prefixes':int(mask[:,early].sum()),'QT_valid_prefixes':int(valid[:,early].sum()),**dict(zip(MET,pval))})
            # Exact small audit for all early paired prefixes, preserving kinds,
            # keys and the actual reason for exclusion instead of imputing cost.
            nat_idx=nat.set_index(['path_id','k']);pg_idx=gg.set_index(['base_path_id','k'])
            for i,bid in enumerate(bases):
                for j in np.where(early)[0]:
                    k=int(ks[j]);nr=nat_idx.loc[bid,k];pr=pg_idx.loc[bid,k];qt=bool(allowed[i,j] and qgood[i,j])
                    eventrows.append(dict(pool_id=pool,image=r['image'],building=r['building'],condition=r['condition'],layer=r['layer'],policy=policy,base_path_id=bid,path_id=pr.path_id,k=k,natural_team_key=nr.team_key,priority_team_key=pr.team_key,natural_time_kind=nd['kind'][i,j],priority_time_kind=pdct['kind'][i,j],natural_recorded_eligible=bool(nd['eligible'][i,j]),priority_recorded_eligible=bool(pdct['eligible'][i,j]),same_semantics_time_pair=bool(allowed[i,j]),same_semantics_QT_pair=qt,natural_source_seconds=nd['time'][i,j] if allowed[i,j] else np.nan,priority_source_seconds=pdct['time'][i,j] if allowed[i,j] else np.nan,QT_Q_delta=(pdct['B8L2'][i,j]-nd['B8L2'][i,j]) if qt else np.nan))
        if len(countrows)%80==0:print('corrected_time_image_phases',len(countrows),flush=True)
    save(pd.DataFrame(countrows),out/'POLICY_MATCHED_TIME_SUPPORT.csv');save(pd.DataFrame(imrows),out/'SAME_SEMANTICS_QT_PER_IMAGE.csv');save(pd.DataFrame(eventrows),out/'SAME_SEMANTICS_EARLY_EXACT_PAIRS.csv.gz')
    common=set.intersection(*[set(v) for (policy,kind),v in point.items() if kind=='all_pairs_matched_within_kind']);allci=[];allb=[]
    for (policy,kind),pdict in point.items():
        met=pd.DataFrame(pm[(policy,kind)]);met=met[met.pool_id.isin(common)]
        # Report the all-attempt denominator even for kinds with no eligible
        # QT in a stratum; no-supported QT estimates remain NaN, never zero.
        ci,b=aggregate(pdict,boot[(policy,kind)],met,MET,['k3_to_floor_N_over_2'],'phase',a.replicates,a.seed,dict(policy=policy,policy_support='common_four_policy_pools',time_source_kind=kind));allci.append(ci);allb.append(b)
    save(pd.concat(allci,ignore_index=True),out/'SAME_SEMANTICS_QT_STABILITY.csv');save(pd.concat(allb,ignore_index=True),out/'SAME_SEMANTICS_QT_PER_BUILDING.csv')
    summary=dict(operation='targeted_time_semantics_correction_fixed_existing_paths',new_fusion=0,new_scoring=0,new_paths=0,source_snapshot=snapshot_receipt,original_time_rule='known_n_equals_k_only; mixed_semantics_may_be_included',corrected_team_rule='all_known_and_positive_total_and_one_known_semantic_kind',corrected_pair_rule='both_teams_eligible_and_same_kind',quality_rule='both_sides_scored_on_same_corrected_time_pair',master_seed=a.seed,replicates=a.replicates,exact_prefix_rows=len(sem),max_existing_vs_record_time_sum_error=float(err.max()),record_source_kinds=actual_kinds,early_policy_image_phases=len(countrows),early_exact_pair_rows=len(eventrows),original_Q_structure_path_estimates_unchanged=True,legacy_time_columns_retained_but_not_used_as_same_semantics_claim=True)
    (out/'CORRECTION_RECEIPT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
