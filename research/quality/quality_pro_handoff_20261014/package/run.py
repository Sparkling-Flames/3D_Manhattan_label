"""解包后运行：python -B run.py。只复算工作版与锚点，不搜索。"""
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parent


def read(name):return json.loads((ROOT/name).read_text(encoding='utf-8-sig'))


def main():
    sys.path.insert(0,str(ROOT/'engine'))
    import audit_geometry,geometric_components,strict_geometry,height_revision,centered_height,traditional_metrics,score
    from prepare_inputs import geometry
    from evaluate_geometry import evaluate_geometry
    frozen=read('stage/WORKING_FINAL.json');config=frozen['config'];cohorts=read('data/cohorts.json');controls=read('stage/COARSE.json')
    counts={k:len(cohorts[k]) for k in ('ordinary','severe','doorway')};assert counts==dict(ordinary=574,severe=9,doorway=217)
    engine=dict(au=audit_geometry,sp=geometric_components,valid=strict_geometry,hm=height_revision,
        center=centered_height,trad=traditional_metrics,configs={'working':config})
    engine['score']=score
    errors=[]
    for row in cohorts['ordinary']+cohorts['severe']:
        computed=score.score_metrics(row['metrics'],config)['score']
        errors.append(abs(computed-controls['records'][row['record_id']]['hill_global08']['score']))
        assert abs(computed-score.score_metrics(row['metrics'],score.BASELINE)['score'])<1e-10
    assert max(errors)<1e-10
    objects={r['object_id']:r for r in read('data/objects.json')['objects']}
    row=next(r for r in cohorts['ordinary'] if r['record_id']=='R03274')
    actual=evaluate_geometry(geometry(objects[row['object_id']]['points_1024x512']),geometry(objects[row['reference_object_id']]['points_1024x512']),engine)
    assert actual['status']=='complete'
    assert max(abs(actual['metrics'][k]-row['metrics'][k]) for k in ('iou_2d','S_bottom_deg','dir','Hmean','Hcenter'))<1e-8
    checks=[]
    for budget in (8,16):
        c=next(c for c in read('preparation/BOTTOM_CONTROLS.json')['rows'] if c['case_id']==f'1x4:distributed_bottom:-1:{budget}')
        result=evaluate_geometry(geometry(c['points']),geometry(c['reference_points']),engine)
        assert result['status']=='complete'
        assert max(abs(result['metrics'][k]-c['metrics'][k]) for k in ('iou_2d','S_bottom_deg','dir','Hmean','Hcenter'))<1e-8
        checks.append(dict(case_id=c['case_id'],metrics=result['metrics'],components=result['candidate_components']['working']))
    rhombus=[]
    for c in controls['controls']:
        if c['source']!='new_complete_rhombus_RMS':continue
        theta=np.radians(c['angle']);u=np.array([1.,0]);v=np.array([np.cos(theta),np.sin(theta)])
        p=np.array([(-u-v)/2,(u-v)/2,(u+v)/2,(-u+v)/2]);ref=np.array([[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]])
        def geo(x):return dict(bottom3d=np.c_[x[:,0],-np.ones(4),x[:,1]].tolist(),top3d=np.c_[x[:,0],np.full(4,1.6),x[:,1]].tolist())
        result=evaluate_geometry(geo(p),geo(ref),engine)
        assert abs(result['metrics']['dir']-c['metrics']['dir'])<1e-8
        rhombus.append(dict(angle=c['angle'],D=result['metrics']['dir'],Q=result['candidate_components']['working']['score']))
    assert checks[0]['components']['score']>checks[1]['components']['score']
    report=dict(status='startup_verified_not_calibration_certified',counts=counts,summary=read('data/supplement.json')['summary'],
        stored_score_max_abs_difference=max(errors),real_record=dict(record_id=row['record_id'],**actual),
        bottom_controls_rebuilt=checks,rhombus_rebuilt=rhombus,review_status=read('data/human_review_manifest.json')['status'],
        open_review='REVIEW.html',read_report='START_HERE.md')
    (ROOT/'startup_result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
