#!/usr/bin/env python3
"""Loss-aware small evidence exports; never edit full research outputs.

All exact strata survive, including zero/negative/unsupported quality outcomes.
Every event in the fixed 13 highlight strata survives. Only precision of the
large aggregate ledger is reduced (six decimals); event scores are unchanged.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd


KEY = ["method_id", "domain", "outgoing_counts", "incoming_counts", "k", "m"]
EVENT_COLUMNS = [
    "highlight_id", "event_id", "phase", "method_id", "domain", "pool_id", "image", "building", "difficulty", "scene",
    "k", "m", "outgoing_counts", "incoming_counts", "A_composition", "C_composition", "reference_id", "reference_version",
    "matching", "matched_origin", "pattern", "actual_source_match", "incoming_Q_close_3", "history_Q_column",
    "outgoing_history_Q", "within_history_Q", "cross_history_Q", "cross_minus_within_history_Q",
    "outgoing_new_n", "within_new_n", "cross_new_n", "computed_arms_n", "event_status",
] + [a + "_" + col for a in "ABC" for col in ["team_key", "B8L2", "D10", "complete", "score_status", "geometry_reason", "score_available", "nodes", "new_n"]] + [
    "within_turnover", "changed_turnover", "net_turnover",
    "within_abs_B8L2_change", "changed_abs_B8L2_change", "excess_abs_B8L2_change", "net_B8L2_change", "net_D10_change",
    "within_floor_jaccard_difference", "changed_floor_jaccard_difference", "excess_floor_jaccard_difference", "net_floor_jaccard_difference",
    "within_structure_bound_cyclic_deg", "changed_structure_bound_cyclic_deg", "within_structure_reason", "changed_structure_reason",
    "within_node_count_difference", "changed_node_count_difference", "net_node_count_change",
    "within_mean_height_prism_pair_iou", "changed_mean_height_prism_pair_iou", "net_mean_height_prism_pair_iou",
    "within_joint_stable_main", "changed_joint_stable_main", "within_quality_comparable", "changed_quality_comparable", "net_quality_comparable",
    "net_iou_2d_change", "net_IoU3D100_change", "net_omission_change", "net_extension_change",
    "net_ref_node_recall_9_change", "net_ref_edge_recall_9_change", "net_diag_wall_coverage_05_change", "net_diag_corner_recall_05_change",
    "net_complete_lost", "net_complete_restored", "similar_Q2_changed_structure",
]
LOOW_SUMMARY_COLUMNS = ["phase", "subset"] + KEY + [
    "removed_workers_tested", "base_events", "base_images", "base_buildings", "base_workers", "base_teams",
    "min_remaining_events", "min_remaining_images", "min_remaining_buildings", "max_removed_event_fraction",
    "removals_retaining_three_Q_buildings", "removals_losing_three_Q_buildings", "retained3b_Q_direction_reversals",
] + [pre + metric + suf for metric in ["net_B8L2_change", "excess_abs_B8L2_change", "excess_floor_jaccard_difference", "net_ref_edge_recall_9_change", "net_diag_wall_coverage_05_change"]
     for pre, suf in [("base_", ""), ("retained3b_", "_min"), ("retained3b_", "_max")]] + ["largest_Q_gain_removed_worker", "smallest_Q_gain_removed_worker"]
LOOW_PERSON_COLUMNS = ["highlight_id", "phase", "subset"] + KEY + [
    "removed_worker", "worker_class", "class_history_workers", "class_workers_remaining_after_removal",
    "base_events", "base_images", "base_buildings", "base_workers", "base_teams", "retained_events", "retained_images", "retained_buildings", "retained_workers", "retained_teams",
    "removed_event_fraction", "supports_three_building_Q_comparison_after_removal",
    "base_net_B8L2_change", "retained_net_B8L2_change", "net_B8L2_change_finite_events", "net_B8L2_change_finite_images", "net_B8L2_change_finite_buildings",
    "retained_excess_abs_B8L2_change", "retained_excess_floor_jaccard_difference", "retained_net_ref_edge_recall_9_change", "retained_net_diag_wall_coverage_05_change",
    "net_ref_edge_recall_9_change_finite_events", "net_ref_edge_recall_9_change_finite_images", "net_ref_edge_recall_9_change_finite_buildings",
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    with (gzip.open(path, "rt") if str(path).endswith(".gz") else open(path)) as f:
        return json.load(f)


def packed(*columns):
    parts = [col.astype("Int64").astype(str).replace("<NA>", "NA") for col in columns]
    out = parts[0]
    for s in parts[1:]:
        out = out + "/" + s
    return out


def finite_support(f, metric):
    return packed(f[metric + "_n"], f[metric + "_finite_images"], f[metric + "_finite_buildings"])


def fixed_highlights(frame, definitions):
    parts = []
    used = set()
    for d in definitions:
        mask = np.ones(len(frame), bool)
        for c in KEY:
            mask &= frame[c].eq(d[c]).to_numpy()
        s = frame.loc[mask].copy()
        s.insert(0, "highlight_id", d["highlight_id"])
        assert not (set(s.index) & used)
        used.update(s.index)
        parts.append(s)
    return pd.concat(parts, ignore_index=True)


def exact_small(f):
    out = f[["view", "subset", "phase"] + KEY + ["difficulty"]].copy()
    out["attempted_events_images_buildings"] = packed(f.events, f.images, f.buildings)
    out["workers_teams_cores"] = packed(f.workers, f.observed_unique_teams, f.unique_cores)
    out["quality_finite_events_images_buildings"] = finite_support(f, "net_B8L2_change")
    out["quality_positive_negative_buildings"] = packed(f.net_B8L2_change_positive_buildings, f.net_B8L2_change_negative_buildings)
    names = {
        "delta_Q": "net_B8L2_change_equal_building_mean",
        "delta_Q_event_p10": "net_B8L2_change_event_p10",
        "within_abs_Q": "within_abs_B8L2_change_equal_building_mean",
        "changed_abs_Q": "changed_abs_B8L2_change_equal_building_mean",
        "excess_abs_Q": "excess_abs_B8L2_change_equal_building_mean",
        "within_floor_distance": "within_floor_jaccard_difference_equal_building_mean",
        "changed_floor_distance": "changed_floor_jaccard_difference_equal_building_mean",
        "excess_floor_distance": "excess_floor_jaccard_difference_equal_building_mean",
        "delta_edge": "net_ref_edge_recall_9_change_equal_building_mean",
        "delta_wall": "net_diag_wall_coverage_05_change_equal_building_mean",
        "delta_nodes": "net_node_count_change_equal_building_mean",
        "within_stable": "within_joint_stable_main_equal_building_mean",
        "changed_stable": "changed_joint_stable_main_equal_building_mean",
    }
    for small, big in names.items():
        out[small] = f[big].round(6)
    for small, big in [("within_Q_support", "within_abs_B8L2_change"), ("changed_Q_support", "changed_abs_B8L2_change"),
                       ("within_floor_support", "within_floor_jaccard_difference"), ("changed_floor_support", "changed_floor_jaccard_difference"),
                       ("edge_support", "net_ref_edge_recall_9_change"), ("wall_support", "net_diag_wall_coverage_05_change")]:
        out[small] = finite_support(f, big)
    out["paired_excess_Q_floor_events"] = packed(f.excess_abs_B8L2_change_n, f.excess_floor_jaccard_difference_n)
    out["node_finite_events"] = f.net_node_count_change_n.astype("Int64")
    b_available = (f.B_score_available_n * f.B_score_available_event_mean).round()
    c_available = (f.C_score_available_n * f.C_score_available_event_mean).round()
    out["B_C_score_missing_events"] = packed(f.events-b_available, f.events-c_available)
    out["complete_lost_restored_events"] = packed((f.net_complete_lost_n*f.net_complete_lost_event_mean).round(),
                                                   (f.net_complete_restored_n*f.net_complete_restored_event_mean).round())
    assert len(out) == len(f)
    return out, names


def verify_requests(highlight_events, manifest, summary_receipt):
    assert summary_receipt["exact_members_and_compositions_rebuilt"] and summary_receipt["missing_computation_teams"] == 0
    expected = {e["event_id"]: e for e in manifest["events"]}
    matched, teams, workers = 0, set(), set()
    digests = {}
    for r in highlight_events.itertuples(index=False):
        e = expected[r.event_id]
        for col in ["phase", "method_id", "domain", "pool_id", "k", "m"]:
            assert getattr(r, col) == e[col]
        for col, src in [("core_workers_json", "core_workers"), ("outgoing_workers_json", "outgoing_workers"),
                         ("within_incoming_json", "within_incoming"), ("cross_incoming_json", "cross_incoming")]:
            assert sorted(json.loads(getattr(r, col))) == sorted(e[src])
        for arm in "ABC":
            key, members = e[arm+"_team_key"], sorted(e[arm+"_workers"])
            assert key == getattr(r, arm+"_team_key") and len(members) == r.k
            canonical = json.dumps(members, separators=(",", ":"), ensure_ascii=True)
            digest = hashlib.sha256(canonical.encode()).hexdigest()
            if key in digests:
                assert digests[key] == digest
            digests[key] = digest
            teams.add(key); workers.update(members)
        matched += 1
    return dict(events_checked=matched, unique_teams_checked=len(teams), workers=len(workers),
                member_digest_sha256=hashlib.sha256(json.dumps(digests, sort_keys=True, separators=(",", ":")).encode()).hexdigest())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    args.out = args.out or args.root / "compact_block_evidence"
    args.out.mkdir(parents=True, exist_ok=True)
    prior_receipt = args.out / "COMPACT_RECEIPT.json"
    prior_outputs = {x["file"]: x["sha256"] for x in read(prior_receipt).get("outputs", [])} if prior_receipt.exists() else {}
    definitions_path = args.root / "block_discovery_specific/HIGHLIGHT_DEFINITIONS.json"
    definitions = read(definitions_path)["definitions"]
    tables = {k: [] for k in ["01_highlight_events", "02_all_exact_strata", "03_loow_stratum_summary", "04_highlight_loow_person", "05_loow_support_ledger"]}
    inputs, checks = {str(definitions_path): sha(definitions_path)}, {}
    for phase in ["discovery", "validation"]:
        root = args.root / f"block_{phase}_specific"
        paths = {
            "events": args.root / f"block_{phase}/block_events.csv.gz",
            "receipt": args.root / f"block_{phase}/BLOCK_SUMMARY_RECEIPT.json",
            "exact": root / "directed_exact_summary.csv.gz", "loow_summary": root / "leave_one_worker_summary.csv.gz",
            "loow_person": root / "leave_one_worker_out.csv.gz", "loow_ledger": root / "leave_one_worker_support_ledger.csv.gz",
            "requests": args.root / (phase.upper() + "_BLOCK_REQUESTS.json.gz"),
        }
        inputs.update({str(p): sha(p) for p in paths.values()})
        events = pd.read_csv(paths["events"], low_memory=False)
        selected = fixed_highlights(events, definitions)
        checks[phase] = verify_requests(selected, read(paths["requests"]), read(paths["receipt"]))
        tables["01_highlight_events"].append(selected[EVENT_COLUMNS])
        exact = pd.read_csv(paths["exact"], low_memory=False)
        small, names = exact_small(exact)
        tables["02_all_exact_strata"].append(small)
        loow = pd.read_csv(paths["loow_summary"], low_memory=False)
        tables["03_loow_stratum_summary"].append(loow[LOOW_SUMMARY_COLUMNS])
        people = pd.read_csv(paths["loow_person"], low_memory=False)
        hp = fixed_highlights(people, definitions)
        tables["04_highlight_loow_person"].append(hp[LOOW_PERSON_COLUMNS])
        ledger = pd.read_csv(paths["loow_ledger"], low_memory=False)
        ledger.insert(0, "phase", phase)
        tables["05_loow_support_ledger"].append(ledger)
        checks[phase].update(all_events=len(events), primary_events=int(events.m.ge(2).sum()),
                             exact_rows_exported=len(small), exact_rows_source=len(exact),
                             loow_strata_exported=len(loow), highlight_loow_rows=len(hp),
                             selected_event_outcome_filter=False, exact_stratum_outcome_filter=False)
    outputs, dictionaries = [], {}
    for name, pieces in tables.items():
        full = pd.concat(pieces, ignore_index=True)
        # XZ efficiently removes long-range repeated exact-stratum fields;
        # it is lossless and readable by pandas/stdlib lzma, with no new dependency.
        suffix = ".csv.xz" if name == "02_all_exact_strata" else ".csv.gz"
        path = args.out / (name + suffix)
        compression = {"method": "xz", "preset": 9} if suffix.endswith(".xz") else {"method": "gzip", "mtime": 0}
        full.to_csv(path, index=False, compression=compression)
        reread = pd.read_csv(path, low_memory=False)
        assert list(reread) == list(full) and len(reread) == len(full)
        # IEEE float text round-trip can change the last bit; meaningful scores,
        # missing masks, IDs and table membership must not change.
        for col in full:
            if pd.api.types.is_numeric_dtype(full[col]):
                assert np.allclose(pd.to_numeric(full[col]).to_numpy(dtype=float, na_value=np.nan),
                                   pd.to_numeric(reread[col]).to_numpy(dtype=float, na_value=np.nan), equal_nan=True, rtol=1e-12, atol=1e-12), (name, col)
            else:
                assert full[col].fillna("__NA__").astype(str).tolist() == reread[col].fillna("__NA__").astype(str).tolist(), (name, col)
        outputs.append(dict(file=path.name, rows=len(full), columns=len(full.columns), bytes=path.stat().st_size, sha256=sha(path)))
        dictionaries[path.name] = list(full.columns)
        if suffix.endswith(".xz"):
            legacy = args.out / (name + ".csv.gz")
            if legacy.exists():
                assert prior_outputs.get(legacy.name) == sha(legacy), "Do not remove a modified or foreign file"
                legacy.unlink()
    dictionary = {
        "common": {
            "phase": "discovery或validation；不能把阶段合并当独立新图片。", "method_id/domain": "冻结人员分类与适用域；all全域，hard为已有困难条件。",
            "outgoing_counts/incoming_counts": "C01:n|C02:n的完整出/入类别人数向量；零计数保留。", "k/m": "总人数/在A→B及A→C中各自精确换人数。",
            "A/B/C": "A原块；B同类构成的其他成员；C改变类别人数块；三臂同图同公共背景。", "within/changed/net": "分别比较A-B/A-C/B-C；net有符号指标为C−B。",
            "actual_source_match": "原块、B换入块及C换入块new/v1人数向量完全相同。", "incoming_Q_close_3": "C与B换入块历史平均Q差绝对值≤3；hard用theta_hard，全域用q_beta。",
            "B8L2/D10": "冻结评分主评价/匹配敏感性，缺失不补零。", "complete/score_status/geometry_reason": "融合完整状态、评分状态、几何不可比理由；与缺计算分开。",
            "team_key": "已核验的图片池＋精确成员hash；用对应spec/seed重新生成requests可恢复成员。", "net_turnover": "B和C实际不同人员数；换入块可能重叠，故可小于m。",
            "floor_jaccard_difference": "两融合底面1−IoU；越大差异越大。", "structure_bound_cyclic_deg": "同节点数时循环匹配的最大边界角度差；节点数不同记缺失并保留reason。",
            "mean_height_prism_pair_iou": "平均高度棱柱之间的三维IoU代理，非主质量分。", "ref_node/edge_recall_9": "相同参考的9度几何对应诊断，非必要结构语义真值。",
            "diag_wall_coverage_05": "参考墙段长度覆盖，空间容差5%√参考底面积且方向差≤10度。", "joint_stable_main": "两臂完整、|ΔQ|≤2、底面差≤.05、同节点数且循环角差≤3度。",
            "event_p10": "有限逐事件C−B差值的第10百分位，不是C的p10减B的p10，也不是置信区间。",
            "similar_Q2_changed_structure": "分数差≤2而几何或节点结构变化的描述标志。",
        },
        "exact_small": {
            "view": "exact_counts_k_m与加difficulty的细分均完整保留。", "subset": "总体、来源匹配、历史Q接近、来源且Q接近分别保留。",
            "attempted_events_images_buildings": "以/分隔的尝试事件数/图片数/建筑数。", "workers_teams_cores": "真实人员数/唯一团队数/(图片,公共人员组)背景数。",
            "quality_finite_events_images_buildings": "C−B质量可比较的事件数/图片数/建筑数。", "quality_positive_negative_buildings": "楼等权前的各楼平均ΔQ为正/负的建筑数。",
            "*_support": "对应指标的有限事件数/图片数/建筑数，以/分隔；不与尝试支持混同。", "paired_excess_Q_floor_events": "AC距离−AB距离在共同有限三队上计算的Q/底面事件数。",
            "B_C_score_missing_events": "B主分缺失事件数/C主分缺失事件数。", "complete_lost_restored_events": "B完整C不完整的次数/B不完整C完整的次数。",
            "aggregate_mean": "所有均值先图片内平均、楼内图片平均、再楼等权；本大台账数值保留6位小数，精确事件未降精度。",
            "renamed_metrics": names,
        },
        "loow": {
            "removal": "删所有A/B/C含某人的事件，保持剩余原团队和类别，重新楼等权；不是删小团队，也不是新人员验证。",
            "retained3b": "只对删人后仍有至少3个有限质量建筑的子集给效应范围；不足支持次数另列。", "base/retained": "删除前/后真实支持或指标。",
            "class_history_workers": "该分类历史已知人员类规模；删人剩余数不是新类别训练。", "support_ledger": "≥3楼且≥12尝试事件方做LOOW，未入选原因保留，无效果符号门槛。",
        },
        "columns_by_file": dictionaries,
    }
    (args.out / "FIELD_DICTIONARY.json").write_text(json.dumps(dictionary, ensure_ascii=False, indent=2)+"\n")
    receipt = dict(schema="compact_block_evidence_v1", utc=datetime.now(timezone.utc).isoformat(), source_code_sha256=sha(__file__),
                   fixed_highlights=len(definitions), checks=checks, source_hashes=inputs, outputs=outputs,
                   total_compressed_table_bytes=sum(o["bytes"] for o in outputs), precision="Only all-exact aggregate floating values rounded to6 decimals; event/LOOW numeric values retain original exported precision.",
                   exclusions="Full flow states, geometries, all-distance matrices and non-highlight per-person LOOW rows excluded; all exact stratum and LOOW support decisions retained.")
    (args.out / "COMPACT_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+"\n")
    (args.out / "README_ZH.md").write_text("""# 类别块精简证据

