import pandas as pd
import pytest

from tools.thesis_main.analysis.verify_descriptive_statistics_20261015 import check_summary


def test_independent_check_rejects_wrong_mean_and_missing_denominator():
    records = pd.DataFrame(dict(image_id=['a','a','b'], WQ=[10.,30.,None]))
    summary = pd.DataFrame([dict(panel='inventory_test', metric='WQ', n_records=3,
        n_valid=2,n_missing=1,mean=20.,median=20.,sd=2**.5*10,image_equal_mean=20.)])
    assert check_summary(records, summary) == 1
    with pytest.raises(AssertionError):
        check_summary(records, summary.assign(mean=30.))
    with pytest.raises(AssertionError):
        check_summary(records, summary.assign(n_missing=0))
