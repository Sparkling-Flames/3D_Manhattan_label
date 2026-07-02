from __future__ import annotations

import argparse
import csv
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote, urlparse


OUT_DIR = Path("analysis_results/calibration_rebuild_20260702")
IMPORT_DIR = Path("import_json/calibration_c1_v2_draft")
SEED = 20260702

INVENTORY_FIELDS = [
    "task_id",
    "base_task_id",
    "image_id",
    "image_stem",
    "source_path",
    "image_path",
    "source_pool",
    "source_files",
    "used_in_prescreen",
    "used_in_random_c1_deprecated",
    "has_final_gold",
    "geometry_gold_ready",
    "scope_gold_ready",
    "gt_keypoint_count",
    "gt_pair_count",
    "corner_count_bin",
    "old_manual_scope_raw",
    "old_manual_difficulty_raw",
    "old_semi_model_issue_raw",
    "legacy_label_status",
    "expert_review_status",
    "latest_human_reviewed",
    "scope_difficulty_reviewed",
    "legacy_proxy",
    "unreviewed",
    "expert_scope_confirmed",
    "expert_proxy_family_primary",
    "expert_proxy_family_secondary",
    "model_issue_only",
    "semi_only",
    "scope_gate_only",
    "requires_gt_fix",
    "requires_gt_review",
    "hard_exclude",
    "exclude_reason",
    "eligible_for_manual_calibration",
    "eligible_for_core_proxy_sampling",
    "eligible_for_anchor_candidate",
    "eligible_for_reserve_candidate",
    "eligible_for_semi_candidate",
    "core_candidate_type",
    "proxy_confidence",
    "notes",
]

POOL_FIELDS = INVENTORY_FIELDS + ["calibration_split", "selection_rank", "selection_reason", "used_for_r_u"]
ASSIGNMENT_FIELDS = [
    "round_id",
    "worker_id",
    "task_id",
    "base_task_id",
    "dataset_group",
    "assignment_batch",
    "assignment_reason",
    "is_common_anchor",
    "expected_completion_order",
    "manifest_version",
    "watch_flag",
]
SEMI_ASSIGNMENT_FIELDS = ASSIGNMENT_FIELDS + ["used_for_r_u", "used_for_rq2", "semi_family"]


def _safe(value: object) -> str:
    return "" if value is None else str(value).strip()


def _bool(value: object) -> bool:
    return _safe(value).lower() in {"1", "true", "yes", "y"}


def _image_name(value: object) -> str:
    s = _safe(value)
    if "://" in s:
        s = unquote(urlparse(s).path)
    return Path(s).name


def _stem(value: object) -> str:
    return Path(_image_name(value)).stem


def _choices(task: dict, from_name: str) -> list[str]:
    out: list[str] = []
    for ann in task.get("annotations") or task.get("completions") or []:
        for result in ann.get("result") or []:
            if result.get("from_name") != from_name:
                continue
            for choice in (result.get("value") or {}).get("choices") or []:
                if choice not in out:
                    out.append(choice)
    return out


def _keypoints(task: dict) -> int:
    total = 0
    for ann in task.get("annotations") or []:
        for result in ann.get("result") or []:
            if result.get("type") == "keypointlabels":
                total += 1
        if total:
            return total
    return total


def _corner_bin(pair_count: int) -> str:
    if pair_count <= 4:
        return "pairs_le_4"
    if pair_count <= 6:
        return "pairs_5_6"
    if pair_count <= 8:
        return "pairs_7_8"
    return "pairs_ge_9"


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _markdown_task_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return set(re.findall(r"^\|\s*(\d+)\s*\|", path.read_text(encoding="utf-8"), flags=re.M))


