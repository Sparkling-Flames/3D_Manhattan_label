"""Local synthetic-only Label Studio serialization and existing-parser round trip."""
from __future__ import annotations

import collections
import hashlib
import math
import re

import numpy as np

from . import simulate_annotators as base
from .quality_core.choice_parser import extract_data
from .semi_edit_distribution import SUCCESS
from ..data_prep.build_post_block2_analysis_pack_v2 import parse_corners


def synthetic_worker(worker, condition):
    return 'S_' + condition.upper() + '_' + str(int(worker)).zfill(3)


def export_samples(samples, images, output):
    tasks, rejected, ledger = {}, [], []
    exported = set()
    for sample in samples:
        sid = sample['simulation_id']
        # Explicit identity is opt-in so historical exports retain their bytes.
        worker = sample.get('export_worker_id', synthetic_worker(sample['source_worker_profile_id'], sample['condition']))
        if not isinstance(worker, str) or not re.fullmatch(r'S_[A-Z]+_\d+', worker):
            raise ValueError('invalid_synthetic_export_identity')
        if sid in exported:
            raise ValueError('duplicate_simulation_id')
        reason = None
        points = np.asarray(sample['points'], dtype=float)
        if sample.get('synthetic') is not True:
            raise ValueError('refusing_non_synthetic_record')
        if not base.parsed(points) or not np.all((points[:, 0] >= 0) & (points[:, 0] < 1024) & (points[:, 1] >= 0) & (points[:, 1] < 512)):
            reason = 'coordinates_not_exportable'
        elif sample.get('worker_scope_response') not in {'in_scope', 'oos'}:
            reason = 'missing_scope_response'
        elif not isinstance(sample.get('lead_time_seconds'), (float, int)) or not math.isfinite(sample['lead_time_seconds']) or sample['lead_time_seconds'] <= 0:
            reason = 'missing_valid_lead_time'
        elif sample['condition'] == 'semi' and sample.get('semi_status') not in SUCCESS:
            reason = 'semi_transfer_not_supported:' + sample.get('semi_status', 'missing')
        ledger.append(dict(simulation_id=sid, synthetic_worker_id=worker, image_id=sample['image_id'], condition=sample['condition'],
            template_worker_id=sample['source_worker_profile_id'], export_status='rejected' if reason else 'exported',
            rejection_reason=reason, synthetic=True, semi_donor=sample.get('semi_donor_annotation_id'),
            residual_donor=sample.get('residual_donor_annotation_id'), scope_donor=sample.get('scope_donor_annotation_id'),
            time_donor=sample.get('time_donor_annotation_id'), lead_time_donor=sample.get('lead_time_donor_annotation_id'),
            semi_generation_method=sample.get('semi_generation_method'), semi_global_source=sample.get('semi_global_source'),
            semi_local_sources=sample.get('semi_local_sources'), semi_addition_source=sample.get('semi_addition_source')))
        if reason:
            rejected.append(dict(simulation_id=sid, image_id=sample['image_id'], condition=sample['condition'], reason=reason))
            continue
        assert re.fullmatch(r'S_[A-Z]+_\d+', worker)
        iid = sample['image_id']
        tid = 'ST_' + hashlib.sha256(iid.encode()).hexdigest()[:16]
        aid = 'SA_' + hashlib.sha256(sid.encode()).hexdigest()[:20]
        scope_choice = 'normal' if sample['worker_scope_response'] == 'in_scope' else 'oos'
        result = [dict(id=f'kp_{i}', from_name='kp', to_name='img', type='keypointlabels',
            original_width=1024, original_height=512, image_rotation=0,
            value=dict(x=float(p[0]) / 10.24, y=float(p[1]) / 5.12, width=.5, keypointlabels=['Corner'])) for i, p in enumerate(points)]
        result.append(dict(id='scope_0', from_name='scope', to_name='img', type='choices', value=dict(choices=[scope_choice])))
        annotation = dict(id=aid, completed_by=worker, result=result, lead_time=sample['lead_time_seconds'],
            worker_scope_response=sample['worker_scope_response'], synthetic=True, ground_truth=False,
            was_cancelled=False, task=tid, simulation_id=sid, condition=sample['condition'],
            provenance_manifest='source_manifest.json', generation_parameters=sample.get('generation_parameters'),
            active_time_seconds=sample.get('active_time_seconds'), timing_status=sample.get('timing_status'),
            lead_time_status=sample.get('lead_time_status'), scope_status=sample.get('scope_status'),
            scope_variant=sample.get('scope_variant'), scope_geometry_bound=False,
            semi_status=sample.get('semi_status'), synthetic_metadata=sample.get('source_hashes'))
        if 'export_worker_id' in sample:
            annotation['source_worker_profile_id'] = sample['source_worker_profile_id']
            annotation['difficulty_wild_metadata'] = {k: sample[k] for k in (
                'difficulty', 'difficulty_version', 'difficulty_source', 'wild', 'wild_error_types',
                'wild_budget_k', 'need', 'real_manual_n', 'gt_error_excluded',
                'pending_review', 'scope_reference_status')}
            for key in ('difficulty_basis', 'disagreement_px', 'difficulty_thresholds',
                        'gt_none', 'evaluation_reason', 'real_count_basis'):
                if key in sample:
                    annotation['difficulty_wild_metadata'][key] = sample[key]
        # Additive opt-in metadata leaves all historical export bytes unchanged.
        if sample.get('geometry_source') == 'space_anchor':
            for key in ('space_id', 'space_kind', 'anchor_source', 'anchor_annotation_id',
                        'anchor_junction_count', 'corner_anchor_dist_px', 'geometry_source',
                        'space_scope_coherence', 'scope_space_coherence', 'space_inventory_version',
                        'space_parent_id', 'sampled_space_id', 'anchor_pair_indices', 'anchor_operations',
                        'source_anchor_junction_count'):
                annotation[key] = sample[key]
        # Both readers preserve the serialized point order; no geometry fitting is invoked.
        parsed, _, choices, _ = extract_data(result)
        if not np.allclose(parsed, points, rtol=0, atol=1e-10) or not np.allclose(parse_corners(result), points, rtol=0, atol=1e-10):
            raise ValueError('existing_parser_roundtrip_failed')
        if choices.get('scope') != [scope_choice]:
            raise ValueError('scope_roundtrip_failed:' + str(choices))
        task = tasks.setdefault(iid, dict(id=tid, data=dict(image=images[iid]['image_url'], image_id=iid),
            annotations=[], meta=dict(synthetic=True, intended_use='local_experimental_only')))
        if any(a['completed_by'] == worker for a in task['annotations']):
            raise ValueError('duplicate_synthetic_worker_image_condition')
        task['annotations'].append(annotation)
        exported.add(sid)
    base.dump(output / 'label_studio_synthetic.json', list(tasks.values()))
    base.write_csv(output / 'export_rejections.csv', rejected)
    base.write_csv(output / 'private_worker_ledger.csv', ledger)
    summary = dict(exported_annotations=len(exported), exported_tasks=len(tasks), rejected=len(rejected),
        rejection_reasons=dict(collections.Counter(r['reason'] for r in rejected)),
        validation='existing extract_data and parse_corners roundtrip', formal_human_intake_used=False)
    base.dump(output / 'export_validation.json', summary)
    return exported, summary
