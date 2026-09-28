"""冻结真实结构共识面板；复读原始导出，沿用已有配对与环，不排序、不删点。"""
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from tools.label_studio.panorama_studio.geometry import pixel_ray
from tools.thesis_main.analysis.build_consensus_handoff_20260923 import read_json, write_json
from tools.thesis_main.analysis.layout_real_case_probe_20260926 import source_points, floor_points, load_reference
from tools.thesis_main.analysis.shared_x_reanalysis_20260922 import shared_x

ROOT = Path(__file__).resolve().parents[3]
INPUTS = 'analysis_results/consensus_research_20260923/inputs'
NOTES = 'tools/thesis_main/analysis/review_reconciliation_notes_20260925.json'
REVIEW = 'analysis_results/review_reconciliation_20260925/evidence/user_review.json'
COMMENTS = 'analysis_results/标注区域差异评论清单_20260926.json'
ORDER = 'analysis_results/order_preliminary_review_20260923/建议清单.json'
EXPLICIT = ('B6ByNegPMKs-11', 'e9zR4mvMWw7-19', 'wc2JMjhGNzB-30')


def annotation_record(root, row, cache, order_evidence):
    cid = row['canonical_annotation_id']
    rec = {key: row.get(key) for key in ('canonical_annotation_id', 'worker_id', 'raw_condition',
           'stage', 'assistance_exposure', 'processing_status', 'imputed_point',
           'accepted_before_new_review', 'known_wrong', 'pairing_status', 'links_zero_based')}
    rec.update(status='unavailable', raw_pairs=None, shared_x_pairs=None, core_record=None,
               order_status='existing_ring_unreviewed', order_evidence=order_evidence)
    if order_evidence is not None:
        rec['order_status'] = 'existing_preliminary_review_pending_confirmation'
    try:
        raw, rec['source'] = source_points(root, row, cache)
        rec['raw_points'] = raw.tolist()
    except ValueError as exc:
        rec.update(source=dict(status='unavailable', reason=str(exc)), reason=str(exc))
        return rec
    effective = np.asarray(row['effective_points_1024x512'], float)
    if effective.shape != raw.shape or not np.allclose(effective, raw, atol=1e-8, rtol=0):
        rec.update(reason='effective_revision_not_used_in_raw_only_probe',
                   existing_effective_points=effective.tolist(),
                   revision_provenance=row.get('imputation_provenance'))
        return rec
    if row['links_zero_based'] is None:
        rec['reason'] = 'existing_pairing_unavailable'
        return rec
    links = np.asarray(row['links_zero_based'], int)
    if links.shape != (len(raw)//2, 2) or sorted(links.ravel()) != list(range(len(raw))):
        rec['reason'] = 'existing_pair_identity_incomplete_or_repeated'
        return rec
    if not np.isfinite(raw).all():
        rec['reason'] = 'nonfinite_raw_coordinate'
        return rec
    rec['raw_pairs'] = raw[links].tolist()
    try:
        pairs = shared_x(raw, links)[links]
        rec['shared_x_pairs'] = pairs.tolist()
        floor = floor_points(pairs)
        top_rays = np.array([pixel_ray(*p[0], 1024, 512) for p in pairs])
        horizontal = np.linalg.norm(top_rays[:, [0, 2]], axis=1)
        if np.any(horizontal < 1e-8):
            raise ValueError('ceiling_ray_at_pole')
        heights = 1 + np.linalg.norm(floor, axis=1) * top_rays[:, 1] / horizontal
        if len(floor) < 3 or not np.isfinite(heights).all() or np.any(heights <= 1):
            raise ValueError('insufficient_vertices_or_ceiling_not_above_camera')
        rec['core_record'] = dict(id=cid, worker=row['worker_id'], floor=floor.tolist(),
                                  heights=heights.tolist(), order_status=rec['order_status'])
        rec['status'] = 'conditional_existing_ring'
    except ValueError as exc:
        rec['reason'] = str(exc)
    return rec


def run(out=ROOT/'analysis_results/structural_consensus_20260926'):
    out = Path(out)
    rows = read_json(ROOT/INPUTS/'annotations.jsonl.gz', lines=True)
    refs = read_json(ROOT/INPUTS/'references.json.gz')
    notes = read_json(ROOT/NOTES)['images']
    review = read_json(ROOT/REVIEW)['decisions']
    comments = {r['image_id']: r for r in read_json(ROOT/COMMENTS)['images']}
    orders = {r['object_id']: r for r in read_json(ROOT/ORDER)['records'] if r['object_type'] == 'canonical_annotation'}
    accepted = [r for r in rows if r['accepted_before_new_review']]
    if len(accepted) != 3019:
        raise ValueError('canonical_inventory_drift')
    by_image = defaultdict(list)
    for row in accepted:
        by_image[row['image_id']].append(row)
    codes = {v['code']: k for k, v in refs.items()}
    hold_codes = {code for code, n in notes.items() if n['doorway_hold'] or n['oos_hold']}
    selected = hold_codes | set(EXPLICIT)
    # 低点数是事前结构分层，不是正确、简单或算法成功标签。
    controls = [code for code, iid in sorted(codes.items())
                if code not in selected and iid not in comments and len(by_image[iid]) >= 8
                and all(r['links_zero_based'] is not None and len(r['links_zero_based']) == 4 for r in by_image[iid])][:4]
    selected |= set(controls)
    if len(hold_codes) != 33 or len(selected) != 40:
        raise ValueError('fixed_panel_selection_drift')
    images, evaluation, raw_cache, gt_cache = [], [], {}, {}
    for code in sorted(selected):
        iid, strata = codes[code], []
        note = notes.get(code, {})
        for label in ('doorway_hold', 'oos_hold'):
            if note.get(label):
                strata.append(label)
        if code in EXPLICIT:
            strata.append('user_named_structural_example')
        if code in controls:
            strata.append('low_corner_count_control')
        context = comments.get(iid, {})
        for category in ('scope_difference_records', 'detail_omission_records'):
            if context.get(category):
                strata.append(category)
        image = dict(image_id=iid, code=code, building_id=refs[iid]['building_id'],
                     image_path=refs[iid]['image_path'], strata=strata,
                     label_status='existing_review_claims_not_final_scope_or_difficulty_labels',
                     label_evidence=dict(notes_source=NOTES, existing_summary=note,
                         original_user_comments=[dict(canonical_annotation_id=cid, **r)
                                                 for cid, r in review.items() if r['image_id'] == iid],
                         original_user_review_source=REVIEW),
                     formal_geometry_confirmation=False,
                     annotations=[annotation_record(ROOT, r, raw_cache, orders.get(r['canonical_annotation_id']))
                                  for r in sorted(by_image[iid], key=lambda r: r['canonical_annotation_id'])],
                     previously_excluded_inventory=[{k: r.get(k) for k in ('canonical_annotation_id', 'worker_id',
                         'raw_condition', 'exclusion_reason', 'processing_status')}
                         for r in rows if r['image_id'] == iid and not r['accepted_before_new_review']])
        images.append(image)
        references = []
        for ref in refs[iid]['references']:
            if ref['name'] not in ('gt_original', 'gt_revised'):
                continue
            record = dict(name=ref['name'], source=ref.get('source'), pairing_basis=ref.get('pairing_basis'),
                          status='unavailable', pairs=None, raw_points=None,
                          order_status='source_ring_not_manually_confirmed')
            try:
                points = load_reference(dict(ref, image_id=iid), ROOT, gt_cache)
                record['raw_points'] = points.tolist()
                if ref['pairing_basis'] == 'source_alternating_pairs':
                    record.update(status='verified_source_ring_conditional', pairs=points.reshape(-1, 2, 2).tolist())
                else:
                    record.update(status='raw_verified_pairing_unconfirmed', reason='reference_pairing_not_source_defined')
            except (ValueError, FileNotFoundError, KeyError) as exc:
                record['reason'] = str(exc)
            references.append(record)
        evaluation.append(dict(image_id=iid, code=code, manual_gt_changed=refs[iid]['manual_gt_changed'], references=references))
    all_records = [r for image in images for r in image['annotations']]
    result = dict(schema='structural_consensus_input_panel_20260926_v1', contract_version='consensus_research_20260923_v1',
        selection=dict(hold_rule='all existing doorway_hold or oos_hold images; not newly adjudicated',
                       explicit_codes=list(EXPLICIT), control_rule='first four code-sorted non-comment images, >=8 accepted rows, all existing pair counts=4',
                       control_codes=controls, uses_gt_scores=False, uses_new_algorithm_outputs=False),
        counts=dict(selected_images=len(images), accepted_annotations=len(all_records),
                    previously_excluded_annotations=sum(len(i['previously_excluded_inventory']) for i in images),
                    strata_images=dict(Counter(s for image in images for s in image['strata'])),
                    condition_annotations=dict(Counter(r['raw_condition'] for r in all_records)),
                    adapter_status=dict(Counter(r['status'] for r in all_records)),
                    unavailable_reasons=dict(Counter(r['reason'] for r in all_records if r['status'] == 'unavailable')),
                    source_status=dict(Counter(r['source']['status'] for r in all_records))),
        geometry=dict(coordinate_system='continuous LS x/1024 and y/512; camera height=1',
                      projection='existing pixel_ray and floor_points; shared_x is circular pair midpoint',
                      adjacency='existing links_zero_based sequence only; no sorting/search/repair',
                      scope='conditional experiment; original coordinates and source evidence preserved',
                      geometry_screening=False, no_new_exclusion=True),
        split_rules=dict(split_unit='worker_id within image; no same person across train and holdout',
                         primary_conditions=['manual', 'oos'], semi='separate analysis, never mix votes',
                         eligibility='status=conditional_existing_ring; unavailable rows stay in denominator',
                         imputed_or_modified_effective_points='retain inventory but unavailable in this raw-only probe'),
        images=images, references_for_evaluation_only=evaluation)
    write_json(out/'input_panel.json', result)
    return result


if __name__ == '__main__':
    import json
    print(json.dumps(run()['counts'], ensure_ascii=False))
