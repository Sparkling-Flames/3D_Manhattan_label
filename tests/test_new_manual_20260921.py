import numpy as np
from tools.thesis_main.analysis.analyze_new_manual_20260921 import statistics
from tools.thesis_main.analysis.clustering_numeric_research.common import next_uncovered
from tools.thesis_main.analysis.analyze_new_manual_20260921 import intake, read, HIST
from tools.thesis_main.analysis.clustering_release.pipeline import rows_at


def test_new_person_can_change_old_groups_without_changing_old_distances():
    d=np.array([[0,1,3],[1,0,2],[3,2,0.]])
    complete,_,_=statistics(d,['a','b','c'],2,'complete')
    representative,_,_=statistics(d,['a','b','c'],2,'representative')
    assert complete['far_but_grouped']==0
    assert representative['groups']==1 and representative['far_but_grouped']==1
    assert next_uncovered(d,1,2)==1/3


def test_intake_keeps_extra_and_repairs_without_duplicate_votes():
    history=rows_at(HIST/'responses.jsonl.gz')
    registry=read('analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json')
    from tools.thesis_main.analysis.reviewed_manual_20260921 import SOURCES
    new,receipts=intake(history,registry,SOURCES)
    by={r['annotation']:r for r in receipts}
    assert by[7498]['assignment']=='outside_required' and by[7498]['strict_include']
    assert by[7502]['point_count']==8 and by[7502]['conditional_include']
    assert not by[7137]['conditional_include']  # 已有同人同图，不增加票。
    assert not by[7271]['strict_include'] and not by[7272]['strict_include']
    assert all(not r['strict_include'] for r in receipts if r['parent_annotation'])
    assert len(new)==len(receipts)==651


def test_scene_holdout_and_review_roundtrip():
    import json
    import pytest
    from tools.thesis_main.analysis.analyze_new_manual_20260921 import OUT
    from tools.thesis_main.analysis.summarize_new_manual_20260921 import local
    from tools.thesis_main.analysis.paired_split_research.release_review import SCHEMA,validate_review
    predictions=local('scene_predictions.json')
    descriptions=local('scene_image_statistics.json')
    assert all(isinstance(r['scene'],str) and r['scene'] for r in descriptions)
    assert sum(r['N'] for r in descriptions if r['pool']=='strict')==2393
    assert predictions and all(all(i.split('_')[0]!=r['building'] for i in r['source_images']) for r in predictions)
    assert not any(r['scene'] in ['主空间待定','无法判断','开放复合空间'] for r in predictions)
    data=json.loads((OUT/'审核/REVIEW_MANIFEST.json').read_text(encoding='utf8'))
    cases=data['cases'];assert len(cases)==39
    key=cases[1]['key'];options={c['key']:c['decision_options'] for c in cases}
    answer={'schema':SCHEMA,'binding':data['binding'],'decisions':{key:{'relation':options[key][0],'comment':'保留原点号p7；这里只确认此作答','defer':True}}}
    assert validate_review(json.loads(json.dumps(answer)),data['binding'],list(options),options)==answer['decisions']
    with pytest.raises(ValueError):validate_review(answer,{},list(options),options)
    with pytest.raises(ValueError):validate_review(answer,data['binding'],list(options))
