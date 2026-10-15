#!/usr/bin/env python3
"""Offline integrity and identity/provenance checks for this frozen publication.

Python 3 standard library only. Does not run historical build scripts, access the
network, recompute geometry/quality, or reopen original desktop/source files.
"""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import sys


def read_json(path):
    with path.open(encoding="utf-8-sig") as stream:
        return json.load(stream)


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def saved_raw_hash(record):
    # Match the frozen integration writer, including its default JSON separators.
    return sha256_bytes(json.dumps(record, ensure_ascii=False, sort_keys=True).encode())


def safe_child(root, name):
    relative = PurePosixPath(name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Unsafe manifest path: " + name)
    path = root.joinpath(*relative.parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Manifest path escapes bundle: " + name)
    return path


def csv_equal(serialized, value):
    if value is None:
        return serialized == ""
    if isinstance(value, (dict, list)):
        try:
            return json.loads(serialized) == value
        except (ValueError, TypeError):
            return False
    return serialized == str(value)


def verify(root):
    checks = Counter()

    def check(condition, label, category="invariants"):
        if not condition:
            raise ValueError(label)
        checks[category] += 1

    def compare_csv(name, expected, directory):
        rows = read_csv(directory / name)
        check(len(rows) == len(expected), "CSV row count: " + name, "csv_json")
        for index, (row, source) in enumerate(zip(rows, expected)):
            for key, value in row.items():
                check(csv_equal(value, source.get(key, "")),
                      "CSV value: %s row %d field %s" % (name, index + 2, key), "csv_json")
        return rows

    cloud = root / "cloud_inventory"
    local = root / "local_increment"
    manifest = read_json(root / "FILE_MANIFEST.json")
    check(manifest["schema"] == "saved-research-bundle-manifest-v1", "bundle manifest schema")
    for name, metadata in manifest["files"].items():
        content = safe_child(root, name).read_bytes()
        check(len(content) == metadata["bytes"], "bundle file length: " + name, "file_integrity")
        check(sha256_bytes(content) == metadata["sha256"], "bundle SHA256: " + name, "file_integrity")
    for name, metadata in read_json(cloud / "FILE_MANIFEST.json").items():
        content = safe_child(cloud, name).read_bytes()
        check(len(content) == metadata["bytes"] and sha256_bytes(content) == metadata["sha256"],
              "frozen cloud file integrity: " + name, "file_integrity")

    with gzip.open(cloud / "inventory.json.gz", "rt", encoding="utf-8") as stream:
        data = json.load(stream)
    with gzip.open(cloud / "scope_by_image.json.gz", "rt", encoding="utf-8") as stream:
        per_image = json.load(stream)
    images = data["images"]
    records = data["geometry_records"]
    comments = data["comments"]
    occurrences = data["occurrences"]
    groups = data["condition_gate_groups"]
    by_image = {item["image_id"]: item for item in images}
    by_record = {item["record_id"]: item for item in records}
    by_comment = {item["comment_id"]: item for item in comments}
    check(len(images) == len(by_image) == 259, "259 unique images")
    check(len({item["image_code"] for item in images}) == 259, "259 unique image codes")
    check(len(records) == len(by_record) == len({item["object_id"] for item in records}) == 3152,
          "3152 unique record and object IDs")
    check(len(comments) == len(by_comment) == 1648, "1648 unique comment IDs")
    check(len(occurrences) == 6340, "6340 source occurrences")
    check(sum(item["total_records"] for item in images) == 3152, "image denominator")
    check(sum(item["n_records"] for item in groups) == 3152, "condition/gate denominator")
    check(sum(item["in_current_manual_pool"] for item in records) == 1866, "1866 current manual")
    check(sum(item["gate"] == "excluded" for item in records) == 218, "218 excluded preserved")
    check(sum(item["broad_review_queue"] for item in images) == 203, "203 retrieval candidates")
    check(sum(not item["broad_review_queue"] for item in images) == 56, "56 no-hit images")
    check(sum(item["user_confirmed_floor_region"] for item in images) == 5, "five floor confirmations")
    check(sum(item["historical_reference_version_pending"] for item in images) == 28,
          "28 selected/original reference differences")
    check({item["image_code"] for item in images if item["current_user_quality_reference_hold"]}
          == {"x8F5xyUWy9e-01", "wc2JMjhGNzB-14"}, "current user holds")
    check({item["image_code"] for item in images if item["formal_quality_hold_observed"]}
          == {"jtcxE69GiFV-18", "q9vSo1VnCiC-29", "zsNo4HB9uLZ-13"},
          "three observed formal holds")
    check(sum(item["historical_snapshot_hold"] for item in images) == 4, "four historical holds")
    check(sum(item["reference_paused"] for item in images) == 9, "nine known hold contexts")
    check({item["image_code"] for item in images if item["memory_identity_confirmed"]}
          == {"uNb9QFRL6hY-88"}, "one remembered-image identity")
    q9 = next(item for item in images if item["image_code"] == "q9vSo1VnCiC-29")
    check(q9["user_confirmed_floor_region"] and q9["formal_quality_hold_observed"],
          "floor confirmation does not release quality hold")

    records_per_image = defaultdict(list)
    for record in records:
        image = by_image.get(record["image_id"])
        check(image is not None and record["image"] == image["image_code"],
              "geometry image join: " + record["record_id"], "geometry_joins")
        records_per_image[record["image_id"]].append(record)
        for prefix in ("selected_gt_metrics_", "original_gt_metrics_"):
            values = [record[prefix + field] for field in ("symmetric_difference", "missing", "excess")]
            check(values == ["", "", ""] or all(type(value) in (int, float) and math.isfinite(value)
                                                       for value in values),
                  "finite-or-empty metric: " + record["record_id"] + " " + prefix, "metrics")
            if values[0] != "":
                check(abs(values[0] - values[1] - values[2]) < 1e-8,
                      "metric sum: " + record["record_id"] + " " + prefix, "metrics")
    for item in images:
        check(len(records_per_image[item["image_id"]]) == item["total_records"],
              "per-image denominator: " + item["image_code"], "geometry_joins")
    group_ids = []
    for group in groups:
        ids = group["record_ids"].split(";")
        check(len(ids) == group["n_records"], "group denominator", "geometry_joins")
        for record_id in ids:
            record = by_record.get(record_id)
            check(record is not None and all(record[field] == group[field]
                  for field in ("image_id", "condition", "gate")),
                  "condition/gate record join: " + record_id, "geometry_joins")
        group_ids.extend(ids)
    check(Counter(group_ids) == Counter(by_record.keys()), "condition/gate partition")

    sources = read_json(cloud / "source_manifest.json")
    source_paths = {item["path"] for item in sources}
    check(len(sources) == len(source_paths) == 54, "54 frozen source manifest entries")
    check(sum(item["state"] == "parsed_json" for item in sources) == 35, "35 parsed JSON sources")
    comment_counts = Counter()
    occurrence_signatures = defaultdict(Counter)
    for occurrence in occurrences:
        comment = by_comment.get(occurrence["comment_id"])
        check(comment is not None and all(occurrence[field] == comment[field]
              for field in ("image_id", "object_id", "record_id", "comment")),
              "occurrence/comment identity-text join", "comment_joins")
        check(occurrence["source_path"] in source_paths, "occurrence/source manifest join", "comment_joins")
        occurrence_signatures[occurrence["comment_id"]][(
            occurrence["source_path"], occurrence["source_pointer"], occurrence["source_field"],
            occurrence["source_record_key"], occurrence["source_role"])] += 1
    for comment in comments:
        check(comment["identity_status"] != "unresolved", "resolved comment identity", "comment_joins")
        comment_counts[comment["image_id"]] += 1
        expected_sources = Counter((item["path"], item["pointer"], item["field"], item["record_key"], item["role"])
                                   for item in comment["source_occurrences"])
        check(expected_sources == occurrence_signatures[comment["comment_id"]],
              "comment/occurrence provenance multiset: " + comment["comment_id"], "comment_joins")
        check(sum(expected_sources.values()) == comment["source_occurrence_count"],
              "comment occurrence count", "comment_joins")
        if comment["object_kind"] == "annotation":
            record = by_record.get(comment["record_id"])
            check(record is not None and record["object_id"] == comment["object_id"]
                  and record["image_id"] == comment["image_id"], "annotation comment binding", "comment_joins")
    for item in images:
        check(item["all_unique_comments"] == comment_counts[item["image_id"]],
              "image/comment denominator", "comment_joins")
        for comment_id in filter(None, item["keyword_comment_ids"].split(";")):
            check(by_comment[comment_id]["image_id"] == item["image_id"], "keyword/image join", "comment_joins")
    historical = [item for item in comments if item["image_id"] not in by_image]
    check(len(historical) == 41 and len({item["image_id"] for item in historical}) == 21,
          "41 historical comments / 21 outside images")
    indexed = [item for item in comments if "historical_deduplicated_index" in item["source_roles"]]
    check(len(indexed) == 1157, "1157 indexed comments")
    check(sum(item["source_roles"] == ["historical_deduplicated_index"] for item in indexed) == 4,
          "four index-only comments")
    check(len(per_image) == 259, "259 per-image evidence records")
    for grouped in per_image:
        image = by_image[grouped["image_id"]]
        check(all(grouped.get(key) == value for key, value in image.items()),
              "scope-by-image identity/fields", "comment_joins")
        check({item["comment_id"]: item for item in grouped["comments"]} == {item["comment_id"]: item for item in comments if item["image_id"] == grouped["image_id"]},
              "scope-by-image comments", "comment_joins")
        check({(item["condition"], item["gate"]): item for item in grouped["geometry_groups"]} == {(item["condition"], item["gate"]): item for item in groups if item["image_id"] == grouped["image_id"]},
              "scope-by-image groups", "geometry_joins")

    for name, rows in (("all_259_images.csv", images), ("all_3152_geometry_records.csv", records),
                       ("unique_comments.csv", comments), ("all_comment_occurrences.csv", occurrences),
                       ("condition_gate_groups.csv", groups), ("historical_outside_259_comments.csv", historical),
                       ("source_manifest.csv", sources)):
        compare_csv(name, rows, cloud)
    for name, field, negate in (("broad_review_queue.csv", "broad_review_queue", False),
             ("no_hit_images.csv", "broad_review_queue", True),
             ("selected_vs_original_reference_pending.csv", "historical_reference_version_pending", False),
             ("paused_reference_images.csv", "reference_paused", False),
             ("historical_snapshot_hold_images.csv", "historical_snapshot_hold", False),
             ("current_user_quality_hold_images.csv", "current_user_quality_reference_hold", False),
             ("formal_quality_hold_observed_images.csv", "formal_quality_hold_observed", False)):
        actual = read_csv(cloud / name)
        expected = {item["image_id"] for item in images if bool(item[field]) != negate}
        check(len(actual) == len(expected) and {item["image_id"] for item in actual} == expected,
              "derived image CSV set: " + name, "csv_json")
    check(len(read_csv(cloud / "keyword_comment_candidates.csv")) == 747, "747 keyword comment candidates")
    check(not read_csv(cloud / "unresolved_comment_identities.csv"), "no unresolved comment CSV rows")

    recent = read_json(local / "verified_recent36.json")
    extra = read_json(local / "additional_current_user_comments.json")
    outside = read_json(local / "additional_outside259_user_comments.json")
    integrated = read_json(local / "integration_verified69.json")
    check(len(recent) == 36 and len(extra) == 33 and len(outside) == 19, "36 + 33 current; 19 outside")
    check(len(integrated) == len({item["local_comment_id"] for item in integrated}) == 69,
          "69 unique local provenance IDs")
    check(len({item["image_id"] for item in integrated}) == 36, "36 locally supplemented images")
    check(len({(item["image_id"], item["comment"]) for item in integrated}) == 66,
          "66 distinct local image/text pairs; distinct annotation bindings retained")
    cloud_text = {(item["image_id"], item["comment"].strip()) for item in comments}
    raw_by_id = {item.get("verification_id", "LOCAL_EXTRA_%02d" % (index - 35)): item
                 for index, item in enumerate(recent + extra)}
    for item in recent + extra + outside:
        check(bool(item["sources"]), "local raw sources present", "local_raw_sources")
        for source in item["sources"]:
            field = source["json_pointer"].rsplit("/", 1)[-1].replace("~1", "/").replace("~0", "~")
            check(source["raw_record"].get(field) == item["text"], "embedded raw text exact", "local_raw_sources")
    for item in integrated:
        image = by_image.get(item["image_id"])
        check(image is not None and image["image_code"] == item["image_code"], "local/image exact join", "local_joins")
        check((item["image_id"], item["comment"].strip()) not in cloud_text,
              "local addition absent from frozen cloud image/text", "local_joins")
        check(item["raw_text_verified"] and not item["scope_difference_confirmed"]
              and item["no_gt_score_or_eligibility_change"], "local evidence safety flags", "local_joins")
        raw = raw_by_id[item["local_comment_id"]]
        check(item["comment"] == raw["text"] and all(item[key] == raw.get(key)
              for key in ("image_id", "image_code", "record_id", "object_id")),
              "integrated/raw exact identity and text", "local_joins")
        check(len(item["sources"]) == len(raw["sources"]), "local source count", "local_raw_sources")
        for saved, source in zip(item["sources"], raw["sources"]):
            original = source["raw_record"]
            check(saved == {"source_file": source["source_file"], "json_pointer": source["json_pointer"],
                  "reported_updated_at": source.get("updated_at"),
                  "raw_updated_at": original.get("updatedAt", original.get("updated_at")),
                  "raw_created_at": original.get("created_at"), "raw_record_sha256": saved_raw_hash(original)},
                  "local raw hash, pointer and time tiers", "local_raw_sources")
        if item["record_id"]:
            record = by_record.get(item["record_id"])
            check(record is not None and record["image_id"] == item["image_id"]
                  and record["object_id"] == item["object_id"], "local exact annotation join", "local_joins")
        for pair in item["pair_bindings"]:
            record = by_record.get(pair["record_id"])
            check(record is not None and record["image_id"] == item["image_id"]
                  and record["object_id"] == pair["object_id"], "local pair binding", "local_joins")
    for item in outside:
        check(item["image_id"] not in by_image and (item["image_id"], item["text"].strip()) not in cloud_text,
              "outside local item remains separate", "local_joins")
    check(Counter(item["binding_level"] for item in integrated) == {
        "exact_annotation": 22, "image_or_wall_group_only": 14, "exact_pair": 7, "image_or_cross_image_context": 26},
        "local binding type counts")
    check(sum(item["content_role"] == "original_user_cross_image_relationship_context" for item in extra) == 12,
          "12 cross-image contexts")
    check({item["verification_id"] for item in recent if not item["time_verified"]} == {"LOCAL36_30", "LOCAL36_32"},
          "two created-versus-parent-updated time distinctions")
    compare_csv("integration_verified69.csv", integrated, local)
    pending = read_json(local / "point109_provenance_pending4.json")
    check(len(pending) == 4 and all(item["original_raw_record_available"] is False for item in pending),
          "four point mirrors remain frozen provenance-pending")
    group_history = read_json(local / "group_history_provenance_pending.json")
    check(len(group_history) == len({item["text"] for item in group_history}) == 9
          and sum(len(item["associated_images"]) for item in group_history) == 35,
          "nine group texts / 35 historical bindings")
    audit = read_csv(local / "all11705_coverage_audit.csv")
    coverage = Counter(item["status"] for item in audit)
    errors = read_csv(local / "search_errors123_audit.csv")
    summary_local = read_json(local / "verification_summary.json")
    check(len(audit) == len({item["candidate_id"] for item in audit}) == 11705, "11705 candidate audit rows")
    check(coverage == summary_local["complete11705"], "11705 status partition")
    check(len(errors) == 123 and Counter(item["category"] for item in errors) == summary_local["search_errors123"],
          "frozen 123 read errors / 119 + 4 categories")
    summary = read_json(cloud / "summary.json")
    check(summary["source_commit"] == data["source_commit"], "frozen source commit")
    check(all(summary[key] == expected for key, expected in {
        "images": 259, "geometry_records": 3152, "all_unique_comments": 1648, "all_source_occurrences": 6340,
        "broad_queue_images": 203, "no_hit_images": 56, "outside_259_comments": 41, "outside_259_images": 21}.items()),
        "frozen cloud summary counts")
    qa = read_json(root / "workbench_source/QA.json")
    check(qa["corpus"]["local_increment_records"] == 69 and qa["corpus"]["cloud_unique_comments"] == 1648,
          "saved workbench count claims")

    return {
        "status": "passed", "scope": "saved-file integrity and exact joins; not quality recomputation",
        "source_commit": data["source_commit"], "checks_count": sum(checks.values()),
        "checks_by_category": dict(sorted(checks.items())),
        "bundle_files_hashed": len(manifest["files"]),
        "counts": {"images": 259, "geometry_records": 3152, "cloud_comments": 1648,
                   "cloud_source_occurrences": 6340, "local_provenance_records": 69,
                   "local_distinct_image_text_pairs": 66, "local_images": 36,
                   "local_exact_annotation_records": 22, "local_exact_pairs": 7,
                   "local_cross_image_contexts": 12, "local_outside_comments": 19,
                   "candidate_audit_rows": 11705, "frozen_search_error_rows": 123},
        "limitations": [
            "Original source files and desktop files are not reopened; cloud pointer rereads are historical checks in cloud_inventory/verification.json.",
            "Only embedded raw records in saved local results are checked against text, identifiers, pointers, hashes and timestamp tiers.",
            "Saved metrics are checked for internal consistency, not recomputed or promoted to scope truth.",
            "Frozen pending-source classifications predate the newly received audit archive; reconciliation and the awaited image batch are separate work.",
            "workbench_source is a code-only snapshot; its saved 3386 state/data checks are not rerun here, and browser QA remains unverified.",
            "The manifest excludes itself and this generated report to avoid self-referential hashes; later appended files need a refreshed manifest."
        ]
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent,
                        help="full_review directory, or its staging parent")
    parser.add_argument("--output", type=Path, help="optional JSON report path; otherwise stdout only")
    args = parser.parse_args()
    root = args.root.resolve()
    if not (root / "cloud_inventory").is_dir() and (root / "full_review/cloud_inventory").is_dir():
        root = root / "full_review"
    try:
        report = verify(root)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
