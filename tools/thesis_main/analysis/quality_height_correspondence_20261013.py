"""核查既有高度/底面对应；同视线深度分解仅为诊断，不修改几何或质量分。"""
from collections import Counter
import json
import math

import numpy as np

from tools.thesis_main.analysis.quality_manual_expansion_20261013 import ROOT, read, engine
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle

OUT=ROOT/'research/quality_height_correspondence_20261013'


def cross(a,b):
    return a[...,0]*b[...,1]-a[...,1]*b[...,0]


def ray_depth_diagnostic(annotation,reference,reference_mean):
    """只用唯一的正向射线交点；多交点不决定语义墙角对应。"""
    b=np.asarray(annotation['bottom3d']);t=np.asarray(annotation['top3d'])
    rb=np.asarray(reference['bottom3d']);rt=np.asarray(reference['top3d'])
    q=rb[:,[0,2]];edge=np.roll(q,-1,axis=0)-q
    gh=rt[:,1]-rb[:,1];rows=[]
    for i,p in enumerate(b[:,[0,2]]):
        radius=float(np.linalg.norm(p));row=dict(corner_index=i,annotation_radius=radius)
        if radius==0:
            rows.append(dict(row,status='zero_annotation_radius'));continue
        direction=p/radius;den=cross(direction,edge)
        # 这些是数值平行/端点容差，不是角度、范围或质量阈值。
        parallel=np.abs(den)<=1e-12*np.maximum(1,np.linalg.norm(edge,axis=1))
        collinear=parallel & (np.abs(cross(q,direction))<=1e-10)
        if np.any(collinear & (np.maximum(q@direction,(q+edge)@direction)>0)):
            rows.append(dict(row,status='collinear_reference_boundary'));continue
        good=~parallel
        distances=cross(q[good],edge[good])/den[good]
        positions=cross(q[good],direction)/den[good]
        hits=[]
        for k,rr,uu in zip(np.where(good)[0],distances,positions):
            if rr>0 and -1e-10<=uu<=1+1e-10:
                h=float(gh[k]+np.clip(uu,0,1)*(gh[(k+1)%len(gh)]-gh[k]))
                if not any(math.isclose(float(rr),hit[0],rel_tol=1e-9,abs_tol=1e-10) for hit in hits):
                    hits.append((float(rr),h,int(k)))
        if len(hits)!=1:
            rows.append(dict(row,status='multiple_reference_depths' if hits else 'no_reference_depth',positive_depths=len(hits)));continue
        rr,ref_h,segment=hits[0]
        ann_h=float(t[i,1]-b[i,1])
        # 相机高度归一化底面y=-1，h=1+r*tan(顶点仰角)。仅分解，不生成修复layout。
        top_ray_h=1+(ann_h-1)*rr/radius
        rows.append(dict(row,status='unique_reference_depth',reference_segment_index=segment,reference_radius=rr,
            annotation_height=ann_h,reference_height_at_ray=ref_h,top_ray_height_at_reference_depth=top_ray_h,
            observed_height_residual_relative=(ann_h-ref_h)/reference_mean,
            top_ray_residual_at_reference_depth_relative=(top_ray_h-ref_h)/reference_mean,
            depth_contribution_relative=(ann_h-top_ray_h)/reference_mean,
            radial_relative_difference=(radius-rr)/rr))
    unique=[r for r in rows if r['status']=='unique_reference_depth']
    result=dict(corners=rows,corner_count=len(rows),unique_reference_depth_corners=len(unique),
        correspondence_is_geometric_not_semantic=True,geometry_repaired=False,score_changed=False)
    for key in ('observed_height_residual_relative','top_ray_residual_at_reference_depth_relative','depth_contribution_relative'):
        result[key.replace('_relative','_rms_relative')]=math.sqrt(sum(r[key]**2 for r in unique)/len(unique)) if unique else None
    return result


