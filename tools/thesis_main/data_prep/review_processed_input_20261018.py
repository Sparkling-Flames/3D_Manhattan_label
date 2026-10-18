"""核查已处理点的继承并生成v1增量快照；不改原始导出和历史包。"""
import copy
import csv
import gzip
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from .consolidate_research_input import load_current_bundle, validate_bundle
from .apply_quality_review_20261010 import apply_data as replay_quality
from .apply_difficulty_orders_20261010 import apply_data as replay_orders
from ..analysis.apply_pairing_preprocessing_20260929 import raw_initial_points
from ..analysis.finalize_review_20260928 import read, dump
from ..analysis.final_review_summary_20260929 import geometry_status
from ..analysis.shared_x_reanalysis_20260922 import shared_x

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT/'analysis_results/research_input_20261017/manifest.json'
OUT = ROOT/'research/data/processed_input_review_20261018'
REVISION = 'confirmed_coordinate_repair_v1_20261018'
GEOMETRY_FIELDS = ('before_preprocessing_points', 'preprocessed_points', 'point_labels',
    'links_zero_based', 'points_1024x512', 'ordered_source_pair_indices', 'ordered_source_point_indices')


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                         for k, v in row.items()} for row in rows)


def point_map(obj):
    return dict(zip(obj['point_labels'], obj['before_preprocessing_points'] or []))


def audit_effective_edits(bundle):
    """原标签身份核查全部当前点，另纳入历史缺映射、撤销和未应用建议。"""
    path = ROOT/'research/point_review_109_received_20261009/history/history_confirmed_point_edits.csv'
    with path.open(encoding='utf-8-sig', newline='') as stream:
        historical = {r['canonical_object_id']: r for r in csv.DictReader(stream)}
    pairing = read(ROOT/'analysis_results/pairing_applied_20260929/evidence/completed_pairing.json')['records']
    overrides = read(ROOT/'analysis_results/review_final_20260928/effective_point_overrides.json')
    revoked = set(overrides['revoked_annotation_ids'])
    rows = []
    for obj in bundle['data']['objects']:
        if obj['object_kind'] != 'annotation': continue
        oid = obj['object_id']; raw = obj['original_export_points'] or []; effective = point_map(obj)
        evidence = obj.get('repair_evidence', [])
        evidence = evidence if isinstance(evidence,list) else [evidence]
        added = [k for k in effective if not re.fullmatch(r'p\d+',k)]
        removed = [f'p{i+1}' for i in range(len(raw)) if f'p{i+1}' not in effective] if effective else []
        moved = [dict(label=k,before=raw[int(k[1:])-1],after=p) for k,p in effective.items()
                 if re.fullmatch(r'p\d+',k) and raw[int(k[1:])-1] != p]
        if not (added or removed or moved or evidence or oid in historical or oid in revoked): continue
        history = historical.get(oid,{})
        status = ('historical_not_accepted_missing_effective_mapping' if not effective and history else
                  'revoked_deletion_original_points_restored' if oid in revoked else
                  'superseded_single_x_move_by_shared_x_policy' if oid=='5e3a87e01e8c7a68' else
                  'current_effective_edit_preserved' if added or removed or moved else
                  'proposal_not_applied' if any(e.get('status')=='proposed_not_applied' for e in evidence) else 'recorded_no_current_edit')
        if history and effective:
            expected_removed = [f'p{i}' for i in json.loads(history['deleted_original_points_1based'])]
            assert set(expected_removed)<=set(removed), (oid,'historical_deletion_reappeared')
        if oid in revoked: assert not added and not removed and not moved, oid
        rows.append(dict(object_id=oid,record_id=history.get('record_id',''),image_code=obj['image_code'],
            worker_id=obj['worker_id'],condition=obj['condition'],annotation_id=obj['source']['annotation'],
            status=status,raw_point_count=len(raw),effective_point_count=len(effective),
            removed_original_labels=removed,added_labels=added,coordinate_edits=moved,
            historical_removed_points_1based=history.get('deleted_original_points_1based',''),
            cleaning_disposition=obj['cleaning_disposition'],independent_vote_eligible=obj['independent_vote_eligible'],
            borrowed_point_provenance=obj.get('borrowed_point_provenance'),repair_evidence=evidence,
            pairing_receipt=pairing.get(oid),quality_review_provenance=obj.get('quality_review_provenance'),
            historical_crosscheck_source=path.relative_to(ROOT).as_posix() if history else '',
            limitation='历史未纳入记录缺有效点映射，不恢复资格' if not effective and history else
                '提议仍缺明确可执行点位或批准，不能自动补点' if status=='proposal_not_applied' else ''))
    write_csv(OUT/'effective_point_edits_current.csv',rows)
    gaps=[r for r in rows if r['status'] in ('historical_not_accepted_missing_effective_mapping','proposal_not_applied')]
    write_csv(OUT/'unapplied_or_historical_gaps.csv',gaps)
    return dict(effective_edit_audit_records=len(rows),effective_edit_status_counts=dict(Counter(r['status'] for r in rows)),
        historical_crosscheck_records=len(historical),history_crosscheck_applied_deletions_preserved=True)


