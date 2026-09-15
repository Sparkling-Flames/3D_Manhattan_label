"""Cross-route diagnostics, paired uncertainty, counterexamples and local review list."""
from __future__ import annotations
import argparse,collections,itertools,json,math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from tools.thesis_main.analysis.image_portrait.pro_core import *
from tools.thesis_main.analysis.image_portrait.pro_core import _d_mask


def building_bootstrap(frame,value,replicates=2000):
    """Building-cluster resampling, conditional on this observed worker pool.
    Returns image-weighted and building-macro mean differences. These resamples
    measure uncertainty only; they are never additional people/images.
    """
    d=frame[['building',value]].dropna();gs=[x[value].to_numpy(float)for _,x in d.groupby('building')]
    if len(gs)<3:return (np.nan,)*4
    rng=np.random.default_rng(SEED);tot=np.array([g.sum()for g in gs]);ns=np.array([len(g)for g in gs]);means=tot/ns;ix=rng.integers(0,len(gs),(replicates,len(gs)))
    im=tot[ix].sum(1)/ns[ix].sum(1);macro=means[ix].mean(1)
    return *np.quantile(im,[.025,.975]),*np.quantile(macro,[.025,.975])


def A_associations():
    f=pd.read_csv(OUT/'A/interpretable_inputs.csv');t=pd.read_csv(OUT/'human/image_outcomes.csv');t=t[t.view=='reviewed'];d=t.merge(f,on=['image_id','building']);rows=[]
    for arm,g in d[d.condition.isin(['manual','semi'])].groupby('condition'):
        for variable in ['scene','doorway','open_layout_evidence',*TRAITS]:
            for level,q in g.groupby(variable):
                for target in TARGETS:
                    z=q.dropna(subset=[target]);rows.append(dict(condition=arm,feature=variable,value=level,target=target,n_images=len(z),n_buildings=z.building.nunique(),n_people_median=z.n_workers.median(),image_median=z[target].median(),image_mean=z[target].mean(),building_macro_mean=z.groupby('building')[target].mean().mean()))
    write_csv('A/trait_outcome_descriptives.csv',rows)
    # These are not simultaneous causal effects. Show categorical contrasts and
    # sparse coverage rather than a misleading 648-image regression denominator.
    mappings={'floor_boundary':{'present':0,'partial':1},'ceiling_boundary':{'present':0,'partial':1},'corner_occlusion':{'absent':0,'present':1},'doorway':{'否':0,'确认':1},'reflection_glass':{'absent':0,'present':1},'connected_space':{'absent':0,'present':1},'low_contrast':{'absent':0,'present':1}}
    contrasts=[];rng=np.random.default_rng(SEED)
    for arm,g in d[d.condition.isin(['manual','semi'])].groupby('condition'):
        for variable,mapping in mappings.items():
            q=g.assign(exposure=g[variable].map(mapping)).dropna(subset=['exposure'])
            for target in TARGETS:
                z=q.dropna(subset=[target]);a=z[z.exposure==0];b=z[z.exposure==1]
                delta=b[target].mean()-a[target].mean() if len(a) and len(b) else np.nan
                intervals=[];bs=sorted(z.building.unique())
                if len(a)>=3 and len(b)>=3 and a.building.nunique()>=2 and b.building.nunique()>=2:
                    ag=z.groupby(['building','exposure'])[target].agg(['sum','count']).unstack(fill_value=0).reindex(bs,fill_value=0)
                    # Use explicit arrays to handle absent levels in resampled clusters.
                    sums=np.array([[z[(z.building==build)&(z.exposure==level)][target].sum()for level in [0,1]]for build in bs]);counts=np.array([[int(((z.building==build)&(z.exposure==level)).sum())for level in [0,1]]for build in bs]);ix=rng.integers(0,len(bs),(1000,len(bs)));ss=sums[ix].sum(1);nn=counts[ix].sum(1);valid=(nn>0).all(1);vals=(ss[valid]/nn[valid])[:,1]-(ss[valid]/nn[valid])[:,0]
                    intervals=np.quantile(vals,[.025,.975]) if len(vals) else []
                contrasts.append(dict(condition=arm,feature=variable,target=target,n0=len(a),n1=len(b),buildings0=a.building.nunique(),buildings1=b.building.nunique(),unadjusted_mean_difference=delta,cluster_CI_low=intervals[0]if len(intervals)else np.nan,cluster_CI_high=intervals[1]if len(intervals)else np.nan,interpretation='exploratory_association_not_causal'))
    write_csv('A/unadjusted_trait_contrasts.csv',contrasts)
    common=pd.read_csv(OUT/'A/same_room_common_workers.csv');pairs=[]
    for variable,mapping in mappings.items():
        if variable+'_a' not in common:continue
        q=common.assign(dx=common[variable+'_b'].map(mapping)-common[variable+'_a'].map(mapping));q=q[q.dx.notna()&(q.dx!=0)]
        for target in ['quality','time','scope_non_normal']:
            for context_policy in ['all_existing_contexts','same_stage_only']:
                z=q[q.same_stage] if context_policy=='same_stage_only' else q;z=z.dropna(subset=[target+'_delta']).copy();z['aligned_difference']=z.dx*z[target+'_delta']
                # Average persons within a view pair, then view pairs within room;
                # the bootstrap unit remains building, not pair/person rows.
                view=z.groupby(['building','room_id','image_a','image_b'],as_index=False).aligned_difference.mean();room=view.groupby(['building','room_id'],as_index=False).aligned_difference.mean()
                ci=building_bootstrap(room,'aligned_difference') if len(room)else (np.nan,)*4
                pairs.append(dict(feature=variable,target=target,context_policy=context_policy,n_person_view_comparisons=len(z),n_distinct_workers=z.worker_id.nunique(),n_view_pairs=len(view),n_rooms=len(room),n_buildings=room.building.nunique(),room_macro_difference=room.aligned_difference.mean(),building_macro_difference=room.groupby('building').aligned_difference.mean().mean(),cluster_CI_low=ci[0],cluster_CI_high=ci[1]))
    write_csv('A/common_worker_matched_view_contrasts.csv',pairs)
    # Endpoint correlations are descriptive, not evidence for a total difficulty score.
    corr=[]
    for arm,g in t[t.condition.isin(['manual','semi'])].groupby('condition'):
        for a,b in itertools.combinations(TARGETS,2):
            z=g[[a,b,'building']].dropna();rho=spearmanr(z[a],z[b]).statistic if len(z)>2 and z[a].nunique()>1 and z[b].nunique()>1 else np.nan
            corr.append(dict(condition=arm,outcome_a=a,outcome_b=b,n_images=len(z),n_buildings=z.building.nunique(),spearman=rho))
    write_csv('cross_route/endpoint_correlations.csv',corr)


