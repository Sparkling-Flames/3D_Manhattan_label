"""接合未变自然曲线与更新池，保留原有/新增支持及精确有限分布。"""
import json
import sys
import numpy as np
import pandas as pd
from .rebuild_v21_20261028 import OUT, ROOT, read
from .prepare_v21_natural_inputs_20261028 import EXT,BASE

TARGET=OUT/'natural_results'


def unchanged_secondary_registry():
    covered=set(pd.read_csv(TARGET/'NATURAL_CURVES.csv.gz',usecols=['pool_id']).pool_id)
    deps=[r for r in read(OUT/'pools/DEPENDENCIES.json') if r['pool_id'] not in covered]
    assert all(r['action']=='reuse_endpoints' and r['same_reference'] and r['same_members'] and r['same_input_geometry'] for r in deps)
    orders=pd.read_csv(BASE/'design/EXACT_ORDER_DESIGN.csv.gz',usecols=['pool_id','policy','path_id'])
    orders=orders[orders.policy.eq('natural_random')]
    saved=pd.read_csv(BASE/'stability_rebuilt_20261023/results/NATURAL_IMAGE_CURVES_REBUILT.csv.gz',usecols=['pool_id'])
    for r in deps:
        r['natural_orders']=int(orders.pool_id.eq(r['pool_id']).sum());assert r['natural_orders']>0
        r['saved_stability_curve_available']=r['pool_id'] in set(saved.pool_id)
        r['source_root']=str(BASE.relative_to(ROOT)).replace('\\','/')
        r['source_tables']='design/EXACT_ORDER_DESIGN.csv.gz|results/PREFIX_TEAM_LINKS.csv.gz|results/ENDPOINT_SCALARS.csv.gz'
        r['interpretation']='unchanged secondary range; original path count retained, not promoted to natural256'
    pd.DataFrame(deps).to_csv(TARGET/'UNCHANGED_SECONDARY_REUSE.csv',index=False,encoding='utf-8-sig')


def combine(old,new):
    assert new.pool_id.notna().all()
    return pd.concat([old[~old.pool_id.isin(new.pool_id)],new],ignore_index=True)


