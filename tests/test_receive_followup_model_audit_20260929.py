import copy
import pytest
from tools.thesis_main.analysis.receive_followup_model_audit_20260929 import OUT, ROOT, read, validate_followup, mentions


def test_v2_label_requires_complete_exact_binding_and_same_image_gate():
    doc=read(OUT/'evidence/user_followup.json')
    sources={o['object_id']:o for o in read(ROOT/'analysis_results/order_followup_20260929/source_objects.json')['objects']}
    validate_followup(doc,sources)
    bad=copy.deepcopy(doc);bad['records'].pop(next(iter(bad['records'])))
    with pytest.raises(ValueError,match='coverage'):validate_followup(bad,sources)
    bad=copy.deepcopy(doc);next(iter(bad['records'].values()))['binding']='{}'
    with pytest.raises(ValueError,match='binding'):validate_followup(bad,sources)
    assert mentions({'comment':'模型的错误预标注有影响'})==[{'field':'.comment','text':'模型的错误预标注有影响'}]
    summary=read(OUT/'summary.json')
    assert summary['followup_changes']=={'unchanged':71,'adjacency_changed':6}
    assert summary['unchanged_rows']==100 and summary['continuation']['next_round_objects']==35
    assert summary['user_comment_explicit_influence_rows']==4
    package=read(OUT/'同房汇集_Matterport_当前确认快照.json')
    ids=[a['object_id'] for room in package['rooms'] for im in room['images'].values() for a in im['annotations']]
    assert len(ids)==len(set(ids))==1237
    assert not set(ids).intersection(package['remaining_order_candidates'])
