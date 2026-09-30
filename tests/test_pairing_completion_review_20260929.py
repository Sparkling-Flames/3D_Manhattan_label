import json
from collections import Counter
from tools.thesis_main.analysis.build_pairing_completion_review_20260929 import OUT, ROOT, DELETIONS


def test_complete_proposals_preserve_identity_and_explicit_pairs():
    def load(path):
        return json.loads(path.read_text(encoding='utf-8').removeprefix('window.PAIRING_DATA=').removesuffix(';'))
    data=load(OUT/'data.js')
    original={r['object_id']:r for r in load(ROOT/'analysis_results/pairing_review_20260929/data.js')['cases']}
    assert len(data['cases'])==15 and len(data['images'])==11
    assert Counter(r['review_reason'] for r in data['cases'])==dict(horizon_role_limit=6,x_completion_required=6,point_edit_pending=3)
    assert data['schema']!='pairing_only_review_20260929_v1'
    for r in data['cases']:
        assert r['points']==original[r['object_id']]['points']
        assert r['labels']==original[r['object_id']]['labels']
        assert r['explicit_pairs']==r['previous_review']['pairs']
        for p in r['proposals']:
            indices=[i for pair in p['pairs'] for i in pair]
            assert sorted(indices)==[i for i in range(len(r['points'])) if i not in p['deleted']]
            assert all(pair in p['pairs'] for pair in r['explicit_pairs'])
            assert all(r['points'][a][1]<r['points'][b][1] for a,b in p['pairs'])
        assert [p['deleted'] for p in r['proposals']]==DELETIONS.get(r['object_id'],[[]])
    b6=next(r for r in data['cases'] if r['object_id']=='f6bfdcf15004e457')
    assert len(b6['proposals'])==2
    for r in data['cases']:
        if r['image_code']=='uNb9QFRL6hY-36':
            assert sorted(r['proposals'][0]['pairs'])==[[0,2],[1,3],[4,7],[5,6]]
