import pandas as pd
import pytest

from tools.thesis_main.analysis.worker_difficulty_profiles_20261018 import add_relative, classify, training_outside, load, OUT


def test_ranks_keep_ties_and_do_not_compare_different_references():
    d = pd.DataFrame({'context_key':['a','a','a','b'], 'worker_id':['w1','w2','w3','w1'], 'B8L2':[80,80,20,99], 'D10':[82,82,23,99]})
    r = add_relative(d)
    assert r.B8L2_rank.tolist()[:3] == [.75,.75,0]
    assert pd.isna(r.B8L2_rank.iloc[3])


def test_specialty_requires_both_hard_performance_and_advantage():
    assert classify(.8,.55,True) == 'hard_advantage'
    assert classify(.8,.8,True) == 'broadly_high'
    assert classify(.55,.2,True) == 'hard_relative_improvement'
    assert classify(.8,.55,False) == 'insufficient'


def test_held_building_and_original_holdout_never_enter_training():
    d=pd.DataFrame({'building_id':['a','b','c'], 'training_allowed':[True,True,False]})
    assert training_outside(d,'a').building_id.tolist() == ['b']


def test_current_labels_full_coverage_and_validation_common_sample():
    d=load()
    assert len(d)==1911 and d.image_id.nunique()==136
    assert set(d[d.image_code.eq('uNb9QFRL6hY-01')].difficulty)=={'medium'}
    main=d[d.panel.eq('manual|ordinary_primary')]
    assert len(main)==1258 and main.image_id.nunique()==103
    assert main.training_allowed.sum()==1048
    assert d.B8L2_rank.dropna().between(0,1).all()
    p=pd.read_csv(OUT/'predictions.csv')
    assert set(p.object_id)<=set(main[main.training_allowed].object_id)
    assert p[['general','specialized','target']].notna().all().all()
    for _,g in p.groupby(['metric','context_key']):
        assert len(g)>=2
        assert abs(g.target.mean())<1e-8
        assert abs(g.general.mean())<1e-8
        assert abs(g.specialized.mean())<1e-8
