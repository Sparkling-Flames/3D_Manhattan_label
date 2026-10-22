#!/usr/bin/env python3
"""Independent count/formula audit plus optional SciPy correlation cross-check."""
import csv
import hashlib
import itertools
import json
import math
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parent
data=json.loads((ROOT/'inputs/review36_user_20261008.json').read_text())
geometry=json.loads((ROOT/'inputs/frozen_geometry.json').read_text())
source={a['id']:a for im in geometry['images'] for a in im['annotations']}
groups=defaultdict(list)
for r in data['ratings']:groups[r['imageCode']].append(r)
try:
    from scipy.stats import spearmanr, kendalltau
except ImportError:
    spearmanr=kendalltau=None
audit=[]
for out in csv.DictReader((ROOT/'analysis/imagewise_ordinal/metric_by_image.csv').open(encoding='utf-8-sig')):
    key=out['metric']; direction=1 if key=='iou' else -1
    vals=[]
    for r in groups[out['image']]:
        x=source[r['recordId']]['metricsByReference'][r['referenceVersion']]['metrics'].get(key)
        if isinstance(x,(int,float)) and math.isfinite(x):vals.append((r['overallScore'],direction*x))
    c=d=m=h=z=0
    for (y1,x1),(y2,x2) in itertools.combinations(vals,2):
        if y1==y2:
            if x1==x2:z+=1
            else:h+=1
        elif x1==x2:m+=1
        elif (y1-y2)*(x1-x2)>0:c+=1
        else:d+=1
    assert [c,d,m,h+z]==[int(out[k]) for k in ['concordant','discordant','metric_tied_on_human_distinct','n_human_tied_pairs']]
    checked=False
    if len(vals)>1 and spearmanr:
        ys,xs=zip(*vals)
        assert math.isclose(spearmanr(ys,xs).statistic,float(out['spearman_rho']),abs_tol=1e-13)
        assert math.isclose(kendalltau(ys,xs).statistic,float(out['kendall_tau_b']),abs_tol=1e-13)
        checked=True
    audit.append(dict(image=out['image'],metric=key,counts_match=True,scipy_correlation_checked=checked))
scales=geometry['scales']; formula_checks=0
for a in source.values():
    for rv in a['metricsByReference'].values():
        m=rv['metrics'];lc=1-m['iou']+0.5*m['C']
        expected=dict(LC=lc,LCT=lc+0.3*scales['L']*m['T']/scales['T'],
            LCG=lc+0.3*scales['L']*(m['dir']/scales['dir']+m['flat']/scales['flat'])/2)
        for k,v in expected.items():assert math.isclose(v,m[k],abs_tol=1e-13)
        formula_checks+=3
# Rerun in a clean output directory; compare all analytical outputs byte for byte.
with tempfile.TemporaryDirectory(prefix='review36-check-') as td:
    subprocess.run([sys.executable,str(ROOT/'analyze_imagewise.py'),'--out',td],check=True,capture_output=True,text=True)
    same=[]
    for path in Path(td).iterdir():
        assert path.read_bytes()==(ROOT/'analysis/imagewise_ordinal'/path.name).read_bytes()
        same.append(path.name)
out=dict(status='passed',per_image_metric_audits=len(audit),
    independent_pair_counts_all_match=True,
    scipy_correlation_audits=sum(x['scipy_correlation_checked'] for x in audit),
    fixed_metric_formula_checks=formula_checks,deterministic_rerun_files=sorted(same),
    input_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'inputs').iterdir()) if p.is_file()})
(ROOT/'analysis/imagewise_ordinal/verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False,indent=2))
