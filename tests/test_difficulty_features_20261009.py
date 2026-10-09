import csv
import json

import pytest

from tools.thesis_main.analysis import difficulty_features_20261009 as features


def fixture_sources(tmp_path, monkeypatch, *, floor_status='computable', floor='0'):
    monkeypatch.setattr(features, 'ROOT', tmp_path)
    files = {
        features.FEATURE_SOURCE: ('image_id', 'd_model_feat_static'),
        features.BILAYOUT_SOURCE: ('image_id', 'floor', 'floor_status', 'band', 'band_status'),
        features.GEOMETRY_SOURCE: ('layout_id', 'floor_ok', 'floor_failure'),
    }
    values = {
        features.FEATURE_SOURCE: [['a', '4.5']],
        features.BILAYOUT_SOURCE: [['a', floor, floor_status, '0.3', 'computable']],
        features.GEOMETRY_SOURCE: [['offline', 'True', '']],
    }
    for relative, header in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.writer(stream)
            writer.writerow(header)
            writer.writerows(values[relative])
    path = tmp_path / features.MODEL_SOURCE
    path.parent.mkdir(parents=True, exist_ok=True)
    model = dict(image_id='a', model_family='HoHoNet', source_role='offline_ep300_replay',
                 layout_id='offline', source_path='prediction/a.txt', source_exists=True,
                 coordinate_width=1024, coordinate_height=512,
                 points_1024x512=[[10, 100], [10, 400], [300, 100], [300, 400]])
    legacy = dict(model, source_role='candidate_prescreen_legacy_output', layout_id='legacy',
                  points_1024x512=[[10, 100], [10, 400]] * 5)
    path.write_text('\n'.join(json.dumps(r) for r in [model, legacy]), encoding='utf-8')
    return {'research': {'images': [
        dict(image_id='a', image_code='A', building_id='verified-building', room_id='G1'),
        dict(image_id='b', image_code='B', building_id='other-building', room_id='G2'),
    ]}}


def test_model_source_roles_missing_and_true_zero(tmp_path, monkeypatch):
    bundle = fixture_sources(tmp_path, monkeypatch)
    rows = features.extract_features(bundle)
    a, b = rows
    assert a['hohonet_offline_pair_count'] == 2
    assert a['hohonet_legacy_pair_count'] == 5
    assert a['bilayout_floor_gap'] == 0.0
    assert a['d_model_feat_static'] == 4.5
    assert a['building'] == 'verified-building'
    assert a['hohonet_fallback_status'] == 'unknown_not_recorded'
    assert a['hohonet_floor_valid'] is True
    assert all(b[name] is None for name in features.SCORE_FEATURES)
    assert b['model_available'] is False
    assert 'difficulty' not in a


def test_uncomputable_geometry_is_missing_not_zero(tmp_path, monkeypatch):
    bundle = fixture_sources(tmp_path, monkeypatch, floor_status='invalid_original_order_polygon', floor='nan')
    row = features.extract_features(bundle)[0]
    assert row['bilayout_floor_gap'] is None
    assert row['bilayout_floor_status'] == 'invalid_original_order_polygon'
    assert row['bilayout_legacy_band'] == .3


def test_nonfinite_computable_feature_is_reported(tmp_path, monkeypatch):
    bundle = fixture_sources(tmp_path, monkeypatch, floor='nan')
    with pytest.raises(ValueError, match='nonfinite_model_field'):
        features.extract_features(bundle)


def test_labels_and_worker_annotations_cannot_change_features(tmp_path, monkeypatch):
    bundle = fixture_sources(tmp_path, monkeypatch)
    expected = features.extract_features(bundle)
    bundle['research']['images'][0]['difficulty'] = '困难'
    bundle['data'] = {'objects': [{'object_kind': 'annotation', 'points_1024x512': [[1, 2]] * 80}]}
    assert features.extract_features(bundle) == expected
