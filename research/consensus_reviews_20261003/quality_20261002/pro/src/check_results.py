"""Focused checks of this independent experiment, not the repository test suite."""
from pathlib import Path
import json, numpy as np
from quality_core import *
B=Path(__file__).resolve().parents[1]
r=json.loads((B/'results/controlled_results.json').read_text())
inputs=json.loads((B/'inputs/controlled_inputs.json').read_text())
checks=[]
def check(name,value):
    assert value,name
    checks.append({'check':name,'passed':bool(value)})
# Model and geometric invariance checks are not visual correctness checks.
for name in ['density','derived_real_subdivision']:
    cases=[c for c in inputs if c['case']==name]
    errors=[]
    for c in cases:
        a,b=reconstruct(c['a']),reconstruct(c['b']);m=compare(a,b)
        errors.append(max(abs(m['bev_iou']-1),abs(m['current_model_volume_iou']-1),abs(m['column_iou']-1)))
    check(name+'_current_geometry_invariance',max(errors)<1e-10)
check('opposing_roofs_equal_proxy_not_equal_volume',abs(r['opposite_roofs']['current_model_volume_iou']-1)<1e-10 and r['opposite_roofs']['exact_synthetic_volume_iou']<.72)
check('fixed_top_pixels_unchanged',r['top_bottom_dependency']['max_top_pixel_change']<1e-10)
check('height_volume_coupling_analytic',abs(r['top_bottom_dependency']['current_model_volume_iou']-.55296)<1e-10)
check('horizon_amplification',r['horizon'][1]['one_corner_shift_h']>100*r['horizon'][0]['one_corner_shift_h'])
# Constant-height same-floor model cannot exceed its 2D IoU.
vals=[]
for c in inputs:
    m=compare(reconstruct(c['a']),reconstruct(c['b']))
    vals.append(m['current_model_volume_iou']<=m['bev_iou']+1e-12)
check('current_model_volume_not_above_bev',all(vals))
sq=np.array([[-2,-2],[2,-2],[2,2],[-2,2]],float)
a=reconstruct(record_from_geometry(sq,2.7));b=reconstruct(record_from_geometry(sq[::-1],2.7));m=compare(a,b)
check('ring_reversal_invariance',abs(m['current_model_volume_iou']-1)<1e-10 and m['column_iou']==1)
(B/'results/checks.json').write_text(json.dumps({'n':len(checks),'checks':checks},indent=2)+'\n')
print(f'{len(checks)} focused checks passed')
