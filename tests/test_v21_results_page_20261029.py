import csv
import json
from tools.thesis_main.analysis.build_v21_results_page_20261029 import PAGE, OUT


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
