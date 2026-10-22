#!/usr/bin/env python3
"""Check completed deliverable files and publish their actual index.

This is serialization/association verification, not a repeated research audit.
Only existing files are indexed. Large endpoint geometry stays in its source
batch; selected mechanism geometry is saved by the adjacent case study.
"""
from __future__ import annotations

import csv
import gzip
import json
import platform
from importlib.metadata import version

import pandas as pd

from build_configuration_distributions import HERE, METRICS, SOURCE_MAIN, save, sha, js


def metric_guide():
    desc = {
        "B8L2": ("分（0—100）", "较大对应冻结参考综合表现较好", "冻结主工作指数；未改评分、权重或参考。"),
        "D10": ("分（0—100）", "较大对应冻结参考综合表现较好", "仅方向尺度8°→10°的冻结敏感性；不改变几何。"),
        "iou_2d": ("0—1", "较大表示底面参考重叠较好", "底面footprint IoU。"),
        "IoU3D100": ("分（0—100）", "较大表示条件三维代理重叠较好", "角点均高棱柱IoU代理×100；不是真实连续实体体积。"),
        "S_bottom_deg": ("度", "较小表示底边更接近参考", "参考底面边界的球面对称距离。"),
        "dir": ("度", "较小表示自身更正交", "作答自身最优正交轴下边长加权RMS残差；不是与GT的整体朝向误差。"),
        "Hmean": ("无量纲", "较小表示沿周长均高更接近参考", "沿周长平均高度比的绝对残差。"),
        "Hcenter": ("无量纲", "较小表示去均值局部高度轮廓更接近参考", "去均值后的近邻高度轮廓残差；底面定位也会影响它。"),
        "omission": ("参考面积比例", "较小表示参考区域遗漏较少", "参考未覆盖面积/参考面积；不等同已裁定的必要语义结构遗漏。"),
        "extension": ("参考面积比例", "需联系真实范围与参考", "候选超出参考面积/参考面积；参考外真实细节不自动判错。"),
        "nodes": ("节点数", "无固定优劣方向", "原融合选中输出节点数；不是语义正确性。"),
        "fusion_turn_n": ("转折数", "无固定优劣方向", "有效footprint节点数减去转角≤5°近共线节点，沿用旧response代码。"),
        "fusion_short_turn_edges": ("边数", "无固定优劣方向", "边长/周长<0.04且两端转角均≥15°；是几何表达，不代替语义裁定。"),
        "fusion_redundancy_n": ("节点数", "无固定优劣方向", "有效footprint中转角≤5°近共线节点。"),
        "geometry_area_h2": ("相机高度平方 h²", "无固定优劣方向", "重建底面面积。"),
        "height_mean_h": ("相机高度 h", "无固定优劣方向", "重建角点高度均值；不是沿周长均高。"),
        "height_min_h": ("相机高度 h", "无固定优劣方向", "重建角点高度最小值。"),
        "height_max_h": ("相机高度 h", "无固定优劣方向", "重建角点高度最大值。"),
        "height_mean_ratio": ("无量纲", "需看偏离1的大小与方向", "质量引擎沿周长均高/参考沿周长均高。"),
        "failure": ("0/1；格均值为比例", "较小表示完整可评失败较少", "1-complete_evaluable；包括below_four、no_connection、invalid_floor，不涵盖所有不准确。"),
        "recorded_time_total_seconds": ("秒", "记录时间成本", "全员记录完整、正总时且单一time_source_kind的原记录总和；不同来源不合并；不是新测生产墙钟。"),
    }
    for c in ["centroid_x_h", "centroid_z_h", "bounds_min_x_h", "bounds_max_x_h", "bounds_min_z_h", "bounds_max_z_h"]:
        desc[c] = ("相机高度 h", "无固定优劣方向", "继承重建底面坐标/范围标量；与同图参考或另一团队比较。")
    for c in ["top_y_mean_px", "bottom_y_mean_px"]:
        desc[c] = ("ERP像素", "无固定优劣方向", "融合顶界/底界的图像y坐标均值；不能直接称为质量改善。")
    for c in ["ref_node_recall_5", "ref_node_recall_9", "ref_edge_recall_5", "ref_edge_recall_9"]:
        desc[c] = ("0—1", "较大表示冻结参考节点/邻接覆盖更高", "5°或9°配对诊断；不是原答9°/12°分簇阈值，也不改融合内部对应参数。")
    for c in ["diag_corner_recall_05", "diag_wall_coverage_03", "diag_wall_coverage_05"]:
        desc[c] = ("0—1", "几何局部覆盖诊断", "直接保留既有endpoint诊断，不赋予新增语义正确性。")
    for c in ["minimum_support", "selected_support_min", "identity_groups_n", "unselected_groups_n", "minority_observations_n", "half_vote_nodes"]:
        desc[c] = ("继承票数/节点或组数", "机制量，无固定优劣方向", "原冻结融合票数、对应组及门槛诊断，未调整算法。")
    for c in ["below_four", "location_unresolved", "order_tied", "connection_available"]:
        desc[c] = ("0/1；格均值为比例", "机制/失败状态", "直接保留原融合或可评性状态；与score_status一起解释。")
    rows = []
    for c in METRICS + ["recorded_time_total_seconds"]:
        unit, direction, definition = desc[c]
        rows.append(dict(metric=c, unit=unit, interpretation=direction, definition_zh=definition,
                         denominator="本指标非缺失有限值团队数valid_n；时间另按同一time_source_kind分层",
                         source="inherited_native_endpoint" if not c.startswith("fusion_") else "inherited_geometry_rederived_with_frozen_response_expression"))
    assert len(rows) == 46
    save(pd.DataFrame(rows), "METRIC_FIELD_GUIDE.csv")


