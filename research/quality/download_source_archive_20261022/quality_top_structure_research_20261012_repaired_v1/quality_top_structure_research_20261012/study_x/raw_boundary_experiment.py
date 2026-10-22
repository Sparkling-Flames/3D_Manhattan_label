#!/usr/bin/env python3
"""Compare unaveraged angular boundary rings with the frozen shared-x baseline.

No top/bottom or GT pairing is inferred. Uses the existing complete source pair
identity and existing ring view only. It compares declared minor great-circle
arcs, not visibility envelopes and not a unique unshared-x 3-D room.
"""
from __future__ import annotations
import argparse,csv,json,math,pathlib,sys,time
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
import numpy as np
from scipy.stats import spearmanr
from audit_representation import save_json,save_csv,count_quantiles,BASE

def rays(points):
    p=np.asarray(points,float);u=2*np.pi*(p[:,0]/1024-.5);v=np.pi*(.5-p[:,1]/512)
    return np.column_stack((np.cos(v)*np.sin(u),np.sin(v),-np.cos(v)*np.cos(u)))

def init(engine):
    sys.path.insert(0,str(pathlib.Path(engine)/'core'))
    from quality_v11 import scalar_score
    from geometric_components import spherical_sym_distance
    global SCORE,DIST
    SCORE=scalar_score;DIST=spherical_sym_distance

