"""独立核对人数曲线精度，不执行融合。"""
from pathlib import Path
import json
import warnings
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[3]
POP=ROOT/'research/workers/personnel_population_curves_v2_20261023'
BASE=POP/'sampling_precision_20261025'
OUT=BASE/'local_audit/natural'
META=['image','building','layer','difficulty','pool_n']
RAW=['B8L2','D10','floor_turn5_n','floor_redundant5_n','nodes','score_failure_nonpolicy','incomplete_nonpolicy','policy_deferred']

def measures(g):
    q=g.B8L2.dropna().to_numpy();a=g.loc[~g.policy_deferred]
    return dict(Q_mean=q.mean() if len(q) else np.nan,Q_p10=np.quantile(q,.1) if len(q) else np.nan,
      Q_sd_ddof1=q.std(ddof=1) if len(q)>1 else np.nan,D10_mean=g.D10.mean(),floor_turn5_mean=g.floor_turn5_n.mean(),
      floor_redundant5_mean=g.floor_redundant5_n.mean(),nodes_mean=g.nodes.mean(),failure_rate=a.score_failure_nonpolicy.mean(),
      incomplete_rate=a.incomplete_nonpolicy.mean(),paths_attempted=len(g),quality_valid_paths=len(q),unique_teams=g.team_key.nunique(),
      policy_deferred_paths=int(g.policy_deferred.sum()),nondeferred_attempts=len(a),failure_paths=int(a.score_failure_nonpolicy.sum()))

