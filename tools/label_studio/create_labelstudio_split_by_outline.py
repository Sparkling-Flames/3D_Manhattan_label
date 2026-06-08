"""Generate Label Studio import JSONs by the latest thesis grouping protocol.

Protocol summary (N_pool=458):
- Stage0 Pilot: 15 (manual)
- Stage1 PreScreen_manual: 30 (manual, includes 12 anchors)
- Stage1 PreScreen_semi: 30 (semi, disjoint from manual)
- Stage2 Calibration_manual_pool: 100 (manual)
    - anchor 12, core 75, reserve 13 (disjoint, union=100)
    - Calibration_semi: 25 sampled from calibration pool (paired subset)
- Stage3 Main:
    - Manual_Test: 100 (manual)
    - SemiAuto_Test: same 100 images (semi paired with Manual_Test)
    - Validation_semi: 60 (semi)
    - Gold_manual: 20 (manual)

Unique image usage target: 355.
"""

from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path


SOURCE_JSON = Path("label_studio_import_docker.json")
DEFAULT_VIS3D_PLACEHOLDER_URL = os.environ.get(
    "HOHONET_VIS3D_PLACEHOLDER_URL",
    "http://175.178.71.217:8000/tools/vis_3d.html",
)


def task_key(task: dict) -> str:
    data = task.get("data") or {}
    title = data.get("title")
    if title:
        return str(title)
    image = data.get("image")
    if image:
        return str(image)
    return json.dumps(task, sort_keys=True, ensure_ascii=False)


def normalize_vis3d_url(raw_vis3d: object, fallback_url: str) -> str:
    s = "" if raw_vis3d is None else str(raw_vis3d).strip()
    if s.startswith("http://") or s.startswith("https://"):
        return s
    return fallback_url


def strip_predictions(
    task: dict,
    dataset_group: str,
    *,
    vis3d_placeholder_url: str,
    is_anchor: bool = False,
    has_expert_ref: bool = False,
) -> dict:
    data = task.get("data") or {}
    out = {
        "data": {
            "image": data.get("image"),
            "vis_3d": normalize_vis3d_url(data.get("vis_3d"), vis3d_placeholder_url),
            "title": data.get("title"),
            "dataset_group": dataset_group,
        }
    }
    if is_anchor:
        out["data"]["is_anchor"] = True
    if has_expert_ref:
        out["data"]["has_expert_ref"] = True
    return out


def with_group(task: dict, dataset_group: str, *, vis3d_placeholder_url: str, init_type: str | None = None) -> dict:
    out = dict(task)
    data = dict(task.get("data") or {})
    data["vis_3d"] = normalize_vis3d_url(data.get("vis_3d"), vis3d_placeholder_url)
    data["dataset_group"] = dataset_group
    if init_type is not None:
        data["init_type"] = init_type
    out["data"] = data
    return out


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def titles(tasks: list[dict]) -> list[str]:
    return [str((t.get("data") or {}).get("title") or task_key(t)) for t in tasks]


def check_disjoint(named_sets: dict[str, list[dict]]) -> None:
    keys_map = {name: set(titles(items)) for name, items in named_sets.items()}
    names = list(keys_map)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            overlap = keys_map[a] & keys_map[b]
            if overlap:
                raise RuntimeError(f"Overlap detected between {a} and {b}: {len(overlap)}")


