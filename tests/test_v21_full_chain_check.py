import pandas as pd
import pytest
from tools.thesis_main.analysis.check_v21_full_chain_20261030 import compare_tables


def test_saved_result_comparison_preserves_missing_support(tmp_path):
    a, b = tmp_path / 'a.csv', tmp_path / 'b.csv'
    pd.DataFrame({'id': ['a', 'b'], 'Q': [1.0, None]}).to_csv(a, index=False)
    pd.DataFrame({'id': ['a', 'b'], 'Q': [1.0 + 1e-12, None]}).to_csv(b, index=False)
    assert compare_tables(a, b)['rows'] == 2
    pd.DataFrame({'id': ['a', 'b'], 'Q': [1.0, 0.0]}).to_csv(b, index=False)
    with pytest.raises(AssertionError, match='missing support changed'):
        compare_tables(a, b)
    pd.DataFrame({'id': ['a', 'b'], 'Q': [2.0, None]}).to_csv(b, index=False)
    with pytest.raises(AssertionError):
        compare_tables(a, b)
