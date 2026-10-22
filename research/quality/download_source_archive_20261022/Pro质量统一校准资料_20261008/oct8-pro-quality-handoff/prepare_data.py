#!/usr/bin/env python3
"""Prepare unchanged evidence for common-rubric absolute quality calibration.
No fitting, relabeling, difficulty offsets, geometry repairs or network calls.
"""
import csv,hashlib,itertools,json,math,statistics
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def write_json(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def write_csv(path,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for row in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in row.items()})
def number(s):
    if s in [None,'','None','nan','NaN']:return None
    return float(s)

DEFS={
 'iou':('范围 IoU','ratio','higher','reference','BEV intersection area / union area; retained declared polygon, relative to recorded GT; not holistic quality'),
 'C':('归一质心距离','dimensionless','lower','reference','Euclidean BEV centroid distance / sqrt(reference footprint area); insensitive to many local boundary errors'),
 'U':('上界经度边界平均绝对误差','degree','lower','reference','Uniform-longitude upper boundary absolute angular error; only valid when required rings are single-valued for one turn'),
 'B':('下界经度边界平均绝对误差','degree','lower','reference','Uniform-longitude lower boundary absolute angular error; same computability requirement as U'),
 'T':('墙顶对参考三维曲线距离','camera_height_h','lower','reference_3D','Symmetric mean nearest finite-segment distance of declared top rings, 512 arclength midpoint samples per direction; fixed floor and paired-depth proxy, not measured physical 3D or semantic wall correspondence'),
 'F':('地面对参考三维曲线距离','camera_height_h','lower','reference_3D','Same symmetric nearest-segment metric for floor rings; camera-to-floor normalization h, not metres'),
 'dir':('自身墙向残差','degree','lower_conditional','intrinsic_3D','Edge-length-weighted RMS residual to fitted orthogonal wall-direction frame; only measures conditional regularity, not scene faithfulness'),
 'flat':('自身平顶残差','degree','lower_conditional','intrinsic_3D','RMS angular residual to fitted horizontal wall-top model, retaining floor; conditional model consistency, not measured truth'),
 'omission':('参考范围未覆盖比例','ratio','lower_conditional','reference','area(G minus A) / area(G); geometric footprint mismatch, NOT independently verified visible-wall omission label'),
 'extension':('超出参考范围比例','ratio','lower_conditional','reference','area(A minus G) / area(G); may exceed 1; not automatically a semantic error'),
 'LC':('既有 LC 诊断组合','unbounded_loss','lower','fixed_legacy','(1-iou)+0.5*C; not calibrated to absolute human quality'),
 'LCT':('既有 LCT 诊断组合','unbounded_loss','lower','fixed_legacy','LC+0.3*sL*T/sT; frozen scales in formulas.json'),
 'LCG':('既有 LCG 诊断组合','unbounded_loss','lower','fixed_legacy','LC+0.3*sL*(dir/sDir+flat/sFlat)/2; frozen scales, not fitted to these ratings'),
 'conditional_volume_iou':('条件平顶体积 IoU','ratio','higher_conditional','reference_3D','Intersection footprint area times min(mean height A,G), divided by summed footprint×mean-height proxy volumes minus intersection; horizontal-cap proxy, not true reconstructed volume overlap'),
 'height_mean_relative_error':('平均高度相对参考误差','ratio','lower_conditional','reference_3D','abs(mean perimeter-weighted height A-G)/mean height G; fixed-floor paired-depth model'),
 'height_mean_signed_h':('平均高度相对参考有符号差','camera_height_h','diagnostic_signed','reference_3D','mean height A minus mean height G; sign is not a quality order'),
 'height_internal_relative_rms':('自身高度相对 RMS','ratio','lower_conditional','intrinsic_3D','Perimeter-integrated height RMS / mean wall height; regularity diagnostic, not scene correctness'),
 'direction_to_reference_rms_deg':('墙向相对参考坐标系残差','degree','lower_conditional','reference_3D','Edge-length-weighted RMS wall-direction residual using reference fitted frame; conditional orthogonality model'),
 'max_depth_sensitivity_h_per_Cpx':('深度对下界像素最大敏感度','h_per_1024x512_pixel','diagnostic_sensitivity','intrinsic_3D','max((1+radius^2)*pi/512); near-horizon geometric sensitivity, not independently validated uncertainty or quality penalty'),
 'height_mean_h':('自身平均墙高','camera_height_h','diagnostic_value','intrinsic_3D','Perimeter-weighted mean under fixed floor=-1 and paired depths; not direct quality order'),
 'height_internal_rms_h':('自身高度 RMS','camera_height_h','lower_conditional','intrinsic_3D','Perimeter-integrated RMS around own mean height; conditional flatness only'),
}
RAW_MAP={'iou':'iou','C':'centroid_distance_normalized','U':'top_mae_deg','B':'bottom_mae_deg',
 'T':'top3d_symmetric_mean_h','F':'floor3d_symmetric_mean_h','dir':'direction_rms_deg','flat':'flat_top_angular_rms_deg',
 'omission':'omission_ref','extension':'extension_ref'}

