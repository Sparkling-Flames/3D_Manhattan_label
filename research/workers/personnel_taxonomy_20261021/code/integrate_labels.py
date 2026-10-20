"""Join independent label axes without fitting a post-hoc cross-product class.

Manual display hierarchy uses B structure; Semi uses the frozen position/scale
partition. Semi SP_LOW/SP_OTHER is a deterministic aggregation of frozen Ward3
SP_L/SP_A/SP_T, not another outcome-driven fit. Raw candidate labels remain.
"""
from pathlib import Path
import hashlib, json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parents[1]
ROOT=HERE.parents[2]
OUT=HERE/'labels'
SHA='6503e2f54966a74352a6ec526f211fc3871c1427'
REPO='https://github.com/Sparkling-Flames/3D_Manhattan_label'

def enrich(base, a, pose, scope):
    b=base.copy()
    b=b.rename(columns={'coarse_class':'structure_coarse_class','fine_class':'structure_fine_class',
        'coarse_name_zh':'structure_coarse_name_zh','fine_name_zh':'structure_fine_name_zh',
        'fine_status':'structure_fine_status','coarse_class_lobo_agreement':'structure_coarse_lobo_agreement',
        'coarse_class_lobo_support':'structure_coarse_lobo_support','fine_class_lobo_agreement':'structure_fine_lobo_agreement',
        'fine_class_lobo_support':'structure_fine_lobo_support'})
    a=a.rename(columns={'aligned_class_id':'geometry_relation_class','n_train_images':'geometry_n_train_images',
        'n_train_buildings':'geometry_n_train_buildings','unknown_reason':'geometry_missing_reason',
        'target_building':'heldout_building'})
    key=['worker_id','condition']+(['heldout_building'] if scope=='leave_building_out' else [])
    a=a[[*key,'geometry_relation_class','geometry_n_train_images','geometry_n_train_buildings','geometry_missing_reason']]
    if a.duplicated(key).any():raise ValueError('ambiguous geometry labels')
    b=b.merge(a,on=key,how='left',validate='1:1')
    pose=pose.rename(columns={'class_id':'position_scale_class','n_images':'position_n_train_images',
                             'n_buildings':'position_n_train_buildings','log_area_peer_delta':'position_log_area_peer_delta',
                             'log_height_peer_delta':'position_log_height_peer_delta'})
    pose['condition']='semi'
    pp=[*key,'position_scale_class','position_n_train_images','position_n_train_buildings',
        'position_log_area_peer_delta','position_log_height_peer_delta']
    b=b.merge(pose[pp],on=key,how='left',validate='1:1')
    b['geometry_relation_class']=b.geometry_relation_class.replace('unknown','unassigned').fillna('unassigned')
    b['position_scale_class']=b.position_scale_class.fillna('unassigned')
    b['primary_coarse_class']=b.structure_coarse_class
    b['primary_fine_class']=b.structure_fine_class
    b['primary_coarse_name_zh']=b.structure_coarse_name_zh
    b['primary_fine_name_zh']=b.structure_fine_name_zh
    b['primary_method']='B_manual_structure_ward2_nested4'
    b['primary_coarse_status']='adopted_conditional_working_class'
    b['primary_fine_status']='conditional_member_sensitive'
    semi=b.condition.eq('semi')
    b.loc[semi,'primary_method']='B_semi_position_scale_ward3_aggregated2'
    b.loc[semi,'primary_fine_class']=b.loc[semi,'position_scale_class']
    b.loc[semi,'primary_coarse_class']=b.loc[semi,'position_scale_class'].map({'SP_L':'SP_LOW','SP_A':'SP_OTHER','SP_T':'SP_OTHER'}).fillna('unassigned')
    b.loc[semi,'primary_coarse_name_zh']=b.loc[semi,'primary_coarse_class'].map({'SP_LOW':'较低推导高度','SP_OTHER':'其余尺度表达','unassigned':'证据不足'})
    b.loc[semi,'primary_fine_name_zh']=b.loc[semi,'position_scale_class'].map({'SP_L':'较低推导高度','SP_A':'较大推导底面积（主要旧批）','SP_T':'常规尺度比较组','unassigned':'证据不足'})
    b.loc[semi,'primary_fine_status']=b.loc[semi,'position_scale_class'].map({'SP_L':'adopted_conditional_working_class','SP_A':'conditional_old_source_only','SP_T':'comparison_group_not_homogeneous_style','unassigned':'unassigned'})
    b.loc[semi & b.position_scale_class.eq('SP_A') & b.origin.eq('new'),'primary_fine_status']='not_supported_in_new_source'
    b['structure_adoption_status']=np.where(semi,'exploratory_not_general_semi_taxonomy','adopted_conditional_working_class')
    b.loc[b.structure_coarse_class.eq('unassigned'),'structure_adoption_status']='unassigned'
    unassigned=b.primary_coarse_class.eq('unassigned')
    b.loc[unassigned,['primary_coarse_status','primary_fine_status']]='unassigned'
    b['label_fit_scope']=scope
    b['label_version']='personnel_taxonomy_20261021_v1'
    b['input_commit']=SHA
    b['eligibility_policy']='labels_do_not_change_quality_or_team_eligibility'
    b['target_usage_rule']='use_exact_condition_and_heldout_building_for_target_evaluation'
    b['geometry_relation_status']=np.where(b.geometry_relation_class.ne('unassigned'),'adopted_geometric_relationship_partition','unassigned')
    first=['worker_id','condition','label_version','label_fit_scope','heldout_building',
           'primary_method','primary_coarse_class','primary_coarse_name_zh','primary_coarse_status',
           'primary_fine_class','primary_fine_name_zh','primary_fine_status','missing_reason',
           'geometry_relation_class','geometry_relation_status','structure_coarse_class','structure_fine_class',
           'structure_adoption_status','position_scale_class','origin','n_images','n_buildings','n_quality_usable','n_independent_vote_eligible']
    return b[[c for c in first if c in b]+[c for c in b if c not in first]]

