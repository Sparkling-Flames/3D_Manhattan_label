#!/usr/bin/env python3
"""Read-only provenance and denominator audit of image difficulty and scene."""
from collections import Counter, defaultdict
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
    with (gzip.open(path, "rt", encoding="utf-8") if path.suffix == ".gz" else path.open(encoding="utf-8")) as f:
        return json.load(f)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_entry(relative, excerpts):
    path = SOURCE / relative
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    result = {"repository_path": relative, "sha256": sha(path), "excerpts": []}
    for excerpt in excerpts:
        matches = [(i + 1, line.strip()) for i, line in enumerate(lines) if excerpt in line]
        assert matches, (relative, excerpt)
        result["excerpts"].extend({"line": i, "text": line} for i, line in matches)
    return result


def counts(values, field):
    return dict(Counter("not_recorded" if v.get(field) is None else str(v.get(field)) for v in values))


def main():
    rows = read(EVIDENCE)["records"]
    images = {}
    for row in rows:
        iid, evidence = row["image_id"], row["image_evidence"]
        assert row["current_class"] == evidence["difficulty_record"]["current_class"]
        assert row["scene"] == evidence["difficulty_record"]["scene"]
        if iid in images:
            assert canonical(images[iid]) == canonical(evidence)
        else:
            images[iid] = evidence
    difficulty = {iid: e["difficulty_record"] for iid, e in images.items()}
    pools = read(SNAPSHOT)["images"]
    strata, not_aligned = defaultdict(list), []
    for pool in pools:
        meta = pool["meta"]
        d = difficulty[meta["image_id"]]
        assert d["image_id"] == meta["image_id"] and d["image"] == meta["image"]
        assert d["current_class"] == meta["difficulty"] and d["scene"] == meta["scene"]
        aligned = d["target_version"] == meta["reference_id"]
        assert aligned == meta["difficulty_aligned"]
        strata[meta["layer"]].append(pool)
        if not aligned:
            not_aligned.append({"pool_id": pool["pool_id"], "image": meta["image"], "layer": meta["layer"],
                                "difficulty": meta["difficulty"], "difficulty_target": d["target_version"],
                                "pool_reference": meta["reference_id"]})
    by_layer = []
    for layer, selected in sorted(strata.items()):
        image_ids = {p["meta"]["image_id"] for p in selected}
        ds = [difficulty[i] for i in image_ids]
        by_layer.append({
            "layer": layer, "pools": len(selected), "images": len(image_ids),
            "records": sum(len(p["records"]) for p in selected),
            "buildings": len({p["meta"]["building"] for p in selected}),
            "pools_difficulty_reference_aligned": sum(p["meta"]["difficulty_aligned"] for p in selected),
            "difficulty_by_image": counts(ds, "current_class"),
            "classification_basis_by_image": counts(ds, "classification_basis"),
            "user_grade_adopted_images": sum(bool(d.get("user_grade_adopted")) for d in ds),
            "scene_by_image": counts(ds, "scene"),
            "coarse_room_type_by_image": dict(Counter((images[i].get("room_spatial_classification") or {}).get("coarse_type") or "not_recorded" for i in image_ids)),
        })
    example_keys = ("image", "image_id", "current_class", "conditional_difficulty", "target_version", "scene", "oos_subtype", "doorway_status",
                    "classification_basis", "basis_before_user_adoption", "class_before_user_adoption", "user_grade_adopted", "review_method",
                    "reviewed", "N_floor", "N_turn", "H", "inference_burden", "evidence", "difficulty_analysis_eligible", "scope_semantics")
    examples = []
    seen_basis = set()
    for iid, d in sorted(difficulty.items(), key=lambda item: item[1]["image"]):
        basis = d.get("classification_basis", "not_recorded")
        if basis in seen_basis:
            continue
        seen_basis.add(basis)
        examples.append({k: d.get(k) for k in example_keys})
    source_chain = [
        source_entry("tools/thesis_main/analysis/difficulty_scope_preferred_20261011.py", [
            '"""重建固定候选范围', "grade = classify(f['N_turn'], d['inference_burden'], special)",
            "classification_basis='geometry_and_codex_photo_review_not_blind'", "exploratory_target_conditioned; photo coding is not automatic"]),
        source_entry("tools/thesis_main/analysis/difficulty_user_adoption_20261016.py", [
            "if v['image_id']!=r['image_id'] or v['target_version']!=r['target_version']:",
            "classification_basis='user_review_adopted_20261016'", "原规则意见仅供对照，不代表新等级由机器自动产生"]),
        source_entry("tools/thesis_main/analysis/difficulty_strata_20261009.py", [
            "def merge_scene_reviews", "是门洞", "def classify_scene", "return 'clear' if", "unflagged_not_certified_normal"]),
        source_entry("tools/thesis_main/analysis/difficulty_review_update_20261015.py", [
            "r['scene']=r['scene']+';oos_suspected'", "r['scene']=r['scene']+';doorway_suspected'"]),
        source_entry("tools/thesis_main/analysis/b8l2_usage_coverage_20261016.py", [
            "def scene_flags", "来源condition=oos不代替场景事实", "worker_unmarkable_choice='unknown_not_independently_recorded'"]),
        source_entry("tools/thesis_main/analysis/quality_workers_v2_20261019.py", [
            "current_class=d['current_class'],scene=d['scene']"]),
        source_entry("tools/thesis_main/analysis/v2_evidence_audit_20261019.py", [
            "current_class=q['current_class'], scene=q['scene']", "image_evidence=dict(room_spatial_classification", "difficulty_record=d)"]),
    ]
    result = {
        "schema": "image_condition_provenance_audit_v1",
        "scope": "Read frozen metadata and source code only; no label, geometry, reference, eligibility or scientific result changed",
        "input_sha256": {str(EVIDENCE.relative_to(ROOT)): sha(EVIDENCE), str(SNAPSHOT.relative_to(ROOT)): sha(SNAPSHOT)},
        "inventory_records": len(rows), "inventory_images": len(images), "quality_pools": len(pools),
        "quality_images": len({p['meta']['image_id'] for p in pools}),
        "all_image_records_consistent": True, "all_pool_condition_values_match_image_evidence": True,
        "all_alignment_flags_recounted": True, "by_layer": by_layer,
        "inventory_difficulty_classification_basis_by_image": counts(difficulty.values(), "classification_basis"),
        "inventory_user_grade_adopted_images": sum(bool(d.get("user_grade_adopted")) for d in difficulty.values()),
        "inventory_scene_by_image": counts(difficulty.values(), "scene"),
        "inventory_review_method_by_image": counts(difficulty.values(), "review_method"),
        "nonaligned_qualified_pools": not_aligned,
        "classification_basis_examples": examples, "source_chain": source_chain,
        "interpretation": {
            "difficulty": "Existing, target-conditioned working labels from reference geometry, qualitative panorama review and adopted user grades; not an automatic pre-collection image feature. Later user grades are authoritative labels, not evidence the earlier numeric rule predicts them.",
            "prospective_rule": "A hard-condition personnel rule can be used only when a comparable difficulty assessment and target-scope definition are already available; these retrospective data do not demonstrate automatic difficulty inference before annotation.",
            "alignment": "Target-version alignment is necessary to interpret a difficulty-conditioned comparison, but alignment alone does not make the difficulty label prospectively available or validate the reference.",
            "scene": "pool.meta.scene is the operational OOS/doorway review status. clear requires explicit absence; unflagged means no special flag. Neither is a room-function class.",
            "room_type": "Coarse room function is separately stored in image_evidence.room_spatial_classification.coarse_type, with qualitative main_visual_space and expected_annotation_extent. Do not substitute scene=unflagged for a room type.",
            "unknown": "Suspected/pending and unrecorded scene evidence remain distinct from confirmed absence; source condition and worker response are separate axes.",
        },
    }
    (OUT / "IMAGE_CONDITION_PROVENANCE_AUDIT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("inventory_images", "quality_pools", "quality_images", "inventory_difficulty_classification_basis_by_image", "inventory_user_grade_adopted_images", "by_layer", "nonaligned_qualified_pools")}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