def audit_history(bundle):
    old = {o['object_id']: o for o in read(ROOT/'analysis_results/shared_x_baseline_20260928/preprocessed_source.json')['objects']}
    paired = {o['object_id']: o for o in read(ROOT/'analysis_results/pairing_applied_20260929/preprocessed_source.json')['objects']}
    current = {o['object_id']: o for o in bundle['data']['objects']}
    rows = []
    for oid, obj in old.items():
        if obj['object_kind'] != 'annotation':
            continue
        a, b, c = point_map(obj), point_map(paired[oid]), point_map(current[oid])
        edits = [dict(label=k, before=a[k], after=b[k]) for k in a if k in b and a[k] != b[k]]
        removed, added = sorted(a.keys()-b.keys()), sorted(b.keys()-a.keys())
        repairs = obj.get('repair_evidence', [])
        if repairs or edits or removed or added:
            rows.append(dict(object_id=oid, image_code=obj['image_code'], worker_id=obj['worker_id'],
                historical_repair_evidence=repairs, labels_20260928=list(a), labels_20260929=list(b),
                labels_current=list(c), initialization_coordinate_changes=edits,
                initialization_removed=removed, initialization_added=added,
                later_coordinate_changes=[dict(label=k,before=b[k],after=c[k]) for k in b if k in c and b[k]!=c[k]],
                later_removed=sorted(b.keys()-c.keys()), later_added=sorted(c.keys()-b.keys())))
    # Replay all 14 accepted point-review receipts, including delete/undo/pair/order.
    update = read(ROOT/'analysis_results/research_input_20260929/quality_update_20261010.json')
    replayed = copy.deepcopy(bundle['data'])
    replayed.pop('quality_update_revision', None)
    replay_quality(replayed, update)
    byid = {o['object_id']: o for o in replayed['objects']}
    point_receipts = []
    for rid, receipt in update['accepted_records'].items():
        oid = receipt['identity']['canonical_object_id']
        assert all(byid[oid][k] == current[oid][k] for k in GEOMETRY_FIELDS), oid
        point_receipts.append(dict(record_id=rid, object_id=oid, image_code=current[oid]['image_code'],
            worker_id=current[oid]['worker_id'], operations=Counter(op['type'] for op in receipt['operations']),
            removed_labels=[p['label'] for p in receipt['points'] if p.get('deleted')],
            point_pair_order_replay_equal=True))
    order_replay = replay_orders(copy.deepcopy(bundle['data']))
    order_rows = []
    for obj in order_replay['objects']:
        if obj.get('order_review_provenance', {}).get('revision') == 'difficulty_orders_20261010_v1':
            assert all(obj[k] == current[obj['object_id']][k] for k in GEOMETRY_FIELDS)
            order_rows.append(dict(object_id=obj['object_id'], image_code=obj['image_code'], current_order_equal=True))
    write_csv(OUT/'historical_point_edits.csv', rows)
    write_csv(OUT/'point_review_20261010_replay.csv', point_receipts)
    write_csv(OUT/'order_review_20261010_replay.csv', order_rows)
    return dict(old_annotations_compared=3152, current_annotations=3222,
        historical_edit_or_proposal_records=len(rows), initialization_coordinate_records=sum(bool(r['initialization_coordinate_changes']) for r in rows),
        pairing_deleted_records=sum(bool(r['initialization_removed']) for r in rows),
        point_review_receipts_replayed=len(point_receipts), order_receipts_replayed=len(order_rows))


