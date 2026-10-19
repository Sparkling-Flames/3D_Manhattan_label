#!/usr/bin/env python3
"""Equivalent accelerated execution wrapper; frozen original implementation retained.

Only aggregation functions are replaced by the independently crosschecked sidecar.
Candidate class construction, folds, support, priors, objective and 1SE are unchanged.
"""
from pathlib import Path
import sys,json,hashlib,time
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H.parent/'forward'))
import selection_fast
import discover_reverse_types as original
parity=json.loads((H/'FAST_SELECTION_PARITY.json').read_text())
fast_sha=hashlib.sha256((H.parent/'forward/selection_fast.py').read_bytes()).hexdigest()
assert parity['passed'] and parity['fast_sidecar_sha256']==fast_sha
original.fit_calibrator=selection_fast.fit_calibrator
original.predict_calibrator=selection_fast.predict_calibrator
original.building_brier=selection_fast.building_brier
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (H/'results/folds').glob('*/COMPLETE.json')}
owned_folds=set(sys.argv[sys.argv.index('--folds')+1].split(',')) if '--folds' in sys.argv else None
original.main()
for p in (H/'results/folds').glob('*/COMPLETE.json'):
    if owned_folds is not None and p.parent.name not in owned_folds:continue
    now=hashlib.sha256(p.read_bytes()).hexdigest()
    if str(p) in before and before[str(p)]==now:continue
    r=json.loads(p.read_text());r['execution_implementation']='equivalent_numpy_sidecar'
    r['fast_sidecar_sha256']=fast_sha;r['fast_parity_receipt']='reverse/FAST_SELECTION_PARITY.json'
    original.write_json(p,r)
