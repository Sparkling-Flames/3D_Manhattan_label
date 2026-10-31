"""Restore the archived source layout in an isolated copy, never in the checkout.

This is an additive compatibility adapter, not a new scientific implementation.
An exact archived SHA256 is required for every source file. Current files must
not silently replace a differing frozen input. No network access is performed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile


STUDY_REL = Path('research/workers/personnel_full_chain_v21_20261030/HOHONET_v21_full_chain_20261030')


def frozen_sources(manifest: Path) -> list[dict]:
    with manifest.open(encoding='utf-8-sig', newline='') as fh:
        rows = list(csv.DictReader(fh))
    found, seen = [], set()
    for row in rows:
        raw = row['path']
        path = PurePosixPath(raw)
        if path.is_absolute() or '..' in path.parts or '\\' in raw:
            raise ValueError(f'Unsafe manifest path: {raw!r}')
        if not path.parts or path.parts[0] != 'source':
            continue
        if '__pycache__' in path.parts or path.suffix == '.pyc':
            continue
        rel = path.relative_to('source').as_posix()
        if rel in seen:
            raise ValueError(f'Duplicate source identity: {rel}')
        seen.add(rel)
        sha = row['sha256']
        if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
            raise ValueError(f'Invalid SHA256 for {rel}')
        found.append(dict(path=rel, bytes=int(row['bytes']), sha256=sha))
    if not found:
        raise ValueError('The delivery manifest contains no frozen source files')
    return found


def fingerprint(path: Path) -> dict:
    h = hashlib.sha256()
    size = 0
    with path.open('rb') as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b''):
            size += len(block)
            h.update(block)
    return dict(bytes=size, sha256=h.hexdigest())


def source_plan(repo: Path, study: Path) -> dict:
    """Read only. Prefer an exact archived copy, then variant, then root reuse."""
    result = []
    for entry in frozen_sources(study / 'delivery_manifests/core_MANIFEST.csv'):
        rel = entry['path']
        candidates = [('archive', study / 'source' / rel),
                      ('variant', study / 'source_variants' / rel),
                      ('root_reuse', repo / rel)]
        attempts, selected = [], None
        for kind, candidate in candidates:
            if not candidate.is_file():
                attempts.append(dict(kind=kind, path=str(candidate), status='missing'))
                continue
            actual = fingerprint(candidate)
            matches = actual['bytes'] == entry['bytes'] and actual['sha256'] == entry['sha256']
            attempts.append(dict(kind=kind, path=str(candidate), status='exact' if matches else 'mismatch', **actual))
            if matches:
                selected = dict(kind=kind, path=str(candidate))
                break
        result.append(dict(**entry, selected=selected, attempts=attempts))
    missing = [x['path'] for x in result if x['selected'] is None]
    return dict(status='ready' if not missing else 'blocked', total=len(result),
                exact=len(result)-len(missing), blocked=missing, entries=result)


def stage_copy(repo: Path, study: Path, destination: Path, plan: dict) -> Path:
    """Create a new disposable copy. Never overwrite an existing destination."""
    if plan['status'] != 'ready':
        raise ValueError('Frozen source preflight is blocked; no copy was created')
    repo, study, destination = repo.resolve(), study.resolve(), destination.resolve()
    if destination.exists():
        raise FileExistsError(destination)
    if destination == study or destination.is_relative_to(study):
        raise ValueError('Destination must not be inside the historical archive')
    # No symlinks into the archive: downstream scripts write generated tables.
    shutil.copytree(study, destination, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for entry in plan['entries']:
        src = Path(entry['selected']['path'])
        # Detect any source changed between preflight and the copy operation.
        if fingerprint(src) != {k: entry[k] for k in ('bytes', 'sha256')}:
            raise ValueError(f'Source changed after preflight: {entry["path"]}; discard isolated copy')
        target = destination / 'source' / entry['path']
        if target.exists():
            if fingerprint(target) != {k: entry[k] for k in ('bytes', 'sha256')}:
                raise ValueError(f'Unexpected existing staged source: {entry["path"]}; discard isolated copy')
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)
        if fingerprint(target) != {k: entry[k] for k in ('bytes', 'sha256')}:
            raise ValueError(f'Staged copy failed verification: {entry["path"]}')
    (destination / 'SOURCE_LAYOUT_ADAPTER_RECEIPT.json').write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return destination


def run_archived_checker(repo: Path, staged: Path, report_dir: Path) -> None:
    """Execute the unchanged checker with source/output roots isolated.

    This requires all recorded Python dependencies and full archived payloads.
    It reruns only the original checker's seven checks, not all native fusion.
    """
    repo, staged, report_dir = repo.resolve(), staged.resolve(), report_dir.resolve()
    archive = repo / STUDY_REL.parent
    if report_dir == archive or report_dir.is_relative_to(archive):
        raise ValueError('Check reports must not overwrite the historical archive')
    if report_dir.exists():
        raise FileExistsError(report_dir)
    checker = repo / 'tools/thesis_main/analysis/check_v21_full_chain_20261030.py'
    spec = importlib.util.spec_from_file_location('v21_frozen_checker_isolated', checker)
    if spec is None or spec.loader is None:
        raise ImportError(f'Cannot load original checker: {checker}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # ROOT is used by the old checker for two byte-identity checks and temporary
    # work placement. Copy current counterparts; do not fake identity with the
    # archived file itself, or write temporary artifacts in the original repo.
    identities = [Path('research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json'),
                  Path('research/data/releases/v2.1/final_classification_downstream/TARGET_MAIN_EVENTS.csv.gz')]
    with tempfile.TemporaryDirectory(prefix='v21_checker_identity_') as tmp:
        isolated_root = Path(tmp)
        for rel in identities:
            target = isolated_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repo / rel, target)
        module.ROOT = isolated_root
        module.STUDY = staged
        module.QT = archive / 'common_support/v21_q_qt_common_support_20261030'
        module.OUT = report_dir
        report_dir.mkdir(parents=True, exist_ok=False)
        module.main()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--study', type=Path, help='Default: full-chain archive within --repo')
    parser.add_argument('--stage-copy', type=Path, help='New isolated directory; omitted = read-only preflight')
    parser.add_argument('--run-checks', action='store_true', help='Run the existing seven-check suite after staging')
    parser.add_argument('--report-dir', type=Path, help='New output directory outside the historical archive')
    args = parser.parse_args()
    if args.run_checks and (not args.stage_copy or not args.report_dir):
        parser.error('--run-checks requires --stage-copy and --report-dir')
    repo = args.repo.resolve()
    study = args.study.resolve() if args.study else repo / STUDY_REL
    plan = source_plan(repo, study)
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if plan['status'] != 'ready':
        return 2
    if args.stage_copy:
        staged = stage_copy(repo, study, args.stage_copy, plan)
        if args.run_checks:
            run_archived_checker(repo, staged, args.report_dir)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
