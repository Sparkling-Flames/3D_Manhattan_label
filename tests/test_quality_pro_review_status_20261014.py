import json
from tools.thesis_main.analysis import quality_pro_offline_20261014 as offline


def test_current_review_status_overrides_historical_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(offline, 'ROOT', tmp_path)
    (tmp_path/'data').mkdir()
    (tmp_path/'data/human_review_manifest.json').write_text(
        json.dumps({'status':'awaiting_receipt'}), encoding='utf-8')
    assert offline.review_context()['review_status']=='awaiting_receipt'
    (tmp_path/'human_review').mkdir()
    current={'status':'received_with_amendments','received_cases':['Q01','Q02','Q03'],
             'amended_cases':['Q02','Q03'],'overall_order_not_established':['Q02','Q03']}
    (tmp_path/'human_review/effective_status.json').write_text(json.dumps(current), encoding='utf-8')
    result=offline.review_context()
    assert result['review_status']=='received_with_amendments'
    assert result['historical_review_status']=='awaiting_receipt'
    assert result['review_details']==current
    assert result['read_report']=='CURRENT_STATUS.md'
    assert result['review_findings']=='human_review/REVIEW_FINDINGS.md'
