"""Read frozen v2 evidence and selected saved teams; no geometry or eligibility writes."""
from collections import Counter
import csv
from dataclasses import replace
import gzip
import json
import math
from pathlib import Path

from research.quality.quality_ab_feedback_handoff_20261015.prior_AB.src import working_models as models

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE = "research/workers/personnel_effective_exchange_conditions_20261022/mechanisms"
SOURCES = [
    BASE + "/positive_cases/cases/E20261022_wc2_56_n20_m6.json",
    BASE + "/positive_cases/cases/E20261022_zs16_n20_m6.json",
    BASE + "/positive_cases/cases/E20261022_zs16_n21_m6.json",
    BASE + "/b6_47_failure/cases/B6_47_invalid_floor_n20_m4.json",
    "research/workers/personnel_interchangeability_20261020/interchangeability_20261020/cases/S09_same_composition_different_shape.json",
]
FIELDS = [
    "case_id", "source_path", "arm", "image", "condition", "team_key",
    "reference_id", "reference_version", "score_status", "complete_evaluable", "nodes",
    "B8L2", "D10", "IoU3D100", "iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter",
    "omission", "extension", "floor_block_loss", "direction_block_loss", "height_loss",
    "pooled_geometry_loss", "B8L2_direction_zero",
]


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def calc_counts(rows):
    return [
        dict(calculation_class=k[0], quality_usable=k[1], records=n)
        for k, n in sorted(Counter((r["calculation_class"], r["quality_usable"]) for r in rows).items())
    ]


def main():
    with gzip.open(ROOT / "research/statistics/v2_evidence_audit_20261019/records.json.gz",
                   "rt", encoding="utf-8") as f:
        records = json.load(f)["records"]
    assert len(records) == len({r["object_id"] for r in records}) == 10439
    assert sum(r["quality_usable"] for r in records) == 7302
    assert all(r["B8L2"] is None for r in records if not r["quality_usable"])
    p_rb = [r for r in records if r["image_code"] == "pRbA3pwrgk9-12"]
    assert len(p_rb) == 35 and all(not r["quality_usable"] for r in p_rb)
    assert all(not r["exclusion_attribution"]["legacy_explicit_person_error"] for r in p_rb)
    assert all(r["calculation_class"] == "full" and r["diagnostic_B8L2"] is not None for r in p_rb)
    non_oos_inventory = [r for r in records if not r["is_oos"]]
    receipt = dict(
        schema="quality_reference_closeout_20261022_v1",
        base_commit="8bfd3e476bd5ae6edc1424e2c8ea07dd2f69a235",
        source="research/statistics/v2_evidence_audit_20261019/records.json.gz",
        all_inventory_records=len(records),
        all_calculation_by_eligibility=calc_counts(records),
        non_oos_records=len(non_oos_inventory),
        non_oos_calculation_by_eligibility=calc_counts(non_oos_inventory),
        non_oos_cleaning_disposition=dict(Counter(r["cleaning_disposition"] for r in non_oos_inventory)),
        floor_only_with_full_reference=sum(r["calculation_class"] == "floor_only" and r["reference_full_available"] for r in records),
        pRb_12=dict(records=len(p_rb), formal_quality_records=0, complete_diagnostic_records=35,
                    reason_source="research/workers/personnel_marking_patterns_20261020/README.md M01"),
        interpretation="calculation, eligibility, scene/reference holds and individual attribution are separate; no eligibility promoted",
    )
    rows = []
    d10 = replace(models.B, version="B8L2-D10-20261016", direction_scale_deg=10.)
    for source in SOURCES:
        case = read(ROOT / source)
        selected = case["teams"][:2] if case["case_id"] == "S09_same_composition_different_shape" else case["teams"]
        assert len({(r["reference_id"], r["reference_version"]) for r in selected}) == 1
        for s in selected:
            row = {k: s.get(k) for k in FIELDS}
            row.update(case_id=case["case_id"], source_path=source, arm=s["label"])
            if s["complete_evaluable"]:
                args = [s[k] for k in ("iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter")]
                assert all(math.isfinite(v) for v in args)
                assert abs(float(models.score(*args, models.B)) - s["B8L2"]) < 1e-8
                assert abs(float(models.score(*args, d10)) - s["D10"]) < 1e-8
                if s.get("omission") is not None and s.get("extension") is not None:
                    assert abs((1 - s["omission"]) / (1 + s["extension"]) - s["iou_2d"]) < 1e-8
                _, bottom, direction, glob, local = models.terms(*args, models.B)
                floor = 1 / args[0] - 1 + float(bottom)
                row.update(floor_block_loss=floor, direction_block_loss=float(direction),
                           height_loss=float(glob + local), pooled_geometry_loss=math.hypot(floor, direction),
                           B8L2_direction_zero=float(models.score(args[0], args[1], 0, args[3], args[4], models.B)))
            else:
                assert s["B8L2"] is None and s["D10"] is None
            rows.append(row)
    assert len(rows) == 14 and sum(r["complete_evaluable"] for r in rows) == 13
    assert len({r["team_key"] for r in rows}) == 14
    with (OUT / "LATEST_CASE_COMPONENTS.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (OUT / "REFERENCE_COUNTS.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("validated 10439 eligibility states and 13 saved B8L2/D10 pairs; preserved 1 invalid-floor endpoint")


if __name__ == "__main__":
    main()
