import copy
import pytest

from tools.thesis_main.analysis.image_portrait.difficulty_tags import materialize, counts_by


def test_tag_identity_and_missing_states():
    images = [dict(image_id=str(i), building='b', source_split='test') for i in range(3)]
    spatial = [dict(image_id=str(i), building='b', spatial_classification={'coarse_type': '卧室'},
                    spatial_field_sources={'coarse_type': 'user_type'}, latest_selection_record=None) for i in range(3)]
    for i, tag in enumerate(['困难', '未定']):
        spatial[i]['latest_selection_record'] = dict(image_id=str(i), difficulty=tag, group='G1')
    spatial[2]['spatial_classification']['coarse_type'] = None
    spatial[2]['spatial_prior_user'] = {'user_type': '复合／待定'}
    rows = materialize(images, spatial)
    assert [r['difficulty_status'] for r in rows] == ['labelled', 'undetermined', 'not_recorded']
    assert [r['difficulty_ordinal'] for r in rows] == [2, None, None]
    assert rows[2]['difficulty_tag'] is None
    assert rows[2]['scene_category'] == '复合／待定'
    assert sum(r['all_images'] for r in counts_by(rows, 'scene_category')) == 3
    for key, bad in [('image_id', 'other'), ('difficulty', '自动推断困难')]:
        changed = copy.deepcopy(spatial)
        changed[0]['latest_selection_record'][key] = bad
        with pytest.raises(ValueError):
            materialize(images, changed)
    with pytest.raises(ValueError):
        materialize(images, spatial + spatial[:1])
