import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


spec = importlib.util.spec_from_file_location('exchange_evidence', Path(__file__).resolve().parents[1] / 'tools/thesis_main/analysis/build_v21_exchange_evidence_20261029.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_equal_image_weighting_does_not_promote_event_replication():
    df = pd.DataFrame([dict(building='B', image='I1', pool_id='p1', q=1)] * 9 +
                      [dict(building='B', image='I2', pool_id='p2', q=9)])
    out = module.equal_image_stats(df, 'q')
    assert out['mean_image'] == 5 and out['valid_events'] == 10 and out['valid_images'] == 2


def test_shared_four_endpoint_gate_preserves_net_identity():
    dc, db, net = module.paired_change([10, np.nan], [12, 15], [20, 21], [25, 23])
    assert dc[0] == 5 and db[0] == 2 and net[0] == 3
    assert np.isnan(dc[1]) and np.isnan(db[1]) and np.isnan(net[1])


def test_blocks_reject_overlap_even_if_team_sizes_match():
    row = dict(D='W1', X='W2', Y='W3', Z='W4', n=2, m=1,
               A_members='W1|W2', B_members='W1|W3', C_members='W1|W4')
    module.validate_blocks(row)
    row['Z'] = 'W2'
    row['C_members'] = 'W1|W2'
    with pytest.raises(AssertionError):
        module.validate_blocks(row)


def test_written_schema_and_all_methods_have_original_cases():
    out = module.OUT
    if not (out / 'CHECKS.json').exists():
        pytest.skip('run evidence builder first')
    matrix = pd.read_csv(out / 'METHOD_EVIDENCE_MATRIX.csv')
    dimensions = pd.read_csv(out / 'METHOD_DIMENSION_COVERAGE.csv')
    cases = pd.read_csv(out / 'METHOD_ORIGINAL_CASES.csv')
    assert len(matrix) == 45 and matrix.method.is_unique
    assert len(dimensions) == 45 * 8
    assert set(matrix.method) == set(cases.method)
    assert (matrix.original_answer_cases > 0).all()
    assert set(pd.read_csv(out / 'EXACT_HALF_CONDITIONS.csv').replacement_band) == {'exact_half'}
    assert set(pd.read_csv(out / 'ABOVE_HALF_CONDITIONS.csv').replacement_band) == {'above_half'}
    numerical = pd.read_csv(out / 'ALL_DIMENSION_N_M_RESULTS.csv')
    assert len(numerical) == 7356
    assert {'B8L2_CB_mean_image', 'B8L2_CB_valid_images', 'boundary_loss_CB_mean_image',
            'direction_loss_CB_mean_image', 'height_loss_CB_mean_image',
            'record_time_CB_pct_source_matched_valid_images', 'A_failed_mean_image'} <= set(numerical)
    for filename in ['FORMAL_DIFFICULTY_RESULTS.csv', 'STRUCTURAL_CONDITION_RESULTS.csv']:
        assert set(pd.read_csv(out / filename).method) == set(matrix.method)
    sources = pd.read_csv(out / 'SOURCE_INDEX.csv')
    assert all((module.ROOT / p).is_file() for p in sources.source_path)
