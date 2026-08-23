from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.thesis_main.analysis.materialize_model_gt_threshold_screen import (
    _boundary_rmse_from_pairs,
    _pairs,
    _read_test_gt,
    _read_txt,
    _write_csv,
)
from tools.thesis_main.analysis.quality_core.geometry_metrics import (
    _interp_periodic,
    compute_layout_mask_iou_from_normalized_pairs,
)


COLORS = {
    "model": (230, 45, 45),
    "adopted": (35, 190, 90),
    "mp3d": (45, 115, 230),
    "no_occ": (240, 155, 35),
}


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _difference(a: list[dict[str, float]], b: list[dict[str, float]]) -> tuple[float, float]:
    iou, meta = compute_layout_mask_iou_from_normalized_pairs(a, b, width=1024, height=512)
    if iou is None:
        raise ValueError(f"layout mask difference failed: {meta}")
    return 1.0 - iou, _boundary_rmse_from_pairs(a, b)


def _draw_geometry(draw: ImageDraw.ImageDraw, pairs: list[dict[str, float]], color: tuple[int, int, int], width: int = 3) -> None:
    xs = np.asarray([pair["x"] for pair in pairs], dtype=float)
    top = _interp_periodic(xs, np.asarray([pair["y_ceiling"] for pair in pairs], dtype=float), 1024)
    floor = _interp_periodic(xs, np.asarray([pair["y_floor"] for pair in pairs], dtype=float), 1024)
    draw.line([(x, float(top[x])) for x in range(1024)], fill=color, width=width)
    draw.line([(x, float(floor[x])) for x in range(1024)], fill=color, width=width)
    for pair in pairs:
        x = float(pair["x"])
        draw.line([(x, pair["y_ceiling"]), (x, pair["y_floor"])], fill=color, width=width)


def _panel(image: Image.Image, series: list[tuple[str, list[dict[str, float]]]]) -> Image.Image:
    panel = image.resize((1024, 512)).convert("RGB")
    draw = ImageDraw.Draw(panel)
    for label, pairs in series:
        _draw_geometry(draw, pairs, COLORS[label])
    x = 8
    font = _font(18)
    for label, _pairs_value in series:
        text = {"model": "Model", "adopted": "Adopted GT", "mp3d": "MP3D original", "no_occ": "HoHoNet no-occ"}[label]
        box = draw.textbbox((0, 0), text, font=font)
        text_width = box[2] - box[0]
        draw.rectangle((x - 3, 5, x + text_width + 5, 31), fill=(20, 20, 20))
        draw.text((x, 7), text, fill=COLORS[label], font=font)
        x += text_width + 18
    return panel


def _sample_strip(row: dict[str, Any], image: Image.Image, *, threshold: float) -> Image.Image:
    panels = [
        _panel(image, [("model", row["model_pairs"]), ("adopted", row["adopted_pairs"])]),
        _panel(image, [("mp3d", row["mp3d_pairs"]), ("no_occ", row["no_occ_pairs"])]),
        _panel(image, [("adopted", row["adopted_pairs"]), ("no_occ", row["no_occ_pairs"])]),
    ]
    canvas = Image.new("RGB", (3072, 562), (245, 245, 245))
    title = (
        f"{row['split']} | {row['image_id']} | threshold={threshold:.2f} | "
        f"diff adopted/mp3d/no-occ={row['adopted_difference']:.4f}/{row['mp3d_difference']:.4f}/{row['no_occ_difference']:.4f} | "
        f"pairs model/adopted/mp3d/no-occ="
        f"{row['model_pair_count']}/{row['adopted_pair_count']}/{row['mp3d_pair_count']}/{row['no_occ_pair_count']}"
    )
    ImageDraw.Draw(canvas).text((10, 12), title, fill=(20, 20, 20), font=_font(22))
    for index, panel in enumerate(panels):
        canvas.paste(panel, (index * 1024, 50))
    return canvas


