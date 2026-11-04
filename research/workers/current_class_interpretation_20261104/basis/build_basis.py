#!/usr/bin/env python3
"""Document frozen current classifications; never fit or alter classifications."""
from pathlib import Path
import hashlib
import json
import gzip
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
HEAD = '48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b'
CUR = 'research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/'
OLD = 'research/workers/personnel_v21_reselection_20261029/'
INPUTS = {
    'current_basis': 'research/data/releases/v2.1/CURRENT_RESEARCH_BASIS.md',
    'current_update': CUR + 'README.md',
    'target_labels': CUR + 'classification/LABELS_ALL_LOBO.csv.gz',
    'rfuse_labels': CUR + 'rfuse/RFUSE_LABELS_ALL_LOBO.csv.gz',
    'main45_labels': OLD + 'classification/MAIN45_LABELS_ALL_LOBO.csv.gz',
    'raw': CUR + 'classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz',
    'history': CUR + 'classification/HISTORY_ALL_LOBO.csv.gz',
    'old_history': OLD + 'independent_review/reaudit_20261029/source_archive/stage06_reproduction/inputs_and_source/prior_extracted/stage02/classification/HISTORY_FEATURES_ALL_LOBO.csv.gz',
    'rfuse_features': CUR + 'rfuse/RFUSE_FEATURES_ALL_LOBO.csv.gz',
    'rfuse_training': CUR + 'rfuse/NATURAL_TRAINING_ENDPOINTS.csv.gz',
    'target_code': OLD + 'classification/code/build_target_aware_candidates.py',
    'rfuse_code': 'analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked/03/reverse/code/learn_natural_fusion_roles.py',
    'rfuse_input_code': 'analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked/03/reverse/code/prepare_natural_training.py',
    'update_code': 'tools/thesis_main/analysis/recompute_v21_image_difficulty_20261030.py',
    'rfuse_v21_code': 'tools/thesis_main/analysis/refit_v21_fusion_roles_20261028.py',
    'ac_frozen_labels': 'research/workers/personnel_ac_v21_20261030/stage00_intake/FINAL_LABELS_FOR_AC_ALL_LOBO.csv.gz',
    'ac_intake_compatibility': 'research/workers/personnel_ac_v21_20261030/stage00_intake/CURRENT_INPUT_COMPATIBILITY.json',
}
METHODS = ['TARGET_DSTRUCT_K2', 'TARGET_DSTRUCT_K3', 'RFUSE_GEOM_K2', 'OPPJOINT_K3', 'OPPJOINT_K4']

def read(key):
    return pd.read_csv(ROOT / INPUTS[key], low_memory=False)

