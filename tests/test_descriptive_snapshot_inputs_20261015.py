import json

import pandas as pd
import pytest

from tools.thesis_main.analysis.descriptive_snapshot_inputs_20261015 import build_snapshot, run


def fixture_manifest(tmp_path):
    records = pd.DataFrame([
        dict(object_id='o1', image_id='i', worker_id='new-person', condition='manual',
             reference_id='ref', use_panel='ordinary', active_time_seconds='10', time_status='usable',
             time_source='active_logs/test', WQ='10', B='20'),
        dict(object_id='o2', image_id='i', worker_id='w2', condition='manual',
             reference_id='ref', use_panel='ordinary', active_time_seconds='', time_status='missing',
             time_source='', WQ='30', B=''),
        dict(object_id='o3', image_id='new-image', worker_id='w2', condition='manual',
             reference_id='', use_panel='not_scored', active_time_seconds='', time_status='missing',
             time_source='', WQ='', B='')])
    records['time_source_file'] = records.time_source
    records['time_rule_version'] = records.time_source.map(lambda v: 'time-v1' if v else '')
    records.to_csv(tmp_path / 'records.csv', index=False)
    pd.DataFrame([dict(image_id='i', difficulty_class='简单'),
                  dict(image_id='new-image', difficulty_class='待核')]).to_csv(tmp_path / 'images.csv', index=False)
    manifest = dict(batches=[dict(batch_id='batch', input_version='input-v1', reference_version='ref-v1',
                                 records_csv='records.csv', images_csv='images.csv')],
                    algorithms=[dict(algorithm_id=name, version='v1', source_csv='records.csv',
                                     value_column=column, input_version='input-v1',
                                     reference_version='ref-v1', minimum=0, maximum=100,
                                     direction='higher_is_better') for name, column in [('WQ', 'WQ'), ('B', 'B')]])
    return manifest


def test_partial_coverage_and_common_reference_set(tmp_path):
    manifest = fixture_manifest(tmp_path)
    tables = build_snapshot(manifest, tmp_path)
    assert len(tables['snapshot_inputs']) == 3
    assert len(tables['score_measurements']) == 6
    coverage = tables['algorithm_coverage'].query("algorithm_id == 'B' and coverage_layer == 'all_inputs'").iloc[0]
    assert (coverage.n_records, coverage.n_valid, coverage.n_missing) == (3, 1, 2)
    pairs = tables['algorithm_common_comparisons'].query("use_panel == 'ordinary'")
    assert pairs.iloc[0].n_valid == 1
    assert abs(pairs.iloc[0]['mean']) == 10
    manifest['algorithms'][1]['reference_version'] = 'ref-v2'
    with pytest.raises(ValueError, match='reference_version'):
        build_snapshot(manifest, tmp_path)


def test_new_batch_worker_image_and_partial_algorithm(tmp_path):
    manifest = fixture_manifest(tmp_path)
    extra = pd.DataFrame([dict(object_id='o4', image_id='later-image', worker_id='later-worker',
                              condition='manual', reference_id='later-ref', use_panel='ordinary',
                              active_time_seconds='12', time_status='usable', time_source='active_logs/later')])
    extra['time_source_file'] = 'active_logs/later/events.jsonl'
    extra['time_rule_version'] = 'time-v1'
    extra.to_csv(tmp_path / 'later.csv', index=False)
    pd.DataFrame([dict(image_id='later-image', difficulty_class='中等')]).to_csv(tmp_path / 'later-images.csv', index=False)
    manifest['batches'].append(dict(batch_id='later', input_version='input-v1', reference_version='ref-v1',
                                    records_csv='later.csv', images_csv='later-images.csv'))
    extra.assign(C='60').to_csv(tmp_path / 'partial-scores.csv', index=False)
    manifest['algorithms'].append(dict(manifest['algorithms'][0], algorithm_id='C',
                                       source_csv='partial-scores.csv', value_column='C'))
    tables = build_snapshot(manifest, tmp_path)
    assert len(tables['snapshot_inputs']) == 4
    assert tables['snapshot_inputs'].worker_id.nunique() == 3
    assert len(tables['score_measurements']) == 12
    coverage = tables['algorithm_coverage'].query("algorithm_id == 'C' and coverage_layer == 'all_inputs'").iloc[0]
    assert (coverage.n_valid, coverage.n_missing, coverage.n_source_rows) == (1, 3, 1)
    assert tables['algorithm_common_comparisons'].query("right_algorithm == 'C'").n_valid.eq(0).all()
    manifest['batches'][1]['input_version'] = 'input-v2'
    manifest['algorithms'][2]['input_version'] = 'input-v2'
    separate = build_snapshot(manifest, tmp_path)['algorithm_common_comparisons']
    assert not separate.left_algorithm.eq('C').any() and not separate.right_algorithm.eq('C').any()
    manifest['batches'][1]['input_version'] = 'input-v1'
    manifest['algorithms'][2]['input_version'] = 'input-v1'
    manifest['batches'][1]['reference_version'] = 'ref-v2'
    manifest['algorithms'][2]['reference_version'] = 'ref-v2'
    separate = build_snapshot(manifest, tmp_path)['algorithm_common_comparisons']
    assert not separate.left_algorithm.eq('C').any() and not separate.right_algorithm.eq('C').any()


