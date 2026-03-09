import argparse
import csv
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = REPO_ROOT / "tools"
BASE_ANALYZE_SCRIPT = TOOLS_DIR / "analyze_quality.py"

FORMAL_DROP_COLUMNS = [
    "scope_missing",
    "difficulty_missing",
    "model_issue_missing",
    "model_issue_types",
    "difficulty_conflict_v2",
    "model_issue_conflict_v2",
    "is_normal",
]

FORMAL_REQUIRED_COLUMNS = [
    "task_id",
    "annotator_id",
    "dataset_group",
    "project_version",
    "analysis_role",
    "condition",
    "active_time",
    "scope",
    "difficulty",
    "model_issue",
    "scope_filled",
    "difficulty_filled",
    "difficulty_conflict",
    "model_issue_required",
    "model_issue_filled",
    "model_issue_conflict",
    "model_issue_missing_required",
    "has_model_issue",
    "model_issue_primary",
    "is_oos",
    "iou",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Formal analysis entrypoint for official annotation rounds.",
    )
    parser.add_argument("export_json", help="Path to Label Studio export JSON file")
    parser.add_argument("--active-logs", default="active_logs", help="Path to active_logs directory")
    parser.add_argument("--output_dir", default="analysis_results", help="Directory to save output files")
    parser.add_argument(
        "--metric",
        choices=["auto", "manual", "corner"],
        default="corner",
        help="Primary metric for iou column.",
    )
    parser.add_argument("--no_smooth", action="store_true", help="Disable boundary curve smoothing for boundary RMSE")
    parser.add_argument("--pair_warn_min_coverage", type=float, default=0.8)
    parser.add_argument("--boundary_method", choices=["auto", "heuristic", "connect"], default="auto")
    parser.add_argument("--no_pointwise", action="store_true", help="Disable pointwise RMSE")
    parser.add_argument("--pointwise_min_coverage", type=float, default=0.9)
    parser.add_argument("--ru_min_tasks", type=int, default=5)
    parser.add_argument("--ru_bootstrap_iters", type=int, default=1000)
    parser.add_argument("--ru_ci", type=float, default=0.95)
    parser.add_argument("--ru_seed", type=int, default=0)
    parser.add_argument("--dataset_group", help="Frozen dataset_group for the official run; auto-inferred from export when unique")
    parser.add_argument("--project_version", required=True, help="Version tag for the official run")
    parser.add_argument(
        "--analysis_role",
        default="performance",
        choices=["performance", "reliability"],
        help="Analysis role used by upstream analyze_quality.py",
    )
    parser.add_argument(
        "--output",
        help="Final formal CSV path. Default: <output_dir>/quality_report_formal_YYYYMMDD.csv",
    )
    parser.add_argument("--append", action="store_true", help="Append at the base-analysis stage before formal filtering")
    parser.add_argument("--keep_temp", action="store_true", help="Keep temporary upstream outputs under .formal_tmp")
    return parser


def summarize_export(export_json: Path) -> dict:
    tasks = json.loads(export_json.read_text(encoding="utf-8"))
    dataset_groups: set[str] = set()
    project_ids: set[str] = set()
    annotation_count = 0
    task_updated_values: list[str] = []
    annotation_updated_values: list[str] = []

    for task in tasks:
        task_data = task.get("data") or {}
        dataset_group = str(task_data.get("dataset_group") or "").strip()
        if dataset_group:
            dataset_groups.add(dataset_group)
        project_ids.add(str(task.get("project") or ""))
        task_updated_values.append(str(task.get("updated_at") or ""))
        annotations = task.get("annotations", []) or []
        annotation_count += len(annotations)
        for annotation in annotations:
            annotation_updated_values.append(str(annotation.get("updated_at") or ""))

    def latest(values: list[str]) -> str:
        latest_dt = None
        latest_text = ""
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                continue
            if latest_dt is None or parsed > latest_dt:
                latest_dt = parsed
                latest_text = text
        return latest_text

    return {
        "task_count": len(tasks),
        "annotation_count": annotation_count,
        "dataset_groups": sorted(dataset_groups),
        "project_ids": sorted([value for value in project_ids if value]),
        "max_task_updated_at": latest(task_updated_values),
        "max_annotation_updated_at": latest(annotation_updated_values),
    }


def resolve_dataset_group(args: argparse.Namespace, export_json: Path) -> tuple[str, str, dict]:
    export_summary = summarize_export(export_json)
    inferred_groups = export_summary["dataset_groups"]

    if len(inferred_groups) == 1:
        inferred = inferred_groups[0]
        if args.dataset_group and args.dataset_group != inferred:
            raise RuntimeError(
                f"Formal analysis failed: --dataset_group={args.dataset_group} conflicts with export-inferred dataset_group={inferred}."
            )
        if args.dataset_group:
            return args.dataset_group, "cli_validated_against_export", export_summary
        return inferred, "export_task_data_single_group", export_summary

    if not args.dataset_group:
        if len(inferred_groups) > 1:
            raise RuntimeError(
                "Formal analysis failed: export JSON contains multiple dataset_group values; please pass --dataset_group explicitly."
            )
        raise RuntimeError(
            "Formal analysis failed: could not infer dataset_group from export JSON; please pass --dataset_group explicitly."
        )

    return args.dataset_group, "cli_argument", export_summary