def one(job):
    rid,op,pre,gt,old,n=job
    raw=rays(op);shared=rays(pre)
    row=dict(record_id=rid,status='available',new_input_semantics='current_before_with_recorded_pairs_and_ring')
    try:
        rt=DIST(raw[::2],gt['top3d'],n);rb=DIST(raw[1::2],gt['bottom3d'],n)
        st=DIST(shared[::2],gt['top3d'],n);sb=DIST(shared[1::2],gt['bottom3d'],n)
        ptop=DIST(raw[::2],shared[::2],n);pbot=DIST(raw[1::2],shared[1::2],n)
        sr=math.hypot(rt,rb)/math.sqrt(2);ss=math.hypot(st,sb)/math.sqrt(2)
        row.update(S_top_raw_deg=rt,S_bottom_raw_deg=rb,S_raw_rms_deg=sr,
                   S_top_shared_recomputed_deg=st,S_bottom_shared_recomputed_deg=sb,S_shared_rms_deg=ss,
                   raw_minus_shared_top_deg=rt-st,raw_minus_shared_bottom_deg=rb-sb,raw_minus_shared_rms_deg=sr-ss,
                   raw_to_shared_top_deg=ptop,raw_to_shared_bottom_deg=pbot,
                   raw_to_shared_boundary_rms_deg=math.hypot(ptop,pbot)/math.sqrt(2),
                   shared_top_parity_error=st-old['S_top_deg'],shared_bottom_parity_error=sb-old['S_bottom_deg'])
        q=SCORE(old['iou_2d'],rt,rb,old['dir'],old['flat'],old['Hstar'])['quality_score']
        row.update(Q_rawS_same_parameters_diagnostic=q,Q_shared_v11=old['Q'],Q_rawS_minus_shared=q-old['Q'])
    except ValueError as exc:row.update(status='unavailable_raw_boundary',reason=str(exc))
    return row

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--previous',default='previous_research/quality_calibration_research_20261011')
    ap.add_argument('--signals',default='study_x/results/representation_signals_all3152.csv');ap.add_argument('--out',default='study_x/results');ap.add_argument('--workers',type=int,default=2)
    args=ap.parse_args();p=pathlib.Path(args.previous);out=pathlib.Path(args.out);engine=p/BASE/'frozen/scope_engine'
    data=json.loads((p/BASE/'inputs/current_formal_loader_data.json').read_text());objs={o['object_id']:o for o in data['objects']}
    comp={r['record_id']:r for r in json.loads((p/BASE/'results/current_components.json').read_text())}
    geo=json.loads((p/BASE/'inputs/current_geometry_compact.json').read_text())['geometries']
    sig=list(csv.DictReader(open(args.signals,encoding='utf-8-sig')))
    include=[r for r in sig if r['held_out']=='False' and r['pair_mechanically_valid']=='True' and r['source_midpoint_verified']=='True' and r['source_ring_view_verified']=='True' and (
             r['target_dev_907']=='True' or r['old_quality_case'] or (r['new_review_status'] in ['reviewed_severe','reviewed_borderline_pending'] and r.get('calibration_barrier_free')=='True'))]
    jobs=[];unavailable=[]
    for s in include:
        c=comp[s['record_id']];o=objs[s['object_id']];ref=geo.get(c['reference_object_id'])
        if not c['reference_strict_available'] or not c['annotation_strict_available'] or not ref or c['Q'] is None:
            unavailable.append(dict(record_id=s['record_id'],status='reference_or_annotation_unavailable'));continue
        ordered=np.asarray(o['before_preprocessing_points'],float)[o['ordered_source_point_indices']]
        jobs.append((s['record_id'],ordered.tolist(),o['points_1024x512'],ref,c,2048))
    start=time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers,initializer=init,initargs=(str(engine),)) as pool:rows=list(pool.map(one,jobs,chunksize=8))
    sb={r['record_id']:r for r in sig}
    for r in rows:
        s=sb[r['record_id']]
        for k in ['object_id','image_code','worker_id','building_id','room_id','target_dev_907','pairing_basis','order_status','ring_confirmed','X_pair_rms_deg','X_pair_max_deg','D_deg','F_deg','old_quality_case','old_quality_grade','new_severe_case','new_review_status','display_geometry_mode']:
            r[k]=s[k]
    valid=[r for r in rows if r['status']=='available'];dev=[r for r in valid if r['target_dev_907']=='True']
    def summary(rr):
        return dict(n=len(rr),raw_rms_higher=sum(r['raw_minus_shared_rms_deg']>1e-8 for r in rr),
                    raw_rms_lower=sum(r['raw_minus_shared_rms_deg']< -1e-8 for r in rr),
                    raw_rms_same=sum(abs(r['raw_minus_shared_rms_deg'])<=1e-8 for r in rr),
                    delta_S_rms=count_quantiles([r['raw_minus_shared_rms_deg'] for r in rr]),
                    delta_Q_rawS_same_parameters=count_quantiles([r['Q_rawS_minus_shared'] for r in rr]),
                    X_rms_vs_D_spearman=float(spearmanr([float(r['X_pair_rms_deg']) for r in rr],[float(r['D_deg']) for r in rr]).statistic),
                    X_rms_vs_F_spearman=float(spearmanr([float(r['X_pair_rms_deg']) for r in rr],[float(r['F_deg']) for r in rr]).statistic),
                    X_rms_vs_sharedS_spearman=float(spearmanr([float(r['X_pair_rms_deg']) for r in rr],[r['S_shared_rms_deg'] for r in rr]).statistic),
                    X_rms_vs_rawS_increment_spearman=float(spearmanr([float(r['X_pair_rms_deg']) for r in rr],[r['raw_minus_shared_rms_deg'] for r in rr]).statistic))
    quality=[r for r in valid if r['old_quality_case']]
    rank=[]
    grades={'可接受':0,'有轻微问题':1,'明显问题':2,'严重不可接受':3}
    for i,a in enumerate(quality):
        for b in quality[:i]:
            if grades[a['old_quality_grade']]==grades[b['old_quality_grade']]:continue
            better,worse=(a,b) if grades[a['old_quality_grade']]<grades[b['old_quality_grade']] else (b,a)
            rank.append(dict(better_case=better['old_quality_case'],worse_case=worse['old_quality_case'],
                     old_inversion=better['Q_shared_v11']<worse['Q_shared_v11'],rawS_inversion=better['Q_rawS_same_parameters_diagnostic']<worse['Q_rawS_same_parameters_diagnostic']))
    report=dict(selected_total=len(include),job_n=len(jobs),available=len(valid),unavailable=unavailable+[r for r in rows if r['status']!='available'],
        shared_boundary_recompute_max_abs=max(abs(r[k]) for r in valid for k in ['shared_top_parity_error','shared_bottom_parity_error']),
        target_dev=summary(dev),quality24=summary(quality),
        quality24_rank_diagnostic=dict(cross_grade_pairs=len(rank),v11_inversions=sum(r['old_inversion'] for r in rank),rawS_same_parameter_inversions=sum(r['rawS_inversion'] for r in rank)),
        elapsed_seconds=time.perf_counter()-start,
        semantics='No unshared 3D inferred; current raw angular boundary compared with fixed reference by existing spherical minor-arc integral. Scores are same-formula diagnostics, not fitted/calibrated recommendations.',
        preserved_holdout=True)
    save_csv(out/'raw_boundary_cases.csv',rows);save_csv(out/'raw_boundary_quality24_rank.csv',rank);save_json(out/'raw_boundary_summary.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
