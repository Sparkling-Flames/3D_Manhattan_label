import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('oos_builder', ROOT / 'tools/thesis_main/analysis/build_oos_review_workbench_20261024.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_complete_inventory_and_generated_payload():
    payload = builder.build_payload()
    saved = json.loads(builder.OUTPUT.read_text(encoding='utf-8').removeprefix('window.OOS_REVIEW_DATA=').strip().removesuffix(';'))
    assert payload == saved
    assert len(payload['images']) == 28
    answers = [a for image in payload['images'] for a in image['answers']]
    assert len(answers) == len({a['id'] for a in answers}) == 1222
    assert all(a['points'] is None or a['points'] == a['raw_points'] for a in answers)
    same_room = [i for i in payload['images'] if i['room'] == 'G231']
    assert len(same_room) == 2
    assert all('斜墙' in i['candidate'] for i in same_room)
    assert all((builder.OUTPUT.parent / i['photo']).is_file() for i in payload['images'])
