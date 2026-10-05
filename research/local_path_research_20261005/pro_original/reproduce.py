"""Reproduce every final numeric stage in a NEW directory (no repository needed)."""
from pathlib import Path
import argparse,sys
ROOT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'upstream_minimal'))
from run_research import construct,evaluate
from diagnostic_extensions import run as extensions
from real_diagnostics import run as real
from tools.thesis_main.analysis.local_shortcut_projection_20261005 import run as upstream
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
a.out.mkdir(parents=True,exist_ok=False)
construct(a.out/'finite')
# Frozen candidate and policy outputs exist before the evaluation stage opens truth.
evaluate(a.out/'finite')
extensions(a.out/'finite')
real(a.out/'real')
upstream(a.out/'upstream_projection')
print('Completed all finite-domain and real diagnostic stages; no visual review.')
