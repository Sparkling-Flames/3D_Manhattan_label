from __future__ import annotations

from pathlib import Path


SOURCE = Path(__file__).with_name("analyze_threshold_anchoring_worker_types_20260823.py")


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count == 1:
        return text.replace(old, new)
    if count == 0 and new in text:
        return text
    raise RuntimeError(f"patch cardinality failure: {count}: {old[:120]}")


def replace_many(text: str, old: str, new: str, expected: int) -> str:
    count = text.count(old)
    if count == expected:
        return text.replace(old, new)
    if count == 0 and text.count(new) == expected:
        return text
    raise RuntimeError(f"patch cardinality failure: {count}/{expected}: {old[:120]}")


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "THRESHOLDS = (0.90, 0.925, 0.93, 0.95, 0.97, 0.98)\n",
        "THRESHOLDS = (0.90, 0.925, 0.93, 0.95, 0.97, 0.98)\n"
        "PREFIX_THRESHOLDS = (0.90, 0.925, 0.95, 0.98)\n",
    )
    text = replace_once(
        text,
        "        for threshold in THRESHOLDS:\n            topology.Q_BOUNDARY = threshold\n",
        "        for threshold in PREFIX_THRESHOLDS:\n            topology.Q_BOUNDARY = threshold\n",
    )
    text = replace_once(
        text,
        'task_quality = task[["base_task_id", "initial_quality_mean", "building_id"]].copy()',
        'task_quality = task[["base_task_id", "initial_quality_mean"]].copy()',
    )
    text = replace_once(
        text,
        '        quality["proposal_correct_stratum"] = numeric(quality["initial_quality_mean"]) >= proposal_cutoff\n',
        '        quality["proposal_correctness_observed"] = numeric(quality["initial_quality_mean"]).notna()\n'
        '        quality["proposal_correct_stratum"] = numeric(quality["initial_quality_mean"]) >= proposal_cutoff\n',
    )
    text = replace_once(
        text,
        '                sub = quality[quality["proposal_correct_stratum"].eq(stratum)].copy()\n',
        '                sub = quality[quality["proposal_correctness_observed"] & quality["proposal_correct_stratum"].eq(stratum)].copy()\n',
    )
    text = replace_once(
        text,
        '    response["initial_correct_095"] = response["U_initial"] >= 0.95\n'
        '    response["final_correct_095"] = response["U_final"] >= 0.95\n'
        '    response["correct_proposal_degraded_095"] = response["initial_correct_095"] & (~response["final_correct_095"])\n'
        '    response["wrong_proposal_corrected_095"] = (~response["initial_correct_095"]) & response["final_correct_095"]\n'
        '    response["wrong_proposal_retained_exact"] = (~response["initial_correct_095"]) & response["exact_geometry_equal_bool"]\n',
        '    response["proposal_correctness_observed_095"] = response["U_initial"].notna() & response["U_final"].notna()\n'
        '    response["initial_correct_095"] = response["proposal_correctness_observed_095"] & (response["U_initial"] >= 0.95)\n'
        '    response["final_correct_095"] = response["proposal_correctness_observed_095"] & (response["U_final"] >= 0.95)\n'
        '    response["correct_proposal_degraded_095"] = response["proposal_correctness_observed_095"] & response["initial_correct_095"] & (~response["final_correct_095"])\n'
        '    response["wrong_proposal_corrected_095"] = response["proposal_correctness_observed_095"] & (~response["initial_correct_095"]) & response["final_correct_095"]\n'
        '    response["wrong_proposal_retained_exact"] = response["proposal_correctness_observed_095"] & (~response["initial_correct_095"]) & response["exact_geometry_equal_bool"]\n',
    )
    text = replace_many(
        text,
        '        wrong = group[~group["initial_correct_095"]]\n',
        '        wrong = group[group["proposal_correctness_observed_095"] & (~group["initial_correct_095"])]\n',
        2,
    )
    text = replace_many(
        text,
        '        correct = group[group["initial_correct_095"]]\n',
        '        correct = group[group["proposal_correctness_observed_095"] & group["initial_correct_095"]]\n',
        2,
    )
    text = replace_once(
        text,
        '    cause_cols = [c for c in cause.columns if c in {\n'
        '        "base_task_id", "cause_code", "manual_review_priority", "GT_gap", "image_reference",\n'
        '        "task_condition", "condition",\n'
        '    }]\n'
        '    if "base_task_id" in cause_cols:\n'
        '        agg = cause[cause_cols].groupby("base_task_id", as_index=False).agg(\n'
        '            observable_cause_codes=("cause_code", lambda s: ";".join(sorted(set(map(str, s.dropna()))))),\n'
        '            cause_audit_rows=("cause_code", "size"),\n'
        '        )\n'
        '        result = result.merge(agg, on="base_task_id", how="left")\n',
        '    cause_field = (\n'
        '        "observable_geometric_difference_codes"\n'
        '        if "observable_geometric_difference_codes" in cause.columns\n'
        '        else "cause_code" if "cause_code" in cause.columns else None\n'
        '    )\n'
        '    if cause_field is not None and "base_task_id" in cause.columns:\n'
        '        agg = cause[["base_task_id", cause_field]].groupby("base_task_id", as_index=False).agg(\n'
        '            observable_cause_codes=(cause_field, lambda s: ";".join(sorted({code for value in s.dropna().astype(str) for code in value.split(";") if code}))),\n'
        '            cause_audit_rows=(cause_field, "size"),\n'
        '        )\n'
        '        result = result.merge(agg, on="base_task_id", how="left")\n',
    )

    SOURCE.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
