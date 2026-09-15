"""Source/phase/measurement sensitivities; never replaces the main fixed results."""
import argparse,collections,itertools,json
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import adjusted_rand_score
from tools.thesis_main.analysis.image_portrait import pro_core as core
from tools.thesis_main.analysis.image_portrait.pro_core import *
from tools.thesis_main.analysis.image_portrait import pro_predict as pred
from tools.thesis_main.analysis.image_portrait.pro_workers import ProfileCache,inputs,COMBOS,standardize_blocks,labels_for,evaluate_in_image,ALL_AXES


def source_forecasts():
    base=core.OUT;r=pd.read_csv(base/'human/response_metrics.csv.gz');r=r[r.main_worker_included];z=np.load(base/'human/dense_boundaries.npz');dense=dict(zip(z['canonical_annotation_ids'],z['boundaries']))
    variants={'no_imputed':r[~r.imputed_point], 'C1_only':r[r.stage=='C1'],'P1_only':r[r.stage=='P1'],'adjudicated_only':r[r.reference_status=='adjudicated_reference'],'public_reference_only':r[r.reference_status=='public_dataset_reference_not_quality_assumed']}
    root=base/'features';reg=json.loads((root/'registry.json').read_text());summary=[]
    for name,frame in variants.items():
        rows=[]
        for (image,arm),g in frame[frame.raw_condition.isin(['manual','semi'])].groupby(['image_id','raw_condition']):rows.append(summarize_group(g,dense,image,arm,name)[0])
        t=pd.DataFrame(rows);dest=base/'sensitivity'/name;dest.mkdir(parents=True,exist_ok=True);core.OUT=dest;pred.OUT=dest;write_csv('image_outcomes.csv',t)
        pred.baseline_predictions(t,pd.read_csv(base/'A/interpretable_inputs.csv'))
        for feat in ['A_all_traits','B_feedback','ABC_traits_feedback_shared','C_bilayout_fg_enclosed_global']:
            pred.evaluate_feature(feat,reg[feat],root,t)
        for path in (dest/'prediction').glob('*.csv.gz'):
            if path.name.endswith('.inner.csv.gz'):continue
            a=pd.read_csv(path)
            for key,g in a[a.design=='leave_building'].groupby(['feature','algorithm','condition','target']):
                v=g.dropna(subset=['prediction']);summary.append(dict(sensitivity=name,feature=key[0],algorithm=key[1],condition=key[2],target=key[3],n_targets=g.image_id.nunique(),n_predictions=v.image_id.nunique(),n_buildings=v.building.nunique(),image_MAE=v.absolute_error.mean(),building_MAE=v.groupby('building').absolute_error.mean().mean()))
        print('source prediction',name,'done',flush=True)
    core.OUT=base;pred.OUT=base;write_csv('sensitivity/source_forecast_summary.csv',summary)


