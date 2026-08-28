from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import sys
from collections import Counter
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.thesis_main.analysis.materialize_model_gt_threshold_screen import (  # noqa: E402
    _ordered_pairs,
    _pairs,
    _read_test_gt,
    _read_txt,
)
from tools.thesis_main.analysis.quality_core.geometry_metrics import _interp_periodic  # noqa: E402


WIDTH = 1024
HEIGHT = 512
LABEL_FONT = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 16)
SCREEN_STRATA = (
    "balanced_boundary_difference",
    "reference_region_missing_dominant",
    "model_region_extra_dominant",
    "pair_count_changed",
)
DEFECTS = (
    "boundary_misalignment",
    "current_space_undercoverage",
    "adjacent_space_inclusion",
    "spurious_nonlayout_structure",
    "duplicate_redundant_corner",
)
REPAIR_ACTIONS = (
    "move_boundary_or_corner",
    "add_missing_boundary_or_corner",
    "remove_adjacent_space_segment",
    "remove_spurious_structure",
    "merge_or_delete_duplicate_corner",
    "redraw_layout",
)
OPTION_LABELS = {
    "main": "主候选",
    "reserve": "备用候选",
    "in_scope": "符合实验范围",
    "revise": "需修改后再审",
    "reject": "排除",
    "PASS": "通过",
    "REVISE": "修改后再审",
    "REJECT": "排除",
    "yes": "是",
    "no": "否",
    "uncertain": "暂不确定",
    "balanced_boundary_difference": "缺失/额外区域近似平衡",
    "reference_region_missing_dominant": "相对参考的缺失区域占主导",
    "model_region_extra_dominant": "相对参考的额外区域占主导",
    "pair_count_changed": "角点对数量发生变化",
    "boundary_misalignment": "边界或角点位置偏移",
    "current_space_undercoverage": "遗漏当前空间",
    "adjacent_space_inclusion": "纳入相邻空间",
    "spurious_nonlayout_structure": "虚构非布局结构",
    "duplicate_redundant_corner": "重复或冗余角点",
    "move_boundary_or_corner": "移动边界或角点",
    "add_missing_boundary_or_corner": "补充遗漏边界或角点",
    "remove_adjacent_space_segment": "删除纳入的相邻空间段",
    "remove_spurious_structure": "删除虚假结构",
    "merge_or_delete_duplicate_corner": "合并或删除重复角点",
    "redraw_layout": "重新标注完整布局",
    "local": "局部修正",
    "multi_region": "多处几何修正",
    "redraw": "重新标注",
    "structurally_valid": "结构有效",
    "structurally_invalid": "配对/闭合/自交等结构无效",
    "single": "单一缺陷",
    "dominant_with_secondary": "有主要缺陷并伴次要缺陷",
    "mixed": "多个缺陷，无可靠单一主类",
    "too_light": "错误过轻",
    "moderate": "适中",
    "too_heavy": "错误过重",
}
TARGET_DISTANCE = {
    "balanced_boundary_difference": 0.07,
    "reference_region_missing_dominant": 0.11,
    "model_region_extra_dominant": 0.11,
    "pair_count_changed": 0.12,
}
BROAD_REVIEW_LIMITS = {
    "layout_mask_difference": [0.05, 0.18],
    "boundary_rmse_px": [8.0, 35.0],
    "max_abs_pair_count_delta": 4,
}


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _supported_split(value: Any) -> bool:
    return str(value).strip() in {"test", "validation"}


def _supported_gt_source(value: Any) -> bool:
    source = str(value).strip()
    return source.startswith("official_") or source == "confirmed_user_manual_gt_correction"


@cache
def _manual_gt_pairs(path: Path) -> dict[str, list[dict[str, float]]]:
    return {
        image_id: _pairs(points, source=path, ordered_source=False)
        for image_id, points in _read_test_gt(path).items()
    }


