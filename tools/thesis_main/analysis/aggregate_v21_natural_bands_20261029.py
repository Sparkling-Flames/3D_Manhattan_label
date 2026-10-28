"""Fixed-image natural curve bands from restored original whole-path draws."""
import json
import sys
import numpy as np
import pandas as pd
from .rebuild_v21_20261028 import OUT
from .prepare_v21_natural_inputs_20261028 import EXT


def main():
    sys.path.insert(0,str(EXT/'analysis_precision26'))
    from precision_core import METRICS,curve_band,boot_summary,seed_for
    from summarize_natural import weights_and_building_draws
    raw=pd.read_csv(OUT/'natural_results/NATURAL_CURVES.csv.gz',low_memory=False)
    raw=raw[raw.layer.isin(['ordinary_manual','doorway_manual'])]
    original=set(raw.loc[raw.cohort.eq('pooled256'),'pool_id']);added=set(raw.loc[raw.cohort.eq('new_space256'),'pool_id'])
    assert len(original)==194 and len(added)==29 and not original&added
    main=raw[(raw.cohort.eq('pooled256')&raw.pool_id.isin(original))|(raw.cohort.eq('new_space256')&raw.pool_id.isin(added))]
    meta=main[['pool_id','image','building','layer','difficulty','pool_n']].drop_duplicates('pool_id').set_index('pool_id')
    assert len(meta)==223 and not main.duplicated(['pool_id','k']).any()
    metrics=['Q_mean','Q_p10','Q_sd_ddof1','actual_consensus_failure_rate']; mi=[METRICS.index(c) for c in metrics]
    values=main.set_index(['pool_id','k']);draws={}
    for pid in meta.index:
        f=OUT/'natural_analysis/bootstrap_cache'/(pid+'.npz')
        if not f.exists():f=OUT/'natural_analysis_restored/bootstrap_cache'/(pid+'.npz')
        with np.load(f,allow_pickle=False) as z:
            cohort='curve_new_space256' if pid in added else 'curve_pooled256'
            a=z[cohort];assert a.shape[0]==2000
            draws[pid]=a[:,:,mi]
    old_support={}
    for metric in metrics:
        sets=[]
        for cohort in ['old48','new208','pooled256']:
            d=raw[raw.cohort.eq(cohort)&raw[metric].notna()]
            sets.append(set(map(tuple,d[['pool_id','k']].to_numpy())))
        old_support[metric]=set.intersection(*sets)
    bands=[];summaries=[]
    for scope,ids in [('original',original),('added',added),('combined',original|added)]:
        for cutoff in [27,30,35]:
            ks=np.array([k for k in range(1,cutoff+1) if k!=2])
            for layer in ['ordinary_manual','doorway_manual']:
                if (cutoff==27)!=(layer=='doorway_manual'):continue
                eligible=meta[(meta.index.isin(ids))&meta.layer.eq(layer)&meta.pool_n.ge(cutoff)]
                groups=[('全部' if layer=='ordinary_manual' else '单列',eligible)]
                if layer=='ordinary_manual':groups += [(str(diff),g) for diff,g in eligible.groupby('difficulty',dropna=False)]
                for difficulty,g in groups:
                    for j,metric in enumerate(metrics):
                        pids=[pid for pid in g.index if all((pid,int(k)) in values.index and pd.notna(values.at[(pid,int(k)),metric]) and (pid in added or (pid,int(k)) in old_support[metric]) for k in ks)]
                        if not pids:continue
                        x=np.array([[values.at[(pid,int(k)),metric] for k in ks] for pid in pids],float)
                        boot=np.stack([draws[pid][:,ks-1,j] for pid in pids]);buildings=meta.loc[pids,'building'].to_numpy()
                        for weighting in ['image_equal','building_equal']:
                            w,bw=weights_and_building_draws(buildings,weighting,2000,seed_for(2026102607,'wholecurve',cutoff,layer,difficulty,metric,'building'))
                            obs=w@x;path=np.sum(boot*w[:,None,None],axis=0);building=bw@x
                            for uncertainty,sample in [('paths_fixed_images',path),('buildings_fixed_path_estimates',building)]:
                                info,band=curve_band(obs,sample,ks,np.repeat(max(2,len(pids)),len(ks)),-1)
                                common=dict(support=scope,panel='fixed_N_ge_'+str(cutoff),layer=layer,difficulty=difficulty,metric=metric,weighting=weighting,uncertainty=uncertainty,images=len(pids),buildings=len(set(buildings)),capacity_images=len(g),excluded_pool_ids='|'.join(sorted(set(g.index)-set(pids))),support_rule='fixed images across all legal k; original old48/new208/pooled256 common support; added new_space256')
                                summaries.append(dict(common,**info))
                                for i,k in enumerate(ks):
                                    point=boot_summary(sample[:,i]);bands.append(dict(common,k=int(k),estimate=obs[i],max_absolute_low=band[i,0],max_absolute_high=band[i,1],max_studentized_low=band[i,2],max_studentized_high=band[i,3],pointwise_low=point['low'],pointwise_high=point['high'],pointwise_MCSE=point['MCSE'],pointwise_valid_draws=point['valid'],complete_bootstrap_draws=info['complete_bootstrap_draws']))
    target=OUT/'natural_results'
    pd.DataFrame(bands).to_csv(target/'FIXED_IMAGE_AGGREGATE_CURVE_BANDS_V21.csv.gz',index=False)
    pd.DataFrame(summaries).to_csv(target/'FIXED_IMAGE_AGGREGATE_CURVE_BAND_SUMMARY_V21.csv',index=False)
    (target/'AGGREGATE_BANDS_CHECKS.json').write_text(json.dumps(dict(original=194,added=29,combined=223,bootstrap=2000,restored_caches=159,existing_caches=64,rows=len(bands),support='fixed images and original common cohort support',k2='originally deferred; independent supplement excluded',path_and_building_uncertainty='separate',no_fusion_or_scoring=True),indent=2)+'\n',encoding='utf8')
    checks=json.loads((target/'CHECKS.json').read_text(encoding='utf8'))
    checks['aggregate_path_MC_bands']='complete_see_AGGREGATE_BANDS_CHECKS.json'
    (target/'CHECKS.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf8')
    print('bands',len(bands),'summaries',len(summaries),flush=True)


if __name__=='__main__':main()
