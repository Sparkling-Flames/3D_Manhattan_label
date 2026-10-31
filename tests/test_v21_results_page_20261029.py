import csv
import json
from tools.thesis_main.analysis.build_v21_results_page_20261029 import PAGE, OUT
from tools.thesis_main.analysis.build_v21_results_page_20261029 import current_research, ROOT


def test_snapshot_tracks_saved_receipts_and_two_person_support():
    data=json.loads((PAGE/'v21-results-data.js').read_text(encoding='utf8').removeprefix('window.V21_RESULTS=').strip().removesuffix(';'))
    receipt=json.loads((OUT/'two_person_natural256/SUMMARY_CHECKS.json').read_text(encoding='utf8'))
    assert data['k2_receipt']==receipt
    with (OUT/'two_person_natural256/IMAGE_RESULTS.csv').open(encoding='utf8',newline='') as f:
        rows=[r for r in csv.DictReader(f) if r['layer']=='ordinary_manual' and int(r['pool_n'])>=30]
    result=next(r for r in data['k2'] if r['scope']=='combined')
    assert result['paired12']==sum(int(float(r['paired_1_2'])) for r in rows)
    assert result['paired23']==sum(int(float(r['paired_2_3'])) for r in rows)
    valid=[float(r['Q2']) for r in rows if r['Q2']]
    assert abs(result['q']-sum(valid)/len(valid))<1e-10
    for stage in ('confirm','reverse_confirm'):
        item=data['strict'][stage]
        assert item is None or 0 <= item['measured'] <= item['registered']
    with (OUT/'current_exchange_results/confirm/combined/summary/METHOD_N_M_COMPARISON.csv').open(encoding='utf-8-sig',newline='') as f:
        expected=[r for r in csv.DictReader(f) if r['method']=='DSTRUCT_K3' and r['metric']=='B8L2']
    assert data['strict_comparison']==expected
    for point in data['natural']:
        if point['k']!=2 and point['scope']=='added':
            assert point['failure_images']==point['failure_eligible']==14
            assert 0 <= point['failure'] <= 1


def test_current_research_snapshot_keeps_source_support_and_working_identity():
    data=json.loads((PAGE/'v21-results-data.js').read_text(encoding='utf8').removeprefix('window.V21_RESULTS=').strip().removesuffix(';'))
    current=data['current_research']
    assert current == current_research()
    assert len(current['modules']) == 21 and current['classification_finalized'] is False
    assert len(current['alliance_resolution']) == 414
    assert sum(r['new_n_at_least3']=='True' for r in current['alliance_resolution']) == 403
    assert len({r['worker_id'] for r in current['worker_wide']}) == 60
    assert sum(int(r['records']) for r in current['worker_difficulty'] if r['scope']=='primary' and r['condition']=='manual') == 6512
    assert sum(int(r['records']) for r in current['worker_difficulty'] if r['scope']=='all_admitted' and r['condition']=='manual') == 6739
    assert all((ROOT/path).exists() for path in current['sources'].values())
    for row in current['modules']:
        assert (ROOT/row['entry']).exists() and (ROOT/row['evidence']).exists()
