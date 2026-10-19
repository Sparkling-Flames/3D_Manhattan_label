#!/usr/bin/env python3
"""Compact personnel-composition replay: quick cases, exact requests, full plan.

Defaults are resolved from this package, independent of the shell's cwd.
--restored is the parent containing work_personnel_typing_A_20261019/recovered.
Nothing here downloads data, refits categories implicitly, or changes GitHub.
"""
from __future__ import annotations

import os
for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"

import argparse
from collections import Counter
import gc
import gzip
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"
COMPOSITION = ANALYSIS / "composition"
SOURCE_MAIN = "e572eb73bedc4fe9056df838e458bab83c3fa423"
SOURCE_SCIENCE = "82c6164b0d4630de5316199c92aa405930973168"
PINNED = {"numpy": "2.3.5", "pandas": "2.2.3", "scipy": "1.17.0", "scikit-learn": "1.8.0",
          "shapely": "2.1.2", "threadpoolctl": "3.6.0", "matplotlib": "3.10.8", "Pillow": "12.3.0"}
SNAPSHOT_LOGICAL = "restored/work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz"
# Original FINAL records contain these paths as provenance text, never as inputs.
ORIGINAL_COMPOSITION_LOGICAL = "/workspace/scratch/1d99618bd862/analysis/composition"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    path = Path(path)
    with (gzip.open(path, "rt", encoding="utf-8") if path.suffix == ".gz" else path.open(encoding="utf-8-sig")) as stream:
        return json.load(stream)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        path.write_bytes(gzip.compress(canonical(value), compresslevel=5, mtime=0))
    else:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def resolved(path, default):
    return (path if path is not None else default).expanduser().resolve()


def snapshot_path(restored):
    return restored / "work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz"


