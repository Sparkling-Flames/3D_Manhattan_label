"""新增作答的同房更新：同资格B8L2/D10、实际共同人员和独立时间来源。"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..data_prep.consolidate_research_input import load_current_bundle
from .descriptive_inventory_20261015 import load_inventory
from .descriptive_same_room_20261015 import _summary
from .quality_b8l2_d10_20261017 import model_parameters
from .same_room_b8l2_20261016 import ROOT, metadata, pair_tables, aggregate_pairs, matched_controls
from .same_room_quality_curves_20261015 import save
from .same_room_usage_adoption_20261016 import qt_observations
from .same_room_working_analysis_20261016 import curve_coverage, OUT as OLD
from .scope_quality_scoring_20261016 import scoring_engine

SHARED=ROOT/'research/quality/quality_b8l2_d10_20261017'
RELATIONS=ROOT/'research/same_room/relation_adoption_20261016'
OUT=ROOT/'research/same_room/same_room_update_20261017'
CURRENT_WORKERS=ROOT/'research/workers/worker_b8l2_d10_20261017'
CURRENT_FUSION=ROOT/'research/fusion/wall_consensus_d10_20261017'
METRICS=['B8L2','D10','IoU3D100','source_time_seconds','target_matched_time_seconds']


def prepare_panel(records):
    if not records.object_id.is_unique:
        raise ValueError('duplicate object identity')
    quality=records.quality_usable
    if records.loc[quality,['B8L2','D10']].isna().any().any():
        raise ValueError('both metrics require the same qualified records')
    if records.loc[~quality,['B8L2','D10']].notna().any().any() or (records.is_oos & quality).any():
        raise ValueError('excluded or OOS records cannot supply quality')
    result=records[records.pool_analysis_eligible].copy()
    if result.duplicated(['image_id','worker_id','condition']).any():
        raise ValueError('duplicate effective image/person/condition')
    result['source_time_seconds']=result.source_active_time_seconds
    valid=result.source_time_seconds.notna()
    if not (result.loc[valid,'time_status'].eq('usable').all() and
        result.loc[valid,'source_time_seconds'].gt(0).all() and
        result.loc[valid,'time_source_file'].notna().all() and
        ~result.loc[valid,'time_source'].str.contains('lead_time',na=False).any()):
        raise ValueError('invalid source time provenance or seconds')
    if (result.target_matched_time_seconds.notna() &
        result.target_time_interpretation.eq('task_worker_total_not_target_specific')).any():
        raise ValueError('task-worker total cannot become target time')
    return result


def metric_sensitivity(pairs):
    keys=['image_a','image_b','condition']
    fields=['paired_workers','n_paired','absolute_mean_gap','mean_absolute_person_delta']
    a=pairs[pairs.metric.eq('B8L2')][keys+fields]
    b=pairs[pairs.metric.eq('D10')][keys+fields]
    joined=a.merge(b,on=keys,suffixes=('_B8L2','_D10'),how='outer',indicator=True,validate='one_to_one')
    if not joined._merge.eq('both').all() or not joined.n_paired_B8L2.eq(joined.n_paired_D10).all() or not (
        joined.paired_workers_B8L2.fillna('').eq(joined.paired_workers_D10.fillna('')).all()):
        raise ValueError('metric comparison requires identical workers and eligibility')
    joined['gap_change_D10_minus_B8L2']=joined.absolute_mean_gap_D10-joined.absolute_mean_gap_B8L2
    return joined


def worker_groups(records,relations,out):
    memberships=set()
    for (a,b),r in relations.items():
        if r['physical_adopted']:
            group='|'.join(r['user_group_ids'])
            for image in [a,b]: memberships.add((image,group,r['analysis_layer']))
    links=pd.DataFrame(sorted(memberships),columns=['image_id','user_group_ids','relation_layer'])
    detailed=records.merge(links,on='image_id',validate='many_to_many')
    fields=['object_id','worker_id','image_id','image_code','condition','reference_id','difficulty_class',
        'user_group_ids','relation_layer','new_batch','quality_use']+METRICS
    save(out,'worker_group_image_records.csv',detailed[fields])
    rows=[]
    keys=['worker_id','condition','user_group_ids','relation_layer','difficulty_class']
    for names,g in detailed.groupby(keys,dropna=False):
        row=dict(zip(keys,names),records=len(g),images=g.image_id.nunique(),new_records=int(g.new_batch.sum()))
        for metric in METRICS:
            row.update({metric+'_'+k:v for k,v in _summary(g[metric].dropna().tolist()).items()})
        rows.append(row)
    save(out,'worker_group_difficulty.csv',pd.DataFrame(rows))


def run(shared=SHARED,out=OUT):
    shared,out=Path(shared),Path(out);out.mkdir(parents=True,exist_ok=True)
    cross=json.loads((shared/'CROSS_MODULE_INPUTS.json').read_text(encoding='utf-8'))
    bundle=load_current_bundle(ROOT/cross['input_manifest'])
    inventory=pd.DataFrame(load_inventory(bundle)).set_index('object_id')
    all_records=pd.read_csv(ROOT/cross['full_inventory_with_metric_eligibility'])
    assert set(all_records.object_id)==set(inventory.index)
    assert len(all_records)==cross['counts']['inventory']
    assert int(all_records.quality_usable.sum())==cross['counts']['quality_rows']
    assert all_records.snapshot_version.eq(cross['version']).all()
    source=inventory.loc[all_records.object_id]
    for key in ['image_id','worker_id','condition','time_status','time_source','time_source_file']:
        assert all_records[key].fillna('').tolist()==source[key].fillna('').tolist(),key
    assert np.allclose(all_records.source_active_time_seconds,source.active_time_seconds,equal_nan=True,atol=1e-10,rtol=0)
    record=prepare_panel(all_records)
    qualified=record[record.quality_usable]
    bindings=pd.read_csv(ROOT/cross['all_pre_score_bindings']).set_index('object_id').loc[qualified.object_id]
    assert bindings.target_binding_unique.all() and bindings.chosen_target_id.tolist()==qualified.reference_id.tolist()
    assert qualified.rescore_target_id.eq(qualified.reference_id).all()
    assert not bindings[['annotation_modified','annotation_cropped','quality_used_for_binding']].any().any()
    ref_path=ROOT/cross['reference_catalog'] if 'reference_catalog' in cross else shared/'reference_catalog.json'
    refs={r['target_id']:r for r in json.loads(ref_path.read_text(encoding='utf-8'))}
    assert all(refs[r]['full_reference_available'] for r in qualified.reference_id)
    # Keep one declared reference per image/condition in this pooled comparison; do not silently mix target scopes.
    if qualified.groupby(['image_id','condition']).reference_id.nunique().gt(1).any():
        raise ValueError('multiple reference targets require separate paired comparison panels')
    frozen=ROOT/'research/statistics/b8l2_shared_v6_20261016/inputs'
    with scoring_engine(frozen/'measurement_engine.zip',frozen/'working_models.py') as (_,models):
        inputs=[qualified[k].to_numpy() for k in ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']]
        for name,params in zip(['B8L2','D10'],model_parameters(models)):
            assert asdict(params)==cross['parameters'][name]
            assert np.allclose(models.score(*inputs,params=params),qualified[name],atol=1e-8,rtol=0),name
    relation_manifest=json.loads((RELATIONS/'CROSS_MODULE_RELATIONS.json').read_text(encoding='utf-8'))
    relation_rows=json.loads((ROOT/relation_manifest['relations']).read_text(encoding='utf-8'))
    assert relation_manifest['frozen'] and all(r['adoption_version']==relation_manifest['version'] for r in relation_rows)
    relations={(r['image_a'],r['image_b']):r for r in relation_rows}
    new_ids=set(all_records.loc[all_records.new_batch,'image_id'])
    affected=[dict(r) for (a,b),r in relations.items() if {a,b}&new_ids]
    save(out,'affected_relations.json',affected)
    save(out,'affected_relation_coverage.csv',pd.DataFrame([dict(image_a=r['image_a'],image_b=r['image_b'],
        user_group_ids='|'.join(r['user_group_ids']),layer=r['analysis_layer']) for r in affected]))
    columns=['object_id','image_id','image_code','worker_id','building_id','condition','reference_id','rescore_target_id',
        'reference_version','current_target_id','difficulty_class','target_role','pool_source_workers',
        'pool_analysis_eligible','ordinary_difficulty_eligible','quality_usable','quality_use','is_oos','is_doorway',
        'new_batch','binding_status','target_binding_unique','calculation_status','input_version','snapshot_version',
        'B8L2_version','D10_version','time_status','time_source','time_source_file','time_rule_version',
        'time_stage','time_binding','target_time_interpretation']+METRICS
    save(out,'frozen_analysis_records.csv',record[columns])
    images=metadata(bundle)
    pairs,people,coverage=pair_tables(record,relations,images,METRICS)
    save(out,'current_pairs.csv',pairs);save(out,'current_people.csv',people);save(out,'relation_coverage.csv',coverage)
    save(out,'by_building.csv',aggregate_pairs(pairs))
    save(out,'metric_sensitivity.csv',metric_sensitivity(pairs))
    person_keys=['image_a','image_b','condition','worker_id']
    joint=people[people.metric.eq('B8L2')].drop(columns='metric').rename(columns={'value_a':'B8L2_a','value_b':'B8L2_b'})
    for metric in ['D10','source_time_seconds','target_matched_time_seconds']:
        values=people[people.metric.eq(metric)][person_keys+['value_a','value_b']].rename(
            columns={'value_a':metric+'_a','value_b':metric+'_b'})
        joint=joint.merge(values,on=person_keys,how='left',validate='one_to_one')
    joint['quality_source_time_joint']=joint[['source_time_seconds_a','source_time_seconds_b']].notna().all(axis=1)
    joint['quality_target_time_joint']=joint[['target_matched_time_seconds_a','target_matched_time_seconds_b']].notna().all(axis=1)
    save(out,'joint_quality_time_people.csv',joint)
    old_records=pd.read_csv(OLD/'frozen_analysis_records.csv')
    old_quality=old_records[old_records.B8L2.notna()]
    retained=qualified.set_index('object_id').loc[old_quality.object_id]
    assert retained.reference_id.tolist()==old_quality.reference_id.tolist()
    assert np.allclose(retained.B8L2,old_quality.B8L2,atol=1e-8,rtol=0)
    source_bridge=old_records[['object_id','source_time_seconds','target_matched_time_seconds']].merge(
        record[['object_id','image_code','new_batch','source_time_seconds','target_matched_time_seconds']],
        on='object_id',how='outer',suffixes=('_old','_new'),indicator=True,validate='one_to_one')
    full_index=all_records.set_index('object_id')
    source_bridge['image_code']=source_bridge.object_id.map(full_index.image_code)
    source_bridge['current_source_exclusion_reasons']=source_bridge.object_id.map(full_index.pool_analysis_exclusion_reasons)
    save(out,'source_cohort_bridge.csv',source_bridge)
    keys=['image_a','image_b','condition','metric']
    fields=['n_paired','paired_workers','absolute_mean_gap','mean_absolute_person_delta']
    old_pairs=pd.read_csv(OLD/'current_pairs.csv');old_pairs=old_pairs[old_pairs.metric.isin(METRICS)]
    bridge=old_pairs[keys+fields].merge(pairs[keys+fields],on=keys,how='outer',suffixes=('_old','_new'),indicator=True,validate='one_to_one')
    bridge['same_worker_set']=bridge.paired_workers_old.fillna('').eq(bridge.paired_workers_new.fillna(''))
    save(out,'old_new_pair_bridge.csv',bridge)
    old_positive=old_pairs[old_pairs.metric.eq('B8L2')&old_pairs.n_paired.gt(0)]
    new_positive=pairs[pairs.metric.eq('B8L2')&pairs.n_paired.gt(0)]
    save(out,'quality_pair_membership_bridge.csv',old_positive.merge(new_positive,on=['image_a','image_b','condition'],
        how='outer',suffixes=('_old','_new'),indicator=True,validate='one_to_one'))
    decomposed=[]
    for panel,ids in [('previous_qualified_on_current_relations',set(old_quality.object_id)),
        ('current_qualified_old_inventory_only',set(qualified.loc[~qualified.new_batch,'object_id'])),
        ('current_all_qualified',set(qualified.object_id))]:
        selected=people[people.metric.isin(['B8L2','D10'])&people.object_id_a.isin(ids)&people.object_id_b.isin(ids)]
        n=selected.groupby(['metric','condition','confirmation','image_a','image_b']).worker_id.nunique().reset_index(name='n_common')
        for names,g in n.groupby(['metric','condition','confirmation']):
            decomposed.append(dict(panel=panel,metric=names[0],condition=names[1],confirmation=names[2],
                pairs=len(g),common_ge4=int(g.n_common.ge(4).sum())))
    decomposition=pd.DataFrame(decomposed)
    baseline=decomposition[decomposition.panel.eq('previous_qualified_on_current_relations')&decomposition.metric.eq('B8L2')]
    assert baseline.pairs.sum()==len(old_positive)
    save(out,'coverage_decomposition.csv',decomposition)
    controls=matched_controls(record,pairs,relations,comparable_label='user_classified_comparable')
    save(out,'matched_controls.csv',controls)
    control_keys=['source','target','condition']
    a=controls[controls.metric.eq('B8L2')];b=controls[controls.metric.eq('D10')]
    same=a.merge(b,on=control_keys,suffixes=('_B8L2','_D10'),validate='one_to_one',how='outer',indicator=True)
    assert same._merge.eq('both').all()
    for key in ['workers','control_image_ids']:
        assert same[key+'_B8L2'].fillna('').eq(same[key+'_D10'].fillna('')).all()
    save(out,'control_metric_sensitivity.csv',same)
    target=controls[controls.control_images.gt(0)].groupby(['building','condition','metric','target'],as_index=False).agg(
        source_error=('same_room_error','mean'),control_error=('one_control_expected_error','mean'))
    save(out,'controls_by_target.csv',target)
    save(out,'controls_by_building.csv',target.groupby(['building','condition','metric'],as_index=False).agg(
        targets=('target','size'),source_error=('source_error','mean'),control_error=('control_error','mean')))
    worker_groups(record,relations,out)
    worker_inputs=json.loads((CURRENT_WORKERS/'INPUTS.json').read_text(encoding='utf-8'))
    worker_contract=json.loads((CURRENT_WORKERS/'FIELD_CONTRACT.json').read_text(encoding='utf-8'))
    assert worker_inputs['shared_manifest']['version']==cross['version']
    training=pd.read_csv(CURRENT_WORKERS/'quality_panel.csv')
    checked=qualified.set_index('object_id').loc[training.object_id]
    assert checked.reference_id.tolist()==training.reference_id.tolist()
    assert np.allclose(checked[['B8L2','D10']],training[['B8L2','D10']],atol=1e-8,rtol=0)
    profiles=pd.read_csv(CURRENT_WORKERS/'fold_profiles.csv')
    qt=qt_observations(people,profiles,out,quality_panel='current',quality_metrics=('B8L2','D10'))
    save(out,'Q_T_INPUTS.json',dict(inputs=worker_inputs,contract=worker_contract,training_records_checked=len(training)))
    fusion_inputs=json.loads((CURRENT_FUSION/'INPUT_BRIDGE.json').read_text(encoding='utf-8'))
    assert fusion_inputs['shared_contract']['version']==cross['version']
    curve=curve_coverage(relation_rows,scores_path=CURRENT_FUSION/'subset_scores.csv')
    save(out,'actual_18_curve_relation_coverage.csv',curve)
    save(out,'CURVE_INPUTS.json',fusion_inputs)
    fusion=json.loads((ROOT/'research/fusion/wall_consensus_b8l2_20261016/input_snapshot.json').read_text(encoding='utf-8'))
    assert not new_ids&{r['image_id'] for r in fusion['images']}
    counts=pairs[pairs.n_paired.gt(0)].groupby(['metric','condition','confirmation']).n_paired.agg(
        pairs='size',common_ge4=lambda s:int((s>=4).sum())).reset_index()
    save(out,'pair_counts.csv',counts)
    group=pairs[pairs.n_paired.ge(4)].groupby(['metric','condition','confirmation','user_group_ids'],as_index=False).agg(
        pairs=('image_a','size'),mean_gap=('absolute_mean_gap','mean'),person_gap=('mean_absolute_person_delta','mean'))
    save(out,'by_user_group_ge4.csv',group)
    summary=dict(version='same_room_update_20261017_v1',stage='analysis_completed',common_score_version=cross['version'],
        input_manifest=cross['input_manifest'],relation_version=relation_manifest['version'],
        input_revision=bundle['manifest']['effective_input_revision'],
        inventory=len(all_records),inventory_images=all_records.image_id.nunique(),source_records=len(record),
        quality_records=len(qualified),new_inventory=int(all_records.new_batch.sum()),new_quality=int(qualified.new_batch.sum()),
        quality_images=int(qualified.image_id.nunique()),new_quality_images=int(qualified.loc[qualified.new_batch,'image_id'].nunique()),
        old_quality_retained=len(old_quality),old_inventory_new_quality=int((~qualified.new_batch).sum())-len(old_quality),
        old_source_records_removed=int(source_bridge._merge.eq('left_only').sum()),
        new_images=len(new_ids),affected_relation_edges=len(affected),
        source_time_records=int(record.source_time_seconds.notna().sum()),source_time_seconds=float(record.source_time_seconds.sum()),
        new_source_seconds=float(record.loc[record.new_batch,'source_time_seconds'].sum()),
        target_time_records=int(record.target_matched_time_seconds.notna().sum()),new_target_time_records=int(record.loc[record.new_batch,'target_matched_time_seconds'].notna().sum()),
        pair_counts=counts.to_dict('records'),same_metric_eligibility=True,old_quality_references_and_B8L2_preserved=True,
        Q_T='current personnel-module reviewed ordinary B8L2/D10 Q and source/target T outside-building profiles',
        worker_profile_records=len(training),worker_version=worker_contract['version'],
        qt_ge4=qt[qt.n_supported.ge(4)].groupby(['metric','confirmation']).size().reset_index(name='pairs').to_dict('records'),
        fusion_new_image_overlap=0,curve_physical_pairs=int(curve.physical_adopted.sum()),
        curve_comparable_quality=int(curve.scope_comparable_quality_curve.sum()),new_fusion_experiment=False)
    save(out,'SUMMARY.json',summary)
    save(out,'INPUTS.json',dict(shared=cross,relation=relation_manifest,old_comparison=OLD.relative_to(ROOT).as_posix()))
    save(out,'FIELD_CONTRACT.json',dict(version=summary['version'],
        table_columns={p.name:list(pd.read_csv(p,nrows=0).columns) for p in out.glob('*.csv')},
        metrics='B8L2 primary/D10 direction-scale sensitivity, identical records/references/workers/control budget; D10 is not A10',
        reference='one actual bound reference per image/condition for pooled quality; no local binding or score-selected target',
        time='source active seconds include admitted task-worker totals; target time retained only with existing audit, no lead_time/zero fill',
        groups='versioned overlapping direct user groups; worker/group/difficulty summaries are descriptive, not ability ranks',
        Q_T='personnel-module current B8L2/D10 ordinary Q and source/target T outside-building profiles; no local training/admission/classes',
        curves='only actual saved member subsets; no overlap of new images and old18; no fabricated geometry/curves'))
    assert json.loads((shared/'CROSS_MODULE_INPUTS.json').read_text(encoding='utf-8'))==cross,'shared inputs changed during analysis'
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shared',type=Path,default=SHARED);parser.add_argument('--out',type=Path,default=OUT)
    args=parser.parse_args();run(args.shared,args.out)
