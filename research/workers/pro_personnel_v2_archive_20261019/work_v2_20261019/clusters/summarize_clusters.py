"""Population, threshold/method stability and raw 3D sensitivity diagnostics."""
from __future__ import annotations
import collections,gzip,hashlib,itertools,json,math,sys
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
SEED=2026101912

def interval(g,col,building='building_id'):
    a=g.groupby(building)[col].mean().dropna().to_numpy()
    if not len(a):return dict(buildings=0,mean=None,low=None,high=None)
    rng=np.random.default_rng(SEED);boot=rng.choice(a,(3000,len(a)),replace=True).mean(1)
    return dict(buildings=len(a),mean=float(a.mean()),low=float(np.quantile(boot,.025)),high=float(np.quantile(boot,.975)))

def main():
    summary=pd.read_csv(HERE/'pool_summary.csv');assign=pd.read_csv(HERE/'assignments.csv')
    pairs=pd.read_csv(HERE/'pair_distances.csv.gz');solver=pd.read_csv(HERE/'solver_status.csv')
    records=pd.read_csv(HERE/'records_geometry.csv')
    ag=[]
    for key,g in summary.groupby(['layer','method','threshold_deg'],dropna=False):
        r=dict(zip(['layer','method','threshold_deg'],key));r.update(pools=len(g),images=g.image_id.nunique(),
            buildings=g.building_id.nunique(),responses=int(g.N.sum()),clusters=int(g.cluster_count.sum()),singletons=int(g.singletons.sum()),
            worker_singleton_fraction=float(g.singletons.sum()/g.N.sum()),image_equal_largest_share=float(g.largest_share.mean()),
            image_equal_cluster_count=float(g.cluster_count.mean()))
        r.update({'largest_share_'+k:v for k,v in interval(g,'largest_share').items()});ag.append(r)
    pd.DataFrame(ag).to_csv(HERE/'partition_population_summary.csv',index=False)
    sensitivity=[]
    for pid,p in pairs.groupby('pool_id'):
        first=p.iloc[0]; n=int(first.N); same_count=p.available.eq(True)
        for a,b,label in [('same_affinity_9','same_affinity_12','threshold_9_to_12'),
                          ('same_complete_9','same_complete_12','complete_threshold_9_to_12'),
                          ('same_affinity_9','same_complete_9','affinity_vs_complete_9'),
                          ('same_affinity_12','same_complete_12','affinity_vs_complete_12')]:
            changed=p[a]!=p[b]
            affected=set(p.loc[changed,'object_id_a'])|set(p.loc[changed,'object_id_b'])
            sensitivity.append(dict(pool_id=pid,image_id=first.image_id,image_code=first.image_code,building_id=first.building_id,
                layer=first.layer,N=n,comparison=label,pairs=len(p),changed_pairs=int(changed.sum()),
                changed_pair_fraction=float(changed.mean()),affected_members=len(affected),affected_member_fraction=len(affected)/n,
                joined=int((~p[a]&p[b]).sum()),split=int((p[a]&~p[b]).sum()),same_count_pairs=int(same_count.sum())))
    sens=pd.DataFrame(sensitivity);sens.to_csv(HERE/'partition_sensitivity_per_pool.csv',index=False)
    comparisons=[]
    for key,g in sens.groupby(['layer','comparison']):
        comparisons.append(dict(zip(['layer','comparison'],key),pools=len(g),images=g.image_id.nunique(),
            pairs=int(g.pairs.sum()),changed_pairs=int(g.changed_pairs.sum()),changed_members_occurrences=int(g.affected_members.sum()),
            pools_any_change=int((g.changed_pairs>0).sum()),**interval(g,'changed_pair_fraction')))
    pd.DataFrame(comparisons).to_csv(HERE/'partition_sensitivity_summary.csv',index=False)
    diag=[]
    for layer,g0 in pairs.groupby('layer'):
        for cut in [9,12]:
            for relation,mask in [('all_pairs',np.ones(len(g0),bool)),('same_point_count',g0.available.eq(True)),
                    ('same_affinity',g0[f'same_affinity_{cut}']),('cross_affinity_same_count',~g0[f'same_affinity_{cut}'] & g0.available.eq(True)),
                    ('floor_iou_ge_095',g0.floor_iou.ge(.95))]:
                g=g0[mask];r=dict(layer=layer,threshold_deg=cut,relation=relation,pairs=len(g),images=g.image_id.nunique(),buildings=g.building_id.nunique(),
                    floor_measurable=int(g.floor_iou.notna().sum()),prism_measurable=int(g.prism_3d_iou.notna().sum()),
                    different_point_count=int((~g.available).sum()),floor_near_prism_lt080=int((g.floor_iou.ge(.95)&g.prism_3d_iou.lt(.8)).sum()))
                for col in ['distance_deg','floor_iou','prism_3d_iou','mean_height_abs_log_ratio','max_matched_radius_abs_log_ratio']:
                    x=g[col].dropna();r.update({col+'_mean':x.mean(),col+'_median':x.median(),col+'_q10':x.quantile(.1),col+'_q90':x.quantile(.9)})
                diag.append(r)
    pd.DataFrame(diag).to_csv(HERE/'geometry_relation_summary.csv',index=False)
    reverse=[]
    for layer,g in pairs[pairs.available].groupby('layer'):
        for cut in [9,12]:
            helped=g.distance_deg.gt(cut)&g.reversal_allowed_diagnostic_deg.le(cut)
            reverse.append(dict(layer=layer,threshold_deg=cut,pairs=len(g),images=g.image_id.nunique(),
                bound_cyclic_near=int(g.distance_deg.le(cut).sum()),additional_near_if_reversal_allowed=int(helped.sum()),
                images_with_additional_near=g.loc[helped,'image_id'].nunique(),
                confirmed_both_additional_pairs=int((helped&g.ring_confirmed_a&g.ring_confirmed_b).sum()),
                primary_reversal_allowed=False))
    pd.DataFrame(reverse).to_csv(HERE/'reverse_ring_sensitivity.csv',index=False)
    # Diagnostic exact ray formulas from clustering_numeric_research/sensitivity_3d.py;
    # pixel-center convention is explicitly separate from continuous 3D pair diagnostics.
    with gzip.open(HERE/'CLUSTER_API.json.gz','rt') as f:doc=json.load(f)
    base=[];pert=[]
    for pool in doc['pools']:
        meta=pool['meta']
        for r in pool['geometries']:
            points=np.asarray(r['points'],float).reshape(-1,2,2)
            for j,(top,bottom) in enumerate(points):
                alpha=math.pi/2-(top[1]+.5)*math.pi/512;beta=(bottom[1]+.5)*math.pi/512-math.pi/2
                valid=0<alpha<math.pi/2 and 0<beta<math.pi/2
                rho=1/math.tan(beta) if valid else None; h=1+rho*math.tan(alpha) if valid else None
                z=dict(pool_id=meta['pool_id'],image_id=meta['image_id'],image_code=meta['image_code'],building_id=meta['building_id'],
                       layer=meta['layer'],object_id=r['object_id'],worker_id=r['worker_id'],pair_index=j,
                       bottom_depression_deg=math.degrees(beta),near_horizon=abs(math.degrees(beta))<5,
                       radius_over_camera_height=rho,total_height_over_camera_height=h,valid=valid,convention='pixel_center_inherited_diagnostic')
                base.append(z)
                for delta in [-5,-1,1,5]:
                    beta2=beta+delta*math.pi/512;ok=valid and 0<beta2<math.pi/2 and 0<=bottom[1]+delta<512
                    rho2=1/math.tan(beta2) if ok else None;h2=1+rho2*math.tan(alpha) if ok else None
                    pert.append(dict(**z,bottom_delta_px=delta,direction_difference_deg=abs(delta)*180/512,
                        perturbed_valid=ok,radius_relative_change=rho2/rho-1 if ok else None,
                        height_relative_change=h2/h-1 if ok else None,
                        missing_reason='' if ok else 'projection_assumptions_not_met'))
    pd.DataFrame(base).to_csv(HERE/'bound_pair_projection_base.csv.gz',index=False)
    pert=pd.DataFrame(pert);pert.to_csv(HERE/'bottom_y_perturbations.csv.gz',index=False)
    pp=[]
    for key,g in pert.groupby(['layer','bottom_delta_px','near_horizon']):
        ok=g[g.perturbed_valid];pp.append(dict(zip(['layer','bottom_delta_px','near_horizon'],key),pairs=len(g),
            valid_pairs=len(ok),undefined_pairs=len(g)-len(ok),images=g.image_id.nunique(),workers=g.worker_id.nunique(),
            radius_abs_relative_mean=ok.radius_relative_change.abs().mean(),radius_abs_relative_median=ok.radius_relative_change.abs().median(),
            radius_abs_relative_q90=ok.radius_relative_change.abs().quantile(.9),radius_abs_relative_q99=ok.radius_relative_change.abs().quantile(.99),
            height_abs_relative_median=ok.height_relative_change.abs().median()))
    pd.DataFrame(pp).to_csv(HERE/'bottom_y_sensitivity_summary.csv',index=False)
    # Rank-defined case candidates; all denominators above remain visible.
    ordinary=pairs[pairs.layer=='ordinary_manual'];case_rows=[]
    candidate_groups=[('floor_near_height_far',ordinary[ordinary.floor_iou.ge(.95)].sort_values('prism_3d_iou')),
        ('angle_near_floor_far',ordinary[ordinary.distance_deg.le(9)].sort_values('floor_iou')),
        ('same_cluster_9_3d_far',ordinary[ordinary.same_affinity_9].sort_values('prism_3d_iou')),
        ('different_count_floor_near',ordinary[~ordinary.available].sort_values('floor_iou',ascending=False))]
    for kind,g in candidate_groups:
        chosen=g.drop_duplicates('image_id').head(4)
        for _,row in chosen.iterrows():case_rows.append(dict(case_kind=kind,selection_denominator=len(g),**row.to_dict()))
    pd.DataFrame(case_rows).to_csv(HERE/'geometry_case_candidates.csv',index=False)
    receipt=dict(pools=len(summary)//4,records=len(records),annotation_pairs=len(pairs),ordinary_annotation_pairs=len(ordinary),
        unavailable_count_mismatch_pairs=int((~pairs.available).sum()),geometric_projection_pairs=len(base),bottom_perturbation_rows=len(pert),
        perturbations_modify_source=False,clustering_uses_3d_weights=False,semantic_visual_reviews_performed=0,
        source_review_required='Human overlays may establish detail meaning; numerical similarity never proves same layout semantics.')
    (HERE/'GEOMETRY_DIAGNOSTICS_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
