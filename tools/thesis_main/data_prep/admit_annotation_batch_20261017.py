"""显式原点配对与同版排序回执的纯增量接入；不读写文件、不授予评分资格。

batch.records 每条含 source_id/project_id/task_id/annotation_id/completed_by/
source_file/image_id/image_code/raw_keypoints（百分比）及 review；review 必须重复
source_id/raw_keypoints，并有 filter=keep、order_confirmed=True、order/note。
batch.images 仅为新增图片，含 image_id/image_code/building_id 及
gt_original={source, points_1024x512}。pair_maps[source_id] 是原点索引上下配对。
"""
import copy
import json
import math
from collections import Counter, defaultdict

from tools.thesis_main.analysis.shared_x_reanalysis_20260922 import shared_x
from tools.thesis_main.analysis.build_order_gt_screened_20260928 import gt_object, ordered_layout
from tools.thesis_main.analysis.final_review_summary_20260929 import geometry_status
from .consolidate_research_input import validate_bundle

REVISION = 'annotation_batch_98_20261017_v1'


def _layout(obj, order, record=None):
    layout = ordered_layout(obj, order)
    obj.update({k: layout[k] for k in ('points_1024x512', 'ordered_source_pair_indices',
        'ordered_source_point_indices', 'ordered_source_point_labels')})
    obj.update(matterport_links_zero_based=layout['links_zero_based'],
        geometry=geometry_status(obj, order), ring_confirmed=record is not None,
        order_record=record, order_status='human_confirmed' if record else 'default_unreviewed',
        order_origins=[REVISION] if record else [], method_evaluability='not_assessed_per_method')


def _image(meta):
    return dict(image_id=meta['image_id'], image_code=meta['image_code'], building_id=meta['building_id'],
        room_id='', population='research_annotation_image', annotations=0, references={},
        room_spatial_classification={}, room_classification_sources={}, main_visual_space='',
        expected_annotation_extent='', oos_status='not_recorded', doorway_status='not_recorded',
        scope_explicit_tag=False, detail_explicit_tag=False, scope_existing_ledger=False,
        detail_existing_ledger=False, scope_comment_candidate=False, detail_comment_candidate=False,
        comments=[], image_comment='', coverage='new_batch_not_exhaustively_reviewed',
        gt_substantive_error_mark=False, gt_detail_omission_mark=False, gt_uncertainty_explicit_tag=False,
        stable_nonorthogonal=False, gt_evidence=[], scene_comment_mentions=[])


def _research_row(o, im):
    keys = ('object_id', 'image_id', 'image_code', 'worker_id', 'condition', 'building_id', 'room_id',
        'cleaning_disposition', 'worker_quality_gate', 'consensus_group', 'scene_category',
        'scene_oos_status', 'scene_doorway_status', 'trap_status', 'model_edit_status', 'order_status',
        'independent_vote_eligible', 'main_quality_gate', 'main_consensus_gate', 'source', 'review_evidence')
    row = {k: copy.deepcopy(o[k]) for k in keys}
    row.update(geometry_status=o['geometry']['status'], geometry_issues=o['geometry']['issues'],
        method_evaluability=o['method_evaluability'], gt_version_note='',
        gt_judgment='not_marked_not_proven_correct', explicit_model_influence=False,
        model_outcome='correction_success_not_established', model_influence_evidence=None,
        trap_evidence={}, scope_annotation=False, detail_annotation=False, execution_tag=False,
        annotation_traits={}, current_comments=[], current_comment_mentions=[],
        exclusion_reason_detail='unknown_or_nonspecific', order_state='confirmed',
        order_change='user_confirmed_new_batch_order', order_change_evidence=o['batch_review'],
        point_simplification_applied=False)
    for k in ('gt_substantive_error_mark', 'gt_detail_omission_mark', 'gt_uncertainty_explicit_tag'):
        row[k] = im.get(k, False)
    return row


