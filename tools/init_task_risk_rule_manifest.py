from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_G_TRIGGER_DEFINITION = (
    "trigger when prediction-side structural diagnostics fail before human labeling, "
    "including invalid or self-intersecting polygon construction, topology closure failure, "
    "duplicate or anomalous corners, or computable gating/render failure"
)
STRICT_FAILURE_BOOL_KEYS = ("ref_hash_mismatch", "leakage_check_failed")
STRICT_FAILURE_COUNT_KEYS = ("extract_fail_count", "embed_dim_error_count", "knn_runtime_error_count")


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def _as_int(value: object) -> int:
    if value in {None, ""}:
        return 0
    return int(value)


def load_dt_summary(path: Path, *, strict_health: bool = True, require_tau_d: bool = True) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("dt summary must contain meta")
    required = ("distance_metric", "k", "q")
    missing = [key for key in required if key not in meta]
    if missing:
        raise ValueError(f"dt summary meta missing keys: {', '.join(missing)}")
    if require_tau_d and meta.get("provisional_tau_d") in {None, ""}:
        raise ValueError("dt summary meta.provisional_tau_d must be materialized before initializing task risk manifest")

    failure_audit = payload.get("failure_audit")
    if not isinstance(failure_audit, dict):
        raise ValueError("dt summary must contain failure_audit")

    if strict_health:
        failed_bools = [key for key in STRICT_FAILURE_BOOL_KEYS if _as_bool(failure_audit.get(key))]
        failed_counts = [key for key in STRICT_FAILURE_COUNT_KEYS if _as_int(failure_audit.get(key)) > 0]
        if failed_bools or failed_counts:
            detail = failed_bools + failed_counts
            raise ValueError(
                "dt summary failed strict health gate: "
                + ", ".join(detail)
            )
    return payload


def build_manifest(
    dt_summary: dict,
    *,
    dt_summary_ref: str,
    locked_round: str,
    contract_version: str,
) -> dict:
    meta = dt_summary["meta"]
    tau_d = meta.get("provisional_tau_d")

    return {
        "meta": {
            "contract_version": contract_version,
            "locked_round": locked_round,
            "created_from": dt_summary_ref,
        },
        "dt_rule": {
            "source_artifact": dt_summary_ref,
            "metric": meta["distance_metric"],
            "k": meta["k"],
            "q": meta["q"],
            "tau_d": tau_d,
        },
        "ood_trigger_rule": {
            "definition": "I_t_OOD = 1[d_t > tau_d]",
            "allow_silent_filter": False,
        },
        "g_trigger_rule": {
            "source": "pre_annotation_prediction_structure_checks",
            "definition": DEFAULT_G_TRIGGER_DEFINITION,
            "missing_policy": "NA_and_report",
        },
        "risk_bucket_rule": {
            "bucket_names": ["ood0_g0", "ood0_g1", "ood1_g0", "ood1_g1"],
            "bucket_definition": "cross_product(I_t_OOD, g_t_triggered)",
            "assignment_logic": {
                "default_bucket_policy": "ood0_g0 allows R0 and audited subset of R1/R2",
                "high_risk_bucket_policy": "ood0_g1 and ood1_g0 reserve the primary pool for R0 workers with LCB(r_u) >= tau_r_high",
                "stress_bucket_policy": "ood1_g1 enters stress mode with tightened candidate pool and increased starting redundancy",
                "r2_exclusion": "exclude R2 workers from buckets where prior failure was recorded",
                "r1_semi_policy": "do not use high blind-trust R1 workers as the primary pool for misleading-initialization-heavy semi tasks",
            },
            "r3_default_policy": "exclude_from_main_route",
        },
        "fallback_rule": {
            "scene_specific_unavailable_action": "degrade_to_global",
            "dt_unavailable_action": "report_and_do_not_silent_filter",
            "g_unavailable_action": "report_and_use_bucket_fallback",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize task_risk_rule_manifest_v1.json from dt_reference_summary_C1.json")
    parser.add_argument("--dt-summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--locked-round", default="C2")
    parser.add_argument("--contract-version", default="v1")
    parser.add_argument(
        "--allow-unhealthy-dt-summary",
        action="store_true",
        help="Bypass strict failure_audit gate. Use only for exploratory artifacts, not thesis-facing frozen manifests.",
    )
    parser.add_argument(
        "--allow-null-tau-d",
        action="store_true",
        help="Allow provisional_tau_d to remain null. Use only before the C1 provisional threshold has been materialized.",
    )
    args = parser.parse_args()

    dt_summary = load_dt_summary(
        args.dt_summary,
        strict_health=not args.allow_unhealthy_dt_summary,
        require_tau_d=not args.allow_null_tau_d,
    )
    manifest = build_manifest(
        dt_summary,
        dt_summary_ref=str(args.dt_summary),
        locked_round=args.locked_round,
        contract_version=args.contract_version,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
