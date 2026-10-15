import pytest
from tools.thesis_main.analysis.difficulty_review_update_20261015 import attach_review


def test_wrong_target_is_not_an_adjudication_and_gt_error_excludes():
    row=dict(image_id='i',target_version='new',current_class='中等')
    with pytest.raises(ValueError):
        attach_review(row,dict(image_id='i',target_version='old',grade='困难',note=''),False)
    attach_review(row,dict(image_id='i',target_version='new',grade='中等',note='GT错误'),True)
    assert row['current_class']=='待修正GT'
    assert row['gt_error_excluded'] and row['latest_user_review']['grade']=='中等'


def test_user_grade_is_preserved_without_redefining_the_rule():
    row=dict(image_id='i',target_version='new',current_class='中等')
    attach_review(row,dict(image_id='i',target_version='new',grade='困难',note=''),False)
    assert row['current_class']=='中等'
    assert row['review_disagreement'] is True
    empty=dict(image_id='j',target_version='j',current_class='中等')
    attach_review(empty,dict(image_id='j',target_version='j',grade='',note=''),False)
    assert empty['review_disagreement'] is None