def apply_bundle(bundle, batch, pair_maps, identity_mapping):
    """返回独立新 bundle；旧对象及评论逐值保留。未知配对/绑定直接拒绝。"""
    records = batch['records']
    ids = [r['source_id'] for r in records]
    if len(set(ids)) != len(ids) or set(ids) != set(pair_maps):
        raise ValueError('pair_map_population')
    if identity_mapping['source_project'] != 98 or identity_mapping['identity_confirmed'] is not True:
        raise ValueError('identity_mapping_unconfirmed')
    accounts = {str(r['source_account_id']): r for r in identity_mapping['mappings']}
    if len(accounts) != len(identity_mapping['mappings']): raise ValueError('duplicate_account_mapping')
    result = copy.deepcopy(bundle)
    data, research = result['data'], result['research']
    objects = {o['object_id']: o for o in data['objects']}
    images = {im['image_id']: im for im in data['images']}
    research_images = {im['image_id']: im for im in research['images']}
    old_annotations = [o for o in data['objects'] if o['object_kind'] == 'annotation']
    exposure = {(o['image_id'], o['worker_id']) for o in old_annotations}
    new_meta = {im['image_id']: im for im in batch['images']}
    if len(new_meta) != len(batch['images']) or set(new_meta) & set(images):
        raise ValueError('new_image_population')
    if set(new_meta) != {r['image_id'] for r in records} - set(images):
        raise ValueError('new_image_metadata_coverage')
    for iid, meta in new_meta.items():
        im = _image(meta)
        ref = meta['gt_original']
        gt = gt_object(iid, meta['image_code'], ref['source'], ref['points_1024x512'], 'gt_original', objects)
        gt.update(building_id=im['building_id'], room_id='', gt_version='gt_original')
        _layout(gt, list(range(len(gt['links_zero_based']))))
        data['objects'].append(gt); objects[gt['object_id']] = gt
        im['references']['gt_original'] = gt['object_id']
        data['images'].append(im); images[iid] = im
        research_images[iid] = copy.deepcopy(im); research['images'].append(research_images[iid])
    # 全批重复同时受限，不能以遍历顺序决定哪份有效。
    workers = []
    for r in records:
        if str(r['completed_by']) not in accounts: raise ValueError('unmapped_source_account')
        account = accounts[str(r['completed_by'])]
        if account['identity_confirmed'] is not True: raise ValueError('unconfirmed_account')
        workers.append(account['worker_id'])
    duplicates = Counter((r['image_id'], w) for r, w in zip(records, workers))
    new_objects = []
    for r, worker in zip(records, workers):
        sid, review = r['source_id'], r['review']
        expected_id = f"ls98:{r['task_id']}:{r['annotation_id']}"
        if r['project_id'] != 98 or sid != expected_id or review['source_id'] != sid:
            raise ValueError('source_identity:' + sid)
        if review['raw_keypoints'] != r['raw_keypoints']:
            raise ValueError('review_raw_point_binding:' + sid)
        if review['filter'] != 'keep' or review['order_confirmed'] is not True:
            raise ValueError('unconfirmed_review:' + sid)
        if r.get('was_cancelled') or r.get('ground_truth') or r.get('parent_annotation'):
            raise ValueError('cancelled_gold_or_parent_requires_review:' + sid)
        raw = r['raw_keypoints']; links = pair_maps[sid]
        if (not raw or any(len(p) != 2 or any(not math.isfinite(v) or not 0 <= v <= 100 for v in p) for p in raw)
            or any(len(p) != 2 or any(type(i) is not int for i in p) for p in links)
            or sorted(i for p in links for i in p) != list(range(len(raw)))):
            raise ValueError('incomplete_raw_pairing:' + sid)
        if any(raw[a][1] >= raw[b][1] for a, b in links): raise ValueError('top_bottom_pairing:' + sid)
        order = review['order']
        if any(type(i) is not int for i in order) or sorted(order) != list(range(len(links))):
            raise ValueError('order_permutation:' + sid)
        iid = r['image_id']; im = research_images[iid]
        if r['image_code'] != im['image_code']: raise ValueError('image_code_binding:' + sid)
        condition = r.get('condition', 'manual')
        if condition != 'manual': raise ValueError('unexpected_batch_condition')
        oid = f"new_98_{r['task_id']}_{r['annotation_id']}_{worker}"
        if oid in objects: raise ValueError('existing_object:' + oid)
        before = [[x*1024/100, y*512/100] for x, y in raw]
        source = dict(path=r['source_file'], project=98, task=r['task_id'], annotation=r['annotation_id'],
            worker=worker, source_account_id=str(r['completed_by']), source_id=sid)
        reasons = []
        if worker in {'W019', 'W026'}: reasons.append('existing_worker_exclusion')
        if (iid, worker) in exposure: reasons.append('prior_exposure_not_new_independent_vote')
        if duplicates[iid, worker] > 1: reasons.append('multiple_submissions_version_pending')
        cleaning = 'historical_not_accepted' if worker in {'W019', 'W026'} else 'retained_pending' if reasons else 'retained'
        # 图级旧暂停继续传递；不继承别人的个体复核结论。
        peers = [o for o in old_annotations if o['image_id'] == iid]
        hold_priority = ('hold_all_analysis', 'hold_main_analysis', 'hold_reference_quality')
        gate = next((s for s in hold_priority if any(o['worker_quality_gate'] == s for o in peers)), 'candidate_pending_geometry')
        consensus = next((s for s in ('hold_all_analysis', 'hold_main_analysis', 'inner_space_only_reference_hold')
                          if any(o['consensus_group'] == s for o in peers)), 'main_candidate')
        scene = Counter(o['scene_category'] for o in peers).most_common(1)[0][0] if peers else 'unconfirmed'
        if gate == 'candidate_pending_geometry' and peers:
            applicable = [o for o in peers if o['worker_quality_gate'] not in {'excluded', 'hold_individual_review'}]
            if applicable: gate = Counter(o['worker_quality_gate'] for o in applicable).most_common(1)[0][0]
        if worker in {'W019', 'W026'}: gate = consensus = 'excluded'
        evidence = dict(verdict='new_batch_user_keep', historical_exclusion_reason='', current_comment='',
            current_decision_comment=review['note'], image_comment=im.get('image_comment', ''),
            scope_policy='retain_scope_variation', gt_version_note='', analysis_gate_reasons=[gate],
            annotation_traits={}, image_traits={}, review_history=[], image_review_history=[], coverage_review={},
            semantic_annotation_evidence={}, semantic_image_evidence={}, trap_model_evidence={},
            gt_substantive_error=im.get('gt_substantive_error_mark', False),
            gt_detail_omission=im.get('gt_detail_omission_mark', False), points_without_imputation=True)
        o = dict(object_id=oid, object_kind='annotation', image_id=iid, image_code=im['image_code'],
            worker_id=worker, condition=condition, source=source, original_export_points=before,
            before_preprocessing_points=before, preprocessed_points=shared_x(before, links).tolist(),
            links_zero_based=copy.deepcopy(links), point_labels=[f'p{i+1}' for i in range(len(raw))],
            preprocessing='shared_x_periodic_shortest_arc_v1', preprocessing_status='ready',
            pairing_basis='explicit_source_index_pair_map', building_id=im['building_id'], room_id=im['room_id'],
            cleaning_disposition=cleaning, worker_quality_gate=gate, consensus_group=consensus,
            independent_vote_eligible=not reasons, independent_vote_reasons=reasons,
            canonical_unit=[worker, iid, condition], person_image_unit=[worker, iid], borrowed_point_provenance=[],
            scene_category=scene, scene_oos_status=im['oos_status'], scene_doorway_status=im['doorway_status'],
            trap_status='unknown', model_edit_status='not_checked_non_semi', repair_evidence=[],
            main_quality_gate=dict(status=gate, reasons=[gate]),
            main_consensus_gate=dict(status=consensus, reasons=[consensus], scope_policy='retain_scope_variation'),
            review_evidence=evidence, batch_review=copy.deepcopy(review), worker_scope_response=r.get('scope_response'),
            batch_revision=REVISION)
        binding = dict(id=oid, points=o['preprocessed_points'], labels=o['point_labels'], links=links, preprocessing=o['preprocessing'])
        record = dict(binding=json.dumps(binding, ensure_ascii=False), order=order, status='confirmed',
            note=review['note'], cause=REVISION, updated_at=review.get('updated_at', ''))
        _layout(o, order, record)
        o['final_review'] = dict(object_id=oid, cleaning_disposition=cleaning, worker_quality_gate=gate,
            order_state='confirmed', geometry_status=o['geometry']['status'], geometry_issues=o['geometry']['issues'],
            scope_difference_annotation=False, detail_difference_annotation=False)
        data['objects'].append(o); objects[oid] = o; new_objects.append(o)
        research['annotations'].append(_research_row(o, im))
        result['final_orders']['records'][oid] = record
        result['final_orders'].setdefault('origins', {})[oid] = [REVISION]
    _summaries(result, new_objects, set(new_meta))
    result['validation'] = validate_bundle(data, research, result['comments'], result['final_summary'])
    return result


