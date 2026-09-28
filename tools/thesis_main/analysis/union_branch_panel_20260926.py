"""用户指定八图的点集分支输入；复读原件，不换序、不回写裁决。"""
from collections import Counter
import json
from pathlib import Path

import numpy as np

from tools.thesis_main.analysis.structural_consensus_panel_20260926 import (
    ROOT, INPUTS, ORDER, annotation_record, read_json, source_points,
    floor_points, load_reference, pixel_ray, shared_x,
)

PANEL = {
    '7y3sRwLe3Va-12': ['oos'],
    '7y3sRwLe3Va-08': ['oos'],
    'uNb9QFRL6hY-52': ['oos'],
    'pRbA3pwrgk9-11': ['doorway', 'oos'],
    'q9vSo1VnCiC-04': ['doorway'],
    'uNb9QFRL6hY-66': ['difficult'],
    'uNb9QFRL6hY-59': ['difficult'],
    'uNb9QFRL6hY-41': ['difficult'],
}
USER_ORDER = dict(source='current_user_message_20260926',
                  claim='用户明示所选八图默认角点顺序没问题',
                  scope='image_default_order_only_not_annotation_correctness_or_GT_validity')


def attach_borrowed_revision(record, row, by_id, cache):
    """补点保留在描述性视图；不能把 donor 坐标当作另一人的独立观测。"""
    provenance = row['imputation_provenance']
    if row['processing_status'] != 'user_confirmed_add_point' or not provenance['borrowed_other_response']:
        raise ValueError('unhandled_effective_revision:' + row['canonical_annotation_id'])
    donor = by_id[provenance['donor_id']]
    donor_points, donor_source = source_points(ROOT, donor, cache)
    raw = np.asarray(record['raw_points'], float)
    effective = np.asarray(row['effective_points_1024x512'], float)
    expected = np.vstack([raw, donor_points[provenance['donor_raw_point_1based'] - 1]])
    if (donor['image_id'] != row['image_id'] or effective.shape != expected.shape
            or provenance['added_point_1based'] != len(effective)
            or not np.allclose(effective, expected, atol=1e-8, rtol=0)
            or not np.allclose(effective[-1], provenance['coordinate_1024x512'], atol=1e-8, rtol=0)):
        raise ValueError('borrowed_revision_coordinate_or_identity_drift:' + row['canonical_annotation_id'])
    evidence_path = Path('analysis_results/new_manual_reviewed_20260921') / provenance['source']
    evidence = read_json(ROOT / evidence_path)
    decisions = {k: v for k, v in evidence['decisions'].items()
                 if k.startswith(row['image_id'] + '|') and v['relation'] == '漏标需补点（见文字）'}
    if len(decisions) != 1 or next(iter(decisions.values()))['defer']:
        raise ValueError('borrowed_revision_user_evidence_missing')
    links = np.asarray(row['links_zero_based'], int)
    pairs = shared_x(effective, links)[links]
    floor = floor_points(pairs)
    rays = np.array([pixel_ray(*p[0], 1024, 512) for p in pairs])
    heights = 1 + np.linalg.norm(floor, axis=1) * rays[:, 1] / np.linalg.norm(rays[:, [0, 2]], axis=1)
    if not np.isfinite(heights).all() or np.any(heights <= 1):
        raise ValueError('borrowed_revision_invalid_ceiling')
    record.update(reason='borrowed_point_not_independent_geometric_vote',
        revised_core_record=dict(id=row['canonical_annotation_id'], worker=row['worker_id'],
            pairs=pairs.tolist(), floor=floor.tolist(), heights=heights.tolist(),
            order_status='user_confirmed_default_order', independent_raw_vote=False,
            use='full_sample_descriptive_sensitivity_only', donor_worker=donor['worker_id']),
        revision_verification=dict(coordinates_verified=True, donor_worker=donor['worker_id'],
            donor_source=donor_source, user_evidence_source=evidence_path.as_posix(),
            user_decisions=decisions, independence='one_coordinate_borrowed_from_another_response'))


def cohort_counts(records):
    primary = [r for r in records if r['raw_condition'] in ('manual', 'oos')]
    semi = [r for r in records if r['raw_condition'] == 'semi']
    if len(primary) + len(semi) != len(records):
        raise ValueError('unexpected_condition')
    for cohort in (primary, semi):
        if len({r['worker_id'] for r in cohort}) != len(cohort):
            raise ValueError('duplicate_worker_within_image_cohort')
    return dict(accepted_annotations=len(records), primary_input_annotations=len(primary),
                primary_computable_annotations=sum(r['core_record'] is not None for r in primary),
                primary_unavailable_annotations=sum(r['core_record'] is None for r in primary),
                semi_input_annotations=len(semi),
                semi_computable_annotations=sum(r['core_record'] is not None for r in semi))


