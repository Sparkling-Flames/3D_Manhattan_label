"""新版完整输入的B8L2/D10共同评分；沿用旧测量和资格，实算新增可绑定作答。"""
import json
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path

import pandas as pd
from shapely.geometry import Polygon

from ..data_prep.consolidate_research_input import load_current_bundle
from .current_annotation_context_20261017 import load_current_context
from .descriptive_inventory_20261015 import load_inventory
from .scope_quality_binding_20261016 import build_affected_records
from .scope_quality_scoring_20261016 import scoring_engine, score_task
from .b8l2_calculation_status_20261016 import inspect_geometry
from .b8l2_usage_snapshot_20261016 import usage_policy
from .b8l2_usage_coverage_20261016 import scene_flags, build_usage_coverage
from .descriptive_statistics_current_20261015 import QUALITY_METRICS

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'research/quality/quality_b8l2_d10_20261017'
SOURCE = ROOT/'research/statistics/b8l2_shared_v6_20261016'
VERSION = 'quality_b8l2_d10_20261017_v2'
INPUT = 'analysis_results/research_input_20261017/manifest.json'
COMPONENTS = ('iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter')
METRICS = QUALITY_METRICS + ['D10']


def model_parameters(models):
    b = models.MODELS['B8L2']
    assert (b.version, b.direction_scale_deg, b.pooling_order) == ('WQ-B8L2-20261015', 8., 2.)
    return b, replace(b, version='B8L2-D10-20261016', direction_scale_deg=10.)


def dual_scores(metrics, models):
    values = [metrics[k] for k in COMPONENTS]
    return {name: float(models.score(*values, parameter))
            for name, parameter in zip(('B8L2', 'D10'), model_parameters(models))}


def choose_binding(fresh, old):
    result = dict(fresh)
    # 旧用途已清除的目标包含人工/留出限制，不能被唯一候选推断重新放行。
    unresolved = {'pending_multiple_admitted_spaces', 'pending_manual_family_not_unique'}
    if old is not None and not (old['binding_status'] in unresolved and not old['chosen_target_id']):
        result.update(chosen_target_id=old['chosen_target_id'] or '', binding_status=old['binding_status'])
    return result


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def csv(path, records):
    frame = records.copy() if isinstance(records, pd.DataFrame) else pd.DataFrame(records)
    for column in frame:
        if frame[column].map(lambda x: isinstance(x, (dict, list))).any():
            frame[column] = frame[column].map(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (dict, list)) else x)
    frame.to_csv(path, index=False, encoding='utf-8-sig')


def typed(row):
    return {k: True if v == 'True' else False if v == 'False' else v for k, v in row.items()}


