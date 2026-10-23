#!/usr/bin/env python3
"""Fixed-design population stability, implemented anew on saved original values.

No fusion, no new member order, no rescore, no class adjustment. Whole natural
paths are sampled within each fixed pool. All priority policies retain their
paired natural base path and share one resampling index within a pool. Building
resampling is separate and keeps the observed path set fixed.
"""
from pathlib import Path
import argparse, hashlib, json, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore',category=RuntimeWarning)
NAT=['Q_mean','Q_p10','Q_sd_ddof1','D10_mean','score_unavailable_rate','score_failure_nonpolicy_rate','incomplete_nonpolicy_rate','source_labor_mean_seconds','Q80_reached_rate','Q90_reached_rate']
POL=['paired_Q_delta','Q_p10_delta_common','Q_sd_delta_common_ddof1','paired_D10_delta','score_failure_delta','incomplete_delta','Q_loss_gt5_rate','source_time_logratio','QT_Q_delta','QT_time_logratio','Q80_reached_delta','Q90_reached_delta']
METADATA=['pool_id','image','building','condition','layer','difficulty','pool_n']
KS=np.arange(1,21)

def seed_for(seed,kind,pool):
    return int.from_bytes(hashlib.sha256(f'{seed}|{kind}|{pool}'.encode()).digest()[:8],'little')

def asnum(s):
    if s.dtype==bool:return s.astype(float)
    if s.dtype==object:
        s=s.replace({'True':1,'False':0,'true':1,'false':0})
    return pd.to_numeric(s,errors='coerce')

def q10(a):
    # NumPy linear quantile, vectorized for many small samples with NaNs.
    # Sorting places NaNs after valid values; the interpolation rank uses only
    # the valid count. This avoids a Python-level loop per bootstrap/k cell.
    s=np.sort(a,axis=1);count=np.isfinite(a).sum(axis=1)
    rank=np.maximum(count-1,0)*.1;lo=np.floor(rank).astype(int);hi=np.ceil(rank).astype(int)
    lv=np.take_along_axis(s,lo[:,None,:],axis=1)[:,0,:]
    hv=np.take_along_axis(s,hi[:,None,:],axis=1)[:,0,:]
    return np.where(count>0,lv+(hv-lv)*(rank-lo),np.nan)

def nat_stats(d):
    q=d['B8L2'];out=[np.nanmean(q,1),q10(q),np.nanstd(q,1,ddof=1),np.nanmean(d['D10'],1),np.mean(~np.isfinite(q),1),np.mean(d['score_failure_nonpolicy'],1),np.mean(d['incomplete_nonpolicy'],1),np.nanmean(d['source_time_total_seconds'],1),np.mean(q>=80,1),np.mean(q>=90,1)]
    return np.stack(out,axis=-1)

def pol_stats(n,p):
    good=np.isfinite(n['B8L2'])&np.isfinite(p['B8L2'])
    nq=np.where(good,n['B8L2'],np.nan);pq=np.where(good,p['B8L2'],np.nan);dq=pq-nq
    nt=n['source_time_total_seconds'];pt=p['source_time_total_seconds'];tg=(nt>0)&(pt>0)
    lr=np.where(tg,np.log(pt/nt),np.nan);qt=tg&good
    out=[np.nanmean(dq,1),q10(pq)-q10(nq),np.nanstd(pq,1,ddof=1)-np.nanstd(nq,1,ddof=1),np.nanmean(p['D10']-n['D10'],1),np.mean(p['score_failure_nonpolicy']-n['score_failure_nonpolicy'],1),np.mean(p['incomplete_nonpolicy']-n['incomplete_nonpolicy'],1),np.nanmean(np.where(good,dq< -5,np.nan),1),np.nanmean(lr,1),np.nanmean(np.where(qt,dq,np.nan),1),np.nanmean(np.where(qt,lr,np.nan),1),np.mean((p['B8L2']>=80).astype(float)-(n['B8L2']>=80).astype(float),1),np.mean((p['B8L2']>=90).astype(float)-(n['B8L2']>=90).astype(float),1)]
    return np.stack(out,axis=-1)

