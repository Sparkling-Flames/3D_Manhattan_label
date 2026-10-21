import importlib.util
from pathlib import Path
import numpy as np

P=Path(__file__).resolve().parents[1]/'tools/thesis_main/analysis/same_room_stopping_review_20261021.py'
spec=importlib.util.spec_from_file_location('stopping_review',P)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_earliest_near_peak_and_threshold_sensitivity():
    s=np.array([[70,88,90,89],[80,79,77,76]])
    assert m.choose_prefix(s,[1,3,4,5],0).tolist()==[4,1]
    assert m.choose_prefix(s,[1,3,4,5],2).tolist()==[3,1]

def test_missing_source_does_not_select_missing_prefix():
    s=np.array([[np.nan,88,90],[np.nan,np.nan,np.nan]])
    assert m.choose_prefix(s,[1,3,4],2).tolist()==[3,-1]

def test_targets_cannot_affect_choice():
    source=np.array([[80,90,91]])
    # The choice interface accepts source values only, never targets.
    assert m.choose_prefix(source,[1,3,4],2).tolist()==[3]

def test_splits_strict_majority_and_no_leakage():
    for n in range(3,10):
        for h,t in m.splits(n):
            assert len(h)>n/2 and len(t)>0 and not set(h)&set(t)
            assert set(h)|set(t)==set(range(n))

def test_source_average_requires_every_history_view():
    values=np.array([[[90.,91.]],[[np.nan,89.]]])
    source=values.mean(axis=0)
    assert m.choose_prefix(source,[1,3],5).tolist()==[3]

def test_common_support_is_invariant_to_history():
    values=np.ones((4,2,3))
    values[3,1,2]=np.nan
    common=np.isfinite(values).all(axis=(0,2))
    assert common.tolist()==[True,False]
    for history,targets in m.splits(4):
        assert common.tolist()==[True,False]

def test_monotone_tolerance_never_increases_cost():
    rng=np.random.default_rng(724)
    source=rng.normal(85,7,(100,10));source[0,:]=np.nan
    ks=[1,3,4,5,6,7,8,9,10,11]
    choices=[m.choose_prefix(source,ks,t) for t in (0,1,2,5)]
    assert all(np.all(b<=a) for a,b in zip(choices,choices[1:]))

