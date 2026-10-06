"""One-command reproduction of the explicitly available old-panel study."""
from pathlib import Path
import sys,argparse
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from run import run
from analysis import analyze
from controls import run_controls
from patches import run_patches
from evaluate import evaluate
from summarize import summarize
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
 run(a.out);analyze(a.out);run_controls(a.out);run_patches(a.out);evaluate(a.out);summarize(a.out)
 print('Completed. This is not acceptance of the missing latest-local-worktree package.')