def _manual_review_rows(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines() if path.exists() else []:
        if not line.startswith("|") or "---" in line or "task" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells and cells[0].isdigit():
            rows[cells[0]] = {
                "layer": cells[1] if len(cells) > 1 else "",
                "scope": cells[2] if len(cells) > 2 else "",
                "difficulty": cells[3] if len(cells) > 3 else "",
                "note": cells[4] if len(cells) > 4 else "",
                "decision": cells[5] if len(cells) > 5 else "",
            }
    return rows


def _hard_exclude_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    in_section = False
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_section = "直接排除" in line
            continue
        if not in_section or not line.startswith("|") or "---" in line or "task" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells and cells[0].isdigit():
            ids.add(cells[0])
    return ids


GT_FIX_TERMS = ["GT待修正", "GT 待修正", "适合semi但GT待修正"]
GT_REVIEW_TERMS = ["GT 不稳定", "需先确认 GT"]
SEMI_DEFER_TERMS = ["更适合semi", "更适合 semi", "适合做 semi", "适合semi"]


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _final_gold(root: Path) -> dict[str, dict]:
    path = root / "analysis_results/prescreen_closeout_final_gold_v2_20260701/final_gold_records_v2_p1_closeout_corrected.jsonl"
    out: dict[str, dict] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out[_safe(row.get("task_id"))] = row
        out[_safe(row.get("base_task_id"))] = row
    return out


def _prescreen_stems(root: Path) -> set[str]:
    raw = root / "analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs"
    stems: set[str] = set()
    for path in raw.glob("project-*-at-*.json"):
        for task in json.loads(path.read_text(encoding="utf-8")):
            data = task.get("data") or {}
            for key in ("title", "image"):
                s = _stem(data.get(key))
                if s:
                    stems.add(s)
    return stems


def _deprecated_c1_stems(root: Path) -> set[str]:
    path = root / "analysis_results/calibration_c1_prep/calibration_round_input_manifest_v1.json"
    if not path.exists():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    stems: set[str] = set()
    for tasks in (payload.get("task_sets") or {}).values():
        for task in tasks:
            stems.add(_safe(task.get("image_id") or task.get("base_task_id") or task.get("task_id")))
    return stems


def _deprecation_audit(root: Path) -> dict:
    manifest = root / "analysis_results/calibration_c1_prep/calibration_round_input_manifest_v1.json"
    readiness = root / "analysis_results/calibration_c1_prep/c1_launch_readiness_summary.json"
    note = root / "analysis_results/calibration_c1_prep/C1作废说明_20260702.md"
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
    readiness_payload = json.loads(readiness.read_text(encoding="utf-8")) if readiness.exists() else {}
    deprecated = (manifest_payload.get("meta") or {}).get("c1_status") == "deprecated_do_not_launch"
    readiness_blocked = readiness_payload.get("passed") is False
    return {
        "passed": deprecated and readiness_blocked and note.exists(),
        "downstream_allowed": False,
        "manifest_deprecated": deprecated,
        "readiness_passed_false": readiness_blocked,
        "deprecation_note_exists": note.exists(),
        "launch_ready_artifacts_detected": bool(readiness_payload.get("passed") is True),
        "blockers": [] if deprecated and readiness_blocked and note.exists() else ["random_c1_deprecation_incomplete"],
    }


def build_inventory(root: Path) -> tuple[list[dict], dict]:
    old_json = root / "export_label/project-2-at-2026-03-25-10-52-c04c6496.json"
    tasks = json.loads(old_json.read_text(encoding="utf-8"))
    final_gold = _final_gold(root)
    prescreen = _prescreen_stems(root)
    random_c1 = _deprecated_c1_stems(root)
    manual_review = _manual_review_rows(root / "trap集/亲自复核整理与分层_20260702.md")
    scope_difficulty_reviewed = _markdown_task_ids(root / "trap集/范围难度人工分层候选_20260702.md")
    legacy_unreviewed = _markdown_task_ids(root / "trap集/旧标注补充清单_20260702.md")
    pure_model = _markdown_task_ids(root / "trap集/纯模型问题任务记录_20260702.md")
    semi_model = {row["task_id"]: row for row in _read_csv(root / "trap集/校准semi模型问题整理_20260702.csv")}
    hard_exclude = _hard_exclude_ids(root / "trap集/亲自复核整理与分层_20260702.md")

    rows: list[dict] = []
    for task in tasks:
        tid = _safe(task.get("id"))
        data = task.get("data") or {}
        image = data.get("image") or ""
        title = data.get("title") or _image_name(image)
        image_stem = _stem(title or image)
        keypoints = _keypoints(task)
        pairs = keypoints // 2
        fg = final_gold.get(tid) or final_gold.get(image_stem) or {}
        review = manual_review.get(tid, {})
        old_scope = ";".join(_choices(task, "scope"))
        old_diff = ";".join(_choices(task, "difficulty"))
        old_model = ";".join(_choices(task, "model_issue"))
        semi_row = semi_model.get(tid, {})
        used_prescreen = image_stem in prescreen
        used_random = image_stem in random_c1 or tid in random_c1
        note_text = review.get("decision", "") + review.get("note", "") + semi_row.get("manual_note", "")
        model_only = tid in pure_model and tid not in manual_review
        requires_gt_fix = _contains_any(note_text, GT_FIX_TERMS)
        requires_gt_review = _contains_any(note_text, GT_REVIEW_TERMS)
        semi_only = requires_gt_fix or (_contains_any(note_text, SEMI_DEFER_TERMS) and tid not in manual_review)
        excluded = tid in hard_exclude or any(word in review.get("decision", "") + review.get("note", "") for word in ["不适合", "GT 错误", "不好"])
        latest_reviewed = tid in manual_review
        scope_reviewed = tid in scope_difficulty_reviewed
        legacy_proxy = tid in legacy_unreviewed or bool(old_scope or old_diff or old_model)
        unreviewed = (not latest_reviewed) and (not scope_reviewed)
        expert_status = (
            "latest_human_reviewed"
            if latest_reviewed
            else ("scope_difficulty_reviewed" if scope_reviewed else ("legacy_proxy" if legacy_proxy else "unreviewed"))
        )
        legacy_status = "legacy_proxy" if old_scope or old_diff or old_model else "none"
        primary = review.get("difficulty") or semi_row.get("primary_model_issue") or (old_diff.split(";")[0] if old_diff else "")
        secondary = semi_row.get("primary_model_issue") or old_model
        geometry_ready = bool(fg.get("geometry_gold_ready", keypoints >= 2))
        scope_ready = bool(fg.get("scope_gold_ready", bool(old_scope or review.get("scope"))))
        scope_gate_only = "oos" in (old_scope + review.get("scope", "")).lower()
        manual_ok = (not used_prescreen) and (not excluded) and geometry_ready and (not model_only) and (not requires_gt_fix)
        if scope_gate_only:
            core_type = "core_scope_gate_audit_candidate"
        elif old_model or semi_row:
            core_type = "core_paired_semi_counterpart_candidate"
        else:
            core_type = "core_reliability_candidate"
        row = {
            "task_id": tid,
            "base_task_id": image_stem,
            "image_id": image_stem,
            "image_stem": image_stem,
            "source_path": "export_label/project-2-at-2026-03-25-10-52-c04c6496.json",
            "image_path": image,
            "source_pool": "legacy_project2_full_annotation",
            "source_files": ";".join(p for p in [
                "old_label_json",
                "亲自复核整理" if tid in manual_review else "",
                "范围难度人工分层候选" if tid in scope_difficulty_reviewed else "",
                "旧标注补充清单" if tid in legacy_unreviewed else "",
                "纯模型问题任务记录" if tid in pure_model else "",
                "校准semi模型问题整理" if tid in semi_model else "",
            ] if p),
            "used_in_prescreen": str(used_prescreen).lower(),
            "used_in_random_c1_deprecated": str(used_random).lower(),
            "has_final_gold": str(bool(fg)).lower(),
            "geometry_gold_ready": str(geometry_ready).lower(),
            "scope_gold_ready": str(scope_ready).lower(),
            "gt_keypoint_count": str(keypoints or fg.get("n_corners", "")),
            "gt_pair_count": str(pairs or (int(fg.get("n_corners", 0)) // 2 if fg else "")),
            "corner_count_bin": _corner_bin(pairs),
            "old_manual_scope_raw": old_scope,
            "old_manual_difficulty_raw": old_diff,
            "old_semi_model_issue_raw": old_model,
            "legacy_label_status": legacy_status,
            "expert_review_status": expert_status,
            "latest_human_reviewed": str(latest_reviewed).lower(),
            "scope_difficulty_reviewed": str(scope_reviewed).lower(),
            "legacy_proxy": str(legacy_proxy).lower(),
            "unreviewed": str(unreviewed).lower(),
            "expert_scope_confirmed": review.get("scope", ""),
            "expert_proxy_family_primary": primary,
            "expert_proxy_family_secondary": secondary,
            "model_issue_only": str(model_only).lower(),
            "semi_only": str(semi_only).lower(),
            "scope_gate_only": str(scope_gate_only).lower(),
            "requires_gt_fix": str(requires_gt_fix).lower(),
            "requires_gt_review": str(requires_gt_review).lower(),
            "hard_exclude": str(excluded).lower(),
            "exclude_reason": "hard_exclude_from_human_review" if excluded else "",
            "eligible_for_manual_calibration": str(manual_ok).lower(),
            "eligible_for_core_proxy_sampling": str(manual_ok).lower(),
            "eligible_for_anchor_candidate": str(
                manual_ok
                and latest_reviewed
                and geometry_ready
                and scope_ready
                and (not requires_gt_fix)
                and (not requires_gt_review)
                and (not semi_only)
                and (not scope_gate_only)
                and (not model_only)
            ).lower(),
            "eligible_for_reserve_candidate": str(manual_ok).lower(),
            "eligible_for_semi_candidate": str(manual_ok and bool(old_model or semi_row)).lower(),
            "core_candidate_type": core_type,
            "proxy_confidence": "confirmed" if latest_reviewed else ("legacy_proxy" if legacy_proxy else "weak_proxy"),
            "notes": review.get("decision") or review.get("note") or semi_row.get("manual_note", ""),
        }
        rows.append(row)
    summary = {
        "candidate_count": len(rows),
        "eligible_manual_count": sum(_bool(r["eligible_for_manual_calibration"]) for r in rows),
        "hard_exclude_count": sum(_bool(r["hard_exclude"]) for r in rows),
        "prescreen_used_count": sum(_bool(r["used_in_prescreen"]) for r in rows),
        "legacy_unreviewed_count": sum(_bool(r["legacy_proxy"]) and _bool(r["unreviewed"]) for r in rows),
        "model_issue_only_count": sum(_bool(r["model_issue_only"]) for r in rows),
        "semi_only_count": sum(_bool(r["semi_only"]) for r in rows),
    }
    return rows, summary


def _sort_key(row: dict) -> tuple:
    return (
        row["corner_count_bin"],
        row["expert_proxy_family_primary"] or row["old_manual_difficulty_raw"],
        row["image_stem"].split("_")[0],
        row["task_id"],
    )


def _take_balanced(rows: list[dict], n: int, rng: random.Random) -> list[dict]:
    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        buckets[(row["corner_count_bin"], row["expert_proxy_family_primary"] or row["old_manual_difficulty_raw"] or "none")].append(row)
    for bucket in buckets.values():
        rng.shuffle(bucket)
    out: list[dict] = []
    while len(out) < n and any(buckets.values()):
        for key in sorted(buckets):
            if buckets[key] and len(out) < n:
                out.append(buckets[key].pop())
    return out


def select_manual_pools(rows: list[dict], seed: int = SEED) -> tuple[list[dict], list[dict], list[dict], dict]:
    rng = random.Random(seed)
    eligible = [r for r in rows if _bool(r["eligible_for_manual_calibration"])]
    anchors = [r for r in eligible if _bool(r["eligible_for_anchor_candidate"])]
    stable_hard = [r for r in anchors if any(w in r["notes"] + r["expert_proxy_family_primary"] for w in ["高", "难"]) and not r["old_manual_scope_raw"].startswith("oos")]
    rng.shuffle(stable_hard)
    selected_stable = stable_hard[:2]
    anchor_fill = [r for r in anchors if r not in selected_stable]
    anchor = selected_stable + _take_balanced(anchor_fill, 12 - len(selected_stable), rng)
    anchor_ids = {r["task_id"] for r in anchor}
    remaining = [r for r in eligible if r["task_id"] not in anchor_ids]
    core = _take_balanced(remaining, 75, rng)
    core_ids = {r["task_id"] for r in core}
    reserve_candidates = [r for r in remaining if r["task_id"] not in core_ids]
    reserve_candidates.sort(key=lambda r: ("oos" not in r["old_manual_scope_raw"] + r["expert_scope_confirmed"], r["proxy_confidence"], r["task_id"]))
    reserve = reserve_candidates[:13]
    audit = {
        "blockers": [],
        "warnings": [],
        "stable_hard_anchor_count": len([r for r in anchor if r in stable_hard]),
    }
    if len(anchor) != 12 or len(core) != 75 or len(reserve) != 13:
        audit["blockers"].append("insufficient_manual_pool_candidates")
    for split, selected in [("anchor", anchor), ("core", core), ("reserve", reserve)]:
        for rank, row in enumerate(selected, start=1):
            row["calibration_split"] = split
            row["selection_rank"] = str(rank)
            row["selection_reason"] = row["core_candidate_type"] if split == "core" else "draft_proxy_balanced"
            if split == "core":
                row["used_for_r_u"] = "true" if row["core_candidate_type"] == "core_reliability_candidate" else "false_non_reliability_core"
            else:
                row["used_for_r_u"] = "false_scope_gate_audit" if _bool(row["scope_gate_only"]) else "true"
    return anchor, core, reserve, audit


def select_semi_from_core(core: list[dict], seed: int = SEED) -> tuple[list[dict], dict]:
    rng = random.Random(seed + 1)
    quotas = {
        "模型标注质量好": 4,
        "跨门扩张": 5,
        "角点错位/飘移": 5,
        "角点重复": 4,
        "过度解析": 4,
        "漏标": 2,
        "模型预标注失败/拓扑失败": 1,
    }
    by_family: dict[str, list[dict]] = defaultdict(list)
    for row in core:
        family = row["expert_proxy_family_secondary"] or row["old_semi_model_issue_raw"] or row["expert_proxy_family_primary"] or "legacy_proxy_unspecified"
        if "acceptable" in family or "模型标注质量好" in family:
            key = "模型标注质量好"
        elif "overextend" in family or "跨门" in family:
            key = "跨门扩张"
        elif "drift" in family or "mismatch" in family or "错位" in family or "飘移" in family:
            key = "角点错位/飘移"
        elif "duplicate" in family or "重复" in family:
            key = "角点重复"
        elif "over_parsing" in family or "过度" in family:
            key = "过度解析"
        elif "underextend" in family or "漏标" in family:
            key = "漏标"
        elif "fail" in family or "topology" in family:
            key = "模型预标注失败/拓扑失败"
        else:
            key = "legacy_proxy_unspecified"
        row["semi_family"] = key
        by_family[key].append(row)
    for bucket in by_family.values():
        rng.shuffle(bucket)
    selected: list[dict] = []
    shortfalls = {}
    for family, quota in quotas.items():
        take = by_family[family][:quota]
        selected.extend(take)
        if len(take) < quota:
            shortfalls[family] = quota - len(take)
    if len(selected) < 25:
        selected_ids = {r["task_id"] for r in selected}
        fillers = [r for r in core if r["task_id"] not in selected_ids]
        rng.shuffle(fillers)
        selected.extend(fillers[: 25 - len(selected)])
    selected = selected[:25]
    for rank, row in enumerate(selected, start=1):
        row["semi_selection_rank"] = str(rank)
        row["semi_family_confidence"] = "confirmed" if row["proxy_confidence"] == "confirmed" else ("legacy_proxy" if row["legacy_label_status"] == "legacy_proxy" else "likely")
    return selected, {"quotas": quotas, "shortfalls": shortfalls, "semi_count": len(selected)}


def audit_semi_source(semi: list[dict], core: list[dict], anchor: list[dict], reserve: list[dict]) -> dict:
    semi_ids = {row["task_id"] for row in semi}
    core_ids = {row["task_id"] for row in core}
    anchor_ids = {row["task_id"] for row in anchor}
    reserve_ids = {row["task_id"] for row in reserve}
    return {
        "source_pool_all_core": semi_ids <= core_ids,
        "anchor_in_semi_count": len(semi_ids & anchor_ids),
        "reserve_in_semi_count": len(semi_ids & reserve_ids),
        "legacy_proxy_unconfirmed_count": sum(row.get("semi_family_confidence") == "legacy_proxy" for row in semi),
        "used_for_r_u": False,
        "used_for_rq2": True,
    }


def load_workers(root: Path) -> list[dict[str, str]]:
    rows = _read_csv(root / "analysis_results/prescreen_closeout_final_gold_v2_20260701/prescreen_worker_admission.csv")
    workers = [r for r in rows if _bool(r.get("eligible_for_C1"))]
    rng = random.Random(SEED)
    rng.shuffle(workers)
    return workers


def build_manual_assignment(anchor: list[dict], core: list[dict], workers: list[dict[str, str]]) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    order_by_worker = defaultdict(int)
    shuffled_rank = {worker["worker_id"]: idx for idx, worker in enumerate(workers)}
    for task in anchor:
        for worker in workers:
            order_by_worker[worker["worker_id"]] += 1
            rows.append({
                "round_id": "C1",
                "worker_id": worker["worker_id"],
                "task_id": task["task_id"],
                "base_task_id": task["base_task_id"],
                "dataset_group": "Calibration_anchor",
                "assignment_batch": "anchor_all",
                "assignment_reason": "common_anchor",
                "is_common_anchor": "true",
                "expected_completion_order": str(order_by_worker[worker["worker_id"]]),
                "manifest_version": "C1_manual_v2_draft",
                "watch_flag": _safe(worker.get("watch_flag")),
            })
    load = Counter()
    for idx, task in enumerate(core):
        ranked = sorted(workers, key=lambda w: (load[w["worker_id"]], (idx + shuffled_rank[w["worker_id"]]) % len(workers)))
        for worker in ranked[:5]:
            load[worker["worker_id"]] += 1
            order_by_worker[worker["worker_id"]] += 1
            rows.append({
                "round_id": "C1",
                "worker_id": worker["worker_id"],
                "task_id": task["task_id"],
                "base_task_id": task["base_task_id"],
                "dataset_group": "Calibration_core",
                "assignment_batch": "core_rr_k5",
                "assignment_reason": "balanced_core",
                "is_common_anchor": "false",
                "expected_completion_order": str(order_by_worker[worker["worker_id"]]),
                "manifest_version": "C1_manual_v2_draft",
                "watch_flag": _safe(worker.get("watch_flag")),
            })
    core_counts = Counter(r["task_id"] for r in rows if r["dataset_group"] == "Calibration_core")
    total_load = Counter(r["worker_id"] for r in rows)
    audit = {
        "passed": len(anchor) == 12 and len(core) == 75 and set(core_counts.values()) == {5},
        "anchor_task_count": len(anchor),
        "core_task_count": len(core),
        "eligible_worker_count": len(workers),
        "core_redundancy_min": min(core_counts.values()) if core_counts else 0,
        "core_redundancy_max": max(core_counts.values()) if core_counts else 0,
        "reserve_assignment_count": 0,
        "worker_core_load_min": min(load.values()) if load else 0,
        "worker_core_load_max": max(load.values()) if load else 0,
        "worker_total_manual_load_min": min(total_load.values()) if total_load else 0,
        "worker_total_manual_load_max": max(total_load.values()) if total_load else 0,
        "duplicate_worker_task_count": len(rows) - len({(r["worker_id"], r["task_id"]) for r in rows}),
        "duplicate_task_assignment_within_worker": 0,
        "watch_workers_included": sum(_bool(w.get("watch_flag")) for w in workers),
    }
    return rows, audit


def build_semi_assignment(semi: list[dict], manual_rows: list[dict], workers: list[dict[str, str]]) -> tuple[list[dict], dict, dict]:
    manual_by_base: dict[str, set[str]] = defaultdict(set)
    for row in manual_rows:
        manual_by_base[row["base_task_id"]].add(row["worker_id"])
    semi_load = Counter()
    worker_by_id = {worker["worker_id"]: worker for worker in workers}
    shuffled_rank = {worker["worker_id"]: idx for idx, worker in enumerate(workers)}
    rows: list[dict] = []
    overlap = 0
    for task in semi:
        blocked = manual_by_base[task["base_task_id"]]
        available = [w for w in workers if w["worker_id"] not in blocked]
        picked = sorted(available, key=lambda w: (semi_load[w["worker_id"]], shuffled_rank[w["worker_id"]]))[:4]
        for worker in picked:
            semi_load[worker["worker_id"]] += 1
            if worker["worker_id"] in blocked:
                overlap += 1
            rows.append({
                "round_id": "C1",
                "worker_id": worker["worker_id"],
                "task_id": task["task_id"],
                "base_task_id": task["base_task_id"],
                "dataset_group": "Calibration_semi",
                "assignment_batch": "semi_rr_k4",
                "assignment_reason": "rq2_paired_audit",
                "is_common_anchor": "false",
                "expected_completion_order": str(semi_load[worker["worker_id"]]),
                "manifest_version": "C1_semi_v2_draft",
                "watch_flag": _safe(worker.get("watch_flag")),
                "used_for_r_u": "false",
                "used_for_rq2": "true",
                "semi_family": task.get("semi_family", ""),
            })
    for _ in range(1000):
        semi_load = Counter(r["worker_id"] for r in rows)
        lows = [w["worker_id"] for w in workers if semi_load[w["worker_id"]] < 4]
        highs = [w["worker_id"] for w in workers if semi_load[w["worker_id"]] > 4]
        if not lows or not highs:
            break
        low = sorted(lows, key=lambda wid: (semi_load[wid], shuffled_rank[wid]))[0]
        high = sorted(highs, key=lambda wid: (-semi_load[wid], shuffled_rank[wid]))[0]
        for row in rows:
            if row["worker_id"] != high:
                continue
            task_workers = {r["worker_id"] for r in rows if r["task_id"] == row["task_id"]}
            if low in manual_by_base[row["base_task_id"]] or low in task_workers:
                continue
            row["worker_id"] = low
            row["watch_flag"] = _safe(worker_by_id[low].get("watch_flag"))
            break
        else:
            break
    order_by_worker = Counter()
    for row in rows:
        order_by_worker[row["worker_id"]] += 1
        row["expected_completion_order"] = str(order_by_worker[row["worker_id"]])
    counts = Counter(r["task_id"] for r in rows)
    semi_load = Counter(r["worker_id"] for r in rows)
    load_values = [semi_load[w["worker_id"]] for w in workers]
    overlap_audit = audit_manual_semi_overlap(manual_rows, rows)
    audit = {
        "passed": len(semi) == 25 and set(counts.values()) == {4} and overlap_audit["manual_semi_same_image_overlap_count"] == 0 and min(load_values) >= 4 and max(load_values) <= 5,
        "semi_task_count": len(semi),
        "semi_k_min": min(counts.values()) if counts else 0,
        "semi_k_max": max(counts.values()) if counts else 0,
        "worker_semi_load_min": min(load_values) if load_values else 0,
        "worker_semi_load_max": max(load_values) if load_values else 0,
        "manual_semi_same_image_overlap_count": overlap_audit["manual_semi_same_image_overlap_count"],
        "anchor_in_semi_count": 0,
        "reserve_in_semi_count": 0,
        "used_for_r_u_false_count": sum(r["used_for_r_u"] == "false" for r in rows),
        "used_for_rq2_true_count": sum(r["used_for_rq2"] == "true" for r in rows),
    }
    return rows, overlap_audit, audit


def manual_semi_overlap_rows(manual_rows: list[dict], semi_rows: list[dict]) -> list[dict]:
    manual_pairs = {(row["worker_id"], row["base_task_id"]) for row in manual_rows}
    rows = []
    for row in semi_rows:
        overlap = (row["worker_id"], row["base_task_id"]) in manual_pairs
        rows.append(
            {
                "task_id": row.get("task_id", ""),
                "base_task_id": row["base_task_id"],
                "worker_id": row["worker_id"],
                "manual_semi_same_image_overlap": str(overlap).lower(),
            }
        )
    return rows


def audit_manual_semi_overlap(manual_rows: list[dict], semi_rows: list[dict]) -> dict:
    rows = manual_semi_overlap_rows(manual_rows, semi_rows)
    overlap = sum(_bool(row["manual_semi_same_image_overlap"]) for row in rows)
    return {"manual_semi_same_image_overlap_count": overlap, "passed": overlap == 0}


def build_readiness_draft(
    *,
    deprecation: dict,
    balance: dict,
    manual_audit: dict,
    semi_audit: dict,
    overlap_audit: dict,
    semi_quota: dict,
    test_results: str,
) -> dict:
    return {
        "passed": False,
        "status": "draft_pending_human_review",
        "blockers": [
            "manual pool draft pending human approval",
            "semi family draft pending human approval",
            "LS import not yet materialized",
            "active log smoke test not yet run on v2 projects",
            "worker-facing distribution not generated",
        ]
        + balance.get("blockers", []),
        "protocol_checks": {
            "random_c1_deprecated": deprecation["passed"],
            "reserve_excluded_from_c1": manual_audit["reserve_assignment_count"] == 0,
            "semi_only_from_core": semi_quota["source_pool_all_core"],
            "readiness_for_launch": False,
        },
        "overlap_checks": {"prescreen_overlap_count": balance["prescreen_overlap_count"]},
        "assignment_checks": {"manual": manual_audit, "semi": semi_audit, "manual_semi_overlap": overlap_audit},
        "proxy_balance_warnings": balance["warnings"] + [f"semi_shortfall:{k}={v}" for k, v in semi_quota.get("shortfalls", {}).items()],
        "test_results": test_results,
    }


def _import_task(row: dict, group: str, include_model_issue: bool) -> dict:
    data = {
        "image": row["image_path"],
        "title": f"{row['image_stem']}.png",
        "task_id": row["task_id"],
        "base_task_id": row["base_task_id"],
        "image_id": row["image_id"],
        "dataset_group": group,
        "calibration_v2_status": "draft_pending_human_review",
        "launch_allowed": False,
        "artifact_status": "draft_not_for_launch",
        "legacy_scope_raw_sidecar": row["old_manual_scope_raw"],
        "legacy_difficulty_raw_sidecar": row["old_manual_difficulty_raw"],
        "proxy_confidence": row["proxy_confidence"],
    }
    if include_model_issue:
        data["legacy_model_issue_raw_sidecar"] = row["old_semi_model_issue_raw"]
        data["semi_family_proxy"] = row.get("semi_family", "")
    return {"data": data}


def _balance_summary(anchor: list[dict], core: list[dict], reserve: list[dict], audit: dict) -> dict:
    selected = anchor + core + reserve
    return {
        "counts": {"anchor": len(anchor), "core": len(core), "reserve": len(reserve)},
        "prescreen_overlap_count": sum(_bool(r["used_in_prescreen"]) for r in selected),
        "hard_exclude_inclusion_count": sum(_bool(r["hard_exclude"]) for r in selected),
        "semi_only_inclusion_count": sum(_bool(r["semi_only"]) for r in selected),
        "model_issue_only_inclusion_count": sum(_bool(r["model_issue_only"]) for r in selected),
        "corner_count_bin_distribution": dict(Counter(r["corner_count_bin"] for r in selected)),
        "expert_review_status_distribution": dict(Counter(r["expert_review_status"] for r in selected)),
        "legacy_proxy_unreviewed_count": sum(r["expert_review_status"] == "unreviewed" for r in selected),
        "source_concentration": dict(Counter(r["image_stem"].split("_")[0] for r in selected)),
        "stable_hard_anchor_count": audit.get("stable_hard_anchor_count", 0),
        "reserve_c2_only_status": "reserve_not_assigned_in_C1",
        "warnings": audit.get("warnings", []),
        "blockers": audit.get("blockers", []),
    }


def build_all(root: Path, test_results: str = "not_run_by_script") -> dict:
    out = root / OUT_DIR
    import_dir = root / IMPORT_DIR
    deprecation = _deprecation_audit(root)
    _write_json(out / "random_c1_deprecation_audit_v1.json", deprecation)
    inventory, inv_summary = build_inventory(root)
    _write_csv(out / "calibration_candidate_inventory_v2.csv", inventory, INVENTORY_FIELDS)
    _write_json(out / "calibration_candidate_inventory_summary_v2.json", inv_summary)
    anchor, core, reserve, pool_audit = select_manual_pools(inventory)
    manual = anchor + core + reserve
    _write_csv(out / "calibration_manual_pool_draft_v2.csv", manual, POOL_FIELDS)
    _write_csv(out / "calibration_anchor_draft_v2.csv", anchor, POOL_FIELDS)
    _write_csv(out / "calibration_core_draft_v2.csv", core, POOL_FIELDS)
    _write_csv(out / "calibration_reserve_draft_v2.csv", reserve, POOL_FIELDS)
    _write_csv(out / "calibration_pool_selection_audit_v2.csv", manual, POOL_FIELDS)
    balance = _balance_summary(anchor, core, reserve, pool_audit)
    _write_json(out / "calibration_pool_proxy_balance_summary_v2.json", balance)
    semi, semi_quota = select_semi_from_core(core)
    _write_csv(out / "calibration_semi_selection_draft_v2.csv", semi, POOL_FIELDS + ["semi_family", "semi_family_confidence", "semi_selection_rank"])
    semi_source_audit = audit_semi_source(semi, core, anchor, reserve)
    semi_quota = semi_quota | semi_source_audit
    _write_json(out / "calibration_semi_family_quota_draft_v2.json", semi_quota)
    _write_csv(out / "calibration_semi_source_audit_v2.csv", semi, POOL_FIELDS + ["semi_family", "semi_family_confidence", "semi_selection_rank"])
    workers = load_workers(root)
    manual_assign, manual_audit = build_manual_assignment(anchor, core, workers)
    _write_csv(out / "assignment_manifest_C1_manual_draft_v2.csv", manual_assign, ASSIGNMENT_FIELDS)
    _write_json(out / "c1_manual_assignment_audit_v2.json", manual_audit)
    semi_assign, overlap_audit, semi_audit = build_semi_assignment(semi, manual_assign, workers)
    _write_csv(out / "assignment_manifest_C1_semi_draft_v2.csv", semi_assign, SEMI_ASSIGNMENT_FIELDS)
    _write_csv(
        out / "manual_semi_same_image_overlap_audit_v2.csv",
        manual_semi_overlap_rows(manual_assign, semi_assign),
        ["task_id", "base_task_id", "worker_id", "manual_semi_same_image_overlap"],
    )
    _write_json(out / "c1_semi_assignment_audit_v2.json", semi_audit)
    _write_json(import_dir / "stage2_calibration_manual_anchor_import_c1_v2_draft.json", [_import_task(r, "Calibration_anchor", False) for r in anchor])
    _write_json(import_dir / "stage2_calibration_manual_core_import_c1_v2_draft.json", [_import_task(r, "Calibration_core", False) for r in core])
    _write_json(import_dir / "stage2_calibration_semi_import_c1_v2_draft.json", [_import_task(r, "Calibration_semi", True) for r in semi])
    _write_json(import_dir / "stage2_calibration_reserve_import_c2_v2_draft.json", [_import_task(r, "Calibration_reserve", False) for r in reserve])
    _write_json(import_dir / "calibration_import_draft_summary_v2.json", {
        "status": "draft_pending_human_review",
        "artifact_status": "draft_not_for_launch",
        "launch_allowed": False,
        "no_label_studio_import_performed": True,
        "counts": {"anchor": len(anchor), "core": len(core), "semi": len(semi), "reserve": len(reserve)},
        "reserve_import_scope": "C2_draft_only",
    })
    readiness = build_readiness_draft(
        deprecation=deprecation,
        balance=balance,
        manual_audit=manual_audit,
        semi_audit=semi_audit,
        overlap_audit=overlap_audit,
        semi_quota=semi_quota,
        test_results=test_results,
    )
    _write_json(out / "c1_launch_readiness_draft_v2.json", readiness)
    report = "\n".join([
        "# C1/C2 v2 rebuild draft report",
        "",
        "Status: draft_pending_human_review. No C1 launch, no LS import, no worker-facing distribution.",
        "",
        f"- inventory candidates: {len(inventory)}",
        f"- manual draft: anchor={len(anchor)}, core={len(core)}, reserve={len(reserve)}",
        f"- semi draft: {len(semi)} from core only",
        f"- eligible workers read from P1 admission: {len(workers)}",
        f"- readiness passed: {readiness['passed']}",
    ]) + "\n"
    (out / "C1_v2_rebuild_report.md").write_text(report, encoding="utf-8")
    return {
        "inventory": inventory,
        "anchor": anchor,
        "core": core,
        "reserve": reserve,
        "semi": semi,
        "manual_audit": manual_audit,
        "semi_audit": semi_audit,
        "readiness": readiness,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Calibration C1/C2 v2 draft selection and audits.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--test-results", default="not_run_by_script")
    args = parser.parse_args()
    build_all(args.root.resolve(), test_results=args.test_results)


if __name__ == "__main__":
    main()
