#!/usr/bin/env python3
"""Read-only, independent qualification and exposure audit for the top/structure study.

Reads original receipts, overlay, frozen holdout, formal loader and reference registry.
Does not infer grades from comments, impute geometry, or alter any original gate.
"""
from __future__ import annotations
import argparse, collections, csv, hashlib, itertools, json, math
from pathlib import Path

def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p, d):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
def csvout(p, rows):
    if not rows: return
    with Path(p).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})
def count_unit(rows):
    rooms={(r['building_id'],r['room_id']) for r in rows if r['room_id']}
    return dict(records=len(rows), unique_records=len({r['record_id'] for r in rows}),
        labels=dict(collections.Counter(r.get('effective_label','unlabeled') for r in rows)),
        images=len({r['image_id'] for r in rows}), buildings=len({r['building_id'] for r in rows}),
        workers=len({r['worker_id'] for r in rows}),known_room_identifiers=len(rooms),
        records_missing_room_identifier=sum(not r['room_id'] for r in rows),
        images_with_missing_room_identifier=len({r['image_id'] for r in rows if not r['room_id']}),
        original_analysis_groups=len({r['room_group'] for r in rows}),
        grouping_note='known room identifiers do not include missing-room records; original groups may substitute whole buildings and are not a count of physical rooms')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workspace',type=Path,default=Path.cwd())
    ap.add_argument('--previous',type=Path);ap.add_argument('--main-snapshot',type=Path)
    ap.add_argument('--out',type=Path);a=ap.parse_args();W=a.workspace.resolve()
    P=a.previous or W/'previous_research/quality_calibration_research_20261011'
    B=P/'inputs_extracted/quality_cloud_compute_review_20261010'
    N=a.main_snapshot or W/'new_main_snapshot';O=a.out or W/'top_structure_20261012/evidence/results';O.mkdir(parents=True,exist_ok=True)
    sources=dict(receipt=N/'research/quality_severe_feedback_20261011/original_receipt.json',
        overlay=N/'research/quality_severe_feedback_20261011/feedback_overlay.json',
        selection=N/'research/quality_severe_screen_20261011/selection_private.json',
        display=N/'research/quality_severe_screen_20261011/review_data.json',
        formal=B/'inputs/current_formal_loader_data.json',components=B/'results/current_components.json',
        geometry=B/'inputs/current_geometry_compact.json',registry=B/'inputs/reference_exclusion_registry_20261010.json',
        holdout=B/'results/room_holdout_manifest.csv',prior_ledger=W/'study_severe/results/ledger_115.json',
        old24_evidence=W/'study_borderline/results/old24_evidence.json',
        old30_receipt=P/'inputs_extracted/pro_quality_calibration_handoff_20261011/user_originals/quality_review30_receipt.json',
        previous_candidate_scores=W/'study_quality/results/candidate_scores.json')
    hashes={k:digest(p) for k,p in sources.items()}
    receipt=read(sources['receipt']);overlay=read(sources['overlay']);select=read(sources['selection']);display=read(sources['display'])
    formal=read(sources['formal']);objects={r['object_id']:r for r in formal['objects']};components={r['record_id']:r for r in read(sources['components'])}
    geom=read(sources['geometry'])['geometries'];reg=read(sources['registry'])
    hold={r['record_id']:r for r in csv.DictReader(sources['holdout'].open(encoding='utf-8-sig'))}
    old_ledger={r['case_id']:r for r in read(sources['prior_ledger'])}
    answer={r['case_id']:r for r in receipt['answers']};over={r['case_id']:r for r in overlay['records']};show={r['id']:r for r in display['cases']}
    assert len(answer)==len(over)==len(select['cases'])==len(show)==115
    assert len({r['record_id'] for r in select['cases']})==115
    assert overlay['original_receipt_sha256']==hashes['receipt']
    assert receipt['dataset_id']==overlay['dataset_id']==select['dataset_id']==display['dataset_id']
    assert hashlib.sha256(json.dumps(display['cases'],sort_keys=True).encode()).hexdigest()==receipt['dataset_id']
    for name,label in [('severe_cases_25.json','severe'),('borderline_cases_11.json','borderline'),('unreviewed_cases_79.json','unmarked')]:
        assert read(N/'research/quality_severe_feedback_20261011'/name)['records']==[r for r in overlay['records'] if r['original_judgment']==label]
    image_blocks={}
    for sec in ['confirmed_reference_exclusions','preserved_user_analysis_holds','reference_evidence_conflicts_primary_research_quarantine']:
        for r in reg[sec]: image_blocks.setdefault(r['image_id'],[]).append(sec)
    image_hold={r['image_id']:r for r in reg['all_current_hold_images'] if all(k.startswith('hold_') or k in {'excluded','out_of_primary_scene'} for k in r['gate_counts'])}
    rows=[]
    for s in select['cases']:
        cid=s['id'];raw=answer[cid];ov=over[cid];r=components[s['record_id']];obj=objects[s['object_id']]
        assert raw['judgment']==ov['original_judgment']==old_ledger[cid]['original_judgment']
        assert r['object_id']==s['object_id']==ov['object_id'] and r['image_id']==obj['image_id']
        scoped=list(ov['calibration_scope_hold_reasons']);held=hold[r['record_id']]['held_out_of_sample_and_future_calibration']=='True'
        barriers=list(scoped)
        if held:barriers.append('frozen_room_holdout')
        if r['image_id'] in image_blocks:barriers.append('existing_reference_registry_or_image_hold')
        if r['reference_restrictions'] or r['reference_strict_reasons']:barriers.append('existing_reference_restriction_or_strict_unavailable')
        gate=obj.get('main_quality_gate',{}).get('status','')
        if gate.startswith('hold_') or gate=='out_of_primary_scene':barriers.append('original_record_analysis_hold')
        if r['image_id'] in image_hold:barriers.append('existing_image_wide_analysis_hold')
        barriers=list(dict.fromkeys(barriers));ok=not barriers
        assert barriers==old_ledger[cid]['applicability_barriers'],(cid,barriers,old_ledger[cid]['applicability_barriers'])
        frozen=(s['mode']=='frozen_geometry')
        # Verify stored source equality only for known-barrier-free rows; do not evaluate holdout effects.
        available=False
        if ok and frozen:
            g=geom[s['object_id']];gt=geom[s['reference_object_id']]
            assert show[cid]['raw']==obj['points_1024x512']
            assert all(show[cid]['annotation'][k]==g[k] and show[cid]['reference'][k]==gt[k] for k in ['top3d','bottom3d'])
            assert obj['links_zero_based'] and obj['ordered_source_point_indices']
            assert all(len(g[k])>=3 and all(len(v)==3 and all(math.isfinite(x) for x in v) for v in g[k]) for k in ['top3d','bottom3d'])
            available=True
        assert available==old_ledger[cid]['full_Q_calibration_ready']
        effective={'severe':'severe','borderline':'pending_borderline','unmarked':'unreviewed'}[raw['judgment']]
        row=dict(case_id=cid,record_id=r['record_id'],object_id=r['object_id'],image_id=r['image_id'],image_code=r['image_code'],
            building_id=r['building_id'],room_id=r.get('room_id') or '',room_group=hold[r['record_id']]['room_group'],worker_id=r['worker_id'],
            original_label=raw['judgment'],effective_label=effective,comment_is_label=False,confidence=raw.get('confidence'),
            scope_hold_reasons=scoped,original_holdout=held,barriers=barriers,known_barrier_free=ok,
            geometry_mode=s['mode'],conditional_complete_score_available=available,
            explicit_not_oos_and_no_doorway=(obj.get('scene_oos_status')=='not_oos' and obj.get('scene_doorway_status')=='none'),
            final_reference_acceptance=False,recorded_formal_quality_gate=gate,formal_personnel_eligibility_unchanged=True,
            W019_formal_personnel_prohibited=(r['worker_id']=='W019'),unreviewed_is_negative=False,
            ring_human_confirmed=bool(obj.get('ring_confirmed')),reference_object_id=r['reference_object_id'])
        rows.append(row)
    stages={
        'screen_received_115':rows,
        'after_scope_98':[r for r in rows if not r['scope_hold_reasons']],
        'after_scope_and_original_holdout_85':[r for r in rows if not r['scope_hold_reasons'] and not r['original_holdout']],
        'known_barrier_free_81':[r for r in rows if r['known_barrier_free']],
        'conditional_complete_score_65':[r for r in rows if r['conditional_complete_score_available']],
        'severe_known_barrier_free_16':[r for r in rows if r['known_barrier_free'] and r['effective_label']=='severe'],
        'severe_complete_score_9':[r for r in rows if r['conditional_complete_score_available'] and r['effective_label']=='severe'],
        'borderline_complete_score_6':[r for r in rows if r['conditional_complete_score_available'] and r['effective_label']=='pending_borderline'],
        'missing_complete_geometry_16':[r for r in rows if r['known_barrier_free'] and not r['conditional_complete_score_available']]}
    oldreceipt=read(sources['old30_receipt']);oldanswers={r['case_id']:r for r in oldreceipt['answers']};old24=[]
    for e in read(sources['old24_evidence']):
        r=components[e['record_id']];a0=oldanswers[e['case_id']]
        assert a0==e['original_answer'];assert not e['held_out'];assert hold[r['record_id']]['held_out_of_sample_and_future_calibration']=='False'
        old24.append(dict(case_id=e['case_id'],record_id=r['record_id'],object_id=r['object_id'],image_id=r['image_id'],image_code=r['image_code'],
            building_id=r['building_id'],room_id=r.get('room_id') or '',room_group=hold[r['record_id']]['room_group'],worker_id=r['worker_id'],
            effective_label=a0['absolute_quality'],confidence=a0['confidence'],confidence_unknown=(a0['confidence']=='')))
    score39=old24+[r for r in rows if r['conditional_complete_score_available'] and r['effective_label'] in ['severe','pending_borderline']]
    assert len(score39)==len({r['record_id'] for r in score39})==39
    assert {r['record_id'] for r in score39}=={r['record_id'] for r in read(sources['previous_candidate_scores'])}
    stages['old24_quality']=old24;stages['numeric_labels_39']=score39
    units={k:count_unit(v) for k,v in stages.items()}
    heldrows=[r for r in rows if r['original_holdout']];touched={r['room_group'] for r in heldrows}
    origheld=[r for r in hold.values() if r['held_out_of_sample_and_future_calibration']=='True'];allgroups=collections.Counter(r['room_group'] for r in origheld)
    exposure=dict(original_holdout_records=len(origheld),original_holdout_groups=len(allgroups),screen_material_records=len(heldrows),
        raw_effective_labels=dict(collections.Counter(r['effective_label'] for r in heldrows)),
        screen_touch_groups={g:allgroups[g] for g in sorted(touched)},
        groups_not_touched_by_this_screen={g:n for g,n in sorted(allgroups.items()) if g not in touched},
        untouched_by_this_screen_is_not_clean_test_certification=True,
        explanation='Exposure records concern inclusion in material, not proof that every unreviewed record was inspected. No new split. No holdout score effects computed.')
    assert len(heldrows)==14 and len(touched)==4 and sum(n for g,n in allgroups.items() if g not in touched)==103
    assert sum(bool(r['scope_hold_reasons']) and r['original_holdout'] for r in rows)==1
    checks={'label_attachments_equal_original_overlay':True,'original_holdout_preserved':True,'prior_115_barriers_exactly_reproduced':True,
        'source_frozen_geometry_equality_on_65':True,'39_distinct_numerical_label_ids_match':True,'unreviewed_not_negative':True,
        'no_new_grade_or_formal_gate':True,'no_missing_score_imputed':True,'all_input_hashes_unchanged':hashes=={k:digest(p) for k,p in sources.items()}}
    summary=dict(schema='top_structure_qualification_audit_v1',main_sha='38e259c043fed0817307dbc3d21c6dba06bd6662',dataset_id=receipt['dataset_id'],
        count_units=units,checks=checks,source_manifest={k:dict(path=str(p.relative_to(W)),sha256=hashes[k]) for k,p in sources.items()},
        known_barrier_free_explicit_scope_ids=[r['case_id'] for r in rows if r['known_barrier_free'] and r['explicit_not_oos_and_no_doorway']],
        existing_image_wide_hold_ids=[r['case_id'] for r in rows if 'existing_image_wide_analysis_hold' in r['barriers']],
        missing_complete_geometry_ids=[r['case_id'] for r in stages['missing_complete_geometry_16']],
        W019_known_barrier_free=count_unit([r for r in rows if r['known_barrier_free'] and r['worker_id']=='W019']),
        caveats=['Known-barrier-free does not certify reference acceptance.','Frozen source equality does not newly certify a human ring.',
            '164 label pairs are dependent comparisons from 24 chosen records, not 164 subjects.',
            'No unreviewed record is an accepted non-severe control.','Old24 and the severe screen use different wording and selection purposes.'])
    dump(O/'qualification_summary.json',summary);dump(O/'qualification_ledger_115.json',rows);csvout(O/'qualification_ledger_115.csv',rows)
    dump(O/'holdout_exposure_preserved.json',exposure);dump(O/'holdout_exposure_records_14.json',heldrows)
    dump(O/'numeric_evidence_39_metadata.json',score39);csvout(O/'count_units.csv',[dict(stage=k,**{n:v for n,v in u.items() if n!='grouping_note'}) for k,u in units.items()])
    print(json.dumps(dict(count_units=units,checks=checks),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
