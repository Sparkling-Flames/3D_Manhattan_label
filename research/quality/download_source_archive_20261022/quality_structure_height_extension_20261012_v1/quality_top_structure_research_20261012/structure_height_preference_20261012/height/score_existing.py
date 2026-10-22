#!/usr/bin/env python3
"""Apply frozen finite candidates to existing developer metrics, without refits."""
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from candidate_functions import score, parameter_terms, NEW_METHODS


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def csvwrite(path, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def csvread(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def actual_mean_ratio(annotation, reference):
    """Exact linear edge integral of height on each own bottom perimeter."""
    def mean(g):
        b, t = g["bottom3d"], g["top3d"]
        h = [tt[1]-bb[1] for tt, bb in zip(t, b)]
        n = len(b)
        lengths = [math.hypot(b[(i+1)%n][0]-b[i][0], b[(i+1)%n][2]-b[i][2]) for i in range(n)]
        return math.fsum(lengths[i]*(h[i]+h[(i+1)%n])/2 for i in range(n)) / math.fsum(lengths)
    am, gm = mean(annotation), mean(reference)
    return {"annotation_height_mean_h": am, "reference_height_mean_h": gm, "height_mean_ratio": am/gm}


def gates(root=ROOT):
    registry = root / "structure_height_preference_20261012/inputs/main_snapshot/research/quality_holdout_exposure_correction_20261011/exposure_registry.json"
    manifest = root / "previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010/results/room_holdout_manifest.csv"
    reg = json.loads(registry.read_text())
    held = {row["record_id"] for row in csvread(manifest) if row["held_out_of_sample_and_future_calibration"] == "True"}
    exposed = {row["record_id"] for row in reg["screen_records_in_original_holdout"] if row["exclude_from_calibration"]}
    assert len(held) == reg["original_heldout_records"] == 282
    assert len(exposed) == 14 and exposed <= held
    return held, {"registry_sha256": sha(registry), "original_holdout_manifest_sha256": sha(manifest),
                  "held_count": len(held), "exposed_holdout_count": len(exposed),
                  "all_exposed_excluded": True, "no_clean_test_set_claim": True}


def main():
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    held, proof = gates()
    qualified = json.loads((ROOT / "structure_height_preference_20261012/evidence/results/numerical_evidence_39.json").read_text())
    eligible = {r["record_id"] for r in qualified}
    assert len(eligible) == 39 and not eligible & held
    sources = {
        "real39": ROOT / "top_structure_20261012/analysis/results/candidate_scores_39.json",
        "prior_height71": ROOT / "top_structure_20261012/analysis/results/candidate_scores_synthetic.csv",
        "structure40": ROOT / "structure_height_preference_20261012/structure/results/synthetic_metrics.csv",
    }
    real = json.loads(sources["real39"].read_text())
    assert {r["record_id"] for r in real} == eligible
    geometry_path = ROOT / "previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010/inputs/current_geometry_compact.json"
    geometries = json.loads(geometry_path.read_text())["geometries"]
    structure_design_path = ROOT / "structure_height_preference_20261012/structure/results/synthetic_design.json"
    structure_design = {r["case_id"]:r for r in json.loads(structure_design_path.read_text())}
    rows = []
    details = []
    for record in real:
        row = dict(record)
        row.update(actual_mean_ratio(geometries[row["object_id"]], geometries[row["reference_object_id"]]))
        row["case_id"] = record.get("old_case_id") or record.get("new_case_id")
        row.update(score(row))
        assert abs(row["Q_hsplit_top0"] - row["Q_split_local025"]) < 1e-10
        rows.append(row)
        details.append({"case_id": row["case_id"], "record_id": row["record_id"], "image_code": row["image_code"],
                        "parameter_terms": parameter_terms(row)})
    csvwrite(out / "candidate_scores_39.csv", rows)
    dump(out / "candidate_scores_39.json", rows)
    dump(out / "candidate_terms_39.json", details)
    counts = {}
    for group in ("prior_height71", "structure40"):
        results = []
        for record in csvread(sources[group]):
            row = dict(record)
            if record.get("status") == "available":
                if group == "structure40":
                    case = structure_design[row["case_id"]]
                    row.update(actual_mean_ratio(case["annotation"], case["reference"]))
                row.update(score(row))
            results.append(row)
        csvwrite(out / ("candidate_scores_" + group + ".csv"), results)
        if group == "structure40":
            csvwrite(out / "candidate_scores_structure_controls.csv", results)
        counts[group] = {"rows": len(results), "available": sum(r.get("status") == "available" for r in results)}
    dump(out / "existing_score_manifest.json", {"new_method_count": len(NEW_METHODS), "real39": len(rows),
         "reused_synthetic": counts, "gates": proof,
         "input_sha256": {str(p.relative_to(ROOT)): sha(p) for p in sources.values()},
         "config_sha256": sha(HERE / "candidate_config.json"), "protocol_sha256": sha(HERE / "protocol_before_results.json"),
         "log_addendum_sha256": sha(HERE / "candidate_config_log_addendum.json"),
         "geometry_for_actual_height_ratios_sha256": sha(geometry_path),
         "structure_design_for_actual_ratios_sha256": sha(structure_design_path),
         "score_function_sha256": sha(HERE / "candidate_functions.py"),
         "old_split_local025_parity_with_new_top0": "pass", "human_labels_changed": False,
         "new_independent_validation": False})
    dump(out / "STRUCTURE_FILENAME_NOTE.json", {"canonical_file":"candidate_scores_structure_controls.csv",
         "legacy_alias":"candidate_scores_structure40.csv","actual_rows":counts["structure40"]["rows"],
         "reason":"The structural study added protocol-documented controls after the initial40. The legacy alias is retained only for previously running consumers; its number is not the final denominator."})
    print(json.dumps({"real": len(rows), "new_methods": NEW_METHODS, **counts}))


if __name__ == "__main__":
    main()
