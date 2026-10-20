"""Repository entry point for the frozen personnel follow-up research tools."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
FOLLOWUP = ROOT / 'research/workers/personnel_interchangeability_followup_20261020'
AUDIT = ROOT / 'research/statistics/personnel_interchangeability_audit_20261020'
ENTRY = {
    'corner': FOLLOWUP / 'audit_corner/evaluate_corner_extension.py',
    'learning': FOLLOWUP / 'audit_learning/reproduce_learning.py',
    'audit': AUDIT / 'reproduce_audit.py',
    'direct-block-check': FOLLOWUP / 'audit_corner/evaluate_direct_block_family.py',
}
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('component', choices=sorted(ENTRY))
    args, rest = parser.parse_known_args()
    if rest[:1] == ['--']:
        rest = rest[1:]
    return subprocess.call([sys.executable, str(ENTRY[args.component]), *rest])
if __name__ == '__main__':
    raise SystemExit(main())
