#!/usr/bin/env python3
"""Attach explanatory display metadata to two exact exported ABC events.

Only figure metadata are added. Original members, states, points, scores and
references are copied unchanged; composition exports remain the source of truth.
The two cases are selected after results to illustrate a positive and a failure,
not as estimates of the frequency of either outcome.
"""
from __future__ import annotations
import copy
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent

SPECS = {
    "G01_QTD_n20_m8_positive": {
        "title": "20人换8人：同构成相近，改构成丢失多个角点",
        "subtitle": "jtc-26 / Manual / QTD探索细类；A−B、A−C均为12人共同背景＋替换8人；B−C仅换3人",
        "focus_title": "三处投票同时低于10票：约x686、x907、x944",
        "zoom_erp": [640, 975, 125, 435],
        "raw_overlay_groups": [
            {"label": "QH.1：B中保留、C中移出", "class_id": "QH.1", "workers": ["W115", "W130"]},
            {"label": "QH.2：B中保留、C中移出", "class_id": "QH.2", "workers": ["W112"]},
            {"label": "QL.2：C中新加入，表达仍不同", "class_id": "QL.2", "workers": ["W106", "W119", "W128"]},
        ],
    },
    "G02_QTD_n15_m12_counterexample": {
        "title": "15人换12人反例：相同细类构成更不稳定",
        "subtitle": "jtc-26 / Manual / QTD探索细类；A−B、A−C均为3人共同背景＋替换12人；B−C仅换4人",
        "focus_title": "A与C均保留约x907、x930两角；同构成B的两组均只有7票，门槛为8",
        "zoom_erp": [640, 975, 125, 435],
        "raw_overlay_groups": [
            {"label": "QH.1：A中的两位成员", "class_id": "QH.1", "workers": ["W115", "W130"]},
            {"label": "QH.1：B中的两位同类成员", "class_id": "QH.1", "workers": ["W104", "W125"]},
            {"label": "QH.2：C中替入的两位细类成员", "class_id": "QH.2", "workers": ["W112", "W114"]},
            {"label": "QL.2：同类的4点与9点表达", "class_id": "QL.2", "workers": ["W106", "W119"]},
        ],
    },
    "G03_M_structure_pa4_n15_m8": {
        "title": "独立建筑的15人换8人：增加结构类支持，补回局部角点",
        "subtitle": "pa4-10 / Manual / M细类；A−B、A−C均为7人共同背景＋替换8人；B−C仅换6人",
        "focus_title": "约x591位置组7票升至9票，超过固定8票门槛；另两处仍为7票",
        "zoom_erp": [530, 635, 110, 440],
        "raw_overlay_groups": [
            {"label": "M11：共同背景的两位支持者", "class_id": "M11", "workers": ["W109", "W115"]},
            {"label": "M11：C中新增的两位支持者", "class_id": "M11", "workers": ["W112", "W130"]},
            {"label": "M01：本次移出与加入的支持者", "class_id": "M01", "workers": ["W123", "W127"]},
        ],
        "class_names": {"M00": "M00", "M01": "M01", "M10": "M10", "M11": "M11"},
        "class_colors": {"M00": "#315bc6", "M01": "#1e7b74", "M10": "#ad5b1d", "M11": "#ac4c79"},
        "method_status": "taxonomy M_structure target-building-excluded fine labels; independent of QTD classes",
    },
}


def main():
    receipts = []
    for case_id, spec in SPECS.items():
        path = STUDY / "composition/cases" / f"{case_id}.json"
        original = json.loads(path.read_text())
        case = copy.deepcopy(original)
        case.update(spec)
        event = case["event"]
        case["method_id"] = event["method_id"]
        case["tier"] = event["tier"]
        case["pool_meta"] = {k: event[k] for k in ["image", "image_id", "building", "condition", "difficulty", "layer"]}
        case["selection"] = "post_result_positive_and_counterexample_mechanism_not_frequency_estimation"
        case.setdefault("class_names", {x: x for x in ["QH.1", "QH.2", "QL.1", "QL.2"]})
        case.setdefault("class_colors", {"QH.1": "#1e7b74", "QH.2": "#315bc6", "QL.1": "#ad5b1d", "QL.2": "#ac4c79"})
        case["member_overlay_title"] = spec["title"] + "：完整成员按楼外细类叠加"
        case["source_case"] = str(path.relative_to(STUDY))
        case["source_case_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        case.setdefault("method_status", "MV_QTD_manual cross-source exploratory; not MV_QTD_manual_new recommended same-source labels")
        for key in ["members", "teams", "reference", "event"]:
            assert case[key] == original[key]
        output = HERE / "cases" / f"{case_id}.json.gz"
        existing = json.loads(gzip.decompress(output.read_bytes())) if output.exists() else None
        if existing != case:
            output.write_bytes(gzip.compress(json.dumps(case, ensure_ascii=False, allow_nan=False).encode("utf-8"),mtime=0))
        receipts.append({"case_id": case_id, "source_case": case["source_case"],
                         "source_sha256": case["source_case_sha256"], "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                         "event_id": event["event_id"], "actual_m_AB": event["m_AB"], "actual_m_AC": event["m_AC"],
                         "actual_m_BC": event["m_BC"], "unchanged_keys": ["members", "teams", "reference", "event"],
                         "no_fusion_or_scoring": True})
    (HERE / "LARGE_CASE_DISPLAY_RECEIPT.json").write_text(json.dumps(receipts, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(receipts, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