def B_associations():
    f=pd.read_csv(OUT/'B/model_feedback.csv');t=pd.read_csv(OUT/'human/image_outcomes.csv');t=t[(t.view=='reviewed')&t.condition.isin(['manual','semi'])];d=t.merge(f,on=['image_id','building']);stats=[];examples=[]
    numeric=[c for c in f if c not in ['image_id','building']]
    for arm,g in d.groupby('condition'):
        for variable in numeric:
            for target in TARGETS:
                z=g[[variable,target,'building']].dropna();rho=spearmanr(z[variable],z[target]).statistic if len(z)>2 and z[variable].nunique()>1 and z[target].nunique()>1 else np.nan
                stats.append(dict(condition=arm,feature=variable,target=target,n_images=len(z),buildings=z.building.nunique(),spearman=rho))
        for policy in ['enclosed','extended']:
            var='three_architecture_disagreement_'+policy
            for target in ['point_count_disagreement','within_topology_geometry_dispersion']:
                q=g[g.n_workers>=4].dropna(subset=[target,var])
                for building,h in q.groupby('building'):
                    train=q[q.building!=building]
                    if len(train)<10:continue
                    mlo,mhi=train[var].quantile([.25,.75]);hlo,hhi=train[target].quantile([.25,.75])
                    for _,r in h.iterrows():
                        typ='middle'
                        if r[var]<=mlo and r[target]>=hhi:typ='models_agree_humans_disagree'
                        elif r[var]>=mhi and r[target]<=hlo:typ='models_disagree_humans_agree'
                        elif r[var]<=mlo and r[target]<=hlo:typ='both_low_disagreement'
                        elif r[var]>=mhi and r[target]>=hhi:typ='both_high_disagreement'
                        examples.append(dict(image_id=r.image_id,building=building,condition=arm,Bi_policy=policy,target=target,n_workers=r.n_workers,n_same_topology_pairs=r.n_same_topology_pairs,model_disagreement=r[var],human_disagreement=r[target],training_model_q25=mlo,training_model_q75=mhi,training_human_q25=hlo,training_human_q75=hhi,quadrant=typ,reference_error=r.reference_geometry_error,point_disagreement=r.point_count_disagreement))
    write_csv('B/model_human_associations.csv',stats);write_csv('B/cross_fitted_counterexample_quadrants.csv',examples)
    # Geometric closeness to Bi range policies is model-relative, not a human
    # scope-intention label; compare only common point count, and report support.
    r=pd.read_csv(OUT/'human/response_metrics.csv.gz');r=r[r.main_worker_included & r.geometry_valid];z=np.load(OUT/'human/dense_boundaries.npz');dense=dict(zip(z['canonical_annotation_ids'],z['boundaries']));mb=np.load(OUT/'B/model_phase0_boundaries.npz');curves=dict(zip(mb['image_ids'],mb['boundaries']));ph=pd.read_csv(OUT/'B/model_phase_geometry_audit.csv');ph=ph[ph.yaw==0].pivot(index='image_id',columns='model',values='point_count');out=[]
    for row in r.itertuples():
        common=row.effective_point_count==ph.loc[row.image_id,'bi_enclosed']==ph.loc[row.image_id,'bi_extended']
        h=dense[row.canonical_annotation_id];en=curves[row.image_id][1];ex=curves[row.image_id][2]
        # The output boundaries are continuous raw predictions; point count only
        # determines whether model-relative policy comparison is interpretable.
        de=_d_mask(h,en);dx=_d_mask(h,ex);gap=_d_mask(en,ex)
        out.append(dict(canonical_annotation_id=row.canonical_annotation_id,image_id=row.image_id,building=row.building,worker_id=row.worker_id,condition=row.raw_condition,scope=row.scope,human_points=row.effective_point_count,bi_enclosed_points=ph.loc[row.image_id,'bi_enclosed'],bi_extended_points=ph.loc[row.image_id,'bi_extended'],common_point_count=common,heads_boundary_gap=gap,interpretable_policy_contrast=common and gap>=.01,human_to_enclosed=de if common else np.nan,human_to_extended=dx if common else np.nan,extended_minus_enclosed=dx-de if common else np.nan,reference_band_bias=row.band_width_bias_pixels))
    write_csv('B/model_relative_policy_closeness.csv.gz',out)


