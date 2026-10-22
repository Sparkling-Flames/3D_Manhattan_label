#!/usr/bin/env python3
"""Existing, source-bound barriers for a descriptive development pool.

This function does not assign human quality labels or change formal eligibility.
It is intentionally distinct from the authorized severe calibration exception:
historically excluded individual cases remain outside formal personnel pools.
"""
from __future__ import annotations
import argparse,collections,csv,json
from pathlib import Path
from audit_qualification import read,dump,digest,count_unit

def record_barriers(component,obj,holdrow,registry,screen_overlay=None):
    c=component;r=[]
    if holdrow['held_out_of_sample_and_future_calibration']=='True':r.append('original_frozen_group_holdout')
    if not c.get('primary_included'):r.append('original_primary_included_false')
    if not c.get('primary_gate_and_reference_allowed'):r.append('original_primary_gate_and_reference_not_allowed')
    if not c.get('annotation_strict_available'):r.append('annotation_strict_unavailable')
    if not c.get('reference_strict_available'):r.append('reference_strict_unavailable')
    # The registry field also carries informational records with
    # restrict_primary=False (including accepted revised GT). Nonempty is not a ban.
    if any(x.get('restrict_primary',False) for x in c.get('reference_restrictions',[])):r.append('existing_restrict_primary_reference_rule')
    if c.get('reference_strict_reasons'):r.append('existing_reference_strict_reasons')
    status=obj.get('main_quality_gate',{}).get('status','')
    if status.startswith('hold_') or status in {'excluded','out_of_primary_scene'}:r.append('existing_formal_quality_gate_'+status)
    if obj.get('worker_id')=='W019':r.append('W019_not_formal_personnel')
    # These are recorded current task restrictions; missing marks remain unknown.
    if obj.get('scene_oos_status')=='confirmed' or obj.get('scene_category') in {'oos','oos_stable_nonorthogonal'}:r.append('known_OOS_deferred')
    if obj.get('scene_doorway_status') in {'difficult','annotatable'} or obj.get('scene_category') in {'doorway_difficult','doorway_annotatable'}:r.append('known_doorway_deferred')
    for section in ['confirmed_reference_exclusions','preserved_user_analysis_holds','reference_evidence_conflicts_primary_research_quarantine']:
        for entry in registry[section]:
            if entry['image_id']!=c['image_id']:continue
            if section=='preserved_user_analysis_holds':r.append('preserved_user_image_analysis_hold')
            else:
                for version in entry['gt_versions']:
                    if version['gt_object_id']==c['reference_object_id']:
                        assert version['version']==c['reference_version']
                        assert version['coordinates_sha256']==c['reference_points_sha256']
                        r.append('reference_version_barrier_'+section)
    for entry in registry['all_current_hold_images']:
        if entry['image_id']==c['image_id'] and all(g.startswith('hold_') or g in {'excluded','out_of_primary_scene'} for g in entry['gate_counts']):r.append('existing_image_wide_hold')
    # Use known marked image identities from the latest overlay as a consistency
    # barrier; this does not propagate a person's poor-quality label to an image.
    if screen_overlay:
        for entry in screen_overlay['records']:
            if entry['image_code']==c['image_code'] and entry.get('calibration_scope_hold_reasons'):
                r.extend(entry['calibration_scope_hold_reasons'])
    return list(dict.fromkeys(r))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workspace',type=Path,default=Path.cwd());ap.add_argument('--out',type=Path);a=ap.parse_args();W=a.workspace.resolve()
    O=a.out or W/'top_structure_20261012/evidence/results';O.mkdir(parents=True,exist_ok=True)
    B=W/'previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010'
    pp=dict(components=B/'results/current_components.json',formal=B/'inputs/current_formal_loader_data.json',registry=B/'inputs/reference_exclusion_registry_20261010.json',
        holdout=B/'results/room_holdout_manifest.csv',prior_signals=W/'study_x/results/representation_signals_all3152.csv',
        overlay=W/'new_main_snapshot/research/quality_severe_feedback_20261011/feedback_overlay.json')
    c={r['record_id']:r for r in read(pp['components'])};o={r['object_id']:r for r in read(pp['formal'])['objects']};reg=read(pp['registry']);ov=read(pp['overlay'])
    h={r['record_id']:r for r in csv.DictReader(pp['holdout'].open(encoding='utf-8-sig'))}
    ids=[r['record_id'] for r in csv.DictReader(pp['prior_signals'].open(encoding='utf-8-sig')) if r['target_dev_907']=='True'];assert len(ids)==907
    rows=[]
    for rid in ids:
        q=c[rid];ob=o[q['object_id']];bs=record_barriers(q,ob,h[rid],reg,ov)
        rows.append(dict(record_id=rid,object_id=q['object_id'],image_id=q['image_id'],image_code=q['image_code'],building_id=q['building_id'],room_id=q.get('room_id') or '',
            room_group=h[rid]['room_group'],worker_id=q['worker_id'],barriers=bs,descriptive_development_allowed=not bs,
            applicability_confirmed=(ob.get('scene_oos_status')=='not_oos' and ob.get('scene_doorway_status')=='none'),
            reference_acceptance_newly_confirmed=False,unknown_oos_pending=(ob.get('scene_oos_status')=='pending'),
            no_human_quality_label_added=True,reference_object_id=q['reference_object_id'],reference_version=q['reference_version'],
            reference_annotations=q.get('reference_restrictions',[])))
    kept=[r for r in rows if r['descriptive_development_allowed']];removed=[r for r in rows if not r['descriptive_development_allowed']]
    summary=dict(original_pool=count_unit(rows),remaining=count_unit(kept),removed_count=len(removed),removed_image_codes=sorted({r['image_code'] for r in removed}),
        removed_reason_counts=dict(collections.Counter(s for r in removed for s in r['barriers'])),
        applicability_explicit_among_kept=sum(r['applicability_confirmed'] for r in kept),
        pending_oos_among_kept=sum(r['unknown_oos_pending'] for r in kept),
        nonrestrictive_reference_annotation_records=sum(bool(r['reference_annotations']) and not any(x.get('restrict_primary',False) for x in r['reference_annotations']) for r in kept),
        no_label_use=True,no_new_split=True,no_reference_approved_by_filter=True,
        source_hashes={k:digest(p) for k,p in pp.items()})
    dump(O/'development_907_filter.json',rows);dump(O/'development_907_filter_summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
