from __future__ import annotations

import argparse
import csv
import html
import json
import math
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.thesis_main.analysis.full_uncertainty.full_uncertainty_common import cyclic_rmse
from tools.thesis_main.registry.perturbation_operators import (
    canonical_corners_to_runtime_pairs,
    ls_keypoints_to_canonical_corners,
)


ROOT = REPO_ROOT
V5 = ROOT / "analysis_results/full_uncertainty_data_mining_20260821_v5"
DEFAULT_OUT = V5 / "可视化"
IMAGE_DIR = ROOT / "data/mp3d_layout/img_v"
SEMI_IMPORT = ROOT / "import_json/calibration_c1_v3_1_formal/c1_v3_1_semi_import_zh.json"
GT_IMPORT = ROOT / "import_json/groudTruth_458_tasks_import_from_updated_gt_20260701.json"
PALETTE = ("#36c5f0", "#ff647c", "#79d46c", "#c184f4", "#ffb84d", "#5ad1b8", "#f27c48", "#8aa7ff")


METRIC_INFO = {
    "delta_shannon_entropy": ("Shannon 熵变化", "Semi 的 Shannon 熵减去 Manual 的 Shannon 熵；负值表示收敛，正值表示扩张"),
    "manual_shannon_entropy": ("Manual Shannon 熵", "按 Manual 各聚类支持数换算概率后计算 −Σp×ln(p)"),
    "semi_shannon_entropy": ("Semi Shannon 熵", "按 Semi 各聚类支持数换算概率后计算 −Σp×ln(p)"),
    "manual_mode_count": ("Manual 模式数", "Manual 等量重聚类中得到的模式数量"),
    "semi_mode_count": ("Semi 模式数", "Semi 等量重聚类中得到的模式数量"),
    "edit_rate": ("编辑比例", "发生几何编辑的 Semi 记录数除以该任务 Semi 记录数"),
    "edit_rmse_median": ("编辑 RMSE 中位数", "模型初始点与最终点循环对齐后，像素 RMSE 的任务内中位数"),
    "topology_change_count": ("拓扑变化记录数", "模型初始角点数与最终角点数不同的 Semi 记录数"),
    "crowd_gt_gap_best_minus_largest": ("最佳模式相对主模式的 GT 差值", "最接近 GT 模式的 IoU 中位数减去最大支持模式的 IoU 中位数"),
    "largest_cluster_support": ("最大模式支持数", "最大聚类包含的人工标注记录数"),
    "second_cluster_support": ("第二模式支持数", "第二大聚类包含的人工标注记录数"),
    "cyclic_rmse_diagonal_normalized": ("循环对齐坐标 RMSE", "相同拓扑的两份几何循环或反向对齐后的最小坐标 RMSE，再除以全景图对角线"),
    "n_corners_left": ("左侧角点数", "左侧标注中成功规范配对的 ceiling/floor 点总数"),
    "n_corners_right": ("右侧角点数", "右侧标注中成功规范配对的 ceiling/floor 点总数"),
    "supported_replay_rate": ("重放支持多峰比例", "该任务在前缀抽样重放中被判为“有支持的多峰”的次数除以全部重放次数"),
    "k5_supported_rate": ("k=5 支持多峰比例", "每次抽取 5 份标注时判为“有支持的多峰”的重放比例"),
    "geometry_edit_rmse_px": ("几何编辑 RMSE", "模型初始点与最终人工点循环对齐后的像素 RMSE"),
    "active_time_observed_seconds": ("冻结有效操作时间", "冻结 active-time 表中 owner-valid 事件累计秒数；不使用 Lead time 回填"),
    "iou_to_gt": ("相对 GT 的 IoU", "最终布局与当前 operational GT 的交并比"),
    "result_count": ("原始结果项数", "该原始 Label Studio annotation 的 result 数组长度"),
    "revision_rmse": ("版本间循环对齐 RMSE", "同一任务同一标注者的非最终版本与最终版本循环对齐后的归一化坐标 RMSE"),
    "risk_design_score_A": ("预任务风险分数", "任务分发前冻结的图像风险设计分数 A"),
    "edge_density_proxy": ("边缘密度代理", "灰度下采样图中超过固定梯度阈值的像素比例"),
}


@dataclass
class Case:
    category: str
    title: str
    task: str
    selection_rule: str
    sources: list[str]
    metrics: dict[str, Any]
    mode: str = "standard"
    include_gt: bool = False
    focus: dict[str, Any] = field(default_factory=dict)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 v5 原图与标注点证据总览及逐案例 PNG。")
    parser.add_argument("--v5-dir", type=Path, default=V5)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--skip-png", action="store_true", help="只生成 HTML、图片资产和案例索引。")
    return parser.parse_args(argv)


