import json
from tools.thesis_main.analysis.adopt_doorway_similar_exclusions_20261031 import BASE, OUT

def test_adoption_preserves_user_keeps_and_counts_overlap_once():
    ledger=json.loads((OUT/'EFFECTIVE_SCREENING_LEDGER.json').read_text(encoding='utf8'))['records'];byid={r['object_id']:r for r in ledger}
    assert len(ledger)==len(byid)==584
    assert sum(r['eligibility']=='排除' for r in ledger)==60
    for batch in ['scope_recheck_20261031','scope_recheck40_20261031']:
        for oid,r in json.loads((BASE/batch/'ADOPTED_USER_REVIEW.json').read_text(encoding='utf8'))['decisions'].items():
            assert byid[oid]['eligibility']==r['eligibility'] and byid[oid]['scope']==r['scope']
    notes=json.loads((OUT/'VISUAL_REVIEW_RECORDS.json').read_text(encoding='utf8'))
    assert len(notes)==33 and sum(r['decision']=='排除' for r in notes)==9
    q=[r for r in ledger if r['image']=='q9vSo1VnCiC-04' and r['worker'] in ['W101','W110','W106','W111']]
    assert len(q)==4 and all(r['scope']=='空间2' and r['eligibility']=='保留' for r in q)
    assert all(r['ring_unchanged'] and r['individual_quality_not_used'] for r in notes)
