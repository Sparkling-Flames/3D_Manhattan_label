"""第二轮记录来源核对；读取历史真源，保留缺口，不改变人工记录。"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.thesis_main.analysis import audit_annotation_research_data_20260905 as old
from tools.thesis_main.analysis.quality_core.choice_parser import extract_data

BASE = ROOT / 'analysis_results/annotation_research_decision_audit_20260905_v1'
SUB = BASE / 'data_audit/recomputed_uncertainty_substrate'
OUT = ROOT / 'analysis_results/annotation_research_prework_20260905_v2/evidence'


def unique_index(rows, key='canonical_annotation_id'):
    result = {}
    for row in rows:
        if not row.get(key) or row[key] in result:
            raise ValueError(f'missing/duplicate identity: {key}={row.get(key)}')
        result[row[key]] = row
    return result


@lru_cache(maxsize=None)
def tasks(path):
    value = json.loads((ROOT / path).read_text(encoding='utf-8-sig'))
    if not isinstance(value, list):
        raise ValueError(f'expected task list: {path}')
    return value


def same_points(left, right):
    a, b = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    return bool(a.size and a.shape == b.shape and np.allclose(a, b, atol=1e-6, rtol=0))


def preview_points(task):
    encoded = parse_qs(urlparse(task.get('data', {}).get('vis_3d', '')).query).get('data', [])
    return [point for pair in json.loads(encoded[0]) for point in ([pair['x'],pair['y_ceiling']],[pair['x'],pair['y_floor']])] if encoded else []


def parse_layout_split(lines):
    result = set()
    for line in lines:
        parts = line.split()
        if len(parts) == 2:
            result.add(parts[0]+'_'+Path(parts[1]).stem)
        elif len(parts) == 1:
            result.add(Path(parts[0]).stem)
        elif parts:
            raise ValueError('unexpected layout split format')
    return result


def time_status(row):
    source, status = row.get('active_time_source', ''), row.get('timing_status', '')
    if 'partial' in status:
        return 'partial_session_coverage_excluded_from_speed'
    if 'fallback' in source or 'fallback' in status or old.truth(row.get('lead_time_is_active_time')):
        return 'lead_time_only_not_active'
    try:
        value = float(row.get('active_time_seconds', ''))
    except (ValueError, TypeError):
        return 'active_time_missing'
    if not np.isfinite(value) or value <= 0:
        return 'active_time_nonpositive_or_nonfinite'
    if status in {'eligible', 'eligible_with_protocol_deviation', 'project+task+annotator', 'owner_valid'}:
        return 'owner_valid_complete_with_deviation' if 'deviation' in status else 'owner_valid_complete'
    return 'active_time_coverage_unverified'


def initialization_trace(spine, task, response):
    initial = json.loads(response.get('initial_points_json') or '[]')
    predictions = task.get('predictions') or []
    full = [p for p in predictions if isinstance(p, dict)]
    status = 'full_prediction_objects' if full else ('prediction_ids_only' if predictions else 'no_predictions')
    imports, versions, checks = [], set(), []
    for path in json.loads(spine['planned_import_source_paths_json']):
        matches = [t for t in tasks(path) if str(t.get('data', {}).get('base_task_id') or t.get('data', {}).get('image_id')) == spine['base_task_id']]
        for item in matches:
            for prediction in item.get('predictions') or []:
                if not isinstance(prediction, dict):
                    continue
                coords = extract_data(prediction.get('result', []))[0]
                imports.append(path)
                checks.append(same_points(initial, coords))
                if prediction.get('model_version'):
                    versions.add(str(prediction['model_version']))
    preview = preview_points(task)
    source_mapping_match = 'not_c1'
    if spine['stage'] == 'C1':
        source_items = [t for t in tasks('export_label/groudTruth.json') if Path(str(t.get('data',{}).get('title') or t.get('data',{}).get('image',''))).stem == spine['base_task_id']]
        source_mapping_match = same_points(initial, preview_points(source_items[0])) if len(source_items)==1 else 'mapping_identity_ambiguous'
    return {'export_prediction_representation': status,
            'initial_import_match_status': ('all_matching' if all(checks) else 'coordinate_conflict') if checks else 'no_resolved_prediction_payload',
            'initial_import_payload_count': len(checks), 'initial_import_paths_json': json.dumps(sorted(set(imports))),
            'initial_import_model_labels_json': json.dumps(sorted(versions)),
            'initial_runtime_preview_match': same_points(initial, preview) if preview else 'preview_missing',
            'initial_model_checkpoint_status': 'not_bound_to_exact_historical_checkpoint',
            'c1_original_mapping_preview_match': source_mapping_match,
            'initialization_reconstructed_source': 'export_label/groudTruth.json:data.vis_3d -> formal_import:_prediction_from_vis' if spine['stage']=='C1' else 'p1_import_payload; natural_or_synthetic_per_proposal_fact',
            'initial_trace_interpretation': 'planned_payload_and_runtime_preview_crosscheck_not_proof_of_user_view_event'}


def split_overlap(training, evaluation):
    overlap = sorted(set(training) & set(evaluation))
    return {'status': 'overlap_detected' if overlap else 'no_overlap_in_supplied_sets', 'overlap_ids': overlap}


def matched_image_package(records, proposals):
    manual = {r['base_task_id'] for r in records if r['stage'] == 'C1' and r['condition'] == 'manual'}
    semi = {r['base_task_id'] for r in records if r['stage'] == 'C1' and r['condition'] == 'semi'}
    shared = manual & semi
    comparisons = [r for r in old.read_csv(BASE / 'data_audit/geometry_comparisons.csv') if r['base_task_id'] in shared]
    old.write_csv(OUT / 'matched25_comparison_details.csv', comparisons)
    rows, changes = [], []
    reference_map = old._load_gt_pairs()
    for prop in proposals.values():
        initial = old.normalize_geometry(json.loads(prop['initial_points_json']))
        final = old.normalize_geometry(json.loads(prop['final_points_json']))
        usable = initial.get('valid') and final.get('valid')
        changes.append({**prop, 'initial_final_d_mask': old._d_mask(old._dense_boundaries(initial['pairs']), old._dense_boundaries(final['pairs'])) if usable else '',
                        'initial_final_d_mask_status': 'available' if usable else 'incompatible_or_invalid_geometry'})
    for base in sorted(shared):
        group = [r for r in records if r['base_task_id'] == base and r['stage'] == 'C1']
        output = {'base_task_id': base, 'building_id': group[0]['building_id'],
                  'reference_versions_json': json.dumps(sorted({r['reference_version'] for r in group})),
                  'reference_scope_status_json': json.dumps(sorted({r['reference_scope_status'] for r in group})),
                  'reference_warning': 'not_final_human_adjudication; AI50_and_human30_remain_separate',
                  'causal_interpretation_allowed': False}
        for condition in ['manual','semi']:
            g = [r for r in group if r['condition'] == condition]
            comp = [r for r in comparisons if r['base_task_id'] == base and r['stage'] == 'C1' and r['condition'] == condition]
            human_gt = [float(r['d_mask']) for r in comp if r['comparison'] == 'human_gt']
            pairs = [float(r['d_mask']) for r in comp if r['comparison'] == 'human_human_different_worker_same_stage' and r.get('other_stage') == 'C1']
            output.update({f'{condition}_record_count':len(g), f'{condition}_workers_json':json.dumps(sorted({r['worker_id'] for r in g})),
                           f'{condition}_strict_geometry_count':sum(r['geometry_status'] == 'strict_valid' for r in g),
                           f'{condition}_complete_time_count':sum(r['active_time_owner_valid_status'].startswith('owner_valid_complete') for r in g),
                           f'{condition}_reference_d_mask_n':len(human_gt), f'{condition}_reference_d_mask_mean':float(np.mean(human_gt)) if human_gt else '',
                           f'{condition}_within_pair_n':len(pairs), f'{condition}_within_pair_d_mask_mean':float(np.mean(pairs)) if pairs else ''})
        ch = [r for r in changes if r['base_task_id'] == base and r['stage'] == 'C1']
        reference = reference_map.get(base)
        initial = old.normalize_geometry(json.loads(ch[0]['initial_points_json'])) if ch else {}
        output['initial_reference_d_mask'] = old._d_mask(old._dense_boundaries(initial['pairs']), old._dense_boundaries(reference['pairs'])) if initial.get('valid') and reference else ''
        output['initial_reference_identity_warning'] = 'exact_geometry_match_reference_not_independent' if output['initial_reference_d_mask'] == 0 else 'geometry_differs_does_not_establish_reference_independence'
        for model in ['hohonet','bilayout_enclosed','bilayout_extended']:
            model_values = [r for r in comparisons if r['base_task_id'] == base and r['comparison'] == f'{model}_gt']
            output[f'{model}_reference_d_mask'] = model_values[0]['d_mask'] if len(model_values)==1 else ''
            output[f'{model}_reference_status'] = 'available_offline_not_historical_init' if len(model_values)==1 else 'not_computable'
        vals = [r['initial_final_d_mask'] for r in ch if r['initial_final_d_mask_status']=='available']
        output.update(initial_final_d_mask_n=len(vals), initial_final_d_mask_mean=float(np.mean(vals)) if vals else '',
                      exact_retention_count=sum(old.truth(r['exact_geometry_equal']) for r in ch),
                      same_worker_cross_condition_count=len(set(json.loads(output['manual_workers_json'])) & set(json.loads(output['semi_workers_json']))))
        rows.append(output)
    old.write_csv(OUT / 'matched25_image_summary.csv', rows)
    old.write_csv(OUT / 'semi_initial_final_changes.csv', changes)
    record_map = {r['canonical_annotation_id']:r for r in records}
    initialization_groups = defaultdict(list)
    for row in changes:
        initialization_groups[(row['stage'],record_map[row['canonical_annotation_id']]['initialization_source_kind'],row['reference_type'])].append(row)
    initialization_summary = []
    for key, group in sorted(initialization_groups.items()):
        vals = [r['initial_final_d_mask'] for r in group if r['initial_final_d_mask_status']=='available']
        initialization_summary.append({'stage':key[0],'historical_source_kind':key[1],'reference_type':key[2],
            'image_count':len({r['base_task_id'] for r in group}),'response_count':len(group),'geometry_change_n':len(vals),
            'initial_final_d_mask_mean':float(np.mean(vals)) if vals else '', 'exact_retention_count':sum(old.truth(r['exact_geometry_equal']) for r in group),
            'source_note':'C1 legacy missing flag resolved to import+runtime preview; exact checkpoint unknown' if key[0]=='C1' else 'natural/synthetic initialization separate'})
    old.write_csv(OUT/'initialization_condition_summary.csv',initialization_summary)
    return {'matched_images':len(shared), 'manual_records':sum(r['manual_record_count'] for r in rows), 'semi_records':sum(r['semi_record_count'] for r in rows)}


def building_model_audit(records):
    official = Path('D:/Work/Manhattan_3D/mp3d_layout_gt_sources/Matterport_official/tasks/benchmark')
    splits = {name:set((official/f'scenes_{name}.txt').read_text().split()) for name in ['train','val','test']}
    buildings = sorted({r['building_id'] for r in records})
    mapping = [{'building_id':b,'official_split_memberships':';'.join(s for s,ids in splits.items() if b in ids),
                'source_paths':';'.join(str(official/f'scenes_{s}.txt') for s in splits if b in splits[s]),
                'room_instance_status':'not_verified; no_local_house_or_pano_region_instance_file_found_in_bounded_search'} for b in buildings]
    model_rows = []
    historical_images = {r['base_task_id'] for r in records}
    layout_train = {p.stem for p in (ROOT/'data/mp3d_layout/train/img').iterdir() if p.suffix.lower() in {'.jpg','.png'}}
    bi_split = Path('D:/Work/Manhattan_3D/Bi_layout/src/dataset/mp3d/split/train.txt')
    bi_train = parse_layout_split(bi_split.read_text().splitlines())
    layout_overlap = {'HoHoNet_local_training_image_directory':split_overlap(layout_train,historical_images),
                      'Bi_local_training_split_file':split_overlap(bi_train,historical_images),
                      'local_files_are_not_checkpoint_training_lineage':True,
                      'HoHoNet_local_train_count':len(layout_train),'Bi_local_train_count':len(bi_train),
                      'local_train_building_overlap':split_overlap({s.split('_')[0] for s in layout_train},buildings)}
    for split in ['test','val']:
        meta_path = Path(f'D:/Work/Manhattan_3D/Bi_layout/exports/mp3d_dual_predictions/{split}/run_metadata.json')
        meta = json.loads(meta_path.read_text())
        model_rows.append({'model':'Bi-Layout','split':split,'metadata_source':str(meta_path), 'checkpoint':meta['checkpoint'],
                           'config':meta['config'],'postprocess':meta['post_processing'], 'heads_json':json.dumps(meta['branch_mapping']),
                           'sample_count':meta['sample_count'],'checkpoint_exists':Path(meta['checkpoint']).is_file(),
                           'training_data_claim':'mp3d in config; exact training item list and checkpoint training lineage unverified',
                           'train_evaluation_leakage_status':'unknown_for_actual_checkpoint', 'historical_initialization_equivalence':'not_established'})
        model_rows.append({'model':'HoHoNet','split':split,'metadata_source':'tools/thesis_main/analysis/materialize_model_initialization_audit.py default argument; not full run manifest',
                           'checkpoint':'ckpt/mp3d_layout_HOHO_layout_aug_efficienthc_Transen1_resnet34/ep300.pth',
                           'prediction_source':str(old.HOHO_ROOTS[split]),'training_data_claim':'checkpoint path naming only; exact training item list unverified',
                           'train_evaluation_leakage_status':'unknown_for_actual_checkpoint','historical_initialization_equivalence':'offline_ep300_not_automatically_historical_init'})
    model_rows.append({'model':'HorizonNet','split':'unknown','train_evaluation_leakage_status':'no_independent_predictions_or_checkpoint_verified',
                       'metadata_source':'bounded existing asset inventory; implementation/config references are not evaluated outputs'})
    old.write_csv(OUT/'building_split_room_mapping.csv',mapping)
    old.write_csv(OUT/'model_provenance.csv',model_rows)
    return {'building_count':len(mapping),'unknown_building_split_count':sum(not r['official_split_memberships'] for r in mapping),
            'official_train_vs_historical_building_overlap':split_overlap(splits['train'],buildings),
            'layout_training_file_checks':layout_overlap,
            'actual_checkpoint_training_overlap':'unknown_not_inferred_from_benchmark_splits', 'room_instance_verified_count':0}


def additional_response_audit(records):
    inventory = old.read_csv(BASE/'data_audit/export_annotation_version_inventory.csv')
    formal_keys = {(r['project_id'],r['runtime_task_id'],r['worker_id'],r['raw_annotation_id']) for r in records}
    seen, output = Counter(), []
    development = [r for r in inventory if r['source_classification']=='development_export']
    for r in development:
        key = (r['project_id'],r['runtime_task_id'],r['worker_id'],r['annotation_id'])
        seen[key] += 1
        task_matches = [t for t in tasks(r['source_path']) if str(t.get('id'))==r['runtime_task_id']]
        data = task_matches[0].get('data',{}) if len(task_matches)==1 else {}
        reasons = []
        if not r['condition']:
            reasons.append('annotation_condition_unrecorded')
        if key in formal_keys:
            reasons.append('already_in_canonical_identity')
        if data.get('smoke_test'):
            reasons.append('smoke_test_not_verified_new_response')
        # Numeric account IDs alone cannot establish historical person identity or task exposure.
        reasons.append('historical_person_process_and_exposure_not_verified')
        output.append({**r,'candidate_identity_json':json.dumps(key),'recorded_dataset_group':data.get('dataset_group',''),
                       'recorded_smoke_test':data.get('smoke_test',''),'recorded_artifact_status':data.get('artifact_status',''),
                       'new_independent_response_added':False,'unresolved_reasons_json':json.dumps(reasons)})
    old.write_csv(OUT/'additional_response_candidates.csv',output)
    return {'development_snapshot_rows':len(output),'development_unique_runtime_identities':len(seen),
            'condition_missing_rows':sum(not r['condition'] for r in development),'condition_present_rows':sum(bool(r['condition']) for r in development),
            'added_to_canonical':0,'reason':'identity_and_condition_process_verification_pending_not_old_eligibility_exclusion'}


def materialize():
    OUT.mkdir(parents=True, exist_ok=True)
    spine = old.read_csv(SUB / 'annotation_spine.csv')
    unique_index(spine)
    timing = unique_index(old.read_csv(SUB / 'active_time_context.csv'))
    proposals = unique_index(old.read_csv(SUB / 'proposal_response.csv'))
    facts = unique_index(old.read_csv(SUB / 'proposal_fact.csv'), 'proposal_id')
    geometry = unique_index([r for r in old.read_csv(SUB / 'geometry_variants.csv') if r['variant'] == 'strict_normalized'])
    lineage = defaultdict(list)
    for row in old.read_csv(SUB / 'annotation_version_lineage.csv'):
        lineage[row['canonical_annotation_id']].append(row)
    refs = old._load_gt_pairs()
    semantic = {r['image_id']: r for r in old.read_csv(BASE / 'inventory/room_region_mapping_records.csv')}
    records, traces, conflicts = [], [], []
    for row in spine:
        cid, base = row['canonical_annotation_id'], row['base_task_id']
        candidates = [t for t in tasks(row['raw_export_path']) if str(t.get('id')) == row['runtime_task_id']]
        if len(candidates) != 1:
            raise ValueError(f'raw task identity mismatch {cid}')
        task = candidates[0]
        annotations = [a for a in task.get('annotations', []) if str(a.get('id')) == row['raw_annotation_id']]
        if len(annotations) != 1:
            raise ValueError(f'raw annotation identity mismatch {cid}')
        annotation = annotations[0]
        g, ref = geometry.get(cid, {}), refs.get(base, {})
        prop = proposals.get(cid, {})
        trace = initialization_trace(row, task, prop) if prop else {}
        if prop:
            fact = facts[prop['proposal_id']]
            traces.append({**{k: row[k] for k in ['canonical_annotation_id', 'stage', 'base_task_id', 'worker_id', 'raw_export_path']},
                           'legacy_initialization_source_kind': fact['initialization_source_kind'], 'reference_type': prop['reference_type'], **trace})
        raw_points = extract_data(annotation.get('result', []))[0]
        final_matches = same_points(raw_points, json.loads(prop['final_points_json'])) if prop else 'not_semi'
        if final_matches is False or trace.get('initial_import_match_status') == 'coordinate_conflict':
            conflicts.append({'canonical_annotation_id': cid, 'final_matches_proposal_response': final_matches, **trace})
        ts = time_status(timing[cid])
        parsed = old.truth(g.get('strict_valid'))
        record = {**row, 'condition': row['raw_condition'], 'source_role': 'canonical_historical_response',
                  'source_path': row['raw_export_path'], 'raw_annotation_identity_status': 'unique_task_and_annotation',
                  'raw_final_point_count': len(raw_points), 'semi_final_raw_match': final_matches,
                  'geometry_status': 'strict_valid' if parsed else g.get('invalid_reason', 'strict_invalid_or_missing'),
                  'quality_reference_status': ref.get('reference_status', 'missing_reference'),
                  'reference_version': ref.get('source', 'unknown'), 'reference_identity': base,
                  'reference_scope_status': ref.get('scope_status', 'unknown'),
                  'active_time_owner_valid_status': ts, **{f'time_{k}': v for k, v in timing[cid].items() if k not in row},
                  'active_time_seconds': timing[cid]['active_time_seconds'], 'timing_status': timing[cid]['timing_status'],
                  'active_time_source_path': timing[cid]['active_time_source_file'],
                  'habit_feature_status': 'initial_final_available' if prop else ('reference_geometry_available' if parsed and ref else 'not_evaluable'),
                  'initialization_source_kind': facts[prop['proposal_id']]['initialization_source_kind'] if prop else 'not_applicable',
                  'proposal_reference_type': prop.get('reference_type', 'not_applicable'),
                  'revision_version_count': len(lineage[cid]), 'room_instance_id': '', 'room_instance_status': 'not_verified_local_instance_mapping_absent',
                  'region_class': semantic.get(base, {}).get('region_class', ''),
                  'building_identity_status': 'pano_prefix_checked_against_dataset_split' ,
                  'created_at': annotation.get('created_at', ''), 'updated_at': annotation.get('updated_at', ''),
                  'evidence_note': 'history_all_roster; missing_channel_not_global_exclusion; semantic_class_not_room_instance', **trace}
        records.append(record)
    unique_index(records)
    cells = defaultdict(list)
    for r in records:
        cells[(r['stage'], r['condition'], r['building_id'], r['worker_id'])].append(r)
    coverage = [{'stage': k[0], 'condition': k[1], 'building_id': k[2], 'worker_id': k[3], 'record_count': len(v),
                 'image_count': len({r['base_task_id'] for r in v}), 'strict_geometry_count': sum(r['geometry_status'] == 'strict_valid' for r in v),
                 'complete_active_time_count': sum(r['active_time_owner_valid_status'].startswith('owner_valid_complete') for r in v)} for k, v in sorted(cells.items())]
    by_person_image = defaultdict(list)
    for r in records:
        by_person_image[(r['worker_id'], r['base_task_id'])].append(r)
    exposure = [{'worker_id': k[0], 'base_task_id': k[1], 'record_count': len(v), 'conditions_json': json.dumps(sorted({r['condition'] for r in v})),
                 'canonical_ids_json': json.dumps([r['canonical_annotation_id'] for r in v]), 'stages_json': json.dumps(sorted({r['stage'] for r in v})),
                 'created_at_json': json.dumps([r['created_at'] for r in v]), 'interpretation': 'repeated_exposure_possible_not_independent_new_person'}
                for k,v in sorted(by_person_image.items()) if len(v) > 1]
    source_manifest = {'baseline': str(SUB), 'raw_export_paths': sorted({r['raw_export_path'] for r in spine}),
                       'import_paths': sorted({p for r in spine for p in json.loads(r['planned_import_source_paths_json'])}),
                       'additional_development_responses_added': 0,
                       'additional_response_status': 'not_added_without_verified_person_condition_and_exposure; v1_source_inventory_retained',
                       'v1_source_inventory': str(BASE / 'data_audit'), 'room_search_root': 'D:/Work/Manhattan_3D/mp3d_layout_gt_sources/Matterport_official'}
    outputs = {'record_evidence.csv': records, 'initialization_trace.csv': traces, 'source_conflicts.csv': conflicts,
               'worker_building_condition_coverage.csv': coverage, 'historical_exposure.csv': exposure,
               'version_lineage.csv': old.read_csv(SUB / 'annotation_version_lineage.csv')}
    for name, values in outputs.items():
        old.write_csv(OUT / name, values)
    qa = {'record_count': len(records), 'unique_workers': len({r['worker_id'] for r in records}), 'images': len({r['base_task_id'] for r in records}),
          'buildings': len({r['building_id'] for r in records}), 'time_status_counts': dict(Counter(r['active_time_owner_valid_status'] for r in records)),
          'initialization_trace_counts': dict(Counter(r['initial_import_match_status'] for r in traces)),
          'prediction_representation_counts': dict(Counter(r['export_prediction_representation'] for r in traces)),
          'conflict_count': len(conflicts), 'added_responses': 0, 'raw_records_overwritten': False}
    qa['matched25'] = matched_image_package(records, proposals)
    qa['building_model_audit'] = building_model_audit(records)
    qa['additional_response_audit'] = additional_response_audit(records)
    old.write_json(OUT / 'QA.json', qa)
    old.write_json(OUT / 'SOURCE_MANIFEST.json', source_manifest)
    old.write_json(OUT / 'FIELD_CONTRACT.json', {'schema_version': 'prework_record_evidence_v2', 'key': ['canonical_annotation_id'],
                   'fields': sorted({k for row in records for k in row}), 'time_rule': 'positive_complete_owner_valid_only; partial_and_lead_separate',
                   'unknown_rule': 'empty_identity_requires_explicit_status; not_zero', 'reference_version': 'reference_collection_path_not_per_image_id'})
    return qa


if __name__ == '__main__':
    print(json.dumps(materialize(), ensure_ascii=True))
