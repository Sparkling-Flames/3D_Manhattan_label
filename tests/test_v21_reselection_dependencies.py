import importlib.util
from pathlib import Path
import pandas as pd
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/thesis_main/analysis/audit_v21_reselection_dependencies_20261029.py'
spec = importlib.util.spec_from_file_location('reselection_dependencies', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_target_then_image_weighting_and_missing():
    data = pd.DataFrame({'method': ['M'] * 5, 'pool_id': ['a', 'a', 'b', 'c', 'd'], 'image': ['i', 'i', 'i', 'j', 'k'], 'building': ['B', 'B', 'B', 'B', 'C'], 'q': [0., 0., 10., 9., None]})
    im, building = module.hierarchy(data, ['method'], ['q'])
    assert im.set_index('image').loc['i', 'q'] == 5
    assert building.set_index('building').loc['B', 'q'] == 7
    summary = pd.DataFrame([dict(method='M', delta_mean_image=7., delta_mean_building=7., delta_valid_images=2, delta_valid_buildings=1, delta_positive_images=2, delta_positive_buildings=1)])
    assert module.check_summary(data, ['method'], {'delta': 'q'}, summary)['max_error'] == 0
    summary['delta_valid_images'] = 3
    with pytest.raises(AssertionError):
        module.check_summary(data, ['method'], {'delta': 'q'}, summary)


@pytest.mark.parametrize('topic,expected_stage', [
    ('composition_manual', '03B_core'), ('composition_semi', '03C'),
    ('composition_other_targets', '03A'), ('fixed_XYZ_n_raw', '05B'),
    ('screen_frame', '05B'), ('screen_events', '05A'),
])
def test_new_delivery_resolves_actual_package_without_legacy_fallback(tmp_path, topic, expected_stage):
    old = tmp_path / 'legacy/README.md'
    old.parent.mkdir()
    old.write_text('report only', encoding='utf-8')
    with pytest.raises(FileNotFoundError, match='additional_delivery_source_missing'):
        module.resolve_saved_source(topic, 'legacy/README.md', tmp_path)
    actual = tmp_path / 'additional_delivery/packages' / module.ADDITIONAL_SOURCES[topic]
    actual.parent.mkdir(parents=True)
    actual.write_text('actual numeric source', encoding='utf-8')
    resolved = module.resolve_saved_source(topic, 'legacy/README.md', tmp_path)
    assert resolved == actual
    assert resolved.relative_to(tmp_path).parts[2] == expected_stage
    assert old.read_text(encoding='utf-8') == 'report only'


def test_existing_07a_source_keeps_original_execution_path(tmp_path):
    assert module.resolve_saved_source('labels', 'classification/labels.csv', tmp_path) == (
        tmp_path / 'classification/labels.csv')