def paired_prediction_comparisons():
    a=pd.read_csv(OUT/'prediction/all_predictions.csv.gz');summary=[]
    bases=a[a.feature=='baseline'];methods=a[a.feature!='baseline']
    for key,g in methods.groupby(['feature','algorithm','condition','target','design']):
        for baseline in ['constant_median','scene_median']:
            base=bases[(bases.algorithm==baseline)&(bases.condition==key[2])&(bases.target==key[3])&(bases.design==key[4])]
            q=g.merge(base[['image_id','fold_id','prediction','absolute_error']],on=['image_id','fold_id'],suffixes=('','_baseline')).dropna(subset=['prediction','prediction_baseline']).copy()
            # Repeated room/context rows are collapsed per image for paired error.
            q['delta']=q.absolute_error-q.absolute_error_baseline
            z=q.groupby(['building','image_id'],as_index=False)[['delta','absolute_error','absolute_error_baseline']].mean();ci=building_bootstrap(z,'delta')
            summary.append(dict(feature=key[0],algorithm=key[1],condition=key[2],target=key[3],design=key[4],baseline=baseline,n_images=len(z),n_buildings=z.building.nunique(),method_MAE=z.absolute_error.mean(),baseline_MAE=z.absolute_error_baseline.mean(),MAE_difference=z.delta.mean(),relative_MAE_reduction=1-z.absolute_error.mean()/z.absolute_error_baseline.mean() if len(z) and z.absolute_error_baseline.mean()>0 else np.nan,paired_cluster_CI_low=ci[0],paired_cluster_CI_high=ci[1],building_macro_difference=z.groupby('building').delta.mean().mean(),building_macro_CI_low=ci[2],building_macro_CI_high=ci[3]))
    write_csv('cross_route/paired_prediction_comparisons.csv',summary)
    # Explicit sequential additions, on identical observations in each pair.
    comparisons=[('A_all_traits','A_scene_doorway'),('AB_traits_feedback','A_all_traits'),('ABC_traits_feedback_shared','AB_traits_feedback'),('A_21_rechecked','A_all_traits')]
    out=[]
    for new,old in comparisons:
        for key,g in a[(a.feature==new)&(a.design=='leave_building')].groupby(['algorithm','condition','target']):
            b=a[(a.feature==old)&(a.algorithm==key[0])&(a.condition==key[1])&(a.target==key[2])&(a.design=='leave_building')]
            z=g.merge(b[['image_id','absolute_error','prediction']],on='image_id',suffixes=('','_old')).dropna(subset=['prediction','prediction_old']);z['delta']=z.absolute_error-z.absolute_error_old;ci=building_bootstrap(z,'delta')
            out.append(dict(new=new,old=old,algorithm=key[0],condition=key[1],target=key[2],n_images=len(z),new_MAE=z.absolute_error.mean(),old_MAE=z.absolute_error_old.mean(),difference=z.delta.mean(),cluster_CI_low=ci[0],cluster_CI_high=ci[1]))
    write_csv('cross_route/sequential_increments.csv',out)


