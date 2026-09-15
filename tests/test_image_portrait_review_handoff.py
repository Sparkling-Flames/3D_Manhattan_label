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
