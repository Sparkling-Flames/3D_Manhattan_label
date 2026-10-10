"""Offline replay of compact geometry; compare statuses, missingness and frozen components."""
import argparse,sys,math,time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from common import read,save,csvwrite
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'frozen/scope_engine/core'))
from quality_v11 import score_geometry

def job(arg):
    row,a,g=arg;r=score_geometry(a,g,spherical_samples=2048,height_samples=4096)
    deltas={};errors=[]
    if r['status']!=row['current_Q_status']:errors.append('status')
    if r['reason_codes']!=row['failure_codes']:errors.append('reason_codes')
    if row['Q'] is None:
        if r['quality_score'] is not None:errors.append('Q_null')
    elif r['quality_score'] is None or abs(row['Q']-r['quality_score'])>1e-9:errors.append('Q')
    for key in ['iou_2d','iou_3d_corner_mean','S_top_deg','S_bottom_deg','boundary_rms_deg','Hmean','Hlocal','Hstar','dir','flat','direction_bounded_loss','flatness_bounded_loss']:
        a=row.get(key);b=r['metrics'].get(key)
        if a is None or b is None:
            if a!=b:errors.append(key+'_missing')
        else:
            delta=abs(a-b);deltas[key]=delta
            if delta>1e-9:errors.append(key+'_numeric')
    return {'record_id':row['record_id'],'passed':not errors,'errors':errors,'max_numeric_delta':max(deltas.values(),default=0),'component_deltas':deltas}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=4);args=ap.parse_args()
    rows=read(ROOT/'results/current_components.json');geos=read(ROOT/'inputs/current_geometry_compact.json')['geometries'];jobs=[(r,geos[r['object_id']],geos[r['reference_object_id']]) for r in rows];t=time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:checks=list(pool.map(job,jobs,chunksize=8))
    csvwrite(ROOT/'results/offline_replay_checks.csv',checks);summary={'n_all_events':len(checks),'passed':all(r['passed'] for r in checks),'failed':sum(not r['passed'] for r in checks),'maximum_component_delta':max(r['max_numeric_delta'] for r in checks),'elapsed_seconds':time.perf_counter()-t,'missing_values_and_reasons_checked':True};save(ROOT/'results/offline_replay_summary.json',summary);print(summary);assert summary['passed']
if __name__=='__main__':main()
