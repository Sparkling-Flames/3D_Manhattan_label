import pytest

import numpy as np
from PIL import Image

from tools.thesis_main.analysis.difficulty_model_comparison_20261009 import join_model_evidence, compare_image_sources


def test_source_audit_distinguishes_resizing_and_yaw_without_changing_files(tmp_path):
    image = np.zeros((4, 8, 3), dtype=np.uint8)
    image[:, 0:2] = 200
    first, second = tmp_path/'first.png', tmp_path/'second.png'
    Image.fromarray(np.repeat(np.repeat(image, 2, axis=0), 2, axis=1)).save(first)
    Image.fromarray(image).save(second)
    assert compare_image_sources(first, second)['zero_roll_rgb_mae_255'] == 0
    Image.fromarray(np.roll(image, 2, axis=1)).save(second)
    row = compare_image_sources(first, second)
    assert row['best_quarter_roll'] == 1
    assert row['zero_roll_rgb_mae_255'] > 0


def test_model_join_preserves_zero_missing_and_separates_scene_from_features():
    base = [dict(image='a', image_id='id-a', calibration_panel='special_diagnostic_only')]
    hoho = [dict(image='a', image_id='id-a', status='complete', phase0_pair_count='4',
                 raw_boundary_rotation_mae_deg='0', phase0_boundary_correction_mae_deg='')]
    bi = [dict(image='a', image_id='id-a', status='ok', relative_gap='0')]
    row = join_model_evidence(base, hoho, bi)[0]
    assert row['hohonet_rotation_mae_deg'] == 0
    assert row['bilayout_raw_relative_gap'] == 0
    assert row['hohonet_boundary_correction_deg'] is None
    assert row['calibration_panel'] == 'special_diagnostic_only'
    failed = join_model_evidence(base, [dict(hoho[0], status='incomplete_orbit')], bi)[0]
    assert failed['hohonet_replay_pair_count'] is None
    with pytest.raises(ValueError, match='identity'):
        join_model_evidence(base, hoho, [dict(bi[0], image_id='wrong')])
    with pytest.raises(ValueError, match='nonfinite'):
        join_model_evidence(base, hoho, [dict(bi[0], relative_gap='nan')])
