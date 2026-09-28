from tools.thesis_main.analysis.audit_review_return_20260927 import missing_disposition, cluster_binding, trap_classification


def test_missing_individual_exclusion_not_hidden_by_image_resolution():
    assert missing_disposition([{'verdict':'invalid'}], [], {}, {'status':'resolved'})[0]=='excluded_unreviewed'
    assert missing_disposition([{'verdict':'retain'}], [], {}, {'status':'resolved'})[0]=='image_context_inherited'
    assert missing_disposition([], [{'status':'proposed_not_applied'}], {}, {'status':'resolved'})[0]=='repair_unreviewed'
    assert missing_disposition([{'verdict':'pending','comment':'p7没标好','interpretation':{'targets':['annotation']}}], [], {}, {'status':'resolved'})[0]=='individual_unreviewed'
    assert missing_disposition([{'verdict':'pending','comment':'范围不同','interpretation':{'targets':['annotation','image']}}], [], {}, {'status':'resolved'})[0]=='image_context_inherited'


def test_cluster_comment_freezes_worker_condition_and_coordinates():
    s={'worker_id':'W034','condition':'manual','clusters':{'affinity':1,'complete':2},'effective_points':[[1,2]]}
    b=cluster_binding('簇1和簇3有疑问', {'answer':s})
    assert b['groups']['1'][0]['annotation_id']=='answer'
    assert b['groups']['1'][0]['condition']=='manual'
    assert b['groups']['1'][0]['effective_points']==[[1,2]]
    assert b['point_version']=='shared_x'
    assert b['unresolved_labels']==['3']


def test_trap_setting_separate_from_geometry_and_missing_fields():
    assert trap_classification({'semi_role':'trap','source_type':'trap_natural'})[:2]==('confirmed_trap','natural')
    assert trap_classification({'semi_role':'control','source_type':'control_natural'})[0]=='confirmed_nontrap'
    assert trap_classification({'condition':'manual'})[0]=='unknown'
    assert trap_classification({'semi_role':'control','source_type':'trap_synthetic'})[0]=='unknown'
