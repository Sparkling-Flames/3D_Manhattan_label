"""Independent numerical integrity checks for n20 analysis tables."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from analyze_n20 import save, js

HERE=Path(__file__).resolve().parent

def verify(condition):
    out=HERE/condition
    universe=pd.read_csv(out/'N20_WEIGHT_UNIVERSE_CHECK.csv')
    assert universe.all_class_vectors_complete.all()
    assert universe.possible_member_sets.eq(universe.exact_cell_population_sum).all()
    pools=pd.read_csv(out/'N20_CONFIGURATION_POOL_RESULTS.csv.gz')
    assert pools.loc[pools.within_variance_estimable_cells.eq(0),'within_cell_member_variance_estimate'].isna().all()
    one=pools[pools.cells.eq(pools.singleton_population_cells)]
    assert one.within_cell_member_variance_estimate.isna().all()
    p=pd.read_csv(out/'N20_PREDICTION_POOL_RESULTS.csv.gz')
    assert p.sampled_draws.ge(2).all()
    common=p[p.support_scope.str.startswith('common_') & p.model.isin(['source','QT_source','QT_moments_source','QT_moments_team_quadratic_source'])]
    group=[c for c in ['support_scope','design_anchor','family','heldout_building','pool_id','weighting','outcome','model'] if c in common]
    checks=[]
    for key,g in common.groupby(group,dropna=False):
        assert g.method_id.nunique()==3
        for value in ['mse','mae','null_mse','sampled_draws','member_estimator_effective_sample_size']:
            delta=float(g[value].max()-g[value].min())
            assert delta<=1e-9*max(1,float(abs(g[value]).max())),(key,value,delta)
        checks.append(dict(zip(group,key),common_methods=3,identical_QT_baselines=True))
    save(pd.DataFrame(checks),out/'N20_COMMON_BASELINE_CHECK.csv.gz')
    fits=pd.concat([pd.read_csv(p) for p in out.glob('*__FIT_SUPPORT.csv.gz')],ignore_index=True)
    outcomes=pd.concat([pd.read_csv(p) for p in out.glob('*__OUTCOME_SUPPORT.csv.gz')],ignore_index=True)
    save(fits,out/'N20_FIT_SUPPORT_ALL.csv.gz')
    save(outcomes,out/'N20_OUTCOME_SUPPORT_ALL.csv.gz')
    assert not fits.target_y_used_for_fit.astype(bool).any()
    assert not fits.target_feature_scale_used.astype(bool).any()
    assert fits.ridge.eq(.01).all()
    if (fits.support_scope=='own_class_supported').any():
        assert not fits.loc[fits.support_scope.eq('own_class_supported'),'model'].str.contains('QT').any()
    js(out/'N20_INTEGRITY_CHECK.json',dict(condition=condition,status='passed',
        exact_population_identities=len(universe),common_baseline_checks=len(checks),
        singleton_cells_excluded_from_reported_member_variance=True,
        singleton_only_pool_metric_rows=int(len(one)),
        all_model_target_pools_have_two_or_more_teams=True,
        all_target_feature_scaling_and_fit_outside_building=True,
        fixed_ridge=.01))
    print(condition,'checks passed',len(checks),'common baseline groups')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--condition',required=True,choices=['manual','semi'])
    verify(ap.parse_args().condition)
