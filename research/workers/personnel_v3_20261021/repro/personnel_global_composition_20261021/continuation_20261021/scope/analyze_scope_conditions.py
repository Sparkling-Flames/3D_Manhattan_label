"""Existing scope evidence and held-label ABC effects: an auxiliary reanalysis.

Never changes reference, eligibility, labels, scores or fusion.  A response
disagreement is not a semantic adjudication.  Explicit absent/unrecorded states
are retained.  All scientific counts derive from complete source tables.
"""
from __future__ import annotations
import os
for _key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_key] = '1'
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
STUDY = HERE.parents[1]
REPO = STUDY.parents[2]
INPUT = REPO / 'research/statistics/v2_evidence_audit_20261019/records.json.gz'
INDEX = REPO / 'research/workers/personnel_profiles_composition_20261020/source/tables/profiles/record_index.csv.gz'
EVENTS = STUDY / 'analysis/ABC_ALL_COMPONENT_EVENTS.csv.gz'
ATTACHMENT = REPO.parent / 'project_sources/01-scope-.md'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_csv(frame, name):
    path = HERE / name
    temporary = path.with_name(path.name + '.partial')
    compression = {'method': 'gzip', 'mtime': 0} if name.endswith('.gz') else None
    frame.to_csv(temporary, index=False, encoding='utf-8-sig', compression=compression)
    recovered = pd.read_csv(temporary, compression='gzip' if compression else None, low_memory=False)
    assert recovered.shape == frame.shape, (name, recovered.shape, frame.shape)
    if 'event_id' in frame and not frame.event_id.duplicated().any():
        assert set(recovered.event_id) == set(frame.event_id)
    os.replace(temporary, path)


