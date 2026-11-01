"""The audit must examine the entire tail, including invalid later counts."""
import numpy as np

from tools.thesis_main.analysis.audit_image_response_20261101 import onset


def test_flat_tail_requires_enough_followup():
    assert np.isnan(onset(np.ones(7), np.full(7, 256), 7, 2, 64))
    assert onset(np.ones(8), np.full(8, 256), 8, 2, 64) == 3


def test_future_jump_is_not_a_plateau():
    values = np.zeros(12)
    values[-1] = 10
    assert np.isnan(onset(values, np.full(12, 256), 12, 2, 64))


def test_missing_or_under_supported_later_count_disqualifies_tail():
    values = np.ones(12)
    values[-1] = np.nan
    assert np.isnan(onset(values, np.full(12, 256), 12, 2, 64))
    values[-1] = 1
    counts = np.full(12, 256)
    counts[-1] = 63
    assert np.isnan(onset(values, counts, 12, 2, 64))


def test_relative_followup_and_inclusive_tolerance():
    values = np.full(36, 10.0)
    values[29:] = 0
    assert onset(values, np.full(36, 256), 36, 2, 64) == 30
    values[29] = 2
    assert onset(values, np.full(36, 256), 36, 2, 64) == 30
