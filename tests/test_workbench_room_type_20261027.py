"""同用途展示引用已独立核验的小表，不运行预测或融合。"""
import csv
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
TOPIC = ROOT / 'research/statistics/room_type_similarity_20261027'


def rows(path):
    with (TOPIC / path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def test_adopted_image_and_person_supports():
    gain = next(r for r in rows('key_tables/K03_IMAGE_PURPOSE_GAIN.csv')
                if r['metric'] == 'Q' and r['subset'] == 'REPEATED_RECORDED_PURPOSE')
    assert (int(gain['images']), int(gain['buildings'])) == (161, 21)
    assert float(gain['baseline_mae']) == pytest.approx(4.567, abs=.001)
    assert float(gain['purpose_mae']) == pytest.approx(4.188, abs=.001)
    assert (int(gain['improved_images']), int(gain['improved_buildings'])) == (97, 19)
    personal = next(r for r in rows('key_tables/K10_PROTECTED_PURPOSE_SUMMARY.csv')
                    if r['outcome'] == 'Q' and r['support'] == 'recorded_multibuilding161')
    assert float(personal['baseline_mae']) == pytest.approx(11.449, abs=.001)
    assert float(personal['purpose_mae']) == pytest.approx(11.450, abs=.001)


def test_formal_cases_and_workbench_image_routes_exist():
    cases = rows('cases_history/CASE_IMAGE_SUMMARY.csv')
    assert sum(int(r['n']) for r in cases) == 104
    assert len(rows('cases_history/CASE_ALL_FORMAL_ANSWERS.csv')) == 104
    resources = json.loads((ROOT / 'research/statistics/research_explorer_v1_r2_20261017/v2-resources/index.json').read_text(encoding='utf-8'))
    images = {r['image_id'] for r in resources['images']}
    assert {r['reference_id'].split(':')[1] for r in cases} <= images
