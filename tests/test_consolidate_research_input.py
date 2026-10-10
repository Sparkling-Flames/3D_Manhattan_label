import pytest

from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle, validate_bundle


def test_bundle_consistency_and_corruption_rejected():
    b=load_current_bundle()
    v=b['validation']
    assert v['status']=='passed'
    assert (v['objects'],v['annotations'],v['research_images'],v['reference_only_images'],v['confirmed_orders'])==(3441,3152,259,2,1312)
    assert v['comment_occurrences']==b['comments']['summary']['occurrences']
    assert len(b['manifest']['additional_tables'])>=20
    o=next(o for o in b['data']['objects'] if o['preprocessing_status']=='ready')
    o['preprocessed_points'][0][1]+=1
    with pytest.raises(ValueError,match='shared_x_or_y_mismatch'):
        validate_bundle(b['data'],b['research'],b['comments'],b['final_summary'])
