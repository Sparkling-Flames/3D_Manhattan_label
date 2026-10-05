"""Allowlisted public projection of the integrated review; never changes eligibility."""
import argparse
from collections import Counter
import json
from pathlib import Path

from tools.thesis_main.analysis.research_round_20260929 import validate_panel, write_json

IMAGE_REVIEW_FIELDS=('gt_substantive_error_mark','gt_detail_omission_mark','gt_uncertainty_explicit_tag',
    'stable_nonorthogonal','scope_explicit_tag','scope_existing_ledger','scope_comment_candidate',
    'detail_explicit_tag','detail_existing_ledger','detail_comment_candidate')
ANNOTATION_REVIEW_FIELDS=('scope_annotation','detail_annotation','execution_tag','gt_substantive_error_mark',
    'gt_detail_omission_mark','gt_uncertainty_explicit_tag','explicit_model_influence',
    'trap_status','model_edit_status','model_outcome','order_change')


def project(source):
    objects=source['objects']
    workers={w:f'P{i:03d}' for i,w in enumerate(sorted({o['worker_id'] for o in objects if o['object_kind']=='annotation'}),1)}
    ids={o['object_id']:f'R{i:05d}' for i,o in enumerate(sorted(objects,key=lambda o:o['object_id']),1)}
    images=[]
    for im in source['images']:
        row=dict(code=im['image_code'],building=im['building_id'],room=im['room_id'],
                 population=im['population'],scene={k:(im[k] if im['annotations'] else None) for k in ('oos_status','doorway_status','coverage')},
                 annotations=[],references=[])
        for o in objects:
            if o['image_code']!=im['image_code']:continue
            r=dict(id=ids[o['object_id']],points=o['points_1024x512'],order_status=o['order_status'],
                   geometry_status=o['geometry']['status'],geometry_issues=o['geometry']['issues'],
                   source_point_indices=o['ordered_source_point_indices'],
                   source_point_labels=o['ordered_source_point_labels'],
                   preprocessing_status=o['preprocessing_status'],ring_confirmed=o['ring_confirmed'])
            if o['object_kind']=='annotation':
                gate=o['main_consensus_gate']['status']
                r.update(worker=workers[o['worker_id']],condition=o['condition'],cleaning=o['cleaning_disposition'],
                         independent=o['independent_vote_eligible'],independence_reasons=o['independent_vote_reasons'],
                         consensus_eligible=gate in ('main_candidate','oos_doorway_exploratory','stable_nonorthogonal_separate'),
                         quality_candidate=o['main_quality_gate']['status']=='candidate_pending_geometry',
                         main_quality_gate=o['main_quality_gate'],main_consensus_gate=o['main_consensus_gate'],
                         scene_category=o['scene_category'],borrowed_points=bool(o['borrowed_point_provenance']))
                row['annotations'].append(r)
            else:
                r['version']={'gt_original':'original','gt_manual_revision':'manual_revision'}[o['object_kind']]
                row['references'].append(r)
        images.append(row)
    panel=dict(schema='layout_research_panel_v1',source_manifest=dict(
        source_entry='analysis_results/research_input_20260929/preprocessed_source.json',
        source_schema=source['schema'],contract_version=source['contract_version'],
        coordinate_frame=source['coordinate_frame'],preprocessing=source['preprocessing'],
        object_counts=dict(Counter(o['object_kind'] for o in objects)),
        consensus_inclusion='Upstream main_candidate, oos_doorway_exploratory and stable_nonorthogonal_separate; report separately',
        privacy='This alias panel omits raw IDs, comments, photographs, task URLs and mappings; authorized mappings/comments are separately public in the repository (2026-10-01)'),images=images)
    validate_panel(panel)
    assert sum(len(i['annotations'])+len(i['references']) for i in images)==len(objects)
    return panel,dict(workers=workers,records=ids)


def project_bundle(bundle):
    """Project a validated manifest bundle, including incomplete review evidence."""
    if bundle['manifest']['schema']!='research_analysis_bundle_v1' or bundle['validation']['status']!='passed':
        raise ValueError('validated_bundle_required')
    panel,mapping=project(bundle['data']);research=bundle['research']
    anns={r['object_id']:r for r in research['annotations']}
    ims={r['image_code']:r for r in research['images']}
    expected={o['object_id'] for o in bundle['data']['objects'] if o['object_kind']=='annotation'}
    if set(anns)!=expected or len(anns)!=len(research['annotations']) or set(ims)!={i['code'] for i in panel['images'] if i['annotations']}:
        raise ValueError('public_context_population_mismatch')
    reverse={alias:oid for oid,alias in mapping['records'].items()}
    for im in panel['images']:
        im['review']={k:ims[im['code']][k] for k in IMAGE_REVIEW_FIELDS} if im['annotations'] else None
        for r in im['annotations']:r['review']={k:anns[reverse[r['id']]][k] for k in ANNOTATION_REVIEW_FIELDS}
    panel['source_manifest'].update(source_entry='analysis_results/research_input_20260929/manifest.json',
                                    bundle_schema=bundle['manifest']['schema'],review_context_revision='20260930')
    panel['review_context']=dict(
        mark_coverage='partial review: false means no recorded mark, not verified absence; not prevalence or a negative training label',
        priorities='connection and representation first; then spatial metrics, point/detail clustering, worker fusion and geometrically plausible candidates; worker profiles and difficulty later; GT detail omission discovery is tertiary',
        gt_policy='consume existing substantive-error decisions and gates; no new GT adjudication',
        difference_axes=['space_extent','detail_representation','localization_within_matched_structure'],
        comment_summary=bundle['comments']['summary'],
        unique_recorded_texts=len({c['text'] for c in bundle['comments']['comments'] if c['text_role']=='recorded_text'}),
        privacy='Full comments were reviewed; this alias panel contains only allowlisted structured evidence. Authorized mappings/comments are separately public in the repository (2026-10-01)',
        interpretation='Scope/detail evidence can coexist; no automatic semantic classification from metrics, point count, keywords or missing marks')
    return panel,mapping


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--private-map',type=Path,required=True)
    a=p.parse_args()
    # Local-only producer: standalone consumers read the published panel, not private sources.
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    panel,mapping=project_bundle(load_current_bundle())
    a.out.parent.mkdir(parents=True,exist_ok=True);a.private_map.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_bytes((json.dumps(panel,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8'))
    write_json(a.private_map,mapping)
