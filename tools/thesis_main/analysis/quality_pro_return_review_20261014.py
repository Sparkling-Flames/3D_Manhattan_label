"""独立复核 Pro 交付的公式、用途与输入；不调用 Pro 的评分函数。"""
import argparse
import json
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[3]


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def audit(source):
    rows = read(source / "results/effective_use_ledger.json")["records"]
    counts = Counter(row["source_layer"] for row in rows)
    assert counts == dict(ordinary=574, severe=9, doorway=217, historical_only=10)
    assert len({row["record_id"] for row in rows}) == len(rows)
    usable = [row for row in rows if row["working_Q"] is not None]
    held = [row for row in rows if row["working_Q"] is None]
    assert len(usable) == 718 and len(held) == 92
    assert all(row["status"] == "held" and row["reason_codes"] for row in held)
    assert not any(row["formal_eligibility_newly_granted"] for row in rows)

    errors = []
    for row in usable:
        overlap = row["iou_2d"]
        loss = (row["S_bottom_deg"] ** 2 / 32
                + 1.5 * row["dir"] ** 2 / (row["dir"] ** 2 + 37.5)
                + (row["Hmean"] / .8) ** 2 + (row["Hcenter"] / .25) ** 2)
        old = 100 * overlap / (1 + loss)
        new = 100 * overlap / (1 + overlap * loss)
        errors.extend([abs(old - row["current_Q"]), abs(new - row["working_Q"])])
        assert 0 <= old <= new + 1e-10 <= 100 * overlap + 1e-9
    assert max(errors) < 1e-9

    height_changes = {}
    for layer in counts:
        group = [row for row in usable if row["source_layer"] == layer]
        delta = [row["working_height_drop"] - row["current_height_drop"] for row in group]
        height_changes[layer] = dict(n=len(group), increased=sum(x > 1e-8 for x in delta),
                                     decreased=sum(x < -1e-8 for x in delta),
                                     unchanged=sum(abs(x) <= 1e-8 for x in delta))

    summary = read(source / "results/ordinary_candidate_summary.json")
    passing = [name for name, result in summary.items()
               if result["evidence"]["P01_margin"] > 0
               and not result["evidence"]["weak_grade_inversions"]
               and not result["evidence"]["severe_vs_light_inversions"]]
    freeze = read(source / "configs/ordinary_frozen.json")
    final = read(source / "configs/WORKING_FINAL.json")
    assert freeze["config"] == final["config"]
    assert final["parameter_changes_after_ordinary_freeze"] == {}
    q01 = [row for row in rows if row["effective_use"] == "Q01_image_scope_conditional_diagnostic_not_tuning"]
    assert len(q01) == 8
    assert all(row["same_target_worker_quality_Q"] is None and not row["stage2_regression_eligible"] for row in q01)
    assert sum(row["stage2_regression_eligible"] for row in rows) == 117

    unchanged_inputs = []
    with ZipFile(ROOT / "research/quality_pro_handoff_20261014/quality_pro_handoff_20261014_READY.zip") as archive:
        for path in sorted((source / "frozen_input").rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            name = path.relative_to(source / "frozen_input").as_posix()
            assert path.read_bytes() == archive.read(name), name
            unchanged_inputs.append(name)
    assert len(unchanged_inputs) == 119

    return dict(schema="quality_pro_independent_review_v1", counts=dict(counts),
                scored=718, held=92, independent_formula_max_error=max(errors),
                score_bounds_checked=True,
                unchanged_input_files=unchanged_inputs,
                height_drop_changes=height_changes,
                candidates_passing_three_checks=passing, candidate_count=len(summary),
                three_checks="P01 positive margin; no weak-grade inversions; no severe-light inversions. Not all evidence and not a human validity certificate.",
                ordinary_and_doorway_configs_equal=True, q01_diagnostic_only=8,
                conditional_doorway_regression=117,
                same_target_worker_quality_not_certified_by_this_audit=True,
                repository_adoption="parallel_research_candidate_no_default_replacement")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("unchanged_input_files", "candidates_passing_three_checks")}, ensure_ascii=False))
