"""从原前缀、精确顺序独立复算 R03 的曲线、重抽和共同时间域。"""
from pathlib import Path
import argparse
import json
import warnings
import numpy as np
import pandas as pd
from audit_same_room_rebuilt_20261023 import check


def distribution(q):
    """末轴是路径；直接使用有效样本的线性十分位数和样本标准差。"""
    count=np.isfinite(q).sum(-1);ordered=np.sort(q,axis=-1)
    rank=np.maximum(count-1,0)*.1;low=rank.astype(int);high=np.ceil(rank).astype(int)
    a=np.take_along_axis(ordered,low[...,None],axis=-1)[...,0]
    b=np.take_along_axis(ordered,high[...,None],axis=-1)[...,0]
    return np.stack([np.nanmean(q,-1),np.where(count,a+(b-a)*(rank-low),np.nan),np.nanstd(q,-1,ddof=1)],axis=-1)


def audit_common_pool_and_failures(root, out):
    """从前缀重新取四策略交集，失败使用共同时间域的全部尝试。"""
    out.mkdir(parents=True, exist_ok=True)
    checks=[]
    read=lambda p,**kw:pd.read_csv(root/p,low_memory=False,**kw)
    d=read('inputs/PREFIX_VALUES_COMPACT.csv.gz')
    sem=read('inputs/PREFIX_TIME_SEMANTICS.csv.gz')
    assert len(d)==len(sem)==404082
    keys=['pool_id','base_path_id','k']
    meta=['condition','layer','building','pool_id']
    policies=['joint_fast_first','joint_highq_first','structure_dominant_first','structure_moreturn_first']
    d=d.merge(sem[['path_id','k','time_source_kinds','recorded_time_eligible_same_semantics']],
              on=['path_id','k'],validate='one_to_one')
    natural=d[d.policy.eq('natural_random')]
    selected=d[d.policy.isin(policies)&d.pool_n.ge(20)&d.k.ge(3)&d.k.le(d.pool_n//2)]
    cols=keys+['B8L2','team_key','time_source_kinds','recorded_time_eligible_same_semantics',
               'score_failure_nonpolicy','incomplete_nonpolicy']
    x=selected.merge(natural[cols],on=keys,suffixes=('','_natural'),validate='many_to_one')
    assert not x.duplicated(keys+['policy']).any()
    x['Q_delta']=x.B8L2-x.B8L2_natural
    per_image=x.groupby(meta+['difficulty','policy','k']).Q_delta.mean().groupby(meta+['difficulty','policy']).mean().reset_index()
    common_pools=set.intersection(*[set(per_image.loc[per_image.policy.eq(p),'pool_id']) for p in policies])
    per_image=per_image[per_image.pool_id.isin(common_pools)]
    summary=[]
    expected=read('results/POLICY_EARLY_STABILITY.csv')
    expected=expected[expected.policy_support.eq('common_four_policy_pools')&expected.metric.eq('paired_Q_delta')&
                      expected.resampling.eq('path_resampling_fixed_images')&expected.difficulty.eq('全部')]
    for (condition,layer,policy),g in per_image.groupby(['condition','layer','policy']):
        b=g.groupby('building').Q_delta.mean()
        row=dict(condition=condition,layer=layer,policy=policy,policy_support='common_four_policy_pools',
                 pools=g.pool_id.nunique(),scored_images=int(g.Q_delta.notna().sum()),buildings=g.building.nunique(),
                 image_equal=g.Q_delta.mean(),building_equal=b.mean(),
                 positive_images=int(g.Q_delta.gt(0).sum()),negative_images=int(g.Q_delta.lt(0).sum()),
                 zero_images=int(g.Q_delta.eq(0).sum()),positive_image_fraction=g.Q_delta.dropna().gt(0).mean())
        exp=expected[expected.condition.eq(condition)&expected.layer.eq(layer)&expected.policy.eq(policy)]
        for weighting,field in [('image_equal','image_equal'),('building_equal','building_equal')]:
            r=exp[exp.weighting.eq(weighting)].iloc[0]
            check([row[field],row['scored_images'],row['buildings'],row['positive_image_fraction']],
                  [r.estimate,r.observed_images,r.observed_buildings,r.positive_image_fraction],
                  f'common_pool/{condition}/{layer}/{policy}/{weighting}',checks)
        summary.append(row)
    summary=pd.DataFrame(summary)
    assert summary[summary.layer.eq('ordinary_manual')].pools.eq(157).all()
    assert summary[summary.layer.eq('ordinary_semi')].pools.eq(21).all()
    summary.to_csv(out/'POLICY_COMMON_POOL_SUMMARY.csv',index=False)

    x['time_ok']=x.recorded_time_eligible_same_semantics & x.recorded_time_eligible_same_semantics_natural & x.time_source_kinds.eq(x.time_source_kinds_natural)
    x['quality_ok']=x.B8L2.notna() & x.B8L2_natural.notna()
    eligibility=x.groupby(keys).agg(policy_n=('policy','nunique'),time_common=('time_ok','all'),quality_common=('quality_ok','all')).reset_index()
    eligibility=eligibility[eligibility.policy_n.eq(4)]
    x=x.merge(eligibility,on=keys,validate='many_to_one')
    x['time_source_kind']=x.time_source_kinds
    support=[]
    for domain,z in [('four_policy_design',x),('four_policy_time_common',x[x.time_common]),
                     ('four_policy_QT_common',x[x.time_common & x.quality_common])]:
        z=z.copy()
        if domain=='four_policy_design':z['time_source_kind']='all_semantics_design_denominator'
        for (condition,layer,kind),g in z.groupby(['condition','layer','time_source_kind']):
            assert g.groupby(keys).size().eq(4).all()
            support.append(dict(condition=condition,layer=layer,time_source_kind=kind,domain=domain,
                                images=g.pool_id.nunique(),buildings=g.building.nunique(),
                                paired_base_k_units=len(g)//4,policy_rows=len(g)))
    support=pd.DataFrame(support)
    sk=['condition','layer','time_source_kind','domain'];sc=['images','buildings','paired_base_k_units','policy_rows']
    a=support.set_index(sk).sort_index();b=read('results/time_semantics/FOUR_POLICY_COMMON_TIME_SUPPORT.csv').set_index(sk).sort_index()
    assert a.index.equals(b.index)
    check(a[sc],b[sc],'common_time_domain_support',checks)
    support.to_csv(out/'COMMON_TIME_DOMAIN_SUPPORT.csv',index=False)

    x=x[x.time_common].copy()
    assert len(x)==20548 and x.groupby(keys).size().eq(4).all()
    x['natural_Q_unavailable']=x.B8L2_natural.isna().astype(float)
    x['priority_Q_unavailable']=x.B8L2.isna().astype(float)
    x['Q_unavailable_delta']=x.priority_Q_unavailable-x.natural_Q_unavailable
    for metric in ['score_failure_nonpolicy','incomplete_nonpolicy']:
        x['natural_'+metric]=x[metric+'_natural'].astype(float)
        x['priority_'+metric]=x[metric].astype(float)
        x[metric.replace('_nonpolicy','')+'_delta']=x['priority_'+metric]-x['natural_'+metric]
    group=['condition','layer','time_source_kind','policy']
    counts=x.groupby(group).agg(prefix_attempts=('team_key','size'),natural_failed=('natural_score_failure_nonpolicy','sum'),
                               priority_failed=('priority_score_failure_nonpolicy','sum'),
                               natural_incomplete=('natural_incomplete_nonpolicy','sum'),priority_incomplete=('priority_incomplete_nonpolicy','sum'))
    exp=read('results/time_semantics/FOUR_POLICY_COMMON_TIME_FAILURE_COUNTS.csv').set_index(group).sort_index()
    assert counts.index.equals(exp.index)
    check(counts,exp[counts.columns],'common_time_all_attempt_failure_counts',checks)
    counts.reset_index().to_csv(out/'COMMON_TIME_FAILURE_COUNTS.csv',index=False)
    metrics=['natural_Q_unavailable','priority_Q_unavailable','Q_unavailable_delta',
             'natural_score_failure_nonpolicy','priority_score_failure_nonpolicy','score_failure_delta',
             'natural_incomplete_nonpolicy','priority_incomplete_nonpolicy','incomplete_delta']
    image=x.groupby(group+['pool_id','building','k'])[metrics].mean().groupby(group+['pool_id','building']).mean().reset_index()
    results=[]
    for names,g in image.groupby(group):
        for metric in metrics:
            b=g.groupby('building')[metric].mean()
            results.append(dict(zip(group,names),domain='four_policy_time_common',metric=metric,
                                image_equal=g[metric].mean(),building_equal=b.mean(),images=int(g[metric].notna().sum()),
                                buildings=int(b.notna().sum()),positive_image_fraction=g[metric].dropna().gt(0).mean()))
    effects=pd.DataFrame(results);ek=group+['domain','metric'];ec=['image_equal','building_equal','images','buildings','positive_image_fraction']
    a=effects.set_index(ek).sort_index();exp=read('results/time_semantics/FOUR_POLICY_COMMON_TIME_EFFECTS.csv')
    b=exp[exp.domain.eq('four_policy_time_common')].set_index(ek).sort_index()
    assert a.index.equals(b.index)
    check(a[ec],b[ec],'common_time_failure_effects',checks)
    effects.to_csv(out/'COMMON_TIME_FAILURE_EFFECTS.csv',index=False)
    pd.DataFrame(checks).to_csv(out/'COMMON_SUPPORT_NUMERIC_CHECKS.csv',index=False)
    receipt=dict(prefixes_read=len(d),common_time_units=len(x)//4,common_time_policy_rows=len(x),
                 failure_effect_rows=len(effects),failure_count_rows=len(counts),
                 checked_values=sum(r['values'] for r in checks),new_bootstrap=0,new_fusion=0,
                 common_time_domain='five teams have complete single identical time semantics before selecting evaluable Q')
    (out/'COMMON_SUPPORT_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False),flush=True)


def main(root, original, out):
    out.mkdir(parents=True,exist_ok=True);checks=[];read=lambda p,**kw:pd.read_csv(root/p,low_memory=False,**kw)
    d=read('inputs/PREFIX_VALUES_COMPACT.csv.gz');orders=read('inputs/EXACT_ORDER_DESIGN.csv.gz')
    assert len(d)==404082 and len(orders)==12398 and not d.duplicated(['path_id','k']).any()
    old=pd.read_csv(original/'results/ENDPOINT_SCALARS.csv.gz',usecols=['team_key','member_workers','B8L2','D10','score_failure_nonpolicy','incomplete_nonpolicy'],low_memory=False).set_index('team_key')
    assert len(old)==318816 and old.index.is_unique
    for c in ['B8L2','D10','score_failure_nonpolicy','incomplete_nonpolicy']:
        check(d[c],old.loc[d.team_key,c],'original_prefix_'+c,checks)
    member_lookup=old.member_workers.map(lambda x:frozenset(x.split('|'))).to_dict()
    di=d.set_index(['path_id','k']);sem=read('inputs/PREFIX_TIME_SEMANTICS.csv.gz').set_index(['path_id','k'])
    records=read('inputs/RECORD_TIME_SOURCE_INDEX.csv.gz').set_index(['pool_id','worker_id'])
    record_lookup={i:(r.source_time_seconds,r.time_source_kind) for i,r in records.iterrows()}
    timechecks=[]
    for order in orders.itertuples():
        workers=order.worker_order.split('|');assert len(set(workers))==len(workers)==order.pool_n
        seen=set();known=0;total=0.;kinds=set()
        for k,w in enumerate(workers,1):
            seen.add(w);rr=di.loc[(order.path_id,k)];ss=sem.loc[(order.path_id,k)]
            assert member_lookup[rr.team_key]==seen and rr.entrant_worker==w
            seconds,kind=record_lookup[order.pool_id,w]
            if pd.notna(seconds):known+=1;total+=seconds;kinds.add(str(kind))
            eligible=known==k and total>0 and len(kinds)==1 and not (kinds&{'nan','','None','unknown'})
            assert ss.known_n_rederived==known and bool(ss.recorded_time_eligible_same_semantics)==bool(eligible)
            assert str(ss.time_source_kinds if pd.notna(ss.time_source_kinds) else '')=='|'.join(sorted(kinds))
            if known==k:assert abs(total-ss.total_seconds_rederived)<1e-7
        timechecks.append(dict(path_id=order.path_id,full_n=len(workers)))
    print('404082前缀与原端点、12398顺序、逐人时间来源核对完成',flush=True)
    meta=d[['pool_id','building','condition','layer','difficulty','pool_n']].drop_duplicates('pool_id')
    meta=meta[meta.pool_n>=20].set_index('pool_id')
    seed=read('results/EXACT_BOOTSTRAP_SEEDS.csv',dtype={'seed':str}).set_index(['pool_id','kind'])
    curves=read('results/NATURAL_IMAGE_CURVES_REBUILT.csv.gz').set_index(['pool_id','k'])
    intervals=read('results/NATURAL_INTERVAL_STABILITY.csv')
    ipoints={};idraws={};pointrows=[]
    intervals_list=[(3,6),(6,10),(10,20),(3,20)]
    for i,(pool,g) in enumerate(d[d.policy.eq('natural_random')&d.pool_id.isin(meta.index)&d.k.le(20)].groupby('pool_id',sort=True)):
        arr=g.pivot(index='k',columns='path_id',values='B8L2').sort_index().sort_index(axis=1).to_numpy()
        assert arr.shape==(20,24)
        stats=distribution(arr)
        for j,c in enumerate(['Q_mean','Q_p10','Q_sd_ddof1']):
            check(stats[:,j],curves.loc[pool].sort_index()[c],pool+'/'+c,checks)
        rng=np.random.default_rng(int(seed.loc[(pool,'natural_whole_paths'),'seed']))
        draws=rng.integers(24,size=(2000,24))
        boot=distribution(arr[:,draws].transpose(1,0,2)).astype(np.float32)
        check(distribution(arr)[[2,5,9,19],1],np.nanquantile(arr[[2,5,9,19]],.1,axis=1),'quantile_numpy_reference/'+pool,checks)
        ipoints[pool]=np.stack([stats[b-1]-stats[a-1] for a,b in intervals_list])
        idraws[pool]=np.stack([boot[:,b-1]-boot[:,a-1] for a,b in intervals_list],axis=1)
        for j,(a,b) in enumerate(intervals_list):
            pointrows.append(dict(pool_id=pool,**meta.loc[pool].to_dict(),interval=f'{a}_to_{b}',Q_mean=ipoints[pool][j,0],Q_p10=ipoints[pool][j,1],Q_sd_ddof1=ipoints[pool][j,2]))
        if i%30==0:print('natural bootstrap pools',i+1,flush=True)
    bootrows=[]
    for (condition,layer,difficulty),rows in intervals.groupby(['condition','layer','difficulty'],sort=True):
        mm=meta[meta.condition.eq(condition)&meta.layer.eq(layer)]
        if difficulty!='全部':mm=mm[mm.difficulty.eq(difficulty)]
        pp=list(mm.index);point=np.stack([ipoints[p] for p in pp]);draw=np.stack([idraws[p] for p in pp]).astype(float)
        bnames=sorted(mm.building.unique())
        bi=[np.flatnonzero(mm.building.to_numpy()==b) for b in bnames]
        bpoints=np.stack([np.nanmean(point[ix],axis=0) for ix in bi])
        bdraws=np.stack([np.nanmean(draw[ix],axis=0) for ix in bi])
        bsum=np.stack([np.nansum(point[ix],axis=0) for ix in bi]);bcount=np.stack([np.isfinite(point[ix]).sum(0) for ix in bi])
        bseed=int(rows[rows.resampling.eq('building_resampling_fixed_paths')].building_seed.iloc[0][4:])
        weights=np.random.default_rng(bseed).multinomial(len(bnames),np.ones(len(bnames))/len(bnames),size=2000)
        cluster_image=np.einsum('rb,bij->rij',weights,bsum)/np.einsum('rb,bij->rij',weights,bcount)
        cluster_building=np.einsum('rb,bij->rij',weights,np.nan_to_num(bpoints))/np.einsum('rb,bij->rij',weights,np.isfinite(bpoints).astype(float))
        for weight,point_est in [('image_equal',np.nanmean(point,axis=0)),('building_equal',np.nanmean(bpoints,axis=0))]:
            for mode,dd in [('path_resampling_fixed_images',np.nanmean(draw if weight=='image_equal' else bdraws,axis=0)),
                            ('building_resampling_fixed_paths',cluster_image if weight=='image_equal' else cluster_building)]:
                for j,(a,b) in enumerate(intervals_list):
                    for k,metric in enumerate(['Q_mean','Q_p10','Q_sd_ddof1']):
                        r=rows[rows.interval.eq(f'{a}_to_{b}')&rows.metric.eq(metric)&rows.weighting.eq(weight)&rows.resampling.eq(mode)].iloc[0]
                        actual=[point_est[j,k],*np.nanquantile(dd[:,j,k],[.025,.975])]
                        check(actual,r[['estimate','percentile_2_5','percentile_97_5']],f'natural_interval/{condition}/{layer}/{difficulty}/{a}_{b}/{metric}/{weight}/{mode}',checks,atol=2e-6)
                        bootrows.append(dict(condition=condition,layer=layer,difficulty=difficulty,interval=f'{a}_to_{b}',metric=metric,weighting=weight,resampling=mode,estimate=actual[0],low=actual[1],high=actual[2]))
    pd.DataFrame(pointrows).to_csv(out/'POPULATION_IMAGE_INTERVALS.csv',index=False)
    pd.DataFrame(bootrows).to_csv(out/'POPULATION_BOOTSTRAP_INTERVALS.csv',index=False)
    # 每策略相对自己的同一自然路径；先路径、k、图片，再建筑。
    policies=sorted(set(d.policy)-{'natural_random'});pr=read('results/POLICY_EARLY_IMAGE_REBUILT.csv').set_index(['pool_id','policy'])
    ppoints={};pdraws={};pnat=d[d.policy.eq('natural_random')].set_index(['pool_id','path_id','k'])
    prow=[]
    for (pool,policy),g in d[d.pool_id.isin(meta.index)&d.policy.ne('natural_random')].groupby(['pool_id','policy'],sort=True):
        N=int(meta.loc[pool,'pool_n']);g=g[g.k.between(3,N//2)]
        natural=pnat.loc[pd.MultiIndex.from_arrays([g.pool_id,g.base_path_id,g.k])]
        delta=g.B8L2.to_numpy()-natural.B8L2.to_numpy()
        x=g[['k','base_path_id']].assign(delta=delta).pivot(index='k',columns='base_path_id',values='delta').sort_index().sort_index(axis=1).to_numpy()
        point=np.nanmean(np.nanmean(x,axis=1))
        check([point],[pr.loc[(pool,policy),'paired_Q_delta']],pool+'/'+policy+'/early_Q',checks)
        rng=np.random.default_rng(int(seed.loc[(pool,'paired_base_whole_paths'),'seed']))
        ix=rng.integers(x.shape[1],size=(2000,x.shape[1]))
        draw=np.nanmean(np.nanmean(x[:,ix],axis=2),axis=0).astype(np.float32)
        ppoints[pool,policy]=point;pdraws[pool,policy]=draw
        prow.append(dict(pool_id=pool,policy=policy,**meta.loc[pool].to_dict(),paired_Q_delta=point))
    pst=read('results/POLICY_EARLY_STABILITY.csv')
    pst=pst[pst.metric.eq('paired_Q_delta')&pst.policy_support.eq('common_four_policy_pools')]
    common_pools=set.intersection(*[{pool for pool,pol in ppoints if pol==policy} for policy in policies])
    for (condition,layer,difficulty,policy),rows in pst.groupby(['condition','layer','difficulty','policy']):
        mm=meta[meta.condition.eq(condition)&meta.layer.eq(layer)&meta.index.isin(common_pools)]
        if difficulty!='全部':mm=mm[mm.difficulty.eq(difficulty)]
        pts=np.array([ppoints[p,policy] for p in mm.index]);dr=np.stack([pdraws[p,policy] for p in mm.index]).astype(float)
        bnames=sorted(mm.building.unique());bi=[np.flatnonzero(mm.building.to_numpy()==b) for b in bnames]
        bp=np.array([np.nanmean(pts[ix]) for ix in bi]);bd=np.stack([np.nanmean(dr[ix],axis=0) for ix in bi])
        bseed=int(rows[rows.resampling.eq('building_resampling_fixed_paths')].building_seed.iloc[0][4:])
        w=np.random.default_rng(bseed).multinomial(len(bnames),np.ones(len(bnames))/len(bnames),size=2000)
        for row in rows.itertuples():
            if row.resampling=='path_resampling_fixed_images':xx=np.nanmean(dr if row.weighting=='image_equal' else bd,axis=0)
            elif row.weighting=='building_equal':xx=w@bp/len(bnames)
            else:xx=(w@np.array([np.nansum(pts[ix]) for ix in bi]))/(w@np.array([np.isfinite(pts[ix]).sum() for ix in bi]))
            pval=np.nanmean(pts if row.weighting=='image_equal' else bp)
            check([pval,*np.nanquantile(xx,[.025,.975])],[row.estimate,row.percentile_2_5,row.percentile_97_5],
                  f'policy_bootstrap/{condition}/{layer}/{difficulty}/{policy}/{row.weighting}/{row.resampling}',checks,atol=2e-6)
    pd.DataFrame(prow).to_csv(out/'POLICY_IMAGE_EFFECTS.csv',index=False)
    # 用已独立核过的前缀和时间重新取五支队伍的精确共同域。
    sem=sem.reset_index();cols=['path_id','k','time_source_kinds','recorded_time_eligible_same_semantics']
    merged=d.merge(sem[cols],on=['path_id','k'],validate='one_to_one')
    keys=['pool_id','base_path_id','k'];nat=merged[merged.policy.eq('natural_random')].copy()
    priority=merged[merged.policy.ne('natural_random')&merged.pool_id.isin(meta.index)&merged.k.ge(3)&merged.k.le(merged.pool_n//2)]
    ncols=keys+['team_key','B8L2','source_time_total_seconds','time_source_kinds','recorded_time_eligible_same_semantics','score_failure_nonpolicy']
    x=priority.merge(nat[ncols],on=keys,suffixes=('','_natural'),validate='many_to_one')
    x['time_ok']=x.recorded_time_eligible_same_semantics & x.recorded_time_eligible_same_semantics_natural & x.time_source_kinds.eq(x.time_source_kinds_natural)
    x['q_ok']=x.B8L2.notna() & x.B8L2_natural.notna()
    status=x.groupby(keys).agg(policies=('policy','nunique'),time_ok=('time_ok','all'),q_ok=('q_ok','all')).reset_index()
    allowed=status[status.policies.eq(4)&status.time_ok]
    x=x.merge(allowed[keys+['q_ok']],on=keys,suffixes=('','_five'),validate='many_to_one')
    saved=read('results/time_semantics/FOUR_POLICY_COMMON_TIME_EXACT_PAIRS.csv.gz').set_index(keys+['policy'])
    x=x.set_index(keys+['policy'])
    assert x.index.is_unique and set(x.index)==set(saved.index)
    x=x.loc[saved.index].reset_index()
    for c in ['team_key','team_key_natural']:
        expected=saved['priority_team_key' if c=='team_key' else 'natural_team_key']
        assert (x[c].to_numpy()==expected.to_numpy()).all()
    x['Q_delta']=x.B8L2-x.B8L2_natural;x['time_ratio']=x.source_time_total_seconds/x.source_time_total_seconds_natural
    x['Q_loss_gt5']=x.Q_delta.lt(-5).where(x.Q_delta.notna())
    effects=read('results/time_semantics/FOUR_POLICY_COMMON_TIME_EFFECTS.csv')
    results=[]
    for (condition,layer,kind,policy),g in x[x.q_ok_five].groupby(['condition','layer','time_source_kinds','policy']):
        for metric in ['Q_delta','time_ratio','Q_loss_gt5']:
            im=g.groupby(['pool_id','building','k'])[metric].mean().groupby(['pool_id','building']).mean()
            building=im.groupby('building').mean()
            rr=effects[effects.condition.eq(condition)&effects.layer.eq(layer)&effects.time_source_kind.eq(kind)&effects.policy.eq(policy)&effects.metric.eq(metric)&effects.domain.eq('four_policy_QT_common')].iloc[0]
            check([im.mean(),building.mean()],[rr.image_equal,rr.building_equal],f'five_team_time/{condition}/{layer}/{kind}/{policy}/{metric}',checks)
            results.append(dict(condition=condition,layer=layer,kind=kind,policy=policy,metric=metric,images=len(im),buildings=len(building),image_equal=im.mean(),building_equal=building.mean(),units=len(g)))
    pd.DataFrame(results).to_csv(out/'COMMON_TIME_RESULTS.csv',index=False)
    pd.DataFrame(checks).to_csv(out/'POPULATION_NUMERIC_CHECKS.csv',index=False)
    receipt=dict(prefixes=len(d),unique_endpoints=len(old),orders=len(orders),N20_pools=len(meta),bootstrap_replicates=2000,
                 natural_bootstrap_metrics=['Q_mean','Q_p10','Q_sd_ddof1'],policy_bootstrap_metric='paired_Q_delta',
                 checked_values=sum(r['values'] for r in checks),numeric_checks=len(checks),
                 new_fusion=0,new_orders=0,record_time_prefixes_reconstructed=len(sem))
    (out/'POPULATION_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False),flush=True)
    audit_common_pool_and_failures(root,out)


if __name__=='__main__':
    warnings.filterwarnings('ignore',category=RuntimeWarning)
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--original',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--common-support-only',action='store_true',help='仅补核四策略共同池和共同时间失败，不重抽')
    a=p.parse_args()
    if a.common_support_only:audit_common_pool_and_failures(a.root,a.out)
    else:main(a.root,a.original,a.out)
