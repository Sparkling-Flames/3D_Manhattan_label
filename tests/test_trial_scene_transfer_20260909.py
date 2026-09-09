import numpy as np
import pytest
from scipy.optimize import linprog
from tools.thesis_main.analysis.trial_scene_transfer_20260909 import transport, image_splits, predict


def test_uniform_transport_matches_independent_linear_program():
    cost=np.array([[0.,2.,7.],[4.,1.,3.]])
    constraints=[]
    for i in range(2):
        row=np.zeros((2,3));row[i,:]=1;constraints.append(row.ravel())
    for j in range(3):
        row=np.zeros((2,3));row[:,j]=1;constraints.append(row.ravel())
    reference=linprog(cost.ravel(),A_eq=constraints,b_eq=[.5,.5,1/3,1/3,1/3],bounds=(0,None),method='highs')
    assert reference.success
    assert transport(cost)==pytest.approx(reference.fun)
    assert transport(cost.T)==pytest.approx(reference.fun)
    assert transport(np.array([[0.,9.],[9.,0.]]))==0
    with pytest.raises(ValueError):transport(np.empty((0,2)))


def test_image_splits_are_disjoint_complete_and_directional():
    folds=list(image_splits(list('abcdef')))
    assert len(folds)==62
    assert sum(len(s)==3 for s,t in folds)==20
    assert all(set(s).isdisjoint(t) and set(s+t)==set('abcdef') for s,t in folds)
    with pytest.raises(ValueError):list(image_splits(['a','a','b']))


def test_prediction_never_reads_held_out_values():
    values={'a':np.array([3.,2.]),'b':np.array([5.,4.]),'c':np.array([9.,8.])}
    before=predict(['a','b'],values)
    values['c']=np.array([-999.,999.])
    assert np.array_equal(before,predict(['a','b'],values))
    assert np.array_equal(before,[4.,3.])


def test_reference_error_preserves_reference_draw_and_target_axes():
    from tools.thesis_main.analysis.review_scene_transfer_trial_20260909 import reference_errors
    result=reference_errors([[0,2],[2,4]],[[1,3],[5,7],[0,2]])
    assert np.array_equal(result,[[1,5,0],[1,3,2]])
