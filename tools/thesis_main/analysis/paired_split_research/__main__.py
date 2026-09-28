"""Reproduce accepted research into separate outputs; received evidence stays read-only."""
import argparse
import contextlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from . import study, diagnostics, checks


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input-root',type=Path,default=study.ROOT);ap.add_argument('--output',type=Path)
    args=ap.parse_args();root=args.input_root.resolve();out=(args.output or root/'local_recheck').resolve()
    protected=[root/n for n in ['inputs','source_code','received_results','received_min_horizontal','report','visual_checked']]
    if out==root or any(out==p or p in out.parents for p in protected):raise ValueError('output overlaps frozen evidence')
    out.mkdir(parents=True,exist_ok=True)
    for name,policy in [('sensitivity_min_horizontal_results','min_horizontal'),('results','legacy_guarded')]:
        with (out/(name+'.log')).open('w',encoding='utf-8') as log,contextlib.redirect_stdout(log):study.run(root,policy,out/name)
        print('completed '+policy,flush=True)
    with (out/'diagnostics.log').open('w',encoding='utf-8') as log,contextlib.redirect_stdout(log):
        diagnostics.run(root,out);checks.run(root,out)
    report=[]
    for old,new in [('received_results','results'),('received_min_horizontal','sensitivity_min_horizontal_results')]:
        for p in sorted((root/old).iterdir()):
            if not (p.name.endswith('.csv') or p.name.endswith('.csv.gz')):continue
            a=pd.read_csv(p);b=pd.read_csv(out/new/p.name)
            if list(a.columns)!=list(b.columns) or a.shape!=b.shape:raise ValueError('schema drift: '+p.name)
            differences={}
            for c in a:
                if pd.api.types.is_numeric_dtype(a[c]) and not pd.api.types.is_bool_dtype(a[c]):
                    diff=~np.isclose(a[c],b[c],atol=1e-9,rtol=1e-9,equal_nan=True)
                else:diff=~(a[c].eq(b[c])|(a[c].isna()&b[c].isna()))
                if np.any(diff):differences[c]=int(np.sum(diff))
            report.append(dict(table=old+'/'+p.name,rows=len(a),differences=differences))
    study.dump(out/'REPRODUCTION_CHECK.json',report)
    print(f'Compared {len(report)} tables; {sum(bool(r["differences"]) for r in report)} differ. See REPRODUCTION_CHECK.json.',flush=True)


if __name__=='__main__':main()