def inspect_csv(path):
    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        n = 0
        for row in reader:
            assert len(row) == len(header), (path.name, n, len(row), len(header))
            n += 1
    return n, len(header)


def main():
    metric_guide()
    expected = {
        "TEAM_MEMBERS.csv.gz": 310458, "PANEL_TEAMS.csv.gz": 310464,
        "LOBO_LABELS_USED.csv.gz": 5456, "PANEL_CONFIGURATION_CENSUS.csv.gz": 13406,
        "TEAM_CONFIGURATION_LINKS.csv.gz": 941248,
        "CONFIGURATION_OVERVIEW_manual.csv.gz": 10094, "CONFIGURATION_OVERVIEW_semi.csv.gz": 3312,
        "CONFIGURATION_DISTRIBUTIONS_manual.csv.gz": 464324, "CONFIGURATION_DISTRIBUTIONS_semi.csv.gz": 152352,
        "ENDPOINT_OUTCOMES_manual.csv.gz": 213442, "ENDPOINT_OUTCOMES_semi.csv.gz": 97016,
        "CASE_7y13_BACKGROUND_ADDITION_PAIRS.csv.gz": 924,
    }
    rows = []
    for path in sorted(HERE.iterdir()):
        if not path.is_file() or path.name.endswith(".partial") or path.name in ["FILE_INDEX.csv", "DELIVERY_COMPLETE.json"]:
            continue
        row = dict(path=path.name, bytes=path.stat().st_size, sha256=sha(path), rows=None, columns=None,
                   stage="current_reaggregation_or_presentation", status="exists")
        if path.name.endswith((".csv", ".csv.gz")):
            n, columns = inspect_csv(path)
            row.update(rows=n, columns=columns, status="full_CSV_rows_and_gzip_footer_checked" if path.name.endswith(".gz") else "full_CSV_rows_checked")
            if path.name in expected:
                assert n == expected[path.name], (path.name, n, expected[path.name])
        if path.name.startswith("STAGE01"):
            row["stage"] = "preserved_initial_checkpoint_current_completion_in_DELIVERY_COMPLETE"
        rows.append(row)
    assert set(expected) <= {r["path"] for r in rows}
    index = save(pd.DataFrame(rows), "FILE_INDEX.csv")
    js("DELIVERY_COMPLETE.json", dict(status="complete", source_main=SOURCE_MAIN, underlying_data="true_v2",
                                      source_endpoint_batches=17, unique_inherited_endpoints=310458, new_fusion_calls=0,
                                      conditional_member_panels=336, per_panel_registered_member_sets=924,
                                      label_supported_configuration_cells=13406, metric_distribution_rows=616676,
                                      team_method_tier_panel_links=941248, full_actual_CSV_read_to_EOF=True,
                                      gzip_footer_and_ragged_rows_checked=True, exact_key_table_row_counts=expected,
                                      singleton_dispersion_not_estimated=True, time_sources_separate=True,
                                      source_domain_full_member_enumeration_claim=False, file_index=index,
                                      python=platform.python_version(), versions={p: version(p) for p in ["pandas", "numpy", "matplotlib"]},
                                      code_sha256={p: sha(HERE / p) for p in ["build_configuration_distributions.py", "summarize_and_render.py", "finalize_files.py"]}))
    print(json.dumps(dict(status="complete", indexed_files=len(rows), total_indexed_bytes=sum(r["bytes"] for r in rows), index=index), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
