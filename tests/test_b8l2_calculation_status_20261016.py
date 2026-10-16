from copy import deepcopy

import pytest

from tools.thesis_main.analysis.layout_foundation_20260930 import synthetic_record
from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine
from tools.thesis_main.analysis.b8l2_calculation_status_20261016 import inspect_geometry, measure_status


@pytest.fixture(scope='module')
def engine():
    with scoring_engine() as (engine,models):
        yield engine


def obj():
    return dict(object_id='o',points_1024x512=synthetic_record([[-2,-2],[2,-2],[2,2],[-2,2]],3)['points'],
                geometry=dict(status='legacy_other'),ring_confirmed=False)


def test_actual_route_support_ignores_legacy_status_and_unconfirmed_ring(engine):
    record=obj();before=deepcopy(record)
    result=inspect_geometry(record,engine)
    assert result['input_geometry_status']=='full_geometry_available'
    assert result['full_input_available'] and result['floor_input_available']
    assert record==before


def test_only_bottom_remains_available_when_top_is_missing_or_unpaired(engine):
    record=obj();record['points_1024x512'][0][1]=float('nan')
    result=inspect_geometry(record,engine)
    assert result['floor_input_available'] and not result['full_input_available']
    assert result['input_geometry_status']=='floor_only_available'
    assert len(result['floor_xz_h'])==4
    record=obj();record['points_1024x512'][0][0]+=10
    result=inspect_geometry(record,engine)
    assert result['floor_input_available'] and not result['full_input_available']
    assert 'top_bottom_longitude_mismatch_not_repaired' in result['reasons']


def test_insufficient_unpaired_and_degenerate_are_distinct(engine):
    record=obj();record['points_1024x512']=record['points_1024x512'][:4]
    assert inspect_geometry(record,engine)['input_geometry_status']=='insufficient_paired_points'
    record=obj();record['points_1024x512'].pop()
    assert inspect_geometry(record,engine)['input_geometry_status']=='unpaired_points'
    record=obj();record['points_1024x512']=record['points_1024x512'][:2]*3
    assert not inspect_geometry(record,engine)['floor_input_available']


def test_not_run_and_reference_pending_are_not_measurement_failures(engine):
    task=dict(annotation_points=obj()['points_1024x512'],reference_points=None)
    assert measure_status(task,engine)['measurement_status']=='not_run'
    result=measure_status(task,engine,run=True)
    assert result['reference_status']=='missing_full_reference'
    assert not result['measurement_attempted'] and not result['calculation_failed']
    task['reference_points']=deepcopy(task['annotation_points'])
    measured=measure_status(task,engine,run=True)
    assert measured['measurement_status']=='complete' and measured['measurement_attempted']
    assert not measured['calculation_failed']