def apply_confirmed_repairs(bundle):
    affected = []
    for obj in bundle['data']['objects']:
        if obj['object_kind'] != 'annotation':
            continue
        evidence = obj.get('repair_evidence', [])
        evidence = evidence if isinstance(evidence, list) else [evidence]
        if not any(e.get('status') == 'applied' and e.get('changed_points') for e in evidence):
            continue
        points, _, notes = raw_initial_points(obj)
        if points == obj['before_preprocessing_points']:
            continue
        before = copy.deepcopy(obj)
        obj['before_preprocessing_points'] = points
        obj['preprocessed_points'] = shared_x(points, obj['links_zero_based']).tolist()
        obj['points_1024x512'] = [obj['preprocessed_points'][i] for i in obj['ordered_source_point_indices']]
        obj['geometry'] = geometry_status(obj, obj['ordered_source_pair_indices'])
        obj['processed_input_revision'] = REVISION
        obj['initialization_notes'] += notes
        if obj['ring_confirmed']:
            record = obj['order_record']
            binding = dict(id=obj['object_id'], points=obj['preprocessed_points'], labels=obj['point_labels'],
                           links=obj['links_zero_based'], preprocessing=obj['preprocessing'])
            record['binding'] = json.dumps(binding, ensure_ascii=False)
            record['coordinate_revision'] = REVISION
            bundle['final_orders']['records'][obj['object_id']] = copy.deepcopy(record)
        obj['final_review'].update(geometry_status=obj['geometry']['status'], geometry_issues=obj['geometry']['issues'])
        affected.append(dict(object_id=obj['object_id'], image_code=obj['image_code'], worker_id=obj['worker_id'],
            previous_geometry=before['geometry'], geometry=obj['geometry'], before=before, after=copy.deepcopy(obj)))
    byid = {o['object_id']: o for o in bundle['data']['objects']}
    changed = {r['object_id'] for r in affected}
    for row in bundle['research']['annotations']:
        if row['object_id'] in changed:
            obj = byid[row['object_id']]
            row.update(geometry_status=obj['geometry']['status'], geometry_issues=obj['geometry']['issues'])
    for images in (bundle['data']['images'], bundle['research']['images']):
        for im in images:
            group = [o for o in byid.values() if o['object_kind']=='annotation' and o['image_id']==im['image_id']]
            if any(o['object_id'] in changed for o in group):
                im['geometry_counts'] = dict(Counter(o['geometry']['status'] for o in group))
    research = bundle['research']
    for name, table in research['cross_tables'].items():
        if not table or not any(k.startswith('geometry') for k in table[0]['dimensions']):
            continue
        fields = list(table[0]['dimensions']); included = {oid for r in table for oid in r['ids']}
        groups = defaultdict(list)
        for row in research['annotations']:
            if row['object_id'] in included:
                groups[tuple(row[k] for k in fields)].append(row['object_id'])
        research['cross_tables'][name] = [dict(dimensions=dict(zip(fields,k)), n=len(v), ids=v) for k,v in groups.items()]
    anns = [o for o in byid.values() if o['object_kind']=='annotation']
    retained = dict(Counter(o['geometry']['status'] for o in anns if o['cleaning_disposition'] in {'retained','retained_pending'}))
    research['summary']['retained_geometry'] = retained
    bundle['final_summary'].update(geometry=dict(Counter(o['geometry']['status'] for o in anns)), retained_geometry=retained)
    bundle['data']['processed_input_revision'] = REVISION
    research['processed_input_revision'] = REVISION
    return affected