def save(df, name):
    data = df.to_csv(index=False).encode('utf-8-sig')
    if name.endswith('.gz'):
        data = gzip.compress(data, mtime=0)
    (OUT / name).write_bytes(data)

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    frames = []
    for key, methods in [('target_labels', METHODS[:2]), ('rfuse_labels', METHODS[2:3]), ('main45_labels', METHODS[3:])]:
        f = read(key)
        f = f[f.method.isin(methods)].copy()
        f['label_source'] = INPUTS[key]
        f['current_source_commit'] = HEAD
        f['current_research_release'] = 'v2.1'
        f['source_underlying_data_version'] = f['underlying_data_version']
        f['class_id'] = f.class_id.fillna('unknown')
        frames.append(f)
    labels = pd.concat(frames, ignore_index=True)
    cols = ['method','family','k','worker_id','origin','heldout_building','class_id','known','missing_reason','label_stage','input_conditions','evaluation_condition','source_underlying_data_version','current_research_release','label_source','current_source_commit']
    labels = labels[cols].sort_values(['method','heldout_building','worker_id']).reset_index(drop=True)
    assert not labels.duplicated(['method','heldout_building','worker_id']).any()
    assert len(labels) == 5 * 23 * 62
    labels['class_order_basis'] = labels.method.map(lambda m: 'training_hard_structure_center_ascending' if m.startswith('TARGET') else ('training_hard_fusion_turn_response_ascending' if m.startswith('RFUSE') else 'training_peer_centered_quality_center_ascending'))
    save(labels, 'WORKER_LABELS_ALL_LOBO.csv.gz')
    all_labels = labels[labels.heldout_building.eq('ALL')]
    roster = all_labels.pivot(index=['worker_id','origin'],columns='method',values='class_id').reset_index()
    save(roster, 'WORKER_ROSTER_ALL.csv')
    members = all_labels.groupby(['method','class_id'],dropna=False).agg(workers=('worker_id','nunique'),members=('worker_id',lambda s:'|'.join(sorted(s)))).reset_index()
    members['label_use'] = 'ALL descriptive roster, not permanent LOBO membership'
    save(members, 'CLASS_MEMBERS_ALL.csv')

    history = read('history')
    old_history = read('old_history')
    k = ['worker_id','heldout_building']
    unchanged = [c for c in history if c.startswith(('m_all_','m_opp_','m_challenge_','m_timed_')) and c in old_history]
    hc = history[k+unchanged].merge(old_history[k+unchanged],on=k,validate='one_to_one',suffixes=('_new','_old'))
    identical = all(np.allclose(hc[c+'_new'],hc[c+'_old'],equal_nan=True,atol=1e-10,rtol=1e-10) for c in unchanged)
    assert identical
    # Training history only. These values are not held-out original-answer outcomes.
    hcols = [c for c in history if c.startswith(('m_all_','m_hard_','m_easy_','m_challenge_','m_opp_','m_timed_')) and pd.api.types.is_numeric_dtype(history[c])]
    joined = labels[labels.known & ~labels.method.str.startswith('RFUSE')].merge(history[k+hcols],on=k,validate='many_to_one')
    centers = joined.groupby(['method','heldout_building','class_id'])[hcols].mean().reset_index()
    n = joined.groupby(['method','heldout_building','class_id']).size().rename('workers').reset_index()
    centers = centers.merge(n, on=['method','heldout_building','class_id'])
    centers['interpretation'] = 'training_descriptive_center_not_heldout_outcome'
    save(centers,'CLASS_TRAINING_CENTERS_BY_FOLD.csv.gz')
    ff = read('rfuse_features')
    ff = ff[ff.family.eq('RFUSE_GEOM')].drop(columns=['family'])
    fcols = [c for c in ff if c.startswith(('all_','easy_','hard_')) and pd.api.types.is_numeric_dtype(ff[c])]
    fj = labels[labels.known & labels.method.eq('RFUSE_GEOM_K2')].merge(ff,on=k,validate='one_to_one')
    fc = fj.groupby(['method','heldout_building','class_id'])[fcols].mean().reset_index()
    fn = fj.groupby(['method','heldout_building','class_id']).size().rename('workers').reset_index()
    fc = fc.merge(fn,on=['method','heldout_building','class_id'])
    fc['interpretation'] = 'training_fusion_response_ridge_coefficients_not_original_answer_values'
    save(fc,'RFUSE_FUSION_RESPONSE_CENTERS_BY_FOLD.csv.gz')

    raw = read('raw')
    ordinary = raw[raw.layer.isin(['ordinary_manual','ordinary_semi'])].copy()
    assert ordinary.object_id.is_unique
    capacity = []
    for method in METHODS:
        lab = labels[labels.method.eq(method) & labels.heldout_building.ne('ALL')]
        d = ordinary.merge(lab[['worker_id','heldout_building','class_id']],left_on=['worker_id','building'],right_on=['worker_id','heldout_building'],how='left',validate='many_to_one')
        d['class_id'] = d.class_id.fillna('unknown')
        for pool,g in d.groupby('pool_id'):
            meta = {c:g[c].iloc[0] for c in ['pool_id','image','image_id','building','reference_id','reference_version','condition','scope','layer','official_difficulty']}
            for cl in [f'C{i}' for i in range(1,int(method[-1])+1)]+['unknown']:
                z = g[g.class_id.eq(cl)]
                capacity.append(dict(method=method,class_id=cl,**meta,workers=z.worker_id.nunique(),records=len(z),Q_available_workers=z[z.B8L2.notna()].worker_id.nunique(),positive_T_workers=z[z.source_active_time_seconds.gt(0)].worker_id.nunique(),members='|'.join(sorted(z.worker_id.unique())),capacity_scope='ordinary_scored_raw_inventory',label_use='target_building_excluded'))
    capacity = pd.DataFrame(capacity)
    save(capacity,'CLASS_CAPACITY_PER_POOL.csv.gz')
    summary = capacity.groupby(['method','condition','scope','class_id']).agg(pools=('pool_id','size'),images=('image_id','nunique'),buildings=('building','nunique'),capacity_min=('workers','min'),capacity_median=('workers','median'),capacity_max=('workers','max'),pools_with_class=('workers',lambda s:int(s.gt(0).sum())),pools_with_3=('workers',lambda s:int(s.ge(3).sum())),pools_with_7=('workers',lambda s:int(s.ge(7).sum()))).reset_index()
    save(summary,'CLASS_CAPACITY_SUMMARY.csv')

    training = read('rfuse_training')
    eligible = training[training.training_eligible].copy()
    eligible = eligible[eligible.groupby('group_id').team_key.transform('size').ge(4)]
    checks = dict(frozen_commit=HEAD, labels_rows=len(labels), label_unique_key=['method','heldout_building','worker_id'], folds=23, workers_in_roster=62, methods=METHODS,
        target_ALL_sizes=members[members.method.str.startswith('TARGET')][['method','class_id','workers']].to_dict('records'),
        OPPJOINT_non_difficulty_history_identical=identical, OPPJOINT_unchanged_columns=unchanged, OPPJOINT_checked_person_fold_rows=len(hc),
        rfuse_registered_endpoints=len(training),rfuse_training_endpoints=len(eligible),rfuse_training_pools=eligible.pool_id.nunique(),rfuse_training_images=eligible.image_id.nunique(),rfuse_training_buildings=eligible.building.nunique(),rfuse_training_n_min=int(eligible.k.min()),rfuse_training_n_max=int(eligible.k.max()),
        rfuse_legacy_metadata_note='underlying_data_version=v2 is inherited by labels_for(); current update input/labels belong to v2.1 and are not replaced with historical v2 labels',
        ordinary_raw_records=len(ordinary),raw_original_records=len(raw),new_fusion=0,new_scoring=0,new_classification_fit=0)
    (OUT/'LABEL_VERSION_CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    contract = dict(frozen_commit=HEAD, methods={
        'TARGET_DSTRUCT_K2_K3':dict(role='ordinary Manual forward classification; K2 coarse, K3 main',label_source=INPUTS['target_labels'],training='ordinary Manual, primary and admitted other targets',heldout='ALL descriptive plus 22 leave-one-building-out folds',direct_Q=False,direct_T=False,reference_informed=True,raw_structure=['turn_n','short_turn_edges','near_straight_nodes_5deg','unmatched_ref_9'],domains=['overall structure','hard structure and hard minus easy structure'],ordering=['m_hard_turn_n','m_hard_short_turn_edges','m_all_turn_n'],gates='all>=12 images/3 buildings; easy>=5/2; hard>=4/2; complete required features',embedding='robust median/(p85-p15), std then1 fallback, clip ±3, PCA <=2/domain, equal-domain RMS normalization; Ward one tree'),
        'RFUSE_GEOM_K2':dict(role='reverse fusion-response explanation',label_source=INPUTS['rfuse_labels'],training='actual ordinary Manual natural teams, n10–24, legal targets, complete model outputs, at least four unique teams within pool×n',direct_Q=False,direct_T=False,indirect_quality_dependence='shared training eligibility requires all geometry and quality outputs; Q coefficients are saved for description but do not enter GEOM embedding or alpha selection',geometry_outputs=['floor_turn5_n','floor_short_edge_03_n','floor_redundant5_n','bottom_y_mean_px','top_y_mean_px','log_floor_area','log_height_mean'],domains=['structure response','boundary/scale response'],strata=['all','hard','hard_minus_easy'],regression='occurrence-weighted centered team composition shares and outputs within pool×n; buildings equal, images equal, available pool×n groups equal within image; ridge coefficients',team_sizes=[10,12,14,16,20,24],alpha_grid=[0.1,1,10],alpha_selection='minimum inner-building normalized geometry response MSE, domain/stratum balanced; outer building excluded',ordering=['hard_floor_turn5_n','all_bottom_y_mean_px'],gates='all>=8 images/3 buildings; easy>=5/2; hard>=3/2',embedding='robust median/(p85-p15), clip ±3, PCA2/domain, equal-domain RMS normalization; Ward',semi_use='cross-mode application of Manual response labels, not a separately trained Semi classifier',distinct_methods='GEOMQ includes Q; TARGET_RFUSE changes target weighting; neither silently substitutes for RFUSE_GEOM_K2'),
        'OPPJOINT_K3_K4':dict(role='joint original-answer, quality/time and mixture profile',label_source=INPUTS['main45_labels'],training='ordinary Manual, legal primary and admitted other targets; not Manual+Semi joint training',direct_Q=True,direct_T=True,domains=['structure response to geometric opportunity','boundary/scale response to geometric opportunity','Q overall, weighted p20 and opportunity response','source-centered logT overall and opportunity response'],opportunity=['log1p(max(reference turns−4,0))','log1p(reference self-occlusion H)','log1p(reference short turns)'],ordering=['m_all_B8L2','m_challenge_turn_n','m_all_log_time'],gates='all>=12 images/3 buildings; opportunity variance>1e-5, >=2 levels; positive time>=12 images/3 buildings and estimable response',embedding='robust median/(p85-p15), clip ±3, PCA<=2/domain, equal-domain RMS normalization; Ward one tree',difficulty='formal picture difficulty is not a JOINT clustering input; current label reuse verified numerically',warning='C1...Ck are per-fold training Q-center ranks. ALL role names and K3/K4 splits are not fixed identities across folds'),
    }, analysis=dict(ALL='roster and training description only',LOBO='join worker_id and target building to heldout_building',unit='object then worker-target; class means within the same legal target; target differences equally within image; images equally within building; report both image- and building-equal summaries',time='positive source_active_time_seconds only, comparisons stratified by origin/time_source; other-target time denotes original task record and is not space-specific labor',scope='ordinary Manual primary main; other targets separate; Semi cross-mode separate; no doorway or special-range expansion',missing='unscored or unknown-class results remain missing, never zero; metric-specific finite support',no_new_experiment=True))
    (OUT/'CURRENT_METHOD_CONTRACT.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest=[]
    for role,p in INPUTS.items():
        b=(ROOT/p).read_bytes()
        manifest.append(dict(role=role,path=p,commit=HEAD,bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),git_blob_sha1=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()))
    save(pd.DataFrame(manifest),'INPUT_MANIFEST.csv')
    ac=read('ac_frozen_labels')
    ac=ac[ac.method.isin(METHODS)].copy()
    ac['class_id']=ac.class_id.fillna('unknown')
    join_keys=['method','heldout_building','worker_id']
    aj=ac[join_keys+['class_id','known']].merge(labels[join_keys+['class_id','known']],on=join_keys,suffixes=('_AC','_current'),validate='one_to_one')
    aj['class_id_changed']=aj.class_id_AC.ne(aj.class_id_current)
    aj['known_changed']=aj.known_AC.ne(aj.known_current)
    save(aj,'AC_CURRENT_LABEL_CORRESPONDENCE.csv.gz')
    acsum=aj.groupby(['method','heldout_building']).agg(workers=('worker_id','size'),class_id_changed=('class_id_changed','sum'),known_changed=('known_changed','sum')).reset_index()
    save(acsum,'AC_CURRENT_LABEL_CHECK_BY_FOLD.csv')
    print(json.dumps({k:v for k,v in checks.items() if k not in ['OPPJOINT_unchanged_columns','target_ALL_sizes']},ensure_ascii=False))

if __name__ == '__main__':
    main()
