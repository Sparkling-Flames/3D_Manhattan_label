"""Current LOBO class composition on saved v2.1 random paths; no fusion or scoring.
Run from repository root. Inputs are immutable paths listed in NATURAL_SOURCE_POOLS.csv.
Outputs preserve all randomized path repetitions and use paired images/buildings.
"""
from pathlib import Path
import argparse,json,gzip,hashlib,warnings,time
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
METHODS={'TARGET_DSTRUCT_K3':'C3','RFUSE_GEOM_K2':'C2','OPPJOINT_K3':'C3','OPPJOINT_K4':'C4'}
STRATA={'old24','prior_new24','new104A','new104B','new_space256'}
METRICS=['B8L2','D10','IoU3D100','floor_turn5_n','floor_redundant5_n','floor_short_edge_03_n','nodes','boundary_loss','omission','extension']
THRESHOLDS=(80,90)

def save(name,d):
    f=OUT/name;f.parent.mkdir(parents=True,exist_ok=True)
    data=d.to_csv(index=False).encode('utf-8-sig')
    f.write_bytes(gzip.compress(data,mtime=0) if f.suffix=='.gz' else data)

def truth(s): return s.fillna(False).astype(str).str.lower().isin(['true','1','1.0'])
def avg(x):
    a=np.asarray(x,float);return float(np.nanmean(a)) if np.isfinite(a).any() else np.nan

def quant(x,p):
    a=np.asarray(x,float);a=a[np.isfinite(a)];return float(np.quantile(a,p)) if len(a) else np.nan

def bootstrap(v,seed=20261104):
    a=np.asarray(v,float);a=a[np.isfinite(a)]
    if len(a)<2:return (np.nan,np.nan)
    rng=np.random.default_rng(seed);b=np.mean(rng.choice(a,size=(2000,len(a)),replace=True),axis=1)
    return tuple(np.quantile(b,[.025,.975]))

def summarize(effects,groupcols,by=['metric'],name='SUMMARY.csv'):
    rows=[]
    for keys,g in effects.groupby(groupcols+by,dropna=False,sort=True):
        if not isinstance(keys,tuple): keys=(keys,)
        meta=dict(zip(groupcols+by,keys));g=g[np.isfinite(g.effect)]
        if not len(g):continue
        images=g.groupby(['image','building'],dropna=False).effect.mean().reset_index()
        bs=images.groupby('building').effect.mean();ci=bootstrap(bs.values)
        vals=images.effect.values;bvals=bs.values
        loo=(bvals.sum()-bvals)/(len(bvals)-1) if len(bvals)>1 else np.array([np.nan])
        rows.append(dict(meta,images=len(images),buildings=len(bs),mean_image=avg(vals),median_image=quant(vals,.5),
            p10_image=quant(vals,.1),p90_image=quant(vals,.9),positive_images=int((vals>1e-10).sum()),
            negative_images=int((vals<-1e-10).sum()),tie_images=int((np.abs(vals)<=1e-10).sum()),
            mean_building=avg(bvals),building_bootstrap_low=ci[0],building_bootstrap_high=ci[1],
            leave_one_building_low=avg([np.nanmin(loo)]) if len(bs)>1 else np.nan,
            leave_one_building_high=avg([np.nanmax(loo)]) if len(bs)>1 else np.nan))
    z=pd.DataFrame(rows);save(name,z);return z

