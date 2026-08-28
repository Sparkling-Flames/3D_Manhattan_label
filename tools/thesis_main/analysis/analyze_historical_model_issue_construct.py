from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.prescreen_worker_gold_alignment_audit import (
    _load_final_gold,
    _load_source_gt_from_scope_summary,
    _reference_points,
)
from tools.thesis_main.analysis.quality_core.geometry_metrics import _interp_periodic
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_json

DEFAULT_OUT = ROOT / "analysis_results" / "historical_model_issue_construct_validation_20260827_v1"
FACT = ROOT / "analysis_results" / "uncertainty_substrate_20260823_v1" / "proposal_fact.csv"
RESPONSES = ROOT / "analysis_results" / "uncertainty_substrate_20260823_v1" / "proposal_response.csv"
FINAL_GOLD = ROOT / "analysis_results" / "prescreen_closeout_final_gold_v2_20260701" / "final_gold_records_v2_p1_closeout_corrected.jsonl"
GOLD_STATUS = ROOT / "analysis_results" / "prescreen_closeout_final_gold_v2_20260701" / "prescreen_gold_status_audit.csv"
SYNTHETIC_BINDING = ROOT / "analysis_results" / "prescreen_closeout_final_gold_v2_20260701" / "prescreen_synthetic_geometry_gt_binding_audit.csv"
SCOPE_SUMMARY = ROOT / "analysis_results" / "prescreen_closeout_final_gold_v2_20260701" / "prescreen_scope_summary.json"
SEMI_REVIEW_FACT = ROOT / "analysis_results" / "full_uncertainty_data_mining_20260821_v5" / "SEMI_REVIEW_FACT.csv"

WIDTH = 1024
HEIGHT = 512
LABELS = (
    "acceptable",
    "corner_drift",
    "corner_duplicate",
    "over_parsing",
    "overextend_adjacent",
    "underextend",
    "topology_failure",
    "fail",
)
ISSUES = tuple(value for value in LABELS if value != "acceptable")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _choice_set(value: str) -> set[str]:
    parsed = json.loads(value or "[]")
    return {str(item) for item in parsed}


