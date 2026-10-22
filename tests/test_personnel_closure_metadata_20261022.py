import pytest

from research.workers.personnel_exchange_closure_20261022.build_endpoint_delivery import complete_legacy_geometry


def test_legacy_geometry_receives_only_matching_scalar_metadata():
    scalar = dict(team_key='t', pool_id='p', member_workers='W101|W102', k='2',
                  score_status='below_four', complete_evaluable='False',
                  node_supports='2|2|2', minimum_support='1', reference_id='ref',
                  reference_version='v1')
    old = dict(team_key='t', pool_id='p', member_workers='W101|W102',
               k='', geometry_json='{"points": [[1, 2]]}')
    fixed = complete_legacy_geometry(old, scalar)
    assert fixed == dict(scalar, geometry_json=old['geometry_json'])
    assert old['k'] == ''
    assert complete_legacy_geometry(fixed, scalar) == fixed
    with pytest.raises(AssertionError):
        complete_legacy_geometry(dict(old, member_workers='W103|W104'), scalar)
    with pytest.raises(AssertionError):
        complete_legacy_geometry(dict(old, reference_version='different'), scalar)
