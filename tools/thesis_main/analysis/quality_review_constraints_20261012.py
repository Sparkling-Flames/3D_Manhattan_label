"""开发审核约束核查；独立复算已有标量，不重建几何、不拟合参数或修改资格。"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from zipfile import ZipFile


METRICS = ("iou_2d", "dir", "flat", "Hmean", "Hcenter", "S_top_deg", "S_bottom_deg")
PANELS = {
    "P01": ("R02015", "R00637", "overall_B01_preferred"),
    "C01": ("R01810", "R01385", "uncertain_qualitatively_close"),
    "C02": ("R03351", "R03350", "uncertain_qualitatively_close"),
    "C03": ("R01033", "R01022", "A_preferred_both_good"),
    "C04": ("R02447", "R01973", "qualitatively_close"),
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def components(m, c):
    """复算明确给出的现有配置；top-only 是评价算子，不是独立物理误差分解。"""
    i, d, f, hm, hc, st, sb = (float(m[k]) for k in METRICS)
    old_d, old_f = .075 * d * d / (d * d + 25), .075 * f * f / (f * f + 4)
    direction, direction_fraction = 0.0, 0.0
    mode = c["direction_mode"]
    if mode == "old_numerator":
        direction_fraction = old_d
    elif mode == "bounded_denominator":
        direction = c["direction_cap"] * d * d / (d * d + c["direction_scale_deg"] ** 2)
    elif mode == "unbounded_denominator":
        direction = (d / c["direction_scale_deg"]) ** 2
    else:
        raise ValueError(mode)
    flat_fraction = old_f if c["flat_mode"] == "old_numerator" else 0.0
    if c["flat_mode"] not in ("old_numerator", "none"):
        raise ValueError(c["flat_mode"])
    if c.get("height_mean_representation") == "absolute_log_ratio":
        hm = abs(math.log(float(m["height_mean_ratio"])))
    global_height, local_height = (hm / c["height_mean_scale"]) ** 2, (hc / c["height_center_scale"]) ** 2
    combine = {"sum": sum, "max": max}
    height = combine[c["height_combine"]]([global_height, local_height])
    top = c["top_weight"] * st * st / 32
    top_height = combine[c["top_combine"]]([height, top])
    base = 1 + sb * sb / 32 + direction
    score = 100 * i * (1 - direction_fraction - flat_fraction) / (base + top_height)
    without = 100 * i * (1 - direction_fraction) / base
    return {
        "score": score, "global_height_loss": global_height, "local_height_loss": local_height,
        "top_boundary_loss": top, "combined_top_height_loss": top_height,
        "flat_numerator_fraction": flat_fraction, "direction_denominator": direction,
        "direction_numerator_fraction": direction_fraction,
        "top_only_penalty": 1 - (1 - flat_fraction) / (1 + top_height),
        "score_without_top_height": without, "actual_top_height_score_drop": without - score,
        "actual_top_height_relative_drop": 1 - score / without if without else None,
    }


def local_scale_boundary(a, b, mean_scale, top_weight):
    """在无F、相加、相对均高平方族中，B顶部应罚更重所需的hc严格上界。"""
    numerator = float(b["Hcenter"]) ** 2 - float(a["Hcenter"]) ** 2
    denominator = ((float(a["Hmean"]) ** 2 - float(b["Hmean"]) ** 2) / mean_scale ** 2
                   + top_weight * (float(a["S_top_deg"]) ** 2 - float(b["S_top_deg"]) ** 2) / 32)
    if numerator <= 0 or denominator <= 0:
        raise ValueError("This directional upper-bound derivation requires positive differences")
    return math.sqrt(numerator / denominator)


def periodic_pair(top_x, bottom_x, width=1024):
    delta = (bottom_x - top_x + width / 2) % width - width / 2
    return {"shared_x": (top_x + delta / 2) % width,
            "gap_px": abs(delta), "gap_deg": abs(delta) * 360 / width}


def compact_row(row, names):
    key = row.get("record_id") or row["case_id"]
    status = row.get("status", "available")
    metadata = {k: row[k] for k in (
        "record_id", "case_id", "image_id", "image_code", "worker_id", "building_id", "reference_object_id",
        "original_holdout", "pairing_basis", "family", "evidence_layer", "evidence_class",
        "wall_height_ratio", "horizontal_scale", "mode", "camera_inside_height_assumption",
        "scope_reference_acceptance", "ring_confirmed", "unavailable_reason") if k in row}
    if status != "available":
        return {"id": key, "status": status, "metadata": metadata}
    metrics = {k: float(row[k]) for k in METRICS}
    ratio = row.get("height_mean_ratio")
    if ratio not in (None, ""):
        metrics["height_mean_ratio"] = float(ratio)
    elif row.get("annotation_height_mean_h") not in (None, ""):
        metrics["height_mean_ratio"] = float(row["annotation_height_mean_h"]) / float(row["reference_height_mean_h"])
    return {"id": key, "status": status, "metadata": metadata, "metrics": metrics,
            "expected_scores": {name: float(row[name]) for name in names if row.get(name) not in (None, "")}}


def import_evidence(extension, handoff, prior_zip):
    configs = read_json(extension / "height/candidate_config.json")["candidates"]
    configs += read_json(extension / "height/candidate_config_log_addendum.json")["candidates"]
    names = [c["name"] for c in configs]
    files = {
        "real39": "height/results/candidate_scores_39.csv",
        "prior_height71": "height/results/candidate_scores_prior_height71.csv",
        "structure43": "height/results/candidate_scores_structure_controls.csv",
        "matched65": "height/results/matched_control_scores.csv",
    }
    tables = {}
    for name, relative in files.items():
        with (extension / relative).open(encoding="utf-8-sig", newline="") as stream:
            tables[name] = [compact_row(row, names) for row in csv.DictReader(stream)]
    selection = read_json(extension / "structure/review_pairs/selection_research.json")
    tables["targeted8"] = [compact_row(row, names) for pair in selection["selected_pairs"]
                           for row in pair["source_scores_and_components"]]
    with ZipFile(prior_zip) as archive:
        member = "quality_top_structure_research_20261012/top_structure_20261012/review/inputs/review_inputs.json"
        review_inputs = json.loads(archive.read(member))
    p05 = next(row for row in review_inputs["records"] if row["record_id"] == "R00678")
    input_fields = ("object_id", "image_code", "before_preprocessing_points", "original_export_points",
                    "links_zero_based", "preprocessed_points", "ordered_source_pair_indices", "ring_confirmed", "pairing_basis")
    feedback = read_json(handoff / "02_human_review/latest_interpretation.json")
    raw_receipt = read_json(handoff / "02_human_review/original_receipt.json")
    mapping = read_json(handoff / "02_human_review/dataset_mapping.json")
    assert feedback["dataset_id"] == raw_receipt["dataset_id"] == mapping["dataset_id"]
    return {
        "schema": "quality_review_constraint_evidence_v1", "configs": configs, "tables": tables,
        "feedback": feedback, "raw_receipt": raw_receipt,
        "dataset_mapping": mapping,
        "qualification_snapshot": read_json(extension / "evidence/results/qualification_summary.json"),
        "p05_input": {k: p05["current_formal_input"][k] for k in input_fields},
        "provenance": {"extension_root": str(extension), "handoff_root": str(handoff),
                       "prior_zip": str(prior_zip), "prior_member": member, "tables": files,
                       "transform": "保留所列数值、既有候选分数和状态；不重新生成几何、参考或标签；无SHA检查"},
    }


def audit(evidence):
    configs = evidence["configs"]
    parity = []
    for table, rows in evidence["tables"].items():
        errors, missing, unavailable = [], [], []
        for row in rows:
            if row["status"] != "available":
                unavailable.append({"id": row["id"], "status": row["status"], "metadata": row["metadata"]})
                continue
            for c in configs:
                if c["name"] not in row["expected_scores"]:
                    missing.append([row["id"], c["name"]])
                    continue
                value = components(row["metrics"], c)["score"]
                delta = abs(value - row["expected_scores"][c["name"]])
                if not math.isfinite(delta) or delta > 1e-9:
                    raise ValueError(f"Scalar mismatch: {table}, {row['id']}, {c['name']}, {delta}")
                errors.append(delta)
        parity.append({"table": table, "rows": len(rows), "scalar_cells": len(errors),
                       "max_absolute_delta": max(errors), "unavailable": unavailable,
                       "missing_candidate_cells": missing})
    records = {r["id"]: r for r in evidence["tables"]["real39"]}
    for row in evidence["tables"]["targeted8"]:
        if row["id"] in records:
            assert all(math.isclose(row["metrics"][k], records[row["id"]]["metrics"][k], rel_tol=0, abs_tol=1e-10) for k in METRICS)
        else:
            records[row["id"]] = row
    # Post-feedback identification probes: same hm/hc ratio=4 as the existing mean1
    # branch, achieved by strengthening local loss instead of weakening global loss.
    base = next(c for c in configs if c["name"] == "Q_dbounded1_hsplit")
    probes = [dict(base, name="probe_local0125_noTop", height_center_scale=.125),
              dict(base, name="probe_local0125_weakTop", height_center_scale=.125, top_weight=1/16)]
    evaluated = configs + probes
    feedback = evidence["feedback"]["interpretations"]
    # These bindings are part of this named audit, not a generic grade parser.
    assert feedback["P01"]["choice"] == "B01更好"
    assert feedback["P04"]["scope"] == "top_penalty_only" and feedback["P04"]["choice"] == "B06应罚更重"
    assert all(feedback[p]["choice"] == "不确定" and feedback[p]["numeric_margin"] is None for p in ("C01", "C02"))
    pairs = []
    for panel, (a, b, interpretation) in PANELS.items():
        scores = []
        for c in evaluated:
            # New paired examples have no saved mean ratio: do not infer its sign from Hmean.
            if c.get("height_mean_representation") == "absolute_log_ratio" and any(
                    "height_mean_ratio" not in records[r]["metrics"] for r in (a, b)):
                continue
            qa, qb = (components(records[r]["metrics"], c)["score"] for r in (a, b))
            scores.append({"candidate": c["name"], "score_a": qa, "score_b": qb, "a_minus_b": qa - qb,
                           "strict_preference_agrees": qa > qb if panel in ("P01", "C03") else None})
        pairs.append({"panel": panel, "a": a, "b": b, "interpretation": interpretation,
                      "numeric_close_tolerance": None, "close_pass_fail_assigned": False, "scores": scores})
    a, b = (records[r]["metrics"] for r in ("R00397", "R00418"))
    top = []
    for c in evaluated:
        ta, tb = components(a, c), components(b, c)
        top.append({"candidate": c["name"], "T20": ta, "S034": tb,
                    "P04_direction_agrees_under_declared_top_operator": tb["top_only_penalty"] > ta["top_only_penalty"]})
    bounds = [{"mean_scale": hm, "top_weight": gamma,
               "local_scale_strict_upper_bound": local_scale_boundary(a, b, hm, gamma)}
              for hm, gamma in ((.5, 0), (.5, 1/16), (1, 0))]
    original = evidence["p05_input"]
    input_pairs = []
    for pair_index, (t, btm) in enumerate(original["links_zero_based"]):
        points = original["before_preprocessing_points"]
        pair = periodic_pair(points[t][0], points[btm][0])
        shared = original["preprocessed_points"]
        assert all(abs((shared[j][0] - pair["shared_x"] + 512) % 1024 - 512) < 1e-9 for j in (t, btm))
        input_pairs.append({"source_pair_index_zero_based": pair_index, "source_point_indices_zero_based": [t, btm],
                            "top_x_before": points[t][0], "bottom_x_before": points[btm][0], **pair})
    controlled = []
    for table in ("matched65", "prior_height71", "structure43"):
        for row in evidence["tables"][table]:
            if row["status"] == "available":
                controlled.append({"table": table, "id": row["id"], "metadata": row["metadata"],
                                   "scores": row["expected_scores"],
                                   "post_feedback_probes": {c["name"]: components(row["metrics"], c)["score"] for c in probes},
                                   "human_grade": None})
    return {
        "schema": "quality_review_constraint_audit_v1", "status": "development_diagnostic_not_calibrated",
        "unique_real_records_in_scalar_pool": len(records),
        "probe_definitions": {"stage": "post_feedback_analytic_identification_probe_not_selection",
                              "purpose": "同一整体/局部相对尺度可由两种改变产生；检验绝对处罚差异及弱顶部交互",
                              "configs": probes, "grid_search": False, "new_parameters_fitted": False},
        "parity": parity, "overall_pairs": pairs, "P04": top, "P04_conditional_boundaries": bounds,
        "P05": {"record_id": "R00678", "input": original, "pairs": input_pairs,
                "largest_gap_pair": max(input_pairs, key=lambda p: p["gap_px"]),
                "raw_export_equals_current_before": original["original_export_points"] == original["before_preprocessing_points"],
                "same_midpoint_distinct_input_counterexample": [periodic_pair(1018, 6), periodic_pair(0, 0)],
                "semantic_issue_source": "user_P05_observation_plus_separate_local_image_inspection",
                "input_quality_grade": None, "automatic_pairing_repair": False, "overall_quality_certified": False},
        "controlled_results": controlled,
        "scope": {"candidate_parameters_fitted": False, "new_human_labels": 0, "new_geometries": 0,
                  "independent_human_validation": False, "formal_scores_changed": False,
                  "eligibility_changed": False, "unknown_feedback_imputed": False},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--extension-root", type=Path)
    parser.add_argument("--handoff-root", type=Path)
    parser.add_argument("--prior-zip", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    evidence_path = args.output / "evidence.json"
    if args.extension_root:
        if not args.handoff_root or not args.prior_zip:
            parser.error("import requires extension-root, handoff-root and prior-zip")
        evidence = import_evidence(args.extension_root, args.handoff_root, args.prior_zip)
        save_json(evidence_path, evidence)
    else:
        evidence = read_json(evidence_path)
    result = audit(evidence)
    save_json(args.output / "audit.json", result)
    print(json.dumps({"tables": [{k: row[k] for k in ("table", "rows", "scalar_cells", "max_absolute_delta")}
                                 for row in result["parity"]],
                      "P04_agreeing_candidates": [r["candidate"] for r in result["P04"] if r["P04_direction_agrees_under_declared_top_operator"]]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
