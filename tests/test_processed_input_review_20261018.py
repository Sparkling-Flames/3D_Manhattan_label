import copy

from tools.thesis_main.analysis.apply_pairing_preprocessing_20260929 import raw_initial_points


def test_confirmed_coordinate_repair_survives_raw_initialization():
    obj = dict(object_id='confirmed', before_preprocessing_points=[[20, 30], [22, 390]],
               original_export_points=[[20, 30], [22, 3900]], point_labels=['p1', 'p2'],
               repair_evidence=[dict(status='applied', changed_points=[
                   dict(label='p2', before=[22, 3900], after=[22, 390])])])
    points, indices, notes = raw_initial_points(obj)
    assert points == [[20, 30], [22, 390]]
    assert indices == [0, 1]
    assert notes
    # A proposal has no authority; the later shared-x policy still uses raw x.
    proposed = copy.deepcopy(obj)
    proposed['repair_evidence'][0]['status'] = 'proposed_not_applied'
    assert raw_initial_points(proposed)[0][1] == [22, 3900]
    moved_x = dict(object_id='x', before_preprocessing_points=[[20, 30], [20, 390]],
                   original_export_points=[[20, 30], [22, 390]], point_labels=['p1', 'p2'],
                   repair_evidence=dict(status='applied_effective_override', operation='p2.x=p1.x'))
    assert raw_initial_points(moved_x)[0] == [[20, 30], [22, 390]]


def test_coordinate_repair_must_bind_the_recorded_before_value():
    import pytest
    obj = dict(object_id='bad_binding', before_preprocessing_points=[[20, 390]],
               original_export_points=[[20, 3900]], point_labels=['p1'],
               repair_evidence=[dict(status='applied', changed_points=[
                   dict(label='p1', before=[20, 999], after=[20, 390])])])
    with pytest.raises(ValueError, match='coordinate_repair_binding'):
        raw_initial_points(obj)


def test_revision_preserves_all_other_objects_and_current_bundle_contract():
    from tools.thesis_main.data_prep.review_processed_input_20261018 import (
        OUT, SOURCE, apply_confirmed_repairs, load_current_bundle)
    original = load_current_bundle(SOURCE)
    before = copy.deepcopy(original['data']['objects'])
    changed = apply_confirmed_repairs(original)
    assert [r['object_id'] for r in changed] == ['8ffe08f072e2b12e']
    revised = load_current_bundle(OUT/'manifest.json')
    assert revised['data']['objects'] == original['data']['objects']
    for old, new in zip(before, revised['data']['objects']):
        if old['object_id'] != '8ffe08f072e2b12e':
            assert old == new
        else:
            assert old['original_export_points'] == new['original_export_points']
            assert new['before_preprocessing_points'][7][1] == 389.7282406015037
            assert new['geometry']['status'] == 'surface_valid'
            for key in ('cleaning_disposition','independent_vote_eligible','main_quality_gate',
                        'worker_quality_gate','links_zero_based','ordered_source_pair_indices'):
                assert old[key] == new[key]
    deletion = next(o for o in revised['data']['objects'] if o['object_id']=='9b8f8bec4da82b48')
    assert 'p7' not in deletion['point_labels'] and len(deletion['point_labels']) == 20


def test_scored_context_applies_delta_only_to_corrected_input_revision():
    from tools.thesis_main.analysis.current_annotation_context_20261017 import load_scored_context
    from tools.thesis_main.data_prep.review_processed_input_20261018 import OUT, SOURCE, load_current_bundle
    old = load_scored_context(load_current_bundle(SOURCE))
    new = load_scored_context(load_current_bundle(OUT/'manifest.json'))
    old_rows = {r['object_id']:r for r in old['quality_records']}
    new_rows = {r['object_id']:r for r in new['quality_records']}
    oid='8ffe08f072e2b12e'
    assert old_rows[oid]['calculation_status'] == 'pending_target'
    assert new_rows[oid]['calculation_status'] == 'full_computed'
    assert new_rows[oid]['full_input_available'] is True
    assert new_rows[oid]['quality_usable'] is False
    assert new_rows[oid]['B8L2'] is None
    assert float(new_rows[oid]['diagnostic_B8L2']) > 85
    old_qualified={k:r for k,r in old_rows.items() if r['quality_usable']}
    new_qualified={k:r for k,r in new_rows.items() if r['quality_usable']}
    assert len(old_qualified) == 1911
    assert old_qualified == new_qualified
