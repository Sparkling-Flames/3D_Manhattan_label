import numpy as np
import pandas as pd
import pytest

from tools.thesis_main.analysis.same_room_b8l2_20261016 import QUALITY_METRICS
from tools.thesis_main.analysis.same_room_usage_20261016 import quality_projection


def test_oos_quality_is_masked_including_iou_while_diagnostic_and_time_survive():
    records = pd.DataFrame(dict(is_oos=[False, True, True], is_doorway=[True, False, True],
        reference_quality_allowed=[True, False, False], source_time_seconds=[10., 20., np.nan],
        target_matched_time_seconds=[10., np.nan, np.nan],
        **{metric: [75., 80., 90.] for metric in QUALITY_METRICS}))
    result = quality_projection(records)
    assert result.loc[0, QUALITY_METRICS].eq(75.).all()  # usable doorway is retained
    assert result.loc[[1, 2], QUALITY_METRICS].isna().all().all()
    for metric in QUALITY_METRICS:
        assert result['numeric_' + metric].equals(records[metric])
        assert records[metric].notna().all()
    for field in ['source_time_seconds', 'target_matched_time_seconds']:
        assert result[field].equals(records[field])


def test_inconsistent_shared_permission_cannot_admit_oos_quality():
    with pytest.raises(ValueError, match='OOS'):
        quality_projection(pd.DataFrame(dict(is_oos=[True], reference_quality_allowed=[True])))
