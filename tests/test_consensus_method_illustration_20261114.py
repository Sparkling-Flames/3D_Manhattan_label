from pathlib import Path
import runpy
import numpy as np
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/thesis_main/analysis/draw_consensus_method_illustration_20261114.py'

@pytest.fixture(scope='module')
def example():
    m = runpy.run_path(str(SCRIPT))
    obs = m['simulate']()
    return m, obs, m['run_pipeline'](obs, 7.5)

def test_complete_layout_keeps_half_supported_recess(example):
    m, obs, result = example
    groups = {g['truth']: g for g in result['groups']}
    assert not groups['S']['retained']
    assert all(groups[k]['support'] == 3 and groups[k]['retained'] for k in ['R1','R2','R3','R4'])
    points = m['layout'](result)
    assert len(points) == 8
    assert m['simple_polygon']([(p['x'],p['z']) for p in points])
    assert np.ptp([p['top'] for p in points]) > .1

@pytest.mark.parametrize('reverse', [False, True])
def test_cyclic_start_and_traversal_do_not_change_output(example, reverse):
    m, obs, expected = example
    changed = [r[::-1] if reverse else r[2:]+r[:2] for r in obs]
    actual = m['run_pipeline'](changed, 7.5)
    assert m['signature'](expected) == m['signature'](actual)
    pairs = {g['truth']: g for g in actual['groups']}
    for g in expected['groups']:
        np.testing.assert_allclose([g[k] for k in ['az','up','low']], [pairs[g['truth']][k] for k in ['az','up','low']])