def main():
    TARGET.mkdir(exist_ok=True)
    oldpath=EXT/'analysis_precision26/results_stage2'
    pools={p['pool_id']:p['meta'] for p in read(OUT/'pools/INPUT_SNAPSHOT.json')['images']}
    newids={r['pool_id'] for r in read(OUT/'pools/DEPENDENCIES.json') if r['action']=='new_or_changed_pool'}
    receipts=[]
    for stem in ['CURVES','INTERVALS','COMPONENTS','STATUS','CURVE_BANDS','CURVE_BAND_SUMMARY','PATH_STRATA']:
        old=pd.read_csv(oldpath/f'NATURAL_{stem}.csv.gz',low_memory=False,dtype={'bootstrap_stratum_seed':str})
        new=pd.read_csv(OUT/'natural_analysis'/f'UPDATED_{stem}.csv.gz',low_memory=False,dtype={'bootstrap_stratum_seed':str})
        d=combine(old,new)
        for field in ['image','image_id','building','condition','layer','difficulty','pool_n','reference_id','reference_version']:
            if field in d:d[field]=d.pool_id.map({pid:meta[field] for pid,meta in pools.items()})
        d['support_origin']=np.where(d.pool_id.isin(newids),'new_reference_pool','original_pool')
        d['data_release']='v2.1'
        d['analysis_eligible']=d.pool_id.map({pid:meta['pool_n']>=3 for pid,meta in pools.items()})
        d.to_csv(TARGET/f'NATURAL_{stem}.csv.gz',index=False,encoding='utf-8-sig')
        receipts.append(dict(table=stem,old_pools=old.pool_id.nunique(),updated_pools=new.pool_id.nunique(),combined_pools=d.pool_id.nunique(),rows=len(d)))
    curve=pd.read_csv(TARGET/'NATURAL_CURVES.csv.gz',low_memory=False)
    assert not curve.duplicated(['pool_id','cohort','k']).any()
    main=curve[curve.cohort.isin(['pooled256','new_space256']) & curve.analysis_eligible].copy()
    assert main.loc[main.layer.isin(['ordinary_manual','doorway_manual']),'pool_id'].nunique()==223
    exact=pd.read_csv(OUT/'exact_marginals/EXACT_FINITE_MARGINAL_STATISTICS.csv')
    assert exact.exact_complete.all() and not exact.duplicated(['pool_id','k']).any()
    hybrid=main.merge(exact[exact.k.ne(2)],on=['pool_id','k'],suffixes=('','_exact'),validate='many_to_one',how='left')
    hybrid['display_source']=np.where(hybrid.exact_complete.eq(True),'complete_finite_team_population','uniform_path_MC')
    for field in ['Q_mean','Q_p10','Q_p10_inverse_cdf','D10_mean','floor_turn5_mean','floor_redundant5_mean','nodes_mean','failure_rate','incomplete_rate','actual_consensus_failure_rate','output_unscoreable_rate','reference_unavailable_rate','not_executed_rate']:
        hybrid['display_'+field]=np.where(hybrid.exact_complete.eq(True),hybrid[field+'_exact'],hybrid[field])
    hybrid['display_Q_sd']=np.where(hybrid.exact_complete.eq(True),hybrid.Q_sd_population_exact,hybrid.Q_sd_ddof1)
    hybrid['display_Q_sd_definition']=np.where(hybrid.exact_complete.eq(True),'finite_population_ddof0','MC_sample_ddof1')
    hybrid.to_csv(TARGET/'HYBRID_DISPLAY_CURVES.csv.gz',index=False,encoding='utf-8-sig')
    sys.path.insert(0,str(EXT/'analysis_precision26'))
    from summarize_natural import weights_and_building_draws
    from precision_core import seed_for
    rows=[]
    for support,frame in [('original',hybrid[hybrid.support_origin.eq('original_pool')]),('added',hybrid[hybrid.support_origin.eq('new_reference_pool')]),('combined',hybrid)]:
        for cutoff in [0,30,35]:
            d=frame if cutoff==0 else frame[frame.pool_n.ge(cutoff)&frame.k.le(cutoff)]
            for (layer,k),g in d.groupby(['layer','k']):
                for metric in ['Q_mean','Q_p10_inverse_cdf','Q_sd','D10_mean','actual_consensus_failure_rate','output_unscoreable_rate']:
                    col='display_'+metric;valid=g[g[col].notna()];x=valid[col].to_numpy(float)
                    if not len(x):continue
                    for weighting in ['image_equal','building_equal']:
                        w,bw=weights_and_building_draws(valid.building.to_numpy(),weighting,2000,seed_for(2026102607,'v21',support,cutoff,layer,k,metric,weighting))
                        draws=bw@x;ci=np.quantile(draws,[.025,.975]);nb=valid.building.nunique()
                        rows.append(dict(support=support,panel='available_at_k' if cutoff==0 else f'fixed_N_ge_{cutoff}',layer=layer,k=k,metric=metric,weighting=weighting,estimate=w@x,images=len(valid),eligible_images=len(g),missing_images=len(g)-len(valid),buildings=nb,building95_low=ci[0] if nb>1 else np.nan,building95_high=ci[1] if nb>1 else np.nan,uncertainty='building_resampling_fixed_estimated_image_curves',bootstrap=2000))
    pd.DataFrame(rows).to_csv(TARGET/'SUPPORT_STRATIFIED_SUMMARY.csv.gz',index=False,encoding='utf-8-sig')
    (TARGET/'CHECKS.json').write_text(json.dumps(dict(tables=receipts,primary_manual_pools=223,original_manual_pools=194,added_manual_pools=29,exact_cells=int(hybrid.exact_complete.eq(True).sum()),new_fusion=0,aggregate_path_MC_bands=('complete_see_AGGREGATE_BANDS_CHECKS.json' if (TARGET/'AGGREGATE_BANDS_CHECKS.json').exists() else 'not_reconstructed_missing_archived_unaffected_bootstrap_arrays'),per_image_path_precision='preserved_or_updated'),indent=2),encoding='utf-8')
    added=curve[curve.cohort.eq('new_space256')]
    assert added.loc[added.k.ne(2),'actual_consensus_failure_rate'].notna().all()
    assert added.loc[added.k.eq(2),'actual_consensus_failure_rate'].isna().all()
    checks=read(TARGET/'CHECKS.json')
    checks['deferred_schema_correction']=dict(version='explicit_k2_v1',pools=int(added.pool_id.nunique()),cells=len(added),nondeferred_cells=int(added.k.ne(2).sum()),deferred_paths=int(added.policy_deferred_paths.sum()),source='saved endpoint status and original paths',bootstrap=2000,new_fusion=0)
    (TARGET/'CHECKS.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    unchanged_secondary_registry()


if __name__=='__main__':main()