def test_new_worker_on_same_image_ignores_old_coverage_counts(tmp_path):
    manifest = fixture_manifest(tmp_path)
    extra = pd.read_csv(tmp_path / 'records.csv', keep_default_na=False).iloc[:1].copy()
    extra['object_id'], extra['worker_id'] = 'extra-object', 'extra-worker'
    extra.to_csv(tmp_path / 'later.csv', index=False)
    original = pd.read_csv(tmp_path / 'images.csv', keep_default_na=False)
    original['all_answer_count'] = '3'
    original.to_csv(tmp_path / 'images.csv', index=False)
    original['all_answer_count'] = '999'
    original.to_csv(tmp_path / 'later-images.csv', index=False)
    manifest['batches'].append(dict(batch_id='later', input_version='input-v1', reference_version='ref-v1',
                                    records_csv='later.csv', images_csv='later-images.csv'))
    assert len(build_snapshot(manifest, tmp_path)['snapshot_inputs']) == 4


@pytest.mark.parametrize('field,value,error', [
    ('worker_id', 'impostor', 'identity'), ('reference_id', 'wrong-reference', 'reference'),
    ('input_version', 'wrong-version', 'input_version'), ('WQ', '101', 'range')])
def test_rejects_score_identity_and_version_drift(tmp_path, field, value, error):
    manifest = fixture_manifest(tmp_path)
    scores = pd.read_csv(tmp_path / 'records.csv', keep_default_na=False)
    scores.loc[0, field] = value
    scores.to_csv(tmp_path / 'scores.csv', index=False)
    manifest['algorithms'][0]['source_csv'] = 'scores.csv'
    with pytest.raises(ValueError, match=error):
        build_snapshot(manifest, tmp_path)


def test_rejects_duplicate_objects_image_conflicts_and_overwrite(tmp_path):
    manifest = fixture_manifest(tmp_path)
    manifest['batches'].append({**manifest['batches'][0], 'batch_id': 'second'})
    with pytest.raises(ValueError, match='duplicate object_id'):
        build_snapshot(manifest, tmp_path)
    manifest['batches'].pop()
    data = pd.read_csv(tmp_path / 'records.csv', keep_default_na=False)
    data['difficulty_class'] = '困难'
    data.to_csv(tmp_path / 'records.csv', index=False)
    with pytest.raises(ValueError, match='image axis conflict'):
        build_snapshot(manifest, tmp_path)
    data.drop(columns='difficulty_class').to_csv(tmp_path / 'records.csv', index=False)
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    run(tmp_path / 'manifest.json', tmp_path / 'out')
    locations = json.loads((tmp_path/'out/SOURCE_LOCATIONS.json').read_text(encoding='utf-8'))
    assert locations['manifest_origin'] == str((tmp_path/'manifest.json').resolve())
    assert locations['batches'][0]['records_csv'] == str((tmp_path/'records.csv').resolve())
    with pytest.raises(FileExistsError):
        run(tmp_path / 'manifest.json', tmp_path / 'out')


def test_unbound_score_and_duplicate_measurement_rejected(tmp_path):
    manifest = fixture_manifest(tmp_path)
    records = pd.read_csv(tmp_path / 'records.csv', keep_default_na=False)
    records.loc[2, 'WQ'] = '25'
    records.to_csv(tmp_path / 'records.csv', index=False)
    with pytest.raises(ValueError, match='unbound reference'):
        build_snapshot(manifest, tmp_path)
    records.loc[2, 'WQ'] = ''
    records.to_csv(tmp_path / 'records.csv', index=False)
    manifest['algorithms'].append(manifest['algorithms'][0])
    with pytest.raises(ValueError, match='duplicate measurement'):
        build_snapshot(manifest, tmp_path)


def test_missing_identity_and_active_time_source_are_not_silently_accepted(tmp_path):
    manifest = fixture_manifest(tmp_path)
    records = pd.read_csv(tmp_path / 'records.csv', keep_default_na=False)
    records.drop(columns='condition').to_csv(tmp_path / 'records.csv', index=False)
    with pytest.raises(ValueError, match='missing fields'):
        build_snapshot(manifest, tmp_path)
    records.loc[0, 'time_source'] = ''
    records.to_csv(tmp_path / 'records.csv', index=False)
    with pytest.raises(ValueError, match='active_time_seconds'):
        build_snapshot(manifest, tmp_path)


@pytest.mark.parametrize('field,value', [('active_time_seconds', '0'),
                                       ('time_source', 'lead_time_fallback'),
                                       ('time_source_file', ''), ('time_rule_version', '')])
def test_usable_time_requires_positive_value_and_provenance(tmp_path, field, value):
    manifest = fixture_manifest(tmp_path)
    records = pd.read_csv(tmp_path / 'records.csv', keep_default_na=False)
    records.loc[0, field] = value
    records.to_csv(tmp_path / 'records.csv', index=False)
    with pytest.raises(ValueError, match='active_time_seconds'):
        build_snapshot(manifest, tmp_path)
