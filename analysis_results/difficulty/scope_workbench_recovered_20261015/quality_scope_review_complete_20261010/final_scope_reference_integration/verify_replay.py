#!/usr/bin/env python3
"""Relocate only the standalone code and inputs; compare every core result byte-for-byte."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from recompute_bev import ROOT, save, sha

CORE = [
    'reference_registry.json', 'source_bindings.json', 'record_metrics.json', 'record_metrics.csv',
    'space_record_metrics.json', 'space_record_metrics.csv',
    'image_summary.json', 'image_summary.csv', 'condition_gate_summary.json',
    'condition_gate_summary.csv', 'previous_confirmed_floor_delta.json',
    'historical_artifact_applicability.json', 'floor_geometry_changes.json',
    'floor_geometry_changes.csv', 'summary.json', 'unavailable_records.json', 'unavailable_records.csv', 'validation.json',
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--report', type=Path)
    args = p.parse_args()
    with tempfile.TemporaryDirectory(prefix='scope_bev_relocated_') as folder:
        relocated = Path(folder)
        shutil.copyfile(ROOT / 'recompute_bev.py', relocated / 'recompute_bev.py')
        shutil.copytree(ROOT / 'inputs', relocated / 'inputs')
        env = os.environ.copy()
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        # Preserve only installed dependencies; remove relative search paths before changing cwd.
        if env.get('PYTHONPATH'):
            env['PYTHONPATH'] = os.pathsep.join(str(Path(p).resolve()) for p in env['PYTHONPATH'].split(os.pathsep) if p)
        proc = subprocess.run([sys.executable, str(relocated / 'recompute_bev.py')], cwd=relocated,
                              env=env, text=True, capture_output=True)
        if proc.returncode:
            raise RuntimeError(proc.stdout + proc.stderr)
        checks = [{'file': name, 'sha256': sha(ROOT / 'results' / name),
                   'relocated_sha256': sha(relocated / 'results' / name),
                   'byte_identical': (ROOT / 'results' / name).read_bytes() == (relocated / 'results' / name).read_bytes()}
                  for name in CORE]
        assert all(c['byte_identical'] for c in checks)
        result = {'passed': True, 'core_files_byte_identical': len(checks), 'checks': checks,
                  'portable_inputs': sorted(p.name for p in (ROOT / 'inputs').iterdir()),
                  'repository_required_for_replay': False, 'network_required_for_replay': False,
                  'operation': 'Copied only recompute_bev.py and inputs into a fresh temporary directory, ran with relocated defaults.'}
        if args.report:
            save(args.report, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
