import pytest
from tools.thesis_main.analysis.audit_participant_support_20260909 import project_people, composition_support


def test_building_projection_does_not_borrow_responses_from_other_images():
    h,v=project_people({'1','3','5'},['1','2','3'],['4','5','6'],{'1','5'})
    assert h==['1'] and v==['5']
    with pytest.raises(ValueError):project_people({'1'},['1'],['1'],{'1'})
    with pytest.raises(ValueError):project_people({'7'},['1'],['2'],{'7'})


def test_balanced_four_is_not_four_way_four_person_comparison():
    assert composition_support(2,2,2,4)==(True,False)
    assert composition_support(4,4,2,4)==(True,True)
    assert composition_support(4,4,1,4)==(False,False)
    assert composition_support(1,1,2,2)==(True,False)
