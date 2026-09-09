"""连接已有人工评语和显示对象；不产生新视觉裁决或工人类型。"""
import argparse
import csv
import gzip
import json
from collections import Counter
from pathlib import Path


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def identity_key(row):
    return tuple(str(row[k]) for k in ("stage", "block_index", "project_id", "runtime_task_id", "worker_id", "raw_annotation_id"))


def resolve_display(display, canonical, versions):
    """全身份连接；旧版本只保留谱系归属，禁止冒充当前几何。"""
    result = dict(display)
    identity = display["annotation_identity"]
    result.update(canonical_annotation_id=None, raw_annotation_version_id=None,
                  geometry_can_use_current_canonical=False)
    if not identity:
        result["join_status"] = "nonhuman_display_object"
        return result
    key = tuple(identity.split("|"))
    matches = [r for r in versions if identity_key(r) == key]
    if len(matches) != 1:
        result["join_status"] = "missing_or_nonunique_version"
        return result
    version = matches[0]
    result["raw_annotation_version_id"] = version["raw_annotation_version_id"]
    result["canonical_annotation_id"] = version["canonical_annotation_id"] or None
    if identity in canonical:
        if canonical[identity]["canonical_annotation_id"] != version["canonical_annotation_id"]:
            raise ValueError("canonical/version disagreement: " + identity)
        result["join_status"] = "exact_canonical_response"
        result["geometry_can_use_current_canonical"] = True
    else:
        result["join_status"] = "historical_version_only" if version["canonical_annotation_id"] else "unlinked_raw_version"
    return result