本目录保留固定13个发现说明层在发现及冻结复查中的**全部事件**，并完整保留未入选的具体类别方向概要。没有按效果、p值或失败状态筛去记录。

## 文件

- `01_highlight_events.csv.gz`：全部说明层事件。A/B/C团队、参考、分数、完整／缺失状态、换人规模、来源／历史Q限制、类内／类间距离与C−B结构方向。可从这些事件重新算全部13层的均值、事件p10和失败率。
- `02_all_exact_strata.csv.xz`：所有方法×域×出入人数×n×m，以及难度细分和四种来源/Q子集；37个关键字段。以6位小数保存聚合指标；每项关键几何指标的有限支持另列。XZ是无损压缩，可由pandas直接读取或Python标准库lzma解压，无新增依赖。
- `03_loow_stratum_summary.csv.gz`：全部通过支持门槛的删人层概要和覆盖收缩。
- `04_highlight_loow_person.csv.gz`：固定13层所有已执行的具体人员删除结果，包括符号反转与删后不足3楼。
- `05_loow_support_ledger.csv.gz`：全部考虑过的删人方向层、支持与是否执行，不按效果删层。
- `FIELD_DICTIONARY.json`：字段含义、压缩支持计数顺序和指标原名。
- `COMPACT_RECEIPT.json`：来源hash、导出行数、精确请求成员一致检查、输出hash和实际大小。

