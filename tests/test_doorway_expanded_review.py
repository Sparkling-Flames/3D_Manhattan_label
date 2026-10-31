import json
from collections import Counter
from tools.thesis_main.analysis.adopt_doorway_expanded_review_20261031 import BASE, OUT


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def test_expanded_review_preserves_prior_and_pending_and_geometry_identity():
    before={r['object_id']:r for r in read(BASE/'similarity_review_20261031/EFFECTIVE_SCREENING_LEDGER.json')['records']}
    after={r['object_id']:r for r in read(OUT/'EFFECTIVE_SCREENING_LEDGER.json')['records']}
    reviews=read(OUT/'VISUAL_REVIEW_RECORDS.json')
    assert len(before)==len(after)==584 and before.keys()==after.keys()
    assert len(reviews)==len({r['object_id'] for r in reviews})==524
    assert sum(r['level']=='detail_original_panorama' for r in reviews)==108
    assert sum(r['eligibility']=='排除' for r in after.values())==140
    changed={oid for oid in before if before[oid]['eligibility']!=after[oid]['eligibility']}
    assert len(changed)==80
    assert changed=={r['object_id'] for r in reviews if r['decision']=='排除'}
    for oid,r in after.items():
        assert r['scope']==before[oid]['scope']
        assert r['inherited_quality_eligible']==before[oid]['inherited_quality_eligible']
        if oid in changed:
            assert before[oid]['eligibility']=='保留'
            assert r['prior_screening_record']==before[oid]
        elif r.get('review_status')=='pending_user_review_preserve_prior':
            assert r['eligibility']==before[oid]['eligibility']=='保留'
        else:
            assert r==before[oid]
    pending=read(OUT/'PENDING_USER_REVIEW.json')
    assert len(pending)==21 and not changed.intersection(r['object_id'] for r in pending)
    assert all(len(r['points'])==2*len(r['floor']) and len(r['spaces'])==2 for r in pending)
    for r in reviews:
        assert (OUT/r['evidence']).exists()
        assert r['scope_unchanged'] and r['ring_unchanged'] and r['individual_quality_not_used']
    for r in after.values():
        if r['image']=='q9vSo1VnCiC-04' and r['worker'] in ['W101','W110','W106','W111']:
            assert r['scope']=='空间2' and r['eligibility']=='保留'


def test_boundary21_adoption_and_distinct_worker_counts():
    before={r['object_id']:r for r in read(OUT/'EFFECTIVE_SCREENING_LEDGER.json')['records']}
    after={r['object_id']:r for r in read(OUT/'FINAL_SCREENING_LEDGER.json')['records']}
    received=read(OUT/'USER_REVIEW_RECEIVED.json')['decisions']
    pending={r['object_id']:r for r in read(OUT/'PENDING_USER_REVIEW.json')}
    assert len(received)==21 and received.keys()==pending.keys()
    assert before.keys()==after.keys() and len(after)==584
    assert Counter(r['eligibility'] for r in after.values())=={'保留':439,'排除':145}
    assert len({(r['image'],r['worker']) for r in after.values()})==584
    for oid,r in after.items():
        if oid not in received:
            assert r==before[oid]
            continue
        assert r['prior_boundary_record']==before[oid]
        assert r['scope']==received[oid]['scope'] and r['eligibility']==received[oid]['eligibility']
        for field in ['object_id','image','worker','previous_scope','points','spaces']:
            assert received[oid][field]==pending[oid][field]
    report=read(OUT/'PER_IMAGE_COUNTS.json')
    assert len(report['records'])==17 and len(report['unassigned_scope_records'])==7
    for row in report['records']:
        group=[r for r in after.values() if r['image']==row['image']]
        kept=[r for r in group if r['eligibility']=='保留']
        assert row['retained_workers']==len(kept)==len({r['worker'] for r in kept})
        assert row['base_workers']==row['retained_workers']+row['excluded_workers']
        assert row['retained_workers']==sum(row[k] for k in ['space1','space2','whole','other_scope'])
        assert row['pending_workers']==0