def provenance_and_worker_sensitivity():
    old,current,r=inputs();inits={a['canonical_annotation_id']:a for a in load(BUNDLE/'human/semi_initializations.jsonl.gz')};base=pd.read_csv(OUT/'B/historical_semi_responses.csv');resolved=[]
    for row in base.to_dict('records'):
        init=inits[row['canonical_annotation_id']];trace=init['trace'];source=trace.get('initialization_reconstructed_source','');row['trace_source']=source
        row['resolved_payload_class']='C1_reference_source_payload_checkpoint_unbound' if source.startswith('export_label/groudTruth.json:data.vis_3d') else row['initialization_source'];row['old_source_field_conflicts_with_new_trace']=row['initialization_source']=='missing_required_initialization' and row['planned_payload_verified'];resolved.append(row)
    a=pd.DataFrame(resolved);write_csv('B/historical_semi_resolved_sources.csv',a)
    conflicts=[]
    for key,g in a.groupby(['resolved_payload_class','current_reference_status']):
        h=g[g.main_worker_included];v=h.dropna(subset=['initial_error_current_reference','final_error_current_reference']);conflicts.append(dict(resolved_payload_class=key[0],reference_status=key[1],all_rows=len(g),main_rows=len(h),quality_pairs=len(v),planned_trace_conflicts=int(h.old_source_field_conflicts_with_new_trace.sum()),zero_initial_reference_error=int((v.initial_error_current_reference<=1e-12).sum()),median_initial_error=v.initial_error_current_reference.median(),mean_net_reference_change=v.net_reference_improvement.mean(),median_edit=v.initial_final_d_mask.median(),actual_view_event_verified=int(h.participant_view_event_verified.sum()),bound_checkpoint=int(h.checkpoint_known.sum())))
    write_csv('B/initialization_source_conflicts.csv',conflicts)
    natural=set(a[a.initialization_source.isin(['control_natural','trap_natural'])].canonical_annotation_id)
    alternative=old[~old.axis.isin(['edit','benefit'])|old.canonical_annotation_id.isin(natural)].copy();oc=ProfileCache(old);nc=ProfileCache(alternative);cc=ProfileCache(current);rows=[];ari=[]
    for building in sorted(current.building_id.unique()):
        p,_=oc.fit([building]);q,_=nc.fit([building]);cp,_=cc.fit([building]);test=current[current.building_id==building]
        for info in ['B','QB','QTB','QTSB','quality_time_edit']:
            blocks=COMBOS[info];cols=[x for b in blocks for x in b]
            if not set(cols)<=set(p) or not set(cols)<=set(q):continue
            pa=p.dropna(subset=cols);qa=q.dropna(subset=cols);common=pa.index.intersection(qa.index)
            if min(len(pa),len(qa),len(common))<6:continue
            xp,_=standardize_blocks(pa,blocks);xq,_=standardize_blocks(qa,blocks)
            for k in [2,3,4]:
                if k>min(len(pa),len(qa))//2:continue
                lp=pd.Series(labels_for(xp,pa,k,cols[0]),index=pa.index);lq=pd.Series(labels_for(xq,qa,k,cols[0]),index=qa.index);ari.append(dict(heldout_building=building,information=info,k=k,n_workers=len(common),ARI_full_vs_natural=adjusted_rand_score(lp.loc[common],lq.loc[common]),full_workers=len(pa),natural_workers=len(qa)))
                for label,labels in [('full_archived_sources',lp),('P1_natural_only_B_axes',lq)]:
                    for axis,g in test.groupby('axis'):
                        if axis not in cp or axis not in ['semi__reference_error','manual__reference_error','semi__log_active_seconds']:continue
                        w=common.intersection(cp[axis].dropna().index);target=cp[axis].reindex(labels.index);preds={}
                        for group in sorted(labels.unique()):
                            value=target[labels==group].mean()
                            for worker in labels[labels==group].index:preds[worker]=value
                        scores=evaluate_in_image(g[g.worker_id.isin(w)],preds,dict(heldout_building=building,source_variant=label,information=info,k=k,axis=axis))
                        rows+=scores
    write_csv('E/B_source_sensitivity_type_ARI.csv',ari);write_csv('E/B_source_sensitivity_oof.csv.gz',rows)
    # Continuous rank reproducibility across genuinely disjoint sets of buildings.
    rng=np.random.default_rng(SEED);bs=np.array(sorted(old.building_id.unique()));out=[]
    for rep in range(100):
        order=rng.permutation(bs);left=order[:len(bs)//2];right=order[len(bs)//2:];p,_=oc.fit(left);q,_=oc.fit(right)
        for axis in ALL_AXES:
            if axis not in p or axis not in q:out.append(dict(repetition=rep,axis=axis,n_workers=0,spearman=np.nan,status='axis_unavailable'));continue
            w=p[axis].dropna().index.intersection(q[axis].dropna().index);rho=spearmanr(p.loc[w,axis],q.loc[w,axis]).statistic if len(w)>=4 else np.nan;out.append(dict(repetition=rep,axis=axis,n_workers=len(w),spearman=rho,status='evaluated'if len(w)>=4 else'insufficient_people'))
    write_csv('E/continuous_disjoint_half_rank_reproducibility.csv',out)
    prof,pa=cc.fit([]);write_csv('E/worker_current_continuous_descriptive.csv',prof.reset_index());rel=[]
    for a,b in itertools.combinations(prof.columns,2):
        z=prof[[a,b]].dropna();rel.append(dict(axis_a=a,axis_b=b,n_workers=len(z),spearman=spearmanr(z[a],z[b]).statistic if len(z)>=4 and z[a].nunique()>1 and z[b].nunique()>1 else np.nan))
    write_csv('E/continuous_worker_axis_correlations.csv',rel)
    write_json(OUT/'inputs/legacy_distances_limitation.json',dict(historical_reference_images=1647,reference_identity_vector_present=False,old_distance_projection='frozen outside current folds',main_inductive_selector_excludes_frozen_distances=True,legacy_d_t='missing_verified_realized_scores_and_calibration_reference_pool',not_used_as_substitute='No other risk or distance field renamed d_t'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['prediction','sources','all'],default='all');a=p.parse_args()
    if a.stage in ['prediction','all']:source_forecasts()
    if a.stage in ['sources','all']:provenance_and_worker_sensitivity()
