from copy import deepcopy
import pytest
from tools.thesis_main.data_prep.floor_scope_update_20261015 import validate_update


def sample():
    points=[[0,1],[0,2],[1,1],[1,2]]
    record=dict(image_id='i', reference_id='scope:i', original_reference_id='gt:i',
        original_points_1024x512=points, floor_xz_h=[[-1,-1],[1,-1],[1,1],[-1,1]],
        floor_region_confirmed=True, top_boundary_pending=True, reference_ready=False,
        confirmed_at='2026-10-15T10:38:08.679Z')
    return dict(schema='confirmed_floor_scope_update_v1',records=[record]),dict(objects=[dict(object_id='gt:i',image_id='i',points_1024x512=points)])


def test_floor_reference_does_not_require_invented_top_points():
    update,data=sample()
    before=deepcopy(data)
    validate_update(update,data)
    assert before==data


@pytest.mark.parametrize('change',[{'original_reference_id':'wrong'}, {'floor_region_confirmed':False}, {'reference_ready':True}, {'floor_xz_h':[[2,2],[3,2],[3,3],[2,3]]}])
def test_reject_misbound_unconfirmed_or_inapplicable_scope(change):
    update,data=sample();update['records'][0].update(change)
    with pytest.raises((ValueError,KeyError)):
        validate_update(update,data)


def test_current_bundle_exposes_the_received_space_scopes():
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    bundle=load_current_bundle()
    records=bundle['floor_scope_update']['records']
    assert {r['image_code'] for r in records}=={'uNb9QFRL6hY-86','q9vSo1VnCiC-34','pa4otMbVnkk-11','uNb9QFRL6hY-54','S9hNv5qa7GM-09','zsNo4HB9uLZ-13'}
    assert len(records)==6
    assert all(r['scope_semantics']=='whole_space_vertical_boundary' and r['space_scope_confirmed'] for r in records)
    validate_update(bundle['floor_scope_update'],bundle['data'])
