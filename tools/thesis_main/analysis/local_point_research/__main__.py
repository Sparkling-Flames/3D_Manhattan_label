"""python -m tools.thesis_main.analysis.local_point_research [--input-root PATH] [--output PATH]"""
import argparse
import contextlib
import hashlib
import importlib
import json
from pathlib import Path

import pandas as pd
import numpy as np

from .local_points import ROOT


def main():
    parser = argparse.ArgumentParser(description='复算已接收的探索快照；原包结果只读')
    parser.add_argument('--input-root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(); root = args.input_root.resolve()
    out = (args.output or root/'local_recheck').resolve()
    protected = [root/name for name in ['inputs','received_results','results','source_code','previous_pairing_time']]
    if out == root or out in protected or any(p in out.parents for p in protected):
        raise ValueError('output must not overwrite received evidence')
    for f in json.loads((root/'INPUT_MANIFEST.json').read_text(encoding='utf-8'))['files']:
        if hashlib.sha256((root/f['path']).read_bytes()).hexdigest() != f['sha256']:
            raise ValueError('input changed: '+f['path'])
    out.mkdir(parents=True,exist_ok=True)
    (out/'visual_cases.json').write_bytes((root/'inputs/analyst_visual_observations.json').read_bytes())
    for name in ['local_points','precision_audit','review_audit','exemplar_cover','validate_and_summarize',
                 'same_person_time','no_borrowed_points','point_witnesses','audit_extensions']:
        module = importlib.import_module('.'+name,__package__)
        with (out/(name+'.log')).open('w',encoding='utf-8') as log, contextlib.redirect_stdout(log):
            module.run(root,out)
        print('completed '+name,flush=True)
    checks = []
    for original in sorted((root/'received_results').glob('*.csv')):
        current = out/original.name
        if not current.exists(): raise ValueError('missing reproduced table: '+original.name)
        expected, actual = pd.read_csv(original), pd.read_csv(current)
        if actual.shape != expected.shape or list(actual.columns) != list(expected.columns):
            raise ValueError('schema drift: '+original.name)
        changes = {}
        for column in actual:
            a,b = actual[column],expected[column]
            if pd.api.types.is_numeric_dtype(a) and not pd.api.types.is_bool_dtype(a):
                changed = ~np.isclose(a,b,atol=1e-9,rtol=1e-9,equal_nan=True)
            else:
                changed = ~(a.eq(b) | (a.isna() & b.isna()))
            if np.any(changed):
                indices = np.flatnonzero(changed)
                changes[column] = dict(cells=len(indices),first_rows=indices[:10].tolist())
        checks.append(dict(table=original.name,rows=len(actual),matches_at_1e_9=not changes,differences=changes))
    (out/'REPRODUCTION_CHECK.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    print(f'Compared {len(checks)} tables; {sum(bool(r["differences"]) for r in checks)} have differences recorded. Not semantic validation.',flush=True)


if __name__ == '__main__': main()
