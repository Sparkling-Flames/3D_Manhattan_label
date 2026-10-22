"""Read-only downstream joins, two-image upper bounds and targeted diagnostics."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from dataclasses import replace
import numpy as np,pandas as pd
from scipy.stats import spearmanr
from shapely.geometry import Polygon
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from working_models import MODELS,WQ,A,B,score,floor_upper_bound,attribution
from native_geometry import project,erp_triples,direction,iou,bottom_distance,height_components,prism_iou

def dump(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def routing(code,a,old,new,margin=.1):
    # No score, height, worker ID, or model ID is accepted by the routing function.
    if code=='B6ByNegPMKs-37':
        branch=Polygon(old).difference(Polygon(new));coverage=Polygon(a).intersection(branch).area/branch.area
        tip='new_no_side_branch_pattern' if coverage<=.2 else ('original_side_branch_pattern' if coverage>=.8 else 'undetermined_branch_coverage')
        return tip,dict(branch_coverage=float(coverage))
    far=float(np.max(old[:,1]));near=float(np.max(new[:,1]));mid=(far+near)/2
    ends=np.sort(a[:,1])[-2:];buffer=margin*(far-near)
    tip='new_near_stop_pattern' if np.all(ends<mid-buffer) else ('original_far_stop_pattern' if np.all(ends>mid+buffer) else 'mixed_or_boundary_stop_pattern')
    return tip,dict(stop_values=ends.tolist(),split_midpoint=mid,safety_buffer=buffer)

def two_images(inp,out):
    source=json.loads((inp/'CURRENT_TWO_IMAGE_MINIMAL_38.json').read_text(encoding='utf-8'));objs=source['objects']
    refs={x['image_code']:x for x in json.loads((inp/'TWO_IMAGE_SCOPE_DELTA.json').read_text(encoding='utf-8'))['records']}
    frozen=pd.read_csv(inp/'JOINT_COMPARISON_1145.csv').set_index('record_id')
    ledger=[];pairs=[];viewer=[];parity=[];requests=[];route_sensitivity=[]
    for code,r in refs.items():
        for j,(x,z) in enumerate(r['new_floor_polygon_xz_h']):
            # Native continuous ERP convention, floor y=-1; no top inferred.
            rho=np.hypot(x,z);u=(np.arctan2(x,-z)/(2*np.pi)+.5)*1024
            y=(np.arctan2(1,rho)/np.pi+.5)*512
            requests.append(dict(image_code=code,image_id=r['image_id'],candidate_id=r['new_floor_candidate_id'],corner_index=j,
               bottom_x_erp=float(u%1024),bottom_y_erp=float(y),top_y_erp=None,top_evidence_status='unconfirmed',
               question='Confirm physical versus protocol-closure edge and its ceiling endpoint from the photo; do not copy old top or presume constant height.'))
    for ob in objs:
        if ob['object_kind']!='annotation':continue
        code=ob['image_code'];r=refs[code];qual=ob['prior_ledger_qualification']
        row={k:ob.get(k) for k in ['record_id','object_id','image_id','image_code','worker_id','condition','cleaning_disposition','preprocessing_status','ring_confirmed','order_status']}
        row.update({('inherited_'+k):v for k,v in qual.items()});row.update(new_reference_id=r['new_floor_candidate_id'],old_reference_id=r['original_reference_object_id'],
            new_top_confirmed=False,new_full_WQ=None,new_full_A10=None,new_full_B8L2=None,new_full_IoU3D=None,
            adopted_reference_id=None,formal_eligibility_newly_granted=False,photo_visual_adjudication_completed=False,
            current_arrays_source='Supplied minimal snapshot previously checked against loader; no fresh full loader in this execution')
        if ob['points_1024x512'] is None:
            row.update(execution_status='unavailable_pairing',scope_pattern='not_computable');ledger.append(row);continue
        a,ah=project(erp_triples(ob['points_1024x512']));g,gh=project(erp_triples(r['original_reference_points_1024x512']));new=np.array(r['new_floor_polygon_xz_h'],float)
        D=direction(a);hm,hc=height_components(a,ah,g,gh);oldI=iou(a,g);oldSb=bottom_distance(a,g)
        tip,diag=routing(code,a,g,new)
        row.update(execution_status='floor_diagnostic_only_new_top_pending',scope_pattern=tip,scope_pattern_is_visual_confirmation=False,dir=D)
        # Old complete numeric scores remain diagnostics: they do not choose scope/reference.
        for name,p in MODELS.items():row['old_reference_diagnostic_'+name]=float(score(oldI,oldSb,D,hm,hc,p))
        row['old_reference_diagnostic_IoU3D']=100*prism_iou(a,ah,g,gh)
        if ob['record_id'] in frozen.index:
            f=frozen.loc[ob['record_id']];assert f.object_id==ob['object_id'] and f.reference_id==r['original_reference_object_id']
            parity.append(dict(record_id=ob['record_id'],baseline_error=abs(float(f.WQ)-row['old_reference_diagnostic_WQ']),
                I_error=abs(float(f.iou_2d)-oldI),Sb_error=abs(float(f.S_bottom_deg)-oldSb),D_error=abs(float(f['dir'])-D),
                Hm_error=abs(float(f.Hmean)-hm),Hc_error=abs(float(f.Hcenter)-hc)))
        for typ,q,refid in [('original',g,r['original_reference_object_id']),('new_floor',new,r['new_floor_candidate_id'])]:
            I=iou(a,q);sb=bottom_distance(a,q)
            z={k:row[k] for k in ['record_id','object_id','image_id','image_code','worker_id','condition','cleaning_disposition']}
            z.update(reference_type=typ,reference_id=refid,I=I,Sb=sb,D=D,full_score_available=False,
                    geometry_only_routing=tip,photo_verified=False,**{('floor_upper_'+name):float(floor_upper_bound(I,sb,D,p)) for name,p in MODELS.items()})
            pairs.append(z)
            for k in ['I','Sb']+['floor_upper_'+name for name in MODELS]:row[typ+'_'+k]=z[k]
        union=Polygon(g).union(Polygon(new));inter=Polygon(g).intersection(Polygon(new));ap=Polygon(a)
        row.update(outside_both_fraction=float(ap.difference(union).area/ap.area),common_floor_recall=float(ap.intersection(inter).area/inter.area))
        ledger.append(row)
        for m in [0.,.1,.2]:
            rt,dd=routing(code,a,g,new,m);route_sensitivity.append(dict(record_id=ob['record_id'],image_code=code,margin_fraction=m,pattern=rt,diagnostics=json.dumps(dd)))
        viewer.append(dict(**{k:row[k] for k in ['record_id','object_id','image_id','image_code','worker_id','condition','cleaning_disposition','scope_pattern']},
                           a=a.tolist(),ah=ah.tolist(),original=g.tolist(),original_heights=gh.tolist(),new_floor=new.tolist(),new_heights=None,
                           upper_bounds={k:row[k] for k in row if 'floor_upper_' in k},new_reference_id=r['new_floor_candidate_id'],original_reference_id=r['original_reference_object_id']))
    pd.DataFrame(ledger).to_csv(out/'TWO_IMAGE_CHANGELOG_36.csv',index=False)
    pd.DataFrame(pairs).to_csv(out/'TWO_IMAGE_FLOOR_COMPARISONS_68.csv',index=False)
    pd.DataFrame(parity).to_csv(out/'TWO_IMAGE_PARITY_28.csv',index=False)
    pd.DataFrame(requests).to_csv(out/'TOP_BOUNDARY_REQUEST_8.csv',index=False)
    pd.DataFrame(route_sensitivity).to_csv(out/'TWO_IMAGE_ROUTING_SENSITIVITY.csv',index=False)
    dump(out/'two_image_geometry.json',viewer)
    assert len(ledger)==36 and len(pairs)==68 and len(parity)==28
    assert max(x['baseline_error'] for x in parity)<1e-10
    info=dict(objects=len(objs),answers=len(ledger),geometry_usable=len(viewer),floor_pairs=len(pairs),inherited_qualifications_unchanged=True,
              new_full_scores=0,new_top_boundaries=0,baseline_parity_count=len(parity),max_baseline_error=max(x['baseline_error'] for x in parity),
              photo_visual_adjudications=0,scope_pattern_only=True)
    dump(out/'TWO_IMAGE_EXECUTION.json',info);return info

def difficulty(inp,out):
    d=pd.read_csv(out/'SCORES_1145.csv');t=pd.read_csv(inp/'difficulty_target_projection_135.csv')
    z=d.merge(t,on=['image_id','image_code'],validate='many_to_one',how='left');assert z.current_class.notna().all()
    z['same_reference_id']=z.reference_id.eq(z.difficulty_reference_id)
    z['difficulty_comparison_allowed']=z.comparison_layer.eq('ordinary_manual_conditional')&z.same_reference_id&z.current_class.isin(['简单','中等','困难'])
    z['target_geometry_version_verified_in_this_run']=False
    z.to_csv(out/'DIFFICULTY_JOIN_1145.csv',index=False)
    z[~z.same_reference_id].to_csv(out/'DIFFICULTY_TARGET_MISMATCH_95.csv',index=False)
    s=z[z.difficulty_comparison_allowed];metrics=['Q_WQ','Q_A10','Q_B8L2','Q_IoU3D']
    # Mean per image/reference BEFORE class averages; do not overweight high-worker images.
    ims=s.groupby(['image_id','image_code','reference_id','building_id','current_class'])[metrics].mean().reset_index()
    ims['n_answers']=s.groupby(['image_id','reference_id']).size().reindex(pd.MultiIndex.from_frame(ims[['image_id','reference_id']])).to_numpy()
    ims.to_csv(out/'DIFFICULTY_IMAGE_UNIT_SCORES.csv',index=False)
    rows=[]
    for cl,g in ims.groupby('current_class'):
        for m in metrics:
            rows.append(dict(current_class=cl,metric=m,n_images=len(g),n_answers=int(g.n_answers.sum()),image_equal_mean=g[m].mean(),image_equal_median=g[m].median(),
                             record_weighted_mean=s[s.current_class.eq(cl)][m].mean(),classification_refitted=False))
    pd.DataFrame(rows).to_csv(out/'DIFFICULTY_CLASS_SUMMARY.csv',index=False)
    # Paired model-difference bootstrap by building: descriptive frozen pool, not causal difficulty.
    rng=np.random.default_rng(20261015);buildings=ims.building_id.unique();boot=[]
    for _ in range(400):
        b=rng.choice(buildings,size=len(buildings),replace=True);x=pd.concat([ims[ims.building_id.eq(v)] for v in b])
        for cl,g in x.groupby('current_class'):
            if len(g):boot.extend([dict(rep=_,current_class=cl,metric=m,mean_change=(g[m]-g.Q_WQ).mean()) for m in ['Q_A10','Q_B8L2']])
    pd.DataFrame(boot).to_csv(out/'DIFFICULTY_BUILDING_RESAMPLE.csv',index=False)
    info=dict(total_1145=len(z),same_reference_id=int(z.same_reference_id.sum()),different_reference_id=int((~z.same_reference_id).sum()),
              ordinary_same_id_three_class_rows=len(s),ordinary_same_id_three_class_images=len(ims),reference_geometry_rechecked=False,
              interpretation='Conditional on unchanged reference identity; geometry equality to difficulty target is not freshly verified. Different targets are excluded, not assigned convenient labels.')
    assert info['same_reference_id']==1050 and info['different_reference_id']==95
    dump(out/'DIFFICULTY_EXECUTION.json',info);return info

def mechanism(inp,out):
    d=pd.read_csv(out/'SCORES_1145.csv');h=pd.read_csv(out/'HUMAN44_AB_COMPARISON.csv');at=pd.read_csv(out/'NONLINEAR_ATTRIBUTIONS.csv')
    selected={'D02':'R02113','N09':'R01174','N10':'R01149','N11':'R01288','N13':'R01030','N14':'R00136','N18':'R03034','N19':'R00655','N24':'R00502','N27':'R02422','N29':'R00215','J04':'R03274','P01_A':'R02015','P01_B':'R00637'}
    rr=[]
    for name,rid in selected.items():
        z=d[d.record_id.eq(rid)].iloc[0];x=[float(z[k]) for k in ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']]
        r=dict(case_label=name,**z.to_dict())
        # Isolate the two changes in B, at fixed input: response scale then pooling.
        q8=float(score(*x,replace(A,direction_scale_deg=8)))
        r.update(B_response_only_A8=q8,B_scale_change=q8-float(z.Q_WQ),B_pooling_change=float(z.Q_B8L2)-q8)
        for nm in MODELS:
            a=at[(at.record_id.eq(rid))&at.model.eq(nm)].iloc[0]
            for k in a.index:
                if k.startswith(('delete_','shapley_','effective_','subadditive_')):r[nm+'_'+k]=a[k]
        rr.append(r)
    pd.DataFrame(rr).to_csv(out/'REPRESENTATIVE_CASES_AND_ATTRIBUTION.csv',index=False)
    near=pd.read_csv(out/'matched_context_pairs.csv');ns=[]
    for m in ['WQ','A10','B8L2','IoU3D']:
        gaps=abs(near[m+'_gap']);ns.append(dict(model=m,n_context_pairs=len(near),median_abs_gap=gaps.median(),mean_abs_gap=gaps.mean(),max_abs_gap=gaps.max(),
           signed_gap_agrees_with_lower_D=int(((near[m+'_gap']*near.D_difference)<0).sum()),causal_identification=False))
    pd.DataFrame(ns).to_csv(out/'MATCHED_CONTEXT_SUMMARY.csv',index=False)
    o=d[d.comparison_layer.eq('ordinary_manual_conditional')]
    summaries=[]
    masks={'I_ge090_D_le3':(o.iou_2d>=.9)&(o.dir<=3),'I_ge090_D_gt3':(o.iou_2d>=.9)&(o.dir>3),'I_lt050':o.iou_2d<.5,'D_ge10':o.dir>=10}
    for name,mask in masks.items():
        z=o[mask]
        for m in MODELS:
            a=at[at.record_id.isin(z.record_id)&at.model.eq(m)]
            summaries.append(dict(stratum=name,model=m,n=len(z),mean_score=z['Q_'+m].mean(),mean_actual_direction_drop=a.delete_intrinsic_direction_gain.mean(),
                                  median_actual_direction_drop=a.delete_intrinsic_direction_gain.median()))
    pd.DataFrame(summaries).to_csv(out/'MECHANISM_STRATA.csv',index=False)
    # Comparison to a literal low-IoU/high-D cross-term (not used as a proposed causal formula).
    sel=pd.read_csv(out/'leave_building_selection_diagnostic.csv')
    summary=sel.groupby(['selection_metric','k']).agg(target_cells=('target_cell','nunique'),changed_teams=('same_team_as_WQ',lambda v:int((~v).sum()))).reset_index()
    summary.to_csv(out/'SELECTION_CHANGE_SUMMARY.csv',index=False)
    return dict(matched_context_pairs=len(near),actual_selected_individual_team_diagnostics=len(sel),no_new_fusion=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();out=args.output
    assert (out/'SCORES_1145.csv').is_file()
    report=dict(two_image=two_images(ROOT/'inputs',out),difficulty=difficulty(ROOT/'inputs',out),mechanism=mechanism(ROOT/'inputs',out))
    dump(out/'EXTENSIONS_EXECUTION.json',report);print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