## 由代码重建

分类标签、INPUT_SNAPSHOT、SPLIT与两阶段BLOCK_SPEC均使用主包中冻结版本，不从原始导出重新加工。按主包复现说明先恢复冻结融合运行时及原始仓库索引输入。

1. 用 `design_blocks.py --snapshot ... --split ... --labels ... --labels ... --spec BLOCK_DISCOVERY_SPEC.json --out DISCOVERY_BLOCK_REQUESTS.json.gz` 重建发现请求，验证同理使用 `BLOCK_VALIDATION_SPEC.json`。请求内每event含精确A/B/C人员、公共成员、出入块和team_key。生成规则／种子和原完整请求hash保留；缺机会不是补人或补零。
2. 用冻结 `fusion_runner.py` 对请求实算，再用 `summarize_blocks.py` 指定requests、runs、两份labels、历史features、snapshot、split、phase，生成原完整逐事件表。程序逐项核对人员、类别构成、参考、人数和团队键。
3. 用 `block_specific_findings.py` 生成全部精确层与删人敏感性；用 `report_block_highlights.py` 原封不动应用固定13定义；运行 `compact_block_evidence.py` 得到本目录。所有CLI完整参数可见主包脚本/对应receipt，运行时依赖由主包requirements固定。
4. 本次精简程序再次把所有保留事件的公共／出／入成员与原请求逐项核对，且按团队键保存了联合人员摘要hash到receipt；主表数值CSV再次读回后校验缺失、类型与精度。代表可视化案例另外独立保存精确人员和最终几何。

不同团队／事件不等于独立图片或人员；均值按图片、建筑层次计算。p10是配对事件差值的低尾；评分失败不补零。来源匹配与Q接近没有机会的情况仍保留在相关汇总，不把缺机会当低能力。困难域来自已有难度复核，不能据此声称新图自动采集前的选人成功。
""", encoding="utf-8")
    print(json.dumps({k: v for k, v in receipt.items() if k not in ["source_hashes"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