def materialize(
    *, output_dir: Path, thresholds: tuple[float, ...] = (0.05, 0.10, 0.20, 0.30),
    test_gt: Path = ROOT / "export_label/groudTruth.json",
    test_model_dir: Path = ROOT / "output/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34",
    test_mp3d_dir: Path = ROOT / "data/mp3d_layout/test/label_cor",
    test_no_occ_dir: Path = ROOT / "data/mp3d_layout/test_no_occ/label_cor",
    test_image_dir: Path = ROOT / "data/mp3d_layout/test/img",
    validation_model_dir: Path = ROOT / "analysis_results/c2b_validation_static_20260802_v16/validation_prediction_txt",
    validation_mp3d_dir: Path = ROOT / "data/mp3d_layout/valid/label_cor",
    validation_no_occ_dir: Path = ROOT / "data/mp3d_layout/valid_no_occ/label_cor",
    validation_image_dir: Path = ROOT / "data/mp3d_layout/valid_no_occ/img",
    validation_registry: Path = ROOT / "analysis_results/c2a_rp_local_launch_20260807_inputs_v2/reference_registry_post_c2_local.csv",
) -> dict[str, Any]:
    test_adopted = _read_test_gt(test_gt)
    registry_rows = list(csv.DictReader(validation_registry.open(encoding="utf-8-sig", newline="")))
    validation_ready = {
        row["image_id"] for row in registry_rows
        if str(row.get("geometry_reference_ready", "")).lower() == "true"
    }
    rows: list[dict[str, Any]] = []

    def append(split: str, image_id: str, adopted_points: Any, adopted_ordered: bool, model_path: Path,
               mp3d_path: Path, no_occ_path: Path, image_path: Path) -> None:
        model_pairs = _pairs(_read_txt(model_path), source=model_path, ordered_source=True)
        adopted_pairs = _pairs(adopted_points, source=test_gt if split == "test" else no_occ_path, ordered_source=adopted_ordered)
        mp3d_pairs = _pairs(_read_txt(mp3d_path), source=mp3d_path, ordered_source=True)
        no_occ_pairs = _pairs(_read_txt(no_occ_path), source=no_occ_path, ordered_source=True)
        adopted_difference, adopted_rmse = _difference(model_pairs, adopted_pairs)
        mp3d_difference, _ = _difference(model_pairs, mp3d_pairs)
        no_occ_difference, _ = _difference(model_pairs, no_occ_pairs)
        model_n, adopted_n, mp3d_n, no_occ_n = map(len, (model_pairs, adopted_pairs, mp3d_pairs, no_occ_pairs))
        rows.append({
            "split": split, "image_id": image_id, "image_path": image_path.as_posix(),
            "model_pair_count": model_n, "adopted_pair_count": adopted_n,
            "mp3d_pair_count": mp3d_n, "no_occ_pair_count": no_occ_n,
            "model_vs_adopted_topology_mismatch": model_n != adopted_n,
            "model_vs_mp3d_topology_mismatch": model_n != mp3d_n,
            "model_vs_no_occ_topology_mismatch": model_n != no_occ_n,
            "adopted_vs_mp3d_topology_mismatch": adopted_n != mp3d_n,
            "adopted_vs_no_occ_topology_mismatch": adopted_n != no_occ_n,
            "mp3d_vs_no_occ_topology_mismatch": mp3d_n != no_occ_n,
            "adopted_difference": adopted_difference, "adopted_boundary_rmse_px": adopted_rmse,
            "mp3d_difference": mp3d_difference, "no_occ_difference": no_occ_difference,
            "adopted_mismatch_resolved_by_mp3d_count": model_n != adopted_n and model_n == mp3d_n,
            "adopted_mismatch_resolved_by_no_occ_count": model_n != adopted_n and model_n == no_occ_n,
            "model_pairs": model_pairs, "adopted_pairs": adopted_pairs,
            "mp3d_pairs": mp3d_pairs, "no_occ_pairs": no_occ_pairs,
        })

    test_ids = set(test_adopted)
    expected_test = {path.stem for path in test_model_dir.glob("*.txt")}
    if test_ids != expected_test:
        raise ValueError("test identities differ")
    for image_id in sorted(test_ids):
        append(
            "test", image_id, test_adopted[image_id], False, test_model_dir / f"{image_id}.txt",
            test_mp3d_dir / f"{image_id}.txt", test_no_occ_dir / f"{image_id}.txt", test_image_dir / f"{image_id}.png",
        )
    validation_ids = {path.stem for path in validation_model_dir.glob("*.txt")}
    if validation_ids != {row["image_id"] for row in registry_rows}:
        raise ValueError("validation identities differ")
    for image_id in sorted(validation_ready):
        no_occ_path = validation_no_occ_dir / f"{image_id}.txt"
        append(
            "validation", image_id, _read_txt(no_occ_path), True, validation_model_dir / f"{image_id}.txt",
            validation_mp3d_dir / f"{image_id}.txt", no_occ_path, validation_image_dir / f"{image_id}.png",
        )

    csv_rows = [{key: value for key, value in row.items() if not key.endswith("_pairs")} for row in rows]
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "gt_variant_attribution.csv", csv_rows, list(csv_rows[0]))

    summary = []
    bool_fields = [key for key, value in csv_rows[0].items() if isinstance(value, bool)]
    for split in ("test", "validation"):
        subset = [row for row in csv_rows if row["split"] == split]
        for field in bool_fields:
            summary.append({"split": split, "criterion": field, "count": sum(bool(row[field]) for row in subset), "denominator": len(subset)})
    _write_csv(output_dir / "gt_variant_summary.csv", summary, list(summary[0]))

    selections = []
    used: dict[tuple[str, bool], set[str]] = {(split, topology): set() for split in ("test", "validation") for topology in (False, True)}
    sheets = []
    for threshold in thresholds:
        strips = []
        for split in ("test", "validation"):
            subset = [row for row in rows if row["split"] == split]
            for topology in (False, True):
                pool = [row for row in subset if bool(row["model_vs_adopted_topology_mismatch"]) == topology]
                above = [row for row in pool if row["adopted_difference"] >= threshold and row["image_id"] not in used[(split, topology)]]
                if above:
                    chosen = min(above, key=lambda row: (row["adopted_difference"] - threshold, row["image_id"]))
                    status = "nearest_at_or_above_threshold"
                else:
                    continue
                used[(split, topology)].add(chosen["image_id"])
                selections.append({
                    "threshold": threshold, "split": split, "topology_mismatch": topology,
                    "selection_status": status, "image_id": chosen["image_id"],
                    "adopted_difference": round(chosen["adopted_difference"], 8),
                    "image_path": chosen["image_path"],
                })
                with Image.open(chosen["image_path"]) as image:
                    strips.append(_sample_strip(chosen, image, threshold=threshold))
        sheet = Image.new("RGB", (3072, len(strips) * 562), (235, 235, 235))
        for index, strip in enumerate(strips):
            sheet.paste(strip, (0, index * 562))
        sheet_path = output_dir / f"comparison_threshold_{str(threshold).replace('.', '_')}.png"
        sheet.save(sheet_path)
        sheets.append(sheet_path.as_posix())
    _write_csv(output_dir / "comparison_selection.csv", selections, list(selections[0]))

    summary_counts = {
        split: {field: sum(bool(row[field]) for row in csv_rows if row["split"] == split) for field in bool_fields}
        for split in ("test", "validation")
    }
    manifest = {
        "schema_version": "model_gt_variant_comparison_v1",
        "test_count": len(test_ids), "validation_evaluable_count": len(validation_ready),
        "validation_reference_unavailable_count": len(validation_ids - validation_ready),
        "thresholds": list(thresholds), "summary_counts": summary_counts,
        "comparison_sheets": sheets,
        "interpretation_limit": "pair-count equality attributes topology only; it does not prove geometric correctness",
    }
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(materialize(output_dir=args.output_dir), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