def _summaries(bundle, new_objects, new_image_ids, revision=REVISION, order_change='user_confirmed_new_batch_order'):
    data, research, final = bundle['data'], bundle['research'], bundle['final_summary']
    anns = [o for o in data['objects'] if o['object_kind'] == 'annotation']
    rows = research['annotations']; touched = {o['image_id'] for o in new_objects}
    for images in (data['images'], research['images']):
        for im in images:
            if im['image_id'] not in touched: continue
            group = [o for o in anns if o['image_id'] == im['image_id']]
            im['annotations'] = len(group)
            for out, key in (('cleaning_counts', 'cleaning_disposition'), ('order_counts', 'order_status'),
                             ('quality_gate_counts', 'worker_quality_gate'), ('consensus_gate_counts', 'consensus_group')):
                im[out] = dict(Counter(o[key] for o in group))
            im['geometry_counts'] = dict(Counter(o['geometry']['status'] for o in group))
    version_groups = defaultdict(list)
    for o in anns: version_groups[tuple(o['canonical_unit'])].append(o)
    new_units = {tuple(o['canonical_unit']) for o in new_objects}
    versions = data['duplicate_versions']
    versions[:] = [v for v in versions if tuple(v['unit']) not in new_units]
    for unit in new_units:
        group = version_groups[unit]
        if len(group) > 1:
            current = [o['object_id'] for o in group if o['cleaning_disposition']=='retained']
            versions.append(dict(unit=list(unit), object_ids=[o['object_id'] for o in group],
                current_object_id=current[0] if len(current)==1 else None))
    nimages = len(research['images']); confirmed = sum(o['ring_confirmed'] for o in data['objects'])
    cleaning = dict(Counter(o['cleaning_disposition'] for o in anns))
    retained = dict(Counter(o['geometry']['status'] for o in anns if o['cleaning_disposition'] in {'retained', 'retained_pending'}))
    data['summary'].update(objects=dict(Counter(o['object_kind'] for o in data['objects'])), images=nimages,
        confirmed_orders=confirmed, cleaning=cleaning, worker_quality_gate=dict(Counter(o['worker_quality_gate'] for o in anns)),
        consensus_group=dict(Counter(o['consensus_group'] for o in anns)), independent_vote_candidates=sum(o['independent_vote_eligible'] for o in anns))
    data['summary']['duplicate_groups'] = len(versions)
    research['summary'].update(annotations=len(anns), research_images=nimages, confirmed_order_objects=confirmed, retained_geometry=retained)
    final.update(annotations=len(anns), images=nimages, confirmed_orders=confirmed, cleaning=cleaning,
        geometry=dict(Counter(o['geometry']['status'] for o in anns)), retained_geometry=retained,
        current_order_status_counts=dict(Counter(o['order_status'] for o in anns)))
    final['scene_images'] = dict(oos=dict(Counter(im['oos_status'] for im in research['images'])),
        doorway=dict(Counter(im['doorway_status'] for im in research['images'])),
        both=sum(im['oos_status']=='confirmed' and im['doorway_status'] in {'difficult', 'annotatable'}
                 for im in research['images']))
    final.setdefault('batches', []).append(dict(batch=revision, objects=len(new_objects),
        images=len(touched), changes={order_change: len(new_objects)}))
    new_ids = {o['object_id'] for o in new_objects}
    for name, table in research['cross_tables'].items():
        if not table: continue
        image_table = name in {'gt_marks', 'scene_images'}
        items = research['images'] if image_table else rows
        selected = new_image_ids if image_table else new_ids
        if name == 'focus_worker_exclusion': selected = set()
        dimensions = list(table[0]['dimensions']); groups = defaultdict(list)
        for row in items:
            identity = row['image_id'] if image_table else row['object_id']
            if identity not in selected: continue
            if name == 'order_changes_by_kind': values = ('annotation', row['order_change'])
            else: values = tuple(row[k] for k in dimensions)
            groups[values].append(identity)
        for values, ids in groups.items():
            dims = dict(zip(dimensions, values))
            existing = next((r for r in table if r['dimensions'] == dims), None)
            if existing is None: table.append(dict(dimensions=dims, n=len(ids), ids=ids))
            else: existing['ids'].extend(ids); existing['n'] = len(existing['ids'])
    bundle['annotation_batch_revision'] = revision
