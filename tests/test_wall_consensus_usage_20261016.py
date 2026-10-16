from tools.thesis_main.analysis.wall_consensus_usage_20261016 import eligibility


def row(**changes):
    base = dict(k=5,below_four=False,connection_available=True,full_reference_available=True,
        floor_evaluable=True,source_pool_allowed=True,primary_comparison_eligible=True,
        use='ordinary_conditional',score_status='complete_conditional',
        iou_2d=.9,S_bottom_deg=1,dir=2,Hmean=.1,Hcenter=.1,IoU3D100=80)
    return dict(base,**changes)


def test_complete_oos_has_numbers_but_never_quality_use():
    value = eligibility(row(), 'oos')
    assert value['computability']=='complete_numeric'
    assert not value['reference_quality_scene_allowed'] and not value['primary_comparison_eligible']
    assert value['geometry_stability_available']


def test_doorway_can_score_but_deferred_and_missing_are_distinct():
    assert eligibility(row(),'doorway_difficult')['reference_quality_scene_allowed']
    value=eligibility(row(k=2,Hmean=None,IoU3D100=None),'oos')
    assert value['computability']=='not_run_two_person_order_deferred'
    value=eligibility(row(Hmean=None,IoU3D100=None,full_reference_available=False),'oos')
    assert value['computability']=='floor_only_reference'
    value=eligibility(row(Hmean=None,IoU3D100=None,below_four=True),'doorway_difficult')
    assert value['computability']=='insufficient_nodes'
