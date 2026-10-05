#!/usr/bin/env python3
"""Recompute in a new temporary directory, comparing deterministic data artifacts."""
import hashlib, json, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='path-evidence-replay-') as p:
    out=Path(p)
    subprocess.run([sys.executable,'-B',str(ROOT/'independent_audit.py'),'--out',str(out)],check=True,stdout=subprocess.DEVNULL)
    checked=[]
    for ref in sorted((ROOT/'results').iterdir()):
        if ref.suffix not in ('.json','.csv') or ref.name=='delivered_comparison.json': continue
        actual=out/ref.name
        assert actual.read_bytes()==ref.read_bytes(),ref.name
        checked.append({'file':ref.name,'sha256':hashlib.sha256(ref.read_bytes()).hexdigest()})
    print(json.dumps({'verified':True,'reproduced_data_artifacts':len(checked),'files':checked},ensure_ascii=False,indent=2))