def main():
    start=time.time();inventory=pd.read_csv(OUT/'NATURAL_SOURCE_POOLS.csv')
    rawpath=ROOT/'research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz'
    raw=pd.read_csv(rawpath,low_memory=False)
    raw=raw[raw.scope.eq('primary')&raw.layer.eq('ordinary_manual')&raw.condition.eq('manual')]
    labels=pd.read_csv(ROOT/'research/workers/current_class_interpretation_20261104/basis/WORKER_LABELS_ALL_LOBO.csv.gz')
    labels=labels[labels.method.isin(METHODS)&truth(labels.known)&labels.heldout_building.ne('ALL')]
    lmaps={(m,b):dict(zip(g.worker_id,g.class_id)) for (m,b),g in labels.groupby(['method','heldout_building'])}
    rawgroups={p:g for p,g in raw.groupby('pool_id')}
    audit=[];stats=[];effects=[];curvestats=[];curveeffects=[];pointstats=[];pointeffects=[];pathrows=[]
    teamkeys=set()
    for ii,r in enumerate(inventory.itertuples(),1):
        source=ROOT/r.path
        d=pd.read_csv(source,low_memory=False)
        allstrata='|'.join(sorted(d.stratum.unique()))
        d=d[d.stratum.isin(STRATA)].copy()
        d['path_key']=d.stratum.astype(str)+'::'+d.path_id.astype(str)
        assert d.groupby('path_key').k.nunique().eq(r.pool_n).all(),(r.pool_id,'incomplete path')
        assert d.path_key.nunique()==256,(r.pool_id,d.path_key.nunique(),allstrata)
        assert not d.duplicated(['path_key','k']).any()
        ps=sorted(d.path_key.unique());n=int(r.pool_n);ks=np.arange(1,n+1)
        teamkeys.update(d.team_key.unique())
        Q=d.pivot(index='path_key',columns='k',values='B8L2').reindex(index=ps,columns=ks).to_numpy(float)
        D=d.pivot(index='path_key',columns='k',values='D10').reindex(index=ps,columns=ks).to_numpy(float)
        workers=d.pivot(index='path_key',columns='k',values='member_workers').reindex(index=ps,columns=ks)
        gr=rawgroups[r.pool_id]
        assert gr.worker_id.nunique()==n,(r.pool_id,len(gr),n)
        assert gr.object_id.nunique()==n
        objtime=dict(zip(gr.object_id,pd.to_numeric(gr.source_active_time_seconds,errors='coerce')))
        ts=gr.time_source.dropna().unique()
        legal_time=len(ts)==1 and len(gr.time_source.dropna())==n and np.isfinite(list(objtime.values())).all() and min(objtime.values())>0
        tsource=str(ts[0]) if legal_time else 'not_same_source_complete_pool'
        times={}
        if legal_time:
            for row in d[['member_object_ids','source_time_total_seconds','k']].drop_duplicates('member_object_ids').itertuples(index=False):
                ids=str(row.member_object_ids).split('|');assert len(ids)==row.k
                assert all(x in objtime for x in ids),(r.pool_id,'object join')
                times[row.member_object_ids]=sum(objtime[x] for x in ids)
            d['legal_time']=d.member_object_ids.map(times)
            T=d.pivot(index='path_key',columns='k',values='legal_time').reindex(index=ps,columns=ks).to_numpy(float)
            assert np.all(np.diff(T,axis=1)>0)
            time_max_abs_error=float(np.nanmax(np.abs(d.legal_time-pd.to_numeric(d.source_time_total_seconds,errors='coerce'))))
        else:T=np.full_like(Q,np.nan);time_max_abs_error=np.nan
        meta=dict(pool_id=r.pool_id,image=r.image,building=r.building,difficulty=r.difficulty,pool_n=n,
                  geometric_challenge=bool(gr.geometric_challenge.iloc[0]),structural_condition=gr.structural_condition.iloc[0],
                  time_source=tsource,source_path=r.path)
        audit.append(dict(meta,paths=256,rows=len(d),raw_strata=allstrata,legal_same_source_time=legal_time,time_max_abs_error=time_max_abs_error,
                          q_missing_n3_plus=int(np.isnan(Q[:,2:]).sum()),unique_teams=int(d.team_key.nunique())))
        # Fixed-n conditional association uses group membership at that same n.
        for method,high in METHODS.items():
            lm=lmaps.get((method,r.building),{})
            for k in (6,10,14,20):
                if k>n:continue
                sets=workers[k].fillna('').str.split('|').tolist()
                labs=[[lm.get(w,'unknown') for w in ss] for ss in sets]
                allknown=np.array([all(x!='unknown' for x in ll) for ll in labs])
                has=np.array([high in ll for ll in labs])
                cnt=np.array([ll.count(high) for ll in labs])
                dd=d[d.k.eq(k)].set_index('path_key').reindex(ps)
                for minarm in (8,16):
                    nums=[int((allknown & (has==g)).sum()) for g in (0,1)]
                    if min(nums)<minarm:continue
                    pp=[]
                    for group in (0,1):
                        take=allknown&(has==group);sub=dd.loc[take]
                        base=dict(meta,method=method,highest_class=high,k=k,min_arm_paths=minarm,group=group,paths=int(take.sum()),
                                  mean_highest_class_count=avg(cnt[take]))
                        vals={m:avg(pd.to_numeric(sub[m],errors='coerce')) for m in METRICS if m in sub}
                        vals['score_available']=float(np.isfinite(Q[take,k-1]).mean())
                        vals['Q_p10']=quant(Q[take,k-1],.1)
                        if legal_time:vals['recorded_time_seconds']=avg(T[take,k-1])
                        for th in THRESHOLDS:vals[f'Q_ge{th}']=float((Q[take,k-1]>=th).mean())
                        pp.append(vals)
                        pointstats.extend(dict(base,metric=m,value=v) for m,v in vals.items())
                    pointeffects.extend(dict(meta,method=method,highest_class=high,k=k,min_arm_paths=minarm,paths_without=nums[0],paths_with=nums[1],
                                              metric=m,without_value=pp[0][m],with_value=pp[1][m],effect=pp[1][m]-pp[0][m]) for m in pp[0])
            # Landmark path comparison, never classify on any score or later prefix.
            if n<20:continue
            for anchor in (6,10):
                sets=workers[anchor].fillna('').str.split('|').tolist()
                labs=[[lm.get(w,'unknown') for w in ss] for ss in sets]
                allknown=np.array([all(x!='unknown' for x in ll) for ll in labs])
                has=np.array([high in ll for ll in labs]);idx=np.arange(anchor-1,20);K=ks[idx]
                qq=Q[:,idx];dd=D[:,idx];tt=T[:,idx];vv=np.isfinite(qq)
                complete=vv.all(1)
                vmean=np.divide(np.nansum(qq,axis=1),vv.sum(1),out=np.full(256,np.nan),where=vv.sum(1)>0)
                pdict={'score_available_fraction':vv.mean(1),'Q_mean_valid_prefixes':vmean,
                       'Q_mean_complete_paths':np.where(complete,qq.mean(1),np.nan),'complete_path':complete.astype(float),
                       'Q20':Q[:,19],'D10_20':D[:,19],
                       'final_pool_score_Q':Q[:,-1], 'Q20_minus_final_pool_Q':Q[:,19]-Q[:,-1]}
                for th in THRESHOLDS:
                    hit=qq>=th;ever=np.maximum.accumulate(hit,axis=1);sustain=np.minimum.accumulate(hit[:,::-1],axis=1)[:,::-1]
                    reached=hit.any(1);firstidx=hit.argmax(1)
                    sustained=sustain.any(1);firstsidx=sustain.argmax(1)
                    pdict[f'ever_Q{th}_by20']=reached.astype(float)
                    pdict[f'sustained_Q{th}_from_anchor']=sustain[:,0].astype(float)
                    pdict[f'first_Q{th}_n_given_reached']=np.where(reached,K[firstidx],np.nan)
                    pdict[f'first_sustained_Q{th}_n_given_reached']=np.where(sustained,K[firstsidx],np.nan)
                    pdict[f'ever_Q{th}_prefix_probability_area']=ever.mean(1)
                    pdict[f'sustained_Q{th}_prefix_probability_area']=sustain.mean(1)
                    if legal_time:
                        pdict[f'first_Q{th}_recorded_seconds_given_reached']=np.where(reached,tt[np.arange(256),firstidx],np.nan)
                        for frac in (.25,.5,.75):
                            budget=T[:,-1]*frac
                            pdict[f'ever_Q{th}_by_{int(frac*100)}pct_full_recorded_labor']=((tt<=budget[:,None])&hit).any(1).astype(float)
                    # pointwise prefix process output, all paths remain denominators.
                    for jj,k in enumerate(K):
                        for minarm in (8,16):
                            nums=[int((allknown&(has==g)).sum()) for g in (0,1)]
                            if min(nums)<minarm:continue
                            pairs=[]
                            for group in (0,1):
                                take=allknown&(has==group)
                                vals={f'ever_Q{th}':avg(ever[take,jj]),f'sustained_Q{th}_through20':avg(sustain[take,jj])}
                                pairs.append(vals)
                                curvestats.extend(dict(meta,method=method,highest_class=high,anchor=anchor,min_arm_paths=minarm,k=int(k),
                                                       group=group,paths=int(take.sum()),metric=m,value=v) for m,v in vals.items())
                            curveeffects.extend(dict(meta,method=method,highest_class=high,anchor=anchor,min_arm_paths=minarm,k=int(k),
                                paths_without=nums[0],paths_with=nums[1],metric=m,without_value=pairs[0][m],with_value=pairs[1][m],
                                effect=pairs[1][m]-pairs[0][m]) for m in pairs[0])
                close=np.abs(qq-Q[:,-1,None])<=2
                pdict['ever_within2_finalQ_by20']=close.any(1).astype(float)
                pdict['sustained_within2_finalQ_from_anchor']=close.all(1).astype(float)
                for jj,k in enumerate(K):
                    for minarm in (8,16):
                        nums=[int((allknown&(has==g)).sum()) for g in (0,1)]
                        if min(nums)<minarm:continue
                        pairs=[]
                        for group in (0,1):
                            take=allknown&(has==group)
                            vals={'Q':avg(qq[take,jj]),'D10':avg(dd[take,jj]),'Q_p10':quant(qq[take,jj],.1),'score_available':avg(vv[take,jj])}
                            if legal_time:vals['recorded_seconds']=avg(tt[take,jj])
                            pairs.append(vals)
                            curvestats.extend(dict(meta,method=method,highest_class=high,anchor=anchor,min_arm_paths=minarm,k=int(k),
                                group=group,paths=int(take.sum()),metric=m,value=v) for m,v in vals.items())
                        curveeffects.extend(dict(meta,method=method,highest_class=high,anchor=anchor,min_arm_paths=minarm,k=int(k),
                            paths_without=nums[0],paths_with=nums[1],metric=m,without_value=pairs[0][m],with_value=pairs[1][m],
                            effect=pairs[1][m]-pairs[0][m]) for m in pairs[0])
                for minarm in (8,16):
                    nums=[int((allknown&(has==g)).sum()) for g in (0,1)]
                    if min(nums)<minarm:continue
                    for m,v in pdict.items():
                        val=[]
                        for group in (0,1):
                            take=allknown&(has==group);x=np.asarray(v)[take]
                            val.append(avg(x))
                            stats.append(dict(meta,method=method,highest_class=high,anchor=anchor,min_arm_paths=minarm,group=group,
                                              paths=int(take.sum()),valid_paths=int(np.isfinite(x).sum()),metric=m,value=avg(x)))
                        effects.append(dict(meta,method=method,highest_class=high,anchor=anchor,min_arm_paths=minarm,
                                            paths_without=nums[0],paths_with=nums[1],metric=m,without_value=val[0],with_value=val[1],effect=val[1]-val[0]))
                # one row per registered all-known path for audit, each anchor/method recorded once.
                for i in np.flatnonzero(allknown):
                    pathrows.append(dict(pool_id=r.pool_id,image=r.image,building=r.building,difficulty=r.difficulty,pool_n=n,
                        method=method,highest_class=high,anchor=anchor,path_key=ps[i],highest_present=int(has[i]),
                        time_source=tsource,**{m:float(v[i]) for m,v in pdict.items()}))
        if ii%10==0 or ii==len(inventory): print('processed',ii,'/',len(inventory),'seconds',round(time.time()-start,1),flush=True)
    save('NATURAL_INPUT_VALIDATION.csv',pd.DataFrame(audit))
    save('PATH_OUTCOMES.csv.gz',pd.DataFrame(pathrows))
    save('LANDMARK_IMAGE_GROUP_METRICS.csv.gz',pd.DataFrame(stats));e=pd.DataFrame(effects);save('LANDMARK_IMAGE_PAIRED_EFFECTS.csv.gz',e)
    c=pd.DataFrame(curveeffects);save('LANDMARK_CURVE_IMAGE_PAIRED_EFFECTS.csv.gz',c);save('LANDMARK_CURVE_GROUP_METRICS.csv.gz',pd.DataFrame(curvestats))
    f=pd.DataFrame(pointeffects);save('FIXED_N_IMAGE_PAIRED_EFFECTS.csv.gz',f);save('FIXED_N_GROUP_METRICS.csv.gz',pd.DataFrame(pointstats))
    groups=['method','highest_class','anchor','min_arm_paths']
    non_time=e[~e.metric.str.contains('recorded|labor')]
    summarize(non_time,groups,name='LANDMARK_ALL_SUMMARY.csv')
    summarize(non_time,groups+['difficulty'],name='LANDMARK_DIFFICULTY_SUMMARY.csv')
    summarize(non_time,groups+['geometric_challenge'],name='LANDMARK_GEOMETRIC_CHALLENGE_SUMMARY.csv')
    summarize(e[e.metric.str.contains('recorded|labor')],groups+['time_source'],name='LANDMARK_RECORDED_LABOR_SUMMARY.csv')
    summarize(c[~c.metric.eq('recorded_seconds')],groups+['k'],name='LANDMARK_CURVE_SUMMARY.csv')
    summarize(c[c.metric.eq('recorded_seconds')],groups+['k','time_source'],name='LANDMARK_RECORDED_LABOR_CURVE_SUMMARY.csv')
    summarize(c[~c.metric.eq('recorded_seconds')],groups+['k','difficulty'],name='LANDMARK_CURVE_DIFFICULTY_SUMMARY.csv')
    summarize(f[~f.metric.eq('recorded_time_seconds')],['method','highest_class','k','min_arm_paths'],name='FIXED_N_SUMMARY.csv')
    summarize(f[f.metric.eq('recorded_time_seconds')],['method','highest_class','k','min_arm_paths','time_source'],name='FIXED_N_RECORDED_LABOR_SUMMARY.csv')
    summarize(f[~f.metric.eq('recorded_time_seconds')],['method','highest_class','k','min_arm_paths','difficulty'],name='FIXED_N_DIFFICULTY_SUMMARY.csv')
    (OUT/'NATURAL_TEAM_KEYS.json.gz').write_bytes(gzip.compress(json.dumps(sorted(teamkeys)).encode(),mtime=0))
    receipt=dict(source_commit='48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b',pools=len(inventory),images=len(inventory),paths_per_pool=256,
        primary_scope='primary ordinary Manual',pool_n_ge20=int(inventory.pool_n.ge(20).sum()),methods=METHODS,
        pooled256_strata=sorted(STRATA),excluded_strata=['prior_focus48'],new_fusions=0,new_scores=0,new_teams=0,
        time_source_homogeneous_pool_required=True,thresholds=list(THRESHOLDS),thresholds_are_descriptive=True,
        classification='current held-out-building labels; presence in first6/first10; group fixed throughout curve',
        missingQ='never converted to Q=0; unavailable prefix cannot certify achievement',
        support_rule='same-image both landmark arms have >=16 registered known-label paths; >=8 sensitivity',
        bootstrap_unit='building,2000 resamples, seed20261104',new_priority_policy_claim=False,
        elapsed_seconds=round(time.time()-start,1))
    (OUT/'NATURAL_ANALYSIS_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps(receipt,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
