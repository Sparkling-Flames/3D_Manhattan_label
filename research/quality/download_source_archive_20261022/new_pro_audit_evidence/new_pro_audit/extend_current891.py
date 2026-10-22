"""Audit-only fresh 891 extension of the supplied GQS v2; no official writes."""
from pathlib import Path
import sys,json,hashlib,time,os
import numpy as np
import pandas as pd

ROOT=Path('/workspace/scratch/81fa50cc64f5');REPO=ROOT/'repo'
STUDY=ROOT/'new_pro_return/panorama_quality_three_routes_20261016'
OUT=Path(os.environ.get('GQS_891_OUT',str(ROOT/'new_pro_audit/current891_extension')));OUT.mkdir(exist_ok=False,parents=True)
sys.path.insert(0,str(REPO));sys.path.insert(0,str(STUDY/'src'))
E=REPO/'analysis_results/quality/quality_joint_closeout_review_20261015/local_replay'
sys.path.insert(0,str(E/'engine'));sys.path.insert(0,str(E/'src'))
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
from prepare_inputs import geometry
from geomscore import Config,score_pair
from run_real import flat

def sha(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def fsha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
stats=REPO/'research/statistics/descriptive_statistics_rescored_20261016'
current=pd.read_csv(stats/'quality_records.csv').fillna('')
prior=pd.read_csv(ROOT/'audit_quality_baseline/current891_complete/current891_fixed_reference_geometry_replay.csv').fillna('').set_index('object_id')
refs=pd.read_csv(stats/'space_reference_catalog.csv').fillna('');refs={r['target_id']:r for r in refs.to_dict('records')}
bundle=load_current_bundle();objects={x['object_id']:x for x in bundle['data']['objects']}
cfg=Config(**json.loads((STUDY/'config.json').read_text()))
metadata=[];pairs=[];rows=[];details={};start=time.time()
for i,row in enumerate(current.to_dict('records')):
    oid=row['object_id'];rid=row['reference_id'];obj=objects[oid];ref=refs[rid]
    assert obj['image_id']==ref['image_id']==row['image_id'] and obj['worker_id']==row['worker_id'] and obj['condition']==row['condition']
    assert row['current_target_id']==rid
    assert row['current_quality_eligible'] and row['pool_analysis_eligible'] and row['pool_source_workers']>=3
    assert not row['gt_error_excluded'] and obj['worker_id'] not in ['W019','W026']
    assert ref['full_reference_available']
    ap=obj['points_1024x512'];rp=json.loads(ref['points_1024x512']);g=geometry(ap);r=geometry(rp);checked=prior.loc[oid]
    assert sha(ap)==checked.annotation_points_sha256 and sha(rp)==checked.reference_points_sha256
    assert sha(g)==checked.answer_3d_sha256 and sha(r)==checked.reference_3d_sha256
    ident={k:row[k] for k in ['object_id','record_id','image_id','image_code','worker_id','condition','reference_id','current_target_id','pool_source_workers','difficulty_class','WQ','A10','B8L2','IoU3D100']}
    ident.update(answer_sha256=sha(g),reference_sha256=sha(r),annotation_points_sha256=sha(ap),reference_points_sha256=sha(rp),eligibility_version=row['pool_rule_version'],algorithm_version=cfg.version,config_sha256=fsha(STUDY/'config.json'),implementation_sha256=fsha(STUDY/'src/geomscore.py'))
    pairs.append({**ident,'answer':g,'reference':r})
    try:
        s=score_pair(g,r,cfg);d=flat(s);details[oid]=s
        status='ok' if s['answer_camera_inside'] and s['reference_camera_inside'] else 'not_evaluable_camera_outside'
        if status!='ok':
            for k in ['QA','QB','QC']:d['diagnostic_'+k]=d[k];d[k]=None
        rows.append({**ident,**d,'status':status})
    except (ValueError,ArithmeticError,TypeError) as exc:rows.append({**ident,'status':'not_evaluable','reason':str(exc)})
    if (i+1)%100==0:print('PROGRESS',i+1,'seconds',time.time()-start,flush=True)

(OUT/'fixed891_pairs.json').write_text(json.dumps(pairs,ensure_ascii=False,allow_nan=False),encoding='utf8')
(OUT/'measurements891.json').write_text(json.dumps(details,ensure_ascii=False,allow_nan=False),encoding='utf8')
data=pd.DataFrame(rows);data.to_csv(OUT/'current891_gqs_audit_scores.csv',index=False)
published=pd.read_csv(STUDY/'results/current244_scores.csv').set_index('object_id')
same=data.set_index('object_id').loc[published.index]
parity={k:float(np.max(np.abs(same[k]-published[k]))) for k in ['QA','QB','QC']}
diff=same[['QA','QB','QC']]-published[['QA','QB','QC']];diff.to_csv(OUT/'published244_fresh_geometry_deltas.csv')
summary=dict(status='COMPLETE',input_rows=891,status_counts=data.status.value_counts().to_dict(),condition_status=data.groupby(['condition','status']).size().to_dict(),images=data.image_id.nunique(),published244_fresh_geometry_parity=parity,
             score_descriptions=data[data.status.eq('ok')].groupby('condition')[['WQ','A10','B8L2','QA','QB','QC']].agg(['mean','min','max']).to_dict(),
             source_hashes={str(p):fsha(p) for p in [stats/'quality_records.csv',stats/'space_reference_catalog.csv',STUDY/'src/geomscore.py',STUDY/'config.json']},
             provenance='Actual current loader; every current input/reference point hash and reconstructed 3D hash equals the independently verified 891 baseline. Fixed reference_id only, no optimization, no official scores/eligibility writes.',
             applicability='Camera-outside pairs suppressed from QA/QB/QC exactly as the supplied formal entrypoint; their low-level numerical scores retained only in diagnostic columns.',
             limitation='New 891 audit extension is NOT an author-claimed result and NOT a new human validation or RGB reference judgment; includes Semi outside the author 244 Manual sample.')
def normalize(v):
    if isinstance(v,dict):return {str(k):normalize(x) for k,x in v.items()}
    if isinstance(v,np.generic):return v.item()
    return v
(OUT/'SUMMARY.json').write_text(json.dumps(normalize(summary),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
print(json.dumps(normalize(summary),ensure_ascii=False,indent=2),flush=True)
