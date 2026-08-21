from __future__ import annotations

import pandas as pd

from tools.paper_a_manhattan.full_uncertainty import audit_v5_followup as audit


_original_read_csv = audit.read_csv
_legacy_task_proxy = (
    audit.ROOT
    / "analysis_results"
    / "annotation_uncertainty_manual_semi_20260820_v2"
    / "DIFFICULTY_PROXY_COVERAGE.csv"
)


def _read_csv(name: str) -> pd.DataFrame:
    if name == "DIFFICULTY_PROXY_COVERAGE.CSV":
        if not _legacy_task_proxy.is_file():
            raise FileNotFoundError(_legacy_task_proxy)
        return pd.read_csv(_legacy_task_proxy, low_memory=False)
    return _original_read_csv(name)


audit.read_csv = _read_csv


if __name__ == "__main__":
    audit.main()
