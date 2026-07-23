"""Join P1, C1 and C2-B evidence without accepting prefilled final gates."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file, write_csv_rows


def _read(path: Path | None) -> list[dict[str, str]]:
    if path is None:
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _index(rows: list[dict[str, str]], label: str) -> dict[tuple[str, str], dict[str, str]]:
    output = {}
    for row in rows:
        key = (str(row.get("worker_id", "")).strip(), str(row.get("component_family", "")).strip())
        if not all(key) or key in output:
            raise ValueError(f"{label} requires unique worker_id+component_family")
        output[key] = row
    return output


def materialize(
    p1_raw_csv: Path, p1_integrity_csv: Path, c1_predictive_csv: Path, output_dir: Path,
    *, c2b_confirmatory_csv: Path | None = None, profile_version: str = "candidate",
) -> dict[str, Any]:
    raw = _index(_read(p1_raw_csv), "P1 raw")
    clean = _index(_read(p1_integrity_csv), "P1 integrity")
    predictive = _index(_read(c1_predictive_csv), "C1 predictive")
    confirmatory = _index(_read(c2b_confirmatory_csv), "C2-B confirmatory")
    rows = []
    for key in sorted(set(raw) | set(clean) | set(predictive) | set(confirmatory)):
        p1, integrity, c1, c2 = raw.get(key, {}), clean.get(key, {}), predictive.get(key, {}), confirmatory.get(key, {})
        p1_ok = _truth(integrity.get("p1_integrity_eligible"))
        c1_ok = p1_ok and _truth(c1.get("c1_predictive_validated"))
        c2_ok = c1_ok and _truth(c2.get("c2b_confirmed"))
        direction = c1_ok and _truth(c1.get("direction_consistent")) and (not c2 or _truth(c2.get("direction_consistent", "true")))
        loto = _truth(c1.get("leave_one_task_out_stable"))
        lobo = _truth(c1.get("leave_one_block_out_stable"))
        activation = _truth(c1.get("routing_activation_allowed"))
        enabled = c2_ok and direction and loto and lobo and activation
        reasons = []
        if not p1_ok: reasons.append("p1_integrity_ineligible")
        if p1_ok and not c1_ok: reasons.append("c1_predictive_not_validated")
        if c1_ok and not c2_ok: reasons.append("pending_c2b_confirmation" if not c2 else "c2b_not_confirmed")
        if not direction: reasons.append("direction_inconsistent")
        if not loto: reasons.append("loto_unstable")
        if not lobo: reasons.append("lobo_unstable")
        if not activation: reasons.append("activation_not_allowed")
        rows.append({
            "worker_id": key[0], "component_family": key[1],
            "p1_raw_effect": p1.get("p1_raw_effect", p1.get("effect", "")),
            "p1_integrity_eligible": p1_ok,
            "c1_predictive_effect": c1.get("c1_predictive_effect", c1.get("effect", "")),
            "c1_predictive_interval": c1.get("c1_predictive_interval", c1.get("interval", "")),
            "c1_predictive_validated": c1_ok,
            "c2b_confirmatory_effect": c2.get("c2b_confirmatory_effect", c2.get("effect", "")),
            "c2b_confirmatory_interval": c2.get("c2b_confirmatory_interval", c2.get("interval", "")),
            "c2b_confirmed": c2_ok,
            "shrunk_effect": c2.get("shrunk_effect", "") if c2_ok else "",
            "support_count": c2.get("support_count", c1.get("support_count", integrity.get("support_count", ""))),
            "direction_consistent": direction,
            "leave_one_task_out_stable": loto,
            "leave_one_block_out_stable": lobo,
            "routing_activation_allowed": activation,
            "full_component_eligible": enabled,
            "disable_reason": ";".join(reasons),
            "evidence_status": "validated_routing_component" if enabled else ("pending_c2b_confirmation" if "pending_c2b_confirmation" in reasons else "diagnostic_or_predictive_only"),
            "profile_version": profile_version,
        })
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv_rows(output_dir / "routing_component_evidence.csv", rows)
    audit = {
        "profile_version": profile_version,
        "n_components": len(rows),
        "n_full_component_eligible": sum(bool(row["full_component_eligible"]) for row in rows),
        "c2b_confirmation_present": c2b_confirmatory_csv is not None,
        "input_sha256": {
            "p1_raw_csv": sha256_file(p1_raw_csv), "p1_integrity_csv": sha256_file(p1_integrity_csv),
            "c1_predictive_csv": sha256_file(c1_predictive_csv),
            **({"c2b_confirmatory_csv": sha256_file(c2b_confirmatory_csv)} if c2b_confirmatory_csv else {}),
        },
    }
    (output_dir / "routing_component_evidence.audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p1-raw-csv", type=Path, required=True)
    parser.add_argument("--p1-integrity-csv", type=Path, required=True)
    parser.add_argument("--c1-predictive-csv", type=Path, required=True)
    parser.add_argument("--c2b-confirmatory-csv", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--profile-version", required=True)
    args = parser.parse_args()
    print(json.dumps(materialize(
        args.p1_raw_csv, args.p1_integrity_csv, args.c1_predictive_csv, args.output_dir,
        c2b_confirmatory_csv=args.c2b_confirmatory_csv, profile_version=args.profile_version,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