def aggregate_p1(
    fact_rows: list[dict[str, str]], response_rows: list[dict[str, str]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    facts = {row["proposal_id"]: row for row in fact_rows if row["stage"] == "P1"}
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in response_rows:
        if row["stage"] == "P1" and row["proposal_id"] in facts:
            grouped[row["proposal_id"]].append(row)

    images: list[dict[str, Any]] = []
    for proposal_id, fact in sorted(facts.items(), key=lambda item: item[1]["image_id"]):
        rows = grouped[proposal_id]
        workers = {row["worker_id"] for row in rows}
        if len(rows) != 26 or len(workers) != 26:
            raise ValueError(f"P1 support drift for {proposal_id}: rows={len(rows)}, workers={len(workers)}")
        truth_set = _choice_set(fact["trap_family_set_json"])
        planned_set = _choice_set(fact["planned_trap_family_set_json"])
        if len(truth_set) != 1:
            raise ValueError(f"P1 realized truth is not singleton for {proposal_id}: {sorted(truth_set)}")
        truth = next(iter(truth_set))
        choices = [_choice_set(row["model_issue_choice_set_json"]) for row in rows]
        counts = Counter(label for selected in choices for label in selected)
        issue_multi = sum(len(selected & set(ISSUES)) >= 2 for selected in choices)
        any_multi = sum(len(selected) >= 2 for selected in choices)
        conflict = sum("acceptable" in selected and bool(selected & set(ISSUES)) for selected in choices)
        issue_rates = sorted(((counts[label] / len(rows), label) for label in ISSUES), reverse=True)
        top_rate, top_label = issue_rates[0]
        second_rate, second_label = issue_rates[1]
        if truth == "acceptable" and counts["acceptable"] / len(rows) >= .75:
            pattern = "stable_acceptable"
        elif top_rate >= .50 and second_rate <= .25 and top_rate - second_rate >= .25 and issue_multi / len(rows) <= .35:
            pattern = "single_dominant_issue"
        elif issue_multi / len(rows) >= .45 and sum(rate >= .25 for rate, _ in issue_rates) >= 2:
            pattern = "stable_mixed_issue"
        else:
            pattern = "boundary_or_other"
        image = {
            "proposal_id": proposal_id,
            "image_id": fact["image_id"],
            "building_id": fact["building_id"],
            "initial_geometry_hash": fact["initial_geometry_hash"],
            "initial_points_json": fact["initial_points_json"],
            "initialization_source_kind": fact["initialization_source_kind"],
            "reference_sha256_set_json": fact["reference_sha256_set_json"],
            "reference_type_set_json": fact["reference_type_set_json"],
            "planned_truth": ";".join(sorted(planned_set)),
            "realized_truth": truth,
            "planned_truth_changed": planned_set != truth_set,
            "response_count": len(rows),
            "worker_count": len(workers),
            "exact_truth_set_count": sum(selected == truth_set for selected in choices),
            "truth_selected_count": counts[truth],
            "any_multi_choice_count": any_multi,
            "multi_issue_count": issue_multi,
            "acceptable_issue_conflict_count": conflict,
            "top_issue": top_label,
            "top_issue_rate": top_rate,
            "second_issue": second_label,
            "second_issue_rate": second_rate,
            "response_pattern": pattern,
        }
        for label in LABELS:
            image[f"{label}_count"] = counts[label]
            image[f"{label}_rate"] = counts[label] / len(rows)
        images.append(image)

    families: list[dict[str, Any]] = []
    for truth in sorted({row["realized_truth"] for row in images}):
        rows = [row for row in images if row["realized_truth"] == truth]
        responses = sum(row["response_count"] for row in rows)
        families.append({
            "realized_truth": truth,
            "image_count": len(rows),
            "response_count": responses,
            "exact_truth_set_rate": sum(row["exact_truth_set_count"] for row in rows) / responses,
            "truth_selected_rate": sum(row["truth_selected_count"] for row in rows) / responses,
            "any_multi_choice_rate": sum(row["any_multi_choice_count"] for row in rows) / responses,
            "multi_issue_rate": sum(row["multi_issue_count"] for row in rows) / responses,
            "acceptable_rate": sum(row["acceptable_count"] for row in rows) / responses,
            **{
                f"{label}_selected_rate": sum(row[f"{label}_count"] for row in rows) / responses
                for label in ISSUES
            },
        })
    return images, families


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _load_references(image_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, float]]]:
    gold_by_runtime = {
        (row["project_id"], row["task_id"]): row
        for row in _read_csv(GOLD_STATUS)
        if row.get("condition") == "semi"
    }
    contexts: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in _read_csv(SEMI_REVIEW_FACT):
        if row.get("stage") == "P1":
            contexts[row["base_task_id"]].add((row["project_id"], row["runtime_task_id"]))
    final_gold = _load_final_gold(FINAL_GOLD)
    synthetic_by_task = {row["runtime_task_id"]: row for row in _read_csv(SYNTHETIC_BINDING)}
    source_gt = _load_source_gt_from_scope_summary(SCOPE_SUMMARY)
    references: dict[str, list[dict[str, float]]] = {}
    for row in image_rows:
        image_id = row["image_id"]
        expected_hashes = _choice_set(row["reference_sha256_set_json"])
        observed: dict[str, list[tuple[float, float]]] = {}
        for context in sorted(contexts[image_id]):
            points, reason, _ = _reference_points(
                gold_by_runtime[context], final_gold, synthetic_by_task, source_gt
            )
            if reason:
                raise ValueError(f"frozen reference unavailable for {image_id}/{context}: {reason}")
            observed[sha256_json(points)] = points
        if set(observed) != expected_hashes or len(observed) != 1:
            raise ValueError(
                f"frozen reference hash drift for {image_id}: expected={sorted(expected_hashes)}, observed={sorted(observed)}"
            )
        normalized = normalize_geometry(next(iter(observed.values())), width=WIDTH, height=HEIGHT)
        if not normalized["valid"]:
            raise ValueError(f"frozen reference geometry invalid for {image_id}: {normalized['reason']}")
        references[image_id] = normalized["pairs"]
    return references


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = Path("C:/Windows/Fonts/msyh.ttc")
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default()


