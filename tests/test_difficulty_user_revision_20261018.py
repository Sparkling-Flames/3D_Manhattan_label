from tools.thesis_main.analysis.current_annotation_context_20261017 import apply_difficulty_overrides


def test_difficulty_revision_preserves_geometry_eligibility_and_other_images():
    rows = [dict(image_id='i', current_class='简单', conditional_difficulty='简单',
                 target_version='r', selected={'floor': [[1, 2]]}, difficulty_analysis_eligible=False),
            dict(image_id='j', current_class='困难')]
    reviews = [dict(image_id='i', old_class='简单', new_class='中等')]
    result = apply_difficulty_overrides(rows, reviews)
    assert result[0] == dict(rows[0], current_class='中等', conditional_difficulty='中等')
    assert result[1] == rows[1] and rows[0]['current_class'] == '简单'
    assert apply_difficulty_overrides(result, reviews) == result


def test_confirmed_image_and_display_use_medium_without_changing_input():
    from tools.thesis_main.analysis.build_research_workbench_20261017 import pack_image
    from pathlib import Path
    image = dict(image_id='uNb9QFRL6hY_00b4950b469b4520b29f895aa029419c',
                 difficulty={'label': '简单'}, scene={'conditional_difficulty': '简单'}, annotations=[])
    packed = pack_image(image, {}, Path('.'))
    assert packed['difficulty']['label'] == packed['scene']['conditional_difficulty'] == '中等'
    assert image['difficulty']['label'] == '简单'
