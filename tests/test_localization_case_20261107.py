"""Keep the illustrative case tied to its original observations and identities."""
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'tools/thesis_main/analysis'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('localization_figure', SCRIPTS / 'render_localization_case_20261107.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_cross_team_identity_uses_retained_observations_and_ring_mapping():
    case = module.load_and_check()
    assert len(case['D_anchor_links']) == 4
    assert case['mechanisms']['D_partition_changed'] is False
    assert all(link['A_support'] == link['C_support'] == 20 for link in case['D_anchor_links'])
    assert all(arm['geometry']['ring_confirmed'] is False for arm in case['arms'].values())


def test_render_receipt_preserves_exact_saved_geometry():
    case = module.load_and_check()
    audit = json.loads((ROOT / 'docs/thesis_main/论文写作工作资料/定位机制图来源核对_20261107.json').read_text(encoding='utf-8'))
    for side, arm in case['arms'].items():
        np.testing.assert_array_equal(audit[side + '_points'], arm['geometry']['points'])
        np.testing.assert_array_equal(audit[side + '_footprint'], arm['geometry']['footprint'])
        assert audit[side + '_Q'] == arm['B8L2']
    assert audit['new_fusion_runs'] == audit['new_scoring_runs'] == 0