def read_csv(v5: Path, name: str) -> pd.DataFrame:
    path = v5 / name
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False, dtype=str).fillna("")


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "matched", "eligible"}


def image_id(value: Any) -> str:
    return Path(str(value).split("?", 1)[0]).stem


def prediction_lookup(path: Path) -> dict[str, dict[str, Any]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {str(row.get("data", {}).get("base_task_id") or image_id(row.get("data", {}).get("image", ""))): row for row in rows}


def gt_lookup(path: Path) -> dict[str, list[dict[str, Any]]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        task = image_id(row.get("data", {}).get("image", ""))
        annotations = row.get("annotations") or []
        if annotations:
            result[task] = annotations[0].get("result") or []
    return result


def runtime_pairs(result: Any) -> list[dict[str, float]]:
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            return []
    corners, meta = ls_keypoints_to_canonical_corners(result or [])
    return canonical_corners_to_runtime_pairs(corners, int(meta.get("width") or 1024), int(meta.get("height") or 512))


def choose_cases(tables: dict[str, pd.DataFrame]) -> list[Case]:
    cases: list[Case] = []
    convergence = tables["SEMI_25_CONVERGENCE_EXPANSION_ALL_IMAGES.csv"].copy()
    convergence["delta"] = pd.to_numeric(convergence["delta_shannon_entropy"], errors="coerce")
    negative = convergence[convergence["delta"] < 0].copy()
    negative["median_distance"] = (negative["delta"] - negative["delta"].median()).abs()
    typical = negative.sort_values(["median_distance", "base_task_id"]).iloc[0]
    expansion = convergence[convergence["delta"] > 0].sort_values(["delta", "base_task_id"], ascending=[False, True]).iloc[0]
    for row, title, rule in (
        (typical, "Manual/Semi：典型收敛", "在熵下降任务中选择最接近下降幅度中位数的任务"),
        (expansion, "Manual/Semi：极端扩张", "在熵上升任务中选择 delta_shannon_entropy 最大的任务"),
    ):
        cases.append(Case("Manual/Semi 不确定性变化", title, row.base_task_id, rule,
                          ["SEMI_25_CONVERGENCE_EXPANSION_ALL_IMAGES.csv", "RAW_ANNOTATION_LEDGER_ALL_2513.csv"],
                          {key: row.get(key, "") for key in ("delta_shannon_entropy", "manual_shannon_entropy", "semi_shannon_entropy", "manual_mode_count", "semi_mode_count")}))

    proposal = tables["PROPOSAL_TASK_ANCHORING_AND_DISCOVERY.csv"].copy()
    proposal["edit"] = pd.to_numeric(proposal["edit_rate"], errors="coerce")
    retained = proposal[proposal["proposal_response_pattern"].eq("convergence_with_high_proposal_retention")].copy()
    retained["median_distance"] = (retained["edit"] - retained["edit"].median()).abs()
    retained_row = retained.sort_values(["median_distance", "base_task_id"]).iloc[0]
    revised = proposal[proposal["proposal_response_pattern"].str.contains("divergent|substantial", regex=True)].copy()
    revised["score"] = (pd.to_numeric(revised["topology_change_count"], errors="coerce").fillna(0) * 100
                        + pd.to_numeric(revised["edit_rmse_median"], errors="coerce").fillna(0))
    revised_row = revised.sort_values(["score", "base_task_id"], ascending=[False, True]).iloc[0]
    for row, title, rule in (
        (retained_row, "模型提案：高保留", "在高提案保留任务中选择编辑比例最接近该组中位数的任务"),
        (revised_row, "模型提案：大幅修正", "先按拓扑变化记录数、再按编辑 RMSE 选择修正幅度最大的任务"),
    ):
        cases.append(Case("模型预标注响应", title, row.base_task_id, rule,
                          ["PROPOSAL_TASK_ANCHORING_AND_DISCOVERY.csv", "PROPOSAL_GEOMETRY_RECORDS.csv"],
                          {key: row.get(key, "") for key in ("edit_rate", "edit_rmse_median", "topology_change_count", "delta_shannon_entropy")}))

    crowd = tables["CROWD_GT_101_GEOMETRIC_CAUSE_AUDIT.csv"].copy()
    crowd["gap"] = pd.to_numeric(crowd["crowd_gt_gap_best_minus_largest"], errors="coerce")
    minority = crowd[crowd["crowd_gt_relationship"].str.contains("nonlargest_supported_cluster_better")].sort_values(
        ["gap", "base_task_id"], ascending=[False, True]).iloc[0]
    conflict = crowd[crowd["crowd_gt_relationship"].str.contains("diffuse_all_singletons|unimodal_low_gt_alignment", regex=True)].copy()
    conflict["support"] = pd.to_numeric(conflict["largest_cluster_support"], errors="coerce").fillna(0)
    conflict_row = conflict.sort_values(["support", "base_task_id"], ascending=[True, True]).iloc[0]
    for row, title, rule in (
        (minority, "Crowd–GT：非最大支持模式更接近 GT", "在有支持的非最大模式更接近 GT 的任务中选择 GT 差值最大的任务"),
        (conflict_row, "Crowd–GT：分散分歧或低 GT 对齐", "在全部单例或低 GT 对齐任务中选择最大模式支持最弱的任务"),
    ):
        cases.append(Case("Crowd–GT 关系", title, row.base_task_id, rule,
                          ["CROWD_GT_101_GEOMETRIC_CAUSE_AUDIT.csv", "C1_CROWD_GT_CLUSTER_METRICS.CSV"],
                          {key: row.get(key, "") for key in ("crowd_gt_gap_best_minus_largest", "largest_cluster_support", "second_cluster_support")},
                          include_gt=True, focus={"condition": row.get("condition", "")}))

    dual = tables["DUAL_ANNOTATOR_GEOMETRY_SENSITIVITY_ALL.csv"].copy()
    dual["rmse"] = pd.to_numeric(dual["cyclic_rmse_diagonal_normalized"], errors="coerce")
    same = dual[dual["same_topology"].map(truth) & dual["rmse"].notna()].sort_values(["rmse", "base_task_id"], ascending=[False, True]).iloc[0]
    different = dual[~dual["same_topology"].map(truth)].copy()
    different["corner_gap"] = (pd.to_numeric(different["n_corners_left"], errors="coerce")
                               - pd.to_numeric(different["n_corners_right"], errors="coerce")).abs()
    different_row = different.sort_values(["corner_gap", "base_task_id"], ascending=[False, True]).iloc[0]
    for row, title, rule in (
        (same, "双标注者：同拓扑坐标差异最大", "在相同拓扑双人任务中选择循环对齐 RMSE 最大的任务"),
        (different_row, "双标注者：拓扑不同", "在拓扑不同任务中选择角点数差异最大的任务"),
    ):
        cases.append(Case("双标注者几何差异", title, row.base_task_id, rule,
                          ["DUAL_ANNOTATOR_GEOMETRY_SENSITIVITY_ALL.csv", "RAW_ANNOTATION_LEDGER_ALL_2513.csv"],
                          {key: row.get(key, "") for key in ("cyclic_rmse_diagonal_normalized", "n_corners_left", "n_corners_right")},
                          mode="dual", include_gt=True,
                          focus={"stage": row.stage, "condition": row.condition, "workers": [str(row.worker_id_left), str(row.worker_id_right)]}))

    replay = tables["C1_K22_PREFIX_REPLAY.csv"].copy()
    replay["k_num"] = pd.to_numeric(replay["k"], errors="coerce")
    replay["supported"] = replay["task_crowd_structure_status"].eq("supported_multimodal")
    summary = replay.groupby("base_task_id").agg(supported_replay_rate=("supported", "mean")).reset_index()
    k5 = replay[replay["k_num"].eq(5)].groupby("base_task_id")["supported"].mean().rename("k5_supported_rate")
    k22 = replay[replay["k_num"].eq(22)].groupby("base_task_id")["supported"].max().rename("final_supported")
    summary = summary.join(k5, on="base_task_id").join(k22, on="base_task_id")
    stable = summary.sort_values(["supported_replay_rate", "base_task_id"], ascending=[False, True]).iloc[0]
    late = summary[summary["final_supported"]].sort_values(["k5_supported_rate", "supported_replay_rate", "base_task_id"], ascending=[True, True, True]).iloc[0]
    for row, title, rule in (
        (stable, "持续多峰：重放中稳定分裂", "选择全部前缀重放中支持多峰比例最高的任务"),
        (late, "持续多峰：增加标注后暴露", "在完整样本支持多峰的任务中选择 k=5 支持多峰比例最低者"),
    ):
        cases.append(Case("持续多峰", title, row.base_task_id, rule,
                          ["C1_K22_PREFIX_REPLAY.csv", "PERSISTENT_DISAGREEMENT_TASKS.CSV"],
                          {key: row.get(key, "") for key in ("supported_replay_rate", "k5_supported_rate")},
                          mode="persistent", include_gt=True))

    tags = tables["TAG_BEHAVIOR_ALL_CASES.csv"].copy()
    tags["edit_px"] = pd.to_numeric(tags["geometry_edit_rmse_px"], errors="coerce").fillna(-1)
    acceptable = tags[(tags["stage"].eq("C1")) & tags["condition"].eq("semi")
                      & tags["case_codes"].str.contains("acceptable_proposal_with_material_or_topology_edit")].sort_values(
        ["edit_px", "base_task_id"], ascending=[False, True]).iloc[0]
    trivial = tags[(tags["stage"].eq("C1")) & tags["condition"].eq("semi")
                   & tags["case_codes"].str.contains("trivial_tag_but_material_edit|trivial_tag_but_long_active_time", regex=True)].copy()
    trivial["time"] = pd.to_numeric(trivial["active_time_observed_seconds"], errors="coerce").fillna(-1)
    trivial["score"] = trivial["time"] + trivial["edit_px"].clip(lower=0)
    trivial_row = trivial.sort_values(["score", "base_task_id"], ascending=[False, True]).iloc[0]
    for row, title, rule in (
        (acceptable, "元标签：报告可接受但明显编辑", "在报告可接受且有实质编辑的记录中选择几何编辑 RMSE 最大者"),
        (trivial_row, "元标签：报告简单但编辑或耗时突出", "在简单标签矛盾记录中按冻结 active time 与编辑 RMSE 之和选择最大者"),
    ):
        cases.append(Case("元标签与实际行为", title, row.base_task_id, rule,
                          ["TAG_BEHAVIOR_ALL_CASES.csv", "ACTIVE_TIME_TASK_WORKER.CSV"],
                          {key: row.get(key, "") for key in ("geometry_edit_rmse_px", "active_time_observed_seconds", "iou_to_gt")},
                          mode="meta", include_gt=True,
                          focus={"stage": row.stage, "condition": row.condition, "workers": [str(row.worker_id)], "tags": row.get("tag_labels_zh", "")}))

    excluded = tables["OUT_OF_TASK_AND_NONSELECTED_ROWS.csv"].copy()
    excluded["result_n"] = pd.to_numeric(excluded["result_count"], errors="coerce").fillna(0)
    w31 = excluded[(excluded["worker_id"].eq("31")) & excluded["audit_class"].str.contains("outside_assignment") & (excluded["result_n"] > 0)].sort_values("base_task_id").iloc[0]
    raw = tables["RAW_ANNOTATION_LEDGER_ALL_2513.csv"]
    revision_candidates = excluded[(excluded["canonical_join_status"].eq("raw_version_not_in_canonical_spine")) & (excluded["result_n"] > 0)].copy()
    revision_rows: list[tuple[float, pd.Series, pd.Series]] = []
    for _, old in revision_candidates.iterrows():
        final = raw[(raw["base_task_id"].eq(old.base_task_id)) & raw["worker_id"].eq(old.worker_id) & raw["canonical_join_status"].eq("matched")]
        if final.empty:
            continue
        old_points = [[p["x"], y] for p in runtime_pairs(old.result_json) for y in (p["y_ceiling"], p["y_floor"])]
        for _, new in final.iterrows():
            new_pairs = runtime_pairs(new.result_json)
            new_points = [[p["x"], y] for p in new_pairs for y in (p["y_ceiling"], p["y_floor"])]
            distance = cyclic_rmse(old_points, new_points)
            if distance is not None:
                revision_rows.append((distance, old, new))
    if not revision_rows:
        raise ValueError("没有可视化所需的非最终版本与最终版本配对。")
    revision_distance, old, new = sorted(revision_rows, key=lambda item: (-item[0], str(item[1].base_task_id)))[0]
    cases.append(Case("被排除及非规范记录", "任务外记录：W31", w31.base_task_id,
                      "选择 W31 有几何结果的任务外记录中 task ID 最小者",
                      ["OUT_OF_TASK_AND_NONSELECTED_ROWS.csv", "RAW_ANNOTATION_LEDGER_ALL_2513.csv"],
                      {"result_count": w31.result_count}, mode="excluded", include_gt=True,
                      focus={"annotation_id": str(w31.annotation_id), "worker": "31", "condition": w31.condition, "stage": w31.stage}))
    cases.append(Case("被排除及非规范记录", "修订链：非最终版本与最终版本", old.base_task_id,
                      "对同任务同标注者的非最终/最终版本配对，选择版本间几何差异最大的配对",
                      ["OUT_OF_TASK_AND_NONSELECTED_ROWS.csv", "REVISION_LINEAGE_ALL_2513.csv"],
                      {"revision_rmse": revision_distance, "result_count": old.result_count}, mode="revision", include_gt=True,
                      focus={"old_annotation_id": str(old.annotation_id), "new_annotation_id": str(new.annotation_id), "worker": str(old.worker_id)}))

    features = tables["IMAGE_FEATURES_ALL_214.csv"].copy()
    features["edge_num"] = pd.to_numeric(features["edge_density_proxy"], errors="coerce")
    difficult = convergence.merge(features, on="base_task_id", how="inner", suffixes=("", "_feature"))
    for subset, title, rule in (
        (difficult[difficult["delta"] < 0], "高图像复杂度代理：Semi 收敛", "在熵下降任务中选择图像固有边缘密度代理最高者"),
        (difficult[difficult["delta"] > 0], "高图像复杂度代理：Semi 扩张对照", "在熵上升任务中选择图像固有边缘密度代理最高者"),
    ):
        row = subset.sort_values(["edge_num", "base_task_id"], ascending=[False, True]).iloc[0]
        cases.append(Case("图像歧义与难度", title, row.base_task_id, rule,
                          ["IMAGE_FEATURES_ALL_214.csv", "SEMI_25_CONVERGENCE_EXPANSION_ALL_IMAGES.csv"],
                          {key: row.get(key, "") for key in ("edge_density_proxy", "delta_shannon_entropy")},
                          include_gt=True))

    if len(cases) > 16 or len({case.category for case in cases}) != 8:
        raise AssertionError("案例选择必须保持 8 类且不超过 16 个。")
    return cases


class Renderer:
    def __init__(self, tables: dict[str, pd.DataFrame], semi: dict[str, dict[str, Any]], gt: dict[str, list[dict[str, Any]]], out: Path):
        self.tables, self.semi, self.gt, self.out = tables, semi, gt, out
        self.raw = tables["RAW_ANNOTATION_LEDGER_ALL_2513.csv"]
        self.members = tables["C1_WORKER_TASK_MODE_MEMBERSHIP.CSV"]
        self.assets = out / "assets"

    def asset(self, task: str) -> str:
        source = IMAGE_DIR / f"{task}.jpg"
        if not source.exists():
            raise FileNotFoundError(f"缺少本地原图：{source}")
        destination = self.assets / f"{task}.jpg"
        if not destination.exists():
            with Image.open(source) as image:
                image.convert("RGB").resize((1024, 512)).save(destination, "JPEG", quality=84, optimize=True)
        return f"assets/{destination.name}"

    def selected_rows(self, task: str, condition: str = "", stage: str = "") -> pd.DataFrame:
        rows = self.raw[self.raw["base_task_id"].eq(task) & self.raw["canonical_join_status"].eq("matched")]
        if condition:
            rows = rows[rows["condition"].eq(condition)]
        if stage:
            rows = rows[rows["stage"].eq(stage)]
        return rows.drop_duplicates(["stage", "condition", "worker_id", "annotation_id"])

    def cluster_rank(self, row: pd.Series) -> str:
        match = self.members[(self.members["base_task_id"].eq(row.base_task_id))
                             & self.members["condition"].eq(row.condition)
                             & self.members["worker_id"].eq(row.worker_id)]
        if row.canonical_annotation_id:
            exact = match[match["annotation_id"].eq(row.canonical_annotation_id)]
            if not exact.empty:
                match = exact
        return str(match.iloc[0].cluster_rank) if not match.empty else ""

    def annotation(self, row: pd.Series, special: str = "") -> dict[str, Any] | None:
        pairs = runtime_pairs(row.result_json)
        if not pairs:
            return None
        rank = self.cluster_rank(row)
        color = "#b58cff" if special == "excluded" else "#9aa6b8" if special == "revision" else PALETTE[(int(rank or row.worker_id or 0) - 1) % len(PALETTE)]
        return {"key": f"a-{html.escape(str(row.annotation_id))}", "label": f"W{row.worker_id}", "pairs": pairs,
                "color": color, "rank": rank, "special": special,
                "status": str(row.get("canonical_join_status_zh", ""))}

    def group_panel(self, task: str, title: str, rows: pd.DataFrame, special: str = "") -> str:
        annotations = [item for _, row in rows.iterrows() if (item := self.annotation(row, special))]
        return self.panel(task, title, annotations)

    def model_panel(self, task: str) -> str:
        row = self.semi.get(task)
        if not row or not row.get("predictions"):
            return ""
        prediction = row["predictions"][0]
        pairs = runtime_pairs(prediction.get("result") or [])
        annotation = {"key": f"model-{task}", "label": "MODEL", "pairs": pairs, "color": "#ffd23f", "rank": "", "special": "model", "status": prediction.get("model_version", "")}
        return self.panel(task, "模型初始预标注", [annotation])

    def gt_panel(self, task: str) -> str:
        pairs = runtime_pairs(self.gt.get(task, []))
        if not pairs:
            return ""
        annotation = {"key": f"gt-{task}", "label": "GT", "pairs": pairs, "color": "#ffffff", "rank": "", "special": "gt", "status": "458-task GT import"}
        return self.panel(task, "GT 参考", [annotation])

    def panels(self, case: Case) -> str:
        task, mode = case.task, case.mode
        panels: list[str] = []
        if mode == "dual":
            rows = self.selected_rows(task, case.focus["condition"], case.focus["stage"])
            for worker in case.focus["workers"]:
                worker_rows = rows[rows["worker_id"].eq(worker)].head(1)
                panels.append(self.group_panel(task, f"标注者 W{worker}", worker_rows))
        elif mode == "excluded":
            peers = self.selected_rows(task, case.focus["condition"], case.focus["stage"])
            panels.append(self.group_panel(task, "已整理记录（同任务对照）", peers[~peers["worker_id"].eq(case.focus["worker"])]))
            raw = self.raw[self.raw["annotation_id"].eq(case.focus["annotation_id"])].head(1)
            panels.append(self.group_panel(task, "任务外记录", raw, "excluded"))
        elif mode == "revision":
            old = self.raw[self.raw["annotation_id"].eq(case.focus["old_annotation_id"])].head(1)
            new = self.raw[self.raw["annotation_id"].eq(case.focus["new_annotation_id"])].head(1)
            panels.append(self.group_panel(task, f"W{case.focus['worker']} 非最终版本", old, "revision"))
            panels.append(self.group_panel(task, f"W{case.focus['worker']} 最终整理版本", new))
        elif mode == "meta":
            rows = self.selected_rows(task, case.focus.get("condition", ""), case.focus.get("stage", ""))
            workers = set(case.focus.get("workers", []))
            panels.append(self.model_panel(task))
            panels.append(self.group_panel(task, "该元标签记录的最终标注", rows[rows["worker_id"].isin(workers)]))
            peers = rows[~rows["worker_id"].isin(workers)]
            if not peers.empty:
                panels.append(self.group_panel(task, "同任务其他标注者", peers))
        elif mode == "persistent":
            rows = self.selected_rows(task)
            if not rows.empty:
                group_cols = rows.groupby(["stage", "condition"]).size().sort_values(ascending=False)
                stage, condition = group_cols.index[0]
                panels.append(self.group_panel(task, f"{stage} · {condition} 全部标注", rows[(rows["stage"].eq(stage)) & rows["condition"].eq(condition)]))
        else:
            manual = self.selected_rows(task, "manual")
            semi = self.selected_rows(task, "semi")
            if not manual.empty:
                panels.append(self.group_panel(task, "全手工 Manual", manual))
            panels.append(self.model_panel(task))
            if not semi.empty:
                panels.append(self.group_panel(task, "半自动 Semi 最终标注", semi))
        if case.include_gt:
            panels.append(self.gt_panel(task))
        return "".join(panel for panel in panels if panel)

    def panel(self, task: str, title: str, annotations: list[dict[str, Any]]) -> str:
        groups, controls = [], []
        for annotation in annotations:
            pairs = sorted(annotation["pairs"], key=lambda item: item["x"])
            tops = " ".join(f"{p['x']:.1f},{p['y_ceiling']:.1f}" for p in pairs)
            bottoms = " ".join(f"{p['x']:.1f},{p['y_floor']:.1f}" for p in pairs)
            lines = [f'<polyline points="{tops}"/>', f'<polyline points="{bottoms}"/>']
            lines += [f'<line x1="{p["x"]:.1f}" y1="{p["y_ceiling"]:.1f}" x2="{p["x"]:.1f}" y2="{p["y_floor"]:.1f}"/>' for p in pairs]
            circles = "".join(f'<circle cx="{p["x"]:.1f}" cy="{y:.1f}" r="4.5"/>' for p in pairs for y in (p["y_ceiling"], p["y_floor"]))
            first = pairs[0]
            special = annotation["special"]
            classes = f"annotation {special}".strip()
            groups.append(f'<g class="{classes}" data-layer="{annotation["key"]}" style="--line:{annotation["color"]}">'
                          + "".join(lines) + circles
                          + f'<text x="{first["x"]:.1f}" y="{max(16, first["y_ceiling"]-7):.1f}">{html.escape(annotation["label"])}</text></g>')
            rank = f" · 簇 {annotation['rank']}" if annotation["rank"] else ""
            controls.append(f'<button type="button" class="layer-toggle" data-target="{annotation["key"]}" aria-pressed="true" style="--line:{annotation["color"]}"><i></i>{html.escape(annotation["label"])}{rank}</button>')
        return (f'<article class="panel"><header><b>{html.escape(title)}</b><span>{len(annotations)} 条几何记录</span></header>'
                f'<div class="canvas"><img src="{self.asset(task)}" alt="任务 {html.escape(task)} 全景原图">'
                f'<svg viewBox="0 0 1024 512" role="img" aria-label="全景原图上的墙角点及上下边界线">{"".join(groups)}</svg></div>'
                f'<div class="layer-controls">{"".join(controls)}</div></article>')


def format_value(value: Any) -> str:
    numeric = number(value)
    if numeric is None:
        text = str(value).strip()
        return "不可计算" if not text or text.lower() in {"inf", "+inf", "-inf", "nan", "none"} else html.escape(text)
    if abs(numeric) >= 100:
        return f"{numeric:,.1f}"
    return f"{numeric:.4f}".rstrip("0").rstrip(".")


def metric_html(metrics: dict[str, Any]) -> str:
    blocks = []
    for code, value in metrics.items():
        if code not in METRIC_INFO or str(value) == "":
            continue
        label, calculation = METRIC_INFO[code]
        blocks.append(f'<div class="metric"><span>{html.escape(label)} <code>{html.escape(code)}</code></span>'
                      f'<strong>{format_value(value)}</strong><small>{html.escape(calculation)}</small></div>')
    return "".join(blocks)


def page_html(cases: list[Case], renderer: Renderer) -> str:
    categories = list(dict.fromkeys(case.category for case in cases))
    options = "".join(f'<option value="{html.escape(category)}">{html.escape(category)}</option>' for category in categories)
    sections = []
    for index, case in enumerate(cases, 1):
        slug = f"case-{index:02d}"
        sections.append(f'''<section class="case" id="{slug}" data-category="{html.escape(case.category)}">
          <div class="case-head"><div><span>{html.escape(case.category)} · 案例 {index:02d}</span><h2>{html.escape(case.title)}</h2></div><code>{html.escape(case.task)}</code></div>
          <p class="rule">选例规则：{html.escape(case.selection_rule)}</p>
          <div class="metric-grid">{metric_html(case.metrics)}</div>
          <div class="panel-grid">{renderer.panels(case)}</div>
          <p class="source">数据来源：{html.escape('；'.join(case.sources))}</p>
        </section>''')
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>v5 图像证据可视化总览</title><style>
:root{{--bg:#0b1020;--panel:#111a30;--panel2:#070b14;--text:#edf4ff;--muted:#a8b7d3;--border:#2a3a5d;--accent:#64d6ff}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font-family:"Microsoft YaHei UI","Microsoft YaHei","Noto Sans CJK SC","PingFang SC",Arial,sans-serif}}
main{{max-width:1640px;margin:auto;padding:24px}} h1,h2,p{{margin-top:0}} h1{{font-size:26px}} h2{{font-size:21px;margin:4px 0 0}} code{{font-family:Consolas,"Microsoft YaHei UI",monospace;overflow-wrap:anywhere}}
.intro{{display:flex;justify-content:space-between;gap:18px;align-items:end}} .intro p,.rule,.source{{color:var(--muted)}} .filters{{display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
select,button{{font:inherit}} select{{background:var(--panel);color:var(--text);border:1px solid var(--border);padding:8px 10px;border-radius:7px}}
.case{{background:var(--panel);border:1px solid var(--border);border-radius:14px;padding:17px;margin-top:18px}} .case[hidden]{{display:none}} .case-head{{display:flex;justify-content:space-between;gap:12px;align-items:end}} .case-head span{{color:var(--accent);font-size:12px;letter-spacing:.08em}}
.rule,.source{{font-size:12px;margin:8px 0}} .metric-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:8px;margin:12px 0}}
.metric{{background:#0a1223;padding:9px 10px;border-left:3px solid var(--accent)}} .metric span,.metric small{{display:block;color:var(--muted);font-size:11px}} .metric strong{{display:block;font-size:17px;margin:3px 0;font-weight:500}}
.panel-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:12px}} .panel{{background:var(--panel2);border:1px solid var(--border);border-radius:10px;overflow:hidden}}
.panel header{{display:flex;justify-content:space-between;gap:8px;padding:9px 11px;font-size:13px}} .panel header span{{color:var(--muted)}} .canvas{{position:relative;aspect-ratio:2/1;background:#000}}
.canvas img,.canvas svg{{position:absolute;inset:0;width:100%;height:100%;display:block}} .annotation{{stroke:var(--line);fill:var(--line);stroke-width:2.35;vector-effect:non-scaling-stroke;filter:drop-shadow(0 0 1px #000)}}
.annotation polyline,.annotation line{{fill:none}} .annotation circle{{stroke:#07101c;stroke-width:1.4}} .annotation text{{font-size:14px;font-weight:500;stroke:#07101c;stroke-width:3.5;paint-order:stroke}}
.annotation.model{{stroke-dasharray:9 5}} .annotation.model circle{{fill:none;stroke:#ffd23f;stroke-width:3}} .annotation.gt{{stroke-width:4}} .annotation.gt circle{{fill:#fff;stroke:#172033;stroke-width:2}}
.annotation.excluded{{stroke-dasharray:14 5 3 5}} .annotation.revision{{stroke-dasharray:4 5}} .annotation.off{{opacity:.06}}
.layer-controls{{display:flex;gap:6px;flex-wrap:wrap;padding:9px}} .layer-toggle{{border:1px solid var(--border);background:#16233d;color:var(--text);border-radius:999px;padding:5px 8px;cursor:pointer;font-size:12px}}
.layer-toggle i{{display:inline-block;width:17px;border-top:3px solid var(--line);margin-right:5px;vertical-align:middle}} .layer-toggle[aria-pressed="false"]{{opacity:.35;text-decoration:line-through}}
@media(max-width:760px){{main{{padding:12px}}.intro,.case-head{{align-items:start;flex-direction:column}}.panel-grid{{grid-template-columns:1fr}}}}
</style></head><body><main><div class="intro"><div><h1>v5 图像证据可视化总览</h1><p>8 类、每类 2 个案例；原图、人工标注、模型预标注和 GT 按实际可用证据显示。</p></div><div class="filters"><label for="category-filter">类型</label><select id="category-filter"><option value="all">全部类型</option>{options}</select></div></div>
{''.join(sections)}</main><script>
document.querySelectorAll('.layer-toggle').forEach(button=>button.addEventListener('click',()=>{{const on=button.getAttribute('aria-pressed')==='true';button.setAttribute('aria-pressed',String(!on));document.querySelector(`[data-layer="${{button.dataset.target}}"]`)?.classList.toggle('off',on)}}));
document.getElementById('category-filter').addEventListener('change',event=>document.querySelectorAll('.case').forEach(node=>node.hidden=event.target.value!=='all'&&node.dataset.category!==event.target.value));
</script></body></html>'''


def write_index(path: Path, cases: list[Case], renderer: Renderer) -> None:
    fields = ["序号", "案例类型", "案例标题", "base_task_id", "worker_ids", "选例规则", "数据来源", "指标变量", "HTML锚点", "PNG文件"]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for index, case in enumerate(cases, 1):
            workers = case.focus.get("workers") or ([case.focus["worker"]] if case.focus.get("worker") else [])
            writer.writerow({"序号": index, "案例类型": case.category, "案例标题": case.title, "base_task_id": case.task,
                             "worker_ids": ";".join(workers), "选例规则": case.selection_rule, "数据来源": ";".join(case.sources),
                             "指标变量": ";".join(case.metrics), "HTML锚点": f"#case-{index:02d}", "PNG文件": f"单图/{index:02d}_{case.task}.png"})


def render_pngs(html_path: Path, out: Path, cases: list[Case]) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1200}, device_scale_factor=1)
        page.goto(html_path.as_uri(), wait_until="load")
        page.evaluate("document.fonts.ready")
        for index, case in enumerate(cases, 1):
            locator = page.locator(f"#case-{index:02d}")
            locator.scroll_into_view_if_needed()
            locator.screenshot(path=out / "单图" / f"{index:02d}_{case.task}.png")
        browser.close()


def build(v5: Path, out: Path, *, png: bool = True) -> list[Case]:
    names = [
        "SEMI_25_CONVERGENCE_EXPANSION_ALL_IMAGES.csv", "PROPOSAL_TASK_ANCHORING_AND_DISCOVERY.csv",
        "CROWD_GT_101_GEOMETRIC_CAUSE_AUDIT.csv", "C1_CROWD_GT_CLUSTER_METRICS.CSV",
        "DUAL_ANNOTATOR_GEOMETRY_SENSITIVITY_ALL.csv", "C1_K22_PREFIX_REPLAY.csv",
        "PERSISTENT_DISAGREEMENT_TASKS.CSV", "TAG_BEHAVIOR_ALL_CASES.csv", "ACTIVE_TIME_TASK_WORKER.CSV",
        "OUT_OF_TASK_AND_NONSELECTED_ROWS.csv", "REVISION_LINEAGE_ALL_2513.csv", "IMAGE_FEATURES_ALL_214.csv",
        "RAW_ANNOTATION_LEDGER_ALL_2513.csv", "C1_WORKER_TASK_MODE_MEMBERSHIP.CSV",
    ]
    tables = {name: read_csv(v5, name) for name in names}
    cases = choose_cases(tables)
    out.mkdir(parents=True, exist_ok=True)
    for child in (out / "assets", out / "单图"):
        child.mkdir(exist_ok=True)
        for file in child.iterdir():
            if file.is_file():
                file.unlink()
    renderer = Renderer(tables, prediction_lookup(SEMI_IMPORT), gt_lookup(GT_IMPORT), out)
    html_path = out / "可视化总览.html"
    with html_path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(page_html(cases, renderer))
    write_index(out / "案例索引.csv", cases, renderer)
    if png:
        render_pngs(html_path, out, cases)
    return cases


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cases = build(args.v5_dir.resolve(), args.output_dir.resolve(), png=not args.skip_png)
    print(f"generated {len(cases)} cases -> {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