def _draw_layout(image: Image.Image, pairs: list[dict[str, float]], color: tuple[int, int, int]) -> None:
    draw = ImageDraw.Draw(image)
    xs = np.asarray([item["x"] for item in pairs], dtype=np.float32)
    for field in ("y_ceiling", "y_floor"):
        ys = _interp_periodic(xs, np.asarray([item[field] for item in pairs]), WIDTH)
        draw.line([(x, float(y)) for x, y in enumerate(ys)], fill=color, width=4)
    for item in pairs:
        x = float(item["x"]) % WIDTH
        draw.line([(x, item["y_ceiling"]), (x, item["y_floor"])], fill=color, width=4)


def _panel(source: Image.Image, title: str, pairs: list[dict[str, float]] | None, color: tuple[int, int, int]) -> Image.Image:
    panel = source.copy()
    if pairs:
        _draw_layout(panel, pairs, color)
    draw = ImageDraw.Draw(panel)
    draw.rectangle((0, 0, WIDTH, 34), fill=(0, 0, 0))
    draw.text((10, 5), title, fill=(255, 255, 255), font=_font(18))
    return panel


def _render_previews(rows: list[dict[str, Any]], output: Path) -> None:
    references = _load_references(rows)
    preview_dir = output / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    for index, row in enumerate(rows, 1):
        image_path = ROOT / "data" / "mp3d_layout" / "img_v" / f"{row['image_id']}.jpg"
        source = Image.open(image_path).convert("RGB").resize((WIDTH, HEIGHT))
        initial = normalize_geometry(json.loads(row["initial_points_json"]), width=WIDTH, height=HEIGHT)
        if not initial["valid"] or row["image_id"] not in references:
            raise ValueError(f"missing valid proposal/reference for {row['image_id']}")
        panels = (
            _panel(source, "原图", None, (0, 0, 0)),
            _panel(source, "历史 Semi 初始标注（红）", initial["pairs"], (255, 55, 55)),
            _panel(source, "冻结参考布局（绿）", references[row["image_id"]], (0, 235, 90)),
        )
        canvas = Image.new("RGB", (WIDTH, HEIGHT * len(panels)), "white")
        for panel_index, panel in enumerate(panels):
            canvas.paste(panel, (0, panel_index * HEIGHT))
        row["review_id"] = f"HMI-{index:02d}"
        row["preview"] = f"previews/{row['review_id']}.jpg"
        canvas.save(preview_dir / f"{row['review_id']}.jpg", quality=92)


def _write_html(output: Path, rows: list[dict[str, Any]]) -> None:
    cards = []
    for row in rows:
        counts = "，".join(f"{label}={row[f'{label}_count']}" for label in LABELS if row[f"{label}_count"])
        cards.append(
            f'<section><h2>{row["review_id"]} · <code>{html.escape(row["image_id"])}</code></h2>'
            f'<p>实际冻结类型：<b>{html.escape(row["realized_truth"])}</b>；计划类型：{html.escape(row["planned_truth"])}；'
            f'响应模式：{html.escape(row["response_pattern"])}；26人选择：{html.escape(counts)}</p>'
            f'<img loading="lazy" src="{html.escape(row["preview"])}" alt="{html.escape(row["image_id"])}"></section>'
        )
    page = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>P1 历史 Model Issue 构念回放</title>
<style>body{font-family:system-ui,sans-serif;max-width:1120px;margin:auto;background:#f5f6f8;color:#17202a}header,section{background:white;margin:16px;padding:16px;border:1px solid #ccd3da;border-radius:8px}img{width:100%;height:auto}code{word-break:break-all}</style></head><body>
<header><h1>P1 历史 Model Issue 构念回放</h1><p>18张图全部纳入；每张26名不同工人。计划类型不是真值，实际冻结类型来自专家复核。三幅图依次为原图、历史初始标注、冻结参考布局，不显示红绿叠加。</p></header>
""" + "\n".join(cards) + "</body></html>"
    (output / "review.html").write_text(page, encoding="utf-8")


def build(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    images, families = aggregate_p1(_read_csv(FACT), _read_csv(RESPONSES))
    _render_previews(images, output)
    _write_csv(output / "image_level_worker_label_distribution.csv", images)
    _write_csv(output / "family_level_worker_label_distribution.csv", families)
    _write_html(output, images)


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay historical P1 model-issue labels against frozen proposal truth.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    build(args.output)


if __name__ == "__main__":
    main()
