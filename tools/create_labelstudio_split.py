"""Helper to split a Label Studio import into multiple reproducible datasets.

Default behavior stays backward compatible:
    - generate the same main 100-image set for both Manual and Semi groups.

Extended behavior (recommended for the paper protocol):
    - also generate disjoint Manual calibration set (for Scheme A expert scoring)
    - optional validation set (for allocation strategy evaluation)
    - optional gold set (for adjudicated reference)

All outputs are written under an output directory with a JSON report
that records the seed and per-split item lists for full reproducibility.
"""

import argparse
import json
import random
from pathlib import Path
import os

# Kept for backward compatibility / environment conventions.
BASE_URL = os.environ.get("HOHONET_BASE_URL", "http://106.53.106.49:8000")
IMAGE_DIR_REL = "data/mp3d_layout/test/img"
PREDICTION_FILE = Path("label_studio_import_docker.json")


def _task_key(task: dict) -> str:
    data = task.get("data") or {}
    # Prefer stable human-readable key if present.
    title = data.get("title")
    if title:
        return str(title)
    image = data.get("image")
    if image:
        return str(image)
    # Fallback: deterministic JSON string (should be rare).
    return json.dumps(task, sort_keys=True, ensure_ascii=False)


def load_predictions():
    if not PREDICTION_FILE.exists():
        raise FileNotFoundError(
            f"{PREDICTION_FILE} is missing. Run prepare_labelstudio_docker.py first."
        )
    with PREDICTION_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def split_tasks(tasks, *, main_count: int, calib_count: int, val_count: int, gold_count: int, seed: int):
    """Split tasks into disjoint subsets by a single seeded shuffle."""

    counts = {
        "main": int(main_count),
        "calibration": int(calib_count),
        "validation": int(val_count),
        "gold": int(gold_count),
    }
    for k, v in counts.items():
        if v < 0:
            raise ValueError(f"{k}_count must be >= 0")

    need = sum(counts.values())
    if len(tasks) < need:
        raise ValueError(
            f"Need at least {need} pre-generated tasks, but only found {len(tasks)}. "
            f"(main={counts['main']}, calib={counts['calibration']}, val={counts['validation']}, gold={counts['gold']})"
        )

    rng = random.Random(int(seed))
    shuffled = tasks.copy()
    rng.shuffle(shuffled)

    a = 0
    main = shuffled[a : a + counts["main"]]
    a += counts["main"]
    calib = shuffled[a : a + counts["calibration"]]
    a += counts["calibration"]
    val = shuffled[a : a + counts["validation"]]
    a += counts["validation"]
    gold = shuffled[a : a + counts["gold"]]

    # Safety: ensure disjoint keys
    def keys(xs):
        return set(_task_key(t) for t in xs)

    km, kc, kv, kg = keys(main), keys(calib), keys(val), keys(gold)
    if (km & kc) or (km & kv) or (km & kg) or (kc & kv) or (kc & kg) or (kv & kg):
        raise RuntimeError("Split overlap detected; check task key stability.")

    return main, calib, val, gold


def strip_predictions(task):
    data = task.get("data") or {}
    return {
        "data": {
            "image": data.get("image"),
            "vis_3d": data.get("vis_3d"),
            "title": data.get("title"),
        }
    }


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def main(*, num_per_group: int, calib_count: int, val_count: int, gold_count: int, seed: int, output_dir: Path):
    tasks = load_predictions()

    main_set, calib_set, val_set, gold_set = split_tasks(
        tasks,
        main_count=num_per_group,
        calib_count=calib_count,
        val_count=val_count,
        gold_count=gold_count,
        seed=seed,
    )

    # Backward-compatible filenames (main split)
    manual_main_path = output_dir / "label_studio_manual_import.json"
    semi_main_path = output_dir / "label_studio_semiauto_import.json"

    # Extended filenames
    manual_calib_path = output_dir / "label_studio_manual_calibration_import.json"
    manual_val_path = output_dir / "label_studio_manual_validation_import.json"
    semi_val_path = output_dir / "label_studio_semiauto_validation_import.json"
    manual_gold_path = output_dir / "label_studio_manual_gold_import.json"
    report_path = output_dir / "label_studio_split_report.json"

    # Main
    manual_payload = [strip_predictions(t) for t in main_set]
    semi_payload = main_set
    write_json(manual_main_path, manual_payload)
    write_json(semi_main_path, semi_payload)

    # Calibration (Manual only, Scheme A)
    if calib_count > 0:
        write_json(manual_calib_path, [strip_predictions(t) for t in calib_set])

    # Validation (both conditions; can be used for allocation evaluation)
    if val_count > 0:
        write_json(manual_val_path, [strip_predictions(t) for t in val_set])
        write_json(semi_val_path, val_set)

    # Gold (Manual only; for adjudication/reference)
    if gold_count > 0:
        write_json(manual_gold_path, [strip_predictions(t) for t in gold_set])

    def titles(xs):
        return [str((t.get("data") or {}).get("title") or _task_key(t)) for t in xs]

    report = {
        "seed": int(seed),
        "source": str(PREDICTION_FILE),
        "counts": {
            "main_per_group": int(num_per_group),
            "calibration": int(calib_count),
            "validation": int(val_count),
            "gold": int(gold_count),
        },
        "outputs": {
            "main_manual": str(manual_main_path),
            "main_semi": str(semi_main_path),
            "calibration_manual": str(manual_calib_path) if calib_count > 0 else "",
            "validation_manual": str(manual_val_path) if val_count > 0 else "",
            "validation_semi": str(semi_val_path) if val_count > 0 else "",
            "gold_manual": str(manual_gold_path) if gold_count > 0 else "",
            "report": str(report_path),
        },
        "splits": {
            "main": titles(main_set),
            "calibration": titles(calib_set),
            "validation": titles(val_set),
            "gold": titles(gold_set),
        },
    }
    write_json(report_path, report)

    print("Split created:")
    print(f"  output_dir: {output_dir}")
    print(f"  main manual: {manual_main_path} ({num_per_group} tasks)")
    print(f"  main semi:   {semi_main_path} ({num_per_group} tasks)")
    if calib_count > 0:
        print(f"  calib manual: {manual_calib_path} ({calib_count} tasks)")
    if val_count > 0:
        print(f"  val manual:   {manual_val_path} ({val_count} tasks)")
        print(f"  val semi:     {semi_val_path} ({val_count} tasks)")
    if gold_count > 0:
        print(f"  gold manual:  {manual_gold_path} ({gold_count} tasks)")
    print(f"  report:       {report_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create reproducible Label Studio imports for main/manual+semi, calibration, validation, and gold sets."
    )
    parser.add_argument(
        "--num-per-group",
        type=int,
        default=100,
        help="Number of tasks in each experimental group.",
    )
    parser.add_argument(
        "--calib-count",
        type=int,
        default=30,
        help="Number of tasks in the Manual calibration set (Scheme A). Use 0 to disable.",
    )
    parser.add_argument(
        "--val-count",
        type=int,
        default=60,
        help="Number of tasks in the validation set (written for both Manual and Semi). Use 0 to disable.",
    )
    parser.add_argument(
        "--gold-count",
        type=int,
        default=0,
        help="Number of tasks in the Manual gold set (for adjudication/reference). Use 0 to disable.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed used for sampling.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="import_json",
        help="Directory to write split JSONs and the report.",
    )
    args = parser.parse_args()
    main(
        num_per_group=args.num_per_group,
        calib_count=args.calib_count,
        val_count=args.val_count,
        gold_count=args.gold_count,
        seed=args.seed,
        output_dir=Path(args.output_dir),
    )
