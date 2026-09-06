"""整理可离线读取的研究输入；不重新聚类、不推断歧义或人员状态。"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import sys
import urllib.request

csv.field_size_limit(20_000_000)
ROOT = Path(__file__).resolve().parents[3] if len(Path(__file__).resolve().parents) > 3 else Path(__file__).resolve().parent
PACKAGE = 'analysis_results/uncertainty_cloud_inputs_20260906_v1'
SUB = 'analysis_results/uncertainty_substrate_20260823_v1'
AUDIT = 'analysis_results/annotation_research_decision_audit_20260905_v1'
PRE = 'analysis_results/annotation_uncertainty_prescreen_20260903_v1'
HIST = 'analysis_results/historical_uncertainty_recompute_20260829_v1'
CURRENT = {str(x) for x in [1, 2, 6, 8, 10, 11, 12, 13, 15, 17, *range(28, 38)]}


def read_csv(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def write_rows(path, rows, fields=None):
    rows = list(rows)
    fields = fields or list(dict.fromkeys(k for row in rows for k in row))
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader(); writer.writerows(rows)
    payload = buffer.getvalue().encode('utf-8')
    path.write_bytes(gzip.compress(payload, mtime=0) if str(path).endswith('.gz') else payload)


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r, ensure_ascii=False, allow_nan=False) + '\n' for r in rows), encoding='utf-8')


def read_jsonl(path):
    with Path(path).open(encoding='utf-8-sig') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def truth(value):
    return str(value).lower() in {'true', '1'}


def context_key(row):
    return '|'.join(str(row[k]) for k in ['stage', 'block_index', 'base_task_id', 'raw_condition'])


def resolve_member(spine, stage, image, condition, worker, block=None):
    matches = [r for r in spine if r['stage'] == stage and r['base_task_id'] == image
               and r['raw_condition'] == condition and r['worker_id'] == str(worker)
               and (block is None or r['block_index'] == str(block))]
    return ('matched', matches[0]['canonical_annotation_id']) if len(matches) == 1 else ('missing' if not matches else 'ambiguous', '')


def resolve_raw_version(item, canonical_ids):
    if item is None:
        return 'missing', '', ''
    canonical = item['canonical_annotation_id']
    if truth(item['selected_canonical_version']) and canonical in canonical_ids:
        return 'matched', canonical, canonical
    return 'raw_version_only', '', canonical if canonical in canonical_ids else ''


def ordered_geometry_status(points):
    if len(points) < 4 or len(points) % 2:
        return 'degenerate_or_odd_point_count'
    if any(len(p) != 2 or not all(math.isfinite(v) for v in p) for p in points):
        return 'nonfinite_or_bad_dimension'
    if any(not 0 <= x <= 1024 or not 0 <= y < 512 for x, y in points):
        return 'coordinate_out_of_range'
    for a, b in zip(points[::2], points[1::2]):
        dx = abs(a[0] - b[0])
        if min(dx, 1024 - dx) > 1 or abs(a[1] - b[1]) < 1:
            return 'invalid_consecutive_vertical_pair'
    return 'ordered_pairs_parseable_not_manhattan_certified'


def pair_equality(left, right):
    valid = all(ordered_geometry_status(p) == 'ordered_pairs_parseable_not_manhattan_certified' for p in [left, right])
    result = dict(comparison_status='comparable' if valid else 'not_evaluable',
                  raw_sequence_equal=left == right if valid else None, ordered_cycle_equal=None)
    if not valid:
        return result
    a = [left[i:i+2] for i in range(0, len(left), 2)]
    b = [right[i:i+2] for i in range(0, len(right), 2)]
    result['ordered_cycle_equal'] = len(a) == len(b) and any(
        a == direction[k:] + direction[:k] for direction in [b, b[::-1]] for k in range(len(b)))
    return result


def deduplicate_partitions(rows):
    selected = {}
    fields = ['full_cluster_worker_memberships_json', 'full_structure_status', 'full_partition_status',
              'strict_support', 'full_cluster_count', 'full_second_cluster_support']
    for row in rows:
        if row.get('evaluable') is not None and not truth(row['evaluable']):
            if row.get('full_cluster_worker_memberships_json'):
                raise ValueError('Unexpected partition attached to an unevaluable k row')
            continue
        key = (row['stage'], row['condition'], row['base_task_id'])
        if key in selected and any(selected[key].get(k) != row.get(k) for k in fields):
            raise ValueError(f'Full partition changed between k rows: {key}')
        selected.setdefault(key, row)
    return list(selected.values())


def build(root, out, bi_root):
    # Only the local materializer imports existing repository parsers; validate/image work with stdlib alone.
    sys.path.insert(0, str(root))
    from tools.thesis_main.analysis.quality_core.choice_parser import extract_data
    from tools.thesis_main.analysis.materialize_model_gt_threshold_screen import _read_txt

    out.mkdir(parents=True, exist_ok=True)
    sources, gaps = [], []

    def source(path, target, role, compress=False):
        path = Path(path); destination = out / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = path.read_bytes()
        destination.write_bytes(gzip.compress(payload, mtime=0) if compress else payload)
        sources.append(dict(package_path=target, original_source=str(path), role=role,
                            original_bytes=len(payload), original_sha256=hashlib.sha256(payload).hexdigest(),
                            source_content_preserved=True, compression='gzip' if compress else 'none'))

    # Snapshot existing tables losslessly; these are archived facts/results, not newly estimated truths.
    for path in sorted((root / SUB).glob('*.csv')):
        if path.name == 'active_event_fact.csv':
            continue
        source(path, 'facts/' + path.name + '.gz', 'existing_substrate_snapshot', True)
    events = read_csv(root / SUB / 'active_event_fact.csv')
    write_rows(out / 'facts/active_event_observed.csv.gz', [{k:v for k,v in r.items() if k != 'raw_event_json'} for r in events])
    sources.append(dict(package_path='facts/active_event_observed.csv.gz', original_source=SUB+'/active_event_fact.csv',
                        role='existing_event_fields_without_nested_raw_payload_no_fatigue_inference', source_content_preserved=False))
    for name in ['README_ZH.md', 'QA_SUMMARY.json', 'SOURCE_MANIFEST.json']:
        source(root / SUB / name, 'facts/' + name, 'existing_substrate_documentation')
    archived = {
        'extended73_k_replay.csv': AUDIT + '/data_audit/full_high_support_k15_20_task.csv',
        'extended73_k_summary.csv': AUDIT + '/data_audit/full_high_support_k15_20_summary.csv',
        'historical42_partitions.csv': HIST + '/full_roster_structure_tasks.csv',
        'historical42_threshold_sensitivity.csv': HIST + '/structure_threshold_sensitivity.csv',
        'historical42_membership_threshold_source.csv': 'analysis_results/rq1_raw_recompute_20260826/high_density_cluster_threshold_sensitivity.csv',
        'historical42_readme.md': HIST + '/README_ZH.md',
        'worker_mode_membership_lanes.csv': 'analysis_results/full_uncertainty_data_mining_20260821_v5/WORKER_MODE_MEMBERSHIP_LANES.csv',
        'legacy213_partitions_and_representatives.csv': 'analysis_results/post_block2_analysis_pack_20260817_v4/post_block2_geometry_reconstructed_consensus.csv',
        'legacy_geometry_comparisons.csv': AUDIT + '/data_audit/geometry_comparisons.csv',
        'all_condition_support.csv': AUDIT + '/data_audit/full_stage_condition_image_support_census.csv',
        'matched_three_paths.csv': AUDIT + '/data_audit/three_path_coverage_and_matched_images.csv',
        'room_region_mapping.csv': AUDIT + '/inventory/room_region_mapping_records.csv',
        'room_region_mapping_audit.csv': AUDIT + '/inventory/room_region_mapping_audit.csv',
        'broader_source_catalog.csv': AUDIT + '/inventory/package_catalog.csv',
        'source_inventory.csv': AUDIT + '/data_audit/source_inventory.csv',
        'model_asset_summary.csv': AUDIT + '/inventory/model_asset_summary.csv',
        'human30.json': AUDIT + '/inventory/human_review_export_20260905_raw.json',
        'ai50.json': AUDIT + '/review50/ai_visual_advisory.json',
        'ai50_selection.json': AUDIT + '/review50/selected50_manifest.json',
    }
    for name, path in archived.items():
        source(root / path, 'archive/' + name + ('.gz' if name.endswith('.csv') else ''), 'existing_result_or_review', name.endswith('.csv'))

    spine = read_csv(root / SUB / 'annotation_spine.csv')
    lineage = read_csv(root / SUB / 'annotation_version_lineage.csv')
    registry = read_csv(root / SUB / 'image_registry.csv')
    geometry = read_csv(root / SUB / 'geometry_variants.csv')
    by_id = {r['canonical_annotation_id']: r for r in spine}
    if len(by_id) != len(spine):
        raise ValueError('Duplicate canonical annotation identity')
    raw = {r['canonical_annotation_id']: json.loads(r['points_json']) for r in geometry if r['variant'] == 'raw'}
    canonical_view = [{**r, 'context_key': context_key(r), 'current20_member': r['worker_id'] in CURRENT,
                       'coordinate_width':1024, 'coordinate_height':512} for r in spine]
    write_rows(out / 'annotations.csv.gz', canonical_view)

    print('核对原始导出坐标和修订版本...', flush=True)
    exports = {}
    def find_annotation(path, task_id, worker_id, annotation_id):
        if path not in exports:
            index = {}
            for task in read_json(root / path):
                for a in task.get('annotations', []):
                    worker = a.get('completed_by')
                    if isinstance(worker, dict): worker = worker.get('id', worker.get('pk'))
                    key = (str(a.get('task', task.get('id'))), str(worker), str(a['id']))
                    if key in index: raise ValueError(f'Duplicate raw annotation: {path} {key}')
                    index[key] = a
            exports[path] = index
        return exports[path][(str(task_id), str(worker_id), str(annotation_id))]
    versions, raw_checks = [], []
    for r in lineage:
        a = find_annotation(r['source_path'], r['runtime_task_id'], r['worker_id'], r['raw_annotation_id'])
        points = extract_data(a.get('result', []))[0]
        points = [[float(x), float(y)] for x,y in points]
        if truth(r['selected_canonical_version']):
            archived_points = raw[r['canonical_annotation_id']]
            match = len(points) == len(archived_points) and all(abs(x-y) <= 1e-8 for p,q in zip(points,archived_points) for x,y in zip(p,q))
            if not match: raise ValueError(f'Raw coordinate drift: {r["raw_annotation_version_id"]}')
            raw_checks.append(dict(canonical_annotation_id=r['canonical_annotation_id'], raw_coordinates_match=True))
        versions.append({**r, 'points_1024x512':points,
                         'raw_keypoint_results':[p for p in a.get('result', []) if p.get('type') == 'keypointlabels']})
    write_jsonl(out / 'raw_annotation_versions.jsonl', versions)
    write_rows(out / 'checks/raw_coordinate_check.csv', raw_checks)

    prescreen = read_json(root / PRE / 'machine_manifest.json')['items']
    candidates = [r for r in prescreen if r['history_layer'] == 'no_existing_annotation_record']
    candidate_by = {r['image_id']:r for r in candidates}
    historical_ids = {r['base_task_id'] for r in registry}
    if historical_ids & set(candidate_by): raise ValueError('Candidate and historical images overlap')
    image_ids = historical_ids | set(candidate_by)
    room = defaultdict(list)
    for row in read_csv(root / AUDIT / 'inventory/room_region_mapping_records.csv'):
        room[row['image_id']].append(row)
    dual = {}
    for split in ['test', 'val']:
        path = bi_root / split / 'manifest.csv'
        source(bi_root / split / 'run_metadata.json', f'models/bilayout_{split}_run_metadata.json', 'actual_inference_metadata')
        rows = [r for r in read_csv(path) if r['pano_id'] in image_ids]
        write_rows(out / f'models/bilayout_{split}_manifest.csv', rows)
        for r in rows:
            if r['pano_id'] in dual: raise ValueError('Model split identity collision')
            dual[r['pano_id']] = r
    if set(dual) != image_ids: raise ValueError('Bi manifest missing required image IDs')
    source(bi_root.parent.parent / 'src/config/mp3d.yaml', 'models/bilayout_mp3d_config.yaml.gz', 'actual_inference_config_not_training_overlap_verification', True)
    hist_by = {r['base_task_id']:r for r in registry}
    images = []
    for image in sorted(image_ids):
        records = room[image]
        classes = sorted({r['region_class'] for r in records if r['region_class']})
        url = hist_by.get(image, {}).get('image_reference', '')
        images.append(dict(image_id=image, building_id=image.split('_')[0], split=dual[image]['split'],
                           population_role='historical_annotated' if image in historical_ids else 'candidate_without_historical_annotation',
                           image_url=url, image_url_provenance='historical_registry' if url else 'pending_import_lookup',
                           local_image_source=candidate_by.get(image,{}).get('assets',{}).get('image',{}).get('path',''),
                           room_instance_id='', room_identity_status='unknown_not_inferred_from_building_or_class',
                           region_class_values_json=json.dumps(classes), room_mapping_status='region_class_only' if classes else 'unmapped',
                           coordinate_width=1024, coordinate_height=512))

    print('物化模型和参考坐标，不重新推理...', flush=True)
    layouts = []
    def layout(path, image, model, head, role, **extra):
        path = Path(path)
        key = f'{image}|{model}|{head}|{role}'
        item = dict(layout_id=key, image_id=image, model_family=model, head=head, source_role=role,
                    source_path=str(path), coordinate_width=1024, coordinate_height=512, **extra)
        if path.is_file():
            text_value = path.read_text(encoding='utf-8-sig')
            points = [[float(x),float(y)] for x,y in _read_txt(path)]
            item.update(points_1024x512=points, raw_file_text=text_value, parse_status=ordered_geometry_status(points), source_exists=True)
        else:
            item.update(points_1024x512=[], raw_file_text='', parse_status='missing_file', source_exists=False)
            gaps.append(dict(kind='missing_model_or_reference_file', identity=key, source=str(path), action='retain_missing_no_substitute'))
        layouts.append(item)
        return item
    bi_pairs = {}
    for image in sorted(image_ids):
        d = dual[image]; split = d['split']
        pair = []
        for head in ['enclosed', 'extended']:
            item = layout(bi_root / d[f'{head}_corners_px_path'], image, 'Bi-Layout', head, 'offline_dual_prediction',
                          split=split, shared_model_id='Bi-Layout_mp3d_dual', manifest_status=d['status'],
                          declared_is_polygon=truth(d[f'{head}_is_polygon']),
                          declared_corner_count=int(d[f'{head}_corner_count']))
            if item['source_exists'] and len(item['points_1024x512']) != 2*item['declared_corner_count']:
                raise ValueError(f'Bi point count drift: {image} {head}')
            floor = bi_root / d[f'{head}_floor_uv_path']
            item['floor_uv_text'] = floor.read_text(encoding='utf-8-sig') if floor.is_file() else None
            pair.append(item)
        bi_pairs[image] = pair
        hoho_dir = 'model_initialization_test_ep300_replay_20260823_v1' if split == 'test' else 'model_initialization_validation_ep300_replay_20260823_v1'
        layout(root / 'analysis_results' / hoho_dir / 'prediction_txt' / f'{image}.layout.txt', image,
               'HoHoNet', 'single', 'offline_ep300_replay', split=split)
        if image in candidate_by:
            p = root / candidate_by[image]['assets']['model_txt']['path']
            layout(p, image, 'HoHoNet', 'single', 'candidate_prescreen_legacy_output', split=split)
            ref = candidate_by[image]['assets']['reference']
            layout(root / ref['path'], image, 'reference', 'dataset_label', 'candidate_dataset_reference',
                   reference_status='not_adjudicated_for_this_study', split=split)
    references = [{**r,'reference_id':r['layout_id'], 'scope_status':'not_adjudicated_for_this_study',
                   'reference_quality_status':r['reference_status']} for r in layouts if r['model_family']=='reference']
    layouts = [r for r in layouts if r['model_family']!='reference']
    url_lookup = {}
    imports = {'test':'import_json/groudTruth_458_tasks_import_from_updated_gt_20260701.json',
               'val':'import_json/mp3d_validation_gt_audit_20260809/mp3d_validation_all_gt_import.json'}
    for split, file in imports.items():
        for task in read_json(root / file):
            d = task.get('data', {})
            image = Path(str(d.get('base_task_id') or d.get('task_id') or d.get('title') or '')).stem
            if image not in image_ids: continue
            if d.get('image'): url_lookup[image] = d['image']
            for i, a in enumerate(task.get('annotations', []) + task.get('predictions', [])):
                points = [[float(x),float(y)] for x,y in extract_data(a.get('result', []))[0]]
                references.append(dict(reference_id=f'{image}|public_import|{split}|{i}', image_id=image,
                                       points_1024x512=points, source_path=file, source_role='public_dataset_import_reference',
                                       scope_status='not_adjudicated_for_this_study', reference_quality_status='not_assumed_correct',
                                       raw_keypoint_results=[p for p in a.get('result',[]) if p.get('type')=='keypointlabels']))
    gold_path = 'analysis_results/prescreen_closeout_final_gold_v2_20260701/final_gold_records_v2_p1_closeout_corrected.jsonl'
    for r in read_jsonl(root / gold_path):
        if r['base_task_id'] in image_ids:
            pairs = r.get('runtime_pairs_1024x512', [])
            points = [[p['x'], p[k]] for p in pairs for k in ['y_ceiling','y_floor']]
            references.append(dict(reference_id=r['base_task_id']+'|historical_adjudicated', image_id=r['base_task_id'],
                                   points_1024x512=points, source_path=gold_path, source_role='historical_adjudication_not_new_review',
                                   scope_status=r.get('final_scope_binary',''), reference_quality_status='geometry_ready' if r.get('geometry_gold_ready') else 'not_geometry_ready',
                                   original_reference_record=r))
    for r in images:
        if not r['image_url'] and r['image_id'] in url_lookup:
            r.update(image_url=url_lookup[r['image_id']], image_url_provenance='public_GT_import')
        if not r['image_url']:
            gaps.append(dict(kind='image_url_missing', identity=r['image_id'], source='registries_and_public_imports', action='visual_access_unavailable_offline_geometry_retained'))
    write_rows(out / 'images.csv', images)
    write_jsonl(out / 'models/layouts.jsonl', layouts)
    write_jsonl(out / 'references.jsonl', references)
    legacy_gap = {r['base_task_id']:r for r in read_csv(root / AUDIT / 'data_audit/geometry_comparisons.csv') if r['comparison']=='bilayout_enclosed_extended'}
    equality = []
    for image, (a,b) in sorted(bi_pairs.items()):
        eq = pair_equality(a['points_1024x512'], b['points_1024x512'])
        old = legacy_gap.get(image, {})
        equality.append(dict(image_id=image, **eq, declared_manifest_status=dual[image]['status'],
                             legacy_linear_gap=old.get('d_mask',''), legacy_linear_gap_zero=float(old['d_mask'])==0 if old else '',
                             legacy_metric='periodic_linear_image_plane_mask_proxy_1024x512' if old else '',
                             interpretation='coordinate_or_proxy_equality_only_not_image_ambiguity_label'))
    write_rows(out / 'models/dual_equality_checks.csv', equality)
    metadata = dict(Bi_Layout=dict(shared_model=True, raw_predictions_in_package=True,
                                  checkpoint_locator=str(bi_root.parent.parent/'checkpoints/Bi_Layout_Net/mp3d/mp3d_best_model.pkl'),
                                  training_overlap_status='not_independently_verified_do_not_infer_from_split_name',
                                  definition_source='https://liagm.github.io/Bi_Layout/'),
                    HoHoNet=dict(offline_replay_and_candidate_legacy_roles_separate=True,
                                 historical_exposure_source='facts/proposal_fact.csv.gz',
                                 checkpoint_label='ep300', training_overlap_status='not_independently_verified'),
                    HorizonNet=dict(role='inventory_only_no_inference', available_output_status='not_located_in_current_asset_inventory'),
                    no_model_weights_required=True)
    write_json(out / 'models/MODEL_PROVENANCE.json', metadata)

    print('连接已有分簇成员，保留阈值和分区版本...', flush=True)
    partitions, memberships = [], []
    extended = deduplicate_partitions(read_csv(root / AUDIT / 'data_audit/full_high_support_k15_20_task.csv'))
    legacy = read_csv(root / HIST / 'full_roster_structure_tasks.csv')
    raw_alias = {r['raw_annotation_version_id']:r for r in lineage}
    for version, rows in [('extended73', extended), ('historical42', legacy)]:
        for r in rows:
            image, stage = r['base_task_id'], r['stage']
            condition = r.get('condition','manual')
            clusters = json.loads(r['full_cluster_worker_memberships_json'] if version == 'extended73' else r['cluster_membership_json'])
            key = f'{version}|{stage}|{condition}|{image}'
            contexts = {context_key(s) for s in spine if s['stage']==stage and s['base_task_id']==image and s['raw_condition']==condition}
            sizes = [len(c) for c in clusters]
            partitions.append(dict(partition_id=key, version=version, image_id=image, stage=stage, condition=condition,
                                   context_key=next(iter(contexts)) if len(contexts)==1 else '', context_mapping_status='matched' if len(contexts)==1 else 'ambiguous',
                                   cluster_count=len(clusters), member_count=sum(sizes), reported_support=r.get('strict_support',r.get('full_valid_support','')),
                                   partition_status=r.get('full_partition_status',r.get('partition_status','')),
                                   structure_status=r.get('full_structure_status',r.get('structure_status','')),
                                   top_support_tie=len(sizes)>1 and sizes[0]==sizes[1], second_support_tie=len(sizes)>2 and sizes[1]==sizes[2],
                                   geometry_version='strict_normalized', min_boundary_similarity=.95, min_wallwall_similarity=.95,
                                   pointwise_correspondence_compatibility_required=True,
                                   cluster_algorithm='archived_complete_link_with_partition_uniqueness',
                                   representative_status='not_saved_in_this_partition_table_no_new_medoid_selected',
                                   semantic_label='', original_row_json=json.dumps(r,ensure_ascii=False)))
            for rank, cluster in enumerate(clusters,1):
                for member in cluster:
                    raw_version_id, related_canonical = '', ''
                    if version == 'historical42':
                        item = raw_alias.get(member)
                        status, canonical, related_canonical = resolve_raw_version(item, by_id)
                        raw_version_id = member if item else ''
                    else:
                        status, canonical = resolve_member(spine,stage,image,condition,str(member))
                    if status != 'matched':
                        gaps.append(dict(kind='cluster_member_'+status, identity=key+'|'+str(member),source=version,
                                         action='use_raw_annotation_version_id_not_related_canonical_geometry' if status=='raw_version_only' else 'retain_unresolved_do_not_guess'))
                    memberships.append(dict(partition_id=key, cluster_id=key+f'|cluster{rank}', rank=rank,
                                            source_member_id=member, canonical_annotation_id=canonical, mapping_status=status,
                                            raw_annotation_version_id=raw_version_id, related_canonical_annotation_id=related_canonical,
                                            cluster_support=len(cluster), worker_id=by_id[canonical]['worker_id'] if canonical else '', semantic_label=''))
    write_rows(out / 'clusters/partitions.csv.gz', partitions)
    write_rows(out / 'clusters/memberships.csv.gz', memberships)
    # Preserve other lanes unchanged, and add an identity-resolution sidecar rather than silently filling blank IDs.
    lane_links = []
    for i,r in enumerate(read_csv(root / 'analysis_results/full_uncertainty_data_mining_20260821_v5/WORKER_MODE_MEMBERSHIP_LANES.csv')):
        candidates_for_member = [s for s in spine if s['base_task_id']==r['base_task_id'] and s['worker_id']==r['worker_id'] and s['raw_condition']==r['condition']]
        if r['annotation_id']:
            candidates_for_member = [s for s in candidates_for_member if r['annotation_id'] in [s['canonical_annotation_id'],s['raw_annotation_id']]]
        status = 'matched' if len(candidates_for_member)==1 else ('missing' if not candidates_for_member else 'ambiguous')
        lane_links.append(dict(source_row=i+2,analysis_lane=r['analysis_lane'],image_id=r['base_task_id'],worker_id=r['worker_id'],
                               canonical_annotation_id=candidates_for_member[0]['canonical_annotation_id'] if status=='matched' else '',mapping_status=status))
        if status!='matched': gaps.append(dict(kind='legacy_lane_member_'+status,identity=str(i+2),source='worker_mode_membership_lanes',action='retain_unresolved_no_stage_guess'))
    write_rows(out / 'clusters/legacy_lane_links.csv', lane_links)
    representative_links = []
    aliases = {}
    for a in spine:
        alias=a['canonical_annotation_id_legacy_alias']
        if alias:
            if alias in aliases: raise ValueError('Duplicate legacy canonical alias')
            aliases[alias]=a
    for i,r in enumerate(read_csv(root / 'analysis_results/post_block2_analysis_pack_20260817_v4/post_block2_geometry_reconstructed_consensus.csv')):
        for rank,field in [(1,'largest_cluster_medoid_annotation_id'),(2,'second_cluster_medoid_annotation_id')]:
            identifier = r[field]
            a = by_id.get(identifier) or aliases.get(identifier)
            status = 'matched' if a and (a['base_task_id'],a['raw_stage'],a['raw_condition'])==(r['base_task_id'],r['stage'],r['condition']) else ('not_saved' if not identifier else ('source_not_identifiable' if identifier=='not_identifiable' else 'unresolved'))
            representative_links.append(dict(source_partition_row=i+2,source_partition_version='legacy213',image_id=r['base_task_id'],
                                              raw_stage=r['stage'],condition=r['condition'],cluster_rank=rank,raw_representative_id=identifier,
                                              canonical_annotation_id=a['canonical_annotation_id'] if status=='matched' else '',mapping_status=status,
                                              use_scope='legacy213_partition_only_not_representative_of_extended73'))
            if status=='unresolved': gaps.append(dict(kind='legacy_representative_unresolved',identity=str(i+2)+'|'+str(rank),source='legacy213',action='preserve_source_id_no_substitution'))
    write_rows(out / 'clusters/legacy_representative_links.csv', representative_links)
    partition_by_context = defaultdict(list)
    for r in partitions:
        if r['context_key']: partition_by_context[r['context_key']].append(r['partition_id'])
    refs_by_image = defaultdict(list)
    for r in references: refs_by_image[r['image_id']].append(r['reference_id'])
    models_by_image = defaultdict(list)
    for r in layouts:
        if r['model_family'] != 'reference': models_by_image[r['image_id']].append(r['layout_id'])
    proposals_by_annotation = defaultdict(list)
    for r in read_csv(root / SUB / 'proposal_response.csv'): proposals_by_annotation[r['canonical_annotation_id']].append(r['proposal_id'])
    write_rows(out / 'response_links.csv.gz', [dict(canonical_annotation_id=r['canonical_annotation_id'], context_key=context_key(r),
        image_id=r['base_task_id'],worker_id=r['worker_id'], partition_ids_json=json.dumps(partition_by_context[context_key(r)]),
        model_layout_ids_json=json.dumps(models_by_image[r['base_task_id']]),reference_ids_json=json.dumps(refs_by_image[r['base_task_id']]),
        actual_proposal_ids_json=json.dumps(proposals_by_annotation[r['canonical_annotation_id']])) for r in spine])
    metric_links=[]
    model_keys={'hohonet':'HoHoNet|single|offline_ep300_replay',
                'bilayout_enclosed':'Bi-Layout|enclosed|offline_dual_prediction',
                'bilayout_extended':'Bi-Layout|extended|offline_dual_prediction'}
    for i,r in enumerate(read_csv(root / AUDIT / 'data_audit/geometry_comparisons.csv')):
        link=dict(source_row=i+2,image_id=r['base_task_id'],comparison=r['comparison'],metric_contract=r['metric_contract'])
        for side in ['left','right']:
            identifier=r[side+'_id']; a=by_id.get(identifier) or aliases.get(identifier)
            link[side+'_canonical_annotation_id']=a['canonical_annotation_id'] if a else ''
            link[side+'_context_key']=context_key(a) if a else ''
            link[side+'_model_layout_id']=r['base_task_id']+'|'+model_keys[identifier] if identifier in model_keys else ''
            ref_matches=[x['reference_id'] for x in references if x['image_id']==r['base_task_id']
                         and x['source_path'].replace('\\','/')==r.get('reference_source','').replace('\\','/')] if identifier=='gt' else []
            link[side+'_reference_id']=ref_matches[0] if len(ref_matches)==1 else ''
            link[side+'_identity_status']='matched' if a or identifier in model_keys or len(ref_matches)==1 else 'unresolved'
        link['human_pair_context_relation']=('same_context' if link['left_context_key']==link['right_context_key'] else 'different_context') if link['left_context_key'] and link['right_context_key'] else 'not_two_human_responses'
        metric_links.append(link)
    write_rows(out / 'metric_identity_links.csv.gz',metric_links)
    write_rows(out / 'checks/unresolved.csv', gaps, ['kind','identity','source','action'])
    write_rows(out / 'SOURCE_CATALOG.csv', sources)
    qa = dict(status='materialized_pending_offline_validation',historical_images=len(historical_ids),candidate_images=len(candidates),
              workers=len({r['worker_id'] for r in spine}),canonical_annotations=len(spine),raw_versions=len(lineage),
              noncanonical_versions=sum(not truth(r['selected_canonical_version']) for r in lineage),raw_coordinate_matches=len(raw_checks),
              model_layout_rows=len(layouts),reference_variants=len(references),extended_partitions=len(extended),historical_partitions=len(legacy),
              stage_condition_counts=dict(Counter(r['stage']+'|'+r['block_index']+'|'+r['raw_condition'] for r in spine)),
              historical_dual_raw_equal=sum(truth(r['raw_sequence_equal']) for r in equality if r['image_id'] in historical_ids),
              historical_dual_legacy_gap_zero=sum(r['legacy_linear_gap_zero'] is True for r in equality if r['image_id'] in historical_ids),
              legacy_representative_status_counts=dict(Counter(r['mapping_status'] for r in representative_links)),
              legacy_metric_identity_status_counts=dict(Counter(r[s+'_identity_status'] for r in metric_links for s in ['left','right'])),
              legacy_human_pair_context_counts=dict(Counter(r['human_pair_context_relation'] for r in metric_links)),
              unresolved_counts=dict(Counter(g['kind'] for g in gaps)),human_decisions_modified=False,new_clustering_performed=False,
              image_downloads_included=False,raw_sources_modified=False)
    write_json(out / 'BUILD_QA.json', qa)
    field_index=[]
    for p in sorted(out.rglob('*')):
        if p.name in ['FIELD_INDEX.csv','DELIVERY_MANIFEST.json'] or not p.is_file(): continue
        rel=p.relative_to(out).as_posix()
        if p.name.endswith(('.csv','.csv.gz')):
            opener=gzip.open if p.name.endswith('.gz') else open
            with opener(p,'rt',encoding='utf-8-sig',newline='') as stream:
                fields=next(csv.reader(stream))
        elif p.suffix=='.jsonl':
            fields=list(dict.fromkeys(k for row in read_jsonl(p) for k in row))
        else: continue
        field_index.extend(dict(table=rel,field_name=k,semantics_document='FIELDS_ZH.md',
                                preserved_upstream_schema=rel.startswith(('facts/','archive/'))) for k in fields)
    write_rows(out/'FIELD_INDEX.csv',field_index)
    shutil.copyfile(Path(__file__), out / 'cloud_inputs.py')
    print(json.dumps(qa,ensure_ascii=False),flush=True)


def validate(package):
    images = read_csv(package / 'images.csv')
    annotations = read_csv(package / 'annotations.csv.gz')
    versions = read_jsonl(package / 'raw_annotation_versions.jsonl')
    model = read_jsonl(package / 'models/layouts.jsonl')
    references = read_jsonl(package / 'references.jsonl')
    members = read_csv(package / 'clusters/memberships.csv.gz')
    partitions = read_csv(package / 'clusters/partitions.csv.gz')
    ids = {r['image_id'] for r in images}; aids = {r['canonical_annotation_id'] for r in annotations}
    assert len(ids)==len(images) and len(aids)==len(annotations), 'duplicate primary IDs'
    assert len({r['raw_annotation_version_id'] for r in versions})==len(versions), 'duplicate version IDs'
    assert all(r['base_task_id'] in ids and context_key(r)==r['context_key'] for r in annotations)
    selected = [r for r in versions if truth(r['selected_canonical_version'])]
    assert len(selected)==len(annotations) and {r['canonical_annotation_id'] for r in selected}==aids
    assert all(not truth(r['independent_analysis_unit']) for r in versions if not truth(r['selected_canonical_version']))
    assert all(r['image_id'] in ids for r in model+references)
    assert len({r['layout_id'] for r in model})==len(model)
    assert len({r['reference_id'] for r in references})==len(references)
    assert all(r['room_instance_id']=='' for r in images), 'room class must not become an instance ID'
    assert all(not r['semantic_label'] for r in partitions+members), 'no inferred enclosed/extended labels'
    by_id = {r['canonical_annotation_id']:r for r in annotations}
    p_by_id = {r['partition_id']:r for r in partitions}
    seen = set()
    versions_by_id = {r['raw_annotation_version_id']:r for r in versions}
    for member in members:
        p = p_by_id[member['partition_id']]
        if member['mapping_status']=='matched':
            a = by_id[member['canonical_annotation_id']]
            assert (a['base_task_id'],a['stage'],a['raw_condition'])==(p['image_id'],p['stage'],p['condition'])
            key = (member['partition_id'],member['canonical_annotation_id'])
            assert key not in seen, 'same annotation appears twice in a partition'
            seen.add(key)
        elif member['mapping_status']=='raw_version_only':
            version=versions_by_id[member['raw_annotation_version_id']]
            assert not truth(version['selected_canonical_version']) and not member['canonical_annotation_id']
            assert (version['base_task_id'],version['stage'],version['raw_condition'])==(p['image_id'],p['stage'],p['condition'])
    counts = Counter(r['partition_id'] for r in members)
    assert all(counts[r['partition_id']]==int(r['member_count']) for r in partitions)
    assert all(int(r['member_count'])<=int(r['reported_support']) for r in partitions)
    by_model = defaultdict(list)
    for r in model:
        if r['model_family']=='Bi-Layout': by_model[r['image_id']].append(r)
    assert set(by_model)==ids and all({r['head'] for r in x}=={'enclosed','extended'} for x in by_model.values())
    for r in read_csv(package / 'models/dual_equality_checks.csv'):
        a,b = sorted(by_model[r['image_id']],key=lambda x:x['head'])
        eq = pair_equality(a['points_1024x512'],b['points_1024x512'])
        assert eq['comparison_status']==r['comparison_status']
        for k in ['raw_sequence_equal','ordered_cycle_equal']:
            assert ('' if eq[k] is None else str(eq[k]))==r[k]
    links = read_csv(package / 'response_links.csv.gz')
    assert len(links)==len(annotations) and {r['canonical_annotation_id'] for r in links}==aids
    model_ids = {r['layout_id'] for r in model}; ref_ids = {r['reference_id'] for r in references}
    proposals = {r['proposal_id'] for r in read_csv(package / 'facts/proposal_fact.csv.gz')}
    for r in links:
        assert set(json.loads(r['partition_ids_json']))<=set(p_by_id)
        assert set(json.loads(r['model_layout_ids_json']))<=model_ids
        assert set(json.loads(r['reference_ids_json']))<=ref_ids
        assert set(json.loads(r['actual_proposal_ids_json']))<=proposals
    metric_rows=read_csv(package/'archive/legacy_geometry_comparisons.csv.gz')
    metric_links=read_csv(package/'metric_identity_links.csv.gz')
    assert len(metric_rows)==len(metric_links)
    for i,(r,link) in enumerate(zip(metric_rows,metric_links)):
        assert int(link['source_row'])==i+2 and r['base_task_id']==link['image_id'] and r['metric_contract']==link['metric_contract']
        for side in ['left','right']:
            identifier=link[side+'_canonical_annotation_id']
            if identifier: assert context_key(by_id[identifier])==link[side+'_context_key']
            model_id=link[side+'_model_layout_id']; ref_id=link[side+'_reference_id']
            assert not model_id or model_id in model_ids
            assert not ref_id or ref_id in ref_ids
    raw_geometry={r['canonical_annotation_id']:json.loads(r['points_json']) for r in read_csv(package/'facts/geometry_variants.csv.gz') if r['variant']=='raw'}
    for r in selected:
        points=raw_geometry[r['canonical_annotation_id']]
        assert len(points)==len(r['points_1024x512'])
        assert all(abs(x-y)<=1e-8 for p,q in zip(points,r['points_1024x512']) for x,y in zip(p,q))
    # Human answers and AI advisory stay in different archives; no newly filled verdicts.
    human=read_json(package/'archive/human30.json')
    advisory=read_json(package/'archive/ai50.json')
    assert len(human['items'])==30 and len(advisory['items'])==50
    assert advisory['advisory_only'] is True
    assert all(r.get('advisory_only') is True and 'human_review' not in r for r in advisory['items'])
    return dict(validated=True,offline=True,external_paths_opened=0,images=len(images),canonical_annotations=len(annotations),
                versions=len(versions),partitions=len(partitions),cluster_member_rows=len(members),model_layouts=len(model),reference_variants=len(references))


def image_access(package, image_id, output=None):
    rows = [r for r in read_csv(package / 'images.csv') if r['image_id']==image_id]
    if len(rows)!=1 or not rows[0]['image_url']: raise ValueError('Unknown image or missing observed URL')
    url=rows[0]['image_url']
    if not url.startswith('https://'): raise ValueError('Image source requires HTTPS')
    request=urllib.request.Request(url,method='GET' if output else 'HEAD')
    with urllib.request.urlopen(request,timeout=20) as response:
        result=dict(image_id=image_id,url=url,http_status=response.status,content_type=response.headers.get('Content-Type'),
                    content_length=response.headers.get('Content-Length'))
        if not (result['content_type'] or '').startswith('image/'): raise ValueError('Response is not an image')
        if output:
            output.parent.mkdir(parents=True,exist_ok=True)
            with output.open('wb') as stream: shutil.copyfileobj(response,stream)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('build');p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--output',type=Path)
    p.add_argument('--bilayout-root',type=Path,default=Path('D:/Work/Manhattan_3D/Bi_layout/exports/mp3d_dual_predictions'))
    p=sub.add_parser('validate');p.add_argument('--package',type=Path,required=True)
    p=sub.add_parser('image');p.add_argument('--package',type=Path,required=True);p.add_argument('--image-id',required=True);p.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.command=='build': build(args.root.resolve(),(args.output or args.root/PACKAGE).resolve(),args.bilayout_root.resolve())
    elif args.command=='validate': print(json.dumps(validate(args.package),ensure_ascii=False,indent=2))
    else: print(json.dumps(image_access(args.package,args.image_id,args.output),ensure_ascii=False,indent=2))


if __name__=='__main__': main()
