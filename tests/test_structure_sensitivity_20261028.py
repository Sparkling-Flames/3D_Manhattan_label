import numpy as np
import pandas as pd
from tools.thesis_main.analysis.structure_condition_curves_20261028 import condition, complete_curve
from tools.thesis_main.analysis.dstruct_definition_sensitivity_20261028 import align_labels, strict_relation, decompose, balanced_images


def test_conditions_not_difficulty_and_missing_curve():
    d=pd.DataFrame(dict(ref_turn5=[6,6,6],ref_H=[0,0,1],ref_short_edges=[0,1,1]))
    assert condition(d).tolist()==['plain_H0','short_H0','H_positive']
    c=pd.DataFrame(dict(pool_id=['a','a','b','b'],point=['1','full']*2,value=[1,np.nan,2,3]))
    assert complete_curve(c,['1','full'])=={'b'}


def test_alignment_does_not_change_partition():
    lab=np.array(['C3','C3','C1','C2']);ref=np.array(['C1','C1','C2','C3'])
    aligned,_=align_labels(lab,ref)
    np.testing.assert_array_equal(aligned,ref)


def test_invalid_abc_not_retained():
    r=dict(D='d',X='a|b',Y='c|e',Z='f|g',m=2,A_members='d|a|b',B_members='d|c|e',C_members='d|f|g')
    lab=dict(a='C1',b='C1',c='C1',e='C1',f='C2',g='C2')
    assert strict_relation(r,lab)==(True,'strict_ABC')
    lab['g']='C1';assert strict_relation(r,lab)==(False,'mixed_block')
    del lab['g'];assert strict_relation(r,lab)==(False,'unknown_block_member')


def test_variance_weights_keep_repeated_team_occurrence():
    a=decompose([0,0,2,4],['a','a','a','b'])
    assert a['valid']==4
    assert np.isclose(a['total'],2.75)
    assert np.isclose(a['total'],a['between']+a['within'])


def test_abc_balances_background_levels_before_blocks():
    d=pd.DataFrame(dict(method=['m']*4,building=['b']*4,image=['i']*4,
        block_id=['x','x','x','y'],background_target_n=[0,0,1,0],
        within=[0,0,4,8],cross=[0,0,4,8],gap=[0]*4,CB=[0]*4))
    r=balanced_images(d,['method'])
    assert r.within.iloc[0]==5 and r.events.iloc[0]==4
