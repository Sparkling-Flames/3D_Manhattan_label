#!/usr/bin/env python3
"""Export every qualified pool's unchanged room and difficulty metadata.

No fusion/result table is read and no room classes are merged or inferred.
The optional original image metadata can add field-level provenance if present.
"""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "restored/work_personnel_typing_A_20261019/recovered/repo_main_20261019"
EVIDENCE = SOURCE / "research/statistics/v2_evidence_audit_20261019/records.json.gz"
SNAPSHOT = ROOT / "restored/work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz"
OUT = ROOT / "analysis/independent"


def read(path):
    with (gzip.open(path, "rt", encoding="utf-8") if path.suffix == ".gz" else path.open(encoding="utf-8-sig")) as f:
        return json.load(f)


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-metadata", type=Path)
    args = parser.parse_args()
    raw = read(EVIDENCE)["records"]
    images = {}
    for r in raw:
        if r["image_id"] in images:
            assert dump(images[r["image_id"]]) == dump(r["image_evidence"])
        else:
            images[r["image_id"]] = r["image_evidence"]
    upstream = {r["image_id"]: r for r in read(args.image_metadata)["images"]} if args.image_metadata else {}
    pools = read(SNAPSHOT)["images"]
    rows = []
    for pool in pools:
        meta = pool["meta"]; iid = meta["image_id"]
        evidence = images[iid]; room = evidence.get("room_spatial_classification") or {}; d = evidence["difficulty_record"]
        original = upstream.get(iid)
        if original:
            assert original.get("room_spatial_classification") == evidence.get("room_spatial_classification")
            assert original.get("main_visual_space") == evidence.get("main_visual_space")
        sources = original.get("room_classification_sources") if original else None
        latest = d.get("latest_user_review") or {}
        row = {k: meta[k] for k in ("pool_id", "image", "image_id", "building", "room_id", "condition", "layer", "pool_n", "old_member_n", "new_member_n", "reference_id", "reference_version", "difficulty", "difficulty_aligned", "scene")}
        row.update(
            room_coarse_type=room.get("coarse_type"), room_coarse_type_recorded=room.get("coarse_type") is not None,
            room_functions_json=dump(room.get("functions")), room_focus_json=dump(room.get("focus")), room_boundary_json=dump(room.get("boundary")),
            main_visual_space=evidence.get("main_visual_space"), expected_annotation_extent=evidence.get("expected_annotation_extent"),
            room_classification_sources_json=dump(sources),
            room_source_status="upstream_field_sources_present" if sources is not None else "field_level_source_not_embedded_in_frozen_evidence",
            metadata_source="research/statistics/v2_evidence_audit_20261019/records.json.gz#image_id=" + iid + "/image_evidence",
            room_evidence_sha256=hashlib.sha256(dump(room).encode()).hexdigest(),
            difficulty_target_version=d["target_version"], difficulty_classification_basis=d.get("classification_basis"),
            difficulty_basis_before_user_adoption=d.get("basis_before_user_adoption"),
            difficulty_class_before_user_adoption=d.get("class_before_user_adoption"),
            difficulty_user_grade_adopted=d.get("user_grade_adopted"), difficulty_review_method=d.get("review_method"),
            difficulty_reviewed=d.get("reviewed"), difficulty_evidence=d.get("evidence"),
            difficulty_analysis_eligible=d.get("difficulty_analysis_eligible"),
            difficulty_scope_semantics=d.get("scope_semantics"),
            latest_user_review_version=latest.get("review_version"), latest_user_review_updated_at=latest.get("updated_at"),
            source_oos_subtype=d.get("oos_subtype"), source_doorway_status=d.get("doorway_status"))
        assert row["difficulty"] == d["current_class"] and row["scene"] == d["scene"]
        assert row["difficulty_aligned"] == (row["reference_id"] == row["difficulty_target_version"])
        rows.append(row)
    target = OUT / "POOL_IMAGE_CONDITIONS.csv"
    with target.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    by_room = defaultdict(list)
    for row in rows:
        by_room[row["room_coarse_type"]].append(row)
    summary = {
        "schema": "unaltered_qualified_pool_image_conditions_v1", "rows": len(rows),
        "images": len({r["image_id"] for r in rows}), "pools": len({r["pool_id"] for r in rows}),
        "metadata_only_no_fusion_results_read": True, "all_duplicate_image_evidence_consistent": True,
        "csv_sha256": sha(target), "csv_bytes": target.stat().st_size,
        "sources": {str(EVIDENCE.relative_to(ROOT)): sha(EVIDENCE), str(SNAPSHOT.relative_to(ROOT)): sha(SNAPSHOT)},
        "upstream_image_metadata": {"path": str(args.image_metadata), "sha256": sha(args.image_metadata)} if args.image_metadata else None,
        "room_type_support": [{"room_coarse_type": kind, "pools": len(part), "images": len({r["image_id"] for r in part}), "buildings": len({r["building"] for r in part}), "qualified_record_slots": sum(r["pool_n"] for r in part)} for kind, part in sorted(by_room.items(), key=lambda item: str(item[0]))],
        "missing_policy": "Raw room_coarse_type and text values retained unchanged. Missing values remain null in JSON/empty in CSV; the recorded boolean distinguishes missing from literal unknown labels such as 无法判断. No class merging.",
        "source_scope": "Frozen evidence directly contains room_spatial_classification/main_visual_space/expected_annotation_extent. Its source builder copies these from v2 analysis_input data.images. Field-level room_classification_sources is recorded only if that optional upstream metadata is supplied; otherwise provenance is not invented.",
        "interpretation": "scene remains the independent OOS/doorway status. Room type is inherited image metadata, not a newly validated automatic prediction. Difficulty is target-conditioned curated evidence, often nonblind geometry/photo review. Additional room strata of previously frozen effects are post-freeze exploratory interpretation.",
    }
    (OUT / "POOL_IMAGE_CONDITIONS_PROVENANCE.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"path": str(target), "rows": len(rows), "bytes": target.stat().st_size, "room_type_support": summary["room_type_support"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