def _reference_pairs(row: dict[str, str], path: Path) -> list[dict[str, float]]:
    if row.get("gt_source_type") == "confirmed_user_manual_gt_correction":
        try:
            return _manual_gt_pairs(path)[row["image_id"]]
        except KeyError as exc:
            raise ValueError(f"manual GT missing image_id {row['image_id']}: {path}") from exc
    return _pairs(_read_txt(path), source=path, ordered_source=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _layout_mask(pairs: list[dict[str, float]]) -> np.ndarray:
    xs = np.asarray([item["x"] for item in pairs], dtype=np.float32)
    ceiling = np.rint(_interp_periodic(xs, np.asarray([item["y_ceiling"] for item in pairs]), WIDTH)).astype(int)
    floor = np.rint(_interp_periodic(xs, np.asarray([item["y_floor"] for item in pairs]), WIDTH)).astype(int)
    ceiling = np.clip(ceiling, 0, HEIGHT - 1)
    floor = np.clip(floor, 0, HEIGHT - 1)
    mask = np.zeros((HEIGHT, WIDTH), dtype=bool)
    for x, (top, bottom) in enumerate(zip(ceiling, floor)):
        if bottom < top:
            top, bottom = bottom, top
        mask[top : bottom + 1, x] = True
    return mask


def classify_screen_stratum(*, pair_delta: int, false_negative_ratio: float, false_positive_ratio: float) -> str:
    """Assign a mechanical coverage stratum, never an experimental truth family."""
    if pair_delta:
        return "pair_count_changed"
    if false_negative_ratio >= 0.025 and false_negative_ratio >= 1.35 * false_positive_ratio:
        return "reference_region_missing_dominant"
    if false_positive_ratio >= 0.025 and false_positive_ratio >= 1.35 * false_negative_ratio:
        return "model_region_extra_dominant"
    return "balanced_boundary_difference"


def _measure(row: dict[str, str]) -> dict[str, Any] | None:
    image_path = ROOT / row["image_path"]
    model_path = ROOT / row["model_path"]
    gt_path = ROOT / row["gt_path"]
    if not all(path.is_file() for path in (image_path, model_path, gt_path)):
        return None
    if (
        not _supported_split(row.get("split"))
        or not _supported_gt_source(row.get("gt_source_type"))
        or not _truth(row.get("model_pair_encoding_valid"))
    ):
        return None

    distance = float(row["layout_mask_difference"])
    if not 0.025 <= distance <= 0.25:
        return None
    model_pairs = _ordered_pairs(_read_txt(model_path), source=model_path)
    gt_pairs = _reference_pairs(row, gt_path)
    correct_mask = _layout_mask(gt_pairs)
    wrong_mask = _layout_mask(model_pairs)
    denominator = max(int(correct_mask.sum()), 1)
    fn_ratio = float(np.logical_and(correct_mask, ~wrong_mask).sum() / denominator)
    fp_ratio = float(np.logical_and(wrong_mask, ~correct_mask).sum() / denominator)
    pair_delta = len(model_pairs) - len(gt_pairs)
    stratum = classify_screen_stratum(
        pair_delta=pair_delta,
        false_negative_ratio=fn_ratio,
        false_positive_ratio=fp_ratio,
    )
    boundary_rmse = float(row["boundary_rmse_px"] or 0)
    if stratum == "balanced_boundary_difference" and not 7 <= boundary_rmse <= 35:
        return None

    return {
        "split": row["split"],
        "gt_source_type": row["gt_source_type"],
        "image_id": row["image_id"],
        "building_id": row["image_id"].split("_", 1)[0],
        "image_path": image_path,
        "correct_path": gt_path,
        "wrong_path": model_path,
        "image_sha256": row.get("image_sha256", "") or _sha256(image_path),
        "correct_sha256": row.get("gt_sha256", "") or _sha256(gt_path),
        "wrong_sha256": row.get("model_sha256", "") or _sha256(model_path),
        "screen_stratum": stratum,
        "layout_mask_difference": distance,
        "boundary_rmse_px": boundary_rmse,
        "correct_pair_count": len(gt_pairs),
        "wrong_pair_count": len(model_pairs),
        "pair_count_delta": pair_delta,
        "false_negative_ratio": fn_ratio,
        "false_positive_ratio": fp_ratio,
        "score": abs(distance - TARGET_DISTANCE[stratum]),
        "correct_pairs": gt_pairs,
        "wrong_pairs": model_pairs,
    }


def select_balanced(
    candidates: list[dict[str, Any]],
    *,
    main_per_stratum: int,
    reserve_per_stratum: int,
    main_count_by_stratum: dict[str, int] | None = None,
    excluded_image_ids: set[str] | None = None,
    review_prefix: str = "B1",
) -> list[dict[str, Any]]:
    main_counts = main_count_by_stratum or {stratum: main_per_stratum for stratum in SCREEN_STRATA}
    if set(main_counts) != set(SCREEN_STRATA):
        raise ValueError("main_count_by_stratum must define every screen stratum")
    excluded = excluded_image_ids or set()
    by_stratum = {stratum: sorted((row for row in candidates if row["screen_stratum"] == stratum), key=lambda row: (row["score"], row["image_id"])) for stratum in SCREEN_STRATA}
    selected: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    building_counts: Counter[str] = Counter()

    for stratum in SCREEN_STRATA:
        if main_counts[stratum] == 0:
            continue
        chosen = []
        for row in by_stratum[stratum]:
            if row["image_id"] in excluded or row["image_id"] in used_ids or building_counts[row["building_id"]] >= 2:
                continue
            chosen.append(row)
            used_ids.add(row["image_id"])
            building_counts[row["building_id"]] += 1
            if len(chosen) == main_counts[stratum]:
                break
        if len(chosen) != main_counts[stratum]:
            raise RuntimeError(f"insufficient building-diverse candidates for {stratum}: {len(chosen)}/{main_counts[stratum]}")
        for row in chosen:
            row["candidate_role"] = "main"
        selected.extend(chosen)

    for stratum in SCREEN_STRATA:
        if reserve_per_stratum == 0:
            continue
        chosen = []
        for row in by_stratum[stratum]:
            if row["image_id"] in excluded or row["image_id"] in used_ids:
                continue
            chosen.append(row)
            used_ids.add(row["image_id"])
            if len(chosen) == reserve_per_stratum:
                break
        if len(chosen) != reserve_per_stratum:
            raise RuntimeError(f"insufficient reserve candidates for {stratum}: {len(chosen)}/{reserve_per_stratum}")
        for row in chosen:
            row["candidate_role"] = "reserve"
        selected.extend(chosen)

    selected.sort(key=lambda row: (row["candidate_role"] != "main", SCREEN_STRATA.index(row["screen_stratum"]), row["score"], row["image_id"]))
    for index, row in enumerate(selected, 1):
        row["review_id"] = f"{review_prefix}-{index:03d}"
    return selected


def select_broad_review_range(
    candidates: list[dict[str, Any]],
    *,
    excluded_image_ids: set[str] | None = None,
    review_prefix: str = "B1W",
) -> list[dict[str, Any]]:
    excluded = excluded_image_ids or set()
    selected = [
        row for row in candidates
        if row["image_id"] not in excluded
        and BROAD_REVIEW_LIMITS["layout_mask_difference"][0]
        <= row["layout_mask_difference"]
        <= BROAD_REVIEW_LIMITS["layout_mask_difference"][1]
        and BROAD_REVIEW_LIMITS["boundary_rmse_px"][0]
        <= row["boundary_rmse_px"]
        <= BROAD_REVIEW_LIMITS["boundary_rmse_px"][1]
        and abs(row["pair_count_delta"]) <= BROAD_REVIEW_LIMITS["max_abs_pair_count_delta"]
    ]
    selected.sort(key=lambda row: (
        SCREEN_STRATA.index(row["screen_stratum"]),
        row["pair_count_delta"],
        row["layout_mask_difference"],
        row["image_id"],
    ))
    for index, row in enumerate(selected, 1):
        row["candidate_role"] = "main"
        row["review_id"] = f"{review_prefix}-{index:03d}"
    return selected


def _draw_layout(image: Image.Image, pairs: list[dict[str, float]], color: tuple[int, int, int]) -> None:
    draw = ImageDraw.Draw(image)
    xs = np.asarray([item["x"] for item in pairs], dtype=np.float32)
    for field in ("y_ceiling", "y_floor"):
        ys = _interp_periodic(xs, np.asarray([item[field] for item in pairs]), WIDTH)
        draw.line([(x, float(y)) for x, y in enumerate(ys)], fill=color, width=4)
    for item in pairs:
        x = float(item["x"]) % WIDTH
        draw.line([(x, item["y_ceiling"]), (x, item["y_floor"])], fill=color, width=4)


def _panel(image: Image.Image, label: str, layouts: list[tuple[list[dict[str, float]], tuple[int, int, int]]]) -> Image.Image:
    panel = image.copy()
    for pairs, color in layouts:
        _draw_layout(panel, pairs, color)
    draw = ImageDraw.Draw(panel)
    draw.rectangle((0, 0, WIDTH, 30), fill=(0, 0, 0))
    draw.text((10, 4), label, fill=(255, 255, 255), font=LABEL_FONT)
    return panel


def _render_preview(row: dict[str, Any], path: Path) -> None:
    source = Image.open(row["image_path"]).convert("RGB").resize((WIDTH, HEIGHT))
    green = (0, 255, 80)
    red = (255, 65, 65)
    panels = [
        _panel(source, "原图（无标线）", []),
        _panel(source, "正确预标注候选（绿色参考标注）", [(row["correct_pairs"], green)]),
        _panel(source, "错误预标注候选（红色模型输出）", [(row["wrong_pairs"], red)]),
    ]
    canvas = Image.new("RGB", (WIDTH, HEIGHT * len(panels)), "white")
    for index, panel in enumerate(panels):
        canvas.paste(panel, (0, index * HEIGHT))
    canvas.save(path, quality=92)


def _public_row(row: dict[str, Any]) -> dict[str, Any]:
    public = {}
    for key, value in row.items():
        if key in {"correct_pairs", "wrong_pairs", "score"}:
            continue
        if isinstance(value, Path):
            try:
                value = value.relative_to(ROOT)
            except ValueError:
                pass
            value = value.as_posix()
        public[key] = value
    return public


def _write_html(rows: list[dict[str, Any]], output_dir: Path) -> None:
    items = []
    for row in rows:
        item = _public_row(row)
        item["preview"] = f"previews/{row['review_id']}.jpg?v={row['preview_sha256'][:12]}"
        item["image_href"] = "../../" + item["image_path"]
        items.append(item)
    payload = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    options = "".join(f'<option value="{html.escape(value)}">{OPTION_LABELS[value]}</option>' for value in SCREEN_STRATA)
    option_labels = json.dumps(OPTION_LABELS, ensure_ascii=False)
    page = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>不确定性实验候选 Batch 1 研究者审核</title>
<style>
body{{font-family:system-ui,sans-serif;margin:0;background:#f4f6f8;color:#17202a}}header{{position:sticky;top:0;z-index:2;background:#fff;padding:14px 20px;border-bottom:1px solid #ccd3da}}main{{max-width:1180px;margin:auto;padding:18px}}.notice{{background:#fff4ce;border:1px solid #e2bd55;padding:12px;margin:12px 0}}.controls{{display:flex;gap:10px;flex-wrap:wrap;align-items:center}}button,select,input,textarea{{font:inherit}}button{{padding:7px 12px}}.card{{background:#fff;border:1px solid #ccd3da;border-radius:8px;margin:16px 0;padding:14px}}.card img{{width:100%;height:auto;border:1px solid #ddd}}.meta{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:5px 16px;font-size:13px;margin:8px 0}}.form{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}}label{{display:flex;flex-direction:column;gap:4px;font-size:13px}}fieldset{{margin:0;border:1px solid #9da8b2;border-radius:4px}}.checks{{display:grid;gap:6px;margin-top:6px}}label.check{{display:flex;flex-direction:row;align-items:flex-start;gap:7px}}textarea{{min-height:64px}}.hidden{{display:none}}code{{word-break:break-all}}.pass{{border-left:7px solid #27864a}}.revise{{border-left:7px solid #d39b19}}.reject{{border-left:7px solid #b33a3a}}
</style></head><body>
<header><strong>候选 Batch 1 研究者审核 v3</strong>　<span id="progress"></span><div class="controls"><select id="roleFilter"><option value="">全部角色</option><option value="main">主候选</option><option value="reserve">备用候选</option></select><select id="splitFilter"><option value="">全部数据集</option><option value="test">Test</option><option value="validation">Validation</option></select><select id="stratumFilter"><option value="">全部机械筛选层</option>{options}</select><select id="decisionFilter"><option value="">全部决定</option><option value="PASS">通过</option><option value="REVISE">修改后再审</option><option value="REJECT">排除</option></select><button id="export">导出审核 JSON（允许未完成）</button></div></header>
<main><div class="notice"><b>不是正式 Batch 1，也不是 R_vis。</b> 每张预览从上到下依次为：无标线原图、仅绿色 Correct 候选、仅红色 Wrong 候选。机械筛选层只描述 mask 方向或角点对数量变化，不是错误真值。请多选全部实际缺陷，再从已选项中指定主要缺陷；修复动作和结构有效性单独记录。</div><div id="cards"></div></main>
<script>
const items={payload}; const key='annotation-uncertainty-'+(items[0]?.review_id.split('-')[0]||'review'); const saved=JSON.parse(localStorage.getItem(key)||'{{}}');
const defectOptions={json.dumps(list(DEFECTS), ensure_ascii=False)};
const repairOptions={json.dumps(list(REPAIR_ACTIONS), ensure_ascii=False)};
const optionLabels={option_labels};
function field(label,name,opts){{return `<label>${{label}}<select data-name="${{name}}"><option value="">请选择</option>${{opts.map(x=>`<option value="${{x}}">${{optionLabels[x]||x}}</option>`).join('')}}</select></label>`}}
function multiField(label,name,opts){{return `<fieldset><legend>${{label}}（可多选）</legend><div class="checks">${{opts.map(x=>`<label class="check"><input type="checkbox" data-name="${{name}}" value="${{x}}">${{optionLabels[x]||x}}</label>`).join('')}}</div></fieldset>`}}
function render(){{const root=document.getElementById('cards');root.innerHTML='';for(const x of items){{const s=saved[x.review_id]||{{}};const card=document.createElement('section');card.className='card '+(s.decision||'').toLowerCase();card.dataset.role=x.candidate_role;card.dataset.split=x.split;card.dataset.stratum=x.screen_stratum;card.dataset.decision=s.decision||'';card.innerHTML=`<h2>${{x.review_id}} · ${{optionLabels[x.candidate_role]}} · <code>${{x.image_id}}</code></h2><a href="${{x.image_href}}"><img loading="lazy" src="${{x.preview}}" alt="${{x.image_id}}"></a><div class="meta"><span>数据集：<b>${{x.split}}</b></span><span>机械筛选层：<b>${{optionLabels[x.screen_stratum]}}</b></span><span>D_mask(C,W)：${{x.layout_mask_difference.toFixed(3)}}</span><span>边界均方根误差：${{x.boundary_rmse_px.toFixed(1)}} px</span><span>角点对 正确/错误：${{x.correct_pair_count}} / ${{x.wrong_pair_count}}</span><span>参考区域缺失比：${{x.false_negative_ratio.toFixed(3)}}</span><span>模型区域额外比：${{x.false_positive_ratio.toFixed(3)}}</span><span>建筑：${{x.building_id}}</span></div><div class="form">${{field('图片/曼哈顿资格','scope',['in_scope','revise','reject'])}}${{field('绿色参考候选能否作为 Correct-Semi','correct',['PASS','REVISE','REJECT'])}}${{field('红色 Wrong 候选是否有实质问题','wrong_material',['yes','no','uncertain'])}}${{multiField('观察到的实质缺陷','observed_defects',defectOptions)}}${{field('主要缺陷（必须来自已选缺陷）','primary_defect',defectOptions)}}${{multiField('需要的修复动作','repair_actions',repairOptions)}}${{field('修正范围','repair_extent',['local','multi_region','redraw'])}}${{field('红色 Wrong 候选结构有效性 QC','structural_validity',['structurally_valid','structurally_invalid','uncertain'])}}${{field('红色 Wrong 候选刺激纯度','stimulus_purity',['single','dominant_with_secondary','mixed'])}}${{field('红色 Wrong 候选错误严重度','severity',['too_light','moderate','too_heavy'])}}${{field('整组候选最终决定','decision',['PASS','REVISE','REJECT'])}}<label>备注<textarea data-name="notes"></textarea></label></div>`;for(const el of card.querySelectorAll('[data-name]')){{const old=s[el.dataset.name];if(el.type==='checkbox')el.checked=Array.isArray(old)&&old.includes(el.value);else el.value=old||'';el.addEventListener('change',()=>{{saved[x.review_id]=saved[x.review_id]||{{}};saved[x.review_id][el.dataset.name]=el.type==='checkbox'?[...card.querySelectorAll(`input[type="checkbox"][data-name="${{el.dataset.name}}"]:checked`)].map(o=>o.value):el.value;localStorage.setItem(key,JSON.stringify(saved));if(el.dataset.name==='decision'){{card.dataset.decision=el.value;card.className='card '+el.value.toLowerCase()}}progress();filter();}})}}root.appendChild(card)}}filter();progress()}}
function filter(){{const role=document.getElementById('roleFilter').value;const split=document.getElementById('splitFilter').value;const stratum=document.getElementById('stratumFilter').value;const decision=document.getElementById('decisionFilter').value;for(const c of document.querySelectorAll('.card')){{c.classList.toggle('hidden',(role&&c.dataset.role!==role)||(split&&c.dataset.split!==split)||(stratum&&c.dataset.stratum!==stratum)||(decision&&c.dataset.decision!==decision))}}}}
function progress(){{const done=items.filter(x=>saved[x.review_id]?.decision).length;document.getElementById('progress').textContent=`已决定 ${{done}} / ${{items.length}}`}}
for(const id of ['roleFilter','splitFilter','stratumFilter','decisionFilter'])document.getElementById(id).addEventListener('change',filter);
document.getElementById('export').addEventListener('click',()=>{{const validationWarnings=items.filter(x=>{{const s=saved[x.review_id]||{{}};const defects=s.observed_defects||[];const repairs=s.repair_actions||[];const baseMissing=!s.scope||!s.correct||!s.wrong_material||!s.structural_validity||!s.decision;const positiveInvalid=s.wrong_material==='yes'&&(!defects.length||!defects.includes(s.primary_defect)||!repairs.length||!s.repair_extent||!s.stimulus_purity||!s.severity);const negativeConflict=s.wrong_material==='no'&&(defects.length||s.primary_defect||repairs.length||s.repair_extent);return baseMissing||positiveInvalid||negativeConflict}}).map(x=>x.review_id);const blob=new Blob([JSON.stringify({{schema_version:'annotation_uncertainty_batch1_researcher_review_v3',exported_at:new Date().toISOString(),validation_warnings:validationWarnings,items:items.map(x=>({{...x,review:saved[x.review_id]||{{}}}}))}},null,2)],{{type:'application/json'}});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='batch1_researcher_review_v3.json';a.click();URL.revokeObjectURL(a.href)}});render();
</script></body></html>"""
    (output_dir / "review.html").write_text(page, encoding="utf-8")


def build(
    metrics_path: Path,
    output_dir: Path,
    *,
    main_per_stratum: int = 6,
    reserve_per_stratum: int = 1,
    main_count_by_stratum: dict[str, int] | None = None,
    excluded_image_ids: set[str] | None = None,
    review_prefix: str = "B1",
    broad_review_range: bool = False,
) -> None:
    with metrics_path.open(encoding="utf-8-sig", newline="") as handle:
        candidates = [item for row in csv.DictReader(handle) if (item := _measure(row)) is not None]
    main_counts = main_count_by_stratum or {stratum: main_per_stratum for stratum in SCREEN_STRATA}
    excluded = excluded_image_ids or set()
    if broad_review_range:
        selected = select_broad_review_range(
            candidates,
            excluded_image_ids=excluded,
            review_prefix=review_prefix,
        )
    else:
        selected = select_balanced(
            candidates,
            main_per_stratum=main_per_stratum,
            reserve_per_stratum=reserve_per_stratum,
            main_count_by_stratum=main_counts,
            excluded_image_ids=excluded,
            review_prefix=review_prefix,
        )
    preview_dir = output_dir / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    for row in selected:
        preview = preview_dir / f"{row['review_id']}.jpg"
        _render_preview(row, preview)
        row["preview_sha256"] = _sha256(preview)
    public_rows = [_public_row(row) for row in selected]
    actual_main_counts = {
        stratum: sum(row["candidate_role"] == "main" and row["screen_stratum"] == stratum for row in selected)
        for stratum in SCREEN_STRATA
    }
    split_counts = dict(Counter(row["split"] for row in selected))
    gt_source_counts = dict(Counter(row["gt_source_type"] for row in selected))
    (output_dir / "candidate_manifest.json").write_text(json.dumps({
        "schema_version": "annotation_uncertainty_batch1_candidate_review_v3",
        "status": "researcher_review_candidate_not_frozen_not_worker_facing",
        "source_metrics": metrics_path.relative_to(ROOT).as_posix(),
        "source_metrics_role": "derived_candidate_screen_only_not_formal_truth",
        "selection_mode": "broad_objective_review_range" if broad_review_range else "balanced_mechanical_sample",
        "review_limits": BROAD_REVIEW_LIMITS if broad_review_range else None,
        "main_count": sum(row["candidate_role"] == "main" for row in selected),
        "reserve_count": sum(row["candidate_role"] == "reserve" for row in selected),
        "main_count_by_stratum": actual_main_counts,
        "split_counts": split_counts,
        "gt_source_counts": gt_source_counts,
        "excluded_image_ids": sorted(excluded),
        "review_prefix": review_prefix,
        "screen_strata": list(SCREEN_STRATA),
        "defect_options": list(DEFECTS),
        "screen_rule": "mechanical_candidate_coverage_only_not_semantic_truth",
        "items": public_rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_html(selected, output_dir)
    mode_note = (
        f"本包从 Test 与 Validation 共同候选池按可复核的中等差异带宽筛选{len(selected)}张"
        f"（Test {split_counts.get('test', 0)}、Validation {split_counts.get('validation', 0)}）；"
        "不设建筑数量上限，不使用 AI 视觉结论自动删图。已审核图片只为避免研究者重复操作而排除，"
        "正式分发才按实际参加者执行worker × image历史暴露去重。AI初筛起点另见 `AI_INITIAL_SUGGESTIONS.md`。\n"
        if broad_review_range else ""
    )
    (output_dir / "README.md").write_text(
        "# 候选 Batch 1 研究者审核包\n\n"
        "打开 `review.html` 逐图审核。每张预览从上到下分别是无标线原图、仅绿色 Correct 候选、仅红色 Wrong 候选；"
        "机械筛选层不是错误真值。v3审核记录全部观察缺陷、主要缺陷、修复动作、刺激纯度和结构QC；"
        "本包未分发、未冻结，不进入正式实验。审核 JSON 允许在字段未完成时导出，并在 `validation_warnings` 保留对应编号。\n"
        + mode_note,
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", type=Path, default=ROOT / "analysis_results/model_initialization_audit_hybrid_gt_20260823_v4/model_initialization_metrics.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "analysis_results/annotation_uncertainty_batch1_candidate_review_20260827_v2")
    parser.add_argument("--exclude-review-json", type=Path)
    parser.add_argument("--exclude-image-id", action="append", default=[])
    parser.add_argument("--main-counts", type=int, nargs=len(SCREEN_STRATA), metavar=tuple(SCREEN_STRATA))
    parser.add_argument("--reserve-per-stratum", type=int, default=1)
    parser.add_argument("--review-prefix", default="B1")
    parser.add_argument("--broad-review-range", action="store_true")
    args = parser.parse_args()
    excluded: set[str] = set()
    if args.exclude_review_json:
        payload = json.loads(args.exclude_review_json.read_text(encoding="utf-8"))
        excluded = {item["image_id"] for item in payload["items"]}
    excluded.update(args.exclude_image_id)
    main_counts = dict(zip(SCREEN_STRATA, args.main_counts)) if args.main_counts else None
    build(
        args.metrics.resolve(),
        args.output_dir.resolve(),
        reserve_per_stratum=args.reserve_per_stratum,
        main_count_by_stratum=main_counts,
        excluded_image_ids=excluded,
        review_prefix=args.review_prefix,
        broad_review_range=args.broad_review_range,
    )


if __name__ == "__main__":
    main()
