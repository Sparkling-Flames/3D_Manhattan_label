"""Final audit and compact summaries of executed numerical research.

This module never fits on a test set, changes inputs, or reconstructs model outputs.
It inventories completed artifacts and pairs predictions already made in fixed folds.
"""
from __future__ import annotations
import collections, hashlib, json, platform, shutil
from importlib.metadata import version
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.image_portrait.pro_core import OUT,BUNDLE,ROOT,COMMIT,SEED,write_json,write_csv
from tools.thesis_main.analysis.image_portrait.pro_statistics import building_bootstrap

CORE=['reference_geometry_error','owner_valid_active_seconds','point_count_disagreement','within_topology_geometry_dispersion','scope_non_normal_rate','scope_entropy']

def paired(a,b,keys):
    z=a.merge(b[['image_id','fold_id','prediction','absolute_error']],on=['image_id','fold_id'],suffixes=('','_base')).dropna(subset=['prediction','prediction_base'])
    z['delta']=z.absolute_error-z.absolute_error_base
    im=z.groupby(['building','image_id'],as_index=False)[['absolute_error','absolute_error_base','delta']].mean()
    ci=building_bootstrap(im,'delta')
    return dict(**keys,n_images=len(im),n_buildings=im.building.nunique(),method_MAE=im.absolute_error.mean(),baseline_MAE=im.absolute_error_base.mean(),delta_MAE=im.delta.mean(),CI_low=ci[0],CI_high=ci[1],building_macro_delta=im.groupby('building').delta.mean().mean(),macro_CI_low=ci[2],macro_CI_high=ci[3])

def summarize_predictions():
    reg=json.loads((OUT/'features/registry.json').read_text());coverage=[];summary=[]
    files={'baseline':OUT/'prediction/baselines.csv.gz',**{n:OUT/'prediction'/f'{n}.csv.gz'for n in reg},'selected_layers':OUT/'prediction/selected_layers.csv.gz'}
    for name,path in files.items():
        assert path.is_file(),path
        a=pd.read_csv(path,low_memory=False)
        assert not a.duplicated(['feature','algorithm','condition','target','design','fold_id','image_id']).any(),name
        for key,g in a.groupby(['feature','algorithm','condition','target','design']):
            v=g.dropna(subset=['prediction']);summary.append(dict(zip(['feature','algorithm','condition','target','design'],key),n_target_images=g.image_id.nunique(),n_prediction_images=v.image_id.nunique(),n_buildings=v.building.nunique(),n_rooms=v.room_id.nunique(),image_MAE=v.absolute_error.mean(),building_macro_MAE=v.groupby('building').absolute_error.mean().mean(),room_macro_MAE=v.groupby('room_id').absolute_error.mean().mean()))
        coverage.append(dict(feature=name,rows=len(a),finite_predictions=int(a.prediction.notna().sum()),missing_predictions=int(a.prediction.isna().sum()),status_counts=json.dumps(a.status.value_counts().to_dict(),ensure_ascii=False),file=str(path.relative_to(OUT))))
        if name in reg:
            assert (OUT/'prediction'/f'{name}.inner.csv.gz').is_file()
            assert (OUT/'prediction'/f'{name}.coverage.csv').is_file()
    write_csv('prediction/final_score_summary.csv',summary);write_csv('prediction/completed_feature_inventory.csv',coverage)
    # Sparse post-registered exploratory representations: paired comparisons against
    # both constant and full-feedback baselines, never replacing earlier candidates.
    base=pd.read_csv(files['baseline']);full=pd.read_csv(files['B_feedback']);comparisons=[]
    for name in reg:
        if not name.startswith(('BX_','DX_')):continue
        a=pd.read_csv(files[name])
        for key,g in a.groupby(['algorithm','condition','target','design']):
            for label,bb in [('constant_median',base),('full_B_feedback',full)]:
                q=bb[(bb.algorithm==('constant_median' if label=='constant_median' else key[0]))&(bb.condition==key[1])&(bb.target==key[2])&(bb.design==key[3])]
                comparisons.append(paired(g,q,dict(method=name,baseline=label,algorithm=key[0],condition=key[1],target=key[2],design=key[3])))
    write_csv('cross_route/sparse_and_auxiliary_paired.csv',comparisons)
    return coverage

def horizon_summaries():
    root=OUT/'stability/horizon_prediction/prediction';base=pd.read_csv(root/'baselines.csv.gz');res=[];scores=[]
    for path in sorted(root.glob('*.csv.gz')):
        if '.inner.'in path.name:continue
        a=pd.read_csv(path)
        for key,g in a.groupby(['feature','algorithm','condition','target','design']):
            v=g.dropna(subset=['prediction']);scores.append(dict(zip(['feature','algorithm','condition','target','design'],key),n_targets=g.image_id.nunique(),n_predictions=v.image_id.nunique(),image_MAE=v.absolute_error.mean(),building_macro_MAE=v.groupby('building').absolute_error.mean().mean()))
            if key[0]=='baseline':continue
            for baseline in ['constant_median','scene_median']:
                b=base[(base.algorithm==baseline)&(base.condition==key[2])&(base.target==key[3])&(base.design==key[4])]
                res.append(paired(g,b,dict(feature=key[0],algorithm=key[1],condition=key[2],target=key[3],design=key[4],baseline=baseline)))
    write_csv('stability/horizon_prediction/score_summary.csv',scores);write_csv('stability/horizon_prediction/paired_comparisons.csv',res)