def local_review_list():
    reasons=[];f=pd.read_csv(OUT/'A/interpretable_inputs.csv').set_index('image_id');t=pd.read_csv(OUT/'human/image_outcomes.csv');t=t[(t.view=='reviewed')&t.condition.isin(['manual','semi'])]
    bad=pd.read_csv(OUT/'B/cross_fitted_counterexample_quadrants.csv')
    for _,r in bad[bad.quadrant.isin(['models_agree_humans_disagree','models_disagree_humans_agree'])].iterrows():
        reasons.append(dict(image_id=r.image_id,condition=r.condition,trigger=r.quadrant,question='核对真实边界是否可见、是否存在合理不同空间范围；共同模型偏差还是人员操作差异？不能仅依据参考或多数票裁决。',numerical_evidence=f"{r.target}={r.human_disagreement:.6f}; model disagreement={r.model_disagreement:.6f}; n={r.n_workers}; Bi policy={r.Bi_policy}",priority='high'))
    phase=pd.read_csv(OUT/'B/model_feedback.csv')
    for _,r in phase[(phase.hohonet_fallback_warning_phases>0)|(phase.bi_heads_boundary_difference>.05)].iterrows():
        reasons.append(dict(image_id=r.image_id,condition='model_only_or_historical',trigger='fallback_or_active_range_policy',question='核对后处理立方体回退是否删除了真实结构；Bi 两头差异是否对应可解释的空间范围，而不是模型错误。',numerical_evidence=f"fallback phases={r.hohonet_fallback_warning_phases}; Bi heads d_mask={r.bi_heads_boundary_difference:.6f}",priority='high'))
    for image,q in f[(f.connected_space!='present')|(f.low_contrast=='present')|(f.reflection_glass=='absent')].iterrows():
        reasons.append(dict(image_id=image,condition='image_portrait',trigger='rare_AI_trait',question='复核近常量 AI 字段的少数反例，并明确连通空间是否指真正可通行空间、门扇开闭或仅可见窗口。',numerical_evidence=f"connected={q.connected_space}; low_contrast={q.low_contrast}; reflection={q.reflection_glass}",priority='medium'))
    for r in load(BUNDLE/'visual/resolution_recheck.json')['images']:
        if r['changes']:reasons.append(dict(image_id=r['image_id'],condition='image_portrait',trigger='AI_resolution_disagreement',question='人工独立复核低清与原分辨率不一致的字段；保留两版本，不以同一 AI 复核当真值。',numerical_evidence=json.dumps(r['changes'],ensure_ascii=False),priority='medium'))
    for _,r in t[(t.n_workers>=10)&(t.point_count_disagreement>=.5)].iterrows():
        reasons.append(dict(image_id=r.image_id,condition=r.condition,trigger='persistent_point_count_diversity',question='不同点数是否代表同一范围的不同分段、有效多解、漏点，或跨范围解释？合理单人标法需单列保留。',numerical_evidence=f"n={r.n_workers}; point-count disagreement={r.point_count_disagreement:.6f}; same-count dispersion={r.within_topology_geometry_dispersion:.6f}",priority='high'))
    a=pd.DataFrame(reasons).drop_duplicates(['image_id','condition','trigger','numerical_evidence']);write_csv('local_image_review_queue.csv',a)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('part',choices=['AB','predictions','review','all']);a=ap.parse_args()
    if a.part in ['AB','all']:A_associations();B_associations()
    if a.part in ['predictions','all']:paired_prediction_comparisons()
    if a.part in ['review','all']:local_review_list()