def main():
    bundle=load_current_bundle();objects={o['object_id']:o for o in bundle['data']['objects']}
    data=read(ROOT/'research/quality_candidate_disagreement_20261013/RESULTS.json')
    e=engine();geometries={};moments={}
    def geometry(oid):
        if oid not in geometries:
            geometries[oid]=e['geometry'](objects[oid]['points_1024x512'])
            moments[oid]=e['hm'].height_moments(geometries[oid])
        return geometries[oid]
    lookup={r['record_id']:r for r in read(ROOT/'research/quality_data_admission_audit_20261013/FULL_ADMISSION.json')['records']}
    targets=[dict(r,analysis_layer='current_conditional_full') for r in data['records'] if r['score_kind']=='full']
    targets += [dict(r,object_id=lookup[r['record_id']]['object_id'],analysis_layer='historical_scope_confounded_fixed_reference')
                for r in data['historical_fixed_reference_replay']]
    rows=[]
    for r in targets:
        a=geometry(r['object_id']);g=geometry(r['reference_object_id'])
        am=moments[r['object_id']];gm=moments[r['reference_object_id']]
        centered=e['center'].centered_height_components(a,g,samples=4096,height_module=e['hm'])
        hm=abs(am['height_mean_h']/gm['height_mean_h']-1)
        errors=dict(Hmean=abs(hm-r['metrics']['Hmean']),Hcenter=abs(centered['Hcenter']-r['metrics']['Hcenter']))
        assert max(errors.values())<1e-8,(r['record_id'],errors)
        centered_a=dict(bottom3d=a['bottom3d'],top3d=np.asarray(a['top3d']).copy())
        centered_a['top3d'][:,1]-=am['height_mean_h']-gm['height_mean_h']
        ag=e['hm'].directed_nearest_footprint_height_mse(centered_a,g,4096,'max')
        ga=e['hm'].directed_nearest_footprint_height_mse(g,centered_a,4096,'max')
        agmin=e['hm'].directed_nearest_footprint_height_mse(centered_a,g,4096,'min')
        gamin=e['hm'].directed_nearest_footprint_height_mse(g,centered_a,4096,'min')
        hmin=math.sqrt((agmin['mse_h2']+gamin['mse_h2'])/2)/gm['height_mean_h']
        obj=objects[r['object_id']];review=obj['review_evidence']
        row=dict(record_id=r['record_id'],object_id=r['object_id'],image_code=r['image_code'],
            reference_object_id=r['reference_object_id'],analysis_layer=r['analysis_layer'],
            annotation_moments=am,reference_moments=gm,original_metrics=r['metrics'],
            metric_replay_absolute_errors=errors,centered_diagnostics=centered,
            nearest_floor_AG=ag,nearest_floor_GA=ga,Hcenter_under_min_tie=hmin,
            Hcenter_max_minus_min_tie=centered['Hcenter']-hmin,
            ray_depth_diagnostic=ray_depth_diagnostic(a,g,gm['height_mean_h']),
            current_geometry_issues=obj['geometry']['issues'],reference_geometry_issues=objects[r['reference_object_id']]['geometry']['issues'],
            scope_and_detail_flags={k:obj['final_review'][k] for k in ('scope_difference_image','scope_difference_annotation','detail_difference_image','detail_difference_annotation')},
            review_evidence={k:review[k] for k in ('current_comment','current_decision_comment','image_comment','gt_version_note')},
            no_new_semantic_wall_correspondence=True)
        rows.append(row)
    case_ids={r['record_id'] for r in data['mechanism_cases'] if any('height' in s for s in r['selection_reasons'])}
    assert len(rows)==len(targets) and len({r['record_id'] for r in rows})==len(targets)
    summary=dict(records=len(rows),layers=dict(Counter(r['analysis_layer'] for r in rows)),
        max_height_metric_replay_error=max(max(r['metric_replay_absolute_errors'].values()) for r in rows),
        max_Hcenter_max_minus_min_tie=max(r['Hcenter_max_minus_min_tie'] for r in rows),
        records_with_distinct_nearest_tied_heights=sum(max(r['nearest_floor_AG']['distinct_tied_height_fraction'],r['nearest_floor_GA']['distinct_tied_height_fraction'])>0 for r in rows),
        ray_status_counts=dict(Counter(c['status'] for r in rows for c in r['ray_depth_diagnostic']['corners'])),
        records_with_all_corners_unique_reference_depth=sum(r['ray_depth_diagnostic']['unique_reference_depth_corners']==r['ray_depth_diagnostic']['corner_count'] for r in rows),
        ray_residual_is_corner_based_not_Hcenter=True, missing_confirmed_top_not_processed=True)
    OUT.mkdir(parents=True,exist_ok=True)
    payload=dict(schema='quality_height_correspondence_20261013_v1',summary=summary,records=rows,
        mechanism_cases=[r for r in rows if r['record_id'] in case_ids],
        policy='仅复算已有高度量、对应与射线深度诊断；不修点、不改总分、不确认语义墙对应。多交点不自动选。')
    (OUT/'RESULTS.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    (OUT/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    for r in payload['mechanism_cases']:
        ray=r['ray_depth_diagnostic']
        print(r['record_id'],r['image_code'], 'Hm/Hc',r['original_metrics']['Hmean'],r['original_metrics']['Hcenter'],
              'observed/depth_fixed_top',ray['observed_height_residual_rms_relative'],ray['top_ray_residual_at_reference_depth_rms_relative'],
              'unique/total',ray['unique_reference_depth_corners'],ray['corner_count'])


if __name__=='__main__':main()