def tables_and_review():
    a=pd.read_csv(OUT/'E/continuous_disjoint_half_rank_reproducibility.csv')
    write_csv('E/continuous_rank_summary.csv',a.groupby('axis',as_index=False).agg(valid_halves=('spearman','count'),median_spearman=('spearman','median'),minimum=('spearman','min'),maximum=('spearman','max'),median_shared_people=('n_workers','median')))
    a=pd.read_csv(OUT/'E/B_source_sensitivity_type_ARI.csv')
    write_csv('E/B_source_type_summary.csv',a.groupby(['information','k'],as_index=False).agg(n_outer_buildings=('heldout_building','nunique'),median_ARI=('ARI_full_vs_natural','median'),minimum_ARI=('ARI_full_vs_natural','min'),maximum_ARI=('ARI_full_vs_natural','max')))
    a=pd.read_csv(OUT/'B/cross_fitted_counterexample_quadrants.csv')
    group=[k for k in ['condition','target','Bi_policy','quadrant'] if k in a]
    if group:write_csv('B/counterexample_counts.csv',a.groupby(group,as_index=False).agg(n_images=('image_id','nunique')))
    r=pd.read_csv(OUT/'local_image_review_queue.csv');extra=[]
    pairs=pd.read_csv(OUT/'D/pair_geometry_audit.csv')
    for row in pairs[pairs.relation_eligible].nlargest(2,'nadir_excluded_predicted_depth_agreement_0.05').to_dict('records'):
        for key in ['image_a','image_b']:
            extra.append(dict(image_id=row[key],condition='multiview_pair',trigger='DA3_depth_agreement_despite_rigid_camera_failure',question='核对两拍摄位置是否存在实际新增可见边界，以及投影候选是否对应真实同一表面。预测深度自一致不等于物理匹配。',numerical_evidence=f"{row['pair_id']}; max same-capture angle={row['max_same_capture_angle']:.6f}deg; nadir-excluded <=5% predicted-depth agreement={row['nadir_excluded_predicted_depth_agreement_0.05']:.6f}",priority='high'))
    extra.append(dict(image_id='X7HyMhZNoso_987fd31155514f6facb131bd5c14881d',condition='manual',trigger='same_point_count_supported_geometric_modes',question='24人均为8点却形成18人/6人几何簇：核对是否两种合理范围/边界解释、共同偏差或真实操作误差；不能凭多数投票或参考裁决。',numerical_evidence='complete-linkage d_mask cut0.10; counts18/6; strict finite-mode-mass stability conditional median k11; not formal stopping rule',priority='high'))
    r=pd.concat([r,pd.DataFrame(extra)],ignore_index=True).drop_duplicates(['image_id','condition','trigger'],keep='last');write_csv('local_image_review_queue.csv',r)
    write_json(OUT/'local_review_coverage.json',dict(question_rows=len(r),unique_image_ids=r.image_id.nunique(),no_original_images_accessed=True))


def manifest(coverage):
    reg=json.loads((OUT/'features/registry.json').read_text());numeric=ROOT.parent/'numerics/NUMERIC_TRANSPORT_MANIFEST.json'
    if numeric.is_file():shutil.copy2(numeric,OUT/'inputs/NUMERIC_TRANSPORT_MANIFEST.json')
    # Preserve all actual versions and text sources, not just a prose list of names.
    records=[]
    for path in sorted(BUNDLE.rglob('*')):
        if not path.is_file() or 'cloud' in path.relative_to(BUNDLE).parts:continue
        if path.suffix not in ['.md','.json','.jsonl','.yaml','.yml']:continue
        records.append(dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    source=[]
    for path in sorted((ROOT/'tools/thesis_main/analysis/image_portrait').glob('pro*.py')):
        source.append(dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    packages={name:version(name)for name in ['numpy','pandas','scipy','scikit-learn','statsmodels','pytest','shapely']}
    write_json(OUT/'EXECUTION_MANIFEST.json',dict(input_commit=COMMIT,method_version='pro_exploration_v1.0_e086b2b9',seed=SEED,python=platform.python_version(),packages=packages,features_registered=len(reg),feature_declarations=dict(collections.Counter('predeclared_candidate_or_protocol'if r.get('prespecified')else'added_exploration'for r in reg.values())),completed_prediction_files=len(coverage),source=source,input_text_versions=records,route_status={k:'executed_with_results_and_explicit_coverage'for k in 'ABCDE'},confirmed_unavailable={'AGENTS.md':'Not tracked anywhere in frozen commit; root fetch404 and git inventory agree','DINOv3':'Author denied access; no inference or substitute','legacy_d_t':'Verified realized scores and calibration reference pool unavailable','DA3_physical_information_completion':'0 of180 relation-eligible pairs pass even20degree within-capture rotation test; pass would still not prove physical validity','A_same_person_varying_trait_effects':'30same-roomviewpairs/108common-person comparisons lack verified varying binary exposures for the tested traits'},scope={'raw_annotation_changes':0,'formal_contract_changes':0,'original_images_read':0,'visual_inference_calls':0,'model_weights_downloaded':0},warnings=['All intervals are exploratory building-cluster bootstrap intervals conditional on this historical worker pool, not new-worker uncertainty or multiplicity-adjusted confirmation.','Conservative room folds reuse leave-building exclusions and are not a second independent test.','OOS not merged with Manual. Historical OSPA axes not renamed current d_mask.','Directory run_status.json reflects the most recent incremental batch only; completed_feature_inventory.csv is the final full inventory.']))

if __name__=='__main__':
    c=summarize_predictions();horizon_summaries();tables_and_review();manifest(c)
    print('Final numerical inventory written:',len(c),'prediction families')
