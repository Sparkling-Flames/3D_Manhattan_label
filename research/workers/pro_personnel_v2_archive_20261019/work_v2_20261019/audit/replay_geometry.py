"""Independently replay frozen measurement code on every embedded v2 input.

This does not rebuild acquisition, preprocessing, reference selection or eligibility.
It intentionally writes only derived audit results outside the pinned source snapshot.
"""
from pathlib import Path
import csv, gzip, hashlib, json, math, sys, time
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
REPO=ROOT/'repo_main_20261019'
OUT=ROOT/'work_v2_20261019/audit'
sys.path[:0]=[str(REPO),str(ROOT/'runtime_deps')]
from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine, score_task
from tools.thesis_main.analysis.quality_b8l2_d10_20261017 import dual_scores
from tools.thesis_main.analysis.b8l2_calculation_status_20261016 import inspect_geometry
from shapely.geometry import Polygon
from initialization_ring import recover_declared_initial_ring

METRICS=['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','height_mean_ratio']
TOL=1e-8

def run():
    OUT.mkdir(parents=True,exist_ok=True)
    source=REPO/'research/statistics/v2_evidence_audit_20261019/records.json.gz'
    rows=json.load(gzip.open(source,'rt',encoding='utf-8'))['records']
    engine_dir=REPO/'research/statistics/b8l2_shared_v6_20261016/inputs'
    started=time.perf_counter(); allout=[]; initials=[]
    by_object={r['object_id']:r for r in rows}
    with scoring_engine(engine_dir/'measurement_engine.zip',engine_dir/'working_models.py') as (engine,models):
        for i,row in enumerate(rows):
            base={k:row[k] for k in ['object_id','worker_id','image_id','image_code','building_id','origin','condition','quality_usable','calculation_class']}
            reference=row.get('reference_evidence')
            task={k:row[k] for k in ['object_id','worker_id','image_id','condition','reference_version']}
            task.update(current_target_id=row['reference_id'],annotation_points=row['points_1024x512'],
                reference_points=reference.get('points_1024x512') if reference else None,
                reference_full_available=row['reference_full_available'])
            if row['calculation_class']=='full':
                got=score_task(task,engine,models)
                if got['score_status']=='complete': got.update(dual_scores(got,models))
                base['replay_class']='full' if got['score_status']=='complete' else 'unavailable'
                expected=row['measurements']['same_reference_measurements']
                for m in METRICS:
                    base['expected_'+m]=expected.get(m)
                    base['replay_'+m]=got.get(m)
                    base['delta_'+m]=got[m]-expected[m] if got.get(m) is not None and expected.get(m) is not None else None
                base['reason']=json.dumps(got['reasons'],ensure_ascii=False)
                base['pass']=base['replay_class']=='full' and all(base['delta_'+m] is not None and abs(base['delta_'+m])<=TOL for m in METRICS)
            else:
                inspection=inspect_geometry(row,engine)
                floor=None;reason='annotation_floor_unavailable'
                if inspection['floor_input_available']:
                    reason='reference_unbound' if not reference else 'reference_floor_unavailable'
                    if reference:
                        valid=engine.valid.validate_footprint(reference['floor_xz_h'],role='reference')
                        if valid['available']:
                            a,b=Polygon(inspection['floor_xz_h']),Polygon(reference['floor_xz_h'])
                            floor=a.intersection(b).area/a.union(b).area;reason=None
                base['replay_class']='floor_only' if floor is not None else 'uncomputable'
                base['replay_diagnostic_floor_iou']=floor
                base['expected_diagnostic_floor_iou']=row['diagnostic_floor_iou']
                base['delta_diagnostic_floor_iou']=floor-row['diagnostic_floor_iou'] if floor is not None else None
                base['reason']=reason
                base['pass']=base['replay_class']==row['calculation_class'] and (floor is None or abs(base['delta_diagnostic_floor_iou'])<=TOL)
            allout.append(base)
            semi=row['semi_evidence']
            if semi.get('paired_scores_current_adopted'):
                scoring_points,ring_evidence=recover_declared_initial_ring(row,by_object)
                itask=dict(task,annotation_points=scoring_points)
                got=score_task(itask,engine,models)
                if got['score_status']=='complete':got.update(dual_scores(got,models))
                ini={k:row[k] for k in ['object_id','worker_id','image_id','building_id','quality_usable']}
                ini.update(worker_attributable=semi['worker_attributable_gain_available'],score_status=got['score_status'])
                ini.update(initial_ring_method=ring_evidence['method'],initial_ring_changed=ring_evidence['ring_changed_from_payload'],
                    ring_source_object_ids=json.dumps(ring_evidence['source_object_ids']),pair_permutation=json.dumps(ring_evidence['pair_permutation']))
                for m in ['B8L2','D10','IoU3D100']:
                    ini['expected_initial_'+m]=semi['current_initial_scores'][m]
                    ini['replay_initial_'+m]=got.get(m)
                    ini['delta_initial_'+m]=got[m]-semi['current_initial_scores'][m] if got.get(m) is not None else None
                    ini['expected_gain_'+m]=semi['current_project_gain'][m]
                    ini['identity_residual_'+m]=row['measurements']['same_reference_measurements'][m]-semi['current_initial_scores'][m]-semi['current_project_gain'][m]
                ini['pass']=got['score_status']=='complete' and all(abs(ini['delta_initial_'+m])<=TOL and abs(ini['identity_residual_'+m])<=TOL for m in ['B8L2','D10','IoU3D100'])
                initials.append(ini)
            if (i+1)%1000==0:print(json.dumps({'rows':i+1,'elapsed_seconds':round(time.perf_counter()-started,2)}),flush=True)
    def save_csv(name,data):
        fields=list(dict.fromkeys(k for x in data for k in x))
        with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
    save_csv('geometry_replay_records.csv',allout)
    save_csv('semi_initial_score_replay.csv',initials)
    full=[x for x in allout if x['calculation_class']=='full']
    result=dict(schema='independent_frozen_geometry_replay_v2_1',commit='82c6164b0d4630de5316199c92aa405930973168',
        input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),inventory=len(rows),full=len(full),
        floor_only=sum(x['calculation_class']=='floor_only' for x in allout),uncomputable=sum(x['calculation_class']=='uncomputable' for x in allout),
        initial_score_replays=len(initials),tolerance_absolute=TOL,
        initial_scoring_ring_inherited=sum(x['initial_ring_changed'] for x in initials),
        max_absolute_difference={m:max(abs(x['delta_'+m]) for x in full if x['delta_'+m] is not None) for m in METRICS},
        failures=[x['object_id'] for x in allout if not x['pass']],initial_failures=[x['object_id'] for x in initials if not x['pass']],
        elapsed_seconds=time.perf_counter()-started,n1_applied=False,
        scope='Every embedded frozen final geometry with its bound reference; current paired initial scores use native payload or explicitly declared pre-existing human-confirmed exact-pair ring, never score-selected. Acquisition and prior human auditing NOT independently rebuilt.')
    (OUT/'GEOMETRY_REPLAY_CHECKS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True)
    if result['failures'] or result['initial_failures']:raise SystemExit(1)

if __name__=='__main__':run()
