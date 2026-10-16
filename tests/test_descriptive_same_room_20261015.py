import math

import pytest

from tools.thesis_main.analysis import descriptive_same_room_20261015 as module


@pytest.fixture
def registry(monkeypatch):
    def candidate(name, images, supported=True, comparable=True, state='explicit_confirmed'):
        return dict(candidate_id=name, image_ids=images, physical_same_supported=supported,
                    comparable_for_prediction=comparable, oos_pending=False, review_state=state)
    data = dict(images=[dict(image_id=i, building_id='building') for i in 'abcd'],
                room_registry=dict(candidates=[candidate('ab', ['a', 'b']),
                    candidate('bc', ['b', 'c'], comparable=False),
                    candidate('cd', ['c', 'd'], supported=False, state='unreviewed')]))
    monkeypatch.setattr(module, 'load_current_bundle', lambda: {'data': data})


def record(image, worker, score, time=None):
    return dict(object_uid=image+worker, image_id=image, worker_id=worker,
                WQ=score, active_time_seconds=time, reference_id='ref:'+image,
                score_version='fixed', use_panel='ordinary')


def test_frozen_room_metadata_never_reads_the_live_loader(monkeypatch):
    def forbidden():
        raise AssertionError('live loader must not run')
    monkeypatch.setattr(module,'load_current_bundle',forbidden)
    frozen=dict(data=dict(images=[dict(image_id='a')],room_registry=dict(candidates=[])))
    tables=module.build_same_room_tables([record('a','p',80)],bundle=frozen)
    assert tables['same_room_relations']==[]


def test_direct_relations_keep_unscored_views_without_transitive_confirmation(registry):
    tables = module.build_same_room_tables([record('a', 'p', 90)])
    rows = tables['same_room_relations']
    assert [(r['image_a'], r['image_b']) for r in rows] == [('a', 'b'), ('b', 'c'), ('c', 'd')]
    assert [r['relation'] for r in rows] == ['confirmed_comparable', 'supported_other', 'candidate_unconfirmed']
    assert rows[1]['physical_same_explicit_confirmed'] is True
    assert rows[2]['physical_same_supported'] is False
    assert rows[0]['n_records_a'] == 1 and rows[0]['n_records_b'] == 0
    metric = tables['same_room_pair_metrics'][0]
    assert metric['n_pairs'] == 0 and metric['paired_a_mean'] is None


def test_pairs_fix_people_and_report_metric_specific_missingness(registry):
    tables = module.build_same_room_tables([
        record('a', 'p', 90, 0), record('a', 'q', 50, 30), record('a', 'only_a', 0),
        record('b', 'p', 70, 20), record('b', 'q', math.nan, 50), record('b', 'only_b', 100)])
    metrics = {r['metric']: r for r in tables['same_room_pair_metrics'] if r['image_a'] == 'a'}
    quality = metrics['WQ']
    assert quality['n_common_workers'] == 2 and quality['n_pairs'] == 1
    assert quality['n_missing_common_b'] == 1 and quality['n_unpaired_common'] == 1
    assert quality['paired_a_mean'] == 90 and quality['paired_b_mean'] == 70
    assert quality['delta_b_minus_a_mean'] == -20
    assert quality['paired_a_sd'] is None
    time = metrics['active_time_seconds']
    assert time['n_pairs'] == 2 and time['delta_b_minus_a_mean'] == 20
    assert time['paired_a_q25'] == 7.5 and time['paired_a_iqr'] == 15
    assert time['delta_b_minus_a_sd'] == 0
    detail = tables['same_room_worker_pairs'][0]
    assert detail['object_uid_a'] == 'ap' and detail['reference_id_b'] == 'ref:b'


def test_duplicate_person_image_or_object_is_not_silently_averaged(registry):
    with pytest.raises(ValueError, match='duplicate'):
        module.build_same_room_tables([record('a', 'p', 80), record('a', 'p', 90)])
    with pytest.raises(ValueError, match='unknown image'):
        module.build_same_room_tables([record('unknown', 'p', 80)])


def test_unannotated_relation_views_use_original_registry_metadata(monkeypatch):
    candidate = dict(candidate_id='g', image_ids=['a', 'b', 'c'],
                     physical_same_supported=True, comparable_for_prediction=True,
                     oos_pending=False, review_state='explicit_confirmed')
    data = dict(images=[dict(image_id='a', building_id='house', image_code='house-01')],
                room_registry=dict(candidates=[candidate], images=[
                    dict(image_id='a', building='house', number=1),
                    dict(image_id='b', building='house', number=12)]))
    monkeypatch.setattr(module, 'load_current_bundle', lambda: {'data': data})
    tables = module.build_same_room_tables([])
    first = tables['same_room_relations'][0]
    assert first['building_b'] == 'house' and first['image_code_b'] == 'house-12'
    assert first['image_metadata_source_b'] == 'room_registry.images'
    assert tables['same_room_pair_metrics'][0]['image_code_b'] == 'house-12'
    assert tables['same_room_relations'][1]['image_code_b'] == 'unknown'
    data['images'][0]['image_code'] = 'house-02'
    with pytest.raises(ValueError, match='metadata mismatch'):
        module.build_same_room_tables([])