def check(actual,saved,keys,columns):
    assert not actual.duplicated(keys).any() and not saved.duplicated(keys).any()
    j=actual.merge(saved,on=keys,how='outer',suffixes=('_a','_s'),indicator=True)
    assert j._merge.eq('both').all(),j._merge.value_counts().to_dict()
    out=[]
    for c in columns:
        a=j[c+'_a'].to_numpy(float);s=j[c+'_s'].to_numpy(float);ok=np.isclose(a,s,atol=1e-9,rtol=1e-11,equal_nan=True)
        out.append(dict(field=c,rows=len(j),mismatches=int((~ok).sum()),max_abs_error=float(np.nanmax(np.abs(a-s)))))
        assert ok.all(),(c,j.loc[~ok,keys+[c+'_a',c+'_s']].head().to_dict('records'))
    return out

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    cols=['pool_id','path_id','k','policy','team_key']+META+RAW
    old=pd.read_csv(POP/'stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz',usecols=cols)
    new=pd.concat([pd.read_csv(p,usecols=cols+['batch']) for p in sorted((BASE/'new_endpoints/table_shards/NEW_PREFIX_VALUES_COMPACT').glob('*.csv.gz'))],ignore_index=True)
    pools=set(pd.read_csv(BASE/'design/POOL_SAMPLING_PLAN.csv').pool_id)
    old=old[old.policy.eq('natural_random')&old.pool_id.isin(pools)].copy();old['batch']='old24'
    new=new[new.policy.eq('natural_random')&new.pool_id.isin(pools)].copy()
    paths=pd.concat([old,new],ignore_index=True);assert not paths.duplicated(['pool_id','path_id','k']).any()
    for f in ['policy_deferred','score_failure_nonpolicy','incomplete_nonpolicy']:assert paths[f].dtype==bool
    assert paths.loc[paths.score_failure_nonpolicy|paths.policy_deferred,'B8L2'].isna().all()
    groups=dict(tuple(paths.groupby('pool_id',sort=True)));rows=[];intervals=[]
    batches=dict(old24=['old24'],new24=['balanced_new24'],pooled48=['old24','balanced_new24'],focus96=['old24','balanced_new24','focus_new48'])
    for pool,g in groups.items():
        meta=g.iloc[0][META].to_dict();n=int(meta['pool_n'])
        for version,batch in batches.items():
            if version=='focus96' and not g.batch.eq('focus_new48').any():continue
            h=g[g.batch.isin(batch)];at={}
            for k,v in h.groupby('k'):
                at[k]=measures(v);rows.append(dict(pool_id=pool,version=version,k=int(k),**meta,**at[k]))
            defs=[('1_to_3',1,3),('3_to_6',3,6),('6_to_10',6,10),('10_to_20',10,20),('20_to_30',20,30),('30_to_35',30,35),('3_to_20',3,20)]
            defs += [(f'{a}_to_full',a,n) for a in [3,10,20,30]]+[('leave_one_out_to_full',n-1,n)]
            for label,a,b in defs:
                if not 1<=a<=b<=n:continue
                pa=h[h.k.eq(a)].merge(h[h.k.eq(b)],on='path_id',suffixes=('_a','_b'),validate='one_to_one')
                dq=(pa.B8L2_b-pa.B8L2_a).dropna();dd=(pa.D10_b-pa.D10_a).dropna()
                intervals.append(dict(pool_id=pool,version=version,interval=label,**meta,
                  marginal_Q_delta=at[b]['Q_mean']-at[a]['Q_mean'],Q_p10_delta=at[b]['Q_p10']-at[a]['Q_p10'],
                  Q_sd_delta=at[b]['Q_sd_ddof1']-at[a]['Q_sd_ddof1'],failure_delta=at[b]['failure_rate']-at[a]['failure_rate'],
                  paired_Q_delta=dq.mean(),paired_D10_delta=dd.mean(),paired_Q_loss_gt5_rate=(dq< -5).mean() if len(dq) else np.nan,
                  paired_Q_gain_gt5_rate=(dq>5).mean() if len(dq) else np.nan))
    curves=pd.DataFrame(rows);iv=pd.DataFrame(intervals)
    checks=check(curves,pd.read_csv(BASE/'analysis_precision/new_results/NATURAL_POOL_K_BATCH_POINTS.csv.gz'),['pool_id','version','k'],list(measures(paths.iloc[:1])))
    metrics=['marginal_Q_delta','Q_p10_delta','Q_sd_delta','failure_delta','paired_Q_delta','paired_D10_delta','paired_Q_loss_gt5_rate','paired_Q_gain_gt5_rate']
    checks+=check(iv,pd.read_csv(BASE/'analysis_precision/new_results/NATURAL_POOL_INTERVAL_BATCH_POINTS.csv.gz'),['pool_id','version','interval'],metrics)
    curves.to_csv(OUT/'RECOMPUTED_POOL_K.csv.gz',index=False);iv.to_csv(OUT/'RECOMPUTED_INTERVALS.csv.gz',index=False)
    saved=pd.read_csv(BASE/'analysis_precision/new_results/NATURAL_FIXED_SUPPORT_STABILITY.csv.gz')
    saved=saved[saved.domain.eq('balanced_all')&saved.kind.eq('interval')&saved.weighting.eq('image_equal')&saved.resampling.eq('path_MC_fixed_images')&saved.metric.isin(metrics)&saved.panel.str.startswith('fixed_N_ge_')]
    summaries=[]
    for (layer,diff,panel,pos,metric),z in saved.groupby(['layer','difficulty','panel','position','metric']):
        h=iv[iv.layer.eq(layer)&iv.pool_n.ge(int(panel.rsplit('_',1)[1]))&iv.interval.eq(pos)]
        if diff not in ['全部','单列']:h=h[h.difficulty.eq(diff)]
        common=h.pivot(index='pool_id',columns='version',values=metric)[['old24','new24','pooled48']].dropna()
        for r in z.itertuples():
            vals=common[r.version];value=vals.mean()
            assert np.isclose(value,r.estimate,atol=1e-9,equal_nan=True),(panel,pos,metric,value,r.estimate)
            assert len(vals)==r.common_observed_images
            summaries.append(dict(layer=layer,difficulty=diff,panel=panel,interval=pos,metric=metric,version=r.version,
              estimate=value,images=len(vals),positive=int((vals>1e-9).sum()),negative=int((vals< -1e-9).sum()),zero=int((vals.abs()<=1e-9).sum())))
    pd.DataFrame(summaries).to_csv(OUT/'COMMON_SUPPORT_INTERVALS.csv',index=False)
    seeds=pd.read_csv(BASE/'analysis_precision/new_results/NATURAL_EXACT_BOOTSTRAP_SEEDS.csv',dtype={'seed':str}).set_index(['pool_id','batch']).seed.to_dict()
    boots=[]
    for ka,kb,cap in [(3,6,20),(10,20,20),(20,30,30)]:
        ps=[]
        for pool,g in groups.items():
            m=g.iloc[0]
            if m.layer!='ordinary_manual' or m.difficulty!='困难' or m.pool_n<cap:continue
            samples=[]
            for batch,sn in [('old24','old24'),('balanced_new24','new24')]:
                q=g[g.batch.eq(batch)].pivot(index='path_id',columns='k',values='B8L2').sort_index()[[ka,kb]].to_numpy();assert q.shape==(24,2)
                ix=np.random.default_rng(int(seeds[(pool,sn)])).integers(24,size=(2000,24));samples.append(q[ix])
            q=np.concatenate(samples,axis=1)
            ss=np.stack([np.nanmean(q,axis=1),np.nanquantile(q,.1,axis=1),np.nanstd(q,axis=1,ddof=1)],axis=-1)
            ps.append(ss[:,1,:]-ss[:,0,:])
        agg=np.stack(ps).mean(axis=0)
        for j,metric in enumerate(['marginal_Q_delta','Q_p10_delta','Q_sd_delta']):
            lo,hi=np.nanquantile(agg[:,j],[.025,.975])
            r=saved[saved.layer.eq('ordinary_manual')&saved.difficulty.eq('困难')&saved.panel.eq(f'fixed_N_ge_{cap}')&saved.position.eq(f'{ka}_to_{kb}')&saved.metric.eq(metric)&saved.version.eq('pooled48')].iloc[0]
            assert np.isclose(lo,r.percentile_2_5,atol=1e-8) and np.isclose(hi,r.percentile_97_5,atol=1e-8),(ka,kb,metric,lo,hi,r.percentile_2_5,r.percentile_97_5)
            boots.append(dict(interval=f'{ka}_to_{kb}',metric=metric,images=len(ps),low=lo,high=hi,valid=int(np.isfinite(agg[:,j]).sum()),replicates=2000))
    pd.DataFrame(boots).to_csv(OUT/'INDEPENDENT_PATH_BOOTSTRAP.csv',index=False)
    receipt=dict(curve_rows=len(curves),interval_rows=len(iv),common_summary_rows=len(summaries),field_checks=checks,bootstrap_cells=len(boots),new_fusion=False)
    (OUT/'AUDIT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in receipt.items() if k!='field_checks'},ensure_ascii=False),flush=True)


def verify_hybrid():
    h=pd.read_csv(BASE/'analysis_precision/new_results/HYBRID48_IMAGE_CURVES.csv.gz')
    original=pd.read_csv(OUT/'RECOMPUTED_POOL_K.csv.gz');original=original[original.version.eq('pooled48')].set_index(['pool_id','k'])
    exact=pd.read_csv(BASE/'new_endpoints/EXACT_MARGINAL_VALUES.csv.gz'); ex=dict(tuple(exact.groupby(['pool_id','k'])))
    metrics=['Q_mean','Q_p10','Q_sd_population_estimate','D10_mean','floor_turn5_mean','floor_redundant5_mean','nodes_mean','failure_rate','incomplete_rate']
    count=0
    for r in h.itertuples():
        key=(r.pool_id,r.k)
        if r.estimator=='contract_deferred_k2':
            assert r.k==2 and all(pd.isna(getattr(r,c)) for c in metrics)
            continue
        if r.estimator=='exact_finite_uniform_marginal':
            g=ex[key];stats=measures(g);q=g.B8L2.dropna().to_numpy()
            stats['Q_sd_population_estimate']=q.std(ddof=0) if len(q) else np.nan
            assert len(g)==r.known_finite_teams and g.team_key.nunique()==len(g)
        else:
            stats=original.loc[key].to_dict();stats['Q_sd_population_estimate']=stats['Q_sd_ddof1']
        for c in metrics:
            assert np.isclose(stats[c],getattr(r,c),atol=1e-9,rtol=1e-11,equal_nan=True),(key,c,stats[c],getattr(r,c))
        count+=1
    result={'total_rows':len(h),'checked_scientific_cells':count*len(metrics),'deferred_rows':int(h.k.eq(2).sum()),'estimators':h.estimator.value_counts().to_dict()}
    (OUT/'HYBRID_CHECK.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(result,flush=True)

if __name__=='__main__':
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning)
        main()
        verify_hybrid()
