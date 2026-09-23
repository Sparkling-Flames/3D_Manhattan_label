"""把已审计的共识先行数值结果接成只读离线复核页。"""

import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from .consensus_region_20260923 import centroid, compare_masks, wall_mask
from tools.label_studio.panorama_studio.geometry import analyze

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "analysis_results/consensus_research_20260923"
OUTPUT = ROOT / "analysis_results/consensus_visual_review_20260923"
ASSETS = Path(__file__).parent
VERSION = "consensus_research_20260923_v1"


def screening(rows, cluster_dir):
    """多通道召回；分簇证据只复用点集完全匹配的当前作答。无自动排除。"""
    pointsets = {p['id']: p for p in json.load(gzip.open(cluster_dir / 'pointsets.json.gz', 'rt', encoding='utf-8'))}
    memberships = json.loads((cluster_dir / 'memberships.json').read_text(encoding='utf-8'))
    clusters = defaultdict(list)
    for group in memberships:
        if group['variant'] != 'shared_x':
            continue
        if not (len(group['ids']) == len(group['labels']) == group['N']):
            raise ValueError('cluster_schema_drift')
        sizes = Counter(group['labels'])
        for cid, label in zip(group['ids'], group['labels']):
            clusters[cid].append({'method': group['method'], 'size': sizes[label], 'N': group['N'], 'label': label})
    counts = defaultdict(Counter)
    for row in rows:
        if row['pairs_shared_x'] is not None:
            counts[(row['image_id'], row['raw_condition'])][len(row['pairs_shared_x'])] += 1
    result = {}
    for row in rows:
        cid, pairs = row['canonical_annotation_id'], row['pairs_shared_x']
        cues, details = [], []
        if row['known_wrong']:
            cues.append('known'); details.append('已有明确错标记录')
        old = pointsets.get(cid)
        match = (old is not None and pairs is not None
                 and np.array_equal(old['raw_effective_points'], row['effective_points_1024x512'])
                 and np.array_equal(np.asarray(old['shared_x_points'])[old['pairs_zero_based']], pairs))
        evidence = clusters[cid] if match else []
        if any(c['size'] == 1 for c in evidence):
            cues.append('singleton'); details.append('共享x历史分簇中存在单人簇（少数解释也可能合理）')
        if any(1 < c['size'] <= 2 and c['N'] >= 6 for c in evidence):
            cues.append('small_cluster'); details.append('共享x历史分簇中存在二人小簇（至少6份作答的图）')
        geometry = None
        if pairs is None:
            cues.append('pairing'); details.append('当前有效点尚无可用配对')
        else:
            freq = counts[(row['image_id'], row['raw_condition'])]
            if sum(freq.values()) >= 3 and freq[len(pairs)] < max(freq.values()):
                cues.append('count'); details.append(f'角点对数 {len(pairs)}，同图同条件分布 {dict(sorted(freq.items()))}；非众数只作提示')
            payload = {'width': 1024, 'height': 512, 'coordinate_mode': 'pixels', 'ordered_pairs': [
                {'source_pair_id': str(i), 'top': dict(zip(('x', 'y'), p[0])), 'bottom': dict(zip(('x', 'y'), p[1]))}
                for i, p in enumerate(pairs)]}
            try:
                geometry = analyze(payload, compute_fit=False)['raw']
            except ValueError as exc:
                geometry = {'surface_valid': False, 'issues': [str(exc)], 'metrics': None}
            if geometry['issues']:
                cues.append('geometry'); details.append('现有配对顺序的原始3D诊断：' + ', '.join(geometry['issues']))
            # 点击先后不是墙体连接真值；只比较无向环边，忽略起点与反向。
            links = row['links_zero_based']
            if links and len(links) >= 4:
                order = sorted(range(len(links)), key=lambda i: min(links[i]))
                edges = lambda seq: {tuple(sorted((seq[i-1], seq[i]))) for i in range(len(seq))}
                if edges(order) != edges(list(range(len(links)))):
                    cues.append('order'); details.append('当前配对环与原始点号先后环不同；点击顺序不是已确认的连接顺序')
        result[cid] = {'cues': cues, 'details': details, 'clusters': evidence,
                       'cluster_coverage': 'matched_effective_points' if evidence else 'not_covered_or_changed',
                       'geometry': geometry, 'order_basis': 'existing_pairs_shared_x; true_ring_not_verified'}
    return result