def matrices(g,paths,ks):
    fields=['B8L2','D10','source_time_total_seconds','score_failure_nonpolicy','incomplete_nonpolicy']
    return {c:g.pivot(index='path_id',columns='k',values=c).reindex(index=paths,columns=ks).to_numpy(float) for c in fields}

def sampled(d,indices):return {k:v[indices] for k,v in d.items()}

def save(d,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    d.to_csv(path,index=False,compression='gzip' if path.suffix=='.gz' else None)

def scopes(meta):
    for (condition,layer),g in meta.groupby(['condition','layer'],sort=True):
        yield dict(condition=condition,layer=layer,difficulty='全部'),g
        if layer.startswith('ordinary'):
            for difficulty,h in g.groupby('difficulty',sort=True):
                yield dict(condition=condition,layer=layer,difficulty=difficulty),h

def aggregate(point,boot,meta,metrics,positions,axis,B,seed,extra=None):
    """Two estimands x two distinct resampling operations, no hierarchy mixing."""
    records=[];building_rows=[]
    for scope,g in scopes(meta):
        pools=list(g.pool_id);x=np.stack([point[p] for p in pools]);shape=x.shape[1:]
        buildings=list(sorted(g.building.unique()));gs=[];gc=[];gb=[]
        total=np.zeros((B,)+shape);count=np.zeros_like(total)
        btot=np.zeros_like(total);bcnt=np.zeros_like(total)
        for building in buildings:
            ids=list(g.index[g.building.eq(building)]);bp=list(g.loc[ids,'pool_id']);xx=np.stack([point[p] for p in bp])
            means=np.nanmean(xx,axis=0);gs.append(np.nansum(xx,axis=0));gc.append(np.isfinite(xx).sum(axis=0));gb.append(means)
            st=np.zeros_like(total);ct=np.zeros_like(total)
            for p in bp:
                z=boot[p];ok=np.isfinite(z);st+=np.where(ok,z,0);ct+=ok
            total+=st;count+=ct
            bz=np.divide(st,ct,out=np.full_like(st,np.nan),where=ct>0);ok=np.isfinite(bz);btot+=np.where(ok,bz,0);bcnt+=ok
            for j,pos in enumerate(positions):
                for k,m in enumerate(metrics):
                    building_rows.append({**scope,**(extra or {}),'building':building,axis:pos,'metric':m,'value':means[j,k],'observed_images':int(np.isfinite(xx[:,j,k]).sum()),'available_images':len(bp)})
        gsum=np.stack(gs).reshape(len(buildings),-1);gcount=np.stack(gc).reshape(len(buildings),-1);gmean=np.stack(gb).reshape(len(buildings),-1)
        rseed=seed_for(seed,'building',json.dumps({**scope,**(extra or {}),'axis':axis},sort_keys=True,ensure_ascii=False));rng=np.random.default_rng(rseed)
        w=rng.multinomial(len(buildings),np.ones(len(buildings))/len(buildings),size=B)
        numer=w@gsum;denom=w@gcount;imgb=np.divide(numer,denom,out=np.full_like(numer,np.nan),where=denom>0).reshape((B,)+shape)
        ok=np.isfinite(gmean);numer=w@np.nan_to_num(gmean);denom=w@ok.astype(float);bb=np.divide(numer,denom,out=np.full_like(numer,np.nan),where=denom>0).reshape((B,)+shape)
        paths_i=np.divide(total,count,out=np.full_like(total,np.nan),where=count>0);paths_b=np.divide(btot,bcnt,out=np.full_like(btot,np.nan),where=bcnt>0)
        points={'image_equal':np.nanmean(x,axis=0),'building_equal':np.nanmean(np.stack(gb),axis=0)}
        draws={('image_equal','path_resampling_fixed_images'):paths_i,('building_equal','path_resampling_fixed_images'):paths_b,('image_equal','building_resampling_fixed_paths'):imgb,('building_equal','building_resampling_fixed_paths'):bb}
        for (weight,uncertainty),z in draws.items():
            lows=np.nanquantile(z,.025,axis=0);highs=np.nanquantile(z,.975,axis=0)
            for j,pos in enumerate(positions):
                for k,m in enumerate(metrics):
                    vals=z[:,j,k];valid=np.isfinite(vals);xm=x[:,j,k];bm=np.stack(gb)[:,j,k]
                    records.append({**scope,**(extra or {}),'panel':'fixed_pool_N_ge_20',axis:pos,'metric':m,'weighting':weight,'resampling':uncertainty,'estimate':points[weight][j,k],'percentile_2_5':lows[j,k],'percentile_97_5':highs[j,k],'positive_draw_fraction':float(np.mean(vals[valid]>0)) if valid.any() else np.nan,'positive_image_fraction':float(np.mean(xm[np.isfinite(xm)]>0)) if np.isfinite(xm).any() else np.nan,'available_images':len(g),'observed_images':int(np.isfinite(xm).sum()),'available_buildings':len(buildings),'observed_buildings':int(np.isfinite(bm).sum()),'valid_bootstrap_draws':int(valid.sum()),'bootstrap_replicates':B,'building_seed':'u64:'+str(rseed) if uncertainty.startswith('building') else ''})
    return pd.DataFrame(records),pd.DataFrame(building_rows)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--replicates',type=int,default=2000);ap.add_argument('--seed',type=int,default=2026102307);ap.add_argument('--resume-policy',action='store_true');a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(a.input/'PREFIX_VALUES_COMPACT.csv.gz',low_memory=False);orders=pd.read_csv(a.input/'EXACT_ORDER_DESIGN.csv.gz',low_memory=False)
    assert len(d)==404082 and len(orders)==12398
    for c in ['B8L2','D10','source_time_total_seconds','source_time_known_n','score_failure_nonpolicy','incomplete_nonpolicy']:d[c]=asnum(d[c]).replace([np.inf,-np.inf],np.nan)
    d.loc[d.source_time_known_n.ne(d.k),'source_time_total_seconds']=np.nan
    fullmeta=d[METADATA].drop_duplicates('pool_id').sort_values('pool_id').reset_index(drop=True)
    meta=fullmeta[fullmeta.pool_n.ge(20)].reset_index(drop=True)
    nat=d[d.policy.eq('natural_random')&d.pool_id.isin(meta.pool_id)]
    point={};boot={};imrows=[];introws=[];seeds=[];raw_nat={};intervals=[(3,6),(6,10),(10,20),(3,20)]
    if not a.resume_policy:
        for i,(pool,g) in enumerate(nat.groupby('pool_id',sort=True)):
            paths=sorted(g.path_id.unique());assert len(paths)==24
            arr=matrices(g,paths,KS);raw_nat[pool]=arr;r=meta.set_index('pool_id').loc[pool].to_dict();r['pool_id']=pool
            p=nat_stats({c:v[None] for c,v in arr.items()})[0];point[pool]=p
            sd=seed_for(a.seed,'natural_path',pool);ix=np.random.default_rng(sd).integers(len(paths),size=(a.replicates,len(paths)))
            boot[pool]=nat_stats(sampled(arr,ix)).astype(np.float32);seeds.append(dict(pool_id=pool,kind='natural_whole_paths',seed=sd,paths=len(paths)))
            for j,k in enumerate(KS):
                vals=arr['B8L2'][:,j];imrows.append({**r,'k':k,'paths_attempted':len(paths),'quality_valid_paths':int(np.isfinite(vals).sum()),'unique_teams':g[g.k.eq(k)].team_key.nunique(),**dict(zip(NAT,p[j]))})
            for ka,kb in [(3,6),(6,10),(10,20),(3,20)]:
                qa=arr['B8L2'][:,ka-1];qb=arr['B8L2'][:,kb-1];good=np.isfinite(qa)&np.isfinite(qb);change=qb-qa
                introws.append({**r,'interval':f'{ka}_to_{kb}','paths_attempted':len(paths),'from_scored_paths':int(np.isfinite(qa).sum()),'to_scored_paths':int(np.isfinite(qb).sum()),'both_scored_paths':int(good.sum()),'gained_score_paths':int((~np.isfinite(qa)&np.isfinite(qb)).sum()),'lost_score_paths':int((np.isfinite(qa)&~np.isfinite(qb)).sum()),'paired_Q_delta':np.nanmean(change),'paired_Q_loss_gt5_rate':np.mean(change[good]<-5) if good.any() else np.nan,**{m+'_delta':p[kb-1,j]-p[ka-1,j] for j,m in enumerate(NAT)}})
            if i%20==0:print('natural_pools',i+1,flush=True)
        save(pd.DataFrame(imrows),a.out/'NATURAL_IMAGE_CURVES_REBUILT.csv.gz');save(pd.DataFrame(introws),a.out/'NATURAL_IMAGE_INTERVALS_REBUILT.csv')
        curves,build=aggregate(point,boot,meta,NAT,list(KS),'k',a.replicates,a.seed)
        save(curves,a.out/'NATURAL_CURVE_STABILITY.csv');save(build,a.out/'NATURAL_BUILDING_CURVES_REBUILT.csv')
        intervals=[(3,6),(6,10),(10,20),(3,20)];ip={p:np.stack([v[kb-1]-v[ka-1] for ka,kb in intervals]) for p,v in point.items()};ib={p:np.stack([v[:,kb-1]-v[:,ka-1] for ka,kb in intervals],axis=1) for p,v in boot.items()}
        ci,bi=aggregate(ip,ib,meta,NAT,[f'{ka}_to_{kb}' for ka,kb in intervals],'interval',a.replicates,a.seed)
        save(ci,a.out/'NATURAL_INTERVAL_STABILITY.csv');save(bi,a.out/'NATURAL_BUILDING_INTERVALS_REBUILT.csv')
        del boot,ib
    else:
        for f in ["NATURAL_CURVE_STABILITY.csv","NATURAL_INTERVAL_STABILITY.csv","NATURAL_IMAGE_CURVES_REBUILT.csv.gz","NATURAL_IMAGE_INTERVALS_REBUILT.csv"]:
            assert (a.out/f).exists(), f
        seeds.extend(dict(pool_id=p,kind="natural_whole_paths",seed=seed_for(a.seed,"natural_path",p),paths=24) for p in meta.pool_id)
    # Reweight and resample paired base paths, carrying all k on each selected path.
    pphase={};bphase={};policy_meta={};pkrows=[];pprows=[];paired_counts=[]
    policies=sorted(set(d.policy)-{'natural_random'})
    for pool in meta.pool_id:
        poolrows=d[d.pool_id.eq(pool)];nrows=poolrows[poolrows.policy.eq('natural_random')];N=int(meta.set_index('pool_id').loc[pool,'pool_n']);ks=np.arange(1,N+1);r=meta.set_index('pool_id').loc[pool].to_dict();r['pool_id']=pool
        bases=sorted(poolrows[~poolrows.policy.eq('natural_random')].base_path_id.unique());assert len(bases)==8
        na=matrices(nrows,bases,ks);sd=seed_for(a.seed,'paired_base_path',pool);ix=np.random.default_rng(sd).integers(len(bases),size=(a.replicates,len(bases)));seeds.append(dict(pool_id=pool,kind='paired_base_whole_paths',seed=sd,paths=len(bases)))
        for policy,g in poolrows[~poolrows.policy.eq('natural_random')].groupby('policy',sort=True):
            assert set(g.base_path_id)==set(bases)
            gg=g.drop(columns='path_id').rename(columns={'base_path_id':'path_id'});pa=matrices(gg,bases,ks)
            p=pol_stats({c:v[None] for c,v in na.items()},{c:v[None] for c,v in pa.items()})[0]
            z=pol_stats(sampled(na,ix),sampled(pa,ix))
            lo,hi=3,N//2;sel=(ks>=lo)&(ks<=hi)
            # Equal k within each image after equal path at each k.
            val=np.nanmean(p[sel],axis=0);bs=np.nanmean(z[:,sel],axis=1).astype(np.float32)
            pphase.setdefault(policy,{})[pool]=val[None];bphase.setdefault(policy,{})[pool]=bs[:,None]
            policy_meta.setdefault(policy,[]).append(r)
            for j,k in enumerate(ks):
                nq=na['B8L2'][:,j];pq=pa['B8L2'][:,j];good=np.isfinite(nq)&np.isfinite(pq)
                pkrows.append({**r,'policy':policy,'k':k,'paired_paths_attempted':len(bases),'paired_quality_valid':int(good.sum()),'natural_quality_valid':int(np.isfinite(nq).sum()),'priority_quality_valid':int(np.isfinite(pq).sum()),**dict(zip(POL,p[j]))})
            good=np.isfinite(na['B8L2'][:,sel])&np.isfinite(pa['B8L2'][:,sel]);pprows.append({**r,'policy':policy,'phase':'k3_to_floor_N_over_2','from_k':lo,'to_k':hi,'k_count':int(sel.sum()),'paired_paths':len(bases),'paired_prefix_attempts':int(good.size),'paired_quality_valid_prefixes':int(good.sum()),**dict(zip(POL,val))})
            paired_counts.append(dict(pool_id=pool,policy=policy,base_paths='|'.join(bases),seed=sd))
        if len(pprows)%80==0:print('policy_image_phases',len(pprows),flush=True)
    save(pd.DataFrame(pkrows),a.out/'POLICY_IMAGE_K_REBUILT.csv.gz');save(pd.DataFrame(pprows),a.out/'POLICY_EARLY_IMAGE_REBUILT.csv')
    allres=[];allb=[];common=set.intersection(*[set(v) for v in pphase.values()])
    for policy in policies:
        pm=pd.DataFrame(policy_meta[policy]);supports=[('own_available_pools',pm),('common_four_policy_pools',pm[pm.pool_id.isin(common)])]
        for support,pm0 in supports:
            ci,bb=aggregate(pphase[policy],bphase[policy],pm0,POL,['k3_to_floor_N_over_2'],'phase',a.replicates,a.seed,dict(policy=policy,policy_support=support))
            allres.append(ci);allb.append(bb)
    save(pd.concat(allres,ignore_index=True),a.out/'POLICY_EARLY_STABILITY.csv');save(pd.concat(allb,ignore_index=True),a.out/'POLICY_EARLY_BUILDING_REBUILT.csv')
    save(pd.DataFrame(seeds),a.out/'EXACT_BOOTSTRAP_SEEDS.csv');save(pd.DataFrame(paired_counts),a.out/'POLICY_PAIRED_PATH_SUPPORT.csv')
    coverage=fullmeta.groupby(['condition','layer','difficulty'],dropna=False).agg(all_pools=('pool_id','nunique'),all_buildings=('building','nunique')).reset_index();main=meta.groupby(['condition','layer','difficulty'],dropna=False).agg(N20_pools=('pool_id','nunique'),N20_buildings=('building','nunique')).reset_index();save(coverage.merge(main,how='left'),a.out/'SUPPORT_BY_LAYER_DIFFICULTY.csv')
    rec=dict(operation='fixed_saved_design_new_bootstrap_implementation',source_commit='e92abe8631d7f01dc192ee796b46f295ece37a6d',new_fusion=0,new_team_design=0,new_member_orders=0,new_scoring=0,replicates=a.replicates,master_seed=a.seed,natural_paths_per_main_pool=24,paired_base_paths_per_main_pool=8,natural_N20_pools=len(meta),natural_N20_buildings=int(meta.building.nunique()),policy_pools_by_policy={p:len(v) for p,v in pphase.items()},policy_common_four_pools=len(common),natural_k=list(map(int,KS)),intervals=[list(x) for x in intervals],policy_phase='3<=k<=floor(N/2)',q_p10='within_image_valid_path_quantile_numpy_linear',q_sd='within_image_valid_path_sample_standard_deviation_ddof1',failure_denominator='all_attempted_paths_k2_policy_defer_separate',quality_missing='remain_nan_never_zero_score',strategy_quality_support='natural_and_priority_both_scored_at_same_k',time='legacy_known_n_only_time_columns; run fix_time_semantics.py for same-kind QT' ,bootstrap_types=['whole_paths_within_each_fixed_image','whole_buildings_with_observed_paths_fixed'],interval_type='pointwise_percentile_95_not_simultaneous_band',path_and_building_uncertainty_not_combined=True)
    (a.out/'ANALYSIS_RECEIPT.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n');print(json.dumps(rec,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