def main():
    for sub in ['data','analysis','review','provenance']: (ROOT/sub).mkdir(exist_ok=True)
    ratings=json.loads((ROOT/'inputs/review36_user_20261008.json').read_text())
    geom=json.loads((ROOT/'inputs/frozen_geometry.json').read_text())
    selection=json.loads((ROOT/'inputs/selection_manifest.json').read_text())
    assert ratings['dataSnapshot']==geom['datasetFingerprintSha256']==selection['datasetFingerprintSha256']
    raw=list(csv.DictReader((ROOT/'inputs/selected48_raw_metrics.csv').open(encoding='utf-8-sig')))
    lookup={(r['id'],r['reference_version'],r['reference_id']):r for r in raw};assert len(lookup)==48
    groups={im['code']:im for im in geom['images']}
    source={a['id']:(im,a) for im in geom['images'] for a in im['annotations']}
    sel={im['image']:im for im in selection['images']}
    rows=[];allrefs=[];crosschecks=0
    for h in ratings['ratings']:
        im,a=source[h['recordId']];assert im['code']==h['imageCode'] and a['reviewId']==h['reviewId']
        versions={}
        for version,ref in a['metricsByReference'].items():
            rawrow=lookup[(h['recordId'],version,ref['referenceId'])]
            assert rawrow['image']==im['code']
            m=dict(ref['metrics'])
            for k,rawkey in RAW_MAP.items():
                x=number(rawrow[rawkey]);y=m[k]
                assert (x is None and y is None) or (x is not None and y is not None and math.isclose(x,y,rel_tol=1e-12,abs_tol=1e-12)),(h['reviewId'],version,k,x,y)
                crosschecks+=1
            for k in DEFS:
                if k not in m:m[k]=number(rawrow.get(k))
            versions[version]=m
            allrefs.append(dict(review_id=h['reviewId'],record_id=h['recordId'],image_code=im['code'],building=im['building'],
                reference_version=version,reference_id=ref['referenceId'],matches_rating_reference=version==h['referenceVersion'],
                **m,longitude_status=ref['longitudeStatus'],longitude_reason=ref['longitudeReason']))
        ref=a['metricsByReference'][h['referenceVersion']];assert ref['referenceId']==h['referenceId']
        current=versions[h['referenceVersion']]
        unavailable={k:(ref['longitudeReason'] if k in ['U','B'] else 'source_unavailable') for k,v in current.items() if v is None}
        rows.append(dict(review_id=h['reviewId'],record_id=h['recordId'],image_code=im['code'],building=im['building'],room=im['room'],
            human_score_original=h['overallScore'],human_score_role='image_adaptive_pilot_NOT_unified_absolute_target',
            unified_quality_score=None,mainset_included=True,
            reference_version=h['referenceVersion'],reference_id=h['referenceId'],
            reference_connections_status='user_confirmed_2026-10-08T08:45:26Z' if im['code']=='UwV83HsGsw3-09' else 'unchanged_recorded_reference',
            gt_visible=h['gtVisible'],metrics_panel_seen=h['metricsSeen'],references_seen=h['referencesSeen'],
            compared_record_ids=h['comparedRecordIds'],source_rubric=h['rubricVersion'],source_updated_at=h['updatedAt'],
            scope_note_original=h['scopeNote'],geometry_note_original=h['geometryNote'],tags_original=h['tags'],
            note_category_status='not_clean_scope_choice_vs_omission_labels_user_clarified',
            selection_component='targeted' if h['recordId'] in sel[im['code']]['targetedIds'] else 'deterministic_random_from_remaining',
            pair_count=a['pairCount'],geometry_status=a['geometryStatus'],
            longitude_status=ref['longitudeStatus'],longitude_reason=ref['longitudeReason'],
            source_geometry_status=a['sourceGeometry']['status'],source_geometry_issues=a['sourceGeometry']['issues'],
            **current,metric_unavailability=unavailable,
            photo_file='inputs/original_photos/'+im['code']+'.png',
            visual_sheet='visuals/review_'+im['code']+'.jpg'))
    assert len(rows)==36 and all(r['unified_quality_score'] is None for r in rows)
    write_csv(ROOT/'data/unified36_existing_metrics.csv',rows)
    write_json(ROOT/'data/unified36_existing_metrics.json',rows)
    write_csv(ROOT/'data/all48_reference_specific_metrics.csv',allrefs)
    dictionary=[dict(field=k,name_zh=v[0],unit=v[1],direction=v[2],family=v[3],definition_and_limit=v[4],
       source='frozen_geometry metricsByReference' if k in geom['images'][0]['annotations'][0]['metrics'] else 'selected48_raw_metrics.csv existing raw output',
       NA_policy='Missing remains blank/null, never zero; U/B require single-valued rings') for k,v in DEFS.items()]
    write_csv(ROOT/'data/metric_dictionary.csv',dictionary)
    write_json(ROOT/'data/formulas.json',dict(formulas=geom['formulas'],scales=geom['scales'],
        weight_source='preexisting frozen examples; no fitting on these 36 ratings',
        metric_direction='LC/LCT/LCG are unbounded losses: smaller is closer/regular under their assumptions; not an absolute quality scale'))
    summaries=[];byimage=defaultdict(list)
    for r in rows:byimage[r['image_code']].append(r)
    for image,rs in byimage.items():
        for key in DEFS:
            vals=[r[key] for r in rs if r[key] is not None]
            summaries.append(dict(image_code=image,reference_version=rs[0]['reference_version'],metric=key,n_records=len(rs),
                n_values=len(vals),n_missing=len(rs)-len(vals),minimum=min(vals) if vals else None,
                median=statistics.median(vals) if vals else None,mean=statistics.mean(vals) if vals else None,
                maximum=max(vals) if vals else None,unit=DEFS[key][1],
                interpretation='selected_six_annotations_only_NOT_image_difficulty_estimate',
                human_score_original_mean=statistics.mean(r['human_score_original'] for r in rs),
                human_mean_warning='image_adaptive_grades_not_comparable_absolute_targets'))
    write_csv(ROOT/'analysis/raw_metrics_by_image.csv',summaries)
    q={r['review_id']:r for r in rows}
    checks=[
      ('X01','Q11','Q20','cross_image_same_grade','Both original 4; large IoU/reference-3D gap. Is the same global quality grade still appropriate?'),
      ('X02','Q01','Q28','cross_image_same_grade','Both original 4; large extent/reference-distance gap, but flat residual favors Q28. Do not let a flat shape automatically excuse missing scene detail.'),
      ('X03','Q03','Q34','cross_image_grade_inversion_candidate','Original 3 vs 4; IoU,C,T,dir,flat all favor Q03. Check a single global rubric against the actual images; metrics do not establish the answer.'),
      ('X04','Q10','Q19','cross_image_near_reference_anchor','Both original 5; high IoU and small reference distances on different scenes. Helps check whether a difficult image can still receive top quality without an image-level penalty.'),
      ('X05','Q02','Q30','cross_image_top_grade_anchor','Both original 5; compare the size/importance of residual defects under one rubric. Same grade does not imply equality.'),
      ('W01','Q14','Q15','within_image_tradeoff','Original 4 vs 2; IoU/centroid/T favor Q15 while intrinsic regularity favors Q14. Scope/omission semantics remain unclassified.'),
      ('W02','Q25','Q30','within_image_fixed_composite_conflict','Original 4 vs 5; LCG favors Q25 whereas LC/LCT favor Q30. Inspect feature tradeoff; no weights are changed now.'),
      ('W03','Q33','Q35','within_image_fixed_composite_conflict','Original 4 vs 3; LC/LCT favor Q35, LCG favors Q33. Original notes use similar scope wording; do not infer a reliable categorical label.'),
    ]
    contrasts=[]
    for cid,qa,qb,typ,reason in checks:
        a,b=q[qa],q[qb]
        d=dict(contrast_id=cid,a=qa,b=qb,type=typ,purpose=reason,
            image_a=a['image_code'],image_b=b['image_code'],human_original_a=a['human_score_original'],human_original_b=b['human_score_original'],
            reference_a=a['reference_version'],reference_b=b['reference_version'],
            corrected_order=None,unified_score_a=None,unified_score_b=None,reviewer_explanation=None)
        for k in DEFS:d[k+'_a']=a[k];d[k+'_b']=b[k]
        contrasts.append(d)
    contrasts=[c for c in contrasts if c['contrast_id'] not in ['X03','X05']]
    write_csv(ROOT/'analysis/selected_review_contrasts.csv',contrasts)
    write_json(ROOT/'analysis/selected_review_contrasts.json',contrasts)
    # Interleaved image order; empty new labels, no old grades/metrics in the blind-first worksheet.
    sequence=[]
    per=[sorted(rs,key=lambda r:hashlib.sha256(('common-rubric-review-v1|'+r['record_id']).encode()).hexdigest()) for rs in byimage.values()]
    for i in range(6):
        for j in range(6):sequence.append(per[(i+j)%6][i])
    review=[]
    for order,r in enumerate(sequence,1):
        review.append(dict(review_order=order,review_id=r['review_id'],record_id=r['record_id'],image_code=r['image_code'],
            reference_version=r['reference_version'],reference_id=r['reference_id'],visual_sheet=r['visual_sheet'],
            new_quality_score_1_to_5=None,unable_to_judge_reason=None,confidence_high_medium_low=None,
            important_visible_omission_yes_no_uncertain=None,
            scope_choice_or_omission_undetermined=None,reference_compatibility_confirmed_uncertain=None,
            principal_defect_note=None,reviewer=None,reviewed_at=None,confirmed_common_rubric_version=None))
    write_csv(ROOT/'review/common_rubric_rereview_blank36.csv',review)
    write_json(ROOT/'review/common_rubric_rereview_blank36.json',review)
    write_csv(ROOT/'review/contrast_decisions_blank6.csv',[{k:c[k] for k in ['contrast_id','a','b','type','purpose','corrected_order','unified_score_a','unified_score_b','reviewer_explanation']} for c in contrasts])
    coverage={k:sum(r[k] is not None for r in rows) for k in DEFS}
    write_json(ROOT/'provenance/preparation_checks.json',dict(status='passed',rows_main=36,rows_per_reference=48,
        source_frozen_common_metric_cells_checked=crosschecks,coverage=coverage,all_mainset_included=True,
        new_labels_all_blank=True,original_human_scores_preserved=True,current_Uw_status='user_confirmed_connections; included; no active GT exclusion',
        scores_present=sorted({r['human_score_original'] for r in rows}),all_metrics_seen_false=all(not r['metrics_panel_seen'] for r in rows),
        all_gt_visible_true=all(r['gt_visible'] for r in rows),human_data_snapshot=ratings['dataSnapshot'],
        no_fitting=True,no_human_normalization=True,no_difficulty_penalty=True))
    print(json.dumps({'status':'ok','main_records':36,'reference_rows':48,'coverage':coverage,'crosschecks':crosschecks},ensure_ascii=False))

if __name__=='__main__':main()
