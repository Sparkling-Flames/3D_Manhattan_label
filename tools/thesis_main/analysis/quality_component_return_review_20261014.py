"""复核分项组合交付并补齐冻结718条；不改参数、几何或资格。"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd


def review(source, native, out):
    out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    # 原交付只识别 FINAL_history，冻结源实际使用 FINAL_historical_only。
    # 仅临时复制文件名，不改源表；原执行回执的硬编码状态不作为本次覆盖依据。
    with tempfile.TemporaryDirectory(prefix="quality_component_tables_") as tmp:
        tables = Path(tmp)
        for name in ("ordinary", "doorway", "severe", "historical_only"):
            alias = "history" if name == "historical_only" else name
            shutil.copyfile(native / f"FINAL_{name}.csv", tables / f"FINAL_{alias}.csv")
        metadata = json.loads((native / "object_and_input_audit.json").read_text(encoding="utf-8"))
        annotations = [r for r in metadata["records"] if r["kind"] == "annotation"]
        assert len(annotations) == 810 and all(isinstance(r["source"], dict) for r in annotations)
        # 原恢复器假定所有source都是字典；完整审核中GT的source是字符串。
        # 仅给人员来源恢复器传入810份作答，97个GT仍由原表绑定保留。
        audit_path = tables / "annotation_sources.json"
        audit_path.write_text(json.dumps({"records": annotations}), encoding="utf-8")
        run = subprocess.run(
            [sys.executable, "-B", str(source / "reproduce.py"),
             "--tables", str(tables), "--source-audit", str(audit_path),
             "--output", str(out / "full_replay")],
            env=env, capture_output=True, text=True, encoding="utf-8")
        (out / "RUN_LOG.txt").write_text(run.stdout + run.stderr, encoding="utf-8")
        if run.returncode:
            raise RuntimeError(run.stderr)

    df = pd.read_csv(out / "full_replay/per_case.csv")
    scored = df[df.execution_status == "scored"].copy()
    assert len(df) == 810 and len(scored) == 718
    assert df.execution_status.value_counts().to_dict() == {"scored": 718, "held_unchanged": 92}
    assert scored.source_layer.value_counts().to_dict() == {
        "ordinary": 574, "doorway": 125, "historical_only": 10, "severe": 9}
    keys = ["record_id", "object_id", "image_id", "reference_object_id"]
    assert not df.record_id.duplicated().any()
    original = pd.concat([pd.read_csv(native / f"FINAL_{name}.csv") for name in
                          ("ordinary", "doorway", "severe", "historical_only")])
    bound = df.merge(original, on=keys, validate="one_to_one", suffixes=("", "_native"))
    assert len(bound) == 810
    for field in ("effective_use", "status", "original_holdout", "personnel_barriers",
                  "context_barriers", "stage2_regression_eligible", "formal_eligibility_newly_granted"):
        assert bound[field].fillna("").equals(bound[field + "_native"].fillna("")), field
    assert not df.formal_eligibility_newly_granted.any()
    assert int(df.stage2_regression_eligible.sum()) == 117
    q01 = df[df.effective_use == "Q01_image_scope_conditional_diagnostic_not_tuning"]
    assert len(q01) == 8 and q01.same_target_worker_quality_Q.isna().all()

    # 独立闭式实现，不导入外部models.py；冻结五项顺序为方向、范围、底边、局部、整体。
    w = np.array([.35, .30, .10, .20, .05])
    p = np.column_stack([
        1.5 * scored["dir"]**2 / (scored["dir"]**2 + 37.5),
        1 / scored.iou_2d - 1, scored.S_bottom_deg**2 / 32,
        (scored.Hcenter / .25)**2, (scored.Hmean / .8)**2])
    v = w[[0, 2, 3, 4]] / .7
    predicted = {
        "WQ_LS08": 100 / (1 + p.sum(axis=1)),
        "arithmetic_candidate": 100 * (w**2 / (w + p)).sum(axis=1),
        "range_anchored_A": 100 * scored.iou_2d.to_numpy() *
            (v**2 / (v + p[:, [0, 2, 3, 4]])).sum(axis=1),
    }
    errors = {name: float(np.max(np.abs(values - scored[name].to_numpy())))
              for name, values in predicted.items()}
    assert max(errors.values()) < 1e-9
    assert np.max(np.abs(scored.WQ_LS08 - scored.working_Q)) < 1e-9
    assert (scored.range_anchored_A <= 100 * scored.iou_2d + 1e-9).all()
    models = list(predicted) + ["geometric_control", "raw_3d_iou"]
    assert df.loc[df.execution_status != "scored", models].isna().all().all()

    partial = pd.read_csv(source / "results/per_case.csv")
    partial = partial[partial.execution_status == "scored"]
    same = partial.merge(scored, on=keys, suffixes=("_partial", "_full"), validate="one_to_one")
    assert len(same) == 331
    measurements = ["iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter", "working_Q", "iou3d_pct"]
    partial_errors = {name: float(np.max(np.abs(same[name + "_partial"] - same[name + "_full"])))
                      for name in measurements + models}
    assert max(partial_errors.values()) < 1e-9

    summary = []
    for (use, condition), rows in scored.groupby(["effective_use", "condition"]):
        delta = rows.range_anchored_A - rows.WQ_LS08
        summary.append(dict(effective_use=use, condition=condition, n=len(rows),
                            images=rows.image_id.nunique(),
                            **{name + "_mean": float(rows[name].mean()) for name in models},
                            RA_higher=int((delta > 1e-9).sum()),
                            RA_lower=int((delta < -1e-9).sum()),
                            RA_equal=int((np.abs(delta) <= 1e-9).sum())))
    result = dict(schema="quality_component_independent_review_v1", rows=810, scored=718, held=92,
                  source_counts=scored.source_layer.value_counts().to_dict(),
                  scored_condition_counts=scored.condition.value_counts().to_dict(),
                  independent_formula_errors=errors, original_subset_comparison_errors=partial_errors,
                  preserved_subset=331, additional_scored=387, q01_diagnostic_only=8,
                  conditional_doorway_regression=117, binding_and_use_preserved=True,
                  raw_geometry_rebuilt=False, personnel_ranking_validated=False,
                  full_3152_scored=False, new_human_labels=False, formal_defaults_changed=False,
                  source_runner_caveats=["FINAL_historical_only.csv requires FINAL_history.csv alias",
                                         "source parser crashes on GT source strings; pass annotation metadata only",
                                         "runner execution_audit contains hardcoded partial-run flags",
                                         "worker means mix different image compositions; not adopted"],
                  summaries=summary)
    (out / "AUDIT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = keys + ["image_code", "building_id", "worker_id", "source_layer", "condition",
                     "condition_evidence", "effective_use", "execution_status", "status",
                     "original_holdout", "exposure", "personnel_barriers", "context_barriers",
                     "formal_gate", "formal_eligibility_newly_granted", "stage2_regression_eligible",
                     "same_target_worker_quality_Q", "reason_codes"] + models
    df[fields].to_csv(out / "FULL_COMPARISON.csv", index=False)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    review(args.source.resolve(), args.native.resolve(), args.output.resolve())
