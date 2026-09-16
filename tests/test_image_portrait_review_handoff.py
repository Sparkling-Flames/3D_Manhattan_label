import pytest
from tools.thesis_main.analysis.image_portrait.review_handoff import validate_memberships, validate_review


def test_memberships_require_real_unique_people_and_equal_point_counts():
    raw = {'a': {'worker_id': 'W001', 'effective_points_1024x512': [[1, 2]] * 8},
           'b': {'worker_id': 'W002', 'effective_points_1024x512': [[1, 2]] * 10}}
    with pytest.raises(ValueError, match='point count'):
        validate_memberships([['a', 'b']], raw)
    with pytest.raises(ValueError, match='duplicate'):
        validate_memberships([['a'], ['a']], raw)
    validate_memberships([['a'], ['b']], raw)


def test_unreviewed_cannot_be_exported_as_human_confirmed():
    validate_review({'status': '未审核', 'grade': '', 'reason': ''})
    with pytest.raises(ValueError):
        validate_review({'status': '未审核', 'grade': '简单', 'reason': ''})
    with pytest.raises(ValueError):
        validate_review({'status': '已审核', 'grade': '', 'reason': '暂不明确'})
    validate_review({'status': '已审核', 'grade': '中等', 'reason': '稳定少数解释'})


def test_focus39_portable_queue_and_response_identity():
    import json
    from tools.thesis_main.analysis.image_portrait.review_handoff import B, read_rows
    evidence = json.loads((B / 'review_workflow_20260915/key39/review_evidence.json').read_text(encoding='utf-8'))
    queue = read_rows(B / 'cloud/image_links_after_review_20260915_v1/run_b02a97e2/local_image_review_queue.csv')
    raw = {r['canonical_annotation_id']: r for r in read_rows(B / 'human/responses.jsonl.gz')}
    assert len(evidence['rows']) == 39
    assert {r['image_id'] for r in evidence['rows']} == {r['image_id'] for r in queue}
    assert sum(len(r['questions']) for r in evidence['rows']) == 44
    assert evidence['image_bytes_included'] is False
    for row in evidence['rows']:
        for question in row['questions']:
            for field in ('canonical_ids', 'representative_canonical_ids'):
                for cid in filter(None, question[field].split(';')):
                    assert raw[cid]['image_id'] == row['image_id']


def test_focus39_local_geometry_and_image_links():
    import json
    from tools.thesis_main.analysis.image_portrait.review_handoff import B, LOCAL, ROOT, read_rows
    if not (LOCAL / 'key39/index.html').exists():
        pytest.skip('本地原图及审核缓存未生成；云端仍运行无图身份关联检查')
    evidence = json.loads((B / 'review_workflow_20260915/key39/review_evidence.json').read_text(encoding='utf-8'))
    queue = read_rows(B / 'cloud/image_links_after_review_20260915_v1/run_b02a97e2/local_image_review_queue.csv')
    assert len(evidence['rows']) == 39
    assert {r['image_id'] for r in evidence['rows']} == {r['image_id'] for r in queue}
    assert sum(len(r['questions']) for r in evidence['rows']) == 44
    for index, row in enumerate(evidence['rows']):
        text = (LOCAL / f'key39/history/{index}.js').read_text(encoding='utf-8')
        payload, _ = json.JSONDecoder().raw_decode(text.split(',', 1)[1])
        sources = {v['source']['canonical_annotation_id']: v['source'] for v in payload['variants']}
        assert (LOCAL / 'key39' / evidence['image_root'] / row['image_path']).resolve() == (ROOT / row['image_path']).resolve()
        assert (ROOT / row['image_path']).is_file()
        for question in row['questions']:
            for cid in filter(None, question['representative_canonical_ids'].split(';')):
                assert cid in sources
            if question['condition'] == 'oos_geometry':
                assert payload['history']['partitions']['OOS']['candidates']
