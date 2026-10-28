import pandas as pd
from tools.thesis_main.analysis.assemble_v21_natural_20261028 import combine
from tools.thesis_main.analysis.rebuild_v21_20261028 import ROOT,OUT


def test_pool_replacement_does_not_keep_stale_cohort_or_drop_unaffected_pool():
    old=pd.DataFrame({'pool_id':['a','a','b'],'cohort':['old48','pooled256','pooled256'],'Q_mean':[1.,2.,3.]})
    new=pd.DataFrame({'pool_id':['a','c'],'cohort':['pooled256','new_space256'],'Q_mean':[None,4.]})
    d=combine(old,new).set_index('pool_id')
    assert len(d)==3 and d.loc['b','Q_mean']==3 and pd.isna(d.loc['a','Q_mean'])
    assert 'old48' not in set(d.cohort)


def test_unchanged_secondary_registry_completes_pool_inventory():
    d=pd.read_csv(OUT/'natural_results/UNCHANGED_SECONDARY_REUSE.csv')
    curves=pd.read_csv(OUT/'natural_results/NATURAL_CURVES.csv.gz',usecols=['pool_id'])
    assert len(d)==25 and len(set(curves.pool_id)|set(d.pool_id))==263
    assert not set(curves.pool_id)&set(d.pool_id)
    assert d.same_reference.all() and d.same_members.all() and d.same_input_geometry.all()
    assert d.action.eq('reuse_endpoints').all() and d.natural_orders.gt(0).all()
    for r in d.itertuples():
        assert all((ROOT/r.source_root/path).exists() for path in r.source_tables.split('|'))