def build_base_command(args: argparse.Namespace, temp_output_dir: Path, temp_quality_csv: Path, resolved_dataset_group: str) -> list[str]:
    cmd = [
        sys.executable,
        str(BASE_ANALYZE_SCRIPT),
        args.export_json,
        "--active-logs",
        args.active_logs,
        "--output_dir",
        str(temp_output_dir),
        "--metric",
        args.metric,
        "--pair_warn_min_coverage",
        str(args.pair_warn_min_coverage),
        "--boundary_method",
        args.boundary_method,
        "--pointwise_min_coverage",
        str(args.pointwise_min_coverage),
        "--ru_min_tasks",
        str(args.ru_min_tasks),
        "--ru_bootstrap_iters",
        str(args.ru_bootstrap_iters),
        "--ru_ci",
        str(args.ru_ci),
        "--ru_seed",
        str(args.ru_seed),
        "--dataset_group",
        resolved_dataset_group,
        "--project_version",
        args.project_version,
        "--analysis_role",
        args.analysis_role,
        "--quality_mode",
        "v2",
        "--output",
        str(temp_quality_csv),
    ]
    if args.no_smooth:
        cmd.append("--no_smooth")
    if args.no_pointwise:
        cmd.append("--no_pointwise")
    if args.append:
        cmd.append("--append")
    return cmd


def load_csv_rows(csv_path: Path) -> tuple[list[dict], list[str]]:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    return rows, fieldnames


def validate_required_columns(fieldnames: list[str]) -> None:
    missing = [name for name in FORMAL_REQUIRED_COLUMNS if name not in fieldnames]
    if missing:
        raise RuntimeError(
            "Formal analysis failed: upstream CSV is missing required columns: "
            + ", ".join(missing)
        )


def write_formal_csv(rows: list[dict], fieldnames: list[str], output_path: Path) -> list[str]:
    dropped = [name for name in FORMAL_DROP_COLUMNS if name in fieldnames]
    final_fieldnames = [name for name in fieldnames if name not in FORMAL_DROP_COLUMNS]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=final_fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return dropped


def write_manifest(args: argparse.Namespace, output_dir: Path, date_str: str, quality_csv: Path, reliability_csv: Path | None, dropped_columns: list[str], base_command: list[str], resolved_dataset_group: str, dataset_group_source: str, export_summary: dict) -> Path:
    manifest_path = output_dir / f"formal_analysis_manifest_{date_str}.json"
    payload = {
        "export_json": str(Path(args.export_json).resolve()),
        "active_logs": str(Path(args.active_logs).resolve()),
        "dataset_group": resolved_dataset_group,
        "dataset_group_source": dataset_group_source,
        "project_version": args.project_version,
        "analysis_role": args.analysis_role,
        "metric": args.metric,
        "quality_mode": "v2",
        "export_summary": export_summary,
        "formal_quality_csv": str(quality_csv.resolve()),
        "formal_reliability_csv": str(reliability_csv.resolve()) if reliability_csv else None,
        "dropped_compatibility_columns": dropped_columns,
        "base_command": base_command,
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    export_json = Path(args.export_json).resolve()
    resolved_dataset_group, dataset_group_source, export_summary = resolve_dataset_group(args, export_json)

    date_str = datetime.now().strftime("%Y%m%d")
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    temp_output_dir = output_dir / ".formal_tmp"
    temp_output_dir.mkdir(parents=True, exist_ok=True)
    temp_quality_csv = temp_output_dir / f"quality_report_formal_source_{date_str}.csv"

    final_quality_csv = Path(args.output).resolve() if args.output else output_dir / f"quality_report_formal_{date_str}.csv"
    final_reliability_csv = output_dir / f"reliability_report_formal_{date_str}.csv"
    temp_reliability_csv = temp_output_dir / f"reliability_report_{date_str}.csv"

    base_command = build_base_command(args, temp_output_dir, temp_quality_csv, resolved_dataset_group)
    print("[formal] running base analyzer:")
    print(" ".join(base_command))
    subprocess.run(base_command, check=True, cwd=str(REPO_ROOT))

    rows, fieldnames = load_csv_rows(temp_quality_csv)
    validate_required_columns(fieldnames)
    dropped_columns = write_formal_csv(rows, fieldnames, final_quality_csv)

    copied_reliability = None
    if temp_reliability_csv.exists():
      shutil.copyfile(temp_reliability_csv, final_reliability_csv)
      copied_reliability = final_reliability_csv

    manifest_path = write_manifest(
        args,
        output_dir,
        date_str,
        final_quality_csv,
        copied_reliability,
        dropped_columns,
        base_command,
        resolved_dataset_group,
        dataset_group_source,
        export_summary,
    )

    if not args.keep_temp:
        shutil.rmtree(temp_output_dir, ignore_errors=True)

    print(f"[formal] quality csv: {final_quality_csv}")
    if copied_reliability:
        print(f"[formal] reliability csv: {copied_reliability}")
    print(f"[formal] dataset_group: {resolved_dataset_group} ({dataset_group_source})")
    print(f"[formal] manifest: {manifest_path}")
    if dropped_columns:
        print(f"[formal] dropped compatibility columns: {', '.join(dropped_columns)}")
    else:
        print("[formal] no compatibility columns were present to drop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())