from tools.thesis_main.analysis.quality_three_model_review_20261017 import stratified, compact_pair


def test_sampling_spans_scores_and_does_not_repeat_images():
    rows=[dict(object_id=str(i),image_id=str(i//2),B8L2=str(i)) for i in range(100)]
    picked=stratified(rows,5,2,set())
    assert len(picked)==10
    assert len({r['image_id'] for r in picked})==10
    assert {int(float(r['B8L2']))//20 for r in picked}==set(range(5))


def test_compaction_keeps_top_break_and_original_numbers():
    b=[[0,-1,0],[1,-1,0],[2,-1,0],[2,-1,2],[0,-1,2]]
    g=dict(bottom3d=b,top3d=[[x,2,z] for x,_,z in b])
    reduced,removed=compact_pair(g)
    assert removed==[2] and reduced['original_labels']==[1,3,4,5]
    g['top3d'][1][1]=3
    _,removed=compact_pair(g)
    assert removed==[]
