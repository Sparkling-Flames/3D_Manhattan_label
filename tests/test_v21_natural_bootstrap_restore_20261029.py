import numpy as np
import pandas as pd
from tools.thesis_main.analysis.restore_v21_natural_bootstrap_20261029 import TARGET, EXT, OUT


def test_restored_pool_reproduces_original_curve_and_deferral():
    pid='2t7WUuJeko7-06__manual__9b197d01a2'
    with np.load(TARGET/'bootstrap_cache'/(pid+'.npz'),allow_pickle=False) as z:
        assert z['curve_pooled256'].shape[0]==2000
        assert np.isnan(z['curve_pooled256'][:,1,0]).all()
    a=pd.read_csv(TARGET/'pool_checkpoints'/(pid+'__curves.csv.gz'))
    b=pd.read_csv(EXT/'analysis_precision26/results_stage2/NATURAL_CURVES.csv.gz',low_memory=False)
    a=a[a.cohort.eq('pooled256')].sort_values('k');b=b[b.pool_id.eq(pid)&b.cohort.eq('pooled256')].sort_values('k')
    assert len(a)==len(b)
    for field in ['Q_mean','Q_p10','actual_consensus_failure_rate']:
        assert np.allclose(a[field],b[field],atol=1e-8,rtol=0,equal_nan=True)


def test_combined_path_band_uses_fixed_image_population():
    curves=pd.read_csv(OUT/'natural_results/NATURAL_CURVES.csv.gz',low_memory=False)
    d=curves[(curves.k==3)&(curves.layer=='ordinary_manual')&(curves.pool_n>=30)&curves.cohort.isin(['pooled256','new_space256'])]
    bands=pd.read_csv(OUT/'natural_results/FIXED_IMAGE_AGGREGATE_CURVE_BANDS_V21.csv.gz',low_memory=False)
    x=bands[(bands.support=='combined')&(bands.panel=='fixed_N_ge_30')&(bands.layer=='ordinary_manual')&(bands.difficulty=='全部')&(bands.metric=='Q_mean')&(bands.weighting=='image_equal')&(bands.uncertainty=='paths_fixed_images')&(bands.k==3)].iloc[0]
    excluded=set(str(x.excluded_pool_ids).split('|')) if pd.notna(x.excluded_pool_ids) else set()
    d=d[~d.pool_id.isin(excluded)];assert len(d)==int(x.images)==171
    assert np.isclose(d.Q_mean.mean(),x.estimate,atol=1e-8)
    draws=[]
    for r in d.itertuples():
        f=OUT/'natural_analysis/bootstrap_cache'/(r.pool_id+'.npz')
        if not f.exists():f=TARGET/'bootstrap_cache'/(r.pool_id+'.npz')
        with np.load(f,allow_pickle=False) as z:draws.append(z['curve_'+r.cohort][:,2,0])
    q=np.quantile(np.mean(draws,axis=0),[.025,.975])
    assert np.allclose(q,[x.pointwise_low,x.pointwise_high],atol=1e-6)
