#!/usr/bin/env python3
"""Apply the a7ff exposure registry in addition to the frozen qualification gates.

This is a consumer patch, not a change to the original split, labels or scores.
Run before any new calibration. Exposure is not treated as human review.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path

MAIN_SHA = 'a7ff459e992769c944541800dbe3be6e4b83ae4b'


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(p, obj):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf8')


def read_csv_typed(p):
    rows = list(csv.DictReader(Path(p).open(encoding='utf-8-sig')))
    for row in rows:
        for k, v in row.items():
            if v in ('True', 'False'):
                row[k] = v == 'True'
            elif v and v[0] in '[{':
                row[k] = json.loads(v)
    return rows


def count(rows):
    return dict(records=len(rows), unique_record_ids=len({r['record_id'] for r in rows}),
                images=len({r['image_id'] for r in rows}),
                buildings=len({r['building_id'] for r in rows}),
                original_analysis_groups=len({r['room_group'] for r in rows}),
                workers=len({r['worker_id'] for r in rows}),
                known_room_identifiers=len({(r['building_id'], r['room_id']) for r in rows if r.get('room_id')}),
                records_without_room_identifier=sum(not r.get('room_id') for r in rows),
                labels=dict(collections.Counter(r.get('effective_label', 'unlabeled') for r in rows)))


def exposure_barriers(record_id, room_group, frozen_holdout, exposure):
    """Explicit safeguards; no one can make exposed groups development by flipping a flag."""
    reasons = []
    if frozen_holdout:
        reasons.append('original_frozen_holdout')
    explicit = {r['record_id'] for r in exposure['screen_records_in_original_holdout'] if r['exclude_from_calibration']}
    if record_id in explicit:
        reasons.append('explicit_screen_exposure_calibration_exclusion')
    if room_group in exposure['groups_touched_by_this_screen']:
        reasons.append('original_holdout_group_with_screen_exposure')
    return reasons


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workspace', type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument('--out', type=Path)
    args = ap.parse_args(); W = args.workspace.resolve()
    O = args.out or W/'structure_height_preference_20261012/evidence/results'
    O.mkdir(parents=True, exist_ok=True)
    old = W/'top_structure_20261012/evidence/results'
    B = W/'previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010'
    ep = W/'structure_height_preference_20261012/inputs/main_snapshot/research/quality_holdout_exposure_correction_20261011/exposure_registry.json'
    ex = read(ep)
    old_audit = read(old/'qualification_summary.json')
    # Recheck every input hash used by the old audit; its result is historical evidence,
    # not an unsupported replacement for the underlying receipt or frozen split.
    prior_hash_checks = {}
    for k, p in old_audit['source_manifest'].items():
        prior_hash_checks[k] = sha(W/p['path']) == p['sha256']
    assert all(prior_hash_checks.values()), prior_hash_checks
    for rel, expected in ex['source_sha256'].items():
        assert sha(W/rel) == expected, rel
    hp = B/'results/room_holdout_manifest.csv'
    hold = {r['record_id']: r for r in csv.DictReader(hp.open(encoding='utf-8-sig'))}
    orig = [r for r in hold.values() if r['held_out_of_sample_and_future_calibration'] == 'True']
    groups = collections.Counter(r['room_group'] for r in orig)
    assert len(orig) == ex['original_heldout_records'] == 282
    assert len(groups) == ex['original_heldout_groups'] == 9
    touched = ex['groups_touched_by_this_screen']
    assert {g: groups[g] for g in touched} == touched
    untouched = {g: n for g, n in groups.items() if g not in touched}
    assert untouched == ex['groups_not_touched_by_this_screen']
    assert sum(untouched.values()) == ex['records_in_groups_not_touched_by_this_screen'] == 103

    screen = read_csv_typed(old/'qualification_ledger_115.csv')
    screen_by_id = {r['record_id']: r for r in screen}
    receipt = read(W/old_audit['source_manifest']['receipt']['path'])
    overlay = read(W/old_audit['source_manifest']['overlay']['path'])
    display = read(W/old_audit['source_manifest']['display']['path'])
    selection = read(W/old_audit['source_manifest']['selection']['path'])
    raw_by_case = {r['case_id']: r for r in receipt['answers']}
    overlay_by_case = {r['case_id']: r for r in overlay['records']}
    display_by_case = {r['id']: r for r in display['cases']}
    selection_by_case = {r['id']: r for r in selection['cases']}
    assert len(raw_by_case) == len(overlay_by_case) == len(screen) == 115
    for r in screen:
        raw = raw_by_case[r['case_id']]; over = overlay_by_case[r['case_id']]
        assert raw['judgment'] == over['original_judgment'] == r['original_label']
        assert r['effective_label'] == {'severe':'severe', 'borderline':'pending_borderline', 'unmarked':'unreviewed'}[raw['judgment']]
        assert r['scope_hold_reasons'] == over['calibration_scope_hold_reasons']
        assert selection_by_case[r['case_id']]['record_id'] == r['record_id']
    for e in ex['screen_records_in_original_holdout']:
        r = screen_by_id[e['record_id']]
        assert e['case_id'] == r['case_id']
        assert r['room_group'] == e['original_room_group'] == hold[r['record_id']]['room_group']
        assert r['original_holdout'] is True and e['exclude_from_calibration'] is True
        assert r['effective_label'] == {'not_reviewed': 'unreviewed', 'reviewed_severe': 'severe'}[e['effective_review_status']]
    assert {r['record_id'] for r in screen if r['original_holdout']} == {e['record_id'] for e in ex['screen_records_in_original_holdout']}

    for r in screen:
        h = hold[r['record_id']]
        extra = exposure_barriers(r['record_id'], h['room_group'], h['held_out_of_sample_and_future_calibration'] == 'True', ex)
        r['new_explicit_exposure_barriers'] = extra
        r['new_calibration_scope_and_geometry_allowed'] = r['conditional_complete_score_available'] and not extra
        r['new_calibration_human_label_available'] = r['new_calibration_scope_and_geometry_allowed'] and r['effective_label'] == 'severe'
        r['pending_is_fixed_label'] = False
        r['unreviewed_is_negative'] = False
    labeled39 = read(old/'numeric_evidence_39_metadata.json')
    for r in labeled39:
        h = hold[r['record_id']]
        r['explicit_exposure_barriers'] = exposure_barriers(r['record_id'], h['room_group'], h['held_out_of_sample_and_future_calibration'] == 'True', ex)
        assert not r['explicit_exposure_barriers'], r
        r['source_reference_newly_accepted'] = False
    p907 = read(old/'development_907_filter.json')
    for r in p907:
        h = hold[r['record_id']]
        r['explicit_exposure_barriers'] = exposure_barriers(r['record_id'], h['room_group'], h['held_out_of_sample_and_future_calibration'] == 'True', ex)
        r['new_descriptive_development_allowed'] = r['descriptive_development_allowed'] and not r['explicit_exposure_barriers']

    scores = read(W/'top_structure_20261012/analysis/results/candidate_scores_39.json')
    assert {r['record_id'] for r in scores} == {r['record_id'] for r in labeled39}
    objects = {r['object_id']: r for r in read(B/'inputs/current_formal_loader_data.json')['objects']}
    components = {r['record_id']: r for r in read(B/'results/current_components.json')}
    frozen = read(B/'inputs/current_geometry_compact.json')['geometries']
    source_geometry_checks = 0
    for r in screen:
        if not r['new_calibration_scope_and_geometry_allowed']:
            continue
        show = display_by_case[r['case_id']]
        ob = objects[r['object_id']]
        assert show['raw'] == ob['points_1024x512']
        assert ob['links_zero_based'] and ob['ordered_source_point_indices']
        for k in ['top3d', 'bottom3d']:
            assert show['annotation'][k] == frozen[r['object_id']][k]
            assert show['reference'][k] == frozen[r['reference_object_id']][k]
        source_geometry_checks += 1
    # Check whether the older screen gate's nonempty-list shorthand altered
    # eligibility. Do not propagate that shorthand to any new pool.
    nonrestrictive_screen = []
    for r in screen:
        c = components[r['record_id']]
        if c['reference_restrictions'] and not any(v.get('restrict_primary', False) for v in c['reference_restrictions']):
            nonrestrictive_screen.append(dict(case_id=r['case_id'], record_id=r['record_id'], restrictions=c['reference_restrictions'], barriers=r['barriers']))
    representation = []
    for s in scores:
        o = objects[s['object_id']]
        representation.append(dict(record_id=s['record_id'], case_id=s['old_case_id'] or s['new_case_id'],
            export_equals_current_before=(o['original_export_points'] == o['before_preprocessing_points']),
            current_before_equals_shared=(o['before_preprocessing_points'] == o['preprocessed_points']),
            old_numeric_pairing_basis=s['pairing_basis'],
            stored_ring_human_confirmed=bool(o.get('ring_confirmed')),
            current_pair_links_present=bool(o.get('links_zero_based')),
            ordered_source_point_indices_present=bool(o.get('ordered_source_point_indices')),
            explicit_not_oos_and_no_doorway=(o.get('scene_oos_status') == 'not_oos' and o.get('scene_doorway_status') == 'none'),
            formal_gate=o.get('main_quality_gate', {}).get('status'),
            original_export_sha256=hashlib.sha256(json.dumps(o['original_export_points'], sort_keys=True).encode()).hexdigest(),
            current_before_sha256=hashlib.sha256(json.dumps(o['before_preprocessing_points'], sort_keys=True).encode()).hexdigest(),
            shared_sha256=hashlib.sha256(json.dumps(o['preprocessed_points'], sort_keys=True).encode()).hexdigest()))
    allowed15 = [r['record_id'] for r in screen if r['new_calibration_scope_and_geometry_allowed'] and r['effective_label'] in ('severe','pending_borderline')]
    assert len(allowed15) == 15
    old24 = [r for r in labeled39 if r['case_id'].startswith('T')]
    kept907 = [r for r in p907 if r['new_descriptive_development_allowed']]
    summary = dict(main_sha=MAIN_SHA, explicitly_applied_exposure_sha256=sha(ep),
        source_hashes_rechecked=prior_hash_checks,
        original_receipt_and_overlay_labels_rechecked=115,
        frozen_display_geometry_exact_matches=source_geometry_checks,
        original_holdout_records=len(orig), original_holdout_groups=len(groups),
        exposed_records=14, exposed_groups=len(touched), exposed_groups_total_records=sum(touched.values()),
        groups_not_in_this_screen_records=sum(untouched.values()), clean_validation_certified=False,
        old24=count(old24), numerical39=count(labeled39), descriptive907=count(kept907),
        screen115=count(screen), known_barrier_free81=count([r for r in screen if r['known_barrier_free']]),
        after_scope98=count([r for r in screen if not r['scope_hold_reasons']]),
        after_scope_and_original_holdout85=count([r for r in screen if not r['scope_hold_reasons'] and not r['original_holdout']]),
        complete65=count([r for r in screen if r['new_calibration_scope_and_geometry_allowed']]),
        missing_complete_geometry16=count([r for r in screen if r['known_barrier_free'] and not r['new_calibration_scope_and_geometry_allowed']]),
        missing_complete_geometry_ids=[r['case_id'] for r in screen if r['known_barrier_free'] and not r['new_calibration_scope_and_geometry_allowed']],
        severe_complete9=count([r for r in screen if r['new_calibration_scope_and_geometry_allowed'] and r['effective_label']=='severe']),
        pending_complete6=count([r for r in screen if r['new_calibration_scope_and_geometry_allowed'] and r['effective_label']=='pending_borderline']),
        delta_old39_removed=39-len(labeled39), delta_old907_removed=907-len(kept907),
        nonrestrictive_annotation_in_screen=nonrestrictive_screen,
        current39_representation=dict(records=len(representation),
            export_current_equal=sum(r['export_equals_current_before'] for r in representation),
            current_before_shared_equal=sum(r['current_before_equals_shared'] for r in representation),
            reliable_stored_pair_links=sum(r['current_pair_links_present'] and r['ordered_source_point_indices_present'] for r in representation),
            explicitly_human_ring_confirmed=sum(r['stored_ring_human_confirmed'] for r in representation),
            explicit_applicability=sum(r['explicit_not_oos_and_no_doorway'] for r in representation)),
        interpretation=['The new registry is an explicit additional consumer guard even though the eligible IDs do not change.',
            'Frozen geometry and stored links are calculability evidence, not new reference acceptance or human ring confirmation.',
            'The 50 complete unreviewed screen cases are not negatives; missing geometry is not a zero score.',
            'Groups absent from this one screen are not certified independent validation.',
            'W019 conditional diagnostics/calibration authorization does not restore formal personnel eligibility.'])
    write(O/'qualification_summary.json', summary)
    write(O/'qualification_ledger_115.json', screen)
    write(O/'numerical_evidence_39.json', labeled39)
    write(O/'allowed_screen_numerical_ids.json', allowed15)
    write(O/'development_907_filter.json', p907)
    write(O/'representation_versions_39.json', representation)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
