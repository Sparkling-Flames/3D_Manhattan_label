"""Offline audit of the two-image handoff; never changes source or eligibility."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PACKAGE = Path(r"C:\Users\ASUS\Downloads\quality_scope_model_research_20261015\quality_scope_model_research_20261015")
sys.path[:0] = [str(ROOT), str(PACKAGE / "src")]
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
from geometry import project, erp_triples, polygon, iou, direction, bottom_distance
from model import floor_diagnostic


def main():
    bundle = load_current_bundle()
    live = {o["object_id"]: o for o in bundle["data"]["objects"]}
    handoff = ROOT / "research/quality_scope_model_handoff_20261015"
    archived = json.loads((PACKAGE / "inputs/archival_geometry_28.json").read_text(encoding="utf-8-sig"))
    snapshot = json.loads((handoff / "CURRENT_TWO_IMAGE_OBJECTS.json").read_text(encoding="utf-8-sig"))["objects"]
    ledger = pd.read_csv(handoff / "TWO_IMAGE_PRIOR_LEDGER.csv").fillna("")
    ids = {r["object_id"]: r for r in ledger.to_dict("records")}
    delta = {r["image_code"]: r for r in json.loads((handoff / "TWO_IMAGE_SCOPE_DELTA.json").read_text(encoding="utf-8-sig"))["records"]}
    fields = ["object_id", "object_kind", "image_id", "image_code", "worker_id", "condition", "source", "points_1024x512", "pairing_basis", "preprocessing_status", "cleaning_disposition", "worker_quality_gate", "ring_confirmed", "order_status", "ordered_source_pair_indices", "geometry", "final_review"]
    objects = []
    for snap in snapshot:
        o = live[snap["object_id"]]
        row = {k: o[k] for k in fields if k in o}
        if o["object_id"] in ids:
            r = ids[o["object_id"]]
            row["record_id"] = r["record_id"]
            row["prior_ledger_qualification"] = {k: r[k] for k in ["source_cohort", "role", "original_holdout", "personnel_barriers", "context_barriers", "numeric_barriers", "score_status", "same_target_quality_hold"]}
        objects.append(row)
    (OUT / "CURRENT_TWO_IMAGE_MINIMAL_38.json").write_text(json.dumps({"source": "live load_current_bundle()", "full_object_snapshot_equal": all(o == live[o["object_id"]] for o in snapshot), "formal_eligibility_changed": False, "objects": objects}, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = []
    for r in ledger.to_dict("records"):
        if r["record_id"] in archived:
            continue
        o = live[r["object_id"]]
        d = delta[o["image_code"]]
        base = {k: r[k] for k in ["record_id", "object_id", "image_code", "worker_id", "condition", "personnel_barriers", "numeric_barriers", "score_status"]}
        base.update(formal_eligibility_changed=False, ring_confirmed=o["ring_confirmed"], geometry_status=o["geometry"]["status"], new_WQ_full=None, new_IoU3D100=None)
        if o["preprocessing_status"] != "ready":
            base.update(computation_status="unavailable_pairing_retained_NA")
            rows.append(base)
            continue
        a, _ = project(erp_triples(o["points_1024x512"]))
        g, _ = project(erp_triples(d["original_reference_points_1024x512"]))
        n = np.asarray(d["new_floor_polygon_xz_h"])
        assert polygon(a).is_valid and polygon(a).area > 0
        D = direction(a)
        for name, ref in [("old", g), ("new", n)]:
            I, Sb = iou(a, ref), bottom_distance(a, ref)
            base.update({name + "_IoU2D100": 100 * I, name + "_Sb_deg": Sb, name + "_floor_upper_bound": floor_diagnostic(I, Sb, D)})
        base.update(D_deg=D, computation_status="diagnostic_only_existing_hold_retained")
        rows.append(base)
    result = pd.DataFrame(rows)
    assert len(result) == 8
    assert (result.computation_status == "diagnostic_only_existing_hold_retained").sum() == 6
    assert result.new_WQ_full.isna().all() and result.new_IoU3D100.isna().all()
    result.to_csv(OUT / "MISSING8_FLOOR_SUPPLEMENT.csv", index=False, encoding="utf-8-sig")
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()
