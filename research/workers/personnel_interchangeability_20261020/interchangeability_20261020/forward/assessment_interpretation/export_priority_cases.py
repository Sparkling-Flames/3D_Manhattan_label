#!/usr/bin/env python3
"""Exact T23 illustration/counterexample list with final native geometries."""
from pathlib import Path
import sys
import json
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "discovery_interpretation"))
from analyze_discovery import stream_events, read, write_json, sha

SELECTED = {
    "I20_58467a3dfec46697895062": ("T23_fast_near_geometry_cached", "历史高Q23慢→快；源/Q匹配，近几何且报告块时间更少", "analysis/selected_originals/q9vSo1VnCiC_3e5aacbc10904d4b88660a3cb91efcb9.png"),
    "I20_280b1d2b8c945dd9fa64e3": ("T23_stable_low_quality_cached", "稳定且报告用时更少，但在冻结主参考下A/B/C均低分", "analysis/selected_originals/UwV83HsGsw3_7482b1a2655e4655ae4ab58749f43f65.png"),
    "I20_4da3873a0cfaa6960e95dd": ("T23_fast_cross_quality_bad_tail", "快类跨入后大幅掉分与足迹变化；来源报告仍更快", None),
    "I20_4a6a26f13240998cc23ff9": ("T23_same_class_bad_tail", "同类具体成员B掉分明显，而另一类C较接近A", None),
}

def main():
    ap = ROOT / "interchangeability_20261020/assessment"
    req = ap / "direction_requests.json.gz"
    events = {e["event_id"]: e for e in stream_events(req) if e["event_id"] in SELECTED}
    assert set(events) == set(SELECTED)
    snapshot = {p["pool_id"]: p for p in read(ROOT / "repo/research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz")["images"]}
    labels = pd.read_csv(HERE.parent / "worker_labels.csv.gz")
    labels = labels.loc[labels.method_id.eq("F20_highQ23_T_qK2") & labels.known]
    cl = dict(zip(labels.worker_id, labels.class_id))
    cases = []
    for eid, (case_id, reason, original) in SELECTED.items():
        e = events[eid]; pid = e["pool_id"]
        assert e["phase"] == "assessment" and e["n"] == 13 and e["m"] == 2 and e["direction"] == "C02>C01"
        metrics = pd.read_csv(ap / "direction_metrics/event_parts" / (pid + ".csv.gz"))
        metrics = metrics.loc[metrics.event_id.eq(eid)]
        assert len(metrics) == 1
        native_path = ap / "native_directions/pools" / (pid + ".json.gz")
        teams = {t["team_key"]: t for t in read(native_path)["teams"]}
        picks = {}
        keys = ["team_key", "member_workers", "k", "B8L2", "D10", "complete_evaluable", "geometry", "reference_id", "score_status", "geometry_reason", "iou_2d", "IoU3D100", "omission", "extension", "ref_node_recall_9", "ref_edge_recall_9", "nodes"]
        for arm in "ABC":
            t = teams[e[arm + "_team_key"]]
            assert sorted(t["member_workers"]) == e[arm + "_workers"] and t["reference_id"] == e["reference_id"]
            picks[arm] = {k: t.get(k) for k in keys}
            picks[arm]["historical_class_by_member"] = {w: cl.get(w, "outside_group") for w in t["member_workers"]}
        pool = snapshot[pid]
        wr = {r["worker_id"]: r for r in pool["records"]}
        block_records = {name: [{k: wr[w].get(k) for k in ("worker_id", "origin", "source_time_seconds", "target_time_seconds", "record_id")} for w in e[name]] for name in ("outgoing_workers", "within_incoming", "cross_incoming")}
        image = dict(file=original, available=bool(original and (ROOT / original).exists()))
        if image["available"]:
            image["sha256"] = sha(ROOT / original)
        cases.append(dict(case_id=case_id, event_id=eid, reason_zh=reason, exact_request=e, original_image=image,
                          metrics=json.loads(metrics.to_json(orient="records"))[0], native_final_teams=picks,
                          reference=pool["reference"], source_records_for_replacement_blocks=block_records,
                          native_path=str(native_path.relative_to(ROOT)), native_sha256=sha(native_path)))
    write_json(HERE / "PRIORITY_CASES.json", dict(schema="F11_priority_T23_exact_cases_v1", root_freeze_sha256=sha(ap / "ASSESSMENT_FREEZE.json"),
        request_sha256=sha(req), labels_sha256=sha(HERE.parent / "worker_labels.csv.gz"), cases=cases,
        geometry="Necessary final geometry and frozen reference only; no full per-team workflow state. Cases illustrate already frozen rules, not new model selection.",
        time="Exact source task reported seconds for the replacement blocks. New target_time_seconds null remains missing. Single-case C/B is a literal ratio; cohort figures exponentiate building-weighted mean log ratios."))
    print(json.dumps({"cases": len(cases), "bytes": (HERE / "PRIORITY_CASES.json").stat().st_size}))

if __name__ == "__main__":
    main()