def runtime_check(render=False):
    names = list(PINNED) if render else [p for p in PINNED if p not in ("matplotlib", "Pillow")]
    actual = {}
    for name in names:
        try:
            actual[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            actual[name] = None
    differences = {name: {"expected": PINNED[name], "actual": actual[name]} for name in names if actual[name] != PINNED[name]}
    if differences:
        raise RuntimeError("Pinned dependency mismatch; install analysis/requirements.txt: " + json.dumps(differences))
    return {"python": sys.version, "packages": actual, "blas_threads": 1}


def selected_cases(args):
    folder = resolved(args.cases_dir, ANALYSIS / "representative_cases/cases")
    paths = [p.expanduser().resolve() for p in args.case]
    selection = args.selection
    if not paths and selection is None and args.cases_dir is None:
        selection = COMPOSITION / "CASE_SELECTION.json"
    if selection:
        selection = selection.expanduser().resolve()
        data = read(selection)
        for entry in data["cases"] if isinstance(data, dict) else data:
            if isinstance(entry, dict) and "case_json" not in entry:
                path = folder / (entry["case_id"] + ".json")
            else:
                path = Path(entry if isinstance(entry, str) else entry["case_json"])
                if not path.is_absolute():
                    path = selection.parent / path
            paths.append(path.resolve())
    if not paths:
        paths = sorted(folder.glob("C[0-9]*.json"))
    if not paths or len(paths) != len(set(paths)):
        raise ValueError("No cases selected, or duplicate case paths")
    for path in paths:
        data = read(path)
        if not data.get("case_id") or not data.get("teams"):
            raise ValueError("Not an exported case JSON: " + str(path))
    return paths


def quick(args):
    runtime_check(args.render)
    restored = resolved(args.restored, ROOT / "restored")
    out = resolved(args.out, ROOT / "replay/quick")
    paths = selected_cases(args)
    command = [sys.executable, str(COMPOSITION / "replay_saved_cases.py"), "--restored", str(restored), "--out", str(out)]
    for path in paths:
        command += ["--case", str(path)]
    if args.render:
        command.append("--render")
        font = resolved(args.font, ANALYSIS / "fonts/NotoSansSC-Regular.ttf")
        if font.is_file():
            command += ["--font", str(font)]
        elif args.font:
            raise FileNotFoundError(font)
        else:
            print("Chinese font not bundled at the default path; use --font as described in REPRODUCE_ZH.md.", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)
    result = read(out / "REPLAY_SUMMARY.json")
    missing = [r["case_id"] for r in result["cases"] if r["render_status"].startswith("skipped_missing_original")]
    if missing:
        print(json.dumps({"numeric_replay_retained": True, "missing_original_case_ids": missing,
                          "restore_images": "See analysis/REPRODUCE_ZH.md section 5; exact Release members only, no full ZIP required."}, ensure_ascii=False), flush=True)


def audit_module():
    sys.path.insert(0, str(ANALYSIS / "independent"))
    import audit_reproduce_requests as audit
    return audit


def checked_sources(audit, restored, expected, require_snapshot=True):
    checks = {}
    for logical, digest in expected["source_sha256"].items():
        path = snapshot_path(restored) if logical == SNAPSHOT_LOGICAL else ROOT / logical
        if logical == SNAPSHOT_LOGICAL and not require_snapshot and not path.is_file():
            checks[logical] = {"resolved_path": str(path), "expected_sha256": digest, "status": "restore_before_execution"}
            continue
        actual = sha(path)
        if actual != digest:
            raise ValueError("Frozen source/label/spec changed: " + logical)
        checks[logical] = {"resolved_path": str(path), "sha256": actual, "matches_frozen": True}
    freeze = read(COMPOSITION / "VALIDATION_FREEZE.json")
    assert freeze["main_commit"] == SOURCE_MAIN and freeze["scientific_commit"] == SOURCE_SCIENCE
    assert all(sha(ROOT / p) == digest for p, digest in freeze["file_sha256"].items())
    return checks


def rebuild_final(audit, out):
    rows, sources = [], []
    for name in audit.FINAL_COMPONENTS:
        source = out / name
        payload = read(source)
        assert sha(source) == audit.EXPECTED[name]
        rows.extend(payload["requests"])
        sources.append({"path": ORIGINAL_COMPOSITION_LOGICAL + "/" + name,
                        "phase": payload["spec"]["phase"], "requests": len(payload["requests"]), "sha256": sha(source)})
    assert len(rows) == len({r["request_id"] for r in rows})
    path = out / "FINAL_REQUESTS.json.gz"
    save(path, {"component_manifests": sources, "freeze_sha256": sha(COMPOSITION / "VALIDATION_FREEZE.json"), "requests": rows})
    assert sha(path) == audit.EXPECTED[path.name]
    return {"name": path.name, "sha256": sha(path), "byte_identical": True, "requests": len(rows),
            "unique_teams": len({r["team_key"] for r in rows}), "components_in_order": audit.FINAL_COMPONENTS,
            "original_absolute_paths_are_provenance_only": True}


def requests(args):
    runtime = runtime_check()
    audit = audit_module()
    expected_path = ANALYSIS / "independent/REPRODUCTION_AUDIT.json"
    expected = read(expected_path)
    assert expected["all_passed"] and len(expected["manifests"]) == 13
    restored = resolved(args.restored, ROOT / "restored")
    out = resolved(args.out, ROOT / "replay/requests")
    out.mkdir(parents=True, exist_ok=True)
    sources = checked_sources(audit, restored, expected)
    audit.SNAPSHOT = snapshot_path(restored)  # Input path only; generator/scientific logic unchanged.
    expected_by_name = {r["name"]: r for r in expected["manifests"]}
    names = args.only or list(expected_by_name)
    if len(names) != len(set(names)) or not set(names) <= expected_by_name.keys():
        raise ValueError("--only requires distinct exact manifest filenames from REPRODUCTION_AUDIT.json")
    split = read(COMPOSITION / "SPLIT.json")
    sets = [set(split[p + "_buildings"]) for p in ("history", "discovery", "validation")]
    assert not any(sets[i] & sets[j] for i in range(3) for j in range(i + 1, 3))
    pools = {p["pool_id"]: p for p in read(audit.SNAPSHOT)["images"]}
    assert all(len(p["records"]) == len({r["worker_id"] for r in p["records"]}) for p in pools.values())
    mappings = audit.load_labels()
    condition = read(ANALYSIS / "forward/condition_experiment_spec.json")
    rules = {(r["stage"], r["method_id"], r["domain"], r["pool_id"]): r for r in condition["rules"]}
    commands = {name: cmd for name, cmd in audit.commands(out)}
    result = {"schema": "portable_request_rebuild_v1", "runtime": runtime,
              "package_root": str(ROOT), "restored_root": str(restored),
              "expected_audit_sha256": sha(expected_path), "source_checks": sources,
              "mode": "verify_existing_rebuilt" if args.check_existing else "physically_regenerate",
              "source_files_checked_before_execution": True, "fusion_results_read": False,
              "manifests": [], "failures": [], "derived_final": None,
              "actual_coverage_and_omissions": expected["actual_coverage_and_omissions"]}
    started = time.monotonic()
    all_sets = [set() for _ in range(5)]
    request_ids = set()
    for index, name in enumerate(names, 1):
        t = time.monotonic()
        print(json.dumps({"step": result["mode"], "manifest": name, "index": index, "of": len(names)}), flush=True)
        if not args.check_existing:
            subprocess.run(commands[name], cwd=ROOT, check=True, stdout=subprocess.PIPE, text=True)
        path = out / name
        payload = read(path)
        by_id = {r["request_id"]: r for r in payload["requests"]}
        assert len(by_id) == len(payload["requests"]) and not request_ids & by_id.keys()
        request_ids.update(by_id)
        signature = hashlib.sha256()
        for rid in sorted(by_id):
            signature.update(audit.canonical([rid, audit.request_signature(by_id[rid])]) + b"\n")
        support, cells, groups, support_sets = audit.audit_requests(payload, pools, mappings, rules, split)
        coverage = audit.audit_coverage(name, payload, cells, groups, rules, pools, mappings)
        original = expected_by_name[name]
        entry = {"name": name, "sha256": sha(path), "expected_sha256": original["original_sha256"],
                 "byte_identical": sha(path) == original["original_sha256"],
                 "member_signature_sha256": signature.hexdigest(),
                 "every_request_member_signature_identical": signature.hexdigest() == original["member_signature_original_sha256"],
                 "support_exact": json.loads(canonical(support)) == original["support"],
                 "support": support, "coverage": coverage, "command": commands[name],
                 "seconds": round(time.monotonic() - t, 3)}
        result["manifests"].append(entry)
        if not (entry["byte_identical"] and entry["every_request_member_signature_identical"] and entry["support_exact"]):
            result["failures"].append(name)
        for accumulator, values in zip(all_sets, support_sets):
            accumulator.update(values)
        save(out / "REQUEST_REBUILD_RECEIPT.json", result)
        print(json.dumps({"manifest": name, "requests": len(by_id), "sha_and_members_exact": name not in result["failures"]}), flush=True)
        del payload, by_id, cells, groups
        gc.collect()
    if set(names) == set(expected_by_name) and not result["failures"]:
        result["derived_final"] = rebuild_final(audit, out)
    result["support"] = {"primary_manifests": len(names), "request_ids": len(request_ids), "unique_actual_teams": len(all_sets[0]),
                         "images": len(all_sets[1]), "buildings": len(all_sets[2]), "workers": len(all_sets[3]), "pools": len(all_sets[4]),
                         "repeated_rows_beyond_actual_teams": len(request_ids) - len(all_sets[0]), "derived_final_counted_again": False}
    result["all_sources_unchanged"] = all(sha(row["resolved_path"]) == row["sha256"] for row in sources.values())
    result["all_passed"] = not result["failures"] and result["all_sources_unchanged"]
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    result["entry_sha256"] = sha(Path(__file__))
    save(out / "REQUEST_REBUILD_RECEIPT.json", result)
    print(json.dumps({"all_passed": result["all_passed"], "support": result["support"], "out": str(out)}, ensure_ascii=False), flush=True)
    if not result["all_passed"]:
        raise SystemExit("Rebuilt requests differ; retain receipt and investigate before scientific replay")


def full(args):
    """Write the exact command sequence; execution is a separate explicit action."""
    audit = audit_module()
    expected = read(ANALYSIS / "independent/REPRODUCTION_AUDIT.json")
    restored = resolved(args.restored, ROOT / "restored")
    out = resolved(args.out, ROOT / "replay/full")
    base = out / "composition"
    if base == COMPOSITION:
        raise ValueError("Full output must be a separate directory from frozen package inputs")
    checks = checked_sources(audit, restored, expected, require_snapshot=False)
    snap = str(snapshot_path(restored))
    split = str(COMPOSITION / "SPLIT.json")
    labels = [str(ANALYSIS / "forward/results/worker_labels.csv.gz"), str(ANALYSIS / "reverse/worker_labels.csv.gz")]
    features = str(ANALYSIS / "forward/results/features_train.csv.gz")
    label_args = [value for path in labels for value in ("--labels", path)]
    steps = []

    def add(name, script, *arguments):
        steps.append({"step": name, "cwd": str(ROOT), "command": [sys.executable, str(script), *map(str, arguments)]})

    add("rebuild_all_frozen_requests", Path(__file__), "requests", "--restored", restored, "--out", base)
    fusion_stages = [("SCREEN_REQUESTS", "runs"), ("DISCOVERY_GRID_REQUESTS", "runs"),
                     ("DISCOVERY_CONDITION_REQUESTS", "runs"), ("DISCOVERY_BLOCK_REQUESTS", "runs_blocks"),
                     ("DISCOVERY_CURVE_REQUESTS", "runs_curves"), ("FINAL_REQUESTS", "runs_final"),
                     ("SPECIAL_REQUESTS", "runs_special")]
    for name, run in fusion_stages:
        add("fusion_" + name, COMPOSITION / "fusion_runner.py", "--restored", restored,
            "--requests", base / (name + ".json.gz"), "--out", base / run, "--jobs", args.jobs)
    stages = read(COMPOSITION / "FROZEN_GRID_STAGES.json")
    relocated_stages = []
    runs = {name + ".json.gz": run for name, run in fusion_stages}
    for name in audit.FINAL_COMPONENTS:
        runs[name] = "runs_final"
    for stage in stages:
        name = Path(stage["requests"]).name
        grid = base / Path(stage["grid"]).name
        moved = dict(stage, requests=str(base / name), grid=str(grid))
        relocated_stages.append(moved)
        # Match the original summary mode; dense curves use separate frozen contrasts.
        mode = "pure_adjacent" if stage["name"] in ("breadth_discovery", "condition_discovery") else "none"
        add("summarize_" + stage["name"], COMPOSITION / "summarize_grid.py", "--requests", base / name,
            "--runs", base / runs[name], *label_args, "--split", split, "--snapshot", snap,
            "--phase", stage["phase"], "--out", grid, "--contrasts", mode)
    stages_path = out / "FROZEN_GRID_STAGES_RELOCATED.json"
    save(stages_path, relocated_stages)
    for phase in ("discovery", "validation"):
        block = base / ("block_" + phase)
        specific = base / ("block_" + phase + "_specific")
        add("summarize_blocks_" + phase, COMPOSITION / "summarize_blocks.py", "--requests", base / (phase.upper() + "_BLOCK_REQUESTS.json.gz"),
            "--runs", base / ("runs_blocks" if phase == "discovery" else "runs_final"), *label_args,
            "--features", features, "--snapshot", snap, "--split", split, "--phase", phase, "--out", block)
        add("directed_and_worker_sensitivity_" + phase, COMPOSITION / "block_specific_findings.py", "--events", block / "block_events.csv.gz",
            *label_args, "--phase", phase, "--out", specific, "--loow-min-buildings", 3, "--loow-min-events", 12)
        add("fixed_block_highlights_" + phase, COMPOSITION / "report_block_highlights.py", "--root", base,
            *label_args, "--phase", phase, "--out", specific)
        add("nested_mechanisms_" + phase, COMPOSITION / "summarize_nested.py", "--requests", base / (phase.upper() + "_NESTED_REQUESTS.json.gz"),
            "--runs", base / "runs_final", "--snapshot", snap, "--out", base / ("nested_" + phase))
    result_dir = base / "frozen_grid_results"
    add("frozen_named_comparisons", COMPOSITION / "frozen_grid_comparisons.py", "--stages", stages_path,
        "--freeze", COMPOSITION / "VALIDATION_FREEZE.json", "--snapshot", snap, "--split", split,
        *label_args, "--features", features, "--out", result_dir)
    add("compact_frozen_findings", COMPOSITION / "summarize_frozen_findings.py", "--results", result_dir)
    add("within_exact_compositions", COMPOSITION / "within_composition_report.py", "--stages", stages_path,
        "--snapshot", snap, "--freeze", COMPOSITION / "VALIDATION_FREEZE.json", *label_args, "--out", base / "within_fixed_compositions")
    add("real_support_and_repeated_team_parity", COMPOSITION / "study_coverage.py", "--base", base, "--snapshot", snap, "--out", base / "study_coverage")
    add("postfreeze_room_strata", COMPOSITION / "scene_condition_analysis.py", "--results", result_dir,
        "--conditions", ANALYSIS / "independent/POOL_IMAGE_CONDITIONS.csv", "--out", base / "scene_analysis")
    if args.render:
        font = resolved(args.font, ANALYSIS / "fonts/NotoSansSC-Regular.ttf")
        add("summary_plots", COMPOSITION / "plot_frozen_curves.py", "--base", base, "--out", out / "figures_summary", "--font", font)
    plan = {"schema": "frozen_composition_full_replay_plan_v1", "main_commit": SOURCE_MAIN, "science_commit": SOURCE_SCIENCE,
            "package_root": str(ROOT), "restored_root": str(restored), "out": str(out), "jobs": args.jobs,
            "source_checks": checks, "scientific_commands_executed_by_this_invocation": False,
            "scope": "Replay the frozen labels/specs, all primary requests, native fusion and numerical summaries. Does not repeat post-hoc candidate/rule selection, refit categories, restore raw exports, or regenerate narrative editorial text.",
            "large_outputs": "Native team caches and derived pair tables are generated only in this separate output directory; not part of the compact delivery.",
            "steps": steps}
    save(out / "FULL_REPLAY_PLAN.json", plan)
    lines = ["#!/usr/bin/env bash", "set -euo pipefail", "export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1", "cd " + shlex.quote(str(ROOT)), ""]
    for step in steps:
        lines += ["# " + step["step"], shlex.join(step["command"]), ""]
    script = out / "FULL_REPLAY_COMMANDS.sh"
    script.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"scientific_computation_started": False, "steps": len(steps), "plan": str(out / "FULL_REPLAY_PLAN.json"),
                      "commands": str(script), "execute_command": "bash " + shlex.quote(str(script)),
                      "estimated_scope": "589990 primary requests / 583261 distinct actual teams; FINAL is a union of existing primary stages, not additional independent data"}, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    for mode, help_text in (("quick", "Replay selected embedded-record cases; original images optional"),
                            ("requests", "Regenerate all 13 frozen primary manifests and check hashes/members"),
                            ("full", "Write exact native fusion and summary commands; no full run started")):
        sub = commands.add_parser(mode, help=help_text)
        sub.add_argument("--restored", type=Path)
        sub.add_argument("--out", type=Path)
        if mode in ("quick", "full"):
            sub.add_argument("--render", action="store_true")
            sub.add_argument("--font", type=Path)
        if mode == "quick":
            sub.add_argument("--case", type=Path, action="append", default=[])
            sub.add_argument("--selection", type=Path)
            sub.add_argument("--cases-dir", type=Path)
        elif mode == "requests":
            sub.add_argument("--only", action="append", help="Exact filename, e.g. SCREEN_REQUESTS.json.gz; repeat to select a subset")
            sub.add_argument("--check-existing", action="store_true", help="Verify previously rebuilt files in --out without regenerating")
        else:
            sub.add_argument("--jobs", type=int, default=5)
    args = parser.parse_args()
    if args.mode == "full" and args.jobs < 1:
        parser.error("--jobs must be positive")
    {"quick": quick, "requests": requests, "full": full}[args.mode](args)


if __name__ == "__main__":
    main()