def run():
    bundle = load_current_bundle(ROOT/INPUT)
    context = load_current_context(bundle)
    admission = {r['object_id']: r for r in bundle['batch_admission']['records']}
    assert bundle['manifest']['effective_input_revision'] == 'annotation_batch_98_20261017_v1'
    old = {r['object_id']: typed(r) for r in context['quality_records'] if r['object_id'] not in admission}
    old_bindings = {r['object_id']: r for r in context['binding_records'] if r['object_id'] in old}
    objects = {o['object_id']: o for o in bundle['data']['objects'] if o['object_kind'] == 'annotation'}
    frozen = read(SOURCE/'FROZEN_INPUTS.json')['bundle']
    frozen_objects = {o['object_id']: o for o in frozen['data']['objects'] if o['object_kind'] == 'annotation'}
    assert set(frozen_objects) == set(old)
    for oid, obj in frozen_objects.items():
        for key in ('image_id', 'worker_id', 'condition', 'points_1024x512', 'ordered_source_pair_indices'):
            assert obj.get(key) == objects[oid].get(key), (oid, key, 'frozen measurement input changed')
    refs = {r['target_id']: r for r in context['reference_catalog']}
    for r in read(SOURCE/'inputs/reference_catalog.json'):
        assert refs[r['target_id']] == r
    difficulty = {r['image_id']: r for r in context['difficulty_records']}
    inventory = {r['object_id']: r for r in load_inventory(bundle)}
    routing = build_affected_records(bundle, context['difficulty_records'], context['reference_catalog'],
                                    include_all_images=True, resolve_multiple_spaces=True)
    rows, bindings, measured, geometry_audit, changes, binding_changes = [], [], [], [], [], []
    with scoring_engine(SOURCE/'inputs/measurement_engine.zip', SOURCE/'inputs/working_models.py') as (engine, models):
        parameters = {k: asdict(v) for k, v in zip(('B8L2','D10'), model_parameters(models))}
        for fresh in routing['affected_records']:
            oid = fresh['object_id']; obj = objects[oid]; prior = old.get(oid)
            d = difficulty[obj['image_id']]
            choice = choose_binding(fresh, old_bindings.get(oid)); ref = refs.get(choice['chosen_target_id'])
            previous_target = old_bindings.get(oid, {}).get('chosen_target_id', '')
            binding_changed = bool(prior and choice['chosen_target_id'] != previous_target)
            row = dict(prior) if prior else dict(inventory[oid], inventory_record_id=oid)
            for k, v in fresh.items():
                if k.startswith('pool_') or k in ('ordinary_difficulty_eligible', 'duplicate_effective_worker'):
                    row[k] = v
            row.update(difficulty_class=d['current_class'], difficulty_analysis_eligible=d['difficulty_analysis_eligible'],
                scene=d['scene'], doorway_status=d['doorway_status'],
                oos_subtype=d['oos_subtype'], gt_error_excluded=d['gt_error_excluded'],
                difficulty_analysis_exclusion=d['difficulty_analysis_exclusion'], current_target_id=d['target_version'],
                target_role=d['selected']['role'], input_version=bundle['manifest']['effective_input_revision'],
                snapshot_version=VERSION, usage_version=VERSION, B8L2_version=parameters['B8L2']['version'],
                D10_version=parameters['D10']['version'], primary_metric='B8L2',
                new_batch=oid in admission, source_scope_response=admission.get(oid, {}).get('worker_scope_response'),
                training_admission_status='requires_module_review' if oid in admission else 'retain_existing_module_rules')
            row['analysis_layer'] = ('ordinary_current' if row['ordinary_difficulty_eligible'] else
                'special_or_pending_separate' if row['pool_analysis_eligible'] else 'held_inventory_only')
            row['use_panel'] = row['analysis_layer']
            row['source_active_time_seconds'] = inventory[oid]['active_time_seconds']
            row['active_time_seconds'] = inventory[oid]['active_time_seconds'] if row['pool_analysis_eligible'] else None
            if not row['pool_analysis_eligible']:row['target_matched_time_seconds'] = None
            scene = scene_flags(row)
            score = None
            if prior and not binding_changed:
                state = prior['full_score_state']; calculation = prior['calculation_status']
                geometry = dict(full_input_available=prior['full_input_available'],
                    floor_input_available=prior['floor_input_available'])
                if state == 'computed':
                    assert ref and prior['rescore_target_id'] == ref['target_id']
                    assert prior['rescore_reference_version'] == ref['reference_version']
                    score = {m: float(prior['diagnostic_'+m]) for m in QUALITY_METRICS}
                    computed = dual_scores(score, models)
                    assert abs(computed['B8L2']-score['B8L2']) < 1e-8, oid
                    score.update(computed)
                row['measurement_source'] = 'frozen_20261016_same_geometry_reference'
            else:
                geometry = inspect_geometry(obj, engine); geometry_audit.append(geometry)
                initial = usage_policy(row,obj,choice,ref,geometry,scene,full_score_state='not_run')
                state = ('pending_target' if not initial['target_binding_unique'] else
                    'input_uncomputable' if not geometry['full_input_available'] else
                    'pending_reference' if not ref or not ref['full_reference_available'] else 'not_run')
                if state == 'not_run':
                    score = score_task(dict(object_id=oid,image_id=obj['image_id'],worker_id=obj['worker_id'],
                        condition=obj['condition'],current_target_id=ref['target_id'],reference_version=ref['reference_version'],
                        annotation_points=obj['points_1024x512'],reference_points=ref['points_1024x512']),engine,models)
                    state = 'computed' if score['score_status'] == 'complete' else 'measurement_failed'
                    if state == 'computed': score.update(dual_scores(score,models))
                    score['measurement_population'] = 'new_batch' if oid in admission else 'old_binding_gap'
                    measured.append(score)
                calculation = 'full_computed' if state == 'computed' else state
                floor_iou = score['iou_2d'] if state == 'computed' else None
                if state != 'computed' and initial['target_binding_unique'] and geometry['floor_input_available'] and ref:
                    valid_floor = engine.valid.validate_footprint(ref['floor_xz_h'], role='reference')
                    if valid_floor['available']:
                        a, b = Polygon(geometry['floor_xz_h']), Polygon(ref['floor_xz_h'])
                        floor_iou = a.intersection(b).area/a.union(b).area
                        calculation = 'floor_only_computed'
                row.update(source_active_time_seconds=inventory[oid]['active_time_seconds'],
                    target_matched_time_seconds=None, target_time_interpretation='task_worker_total_not_target_specific',
                    task_worker_active_seconds=admission.get(oid, {}).get('task_worker_active_seconds'),
                    input_geometry_status=geometry['input_geometry_status'], input_geometry_reasons=geometry['reasons'],
                    measurement_reasons=score['reasons'] if score else [],
                    diagnostic_floor_iou=floor_iou,
                    measurement_source='new_batch_fixed_measurement' if oid in admission else 'old_binding_gap_fixed_measurement')
            policy = usage_policy(row,obj,choice,ref,geometry,scene,full_score_state=state)
            row.update(scene, **policy, full_input_available=geometry['full_input_available'],
                floor_input_available=geometry['floor_input_available'], full_score_state=state,
                calculation_status=calculation, reference_full_available=bool(ref and ref['full_reference_available']),
                reference_id=ref['target_id'] if ref else '', reference_version=ref['reference_version'] if ref else '',
                rescore_target_id=choice['chosen_target_id'], binding_status=choice['binding_status'],
                rescore_status='complete' if state=='computed' else state,
                rescore_reference_version=ref['reference_version'] if ref else '',
                score_version=json.dumps({k:v['version'] for k,v in parameters.items()}),
                current_quality_eligible=policy['quality_usable'])
            row['quality_use'] = ('not_qualified' if not policy['quality_usable'] else 'doorway_quality' if scene['is_doorway']
                else 'ordinary_primary' if row['ordinary_difficulty_eligible'] else 'special_conditional_only')
            for m in METRICS:
                value = score[m] if state == 'computed' else None
                row['diagnostic_'+m] = value
                row[m] = value if policy['quality_usable'] else None
            choice.update(target_binding_unique=policy['target_binding_unique'])
            bindings.append(choice); rows.append(row)
            binding_changes.append(dict(object_id=oid, image_id=obj['image_id'], image_code=obj['image_code'],
                new_batch=oid in admission, previous_target_id=previous_target,
                chosen_target_id=choice['chosen_target_id'], binding_changed=binding_changed,
                previous_binding_status=old_bindings.get(oid, {}).get('binding_status', ''),
                binding_status=choice['binding_status'], target_binding_unique=policy['target_binding_unique'],
                local_routing_evidence=choice.get('local_routing_evidence'), quality_usable=policy['quality_usable'],
                calculation_status=calculation, quality_exclusion_reasons=policy['quality_exclusion_reasons']))
            changes.append(dict(object_id=oid,image_id=obj['image_id'],image_code=obj['image_code'],
                change='added' if policy['quality_usable'] and not (prior and prior['quality_usable']) else
                    'removed' if prior and prior['quality_usable'] and not policy['quality_usable'] else
                    'retained' if policy['quality_usable'] else 'outside_both',
                new_batch=oid in admission, previous_B8L2=float(prior['B8L2']) if prior and prior['quality_usable'] else None,
                B8L2=row['B8L2'],D10=row['D10'],reasons=policy['quality_exclusion_reasons']))
    frame = pd.DataFrame(rows).drop(columns=[k for k in rows[0] if k.startswith('hit_') or k=='primary_reason'])
    for m in METRICS:
        frame[m] = pd.to_numeric(frame[m]); frame['diagnostic_'+m] = pd.to_numeric(frame['diagnostic_'+m])
    coverage = build_usage_coverage(frame)
    qualified = frame[frame.quality_usable].copy()
    assert qualified[['B8L2','D10']].notna().all().all()
    assert frame.loc[~frame.quality_usable,['B8L2','D10']].isna().all().all()
    assert not qualified.is_oos.any()
    OUT.mkdir(parents=True,exist_ok=True)
    for filename, data in [('shared_records.csv',frame),('quality_records.csv',qualified),
        ('shared_bindings.csv',bindings),('source_pools.csv',routing['source_pools']),('member_changes.csv',changes),
        ('new_batch_records.csv',frame[frame.new_batch]),('new_measurements.csv',measured),
        ('binding_changes.csv',binding_changes)]:csv(OUT/filename,data)
    csv(OUT/'pending_new_targets.csv',frame[frame.new_batch & ~frame.target_binding_unique][[
        'object_id','image_id','image_code','worker_id','condition','binding_status','source_scope_response']])
    for name, data in coverage.items():csv(OUT/(name+'.csv'),data)
    for name,keys in [('image_quality_summary',['image_id','image_code','difficulty_class','condition','quality_use']),
                      ('worker_quality_summary',['worker_id','condition','quality_use'])]:
        table=qualified.groupby(keys,dropna=False).agg(n=('object_id','size'),B8L2_mean=('B8L2','mean'),
            D10_mean=('D10','mean'),B8L2_median=('B8L2','median'),D10_median=('D10','median')).reset_index()
        csv(OUT/(name+'.csv'),table)
    write(OUT/'MODEL_PARAMETERS.json',parameters)
    write(OUT/'reference_catalog.json',context['reference_catalog'])
    write(OUT/'difficulty_records.json',context['difficulty_records'])
    write(OUT/'new_geometry_audit.json',geometry_audit)
    checks=dict(version=VERSION,input_manifest=INPUT,inventory=len(frame),quality_rows=len(qualified),
        new_batch=len(admission),new_complete=sum(s['score_status']=='complete' and s['object_id'] in admission for s in measured),
        old_binding_gap_measured=sum(s['object_id'] not in admission for s in measured),
        old_binding_changes=sum(r['binding_changed'] for r in binding_changes),
        new_quality_rows=int(qualified.new_batch.sum()),new_binding_status=dict(Counter(r['binding_status'] for r in bindings if r['object_id'] in admission)),
        quality_use=qualified.quality_use.value_counts().to_dict(),calculation_status=frame.calculation_status.value_counts().to_dict(),
        membership_changes=dict(Counter(r['change'] for r in changes)),
        old_inputs_and_references_verified=True,old_B8L2_recomposition_verified=True,
        new_task_worker_seconds=sum(r['task_worker_active_seconds'] for r in admission.values()),
        main_formula_changed=False,old_snapshots_modified=False)
    checks['routing_version']='current_reference_local_router_20261017_v1'
    checks['pre_routing_snapshot']='research/quality/quality_b8l2_d10_initial_20261017'
    write(OUT/'CHECKS.json',checks)
    write(OUT/'CROSS_MODULE_INPUTS.json',dict(version=VERSION,input_manifest=INPUT,primary_metric='B8L2',
        parallel_metric='D10',parameters=parameters,
        recommended_qualified_scores=(OUT/'quality_records.csv').relative_to(ROOT).as_posix(),
        full_inventory_with_metric_eligibility=(OUT/'shared_records.csv').relative_to(ROOT).as_posix(),
        all_pre_score_bindings=(OUT/'shared_bindings.csv').relative_to(ROOT).as_posix(),
        reference_catalog=(OUT/'reference_catalog.json').relative_to(ROOT).as_posix(),
        difficulty_records=(OUT/'difficulty_records.json').relative_to(ROOT).as_posix(),
        source_pools=(OUT/'source_pools.csv').relative_to(ROOT).as_posix(),
        pre_score_routing=dict(version='current_reference_local_router_20261017_v1',
            implementation='research/quality_pro_joint_archive_20261013/source/routing/router.py',
            parameters='research/quality_pro_joint_archive_20261013/source/routing/config.json',
            evidence=(OUT/'binding_changes.csv').relative_to(ROOT).as_posix(),
            uncertainty_is_probability=False),
        current_relation_adoption_manifest='research/same_room/relation_adoption_20261016/CROSS_MODULE_RELATIONS.json',
        rules=dict(OOS='diagnostic_only',new_worker_training='module_admission_review_required',
            time='source task-worker seconds; no target-time fabrication',pending_targets='no score-selected reference'),counts=checks))
    print(json.dumps(checks,ensure_ascii=False),flush=True)


if __name__=='__main__':run()
