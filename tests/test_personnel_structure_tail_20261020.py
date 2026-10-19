from tools.thesis_main.analysis.personnel_structure_tail_20261020 import pair_stats


def test_equal_count_and_recall_do_not_hide_different_nodes():
    a={'nodes':4,'complete_evaluable':True,'B8L2':80,'reference_nodes':6}
    b=dict(a,B8L2=85)
    for t in [5,9]:
        a[f'ref_matched_nodes_{t}']=[0,1,2,3];b[f'ref_matched_nodes_{t}']=[0,1,2,4]
        a[f'ref_matched_edges_{t}']=[1,8];b[f'ref_matched_edges_{t}']=[1,9]
    r=pair_stats(a,b)
    assert not r['count_changed'] and r['Q_delta']==5
    assert r['node_set_difference_9']==2/6 and r['node_lost_9']==1 and r['node_gained_9']==1


def test_missing_diagnostics_stay_unknown_and_failure_is_recorded():
    a={'nodes':4,'complete_evaluable':True,'B8L2':80,'reference_nodes':6}
    b=dict(a,nodes=3,complete_evaluable=False,B8L2=None)
    r=pair_stats(a,b)
    assert r['count_changed'] and r['incomplete'] and r['count_change_or_incomplete']
    assert r['node_set_difference_9'] is None and r['Q_delta'] is None