def main():
    OUT.mkdir(exist_ok=True)
    a=pd.read_csv(HERE/'route_a/worker_labels.csv')
    a=a[a.method.eq('A2_samecount_source_residual') & a.k.eq(3) & a.stage.eq('all_data_descriptive')]
    al=pd.read_csv(HERE/'route_a/worker_labels_lobo.csv')
    al=al[al.method.eq('A2_samecount_source_residual') & al.k.eq(3)]
    p=pd.read_csv(HERE/'route_b/semi_new_candidate/final_labels.csv');p=p[p.candidate.eq('semi_position_scale')]
    pl=pd.read_csv(HERE/'route_b/semi_new_candidate/lobo_labels.csv');pl=pl[pl.candidate.eq('semi_position_scale')]
    final=enrich(pd.read_csv(HERE/'route_b/final_labels.csv'),a,p,'all_data_descriptive')
    lobo=enrich(pd.read_csv(HERE/'route_b/lobo_labels.csv'),al,pl,'leave_building_out')
    # Only the 22 Manual and 12 Semi buildings actually observed in that
    # condition belong in the recommended target-label inventory.
    lobo=lobo[lobo.target_condition_observed.eq(True)].copy()
    observed=lobo[lobo.target_condition_observed.eq(True)].copy()
    for idx,row in final.iterrows():
        g=observed[observed.worker_id.eq(row.worker_id)&observed.condition.eq(row.condition)]
        for tier in ['coarse','fine']:
            col='primary_'+tier+'_class';valid=g[g[col].ne('unassigned')]
            final.loc[idx,'primary_'+tier+'_lobo_support']=len(valid)
            final.loc[idx,'primary_'+tier+'_lobo_agreement']=valid[col].eq(row[col]).mean() if len(valid) and row[col]!='unassigned' else np.nan
    for cond in ['manual','semi']:
        d=final[final.condition.eq(cond)].sort_values('worker_id')
        d.to_csv(OUT/(cond+'_labels.csv'),index=False,encoding='utf-8-sig')
    lobo.sort_values(['condition','heldout_building','worker_id']).to_csv(OUT/'lobo_labels.csv',index=False,encoding='utf-8-sig')
    catalogs=[]
    for cond,g in final.groupby('condition'):
        for axis,name in [('primary_coarse_class','primary_coarse_name_zh'),('primary_fine_class','primary_fine_name_zh'),('geometry_relation_class',None),('structure_fine_class','structure_fine_name_zh')]:
            for cl,x in g.groupby(axis):
                catalogs.append(dict(condition=cond,axis=axis,class_id=cl,name_zh='证据不足' if cl=='unassigned' else x[name].iloc[0] if name else '几何关系分区',
                    n_people=len(x),members='|'.join(x.worker_id),fit_scope='all_data_descriptive'))
    pd.DataFrame(catalogs).to_csv(OUT/'class_catalog.csv',index=False,encoding='utf-8-sig')
    fields={
        'schema_version':'personnel_taxonomy_20261021_v1',
        'join_keys':{'final':['worker_id','condition'],'target_validation':['worker_id','condition','heldout_building']},
        'primary_hierarchy':{'manual':'M0->{M00,M01}; M1->{M10,M11}',
                             'semi':'SP_LOW->{SP_L}; SP_OTHER->{SP_A,SP_T}; deterministic aggregation of frozen position Ward3 labels'},
        'independent_axes':'A2 geometry_relation_class and B structure classes are not a fitted cross-product taxonomy.',
        'final_labels_use':'membership description and research workstation display only; do not use for target-building estimates',
        'lobo_labels_use':'training inputs, scaling and clustering exclude the entire heldout_building; no target Q/fusion selection',
        'semi_fine_status':'SP_A supported mainly in v1; W131 new-source finer label is not supported. SP_T is a comparison group.',
        'structure_semi_status':'S00/S01/S10 and S0/S1 retained as frozen exploratory candidate for reproducibility; not adopted as universal Semi classes',
        'training_support':'at least 12 comparable ordinary images and 4 buildings for B; A uses at least 6 images and 3 buildings',
        'geometry_distance':'same-count bound top-bottom maximum spherical angle under existing ring and cyclic shift, degrees; differs from fusion wall correspondence 7.5 degrees',
        'missing_reasons':{'no_comparable_ordinary_history_in_this_condition':'该条件无可比较普通历史','fewer_than_12_comparable_images_or_4_buildings':'普通历史少于12图或4楼'},
        'qualification':'These labels never alter is_oos, quality_usable, independent_vote_eligible, reference version, cleaning disposition or team eligibility.',
        'n_quality_usable':'quality-usable records inside this label training input, not all inventory records; see inventory_usage_by_worker for all-inventory counts',
        'n_independent_vote_eligible':'voter flag within this label training input; formal fusion still requires the complete old pool contract',
        'geometric_height':'dimensionless height inferred at camera height=1; never physical measured metres',
        'fusion_event':['event_id','pool_id','condition','building','n','m','core_workers','A_workers','B_workers','C_workers','net_B8L2','net_D10'],
        'fusion_contrasts':{'within':'B versus A, same class counts and same source counts, actual m replacements','cross':'C versus A, changed class block, same source counts and background, actual m replacements','net_quality':'Q(C)-Q(B), equal n/background/m/source counts; not Q(C)-Q(A)'},
        'fusion_frozen_label_binding':{
            'B_main_and_paths':'Use route_b/lobo_labels.csv by condition + heldout_building + worker_id, including exploratory Semi S classes. Later adopted display labels do not redefine the original experiment.',
            'A2_specific_and_relabels':'Use route_a/worker_labels_lobo.csv method=A2_samecount_source_residual, stage=leave_building_out and raw fold class_id. aligned_class_id is display-only. Preserve the original B or historical design when relabelling.',
            'Semi_position':'Use route_b/semi_new_candidate/lobo_labels.csv candidate=semi_position_scale. Exchanges compare SP_L versus SP_T only; SP_A may occur in the common background. SP_OTHER=SP_A+SP_T was not the exchanged block.'},
        'fusion_aggregation_and_denominators':'Event mean within image -> image mean within building -> equal building mean. Paired BEV/top distances use events valid in both arms; joint_stable_main includes all registered events, incomplete/different-count pairs false. Missing Q is not zero.',
        'fusion_joint_stable_main':'Both endpoints complete_evaluable; abs(delta B8L2)<=2; identical node count; BEV Jaccard difference<=0.05; cyclic structural angular bound<=3 degrees. Different from original-answer 9/12 degree clustering and fusion 7.5 degree correspondence.',
        'methods_and_limits':'A has development-selected fixed building checks; B/SP are exploratory working classes with building-out internal checks, not untouched external validation.',
        'input_commit':SHA}
    # Retain independently reviewed supplementary field explanations when the
    # integration is rerun; generated core definitions always take precedence.
    fp=OUT/'FIELD_CONTRACT.json'
    supplement=json.loads(fp.read_text()) if fp.exists() else {}
    (OUT/'FIELD_CONTRACT.json').write_text(json.dumps({**supplement,**fields},ensure_ascii=False,indent=2))
    rows=[]
    inputs=[
       'research/statistics/v2_evidence_audit_20261019/records.json.gz',
       'research/workers/personnel_marking_patterns_20261020/record_expression.csv',
       'research/difficulty/difficulty_mechanisms_v2_20261020/record_conditions.csv.gz',
       'research/same_room/same_room_multiview_20261020/structure_transfer/record_features.csv.gz',
       'research/workers/personnel_interchangeability_20261020/analysis/visual_sources/release_IMAGE_INDEX.csv']
    for rel in inputs:
        path=ROOT/rel
        if path.exists():rows.append(dict(path=rel,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),url=f'{REPO}/blob/{SHA}/{rel}'))
    manifest={'repository':REPO,'commit':SHA,'release_tag':'quality-original-images-20261015',
              'release_url':REPO+'/releases/tag/quality-original-images-20261015','inputs':rows,
              'additional_inputs':'Exact original clustering, fusion engine, frozen pools and reused endpoint paths are declared by route_a/DESIGN_AND_RECEIPT.json, fusion/REGISTRATION.json and source imports in the retained scripts.',
              'source_images':'selected Release PNG members fetched by range, ZIP CRC checked; full source image archives are not included',
              'new_profile_composition_package':'HOHONET_personnel_research_20261020 package not supplied; repo inputs and user specified jtc-26 independently used',
              'point_or_reference_edits':False}
    (HERE/'INPUT_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print(json.dumps({'manual_rows':int(final.condition.eq('manual').sum()),'semi_rows':int(final.condition.eq('semi').sum()),'lobo_rows':len(lobo),'primary_assigned':int(final.primary_coarse_class.ne('unassigned').sum())},ensure_ascii=False))

if __name__=='__main__':main()