def read_csv(name):
    with (SOURCE / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def read_gzip(name, lines=False):
    with gzip.open(SOURCE / "inputs" / name, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()] if lines else json.load(stream)


def numeric(value):
    return None if value in (None, "") else float(value)


def compact_quality(row):
    if row is None:
        return None
    result = {key: row[key] for key in ("status", "reason", "manual_gt_changed", "known_wrong", "imputed_point")}
    for key in ("iou", "erp_dx_px", "dy_px", "erp_distance_px", "circular_dx_px", "moment_distance", "circular_R", "gt_circular_R"):
        result[key] = numeric(row[key])
    return result


def mask_view(pairs, mode):
    if pairs is None:
        return {"status": "pairing_unavailable", "bands": None, "centroid": None}, None
    try:
        mask = wall_mask(pairs, mode=mode)
    except ValueError as exc:
        return {"status": str(exc), "bands": None, "centroid": None}, None
    present = mask.any(axis=0)
    top = mask.argmax(axis=0)
    bottom = mask.shape[0] - 1 - mask[::-1].argmax(axis=0)
    bands = [[int(top[i]), int(bottom[i])] if present[i] else None for i in range(mask.shape[1])]
    return {"status": "ok", "bands": bands, "centroid": centroid(mask)}, mask


def source_mentions(references):
    source_index = json.loads((SOURCE / "review_sources.json").read_text(encoding="utf-8"))
    candidates = []
    for item in source_index["sources"]:
        path = ROOT / item["path"]
        if path.suffix.lower() in {".json", ".csv", ".md"} and path.stat().st_size < 3_000_000:
            candidates.append((item, path.read_text(encoding="utf-8-sig", errors="replace")))
    return {iid: [{"path": item["path"], "role": item["role"], "guard": item["interpretation_guard"]}
                  for item, content in candidates if iid in content or ref["code"] in content]
            for iid, ref in references.items()}


def build(out=OUTPUT):
    rows = [r for r in read_gzip("annotations.jsonl.gz", lines=True) if r["accepted_before_new_review"]]
    if len(rows) != 3019 or len({r["canonical_annotation_id"] for r in rows}) != 3019:
        raise ValueError("accepted_snapshot_drift")
    references = read_gzip("references.json.gz")
    by_image = defaultdict(list)
    for row in rows:
        by_image[row["image_id"]].append(row)
    if set(by_image) != set(references) or len(by_image) != 259:
        raise ValueError("reference_image_mismatch")
    queues = {(r["canonical_annotation_id"], r["mode"]): r for r in read_csv("review_queue.csv")}
    quality = {(r["canonical_annotation_id"], r["mode"], r["gt_version"]): r
               for r in read_csv("individual_quality.csv")}
    if len(quality) != 3019 * 2 * 2:
        raise ValueError("quality_schema_or_count_drift")
    failures = json.loads((SOURCE / "representation_failures.json").read_text(encoding="utf-8"))
    failure_map = {(r["object"], r["mode"]): r["reason"] for r in failures if r["object"] in {x["canonical_annotation_id"] for x in rows}}
    mentions = source_mentions(references)
    screens = screening(rows, ROOT / 'analysis_results/shared_x_reanalysis_20260922')
    out.mkdir(parents=True, exist_ok=True)
    (out / "cases").mkdir(exist_ok=True)
    index = []
    available = 0
    for iid, members in sorted(by_image.items()):
        ref = references[iid]
        image_path = ROOT / ref["image_path"]
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        case = {"image_id": iid, "code": ref["code"], "image_src": "../../" + ref["image_path"].replace("\\", "/"),
                "manual_gt_changed": ref["manual_gt_changed"], "source_mentions": mentions[iid],
                "references": [], "annotations": []}
        masks = {}
        for reference in ref["references"]:
            item = {key: reference.get(key) for key in ("name", "kind", "source", "raw_points", "pairs_shared_x", "pairing_status", "reason", "pairing_basis")}
            item["views"] = {}
            for mode in ("curve", "linear"):
                view, mask = mask_view(reference.get("pairs_shared_x"), mode)
                item["views"][mode] = view
                if mask is not None:
                    masks[(reference["name"], mode)] = mask
            case["references"].append(item)
        for row in members:
            cid = row["canonical_annotation_id"]
            item = {key: row.get(key) for key in ("canonical_annotation_id", "worker_id", "raw_condition", "stage",
                    "raw_points_1024x512", "effective_points_1024x512", "pairs_shared_x", "links_zero_based",
                    "pairing_status", "pairing_review", "processing_status", "imputed_point", "imputation_provenance",
                    "known_wrong", "known_wrong_source", "review_decision", "exclusion_reason", "raw_export_path",
                    "runtime_task_id", "raw_annotation_id", "evidence")}
            item["views"] = {}
            summary = {"id": cid, "image_id": iid, "code": ref["code"], "worker": row["worker_id"],
                       "condition": row["raw_condition"], "known_wrong": row["known_wrong"],
                       "imputed_point": row["imputed_point"], "manual_gt_changed": ref["manual_gt_changed"],
                       "pairing_status": row["pairing_status"], "modes": {}}
            summary['screening'] = {k: v for k, v in screens[cid].items() if k != 'geometry'}
            item['screening'] = screens[cid]
            for mode in ("curve", "linear"):
                view, mask = mask_view(row.get("pairs_shared_x"), mode)
                item["views"][mode] = view
                q = queues.get((cid, mode))
                if q is None or (mask is None) != (q["status"] == "not_evaluable"):
                    raise ValueError(f"queue_mask_mismatch:{cid}:{mode}")
                metrics = {}
                for gt in ("gt_original", "gt_revised"):
                    original = quality[(cid, mode, gt)]
                    metrics[gt] = compact_quality(original)
                    reference_mask = masks.get((gt, mode))
                    if mask is not None and reference_mask is not None:
                        actual = compare_masks(mask, reference_mask)
                        if original["status"] != "ok" or any(abs(actual[k] - float(original[k])) > 1e-9
                                 for k in ("iou", "erp_dx_px", "dy_px", "erp_distance_px", "circular_dx_px", "moment_distance")
                                 if actual[k] is not None):
                            raise ValueError(f"metric_mismatch:{cid}:{mode}:{gt}")
                queue = None if q["status"] == "not_evaluable" else {key: q[key] for key in ("reference_count", "expected_reference_count",
                         "reference_coverage_complete", "peer_count", "closest_reference", "closest_reference_iou",
                         "closest_peer_id", "closest_peer_iou", "joint_distance_rank", "reason")}
                if queue is not None:
                    queue["reference_ious"] = json.loads(q["reference_ious"])
                    queue["peer_ious"] = json.loads(q["peer_ious"])
                    for key in ("closest_reference_iou", "closest_peer_iou", "joint_distance_rank"):
                        queue[key] = numeric(queue[key])
                    for key in ("reference_count", "expected_reference_count", "peer_count"):
                        queue[key] = int(queue[key])
                item.setdefault("queue", {})[mode] = queue
                item.setdefault("quality", {})[mode] = metrics
                summary["modes"][mode] = {"rank": None if queue is None else queue["joint_distance_rank"],
                    "reference_count": None if queue is None else queue["reference_count"],
                    "peer_count": None if queue is None else queue["peer_count"],
                    "failure": view["status"] if mask is None else None,
                    "quality": metrics}
                if mask is not None:
                    available += 1
                elif failure_map.get((cid, mode)) not in (None, view["status"]):
                    raise ValueError(f"failure_reason_mismatch:{cid}:{mode}")
            case["annotations"].append(item)
            if any(v['failure'] for v in summary['modes'].values()):
                summary['screening']['cues'].append('representation')
                summary['screening']['details'].append('至少一种墙带表示不可评价')
            if any(v['rank'] is not None and v['rank'] >= .25 for v in summary['modes'].values()):
                summary['screening']['cues'].append('iou')
                summary['screening']['details'].append('至少一种表示同时远离最近参考和独立同行（IoU≤0.75）')
            index.append(summary)
        (out / "cases" / f"{iid}.js").write_text("window.REVIEW_CASE=" + json.dumps(case, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    manifest = {"schema": "consensus_visual_review_v1", "contract_version": VERSION, "accepted": len(index),
                "images": len(by_image), "modes": ["curve", "linear"], "representable_rows": available,
                "quality_rows": len(quality), "source": "analysis_results/consensus_research_20260923",
                "notice": "只读研究复核；排序不是无效裁决，输出裁决不自动应用"}
    manifest['screening'] = {'schema': 'annotation_screening_v1', 'candidate_count': sum(bool(r['screening']['cues']) for r in index),
        'priority_count': sum(bool(set(r['screening']['cues']) & {'known', 'pairing', 'geometry', 'representation'}) for r in index),
        'by_channel': dict(Counter(c for r in index for c in r['screening']['cues'])),
        'cluster_covered': sum(bool(r['screening']['clusters']) for r in index),
        'guard': '通道取并集且可重叠；角点数、单人/二人簇、顺序、几何失败均非无效裁决；未命中不等于正确。3D仅验证现有配对环，未执行曼哈顿优化。'}
    (out / "data.js").write_text("window.REVIEW_DATA=" + json.dumps({"manifest": manifest, "rows": index}, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    (out / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "README.md").write_text("""# 全历史标注区域与质心复核

双击 [index.html](index.html) 在 Chrome 或 Edge 打开；保持本目录位于仓库内，因为原图及现有仪表盘样式通过仓库相对路径读取。无需服务器或网络。

- 3019份当前起点、259图；质心散点保持全量。默认队列为角点数量、现有配对环3D诊断、原始点号顺序线索、单人/二人簇、配对/墙带失败、既有错标与IoU辅助通道的去重并集。通道数与覆盖见MANIFEST.json。目标是筛查非墙角、乱标等明显无效标注，范围不同、单人簇与机器失败不能自动排除。未命中也不等于正确。Manual、OOS、Semi可分开筛。
- screening字段合同：cues为可重叠通道，details为说明，clusters记录历史shared_x完整链接/亲近度的簇大小与图内N；仅在有效点逐点匹配时复用。cluster_coverage明确缺失，geometry为既有Studio原始射线重建（不运行曼哈顿优化），order_basis表明真实环序未验证。角点数量在同图同条件至少3份时比较非众数；单人簇和至少6份图中的二人小簇独立召回。顺序线索只比较无向环边，不把点击次序当真实连接。
- 墙带及质心预览由 `consensus_region_20260923.wall_mask/centroid` 生成，1024×512等效像素。原始点、既有裁决后的点、共享x配对分开显示。圆周方向及R单列，不把低R方向差读作整体平移。
- `joint_distance_rank`、垂直/圆周/近质心专题只用于安排审核。既有case14明确错标单列；同图提及与作答裁决分开。人工选择不会改原始导出、3019份计算起点或正式资格。
- 裁决先保存在此浏览器的localStorage。请用“导出本轮裁决JSON”备份；导入前检查合同版本与canonical ID。换浏览器或清理站点数据前先导出。
- 导出字段合同：顶层 `schema=consensus_visual_review_decisions_v1`、`contract_version`、`exported_at`、`source`、`decisions`；后者以 canonical ID 为键，每项保存 `verdict`（retain/invalid/gt_scope/representation/pending）、`comment`、`image_id`、`worker_id`、`condition`、`code`、`updated_at`。导入只接受本合同版本、已知 canonical ID 与合法结论。
- 页面依赖仓库内259张原图，不能单独复制本目录当作便携包。本轮没有生成ZIP。

复建：`python -m tools.thesis_main.analysis.build_consensus_visual_review_20260923`。来源数值与方法边界见 `../consensus_research_20260923/README.md`。
""", encoding="utf-8")
    for name in ("index.html", "review.css", "review.js"):
        (out / name).write_bytes((ASSETS / ("consensus_visual_" + name)).read_bytes())
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
