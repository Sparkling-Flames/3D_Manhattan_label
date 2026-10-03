"""Replay analysis into a fresh directory without touching frozen inputs/results."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args()
out=args.out.resolve()
if out.exists():raise ValueError('output must not exist')
expected=json.loads((ROOT/'results_v2/summary.json').read_text())['inputs']
for name,digest in expected.items():
    assert hashlib.sha256((ROOT/'inputs'/name).read_bytes()).hexdigest()==digest,name
out.mkdir(parents=True)
env=os.environ.copy();env['OPENBLAS_NUM_THREADS']='1';env['PYTHONDONTWRITEBYTECODE']='1'
def run(*command,log):
    with (out/log).open('w') as f:
        subprocess.run([sys.executable,'-B',*map(str,command)],stdout=f,stderr=subprocess.STDOUT,env=env,check=True)
run('-m','unittest','discover','-s',ROOT/'tests','-v',log='tests.log')
run(ROOT/'src/explore_replacements.py','--source-dir',ROOT/'inputs','--out',out/'results',log='main.log')
run(ROOT/'src/restricted_pool_sensitivity.py','--source-dir',ROOT/'inputs','--out',out/'restricted_results',log='restricted.log')
run(ROOT/'src/summarize_concentration.py','--results',out/'results','--restricted',out/'restricted_results',log='concentration.log')
run(ROOT/'src/reference_paired_replacement.py','--source-dir',ROOT/'inputs','--out',out/'comparator_results',log='comparator.log')
run(ROOT/'src/validate_reference_comparator.py','--source-dir',ROOT/'inputs','--results',out/'results','--comparator',out/'comparator_results','--out',out/'comparator_validation.json',log='comparator_check.log')
print(out)
