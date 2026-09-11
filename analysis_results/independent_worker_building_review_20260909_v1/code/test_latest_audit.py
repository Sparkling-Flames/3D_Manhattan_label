import numpy as np
import pandas as pd
import pytest
import latest_audit as a

def test_ospa_identical_order_free():
    p=[[100.,100.],[400.,400.],[900.,200.]]
    assert a.ospa(p,p[::-1],30)<1e-12

def test_ospa_cardinality_penalty():
    assert np.isclose(a.ospa([[100.,100.]],[[100.,100.],[100.,100.]],30),15.)

def test_effects_identified_with_item_offsets():
    data=pd.DataFrame([dict(context_key=str(i),worker_id=str(w),v=float(i*10+w-1)) for i in range(4) for w in range(3)])
    assert np.allclose(a.fit_effect(data,'v'),[-1,0,1])

def test_disconnected_graph_fails():
    d=pd.DataFrame([dict(context_key='a' if w<2 else 'b',worker_id=str(w),v=w) for w in range(4)])
    with pytest.raises(ValueError):a.fit_effect(d,'v')

def test_missing_requested_worker_fails():
    d=pd.DataFrame([dict(context_key='a',worker_id=str(w),v=w) for w in range(3)])
    with pytest.raises(ValueError):a.fit_effect(d,'v',['0','1','2','3'])

def test_suffix_crossing_not_first_crossing():
    assert a.onset([1,2,3,4],[.9,.7,.8,.9],[.9,.7,.8,.9])==(3.,3.,'identified')

def test_no_finite_crossing_not_zero():
    x=a.onset([1,2],[.1,.2],[.3,.4]);assert np.isnan(x[0]) and np.isnan(x[1]) and x[2]=='not_reached'

def test_nested_TV_bound_attained():
    for k in [1,5,20]:
        for h in [1,3,5]:
            assert np.isclose(.5*np.abs(np.array([1.,0])-np.array([k/(k+h),h/(k+h)])).sum(),h/(k+h))
