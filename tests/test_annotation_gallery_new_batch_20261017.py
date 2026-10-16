import pytest

from tools.thesis_main.analysis.annotation_gallery_new_batch_20261017 import parse_new_batch


def task(image='known', annotations=None):
    return dict(id=10,project=98,data=dict(base_task_id=image,image=f'https://example.test/{image}.jpg'),
                annotations=annotations if annotations is not None else [dict(id=20,completed_by=6,result=[{'type':'keypointlabels'}],was_cancelled=False,ground_truth=False)])


def test_submission_people_and_review_are_separate():
    t=task();t['annotations'].append(dict(t['annotations'][0],id=21))
    review=dict(schema='task8_screen_order_review_v1',records={'ls98:10:20':dict(source_id='ls98:10:20',filter='exclude',order=[1,0])})
    out=parse_new_batch({'one.json':[t]},review,{'known'})
    row=out['images'][0]
    assert (row['n_raw_records'],row['n_submitted_records'],row['n_people'])==(2,2,1)
    assert row['review_counts']=={'exclude':1,'unreviewed':1}
    assert out['analysis_included'] is False


def test_duplicate_export_deduplicates_submissions_without_guessing_people():
    out=parse_new_batch({'one.json':[task()],'two.json':[task()]},None,{'known'})
    row=out['images'][0]
    assert row['n_raw_records']==2 and row['n_submitted_records']==1
    assert row['n_people'] is None
    assert len(out['checks']['duplicate_annotation_occurrences'])==1


def test_cancelled_empty_unknown_person_and_unmatched_image():
    annotations=[dict(id=1,completed_by=6,result=[{}],was_cancelled=True),dict(id=2,completed_by=6,result=[],was_cancelled=False),dict(id=3,completed_by=None,result=[{}],was_cancelled=False)]
    out=parse_new_batch({'one.json':[task('outside',annotations)]},None,{'known'})
    row=out['images'][0]
    assert row['n_raw_records']==3 and row['n_submitted_records']==1
    assert row['n_people'] is None and row['n_unknown_person_submissions']==1
    assert out['checks']['unmatched_image_ids']==['outside']


def test_identity_conflicts_are_not_silently_deduplicated():
    t=task();t['data']['image']='https://example.test/other.jpg'
    with pytest.raises(ValueError,match='image identity conflict'):
        parse_new_batch({'one.json':[t]},None,{'known'})
    t=task();other=task();other['annotations'][0]['completed_by']=99
    with pytest.raises(ValueError,match='annotation identity conflict'):
        parse_new_batch({'one.json':[t],'two.json':[other]},None,{'known'})
