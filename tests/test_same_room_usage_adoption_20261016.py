import json

import pandas as pd
import pytest

from tools.thesis_main.analysis.same_room_usage_adoption_20261016 import (
    profiles_for_buildings, doorway_relations,
)


def test_profiles_exclude_target_building_even_when_target_is_unseen():
    frame = pd.DataFrame([
        dict(panel='current949', axis='B8L2', fold='full_descriptive', worker_id='w',
             training_buildings=json.dumps(['train']), supported=True, effect=3., contexts=8, buildings=3),
        dict(panel='current949', axis='B8L2', fold='train', worker_id='w',
             training_buildings=json.dumps(['other']), supported=False, effect=9., contexts=2, buildings=1),
    ])
    result = profiles_for_buildings(frame, 'current949', 'B8L2', ['unseen', 'train'])
    assert result.loc[result.building.eq('unseen'), 'effect'].iloc[0] == 3.
    assert not result.loc[result.building.eq('train'), 'supported'].iloc[0]
    frame.loc[1, 'training_buildings'] = json.dumps(['train'])
    with pytest.raises(ValueError, match='target building'):
        profiles_for_buildings(frame, 'current949', 'B8L2', ['train'])


def test_doorway_candidates_do_not_create_confirmation_or_merge_conditions():
    records = pd.DataFrame([
        dict(image_id='a', condition='manual', worker_id='w', B8L2=70., is_doorway=True, reference_id='ra'),
        dict(image_id='b', condition='manual', worker_id='w', B8L2=80., is_doorway=False, reference_id='rb'),
        dict(image_id='c', condition='semi', worker_id='w', B8L2=90., is_doorway=False, reference_id='rc'),
    ])
    base = dict(condition='manual', code_a='A', building='building', candidate_ids='G')
    coverage = pd.DataFrame([
        dict(base, image_a='a', image_b='b', code_b='B', confirmation='not_explicitly_confirmed'),
        dict(base, image_a='a', image_b='c', code_b='C', confirmation='confirmed_other_scope'),
        dict(base, condition='semi', image_a='a', image_b='c', code_b='C', confirmation='confirmed_other_scope'),
    ])
    result = doorway_relations(records, coverage)
    assert result.n_common_quality.tolist() == [1, 0, 0]
    assert not result.quality_comparable.any()
    assert result.iloc[0].reference_ids_a == 'ra' and result.iloc[0].reference_ids_b == 'rb'
