"""冻结归档的数值与空值边界；不把复算一致当成人评验证。"""
import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'research/quality_pro_joint_archive_20261013/source'
spec = importlib.util.spec_from_file_location('archived_joint_score', ROOT / 'calibration/score.py')
score = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score)


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8-sig'))


def test_frozen_922_scores_and_independent_primary_formula():
    rows = read('calibration/inputs/search_inputs.json')['rows']
    configs = {'baseline_quad08': score.BASELINE, **read('calibration/recommended_parameters.json')['candidates']}
    with (ROOT / 'calibration/results/selected_scores_wide.csv').open(encoding='utf-8-sig', newline='') as f:
        expected = {r['record_id']: r for r in csv.DictReader(f)}
    assert len(rows) == len(expected) == 922
    assert {r['id'] for r in rows} == set(expected)
    for row in rows:
        for name, config in configs.items():
            value = score.score_metrics(row['metrics'], config, row['descriptor'])
            assert value['status'] == 'complete'
            assert abs(value['score'] - float(expected[row['id']][name])) < 1e-9
        m = score.normalized_metrics(row['metrics'])
        independent = 100*m['I'] / (1 + m['Sb']**2/32 + 1.5*m['D']**2/(m['D']**2+37.5)
                                     + (m['D']/12)**4 + m['Hm']**2 + (m['Hc']/.25)**2)
        assert abs(independent - float(expected[row['id']]['J_main_hill_tail12_g1_l025'])) < 1e-9


def test_missing_reference_top_never_becomes_complete_score():
    config = read('calibration/recommended_parameters.json')['candidates']['J_main_hill_tail12_g1_l025']
    metrics = dict(I=1, Sb=0, D=0, Hm=0, Hc=0)
    result = score.score_metrics(metrics, config, reference_height_available=False)
    assert result['floor_score'] == 100
    assert result['score'] is None and result['height_loss'] is None
    assert not result['raw_input_quality_certified']
    assert result['human_grade'] is None


def test_zero_overlap_and_missing_overlap_have_different_meanings():
    config = score.BASELINE
    assert score.score_metrics(dict(I=0, Sb=1, D=1, Hm=0, Hc=0), config)['score'] == 0
    result = score.score_metrics(dict(Sb=1, D=1, Hm=0, Hc=0), config)
    assert result['status'] == 'unavailable' and result['score'] is None
