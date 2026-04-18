from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "init_task_risk_rule_manifest.py"


def test_init_task_risk_rule_manifest(tmp_path: Path) -> None:
    dt_summary = tmp_path / "dt_reference_summary_C1.json"
    dt_summary.write_text(
        json.dumps(
            {
                "meta": {
                    "distance_metric": "euclidean",
                    "k": 10,
                    "q": 0.9,
                    "provisional_tau_d": 0.42,
                },
                "reference_pool": [],
                "loo_summary": {},
                "failure_audit": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    output = tmp_path / "task_risk_rule_manifest_v1.json"
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--dt-summary",
            str(dt_summary),
            "--output",
            str(output),
        ],
        check=True,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["dt_rule"]["metric"] == "euclidean"
    assert payload["dt_rule"]["k"] == 10
    assert payload["dt_rule"]["q"] == 0.9
    assert payload["dt_rule"]["tau_d"] == 0.42
    assert payload["g_trigger_rule"]["missing_policy"] == "NA_and_report"
    assert payload["risk_bucket_rule"]["bucket_names"] == ["ood0_g0", "ood0_g1", "ood1_g0", "ood1_g1"]
    assert payload["risk_bucket_rule"]["bucket_definition"] == "cross_product(I_t_OOD, g_t_triggered)"
    assert payload["risk_bucket_rule"]["assignment_logic"]["stress_bucket_policy"].startswith("ood1_g1 enters stress mode")
    assert payload["risk_bucket_rule"]["r3_default_policy"] == "exclude_from_main_route"


def test_init_task_risk_rule_manifest_rejects_unhealthy_dt_summary(tmp_path: Path) -> None:
    dt_summary = tmp_path / "dt_reference_summary_C1.json"
    dt_summary.write_text(
        json.dumps(
            {
                "meta": {
                    "distance_metric": "euclidean",
                    "k": 10,
                    "q": 0.9,
                    "provisional_tau_d": 0.42,
                },
                "reference_pool": [],
                "loo_summary": {},
                "failure_audit": {
                    "extract_fail_count": 1,
                    "embed_dim_error_count": 0,
                    "knn_runtime_error_count": 0,
                    "ref_hash_mismatch": False,
                    "leakage_check_failed": False,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    output = tmp_path / "task_risk_rule_manifest_v1.json"
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--dt-summary",
                str(dt_summary),
                "--output",
                str(output),
            ],
            check=True,
        )


def test_init_task_risk_rule_manifest_requires_tau_d_by_default(tmp_path: Path) -> None:
    dt_summary = tmp_path / "dt_reference_summary_C1.json"
    dt_summary.write_text(
        json.dumps(
            {
                "meta": {
                    "distance_metric": "euclidean",
                    "k": 10,
                    "q": 0.9,
                    "provisional_tau_d": None,
                },
                "reference_pool": [],
                "loo_summary": {},
                "failure_audit": {
                    "extract_fail_count": 0,
                    "embed_dim_error_count": 0,
                    "knn_runtime_error_count": 0,
                    "ref_hash_mismatch": False,
                    "leakage_check_failed": False,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    output = tmp_path / "task_risk_rule_manifest_v1.json"
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--dt-summary",
                str(dt_summary),
                "--output",
                str(output),
            ],
            check=True,
        )
