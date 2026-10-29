#!/usr/bin/env python3
"""Extract already frozen location/scale summary cells; no research recomputation.

Only reads ALL_STAGES_DIRECTION_N_M_SUMMARY.csv.gz and copies exact strings.
No endpoint loading, fusion, scoring, fitting, or fresh event aggregation occurs.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path


STATS = ["mean_image", "median_image", "p10_image", "p90_image", "valid_images",
         "positive_images", "negative_images", "near_zero_images", "mean_building",
         "valid_buildings", "positive_buildings"]

METRICS = [
    ("geometry_centroid_distance", "底面质心位移", "h", False),
    ("geometry_log_area_distance", "底面积绝对对数比", "dimensionless", False),
    ("geometry_area_h2", "底面积", "h^2", True),
    ("height_mean_h", "平均总高度", "h", True),
    ("geometry_pair_angle", "成对角距（可得性旁证）", "degree", False),
    ("geometry_bev_distance", "成对 BEV 距离（可得性旁证）", "h", False),
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    relative = "stage02_comparison/abc_integrated/ALL_STAGES_DIRECTION_N_M_SUMMARY.csv.gz"
    source = root / relative
    source_sha = sha(source)
    csv_path = root / "stage05_synthesis/LOCATION_SCALE_READING.csv"
    txt_path = root / "stage05_synthesis/LOCATION_SCALE_READING_ZH.txt"
    if csv_path.exists() or txt_path.exists():
        raise FileExistsError("Preserve existing supplements; choose a new version explicitly.")

    with gzip.open(source, "rt", encoding="utf-8", newline="") as handle:
        records = list(csv.DictReader(handle))
    common = dict(method="TARGET_DSTRUCT_K3", scope="primary", m="7",
                  axis="hard_turn_rank_asc", rank_direction="2/3->3/3",
                  stage_scope="combined_union")
    selected = {}
    for n in (20, 14):
        filters = {**common, "n": str(n)}
        matches = [(i, r) for i, r in enumerate(records, 1)
                   if all(r[k] == v for k, v in filters.items())]
        assert len(matches) == 1, filters
        selected[n] = (*matches[0], filters)

    output = []
    for n in (20, 14):
        record_number, row, filters = selected[n]
        old_filters = {**filters, "stage_scope": "existing_only"}
        old = [r for r in records if all(r[k] == v for k, v in old_filters.items())]
        assert len(old) == 1
        for metric, title, unit, scalar in METRICS:
            names = ["same_origin_within", "same_origin_cross", "same_origin_gap"]
            if scalar:
                names += ["BA", "CA", "CB"]
            for comparison in names:
                prefix = metric + "_" + comparison
                source_fields = {stat: prefix + "_" + stat for stat in STATS}
                values = {stat: row[field] for stat, field in source_fields.items()}
                assert all(old[0][field] == row[field] for field in source_fields.values())
                if comparison in ("BA", "CA", "CB"):
                    expression = comparison[0] + " - " + comparison[1]
                    support = "Only the named endpoint pair must have this scalar; not restricted to joint ABC support."
                    meaning = "positive = scalar increase; negative = scalar decrease"
                else:
                    pair_metric = not scalar
                    expressions = {
                        "same_origin_within": "distance(A,B)" if pair_metric else "abs(B-A)",
                        "same_origin_cross": "distance(A,C)" if pair_metric else "abs(C-A)",
                        "same_origin_gap": "distance(A,C)-distance(A,B)" if pair_metric else "abs(C-A)-abs(B-A)",
                    }
                    expression = expressions[comparison]
                    support = ("AB and AC distances both present before averaging; no direction vector implied."
                               if pair_metric else "BA, CA and CB scalar differences all present before averaging.")
                    meaning = ("positive = cross-class magnitude exceeds same-class magnitude"
                               if comparison == "same_origin_gap" else "nonnegative change magnitude; not a quality gain")
                output.append({
                    **filters, "metric_id": metric, "metric_zh": title, "unit": unit,
                    "comparison": comparison, "expression": expression,
                    "support_rule": support, "sign_meaning": meaning,
                    **values,
                    "registered_events": row["events"], "registered_images": row["images"],
                    "registered_buildings": row["buildings"],
                    "source_path": relative, "source_sha256": source_sha,
                    "source_record_1based": str(record_number),
                    "source_filter_json": json.dumps(filters, ensure_ascii=False, sort_keys=True),
                    "source_field_prefix": prefix,
                    "source_fields_json": json.dumps(source_fields, ensure_ascii=False, sort_keys=True),
                    "existing_only_values_identical": "true",
                    "positive_threshold": "1e-9", "new_research_computation": "false",
                })
    assert len(output) == 48
    for item in output:
        original = records[int(item["source_record_1based"]) - 1]
        assert all(item[s] == original[f] for s, f in json.loads(item["source_fields_json"]).items())
    with csv_path.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reread = list(csv.DictReader(handle))
    assert reread == output

    def fmt(value: str) -> str:
        return "不可评/未保存" if value == "" else f"{float(value):.9f}"

    lines = [
        "HOHONET v2.1：位置与尺度的已有结果补充阅读",
        "日期：2026-10-29；普通 Manual 优先；本补充独立于已冻结主 PDF。",
        "",
        "一、范围与读法",
        "仅转录既有 ALL_STAGES_DIRECTION_N_M_SUMMARY.csv.gz；未新增融合、评分、人员分类、团队或事件汇总。",
        "方法为 TARGET_DSTRUCT_K3；scope=primary；axis=hard_turn_rank_asc；rank_direction=2/3->3/3；stage_scope=combined_union。",
        "这是按各留楼外折历史 hard_turn 排序的中类→高类，不是统一的历史 Q 高低方向，也不把原始 class_id 当作跨折相同角色。",
        "A=D+X，B=D+Y，C=D+Z；W 为同类换人相对原队 A 的幅度，C_A 为跨类换人相对同一原队 A 的幅度，G=C_A-W。",
        "两项距离使用同时存在的 AB、AC 值；面积和高度的 W/C_A/G 要求 BA、CA、CB 三个差都存在。",
        "下面有向 C−A 使用 AC 自身可评支持，分母比共同三臂幅度多一图；不能直接把这两种支持混为一组或从均值相减恢复另一项。",
        "图片等权前，先平均同一 XYZ 块中的背景，再平均块、图片池；建筑等权均值再对各楼图片均值平均。",
        "正图/负图在既有汇总中以 ±1e-9 划分，只是数值符号容差，不是已验证的重要变化阈值。",
        "",
        "二、单位与含义",
        "h 指相机到地面的归一高度，计算时 h=1。距离和高度变化以 h 表示，底面积变化以 h² 表示；这些数字不是已标定的米或平方米。",
        "质心距离是两个底面多边形质心在 x/z 平面的欧氏距离；表示移动多少，没有保存到本表的东/西或 x/z 方向。",
        "log-area 距离 = |ln(area_2/area_1)|，无量纲，只表示比例尺度差；它本身没有面积增减方向。",
        "geometry_area_h2 是底面多边形面积。height_mean_h 是从入选上下边界点估计的各角总高度的均值（以 h 归一）。",
        "G>0 仅表示跨类变动幅度超过同类换人；面积/高度增加、位移增大均不能直接解释为升质。质量仍需另读 Q 分项与冻结参考。",
    ]
    for n in (20, 14):
        rec, row, _ = selected[n]
        section = "三" if n == 20 else "四"
        lines.extend(["", f"{section}、n={n} / m=7：同一原队 A 的变化幅度",
                      f"登记 {row['events']} 事件、{row['images']} 图、{row['buildings']} 楼；此方向 combined_union 与 existing_only 相同，本轮没有新增加该方向事件。"])
        for metric, title, unit, _ in METRICS[:4]:
            w = metric + "_same_origin_within"
            c = metric + "_same_origin_cross"
            g = metric + "_same_origin_gap"
            lines.append(
                f"{title} [{unit}]：W={fmt(row[w+'_mean_image'])}；C_A={fmt(row[c+'_mean_image'])}；G={fmt(row[g+'_mean_image'])}。"
                f"共同可评 {row[g+'_valid_images']} 图/{row[g+'_valid_buildings']} 楼；G 正/负/近零图="
                f"{row[g+'_positive_images']}/{row[g+'_negative_images']}/{row[g+'_near_zero_images']}。"
                f"建筑等权 G={fmt(row[g+'_mean_building'])}；正楼 {row[g+'_positive_buildings']}/{row[g+'_valid_buildings']}。")
        lines.append("有向变化（AC 自身可评支持）：")
        for metric, title, unit, _ in METRICS[2:4]:
            p = metric + "_CA"
            lines.append(
                f"{title} C−A [{unit}]：图片等权均值={fmt(row[p+'_mean_image'])}；中位数={fmt(row[p+'_median_image'])}；"
                f"正/负/近零图={row[p+'_positive_images']}/{row[p+'_negative_images']}/{row[p+'_near_zero_images']}，"
                f"可评 {row[p+'_valid_images']} 图/{row[p+'_valid_buildings']} 楼。"
                f"建筑等权均值={fmt(row[p+'_mean_building'])}；正楼 {row[p+'_positive_buildings']}/{row[p+'_valid_buildings']}。")
        lines.append(f"精确来源：摘要数据记录第 {rec} 行（不含表头）；CSV 同时保存全部原始十进制字符串、字段名和筛选条件。")
    lines.extend([
        "",
        "五、这些数字支持的解释",
        "n20/m7：质心和对数面积的跨类额外幅度为正，但只有 40/70 和 39/70 图为正，说明是温和且不一致的区分。高度额外幅度在 49/70 图为正；有向 C−A 高度在 55/71 图增加。",
        "n20/m7：底面积 C−A 的图片均值为正，但 42/71 图面积减小、仅 29/71 图增大；建筑均值亦为正，却只有 8/21 楼为正。不能用总体均值写成普遍扩张。",
        "n14/m7：质心额外幅度均值虽为正，但 44/83 图为负（正图 39/83）；对数面积只有 42/83 图为正。高度额外幅度为正的图为 51/83。",
        "n14/m7：有向面积 C−A 为负且 50/84 图缩小；高度为正且 56/84 图增加。与 n20/m7 的面积均值不同，显示团队人数和原队背景会改变响应。两格图片和团队支持不同，这不是控制全部其他条件后的纯 n 效应。",
        "这些结果补足人员分类对位置与尺度的实际响应证据，不要求所有几何量或图片同向，也不据此宣称结构类别的作用独立于历史质量。",
        "",
        "六、旧成对几何的缺失边界",
        "n20/m7 此方向的 geometry_pair_angle、geometry_bev_distance 同 A 汇总均为缺失，可评图/楼为 0。缺失值没有填 0。",
        "该部分旧事件的 centroid 与 log-area 在既有整合阶段已用有效端点质心/面积标量重建；角距和 BEV 边界距离不能由 Q、质心或面积代替。此次只读已保存结果，没有重新恢复多边形或重跑成对几何。",
        "不能笼统说旧成对几何全缺失：n14/m7 此方向已有角距与 BEV 的同 A 结果，均可评 83 图/21 楼。",
        "n14/m7：角距额外幅度为 +0.208254398 度（53/83 图为正）；BEV 额外幅度为 +0.013614684 h（45/83 图为正）。完整均值、分位数、分母均在本 CSV 原样转录。",
        "",
        "七、回查与保存",
        f"摘要来源：{relative}",
        f"摘要文件 SHA256：{source_sha}",
        "字段定义/既有汇总代码：stage02_comparison/summarize_new_and_existing_abc.py（enrich、aggregate、read_old_scalar_reconstructions）。",
        "端点几何定义：stage06_reproduction/inputs_and_source/repo/research/workers/personnel_global_composition_20261021/composition/run_endpoints.py（enrich）。",
        "LOCATION_SCALE_READING.csv 共 48 行，每行保留 11 个既有统计量；528 个单元格已逐项回连源记录、源字段，字符串完全一致。",
        "TXT 为九位小数显示；精确原值以 CSV 为准。CSV 中数值留空且 valid_images=0 代表未有可评结果，不代表结果为零。",
        f"CSV SHA256：{sha(csv_path)}",
        "提取代码：code/extract_location_scale_reading.py。旧文件与旧报告均未改动。",
        "",
    ])
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    assert sha(source) == source_sha
    print(json.dumps({"rows": len(output), "exact_source_cells": len(output)*len(STATS),
                      "source_records": {str(n): selected[n][0] for n in selected},
                      "csv": str(csv_path), "csv_sha256": sha(csv_path),
                      "txt": str(txt_path), "txt_sha256": sha(txt_path),
                      "new_research_computation": False}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
