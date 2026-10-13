import pytest

from tools.thesis_main.analysis.quality_candidate_disagreement_20261013 import (
    select_existing_reference, loss_contributions,
)


def test_reference_choice_never_uses_score_or_borrows_missing_top():
    pairs = {'old': {'score': 99}, 'chosen': {'score': 20}}
    assert select_existing_reference(None, None, pairs) == ('unresolved_versions', None)
    route = {'status': 'available', 'selected_full_status': 'available'}
    assert select_existing_reference(route, 'chosen', pairs) == ('routed_full', 'chosen')
    route['selected_full_status'] = 'unavailable_top_pending'
    assert select_existing_reference(route, None, pairs) == ('routed_floor_only', None)


def test_missing_selected_reference_cannot_fall_back_to_high_scoring_version():
    route = {'status': 'available', 'selected_full_status': 'available'}
    with pytest.raises(ValueError, match='selected reference'):
        select_existing_reference(route, 'missing', {'old': {}})


def test_exact_score_decomposition_allows_opposing_effects():
    old = dict(denominator=2, direction_loss=.2, global_height_loss=.6,
               local_height_loss=.1, boundary_loss=.1)
    new = dict(denominator=2.3, direction_loss=.7, global_height_loss=.4,
               local_height_loss=.1, boundary_loss=.1)
    effects = loss_contributions(.8, old, new)
    assert effects['direction_loss'] < 0 < effects['global_height_loss']
    assert sum(effects.values()) == pytest.approx(80/2.3-80/2)
