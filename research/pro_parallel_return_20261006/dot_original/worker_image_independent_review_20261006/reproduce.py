#!/usr/bin/env python3
"""Run local-only descriptive checks on the supplied transferred arrays."""
import argparse,subprocess,sys
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--output',default='results_recomputed');a=p.parse_args()
root=Path(__file__).resolve().parent;out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
source=root/'input'/'panel_transferred.json'
def run(script,*args):subprocess.run([sys.executable,str(root/script),*map(str,args)],check=True)
run('validate_transfer.py',source,out/'validation.json')
run('convert_transfer.py',source,out/'panel_cells.csv')
run('panel_sensitivity.py',out/'panel_cells.csv',out)
run('verify_claims.py',out)
with (out/'exact_checks.json').open('w') as f:subprocess.run([sys.executable,str(root/'exact_checks.py')],stdout=f,check=True)
print(f'Finished: {out}')
