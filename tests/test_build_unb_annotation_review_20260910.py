"""真实审阅包的身份和点集往返核验；本地历史资产不随代码仓库分发。"""
import gzip
import json

import pytest

from tools.thesis_main.analysis import build_unb_annotation_review_20260910 as review


def test_review_preserves_real_points_and_distinguishes_q_missing(tmp_path, monkeypatch):
    source = review.ROOT / 'analysis_results/confirmed_point_calculation_view_20260909_v1/reviewed/calculation_view.jsonl.gz'
    if not source.exists():
        pytest.skip('requires local reviewed historical annotation assets')
    monkeypatch.setattr(review, 'DEST', tmp_path)
    review.build()
    html = (tmp_path / 'uNb标注对照表.html').read_text(encoding='utf8')
    payload = json.loads(html.split('<script id="data" type="application/json">', 1)[1].split('</script>', 1)[0])
    originals = {r['canonical_annotation_id']: r for r in map(json.loads, gzip.open(source, 'rt', encoding='utf8'))}
    assert len(payload['cards']) == 12 and payload['defaults'] == ['1', '2', '6']
    rows = review.read_csv(tmp_path / 'uNb真实标注明细.csv')
    assert len(rows) == 296 and len({r['canonical_annotation_id'] for r in rows}) == 296
    for card in payload['cards']:
        assert all(card['responses'][w]['included'] for w in payload['defaults'])
        for a in card['responses'].values():
            r = originals[a['canonical']]
            assert r['image_id'] == card['id'] and r['worker_id'] == a['worker']
            assert a['raw'] == r['raw_points_1024x512'] and a['effective'] == r['effective_points_1024x512']
    ambiguous = next(c for c in payload['cards'] if c['short'] == '59484243')
    assert '200/200次分区为多解' in ambiguous['partition_note']
    odd = next(c for c in payload['cards'] if c['short'] == '978d7a8e')
    assert odd['responses']['2']['effective_n'] == 17
    assert odd['responses']['2']['included'] and odd['responses']['2']['q_valid'] is False
    assert odd['q_valid_people'] == 25 and odd['included'] == 26
    assert odd['evidence']['with_workers']['onset']['status'] == 'unknown'
    assert not any('polyline' in line or '<path ' in line for line in html.splitlines())
    first = payload['cards'][0]['partitions']['with_workers']
    assert first['status'] == 'unique'
    assert [len(g) for g in first['candidates'][0]] == [16, 6, 1, 1, 1]
    assert len(ambiguous['partitions']['with_workers']['candidates']) == 4
    assert odd['partitions']['with_workers']['unassigned'] == ['2']
    for card in payload['cards']:
        for mode, partition in card['partitions'].items():
            expected = {w for w, a in card['responses'].items() if a['included'] and a['q_valid']
                        and (mode == 'with_workers' or w not in ('19', '26'))}
            for candidate in partition['candidates']:
                flat = [w for group in candidate for w in group]
                assert len(flat) == len(set(flat)) and set(flat) == expected
                assert all(len({card['responses'][w]['effective_n'] for w in g}) == 1 for g in candidate)
