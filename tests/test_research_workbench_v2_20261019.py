import pytest
import json
from pathlib import Path
import pandas as pd
from tools.thesis_main.analysis import build_research_workbench_v2_20261019 as builder
from tools.thesis_main.analysis.build_research_workbench_v2_20261019 import load_same_room_prediction


def test_prediction_display_preserves_missing_values_and_source_target(tmp_path):
    columns = ['source_image', 'target_image', 'worker_id', 'actual', 'predicted', 'warm_start']
    (tmp_path / 'FIELD_CONTRACT.json').write_text(json.dumps({'tables': {'predictions.csv': columns}}))
    source = tmp_path / 'predictions.csv'
    source.write_text(','.join(columns) + '\ns,t,W100,12.5,,False\n')
    row = load_same_room_prediction(tmp_path)['same_room_prediction__predictions'][0]
    assert row['image_a'] == 's' and row['image_b'] == 't'
    assert row['condition'] == 'manual' and row['worker_id'] == 'W100'
    assert row['actual'] == 12.5 and row['predicted'] is None
    assert row['warm_start'] is False
    source.write_text('source_image,target_image\ns,t\n')
    with pytest.raises(ValueError, match='predictions.csv'):
        load_same_room_prediction(tmp_path)

from tools.thesis_main.analysis.build_research_workbench_v2_20261019 import pack_annotation, validate_objects


def test_v2_uses_final_geometry_and_preserves_missing_raw_and_floor_only():
    obj = dict(object_id='new', image_id='i', worker_id='W100', condition='manual',
               points_1024x512=[[1, 2], [1, 3]], original_export_points=None,
               before_preprocessing_points=[[0, 2], [2, 3]], ring_confirmed=False,
               cleaning_disposition='retained')
    score = dict(object_id='new', image_id='i', rescore_target_id='floor',
                 quality_usable=False, B8L2=None, full_score_state='reference_floor_only')
    result = pack_annotation(obj, score, {'floor'})
    assert result['points'] == obj['points_1024x512']
    assert result['raw_points'] is None
    assert result['before_preprocessing_points'] == obj['before_preprocessing_points']
    assert result['target_id'] == 'floor'
    assert result['quality']['B8L2'] is None
    assert result['ring_confirmed'] is False
    with pytest.raises(ValueError, match='reference'):
        pack_annotation(obj, score, set())


def test_display_requires_exact_object_inventory_not_partial_join():
    objects = [dict(object_id='a', image_id='i', object_kind='annotation')]
    validate_objects(objects, [dict(object_id='a', image_id='i')])
    with pytest.raises(ValueError, match='inventory'):
        validate_objects(objects, [])
    with pytest.raises(ValueError, match='duplicate'):
        validate_objects(objects, [dict(object_id='a'), dict(object_id='a')])


def test_declared_tables_preserve_missing_and_reject_drift(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, 'ROOT', tmp_path)
    source = tmp_path / 'declared.csv'
    source.write_text('worker_id,value,known\nW100,,False\n', encoding='utf-8-sig')
    manifest = {'tables': [dict(id='workers__test', source='declared.csv',
                                columns=['worker_id', 'value', 'known'])]}
    tables, provenance = builder.load_declared_tables(manifest)
    assert tables == {'workers__test': [dict(worker_id='W100', value=None, known=False)]}
    assert provenance == {'workers__test': 'declared.csv'}
    source.write_text('value,worker_id,known\n,W100,False\n')
    with pytest.raises(ValueError, match='display schema drift: workers__test'):
        builder.load_declared_tables(manifest)
    source.unlink()
    with pytest.raises(FileNotFoundError, match='display source missing: workers__test -> declared.csv'):
        builder.load_declared_tables(manifest)


def test_contract_tables_include_filter_and_bom(tmp_path):
    contract = {'tables': {'included.csv': ['worker_id', 'value', 'known'],
                           'excluded.csv': ['not_loaded']}}
    (tmp_path / 'FIELD_CONTRACT.json').write_text(json.dumps(contract))
    source = tmp_path / 'included.csv'
    source.write_text('worker_id,value,known\nW100,,False\n', encoding='utf-8-sig')
    tables = builder.load_contract_tables(tmp_path, 'same_room_multiview__', ['included.csv'])
    assert tables == {'same_room_multiview__included': [dict(worker_id='W100', value=None, known=False)]}
    assert builder.load_contract_tables(tmp_path, 'same_room_multiview__', []) == {}
    with pytest.raises(ValueError, match='display table not in FIELD_CONTRACT: missing.csv'):
        builder.load_contract_tables(tmp_path, 'same_room_multiview__', ['missing.csv'])
    source.write_text('value,worker_id,known\n,W100,False\n', encoding='utf-8-sig')
    with pytest.raises(ValueError, match='display schema drift: included.csv'):
        builder.load_contract_tables(tmp_path, 'same_room_multiview__', ['included.csv'])


def test_real_integration_manifest_matches_sources():
    manifest = builder.read(builder.EXTRA)
    assert manifest['snapshot_id'] == builder.SNAPSHOT
    assert manifest['data_release'] == 'v2'
    declared_ids = [spec['id'] for spec in manifest['tables']]
    assert len(declared_ids) == len(set(declared_ids)) == 10
    for spec in manifest['tables']:
        source = builder.ROOT / spec['source']
        assert source.is_file(), spec['source']
        assert spec['columns'] == pd.read_csv(source, encoding='utf-8-sig').columns.tolist()
    contract = builder.read(builder.MULTIVIEW / 'FIELD_CONTRACT.json')['tables']
    assert len(builder.MULTIVIEW_TABLES) == 7
    multiview_ids = set()
    for filename in builder.MULTIVIEW_TABLES:
        assert filename in contract
        frame = pd.read_csv(builder.MULTIVIEW / filename, encoding='utf-8-sig')
        assert frame.columns.tolist() == contract[filename]
        multiview_ids.add('same_room_multiview__' + Path(filename).stem)
    tabs = [tid for group in builder.EXTRA_MODULE_TABS.values() for _, tid in group]
    assert len(tabs) == len(set(tabs)) == 17
    assert set(tabs) == set(declared_ids) | multiview_ids
