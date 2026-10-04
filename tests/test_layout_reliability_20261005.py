"""Regressions for the two independently reproduced Pro diagnostic defects."""
import json
from pathlib import Path

import numpy as np
import pytest

from tools.thesis_main.analysis.layout_reliability_20261005.arc_consensus import project
from tools.thesis_main.analysis.layout_reliability_20261005.continuous_metrics import (
    height_envelope, height_envelope_audit, witness_and_provenance,
)

ARCHIVE = Path(__file__).resolve().parents[1] / 'research/layout_reliability_20261005/pro_original'


@pytest.mark.parametrize('shift_px', [0., 17.3, 64., 256.])
def test_every_source_is_inside_its_source_height_envelope(shift_px):
    floor = np.array([[-2., 2.], [-2., -2.], [2., -2.], [2., 2.]])
    records = []
    for i, slope in enumerate([.1, -.1]):
        top = project(np.c_[floor[:, 0], 1+slope*floor[:, 1], floor[:, 1]])
        bottom = project(np.c_[floor[:, 0], -np.ones(4), floor[:, 1]])
        points = np.stack([top, bottom], axis=1).reshape(-1, 2)
        points[:, 0] = (points[:, 0]+shift_px) % 1024
        records.append(dict(id=f'r{i}', worker=f'w{i}', points=points.tolist()))
    envelope = height_envelope(records)
    assert max(height_envelope_audit(r, envelope)['height_envelope_violation_h']
               for r in records) < 1e-10


def test_merged_failure_window_does_not_inherit_a_discontinued_donor():
    image = '2t7WUuJeko7-06'
    records = json.loads((ARCHIVE/'inputs'/f'{image}.json').read_text(encoding='utf-8'))['records']
    candidate = json.loads((ARCHIVE/'results/compression'/f'{image}_pixel_only_2px.json').read_text(encoding='utf-8'))
    result = witness_and_provenance(candidate, records, 2)
    before = next(r for r in result['below_bound_intervals'] if r['x_lo'] < 200 < r['x_hi'])
    after = next(r for r in result['below_bound_intervals'] if r['x_lo'] < 311.47336 < r['x_hi'])
    assert before['top_source_curves'] == ['R00227']
    assert after['top_source_curves'] == []
    assert result['longitude_share_zero_witness'] == pytest.approx(.4489233860313962, abs=1e-12)
