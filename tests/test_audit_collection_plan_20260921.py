from tools.thesis_main.analysis.audit_collection_plan_20260921 import blocks


def test_overlapping_candidates_share_only_a_leakage_block():
    candidates = [{'image_ids': ['a', 'b']}, {'image_ids': ['b', 'c']}, {'image_ids': ['d', 'e']}]
    result = blocks(candidates)
    assert result['a'] == result['b'] == result['c']
    assert result['d'] == result['e'] != result['a']
    assert candidates[0]['image_ids'] == ['a', 'b']  # 不生成 a/c 已确认的直接同房关系。