def build(repo, out):
    source = repo / "analysis_results/human_review_reconciliation_20260907_v1"
    followup = repo / "analysis_results/uncertainty_followup_analysis_20260908_v1"
    substrate = repo / "analysis_results/uncertainty_cloud_inputs_20260906_v1"
    records = read_json(source / "reconciled_records.json")
    original = {r["case_id"]: r for r in read_json(source / "原始问卷备份.json")["records"]}
    assert all(r["human_record"] == original[r["case_id"]] for r in records), "human record drift"
    scope = {r["case_id"]: r for r in read_json(source / "scope_comment_readings.json")}
    supplements = {r["case_id"]: r for r in read_json(source / "human_supplements_20260908.json")}
    bindings = {r["statement_id"]: r for r in read_json(followup / "human_scope_identity_bindings.json")["bindings"]}
    annotations = rows(substrate / "annotations.csv.gz")
    canonical = {r["annotation_identity"]: r for r in annotations}
    assert len(canonical) == len(annotations), "nonunique canonical identity"
    versions = rows(substrate / "facts/annotation_version_lineage.csv.gz")
    displays = [resolve_display(r, canonical, versions) for r in rows(followup / "display_identity_links.csv")]
    display_index = {(r["case_id"], r["variant"]): r for r in displays}
    assert len(display_index) == len(displays), "nonunique display identity"
    assert len(records) == 50 and len({r["case_id"] for r in records}) == 50
    cases, statements, links, unresolved = [], [], [], []
    # Explicit singular/model targets only; collective statements remain collective.
    extra = {"V04-S1": ["Bi-Layout_enclosed", "Bi-Layout_extended"],
             "V17-S2": ["HoHoNet_single"], "V22-S1": ["Bi-Layout_extended"],
             "V26-S1": ["Bi-Layout_enclosed", "Bi-Layout_extended"],
             "V30-S1": ["Bi-Layout_enclosed", "Bi-Layout_extended"],
             "V32-S1": ["Bi-Layout_extended"], "V33-S2": ["Bi-Layout_enclosed", "Bi-Layout_extended"],
             "V38-S1": ["Bi-Layout_extended"], "V40-S2": ["Bi-Layout_enclosed", "Bi-Layout_extended"],
             "V44-S4": ["Bi-Layout_enclosed", "Bi-Layout_extended"],
             "V45-S1": ["Bi-Layout_enclosed", "Bi-Layout_extended"]}
    for record in records:
        case = record["case_id"]
        supplement = supplements.get(case)
        cases.append({"case_id": case, "image_id": record["image_id"],
                      "original_human_record": record["human_record"],
                      "later_human_supplement": supplement,
                      "preferred_semantic_source": "later_human_supplement" if supplement else "original_human_record",
                      "prior_ai_followup_not_new_adjudication": record["ai_followup"],
                      "scope_reading_ai_extraction": scope[case],
                      "final_user_decision": record["final_user_decision"],
                      "completion_option_is_certainty": False})
        for statement in scope[case]["scope_statements"]:
            sid = statement["statement_id"]
            binding = bindings.get(sid)
            targets = [r["variant"] for r in binding["matched_display_objects"]] if binding else extra.get(sid, [])
            item = dict(statement, image_id=record["image_id"], case_id=case,
                        source_kind="human_quote_with_existing_ai_extraction",
                        later_supplement_takes_precedence=bool(supplement),
                        existing_binding=binding, whole_cluster_semantics_verified=False,
                        worker_type_inference_allowed=False)
            statements.append(item)
            for target in targets:
                links.append(dict(display_index[(case, target)], statement_id=sid,
                                  semantic_label_provenance="human_quote_with_existing_ai_extraction",
                                  semantic_label_is_final_human_adjudication=False,
                                  scope_label=statement["scope_label"],
                                  scope_of_claim="displayed_object_only"))
            if not targets or (binding and "partially" in binding["identity_status"]):
                unresolved.append({"case_id": case, "statement_id": sid,
                                   "target": statement["target"], "quote": statement["quote"],
                                   "reason": binding["identity_status"] if binding else "scene_or_potential_scope_not_unique_response",
                                   "needs_user_now": False,
                                   "handling": "保留情景／集合陈述；仅在后续必须做响应级分析时补连接，不重复询问已明确评论。"})
    # User explicitly names the two displayed workers and GT in V04; this is
    # a bounded display set, not an extrapolation to the members of a cluster.
    s = supplements["V04"]
    statements.append({"statement_id": "V04-SUP1", "case_id": "V04", "image_id": s["image_id"],
                       "quote": s["original_text"], "source_kind": "direct_user_supplement",
                       "scope_label": "enclosed", "interpretation": "在天花下凸处截止；仅连接两份已显示真人和参考。",
                       "final_user_decision": None, "worker_type_inference_allowed": False})
    for target in ["reference_0", "human_individual_W11", "human_individual_W15"]:
        links.append(dict(display_index[("V04", target)], statement_id="V04-SUP1",
                          semantic_label_provenance="direct_user_supplement_with_ai_target_binding",
                          semantic_label_is_final_human_adjudication=False, scope_label="enclosed",
                          scope_of_claim="displayed_object_only"))
    confirmation = read_json(followup / "confirmed_20260908/user_confirmations.json")
    for item in confirmation:
        if item["canonical_annotation_id"]:
            matches = [r for r in versions if r["raw_annotation_id"] == str(item["annotation_id"])
                       and r["runtime_task_id"] == str(item["task_id"])
                       and r["source_path"] == item["source"]]
            assert len(matches) == 1, "confirmation version not unique"
            version = matches[0]
            item["version_identity_verification"] = resolve_display(
                {"annotation_identity": "|".join(identity_key(version))}, canonical, versions)
    qa = {"cases": len(cases), "original_nonempty_comments": sum(bool(r["original_human_record"]["answers"]["notes"].strip()) for r in cases),
          "later_supplements": len(supplements), "statements": len(statements), "statement_display_links": len(links),
          "display_join_status": dict(Counter(r["join_status"] for r in displays)),
          "human_semantic_links": sum(r["join_status"] == "exact_canonical_response" for r in links),
          "human_semantic_case_ids": sorted({r["case_id"] for r in links if r["join_status"] == "exact_canonical_response"}),
          "unresolved_statement_rows": len(unresolved), "new_human_decisions_required": 0,
          "new_visual_judgments": 0, "classification_of_workers": False,
          "all_original_human_records_equal_backup": True}
    out.mkdir(parents=True, exist_ok=True)
    for name, data in [("case_evidence", cases), ("scope_statements", statements),
                       ("response_semantic_links", links), ("display_identity_index", displays),
                       ("unresolved_scope_targets", unresolved)]:
        (out / (name + ".jsonl")).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in data), encoding="utf-8")
    (out / "prior_user_geometry_confirmations.json").write_text(json.dumps(confirmation, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "QA.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    return qa


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    destination = args.out or args.repo / "analysis_results/uncertainty_decision_ready_20260908_v1/semantics"
    print(json.dumps(build(args.repo, destination), ensure_ascii=False, indent=2))
