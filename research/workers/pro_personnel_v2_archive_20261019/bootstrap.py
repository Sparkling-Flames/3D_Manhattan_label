#!/usr/bin/env python3
"""Materialize an independent, hash-verified replay from the curated repository.

No original delivery ZIP is needed. Scientific scripts are copied unchanged.
Default: verify retained content and prepare a new workspace; no scientific run.
Example (after installing Git and Python 3.11+):
  python bootstrap.py --workspace /tmp/pro-replay --install-deps --stage all --execute
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
COMMIT = '82c6164b0d4630de5316199c92aa405930973168'
STAGES = ['verify', 'audit', 'profiles', 'clusters', 'fusion', 'comparisons',
          'summaries', 'reverse', 'report', 'viewer', 'all']


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(root, relative):
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError(f'Unsafe manifest path: {relative}')
    path = root / rel
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'Path escapes root: {relative}')
    return path


def rows(path):
    data = json.loads(path.read_text(encoding='utf-8'))
    return data['files'] if isinstance(data, dict) else data


def verified(data, row):
    if digest(data) != row['sha256']:
        raise ValueError(f"SHA256 mismatch: {row['path']}")
    if 'bytes' in row and len(data) != row['bytes']:
        raise ValueError(f"Size mismatch: {row['path']}")
    return data


def source_bytes(repo, row):
    # Current main is permitted only when content matches the frozen bytes.
    p = safe_path(repo, row['path'])
    if p.is_file():
        data = p.read_bytes()
        if digest(data) == row['sha256']:
            return verified(data, row)
    result = subprocess.run(['git', '-C', str(repo), 'show', f"{COMMIT}:{row['path']}"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(f"Pinned source unavailable: {row['path']}. Use a full clone "
                           f"containing {COMMIT}, or fetch that commit, then retry in a new workspace. "
                           + result.stderr.decode(errors='replace')[:300])
    return verified(result.stdout, row)


def core_bytes(row):
    parts = row.get('stored_parts')
    data = (b''.join(safe_path(HERE, part).read_bytes() for part in parts)
            if parts else safe_path(HERE, row['stored_path']).read_bytes())
    encoding = row.get('encoding', 'identity')
    if encoding == 'gzip':
        data = gzip.decompress(data)
    elif encoding != 'identity':
        raise ValueError(f'Unsupported encoding: {encoding}')
    return verified(data, row)


def check_runtime_cache_safety(core):
    paths = {r['path'] for r in core if r.get('materialize', True)}
    for path in paths:
        if path.startswith('work_v2_20261019/fusion/pools/') and path.endswith('/context.json'):
            parent = path.rsplit('/', 1)[0]
            for name in ['states.json.gz', 'requests.json.gz', 'request_results.json.gz']:
                if parent + '/' + name not in paths:
                    raise ValueError('Incomplete pool cache: context cannot be materialized without ' + parent + '/' + name)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repository', type=Path, help='Clone root; otherwise discovered by Git')
    ap.add_argument('--workspace', type=Path, required=True, help='NEW independent directory; never the source archive directory')
    ap.add_argument('--stage', choices=STAGES, default='verify')
    ap.add_argument('--execute', action='store_true', help='Run requested scientific stage in the new copy')
    ap.add_argument('--install-deps', action='store_true', help='Create a workspace venv and pip-install the original pinned requirements')
    ap.add_argument('--jobs', type=int, default=3)
    ap.add_argument('--fetch-originals', action='store_true', help='Pass original-image retrieval to viewer stage only')
    ap.add_argument('--check-only', action='store_true', help='Verify stored core and source hashes without creating a workspace')
    ap.add_argument('--smoke', action='store_true', help='Verify the three frozen profile inputs without model fitting')
    args = ap.parse_args()
    if args.jobs < 1:
        ap.error('--jobs must be positive')
    if args.fetch_originals and args.stage != 'viewer':
        ap.error('--fetch-originals requires --stage viewer')
    repo = args.repository
    if repo is None:
        cp = subprocess.run(['git', '-C', str(HERE), 'rev-parse', '--show-toplevel'],
                            check=True, capture_output=True, text=True)
        repo = Path(cp.stdout.strip())
    repo = repo.resolve()
    workspace = args.workspace.resolve()
    if workspace == HERE or HERE.is_relative_to(workspace) or workspace == repo:
        ap.error('Workspace must be independent from the curated source directory and clone root')
    core = rows(HERE / 'PORTABLE_MANIFEST.json')
    sources = rows(HERE / 'SOURCE_FILES.json')
    check_runtime_cache_safety(core)
    if workspace.exists() and not args.check_only:
        ap.error('Workspace already exists. Choose a new directory; existing results are never overwritten.')
    # All hashes checked before any science executes. Staging avoids exposing a partial workspace.
    if not args.check_only:
        workspace.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=workspace.name + '.preparing.', dir=workspace.parent))
    else:
        staging = None
    try:
        for group, prefix, loader in [(sources, 'repo_main_20261019/', lambda row: source_bytes(repo, row)),
                                       (core, '', core_bytes)]:
            for row in group:
                data = loader(row)
                if staging is not None and row.get('materialize', True):
                    dest = safe_path(staging, prefix + row['path'])
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
        receipt = {'source_commit': COMMIT, 'source_files_verified': len(sources),
                   'retained_files_verified': len(core), 'original_archives_required': False,
                   'original_full_payload_verified': False, 'science_executed': False,
                   'portable_manifest_sha256': digest((HERE/'PORTABLE_MANIFEST.json').read_bytes())}
        if staging is not None:
            (staging / 'BOOTSTRAP_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
            staging.rename(workspace)
            staging = None
        print(json.dumps(receipt, indent=2), flush=True)
    finally:
        if staging is not None:
            # Only this newly-created incomplete temporary directory is removed.
            shutil.rmtree(staging)
    if args.check_only:
        return
    python = sys.executable
    work = workspace / 'work_v2_20261019'
    if args.install_deps:
        subprocess.run([python, '-m', 'venv', str(workspace / '.venv')], check=True)
        python = str(workspace / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python'))
        subprocess.run([python, '-m', 'pip', 'install', '-r', str(work / 'requirements.txt')], check=True)
    if args.smoke:
        subprocess.run([python, str(work/'profiles/reproduce_forward_profiles.py'),
                        '--repo', str(workspace/'repo_main_20261019'), '--out', str(work/'profiles'),
                        '--evidence', str(work/'audit/person_evidence_62.csv'), '--verify-inputs-only'],
                       cwd=workspace, check=True)
    if args.stage != 'verify':
        command = [python, str(work/'REPRODUCE.py'), '--stage', args.stage, '--jobs', str(args.jobs)]
        if args.execute:
            command.append('--execute')
        if args.fetch_originals:
            command.append('--fetch-originals')
        subprocess.run(command, cwd=workspace, check=True)
    else:
        print('Verified retained core and frozen source only. Omitted derived payloads are intentionally absent.')
    print('Replay workspace:', workspace)
    print('Continue using this workspace’s unchanged work_v2_20261019/REPRODUCE.py; verification of the original full archive is separate.')


if __name__ == '__main__':
    main()
