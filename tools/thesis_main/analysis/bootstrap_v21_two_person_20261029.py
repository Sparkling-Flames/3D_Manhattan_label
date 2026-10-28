"""Pointwise k=2 uncertainty from saved, stratified natural paths."""
import json
import os
import sys
import numpy as np
import pandas as pd
from .rebuild_v21_20261028 import OUT
from .prepare_v21_natural_inputs_20261028 import EXT

for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
TARGET=OUT/'two_person_natural256'
FIELDS=['Q2','delta_1_2','delta_2_3','failure','Q1','Q3']


def main():
    sys.path.insert(0,str(EXT/'analysis_precision26'))
    from precision_core import bootstrap_weights,weighted_mean,boot_summary,seed_for,METRICS
    from summarize_natural import weights_and_building_draws
    paths=pd.read_csv(TARGET/'PAIRED_PATH_RESULTS.csv.gz',low_memory=False)
    paths['failure']=paths.k2_score_status.isin(['below_four','no_connection','fusion_exception']).astype(float)
    images=pd.read_csv(TARGET/'IMAGE_RESULTS.csv').set_index('pool_id')
    original={p.stem for p in (OUT/'natural_analysis_restored/bootstrap_cache').glob('*.npz')}
    maincurves=pd.read_csv(OUT/'natural_results/HYBRID_DISPLAY_CURVES.csv.gz',usecols=['pool_id','support_origin'])
    origin=maincurves.drop_duplicates('pool_id').set_index('pool_id').support_origin.to_dict()
    assert paths.pool_id.nunique()==223 and len(paths)==223*256
    boot={};rows=[]
    for pid,g in paths.groupby('pool_id',sort=True):
        parts=[];ws=[]
        names=['new_space256'] if origin[pid]=='new_reference_pool' else ['old24','prior_new24','new104A','new104B']
        for name in names:
            sg=g[g.stratum.eq(name)].sort_values('path_id'); expected=256 if name=='new_space256' else (24 if name in ['old24','prior_new24'] else 104)
            assert len(sg)==expected and sg.path_id.is_unique,(pid,name,len(sg))
            parts.append(sg[FIELDS].to_numpy(float));ws.append(bootstrap_weights(pid,name,len(sg),2000,2026102607))
        values=np.concatenate(parts);w=np.concatenate(ws,axis=1)
        estimates=weighted_mean(values,np.ones((1,len(values))))[0][0]
        draws=weighted_mean(values,w)[0]
        expected=images.loc[pid]
        for i,col in enumerate(['Q2','delta_1_2','delta_2_3','consensus_failure_rate']):
            assert np.isclose(estimates[i],expected[col],atol=1e-8,equal_nan=True),(pid,col)
        cache=OUT/('natural_analysis_restored' if pid in original else 'natural_analysis')/'bootstrap_cache'/(pid+'.npz')
        with np.load(cache,allow_pickle=False) as z:
            existing=z['curve_new_space256' if origin[pid]=='new_reference_pool' else 'curve_pooled256']
            for index,k in [(4,1),(5,3)]:
                assert np.allclose(draws[:,index],existing[:,k-1,METRICS.index('Q_mean')],atol=1e-5,rtol=0,equal_nan=True),(pid,k,'path bootstrap identity')
        boot[pid]=draws[:,:4]
        for i,metric in enumerate(FIELDS[:4]):
            b=boot_summary(draws[:,i]);rows.append(dict(pool_id=pid,metric=metric,estimate=estimates[i],paths=256,valid_paths=int(np.isfinite(values[:,i]).sum()),path95_low=b['low'],path95_high=b['high'],path_valid_draws=b['valid']))
    pd.DataFrame(rows).to_csv(TARGET/'K2_IMAGE_INTERVALS.csv',index=False)
    summaries=[]
    for scope in ['original','added','combined']:
        for panel in ['available','N_ge_30','N_ge_35']:
            for layer in ['ordinary_manual','doorway_manual']:
                d=images[images.layer.eq(layer)].copy()
                if scope!='combined':d=d[[origin[x]==('original_pool' if scope=='original' else 'new_reference_pool') for x in d.index]]
                if panel!='available':d=d[d.pool_n.ge(int(panel[5:]))]
                for i,metric in enumerate(FIELDS[:4]):
                    source={'Q2':'Q2','delta_1_2':'delta_1_2','delta_2_3':'delta_2_3','failure':'consensus_failure_rate'}[metric]
                    valid=d[d[source].notna()];pids=list(valid.index)
                    if not pids:continue
                    observed=valid[source].to_numpy(float);arr=np.stack([boot[pid][:,i] for pid in pids]);buildings=valid.building.to_numpy()
                    for weighting in ['image_equal','building_equal']:
                        w,bw=weights_and_building_draws(buildings,weighting,2000,seed_for(2026102607,panel,layer,'k2',metric,'buildings'))
                        path_draws=np.sum(arr*w[:,None],axis=0);building_draws=bw@observed
                        for uncertainty,sample in [('paths_fixed_images',path_draws),('buildings_fixed_path_estimates',building_draws)]:
                            stat=boot_summary(sample);summaries.append(dict(scope=scope,panel=panel,layer=layer,metric=metric,weighting=weighting,uncertainty=uncertainty,estimate=float(w@observed),images=len(pids),eligible_images=len(d),buildings=len(set(buildings)),valid_paths=int(valid[{'Q2':'Q2_valid','delta_1_2':'paired_1_2','delta_2_3':'paired_2_3','failure':'paths'}[metric]].sum()),low=stat['low'],high=stat['high'],valid_draws=stat['valid'],requested_draws=2000))
    pd.DataFrame(summaries).to_csv(TARGET/'K2_AGGREGATE_INTERVALS.csv',index=False)
    (TARGET/'K2_INTERVAL_CHECKS.json').write_text(json.dumps(dict(pools=len(boot),paths=len(paths),bootstrap=2000,stratified_original_weights=True,prior_curve_Q1_Q3_draw_parity=True,paired_changes='separate joint valid paths',fixed_images=True,uncertainties=['paths_fixed_images','buildings_fixed_path_estimates'],interval_type='pointwise only; not part of previous simultaneous curve band',new_fusion=False,new_scoring=False),indent=2)+'\n',encoding='utf8')
    print('k2 intervals:',len(boot),'pools;',len(summaries),'aggregate rows',flush=True)


if __name__=='__main__':main()
