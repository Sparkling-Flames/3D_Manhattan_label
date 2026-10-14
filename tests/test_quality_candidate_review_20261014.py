from tools.thesis_main.analysis import quality_candidate_review_20261014 as q


def test_review_identity_and_comparison_scope():
    data=q.read(q.OUT/'manifest.json'); scores=q.read(q.OUT/'score_provenance.json')
    assert len(data['cards'])==8
    assert sum(len(c['bindings']) for c in data['cards'])==15
    for card,score in zip(data['cards'],scores):
        assert card['id']==score['id']
        assert [r['record_id'] for r in card['bindings']]==[r['record_id'] for r in score['records']]
        assert all((q.OUT/r['photo']).exists() for r in card['bindings'])
        assert all(any(v=='uncertain' for v,_ in item['options']) for item in card['questions'])
        if card['kind']=='height_cross_image':
            assert len({r['image_id'] for r in card['bindings']})==2
            assert 'overall' not in {x['id'] for x in card['questions']}
        else:
            assert len({r['reference_object_id'] for r in card['bindings']})==1
        for ext in ['2d.jpg','3d.png']:assert (q.OUT/'assets'/f"{card['id']}_{ext}").exists()
    assert 'id="scores" hidden' in (q.OUT/'REVIEW.html').read_text(encoding='utf-8')
