from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis import (
    c1_calibration_input_preview,
    c1_calibration_metric_dryrun,
    p1_provisional_pipeline_materialization,
    t1_main_aggregation_dryrun,
    v1_validation_aggregation_dryrun,
)

DEFAULT_CLOSEOUT_DIR = Path("analysis_results/prescreen_closeout")
DEFAULT_OUTPUT_ROOT = Path("analysis_results/pipeline_smoke")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _counts(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key.startswith("n_") or key in {"smoke_pipeline_allowed", "p1_smoke_pipeline_allowed"}}


def _stage(
    name: str,
    output_dir: Path,
    state_file: str,
    runner: Callable[[], int],
) -> dict[str, Any]:
    runner()
    state_path = output_dir / state_file
    payload = _load_json(state_path)
    return {
        "stage_name": name,
        "status": "completed",
        "output_dir": str(output_dir),
        "state_file": str(state_path),
        "key_counts": _counts(payload),
    }


def run_pipeline_smoke(closeout_dir: Path = DEFAULT_CLOSEOUT_DIR, output_root: Path = DEFAULT_OUTPUT_ROOT) -> dict[str, Any]:
    root = Path(output_root)
    p1_dir = root / "p1_provisional"
    c1_preview_dir = root / "c1_calibration_preview"
    c1_metric_dir = root / "c1_metric_dryrun"
    t1_dir = root / "t1_main_dryrun"
    v1_dir = root / "v1_validation_dryrun"
    specs: list[tuple[str, Path, str, Callable[[], int]]] = [
        (
            "p1_provisional",
            p1_dir,
            "p1_provisional_pipeline_state.json",
            lambda: p1_provisional_pipeline_materialization.main(["--closeout-dir", str(closeout_dir), "--output-dir", str(p1_dir)]),
        ),
        (
            "c1_calibration_preview",
            c1_preview_dir,
            "c1_calibration_preview_state.json",
            lambda: c1_calibration_input_preview.main(["--p1-dir", str(p1_dir), "--output-dir", str(c1_preview_dir)]),
        ),
        (
            "c1_metric_dryrun",
            c1_metric_dir,
            "c1_calibration_metric_dryrun_state.json",
            lambda: c1_calibration_metric_dryrun.main(["--preview-dir", str(c1_preview_dir), "--output-dir", str(c1_metric_dir)]),
        ),
        (
            "t1_main_dryrun",
            t1_dir,
            "t1_main_dryrun_state.json",
            lambda: t1_main_aggregation_dryrun.main(["--metric-dir", str(c1_metric_dir), "--preview-dir", str(c1_preview_dir), "--output-dir", str(t1_dir)]),
        ),
        (
            "v1_validation_dryrun",
            v1_dir,
            "v1_validation_dryrun_state.json",
            lambda: v1_validation_aggregation_dryrun.main(["--t1-dir", str(t1_dir), "--c1-dir", str(c1_metric_dir), "--output-dir", str(v1_dir)]),
        ),
    ]
    stages: list[dict[str, Any]] = []
    final_status = "completed"
    failed_stage = ""
    blocked_reasons: list[str] = []
    for name, out_dir, state_file, runner in specs:
        try:
            stages.append(_stage(name, out_dir, state_file, runner))
        except Exception as exc:  # noqa: BLE001 - runner must write failure state instead of bubbling.
            final_status = "failed"
            failed_stage = name
            blocked_reasons = [str(exc)]
            stages.append({"stage_name": name, "status": "failed", "output_dir": str(out_dir), "state_file": str(out_dir / state_file), "key_counts": {}})
            break
    state = {
        "dry_run": True,
        "provisional_only": True,
        "pipeline_smoke_only": True,
        "formal_analysis_allowed": False,
        "not_for_thesis_claim": True,
        "stages": stages,
        "final_status": final_status,
        "failed_stage": failed_stage,
        "blocked_reasons": blocked_reasons,
    }
    _write_state(root / "pipeline_smoke_state.json", state)
    return state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--closeout-dir", default=str(DEFAULT_CLOSEOUT_DIR))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args(argv)
    state = run_pipeline_smoke(Path(args.closeout_dir), Path(args.output_root))
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0 if state["final_status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
