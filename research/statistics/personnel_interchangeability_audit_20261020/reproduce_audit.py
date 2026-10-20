"""Run selected independent checks in an explicit, separate work directory."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--work-root', type=Path, required=True)
parser.add_argument('--bundle-root', type=Path, required=True)
parser.add_argument('--restored-root', type=Path)
parser.add_argument('--stage', choices=['statistics', 'frozen-inputs'], required=True)
args = parser.parse_args()
root = args.work_root.resolve()
root.mkdir(parents=True, exist_ok=True)
source = Path(__file__).resolve().parent
def link(name, target):
    dest = root / name
    target = target.resolve()
    if not target.exists():
        raise FileNotFoundError(target)
    if dest.exists() or dest.is_symlink():
        if dest.resolve() != target:
            raise ValueError(f'Refuse to replace different input: {dest}')
    else:
        dest.symlink_to(target, target_is_directory=True)
link('unpacked', args.bundle_root)
if args.restored_root:
    link('restored', args.restored_root)
scripts = ['recompute.py', 'uncertainty.py'] if args.stage == 'statistics' else ['verify_frozen_inputs.py']
directory = 'statistics' if args.stage == 'statistics' else 'replay'
out = root / ('audit_statistics' if directory == 'statistics' else 'audit_replay')
out.mkdir(exist_ok=True)
env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
for name in scripts:
    text = (source / directory / name).read_text()
    text = text.replace('/workspace/shared/interchangeability_audit_20261020', root.as_posix())
    dst = out / name
    if dst.exists() and dst.read_text() != text:
        raise ValueError(f'Existing code differs: {dst}; use a fresh work root')
    dst.write_text(text)
    subprocess.run([sys.executable, str(dst)], cwd=root, env=env, check=True)
