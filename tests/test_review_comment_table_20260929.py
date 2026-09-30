from tools.thesis_main.analysis.build_review_comment_table_20260929 import extract, build


def test_comment_bindings_and_history():
    objects={'a':dict(image_id='i',image_code='code-01',worker_id='W001',condition='manual',source='raw')}
    images={'i':dict(image_code='code-01')}
    doc=dict(image_decisions={'i':dict(comment='图片意见',view_context={'annotation_id':'a'})},
             records={'a':dict(note='当前')},previous_round_records={'a':dict(note='过去')},
             issue_decisions={'i:continue':dict(comment='续审')})
    result=list(extract(doc,objects,images))
    assert len(result)==4
    assert result[0]['object_id'] is None
    assert result[-1]['image_id']=='i'
    assert [r['text'] for r in result[1:3]]==['当前','过去']
    assert all(r['reviewer'] is None for r in result)
    d=build()
    assert sum(s['comment_occurrences'] for s in d['sources'])==len(d['occurrences'])
    ids={r['occurrence_id'] for r in d['occurrences']}
    assert len(ids)==len(d['occurrences'])
    assert set(i for c in d['comments'] for i in c['occurrence_ids'])==ids
    assert {'order','pairing','compliance'}==set(d['summary']['phases'])
    assert d['frozen_cluster_references'] and d['chat_clarifications']
