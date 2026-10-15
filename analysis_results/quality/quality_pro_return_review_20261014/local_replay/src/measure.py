"""Rebuild frozen points and measure stage-specific cohorts. Writes only results/.
Stage1 never uses doorway scores. Stage2 requires a pre-existing stage1 freeze.
"""
import argparse,time,sys
from collections import Counter
import numpy as np
from core import *

def main(phase):
    if phase=='doorway' and not (ROOT/'configs/ordinary_frozen.json').exists():
        raise RuntimeError('ordinary_freeze_required_before_doorway_measurement')
    start=time.time();c=read(INPUT/'data/cohorts.json');obj=read(INPUT/'data/objects.json');o={r['object_id']:r for r in obj['objects']}
    source_coarse=read(INPUT/'stage/COARSE.json')
    rows=(c['ordinary']+c['severe']+c['historical_only']) if phase=='ordinary' else [r for r in c['doorway'] if r['status']=='complete']
    out=[];failures=[]
    for i,r in enumerate(rows):
        rid=r['record_id'];oid=r['object_id'];ref=r.get('reference_object_id') or r['reference']['object_id']
        try:
            a=geometry(o[oid]['points_1024x512']);g=geometry(o[ref]['points_1024x512'])
            errors={xx+':'+name:float(np.max(abs(np.asarray(x[name])-np.asarray(obj['geometries'][xx][name])))) for xx,x in [(oid,a),(ref,g)] for name in ('bottom3d','top3d')}
            if max(errors.values())>1e-9:raise AssertionError('frozen_geometry_drift:'+rid+str(errors))
            measured=full_measure(a,g);m=measured['metrics']
            delta={k:abs(m[k]-r['metrics'][k]) for k in METRICS} if m else {}
            legacy_iou=source_coarse['current_iou3d'].get(rid,r['metrics'].get('iou_3d_corner_mean'))
            if isinstance(legacy_iou,dict):print('unexpected',legacy_iou);raise ValueError('iou_type')
            if legacy_iou is not None and m is not None:delta['iou_3d_corner_mean']=abs(m['iou_3d_corner_mean']-legacy_iou)
            out.append(dict(record_id=rid,object_id=oid,reference_object_id=ref,source_layer=next((k for k in ('ordinary','severe','historical_only','doorway') if r in c[k]),''),
                input_sha256=digest(o[oid]['points_1024x512']),reference_sha256=digest(o[ref]['points_1024x512']),
                geometry_max_abs_difference=max(errors.values()),metric_abs_differences=delta,**measured))
        except Exception as err:
            failures.append(dict(record_id=rid,path='data/objects.json',error=type(err).__name__+':'+str(err)))
        if (i+1)%100==0:print(phase,i+1,'of',len(rows), 'failures',len(failures),flush=True)
    summary=dict(phase=phase,count=len(out),requested=len(rows),failures=failures,statuses=dict(Counter(r['status'] for r in out)),
        max_geometry_difference=max((r['geometry_max_abs_difference'] for r in out),default=None),
        max_metric_difference={k:max((r['metric_abs_differences'].get(k,0) for r in out),default=None) for k in METRICS+('iou_3d_corner_mean',)},
        seconds=time.time()-start,method='all_admitted_pairs_rebuilt_from_frozen_processed_points_not_saved_metrics')
    dump(ROOT/f'results/{phase}_reconstruction.json',dict(summary=summary,records=out));print(summary,flush=True)
    if phase=='ordinary':
        controls=read(INPUT/'data/control_geometries.json');saved={r['record_id']:r for r in source_coarse['controls']};b={f"quality_calibration_preparation_20261013:{r['case_id']}":r for r in read(INPUT/'preparation/BOTTOM_CONTROLS.json')['rows']}
        cout=[]
        for i,r in enumerate(controls):
            rid=r['record_id'];a=r['annotation_geometry'];g=r['reference_geometry'];method='supplied_synthetic_geometry_remeasured'
            if rid in b:
                a=geometry(b[rid]['points']);g=geometry(b[rid]['reference_points']);method='bottom_control_from_original_points'
            measured=full_measure(a,g);m=measured['metrics'];sm=saved[rid]['metrics']
            delta={k:abs(m[k]-sm[k]) for k in METRICS} if m else {}
            cout.append(dict(record_id=rid,method=method,metric_abs_differences=delta,**measured))
        dump(ROOT/'results/control_reconstruction.json',dict(count=len(cout),max_metric_difference={k:max(r['metric_abs_differences'].get(k,0) for r in cout) for k in METRICS},records=cout))
        print('controls',len(cout),'remeasured',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['ordinary','doorway'],required=True);main(p.parse_args().phase)
