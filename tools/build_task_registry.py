import argparse
import csv
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMPORT_DIR = PROJECT_ROOT / "import_json" / "outline_v2_seed20260228"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "analysis_results" / "registry_20260308"


STAGE_METADATA = {
    "stage0_pilot_manual": {
        "planned_stage": "pilot_manual",
        "planned_condition": "manual",
        "source_pool": "pilot_manual",
    },
    "stage1_prescreen_manual": {
        "planned_stage": "prescreen_manual",
        "planned_condition": "manual",
        "source_pool": "prescreen_manual",
    },
    "stage1_prescreen_manual_anchor": {
        "planned_stage": "prescreen_manual",
        "planned_condition": "manual",
        "source_pool": "prescreen_manual_anchor",
    },
    "stage1_prescreen_semi": {
        "planned_stage": "prescreen_semi",
        "planned_condition": "semi",
        "source_pool": "prescreen_semi",
    },
    "stage2_calibration_manual": {
        "planned_stage": "calibration_manual",
        "planned_condition": "manual",
        "source_pool": "calibration_manual_pool",
    },
    "stage2_calibration_anchor": {
        "planned_stage": "calibration_manual",
        "planned_condition": "manual",
        "source_pool": "calibration_anchor",
    },
    "stage2_calibration_core": {
        "planned_stage": "calibration_manual",
        "planned_condition": "manual",
        "source_pool": "calibration_core",
    },
    "stage2_calibration_reserve": {
        "planned_stage": "calibration_manual",
        "planned_condition": "manual",
        "source_pool": "calibration_reserve",
    },
    "stage2_calibration_semi": {
        "planned_stage": "calibration_semi",
        "planned_condition": "semi",
        "source_pool": "calibration_semi",
    },
    "stage3_manual_test": {
        "planned_stage": "manual_test",
        "planned_condition": "manual",
        "source_pool": "manual_test",
    },
    "stage3_semiauto_test": {
        "planned_stage": "semiauto_test",
        "planned_condition": "semi",
        "source_pool": "semiauto_test",
    },
    "stage3_validation_semi": {
        "planned_stage": "validation_semi",
        "planned_condition": "semi",
        "source_pool": "validation_semi",
    },
    "stage3_gold_manual": {
        "planned_stage": "gold_manual",
        "planned_condition": "manual",
        "source_pool": "gold_manual",
    },
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a planned task registry from split import JSON files.")
    parser.add_argument("--import-dir", default=str(DEFAULT_IMPORT_DIR), help="Directory containing split import JSON files")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory to save registry outputs")
    parser.add_argument("--registry-name", default="task_registry_v1.csv", help="Registry CSV filename")
    parser.add_argument("--summary-name", default="task_registry_summary_v1.json", help="Summary JSON filename")
    return parser


def infer_base_task_id(title: str, image_url: str) -> str:
    candidate = (title or "").strip()
    if not candidate and image_url:
        candidate = Path(image_url).name
    if not candidate:
        return ""
    return Path(candidate).stem


def normalize_title_key(title: str, image_url: str = "") -> str:
    candidate = (title or "").strip()
    if not candidate and image_url:
        candidate = Path(image_url).name
    if not candidate:
        return ""
    return Path(candidate).stem.lower()


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def infer_is_anchor(output_key: str, dataset_group: str, data: dict) -> bool:
    if parse_bool(data.get("is_anchor")):
        return True
    if output_key in {"stage1_prescreen_manual_anchor", "stage2_calibration_anchor"}:
        return True
    return dataset_group in {"Calibration_anchor"}


def infer_has_expert_ref(output_key: str, is_anchor: bool, data: dict) -> bool:
    if parse_bool(data.get("has_expert_ref")):
        return True
    return output_key == "stage1_prescreen_manual_anchor" and is_anchor


def get_stage_key_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    if stem.endswith("_import"):
        stem = stem[: -len("_import")]
    return stem


def build_registry(import_dir: Path) -> tuple[list[dict], dict]:
    split_report_path = import_dir / "label_studio_split_report_v2.json"
    split_report = load_json(split_report_path)
    seed = split_report.get("seed")
    outputs = split_report.get("outputs", {})
    overlap_constraints = split_report.get("overlap_constraints", {})

    rows: list[dict] = []
    seen_keys: set[tuple[str, str, int]] = set()

    for output_key, filename in outputs.items():
        stage_meta = STAGE_METADATA.get(output_key, {})
        json_path = import_dir / filename
        if not json_path.exists():
            continue
        payload = load_json(json_path)
        if not isinstance(payload, list):
            continue
        for index, task in enumerate(payload, start=1):
            data = task.get("data", {}) if isinstance(task, dict) else {}
            title = str(data.get("title") or "").strip()
            image = str(data.get("image") or "").strip()
            dataset_group = str(data.get("dataset_group") or "").strip()
            init_type = str(data.get("init_type") or "").strip()
            is_anchor = infer_is_anchor(output_key, dataset_group, data)
            has_expert_ref = infer_has_expert_ref(output_key, is_anchor, data)
            base_task_id = infer_base_task_id(title, image)
            has_prediction = bool(task.get("predictions"))
            task_key = (filename, base_task_id, index)
            if task_key in seen_keys:
                continue
            seen_keys.add(task_key)
            rows.append(
                {
                    "registry_uid": f"{output_key}:{index}",
                    "planned_task_key": f"{output_key}:{base_task_id}:{index}",
                    "base_task_id": base_task_id,
                    "normalized_title": normalize_title_key(title, image),
                    "title": title,
                    "image": image,
                    "planned_stage": stage_meta.get("planned_stage", ""),
                    "condition": stage_meta.get("planned_condition", ""),
                    "planned_condition": stage_meta.get("planned_condition", ""),
                    "dataset_group": dataset_group,
                    "is_anchor": is_anchor,
                    "has_expert_ref": has_expert_ref,
                    "init_type": init_type,
                    "source_pool": stage_meta.get("source_pool", output_key),
                    "manifest_file": filename,
                    "manifest_stage_key": output_key,
                    "import_index": index,
                    "has_prediction": has_prediction,
                    "seed": seed,
                }
            )

    rows.sort(key=lambda row: (row["planned_stage"], row["dataset_group"], row["base_task_id"], row["import_index"]))

    summary = {
        "import_dir": str(import_dir.resolve()),
        "seed": seed,
        "row_count": len(rows),
        "unique_base_task_ids": len({row["base_task_id"] for row in rows}),
        "counts_by_planned_stage": {},
        "counts_by_dataset_group": {},
        "counts_by_condition": {},
        "anchor_row_count": 0,
        "expert_ref_row_count": 0,
        "prediction_row_count": 0,
        "overlap_constraints": overlap_constraints,
        "notes": [
            "task_registry is a planned split registry keyed by split manifests.",
            "runtime Label Studio task_id is not available until export-side join."
        ],
    }

    for row in rows:
        summary["counts_by_planned_stage"][row["planned_stage"]] = summary["counts_by_planned_stage"].get(row["planned_stage"], 0) + 1
        summary["counts_by_dataset_group"][row["dataset_group"]] = summary["counts_by_dataset_group"].get(row["dataset_group"], 0) + 1
        summary["counts_by_condition"][row["planned_condition"]] = summary["counts_by_condition"].get(row["planned_condition"], 0) + 1
        summary["anchor_row_count"] += int(bool(row["is_anchor"]))
        summary["expert_ref_row_count"] += int(bool(row["has_expert_ref"]))
        summary["prediction_row_count"] += int(bool(row["has_prediction"]))

    return rows, summary


def write_csv(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        output_path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    import_dir = Path(args.import_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    rows, summary = build_registry(import_dir)

    registry_path = output_dir / args.registry_name
    summary_path = output_dir / args.summary_name
    write_csv(rows, registry_path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[task-registry] rows: {len(rows)}")
    print(f"[task-registry] registry: {registry_path}")
    print(f"[task-registry] summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())