"""Reuse established Q80/Q90 thresholds to describe tail probabilities.

No thresholds are selected using new results. This supplements, and does not
replace, P10. Formal failure/output-invalid events cannot attain a score threshold;
reference-unavailable, unknown, not executed and k2-deferred states stay unknown.
"""
from pathlib import Path
import argparse,sys,os,json
for e in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[e]='1'
import numpy as np
import pandas as pd

VERSIONS={'old48':['old24','prior_new24'],'stage1_104':['new104A'],
          'stage2_104':['new104B'],'new208':['new104A','new104B'],
          'pooled256':['old24','prior_new24','new104A','new104B']}
KNOWN_UNSCORED={'fusion_exception','below_four','no_connection','invalid_floor','invalid_full_geometry','measurement_exception'}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);args=ap.parse_args()
    base=args.base.resolve();sys.path.insert(0,str(base/'analysis_precision26'))
    from precision_core import save_csv,save_json,binomial_precision,seed_for,interval_definitions
    from analyze_natural import read_selected
    plan=pd.read_csv(base/'design26/POOL_SAMPLING_PLAN.csv')
    assert len(plan)==194
    out=base/'analysis_reporting26/thresholds';out.mkdir(parents=True,exist_ok=True)
    rows=[];intervals=[]
    for m in plan.itertuples():
        old=pd.read_csv(base/'analysis_precision26/prior_pool_cache'/(m.pool_id+'.csv.gz'),low_memory=False)
        old=old[old.stratum.isin(VERSIONS['old48'])]
        chunks=[old]
        for stage,label in [(1,'new104A'),(2,'new104B')]:
            path=base/f'new_endpoints26/stage{stage}/prefix_values'/(m.pool_id+'.csv.gz')
            assert path.with_suffix('').with_suffix('.receipt.json').exists(),(m.pool_id,stage)
            chunks.append(read_selected(path,label))
        data=pd.concat(chunks,ignore_index=True)
        data['B8L2']=pd.to_numeric(data.B8L2,errors='coerce')
        qgood=np.isfinite(data.B8L2)
        status=data.score_status.fillna('')
        executed=~data.get('endpoint_execution',pd.Series('',index=data.index)).eq('not_executed')
        data['known_trial']=data.k.ne(2)&executed&(qgood|status.isin(KNOWN_UNSCORED))
        md={k:getattr(m,k) for k in ['pool_id','image','building','layer','difficulty','pool_n']}
        for version,strata in VERSIONS.items():
            g=data[data.stratum.isin(strata)].copy()
            assert not g.duplicated(['path_id','k']).any()
            for threshold in [80,90]:
                g['attained']=np.where(g.known_trial,g.B8L2.ge(threshold).astype(float),np.nan)
                pivot=g.pivot(index='path_id',columns='k',values='attained').reindex(columns=range(1,int(m.pool_n)+1))
                for k,h in g.groupby('k'):
                    scoreable=h.B8L2.notna();n=int(h.known_trial.sum());x=int(h.attained.eq(1).sum());nq=int(scoreable.sum())
                    p=x/n if n else np.nan
                    ci=binomial_precision(x,n);full=int(k)==int(m.pool_n)
                    if full and n:ci={name:p for name in ci}
                    rows.append(dict(**md,cohort=version,k=int(k),threshold=threshold,
                        paths=len(h),known_executed_reference_trials=n,unknown_or_deferred_trials=len(h)-n,
                        scoreable_paths=nq,scoreable_and_at_threshold=x,
                        known_trial_attainment_probability=p,
                        Q_conditioned_attainment_probability=x/nq if nq else np.nan,
                        known_trial_attainment_MCSE=(np.sqrt(p*(1-p)/(n-1)) if n>1 else np.nan),
                        fullN_one_known_team=full,**{('attainment_'+key):val for key,val in ci.items()}))
                for label,ka,kb in interval_definitions(int(m.pool_n)):
                    a=pivot[ka].to_numpy();b=pivot[kb].to_numpy();good=np.isfinite(a)&np.isfinite(b)
                    delta=b[good]-a[good];n=len(delta)
                    intervals.append(dict(**md,cohort=version,threshold=threshold,interval=label,k_from=ka,k_to=kb,
                        known_paired_paths=n,all_paths=len(pivot),unknown_pairs=len(pivot)-n,
                        paired_attainment_delta=delta.mean() if n else np.nan,
                        paired_attainment_MCSE=delta.std(ddof=1)/np.sqrt(n) if n>1 else np.nan))
    d=pd.DataFrame(rows);v=pd.DataFrame(intervals)
    save_csv(d,out/'Q80_Q90_PER_IMAGE_K.csv.gz');save_csv(v,out/'Q80_Q90_PAIRED_INTERVALS.csv.gz')
    summaries=[]
    for panel,capacity in [('all_capacity_for_interval',0),('fixed_N_ge_30',30),('fixed_N_ge_35',35)]:
        z=v[v.pool_n.ge(capacity)]
        for (layer,threshold,interval),g0 in z.groupby(['layer','threshold','interval']):
            groups=[('全部' if layer=='ordinary_manual' else '单列',g0)]
            if layer=='ordinary_manual':groups+=list(g0.groupby('difficulty'))
            for difficulty,g in groups:
                a=g.pivot(index='pool_id',columns='cohort',values='paired_attainment_delta')
                if not set(VERSIONS).issubset(a.columns):continue
                ids=a.index[a[list(VERSIONS)].notna().all(axis=1)]
                if not len(ids):continue
                for version in VERSIONS:
                    h=g[g.cohort.eq(version)].set_index('pool_id').loc[ids]
                    values=h.paired_attainment_delta.to_numpy();se=h.paired_attainment_MCSE.to_numpy()
                    bnames,ix=np.unique(h.building,return_inverse=True);nb=len(bnames);sizes=np.bincount(ix)
                    sums=np.bincount(ix,weights=values)
                    bw=np.random.default_rng(seed_for(2026102681,panel,layer,threshold,interval,difficulty)).multinomial(nb,np.repeat(1/nb,nb),size=2000)
                    for weighting in ['image_equal','building_equal']:
                        w=np.repeat(1/len(h),len(h)) if weighting=='image_equal' else 1/(nb*sizes[ix])
                        point=float(w@values);mc=float(np.sqrt(np.sum((w*se)**2)))
                        bdraw=(bw@sums)/(bw@sizes) if weighting=='image_equal' else bw@(sums/sizes)/nb
                        lo,hi=np.quantile(bdraw,[.025,.975])
                        summaries.append(dict(panel=panel,layer=layer,difficulty=difficulty,threshold=threshold,interval=interval,
                            cohort=version,weighting=weighting,images=len(h),buildings=nb,estimate=point,
                            positive_images=int((values>1e-9).sum()),negative_images=int((values < -1e-9).sum()),
                            nearzero_images=int((np.abs(values)<=1e-9).sum()),
                            analytic_path_MCSE=mc,analytic_path_normal95_low=point-1.96*mc,analytic_path_normal95_high=point+1.96*mc,
                            building95_low=lo,building95_high=hi,unknown_pair_count=int(h.unknown_pairs.sum())))
    save_csv(pd.DataFrame(summaries),out/'Q80_Q90_FIXED_SUPPORT_INTERVAL_SUMMARY.csv')
    save_json(dict(source_commit='b9bcec809fbaec8ab055931a1abb7baa5db44dac',complete_pools=len(plan),
        threshold_origin='Existing population study Q80/Q90, no search on new results',new_endpoints=0,new_orders=0,
        point_denominators=['known executed reference-supported trial','conditional on scoreable Q'],
        unknown_states='not executed / unavailable reference / k2 deferred / unclassified unscoreable remain unknown',
        intervals='same complete natural path, both trial states known; all compared batches share observed image support',
        uncertainty='binomial marginal intervals; analytic paired-path MCSE; separate whole-building resampling',
        not_a_replacement_for_P10=True),out/'RECEIPT.json')
    print('Fixed Q80/Q90 attainment supplement complete',flush=True)


if __name__=='__main__':main()