def run(out=ROOT / 'analysis_results/union_branch_consensus_20260926'):
    rows = read_json(ROOT / INPUTS / 'annotations.jsonl.gz', lines=True)
    refs = read_json(ROOT / INPUTS / 'references.json.gz')
    by_id = {r['canonical_annotation_id']: r for r in rows}
    if len(by_id) != len(rows) or sum(r['accepted_before_new_review'] for r in rows) != 3019:
        raise ValueError('canonical_inventory_drift')
    codes = {v['code']: iid for iid, v in refs.items()}
    if not set(PANEL) <= set(codes):
        raise ValueError('user_selected_image_missing')
    orders = {r['object_id']: r for r in read_json(ROOT / ORDER)['records']
              if r['object_type'] == 'canonical_annotation'}
    images, evaluations, raw_cache, gt_cache = [], [], {}, {}
    for code, strata in PANEL.items():
        iid, records = codes[code], []
        inventory = [r for r in rows if r['image_id'] == iid]
        for row in sorted(inventory, key=lambda r: r['canonical_annotation_id']):
            if not row['accepted_before_new_review']:
                continue
            record = annotation_record(ROOT, row, raw_cache, orders.get(row['canonical_annotation_id']))
            record['order_status'] = 'user_confirmed_default_order'
            record['user_order_confirmation'] = USER_ORDER
            record['revised_core_record'] = None
            if record['core_record'] is not None:
                record['core_record'].update(pairs=record['shared_x_pairs'],
                    order_status=record['order_status'], independent_raw_vote=True)
            elif record.get('reason') == 'effective_revision_not_used_in_raw_only_probe':
                attach_borrowed_revision(record, row, by_id, raw_cache)
            records.append(record)
        excluded = [{k: r.get(k) for k in ('canonical_annotation_id', 'worker_id',
                    'raw_condition', 'exclusion_reason', 'processing_status')}
                    for r in inventory if not r['accepted_before_new_review']]
        images.append(dict(image_id=iid, code=code, building_id=refs[iid]['building_id'],
            image_path=refs[iid]['image_path'], strata=strata,
            label_status='user_selected_exploratory_strata_not_formal_difficulty_adjudication',
            default_order_user_confirmed=True, formal_geometry_confirmation=False,
            user_order_confirmation=USER_ORDER, annotations=records,
            counts=dict(cohort_counts(records), previously_excluded_annotations=len(excluded)),
            unavailable_annotations=[dict(canonical_annotation_id=r['canonical_annotation_id'],
                worker_id=r['worker_id'], reason=r.get('reason')) for r in records if r['core_record'] is None],
            previously_excluded_inventory=excluded))
        references = []
        for ref in refs[iid]['references']:
            if ref['name'] not in ('gt_original', 'gt_revised'):
                continue
            item = dict(name=ref['name'], source=ref.get('source'), pairing_basis=ref.get('pairing_basis'),
                status='unavailable', pairs=None, raw_points=None,
                order_status='source_ring_not_individually_confirmed', used_for_fitting=False)
            try:
                points = load_reference(dict(ref, image_id=iid), ROOT, gt_cache)
                item['raw_points'] = points.tolist()
                if ref['pairing_basis'] == 'source_alternating_pairs':
                    item.update(status='verified_source_ring_conditional', pairs=points.reshape(-1, 2, 2).tolist())
                else:
                    item.update(status='raw_verified_pairing_unconfirmed', reason='reference_pairing_not_source_defined')
            except (ValueError, FileNotFoundError, KeyError) as exc:
                item['reason'] = str(exc)
            references.append(item)
        evaluations.append(dict(image_id=iid, code=code, manual_gt_changed=refs[iid]['manual_gt_changed'],
                                references=references))
    all_records = [r for image in images for r in image['annotations']]
    result = dict(schema='union_branch_input_panel_20260926_v1', contract_version='consensus_research_20260923_v1',
        selection=dict(explicit_codes=list(PANEL), uses_gt_scores=False, uses_new_algorithm_outputs=False,
                       source='current_user_selected_eight_images_default_order_confirmed'),
        counts=dict({
            key: sum(image['counts'][key] for image in images) for key in images[0]['counts']},
            selected_images=len(images),
            unavailable_reasons=dict(Counter(r['reason'] for r in all_records if r['core_record'] is None)),
            source_status=dict(Counter(r['source']['status'] for r in all_records)),
            condition_annotations=dict(Counter(r['raw_condition'] for r in all_records))),
        geometry=dict(coordinate_system='continuous_LS_1024x512_camera_height_1',
            adjacency='existing_links_zero_based_sequence_no_sorting_or_repair',
            shared_x='existing_circular_pair_midpoint', default_order_scope='only_these_eight_images',
            geometry_screening=False, no_new_exclusion=True),
        split_rules=dict(primary_conditions=['manual', 'oos'], semi='separate_never_mix_votes',
            one_vote='unique_worker_within_image_cohort', eligibility='core_record_is_not_null',
            unavailable='retain_inventory_and_input_denominator_no_independent_geometric_vote',
            borrowed_points='revised_core_record_full_sample_sensitivity_only_no_independent_replay'),
        images=images, references_for_evaluation_only=evaluations,
        reference_limit='GT_is_one_reference_interpretation_not_a_universal_quality_or_fitting_target')
    path = Path(out) / 'input_panel.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + '\n', encoding='utf8')
    return result


if __name__ == '__main__':
    print(json.dumps(run()['counts'], ensure_ascii=False))
