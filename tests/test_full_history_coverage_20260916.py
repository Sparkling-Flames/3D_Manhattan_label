"""核对研究准备工件；不是人员分型或收敛效果的验证。"""
import json
from collections import Counter
from pathlib import Path


def test_full_history_coverage_contract():
    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / 'analysis_results/full_history_coverage_20260916/全历史覆盖机器表.json').read_text(encoding='utf-8'))
    rows = data['assignments']
    assert len(data['images']) == len(data['matrix']) == 648
    assert len({r['image_id'] for r in data['images']}) == 648
    assert len(rows) == len({(r['slot'], r['image_id']) for r in rows}) == 922
    newcomers = [r for r in rows if r['kind'] == 'new']
    assert len(newcomers) == 750
    assert all(r['worker_id'] is None and r['name'] == '' for r in newcomers)
    assert set(Counter(r['slot'] for r in newcomers).values()) == {50}
    assert all(r['worker_id'] not in {11, 19, 26} for r in rows if r['kind'] == 'existing')
    assert sum(r['history_manual'] for r in data['images']) == 1843
    assert sum(r['new_proposed'] for r in data['images']) == len(rows)
    assert all(r['remaining_if_required_complete'] == 0 for r in data['images'] if r['adopted'])
    assert all(r['expected'] == r['history_manual'] + r['planned'] + r['new_proposed'] for r in data['images'])
    assert {r['group'] for r in data['full_history_rooms']} - {r['room'] for r in data['rooms']}
    assert len(data['backup']) == 52 and len(data['high_history_backup']) == 20
    assert data['user_decisions']['new_worker_id'] is None