def main(seed: int, source_json: Path, output_dir: Path, vis3d_placeholder_url: str) -> None:
    if not source_json.exists():
        raise FileNotFoundError(f"source json not found: {source_json}")

    tasks = json.loads(source_json.read_text(encoding="utf-8"))
    if not isinstance(tasks, list):
        raise ValueError("source json must be a list of Label Studio tasks")

    # de-duplicate by stable key (keep first occurrence)
    uniq = {}
    for t in tasks:
        k = task_key(t)
        if k not in uniq:
            uniq[k] = t
    all_tasks = list(uniq.values())

    rng = random.Random(seed)
    rng.shuffle(all_tasks)

    if len(all_tasks) < 458:
        raise ValueError(f"expected at least 458 tasks, got {len(all_tasks)}")

    # Stage allocations
    idx = 0
    pilot_manual = all_tasks[idx:idx + 15]
    idx += 15

    prescreen_manual = all_tasks[idx:idx + 30]
    idx += 30
    prescreen_manual_anchor = prescreen_manual[:12]

    prescreen_semi = all_tasks[idx:idx + 30]
    idx += 30

    calibration_manual_pool = all_tasks[idx:idx + 100]
    idx += 100
    calibration_anchor = calibration_manual_pool[:12]
    calibration_core = calibration_manual_pool[12:12 + 75]
    calibration_reserve = calibration_manual_pool[12 + 75:12 + 75 + 13]

    calibration_semi = calibration_core[:25]  # paired subset sampled from calibration manual pool

    manual_test = all_tasks[idx:idx + 100]
    idx += 100
    semiauto_test = manual_test  # paired by design

    validation_semi = all_tasks[idx:idx + 60]
    idx += 60

    gold_manual = all_tasks[idx:idx + 20]
    idx += 20

    # disjoint checks for unique pools
    check_disjoint({
        "pilot_manual": pilot_manual,
        "prescreen_manual": prescreen_manual,
        "prescreen_semi": prescreen_semi,
        "calibration_manual_pool": calibration_manual_pool,
        "manual_test": manual_test,
        "validation_semi": validation_semi,
        "gold_manual": gold_manual,
    })

    # paired/subset checks
    assert set(titles(semiauto_test)) == set(titles(manual_test))
    assert set(titles(calibration_semi)).issubset(set(titles(calibration_manual_pool)))
    assert len(calibration_anchor) + len(calibration_core) + len(calibration_reserve) == 100
    assert set(titles(calibration_anchor)).isdisjoint(set(titles(calibration_core)))
    assert set(titles(calibration_anchor)).isdisjoint(set(titles(calibration_reserve)))
    assert set(titles(calibration_core)).isdisjoint(set(titles(calibration_reserve)))

    out = output_dir
    write_json(out / "stage0_pilot_manual_import.json", [
        strip_predictions(t, "Pilot", vis3d_placeholder_url=vis3d_placeholder_url) for t in pilot_manual
    ])

    write_json(out / "stage1_prescreen_manual_import.json", [
        strip_predictions(
            t,
            "PreScreen_manual",
            vis3d_placeholder_url=vis3d_placeholder_url,
            is_anchor=(task_key(t) in set(titles(prescreen_manual_anchor))),
            has_expert_ref=(task_key(t) in set(titles(prescreen_manual_anchor))),
        )
        for t in prescreen_manual
    ])
    write_json(out / "stage1_prescreen_manual_anchor_import.json", [
        strip_predictions(
            t,
            "PreScreen_manual",
            vis3d_placeholder_url=vis3d_placeholder_url,
            is_anchor=True,
            has_expert_ref=True,
        )
        for t in prescreen_manual_anchor
    ])
    write_json(out / "stage1_prescreen_semi_import.json", [
        with_group(t, "PreScreen_semi", vis3d_placeholder_url=vis3d_placeholder_url, init_type="clean")
        for t in prescreen_semi
    ])

    write_json(out / "stage2_calibration_manual_import.json", [
        strip_predictions(t, "Calibration_manual", vis3d_placeholder_url=vis3d_placeholder_url) for t in calibration_manual_pool
    ])
    write_json(out / "stage2_calibration_manual_anchor_import.json", [
        strip_predictions(t, "Calibration_anchor", vis3d_placeholder_url=vis3d_placeholder_url) for t in calibration_anchor
    ])
    write_json(out / "stage2_calibration_manual_core_import.json", [
        strip_predictions(t, "Calibration_core", vis3d_placeholder_url=vis3d_placeholder_url) for t in calibration_core
    ])
    write_json(out / "stage2_calibration_manual_reserve_import.json", [
        strip_predictions(t, "Calibration_reserve", vis3d_placeholder_url=vis3d_placeholder_url) for t in calibration_reserve
    ])
    write_json(out / "stage2_calibration_semi_import.json", [
        with_group(t, "Calibration_semi", vis3d_placeholder_url=vis3d_placeholder_url) for t in calibration_semi
    ])

    write_json(out / "stage3_manual_test_import.json", [
        strip_predictions(t, "Manual_Test", vis3d_placeholder_url=vis3d_placeholder_url) for t in manual_test
    ])
    write_json(out / "stage3_semiauto_test_import.json", [
        with_group(t, "SemiAuto_Test", vis3d_placeholder_url=vis3d_placeholder_url) for t in semiauto_test
    ])
    write_json(out / "stage3_validation_semi_import.json", [
        with_group(t, "Validation_semi", vis3d_placeholder_url=vis3d_placeholder_url) for t in validation_semi
    ])
    write_json(out / "stage3_gold_manual_import.json", [
        strip_predictions(t, "Gold_manual", vis3d_placeholder_url=vis3d_placeholder_url) for t in gold_manual
    ])

    used_unique = set(
        titles(pilot_manual)
        + titles(prescreen_manual)
        + titles(prescreen_semi)
        + titles(calibration_manual_pool)
        + titles(manual_test)
        + titles(validation_semi)
        + titles(gold_manual)
    )

    report = {
        "seed": seed,
        "source": str(source_json),
        "counts": {
            "pool_total": len(all_tasks),
            "used_unique": len(used_unique),
            "reserved_unique": len(all_tasks) - len(used_unique),
            "stage0_pilot_manual": len(pilot_manual),
            "stage1_prescreen_manual": len(prescreen_manual),
            "stage1_prescreen_manual_anchor": len(prescreen_manual_anchor),
            "stage1_prescreen_semi": len(prescreen_semi),
            "stage2_calibration_manual_pool": len(calibration_manual_pool),
            "stage2_calibration_anchor": len(calibration_anchor),
            "stage2_calibration_core": len(calibration_core),
            "stage2_calibration_reserve": len(calibration_reserve),
            "stage2_calibration_semi": len(calibration_semi),
            "stage3_manual_test": len(manual_test),
            "stage3_semiauto_test": len(semiauto_test),
            "stage3_validation_semi": len(validation_semi),
            "stage3_gold_manual": len(gold_manual),
        },
        "overlap_constraints": {
            "semiauto_test_same_as_manual_test": True,
            "calibration_semi_subset_of_calibration_manual": True,
            "major_pools_disjoint": True,
        },
        "outputs": {
            "stage0_pilot_manual": "stage0_pilot_manual_import.json",
            "stage1_prescreen_manual": "stage1_prescreen_manual_import.json",
            "stage1_prescreen_manual_anchor": "stage1_prescreen_manual_anchor_import.json",
            "stage1_prescreen_semi": "stage1_prescreen_semi_import.json",
            "stage2_calibration_manual": "stage2_calibration_manual_import.json",
            "stage2_calibration_anchor": "stage2_calibration_manual_anchor_import.json",
            "stage2_calibration_core": "stage2_calibration_manual_core_import.json",
            "stage2_calibration_reserve": "stage2_calibration_manual_reserve_import.json",
            "stage2_calibration_semi": "stage2_calibration_semi_import.json",
            "stage3_manual_test": "stage3_manual_test_import.json",
            "stage3_semiauto_test": "stage3_semiauto_test_import.json",
            "stage3_validation_semi": "stage3_validation_semi_import.json",
            "stage3_gold_manual": "stage3_gold_manual_import.json",
        },
        "splits": {
            "pilot_manual": titles(pilot_manual),
            "prescreen_manual": titles(prescreen_manual),
            "prescreen_manual_anchor": titles(prescreen_manual_anchor),
            "prescreen_semi": titles(prescreen_semi),
            "calibration_manual_pool": titles(calibration_manual_pool),
            "calibration_anchor": titles(calibration_anchor),
            "calibration_core": titles(calibration_core),
            "calibration_reserve": titles(calibration_reserve),
            "calibration_semi": titles(calibration_semi),
            "manual_test": titles(manual_test),
            "semiauto_test": titles(semiauto_test),
            "validation_semi": titles(validation_semi),
            "gold_manual": titles(gold_manual),
        },
    }
    write_json(out / "label_studio_split_report_v2.json", report)

    print("Generated import files by latest outline grouping:")
    print(f"  output_dir: {out}")
    print(f"  used_unique: {len(used_unique)} / {len(all_tasks)}")
    print("  report: label_studio_split_report_v2.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Label Studio split files by latest thesis grouping.")
    parser.add_argument("--seed", type=int, default=20260228, help="Random seed")
    parser.add_argument("--source-json", type=str, default=str(SOURCE_JSON), help="Source import JSON path")
    parser.add_argument("--output-dir", type=str, default="import_json/outline_v2_seed20260228", help="Output folder")
    parser.add_argument(
        "--vis3d-placeholder-url",
        type=str,
        default=DEFAULT_VIS3D_PLACEHOLDER_URL,
        help="Fallback valid URL for data.vis_3d when source has empty value and XML uses valueType=url",
    )
    args = parser.parse_args()
    main(args.seed, Path(args.source_json), Path(args.output_dir), args.vis3d_placeholder_url)