def stringify(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def extract_images(records, image_ids):
    by_image = {}
    for record in records:
        if record['image_id'] in image_ids:
            by_image.setdefault(record['image_id'], []).append(record)
    rows = []
    for image_id, source_rows in sorted(by_image.items()):
        difficulties = [r['image_evidence'].get('difficulty_record') for r in source_rows]
        difficulties = [r for r in difficulties if r]
        signatures = {stringify(d) for d in difficulties}
        assert len(signatures) <= 1, ('image metadata varies across objects', image_id)
        d = difficulties[0] if difficulties else {}
        flags = d.get('reference_flags', {})
        def flag(name):
            value = flags.get(name)
            return {'True': True, 'False': False, True: True, False: False}.get(value, pd.NA)
        explicit = flag('scope_explicit_tag')
        ledger = flag('scope_existing_ledger')
        row = {
            'image_id': image_id,
            'image': source_rows[0]['image_code'],
            'building': source_rows[0]['building_id'],
            'difficulty_metadata_present': bool(d),
            'reference_target': d.get('target_version'),
            'reference_status': d.get('reference_status', 'not_recorded'),
            'scope_semantics': d.get('scope_semantics', 'not_recorded'),
            'reference_selection_reason': d.get('selection_reason', 'not_recorded'),
            'reference_H': d.get('H'),
            'inference_burden': d.get('inference_burden', 'not_recorded'),
            'prior_scope_explicit_tag': explicit,
            'prior_scope_ledger_flag': ledger,
            'prior_scope_comment_candidate': flag('scope_comment_candidate'),
            'prior_gt_detail_omission_flag': flag('gt_detail_omission_mark'),
            'prior_gt_substantive_error_flag': flag('gt_substantive_error_mark'),
            'expected_annotation_extent': source_rows[0]['image_evidence'].get('expected_annotation_extent'),
            'prior_scope_comparison_artifact': d.get('scope_comparison'),
            'metadata_evidence_text': d.get('evidence'),
            # These task-level axes have no bound values in the frozen source.
            'layout_policy': 'not_independently_recorded',
            'observability_status': 'not_independently_recorded',
            'visible_boundary_mask_status': 'not_available',
            'policy_accepted_reference_ids_status': 'not_independently_recorded',
            # Existing per-object review policy is retained verbatim as a set;
            # it must not be silently promoted into a task-level opening policy.
            'object_review_scope_policy_values': '|'.join(sorted({
                str(r['review_evidence']['scope_policy']) for r in source_rows
                if r['review_evidence'].get('scope_policy') is not None})),
        }
        if explicit is pd.NA or ledger is pd.NA:
            row['prior_scope_review'] = 'not_recorded'
        elif explicit or ledger:
            row['prior_scope_review'] = 'scope_flag_recorded'
        else:
            row['prior_scope_review'] = 'no_scope_flag_recorded'
        h = row['reference_H']
        row['reference_hidden_geometry'] = ('not_recorded' if h is None else
                                           'H0' if h == 0 else 'H_positive')
        rows.append(row)
    return pd.DataFrame(rows)


def response_panels(index):
    rows = []
    for keys, g in index.groupby(['image_id', 'condition', 'origin'], dropna=False):
        # Repeated historical objects from the same person are not independent
        # respondents.  Collapse only consistent reports; conflicting reports
        # remain an explicit unknown instead of choosing a convenient answer.
        states = []
        for worker, w in g.groupby('worker_id'):
            known = set(w.scope_response.dropna())
            assert known <= {'in_scope', 'out_of_scope'}
            states.append(next(iter(known)) if len(known) == 1 else
                          'no_response' if not known else 'within_worker_conflict')
        n_in = states.count('in_scope')
        n_out = states.count('out_of_scope')
        n_recorded = n_in + n_out
        p = n_out / n_recorded if n_recorded else np.nan
        state = ('no_recorded_response' if not n_recorded else
                 'mixed_in_out' if n_in and n_out else
                 'only_in_scope' if n_in else 'only_out_of_scope')
        rows.append(dict(zip(['image_id', 'condition', 'origin'], keys),
            records=len(g), workers=g.worker_id.nunique(), n_in=n_in, n_out=n_out,
            n_missing=states.count('no_response'),
            n_within_worker_conflict=states.count('within_worker_conflict'),
            repeated_object_count=len(g)-len(states), n_recorded=n_recorded,
            n_recorded_objects=int(g.scope_response.notna().sum()),
            out_response_rate=p,
            pairwise_response_disagreement=(2*n_in*n_out/(n_recorded*(n_recorded-1))
                                           if n_recorded > 1 else np.nan),
            response_state=state,
            scope_gold_opportunities=int(g.scope_opportunity.sum()),
            scope_gold_correct=int(g.scope_correct.eq(True).sum()),
            quality_usable_records=int(g.quality_usable.sum()),
            ordinary_quality_records=int(g.quality_use.eq('ordinary_primary').sum()),
            scope_is_correctness=False))
    return pd.DataFrame(rows)


def balanced_summary(events):
    spec = importlib.util.spec_from_file_location('unchanged_analysis', STUDY/'analysis/analyze_global.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    metrics = ['common_quality_within_abs', 'common_quality_cross_abs',
               'abs_Q_change_advantage', 'within_joint_stable_main',
               'cross_joint_stable_main', 'stable_advantage',
               'A_failure', 'B_failure', 'C_failure', 'any_arm_failure',
               'same_loss_gt5', 'cross_loss_gt5',
               'within_floor_jaccard_difference', 'cross_floor_jaccard_difference',
               'cross_minus_within_floor_jaccard_difference',
               'within_mean_height_prism_pair_difference',
               'cross_mean_height_prism_pair_difference',
               'cross_minus_within_mean_height_prism_pair_difference',
               'within_node_count_difference', 'cross_node_count_difference',
               'same_omission', 'cross_omission', 'net_omission',
               'same_extension', 'cross_extension', 'net_extension',
               'net_B8L2', 'net_D10']
    axes = ['prior_scope_review', 'new_source_response_state', 'reference_hidden_geometry']
    regimes = {
        'all_registered': np.ones(len(events), dtype=bool),
        'n_ge20_m_ge4': events.n.ge(20) & events.m_AB.ge(4),
        'n15_m_ge4': events.n.eq(15) & events.m_AB.ge(4),
    }
    summaries, buildings = [], []
    for regime, mask in regimes.items():
        e = events.loc[mask].copy()
        e['regime'] = regime
        for axis in axes:
            e['axis'] = axis
            e['stratum'] = e[axis]
            groups = ['regime', 'axis', 'stratum', 'condition', 'layer', 'method_id', 'tier', 'event_mode']
            s, b = module.balanced(e, metrics, groups)
            summaries.append(s); buildings.append(b)
    return pd.concat(summaries, ignore_index=True), pd.concat(buildings, ignore_index=True)


def within_difficulty_summary(events):
    spec = importlib.util.spec_from_file_location('unchanged_analysis_difficulty', STUDY/'analysis/analyze_global.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    metrics = ['common_quality_within_abs', 'common_quality_cross_abs',
               'within_joint_stable_main', 'cross_joint_stable_main', 'stable_advantage',
               'any_arm_failure', 'within_floor_jaccard_difference',
               'cross_floor_jaccard_difference', 'net_B8L2', 'net_D10']
    e = events[events.n.ge(20) & events.m_AB.ge(4)].copy()
    results = []
    for axis in ['prior_scope_review', 'new_source_response_state']:
        e['axis'] = axis; e['stratum'] = e[axis]
        groups = ['axis', 'stratum', 'condition', 'layer', 'difficulty', 'method_id', 'tier', 'event_mode']
        s, _ = module.balanced(e, metrics, groups)
        results.append(s)
    return pd.concat(results, ignore_index=True)


def main():
    records = json.load(gzip.open(INPUT, 'rt'))['records']
    index = pd.read_csv(INDEX)
    events = pd.read_csv(EVENTS, low_memory=False)
    assert len(index) == 9217
    assert len(events) == 12953 and not events.event_id.duplicated().any()
    images = extract_images(records, set(index.image_id))
    responses = response_panels(index)
    write_csv(images, 'SCOPE_IMAGE_EVIDENCE.csv')
    write_csv(responses, 'SCOPE_RESPONSE_PANELS.csv')
    e = events.merge(images.drop(columns=['image', 'building']), on='image_id',
                     how='left', validate='many_to_one')
    assert e.reference_id.eq(e.reference_target).all(), 'reference-specific metadata mismatch'
    new = responses[responses.origin.eq('new')].drop(columns='origin')
    rename = {c: 'new_source_'+c for c in new if c not in ['image_id', 'condition']}
    e = e.merge(new.rename(columns=rename), on=['image_id', 'condition'],
                how='left', validate='many_to_one')
    e['new_source_response_state'] = e.new_source_response_state.fillna('no_new_source_opportunity')
    e['any_arm_failure'] = e[['A_failure', 'B_failure', 'C_failure']].any(axis=1)
    # Preserve missing quality. Failure is not converted into a zero score.
    assert e[['common_quality_within_abs', 'common_quality_cross_abs']].notna().all(axis=1).equals(e.all_scored)
    linkage_columns = ['event_id', 'method_id', 'tier', 'event_mode', 'pool_id', 'image',
                       'image_id', 'building', 'condition', 'layer', 'difficulty',
                       'reference_id', 'reference_version', 'n', 'm_AB', 'm_AC', 'm_BC']
    added = [c for c in e if c not in events]
    write_csv(e[linkage_columns+added], 'SCOPE_EVENT_LINKAGE.csv.gz')
    summary, building = balanced_summary(e)
    write_csv(summary, 'SCOPE_STRATIFIED_ABC_SUMMARY.csv')
    write_csv(building, 'SCOPE_STRATIFIED_BUILDINGS.csv.gz')
    write_csv(within_difficulty_summary(e), 'SCOPE_WITHIN_DIFFICULTY_SUMMARY.csv')
    cross = e.groupby(['condition', 'layer', 'difficulty', 'prior_scope_review',
                      'new_source_response_state'], dropna=False).agg(
                      events=('event_id', 'size'), images=('image_id', 'nunique'),
                      buildings=('building', 'nunique')).reset_index()
    write_csv(cross, 'SCOPE_DIFFICULTY_CROSSTAB.csv')
    coverage = []
    for axis in ['prior_scope_review', 'new_source_response_state', 'reference_hidden_geometry']:
        for keys, g in e.groupby(['condition', 'layer', axis], dropna=False):
            coverage.append(dict(condition=keys[0], layer=keys[1], axis=axis, stratum=keys[2],
                                 events=len(g), pools=g.pool_id.nunique(), images=g.image_id.nunique(),
                                 buildings=g.building.nunique(), quality_common_events=int(g.all_scored.sum()),
                                 all_complete_events=int(g.all_complete.sum()),
                                 any_failure_events=int(g.any_arm_failure.sum())))
    write_csv(pd.DataFrame(coverage), 'SCOPE_EVENT_SUPPORT.csv')
    inventory_coverage = []
    for c in ['layout_policy', 'observability_status', 'visible_boundary_mask_status',
              'policy_accepted_reference_ids_status', 'prior_scope_review',
              'reference_hidden_geometry', 'reference_status']:
        for value, g in images.groupby(c, dropna=False):
            inventory_coverage.append(dict(field=c, value=value, images=len(g),
                behavior_records=int(index.image_id.isin(g.image_id).sum()),
                abc_events=int(events.image_id.isin(g.image_id).sum())))
    write_csv(pd.DataFrame(inventory_coverage), 'SCOPE_FIELD_SUPPORT.csv')
    selected = summary[(summary.regime=='n_ge20_m_ge4') &
                       (summary.event_mode=='cross_composition') &
                       (summary.axis.isin(['prior_scope_review', 'new_source_response_state'])) &
                       (((summary.method_id=='M_structure') & (summary.tier=='coarse')) |
                        (summary.method_id=='A2_relation') |
                        ((summary.method_id=='SP_scale') & (summary.tier=='coarse')) |
                        ((summary.method_id=='MV_QTD_manual_new') & (summary.tier=='fine')))]
    write_csv(selected, 'SCOPE_MAIN_RESULTS.csv')
    receipt = {
        'schema': 'scope_auxiliary_reanalysis_v1',
        'frozen_source_commit': '51b519f943b2dd3a4fb2f0198133ac5dd17209ab',
        'inputs': {str(p.relative_to(REPO)) if p.is_relative_to(REPO) else str(p): sha(p)
                   for p in [INPUT, INDEX, EVENTS, ATTACHMENT]},
        'behavior_records': len(index), 'behavior_images': len(images),
        'events': len(events), 'event_images': events.image_id.nunique(),
        'reference_metadata_exact_match_events': int(e.reference_id.eq(e.reference_target).sum()),
        'source_responses': responses.groupby(['condition', 'origin']).agg(
            tasks=('image_id', 'size'), recorded=('n_recorded', 'sum'),
            n_out=('n_out', 'sum'), gold=('scope_gold_opportunities', 'sum'),
            correct=('scope_gold_correct', 'sum')).reset_index().to_dict('records'),
        'task_level_opening_policy_adjudicated_images': 0,
        'task_level_observability_adjudicated_images': 0,
        'native_fusion_recomputed': 0,
        'qualification_reference_or_labels_changed': False,
        'source_events_sha256_unchanged': sha(EVENTS),
        'full_event_ids_preserved': set(e.event_id) == set(events.event_id),
        'caveats': [
            'Existing scope ledger flags and in/out response disagreement are not independently adjudicated opening policy or observability.',
            'Target response disagreement is a post-hoc descriptive stratum, not a held-building classifier input.',
            'H is frozen reference bottom-polygon self-occlusion under opaque-wall assumptions, not direct RGB observability.',
            'Building intervals reuse the existing 2000-resample descriptive procedure; no blind validation or multiplicity correction.',
            'No uploaded-document provisional image judgment is assigned to a repository image without an exact identity.'],
        'files': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)}
                  for p in HERE.iterdir() if p.is_file() and p.suffix in ('.csv', '.gz', '.py')},
    }
    path = HERE/'SCOPE_ANALYSIS_RECEIPT.json'
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: receipt[k] for k in ['behavior_records', 'behavior_images', 'events',
                                            'event_images', 'reference_metadata_exact_match_events']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