def rescore_changed(bundle, affected):
    from ..analysis.scope_quality_binding_20261016 import build_affected_records
    from ..analysis.scope_quality_scoring_20261016 import scoring_engine, score_task
    from ..analysis.b8l2_calculation_status_20261016 import inspect_geometry
    from ..analysis.b8l2_usage_snapshot_20261016 import usage_policy
    from ..analysis.b8l2_usage_coverage_20261016 import scene_flags
    from ..analysis.quality_b8l2_d10_20261017 import dual_scores, METRICS
    base = ROOT/'research/quality/quality_b8l2_d10_20261017'
    refs = read(base/'reference_catalog.json'); difficulty = read(base/'difficulty_records.json')
    routing = build_affected_records(bundle, difficulty, refs, include_all_images=True, resolve_multiple_spaces=True)
    bindings = {r['object_id']: r for r in routing['affected_records']}
    refs = {r['target_id']: r for r in refs}
    with (base/'shared_records.csv').open(encoding='utf-8-sig', newline='') as f:
        old_rows = {r['object_id']: r for r in csv.DictReader(f)}
    output, audits = [], []
    engine_dir = ROOT/'research/statistics/b8l2_shared_v6_20261016/inputs'
    with scoring_engine(engine_dir/'measurement_engine.zip',engine_dir/'working_models.py') as (engine, models):
        for change in affected:
            obj = change['after']; oid = obj['object_id']; choice = bindings[oid]; ref = refs.get(choice['chosen_target_id'])
            row = {k: (v=='True' if v in ('True','False') else v) for k,v in old_rows[oid].items()}
            for k in ('pool_analysis_exclusion_reasons','quality_exclusion_reasons'):
                row[k] = json.loads(row[k])
            geometry = inspect_geometry(obj, engine); score = None
            state = 'pending_target' if not ref else 'input_uncomputable' if not geometry['full_input_available'] else 'pending_reference' if not ref['full_reference_available'] else 'not_run'
            if state == 'not_run':
                score = score_task(dict(object_id=oid,image_id=obj['image_id'],worker_id=obj['worker_id'],condition=obj['condition'],
                    current_target_id=ref['target_id'],reference_version=ref['reference_version'],
                    annotation_points=obj['points_1024x512'],reference_points=ref['points_1024x512']), engine, models)
                state = 'computed' if score['score_status']=='complete' else 'measurement_failed'
                if state == 'computed': score.update(dual_scores(score,models))
            policy = usage_policy(row,obj,choice,ref,geometry,scene_flags(row),full_score_state=state)
            row.update(policy, geometry_status=obj['geometry']['status'], geometry_issues=obj['geometry']['issues'],
                input_geometry_unchanged=False, quality_audit_status='recomputed_after_confirmed_coordinate_repair',
                input_geometry_status=geometry['input_geometry_status'], input_geometry_reasons=geometry['reasons'],
                full_input_available=geometry['full_input_available'], floor_input_available=geometry['floor_input_available'],
                calculation_status='full_computed' if state=='computed' else state, full_score_state=state,
                current_quality_eligible=policy['quality_usable'], input_version=REVISION,
                snapshot_version='quality_b8l2_d10_processed_input_20261018_v1',usage_version='quality_b8l2_d10_processed_input_20261018_v1',
                measurement_source='confirmed_coordinate_repair_incremental_rescore', binding_status=choice['binding_status'],
                rescore_status='complete' if state=='computed' else state, rescore_target_id=choice['chosen_target_id'],
                reference_id=choice['chosen_target_id'],reference_full_available=bool(ref and ref['full_reference_available']),
                reference_version=ref['reference_version'] if ref else '',rescore_reference_version=ref['reference_version'] if ref else '',
                measurement_reasons=score['reasons'] if score else [], diagnostic_floor_iou=score['iou_2d'] if state=='computed' else None)
            for metric in METRICS:
                value=score[metric] if state=='computed' else None
                row['diagnostic_'+metric]=value; row[metric]=value if policy['quality_usable'] else None
            output.append(row)
            audits.append(dict(object_id=oid, previous_calculation_status=old_rows[oid]['calculation_status'],
                previous_quality_usable=old_rows[oid]['quality_usable']=='True', geometry=geometry,
                binding=choice, policy=policy, score=score))
    write_csv(OUT/'quality_delta.csv', output); dump(OUT/'quality_reassessment.json',audits)
    return audits


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    bundle = load_current_bundle(SOURCE)
    history = audit_history(bundle)
    affected = apply_confirmed_repairs(bundle)
    assert {r['object_id'] for r in affected} == {'8ffe08f072e2b12e'}
    history.update(audit_effective_edits(bundle))
    scores = rescore_changed(bundle, affected)
    validation = validate_bundle(bundle['data'],bundle['research'],bundle['comments'],bundle['final_summary'])
    bundle['validation'] = validation
    manifest = copy.deepcopy(bundle['manifest'])
    manifest.update(effective_input_revision=REVISION, data_release='v1', source_baseline=SOURCE.relative_to(ROOT).as_posix(),
        validation=validation, additional_tables=[],
        validation_scope='完整当前快照；保留已确认数值修复，重评可计算性，既有资格和参考候选不改。')
    for name in manifest['entrypoints']:
        value = bundle[name]
        if name == 'field_contract':
            value = dict(value, processed_input_revision=REVISION,
                confirmed_coordinate_repair='按已应用repair_evidence.changed_points的before/after绑定恢复；不复活删点或旧单边x移动。',
                quality_delta='quality_delta.csv与quality_reassessment.json只覆盖受影响对象；load_scored_context按本修订叠加。旧manifest不应用。')
        if name in ('data','research','comments','final_orders'):
            target = name+'.json.gz'
            with gzip.open(OUT/target,'wt',encoding='utf-8') as stream: json.dump(value,stream,ensure_ascii=False,allow_nan=False)
        else:
            target = name+'.json'; dump(OUT/target,value)
        manifest['entrypoints'][name] = target
    dump(OUT/'manifest.json',manifest)
    dump(OUT/'affected_objects.json',dict(revision=REVISION, objects=[r['after'] for r in affected]))
    dump(OUT/'coordinate_changes.json',affected)
    checks = dict(history, revision=REVISION, affected_objects=len(affected), changed_object_ids=[r['object_id'] for r in affected],
        bundle_validation=validation, historical_files_written=False, original_exports_opened=False,
        effective_source_references_changed=False, quality_usable_added=sum(r['policy']['quality_usable'] and not r['previous_quality_usable'] for r in scores),
        quality_usable_removed=sum(r['previous_quality_usable'] and not r['policy']['quality_usable'] for r in scores),
        quality_usable_total=1911, full_computed_total=2775,
        coordinate_policy='explicit applied changed_points preserved; old one-sided x override remains superseded by shared-x policy')
    dump(OUT/'CHECKS.json',checks)
    return checks


if __name__ == '__main__':
    print(json.dumps(build(),ensure_ascii=False,indent=2))
