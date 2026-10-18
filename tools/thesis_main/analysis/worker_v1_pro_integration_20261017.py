"""数据v1修订：消费真实团队结果，桥接Pro纠错、scope与审核候选证据。"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..data_prep.consolidate_research_input import load_current_bundle

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / 'research/workers/worker_v1_composition_20261017'
PRO = ROOT / 'inputs/local_reviews/personnel_quality_pro_20261017/study/reliability'
FUSION = ROOT / 'research/fusion/wall_consensus_v1_process_20261017'
STATS = ROOT / 'research/statistics/v1_integrated_analysis_20261017'
OUT = ROOT / 'research/workers/worker_v1_pro_integration_20261017'
SOURCES = {}
RESIDUAL_QUOTES = {
    'b62a4df9e1645fe7': '这个改了一点模型的预标注,但是还是不太对',
    '717840fe8221eba6': '这个改了一点模型的预标注,但是还是不太对',
    '28935ccbb578589d': '这错误预标注他也没改对',
}
CANDIDATE_NAMES = {'strict_specific_personal_severe': 'pro_candidate_specific_reason',
                   'reviewer_personal_nonacceptance': 'pro_candidate_broad_nonacceptance'}


def source(path):
    stat = path.stat()
    SOURCES[str(path.relative_to(ROOT))] = dict(bytes=stat.st_size, mtime_ns=stat.st_mtime_ns)
    return path


def frame(path):
    return pd.read_csv(source(path)).rename(columns=CANDIDATE_NAMES)


def read(path):
    return json.loads(source(path).read_text(encoding='utf-8'))


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def table(name, value):
    pd.DataFrame(value).to_csv(OUT / name, encoding='utf-8-sig', index=False)


def corrected_residual_statement(object_id, comments, edit_status):
    return (edit_status == 'changed_coordinates' and object_id in RESIDUAL_QUOTES
            and RESIDUAL_QUOTES[object_id] in comments)


def compatible_clear_scope(eligible, gold, scene, oos_subtype):
    return bool(eligible and gold == 'in_scope' and scene == 'clear' and oos_subtype == 'not_oos')


def pure_focus_prefix(supported, focus_available, k):
    return bool(supported and focus_available >= k)


def reliability(bundle, old):
    correction = frame(PRO / 'correction_object_ledger.csv')
    semi = frame(PRO / 'semi_scores_b8l2_d10.csv')
    init = frame(PRO / 'initialization_evidence_574.csv')
    scope = frame(PRO / 'scope_object_ledger.csv')
    candidates = frame(PRO / 'exclusion_reason_candidates.csv')
    objects = {o['object_id']: o for o in bundle['data']['objects'] if o['object_kind'] == 'annotation'}
    assert len(correction) == len(semi) == len(init) == 574
    assert set(correction.object_id) == set(old.loc[old.condition.eq('semi'), 'object_id'])
    for data in [correction, semi, init, scope, candidates]:
        assert data.object_id.is_unique
        for row in data.itertuples():
            obj = objects[row.object_id]
            assert (obj['worker_id'], obj['image_id'], obj['condition']) == (row.worker_id, row.image_id, row.condition)
            assert obj['cleaning_disposition'] == row.cleaning_disposition
    correction['pro_original_residual_after_edit_statement'] = correction.reviewer_residual_after_edit_statement
    comments = {}
    for oid in correction.object_id:
        evidence = objects[oid]['review_evidence']
        text = [evidence.get('current_decision_comment', ''), evidence.get('current_comment', ''),
                *[r['record'].get('comment', '') for r in evidence.get('review_history', [])]]
        comments[oid] = list(dict.fromkeys(x for x in text if x))
    correction['reviewer_residual_after_edit_statement'] = [corrected_residual_statement(r.object_id, comments[r.object_id],
        r.recovered_edit_status) for r in correction.itertuples()]
    three = correction[correction.reviewer_residual_after_edit_statement]
    assert set(three.object_id) == set(RESIDUAL_QUOTES)
    assert three.source_verdict.eq('usable').all() and not three.confirmed_initialization_error_opportunity.any()
    correction['residual_statement_quote'] = correction.object_id.map(RESIDUAL_QUOTES)
    correction['source_comments_verified'] = correction.object_id.map(lambda oid: json.dumps(comments[oid], ensure_ascii=False))
    correction['reviewer_statement_is_error_specific_gold'] = False
    correction['statement_adoption'] = np.where(correction.reviewer_residual_after_edit_statement,
        'reviewer_observed_remaining_issue_mechanism_not_fully_specified_usable_preserved', 'no_adopted_post_edit_residual_statement')
    assert correction.confirmed_initialization_error_opportunity.sum() == 156
    assert correction.known_error_unchanged.sum() == 25
    assert correction.changed_error_specific_residual_unknown.sum() == 131
    table('semi_correction_evidence.csv', correction)
    table('semi_initialization_scores.csv', semi)
    table('initialization_evidence.csv', init)
    bridge = old[old.condition.eq('semi')][['object_id', 'worker_id', 'image_id', 'building_id',
        'known_wrong_initialization_opportunity', 'explicit_error_remains', 'semi_error_state']].rename(columns={
            'known_wrong_initialization_opportunity': 'old_opportunity', 'explicit_error_remains': 'old_unrepaired_or_comment'})
    bridge['old_unchanged_opportunity'] = bridge.semi_error_state.eq('confirmed_wrong_initialization_unrepaired')
    bridge = bridge.merge(correction[['object_id', 'confirmed_initialization_error_opportunity', 'known_error_unchanged',
        'changed_error_specific_residual_unknown', 'reviewer_residual_after_edit_statement', 'source_verdict']], on='object_id', validate='one_to_one')
    bridge = bridge.rename(columns={'confirmed_initialization_error_opportunity': 'strong_gold_opportunity',
                                    'known_error_unchanged': 'strong_gold_unchanged'})
    bridge['definition_relation'] = np.select([bridge.old_opportunity & bridge.strong_gold_opportunity,
        bridge.old_opportunity, bridge.strong_gold_opportunity], ['both', 'legacy_natural_trap_label_only',
        'strong_gold_only_historically_excluded_worker'], default='neither')
    table('correction_definition_bridge.csv', bridge)
    assert bridge.old_opportunity.sum() == 288 and bridge.old_unrepaired_or_comment.sum() == 39
    assert (bridge.old_opportunity & bridge.strong_gold_opportunity).sum() == 144
    assert set(bridge.loc[~bridge.old_opportunity & bridge.strong_gold_opportunity, 'worker_id']) == {'W019', 'W026'}
    # Scope gold is historical; the compatibility filter is not a new adjudication.
    scope['historical_gold_current_clear_compatible'] = [compatible_clear_scope(r.historical_eligible,
        r.historical_task_gold, r.scene, r.oos_subtype) for r in scope.itertuples()]
    assert scope.historical_gold_current_clear_compatible.equals(scope.current_clear_in_scope_adjudicated)
    scope = scope.rename(columns={'current_clear_in_scope_adjudicated': 'pro_original_current_clear_adjudicated_flag'})
    scope['current_target_gold_independently_adjudicated_here'] = False
    scope['scope_interpretation'] = 'historical_task_gold_plus_current_clear_compatibility_only'
    table('scope_evidence.csv', scope)
    candidates['subjective_magnitude_basis'] = candidates.error_type.eq('gross_deformation')
    candidates['OOS_geometry_policy_dispute'] = candidates.condition.eq('oos') & candidates.error_type.eq('missing_or_unpaired_points')
    candidates['scope_context_ambiguity'] = candidates.policy_ambiguous | candidates.object_id.eq('58a8d69137385a19')
    candidates['exclusion_attribution_pending'] = candidates.object_id.eq('f21c670566821ce7')
    candidates['independent_severity_adjudicated_here'] = False
    candidates['candidate_interpretation'] = 'recoding_of_existing_85_exclusions_not_new_observations_or_universal_severity_gold'
    assert candidates.pro_candidate_specific_reason.sum() == 25
    assert candidates.pro_candidate_broad_nonacceptance.sum() == 68
    table('exclusion_candidate_evidence.csv', candidates)
    cols = ['object_id', 'worker_id', 'image_id', 'image_code', 'building_id', 'condition', 'cleaning_disposition',
        'reference_id', 'reference_version', 'in_Q_training', 'quality_usable', 'quality_use', 'is_doorway', 'is_oos',
        'pool_analysis_eligible', 'pool_vote_eligible', 'historical_worker_exclusion', 'primary_reason',
        'individually_reviewed', 'final_review_verdict',
        'source_active_time_seconds', 'target_matched_time_seconds', 'B8L2', 'D10', 'confirmed_person_error_exclusion']
    records = old[cols].rename(columns={'confirmed_person_error_exclusion': 'legacy_explicit_person_error_exclusion'})
    ccols = ['object_id', 'pro_candidate_specific_reason', 'pro_candidate_broad_nonacceptance', 'subjective_magnitude_basis',
        'OOS_geometry_policy_dispute', 'scope_context_ambiguity', 'exclusion_attribution_pending', 'reason_code', 'error_type']
    # Candidate presence is a coding flag; absence is not an accepted/error-free label.
    records = records.merge(candidates[ccols], on='object_id', how='left', validate='one_to_one')
    scope_cols = ['object_id', 'raw_binding_verified', 'worker_scope', 'raw_scope_recorded', 'historical_task_gold',
        'historical_gold_source', 'historical_eligible', 'historical_outcome', 'historical_later_hold',
        'historical_gold_current_clear_compatible', 'current_compatible_outcome', 'current_task_judgement_unknown']
    records = records.merge(scope[scope_cols].rename(columns={x: 'scope_' + x for x in scope_cols if x != 'object_id'}),
                            on='object_id', how='left', validate='one_to_one')
    scol = ['object_id', 'confirmed_initialization_error_opportunity', 'known_error_unchanged',
        'changed_error_specific_residual_unknown', 'reviewer_residual_after_edit_statement', 'recovered_edit_status', 'error_specific_residual_state']
    records = records.merge(correction[scol], on='object_id', how='left', validate='one_to_one')
    gains = ['initial_B8L2', 'final_B8L2', 'worker_attributable_gain_B8L2', 'initial_D10', 'final_D10',
        'worker_attributable_gain_D10', 'paired_score_available', 'current_qualified_gain_available',
        'semi_ordinary_profile_training_candidate', 'researcher_point_repair_applied', 'initial_score_reasons', 'final_score_reasons']
    records = records.merge(semi[['object_id'] + gains], on='object_id', how='left', validate='one_to_one')
    records['data_release'] = 'v1'
    records['analysis_revision'] = 'worker_v1_pro_integration_20261017'
    table('record_evidence.csv', records)
    ordinary = semi[semi.current_qualified_gain_available & semi.current_quality_use.eq('ordinary_primary')]
    assert len(ordinary) == 437 and semi.semi_ordinary_profile_training_candidate.sum() == 409
    summaries = []
    for worker, group in records.groupby('worker_id'):
        sg = semi[semi.worker_id.eq(worker)]
        cg = correction[correction.worker_id.eq(worker)]
        og = ordinary[ordinary.worker_id.eq(worker)]
        r = dict(worker_id=worker, canonical_submissions=len(group), Q_training=int(group.in_Q_training.sum()),
            individually_reviewed_records=int(group.individually_reviewed.sum()),
            individual_review_coverage=group.individually_reviewed.mean(),
            original_review_exclusions=int(group.cleaning_disposition.eq('excluded_by_review').sum()),
            specific_reason_candidates=int(group.pro_candidate_specific_reason.sum()),
            broad_nonacceptance_candidates=int(group.pro_candidate_broad_nonacceptance.sum()),
            subjective_magnitude_candidates=int(group.subjective_magnitude_basis.sum()),
            OOS_geometry_policy_disputes=int(group.OOS_geometry_policy_dispute.sum()),
            semi_inventory=len(sg), recovered_initializations=int(sg.initialization_source_verified.sum()),
            semi_without_strong_defect_gold=int((~cg.confirmed_initialization_error_opportunity).sum()),
            semi_initial_measurement_unavailable=int(sg.initial_score_status.ne('complete').sum()),
            semi_final_measurement_unavailable=int(sg.final_score_status.ne('complete').sum()),
            historical_whole_worker_excluded_records=int(group.historical_worker_exclusion.sum()),
            strong_defect_opportunities=int(cg.confirmed_initialization_error_opportunity.sum()),
            strong_defect_unchanged=int(cg.known_error_unchanged.sum()),
            strong_defect_edited_outcome_unknown=int(cg.changed_error_specific_residual_unknown.sum()),
            reviewer_residual_after_edit_statements=int(cg.reviewer_residual_after_edit_statement.sum()),
            ordinary_compatible_gain_rows=len(og), ordinary_semi_training_rows=int(sg.semi_ordinary_profile_training_candidate.sum()),
            no_composite_penalty=True)
        for metric in ['B8L2', 'D10']:
            r[metric + '_ordinary_initial_mean'] = og['initial_' + metric].mean()
            r[metric + '_ordinary_final_mean'] = og['final_' + metric].mean()
            r[metric + '_ordinary_gain_mean'] = og['worker_attributable_gain_' + metric].mean()
        summaries.append(r)
    summary = pd.DataFrame(summaries)
    table('person_evidence_summary.csv', summary)
    profiles = frame(OLD / 'person_profiles.csv')
    semi_profiles = frame(PRO / 'semi_fold_profiles.csv')
    sf = semi_profiles[semi_profiles.panel.eq('ordinary_main') & semi_profiles.fold.eq('full_descriptive')]
    sf = sf[['worker_id', 'axis', 'effect', 'supported', 'contexts', 'buildings']].rename(columns={
        'axis': 'metric', 'effect': 'Semi_effect', 'supported': 'Semi_supported', 'contexts': 'Semi_contexts', 'buildings': 'Semi_buildings'})
    persons = profiles.merge(summary, on='worker_id', validate='many_to_one').merge(sf, on=['worker_id', 'metric'], how='left', validate='one_to_one')
    table('person_profiles_and_evidence.csv', persons)
    table('scope_worker_opportunities.csv', scope.groupby(['worker_id', 'condition']).agg(
        submissions=('object_id', 'size'), historical_gold=('historical_gold_ready', 'sum'),
        historical_eligible=('historical_eligible', 'sum'), current_clear_compatible=('historical_gold_current_clear_compatible', 'sum'),
        current_task_unknown=('current_task_judgement_unknown', 'sum')).reset_index())
    table('scope_outcome_counts.csv', scope.groupby(['worker_id', 'condition', 'historical_gold_current_clear_compatible',
        'historical_outcome', 'current_compatible_outcome'], dropna=False).size().rename('n').reset_index())
    for filename in ['semi_fold_profiles.csv', 'semi_lobo_performance.csv', 'semi_final_gain_effect_equivalence.csv']:
        table(filename, frame(PRO / filename))
    qfits = frame(ROOT / 'research/workers/worker_b8l2_d10_20261017/fold_profiles.csv')
    table('doorway_specialist_profiles.csv', qfits[qfits.panel.eq('doorway')])
    return records, bridge, ordinary


def team_results():
    requests = read(OLD / 'TEAM_REQUESTS.json')
    results = frame(FUSION / 'TEAM_RESULTS.csv')
    assert results.request_id.is_unique
    original = {r['request_id']: r for r in requests['teams']}
    assert set(results.request_id) == set(original)
    meta = pd.DataFrame([dict(request_id=r['request_id'], image_id=r['image_id'], image_code=r['image_code'],
        building_id=r['building_id'], scene_bucket=r['scene_bucket'], request_k=r['k'],
        requested_worker_ids='|'.join(r['worker_ids'])) for r in requests['teams']])
    results = meta.merge(results, on='request_id', validate='one_to_one')
    complete = results.status.eq('completed')
    for r in results[complete].itertuples():
        assert set(r.worker_ids.split('|')) == set(original[r.request_id]['worker_ids'])
        assert r.k == r.request_k
    results['profile_application'] = np.where(results.scene_bucket.eq('doorway_only'),
        'ordinary_QT_to_doorway_transfer', 'ordinary_QT_on_ordinary_pool')
    results['fixed_member_D10_minus_B8L2'] = results.D10 - results.B8L2
    results['metric_change_interpretation'] = 'same_members_different_direction_scale_not_annotation_improvement'
    table('team_results.csv', results)
    coverage = []
    for scene, d in results.groupby('scene_bucket'):
        coverage.append(dict(scene_bucket=scene, planned_images=d.image_id.nunique(),
            completed_images=d.loc[d.status.eq('completed'), 'image_id'].nunique(),
            team_requests=len(d), team_completed=int(d.status.eq('completed').sum()),
            pool_input_failed_requests=int(d.status.ne('completed').sum()),
            complete_geometry=int(d.complete_evaluable.eq(True).sum()),
            full_quality_numeric=int(d.B8L2.notna().sum()),
            main_quality_numeric=int((d.main_comparison_allowed.eq(True) & d.B8L2.notna()).sum()),
            source_time_complete=int(d.source_time_available.eq(True).sum())))
    table('team_coverage.csv', coverage)
    index = results.set_index('request_id')
    pairs = frame(STATS / 'strategy_vs_matched_random.csv')
    paths = {p['path_id']: p for p in requests['paths']}
    pairs['building_id'] = pairs.path_id.map(lambda p: paths[p]['building_id'])
    pairs['scene_bucket'] = pairs.target_request.map(index.scene_bucket)
    pairs['profile_application'] = pairs.target_request.map(index.profile_application)
    pairs['pure_class_prefix'] = [pure_focus_prefix(r.focus_supported, r.focus_available_n, r.k) for r in pairs.itertuples()]
    assert pairs.pure_class_prefix.equals(pairs.focus_covers_k)
    for r in pairs.itertuples():
        p = paths[r.path_id]
        assert p['prefix_request_ids'][r.k - 1] == r.target_request
        assert p['matched_random_prefix_request_ids'][r.k - 1] == r.random_request
    pairs['team_completed'] = pairs.target_request.map(index.status).eq('completed')
    pairs['random_completed'] = pairs.random_request.map(index.status).eq('completed')
    pairs['team_complete_geometry'] = pairs.target_request.map(index.complete_evaluable)
    pairs['random_complete_geometry'] = pairs.random_request.map(index.complete_evaluable)
    expected_main = (pairs.team_completed & pairs.random_completed
        & pairs.target_request.map(index.main_comparison_allowed).eq(True)
        & pairs.random_request.map(index.main_comparison_allowed).eq(True)
        & pairs.target_request.map(index.B8L2).notna() & pairs.random_request.map(index.B8L2).notna())
    assert expected_main.equals(pairs.both_main_quality)
    for metric in ['B8L2', 'D10']:
        left = pairs.target_request.map(index[metric]); right = pairs.random_request.map(index[metric])
        assert np.allclose((left - right).where(pairs.both_main_quality), pairs[metric + '_strategy_minus_random'], equal_nan=True, atol=1e-7)
    pairs['both_source_time_available'] = pairs.target_request.map(index.source_time_available).eq(True) & pairs.random_request.map(index.source_time_available).eq(True)
    pairs['source_time_strategy_minus_random'] = (pairs.target_request.map(index.source_active_seconds)
        - pairs.random_request.map(index.source_active_seconds)).where(pairs.both_source_time_available)
    table('strategy_vs_random.csv', pairs)
    summaries = []
    for interpretation in ['class_priority_path', 'pure_class_prefix']:
        selected = pairs if interpretation == 'class_priority_path' else pairs[pairs.pure_class_prefix]
        for keys, d in selected.groupby(['selection_metric', 'policy', 'k', 'scene_bucket']):
            metric, policy, k, scene = keys
            qualified = d[d.both_main_quality]
            summaries.append(dict(selection_metric=metric, policy=policy, k=k, scene_bucket=scene, interpretation=interpretation,
                planned_images=d.image.nunique(), completed_pair_images=int((d.team_completed & d.random_completed).sum()),
                focus_supported_images=int(d.focus_supported.sum()), main_quality_pair_images=len(qualified),
                main_quality_buildings=qualified.building_id.nunique(),
                geometry_complete_pairs=int((d.team_complete_geometry.eq(True) & d.random_complete_geometry.eq(True)).sum()),
                source_time_complete_pairs=int(d.both_source_time_available.sum()),
                B8L2_mean_difference=qualified.B8L2_strategy_minus_random.mean(),
                D10_mean_difference=qualified.D10_strategy_minus_random.mean(),
                B8L2_positive_images=int(qualified.B8L2_strategy_minus_random.gt(0).sum()),
                B8L2_negative_images=int(qualified.B8L2_strategy_minus_random.lt(0).sum()),
                source_seconds_mean_difference=d.loc[d.both_source_time_available, 'source_time_strategy_minus_random'].mean()))
    table('strategy_summary.csv', summaries)
    reselect = frame(STATS / 'metric_reselection_contrasts.csv')
    for metric in ['B8L2', 'D10']:
        a = reselect.B8L2_selected_team.map(index[metric])
        b = reselect.D10_reselected_team.map(index[metric])
        assert np.allclose((b - a).where(reselect.both_main_quality), reselect['reselection_at_fixed_' + metric], equal_nan=True, atol=1e-7)
    table('metric_reselection_contrasts.csv', reselect)
    common = frame(STATS / 'strategy_common_pool_summary.csv')
    table('pure_group_direct_comparisons.csv', common)
    direct = []
    for r in common.itertuples():
        d = pairs[pairs.selection_metric.eq(r.selection_metric) & pairs.k.eq(r.k)
            & pairs.pure_class_prefix & pairs.both_main_quality]
        a = d[d.policy.eq(r.left_policy)]
        b = d[d.policy.eq(r.right_policy)]
        m = a[['image_id', 'image', 'building_id', 'scene_bucket', 'target_request', 'B8L2_strategy', 'D10_strategy']].merge(
            b[['image_id', 'target_request', 'B8L2_strategy', 'D10_strategy']], on='image_id', suffixes=('_left', '_right'), validate='one_to_one')
        assert len(m) == r.n_common_images
        for metric in ['B8L2', 'D10']:
            m[metric + '_left_minus_right'] = m[metric + '_strategy_left'] - m[metric + '_strategy_right']
            assert np.isclose(m[metric + '_left_minus_right'].mean(), getattr(r, metric + '_left_minus_right_mean'), atol=1e-7)
        m['selection_metric'], m['k'], m['left_policy'], m['right_policy'] = r.selection_metric, r.k, r.left_policy, r.right_policy
        direct.append(m)
    direct = pd.concat(direct, ignore_index=True)
    table('pure_group_direct_by_image.csv', direct)
    table('pure_group_direct_by_building.csv', direct.groupby(['selection_metric', 'k', 'left_policy', 'right_policy', 'building_id']).agg(
        image_pairs=('image_id', 'size'), B8L2_mean_difference=('B8L2_left_minus_right', 'mean'),
        D10_mean_difference=('D10_left_minus_right', 'mean')).reset_index())
    return results, pairs, reselect


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    bundle = load_current_bundle(ROOT / 'analysis_results/research_input_20261017/manifest.json')
    old = frame(OLD / 'record_evidence.csv')
    records, bridge, ordinary = reliability(bundle, old)
    teams, pairs, reselect = team_results()
    f21 = records[records.object_id.eq('f21c670566821ce7')].iloc[0]
    save('HUMAN_REVIEW_CASES.json', dict(data_release='v1', needed_for_current_main_Q_or_team_consumption=False,
        no_request_to_review_all_131=True, cases=[dict(object_id=f21.object_id, worker_id=f21.worker_id,
            image_code=f21.image_code, source_verdict='invalid_preserved', issue='historical_OOS_geometry_submission_requirement_vs_personal_error_attribution',
            question='该P1任务当时是否要求OOS也提供完整成对布局，还是只需足以支持OOS判断？原invalid是否针对独立个人错误？',
            evidence_quote='oos,但是他只标了3个点', historical_scope_outcome=f21.scope_historical_outcome,
            original_source=objects_source(bundle, f21.object_id),
            record_table='record_evidence.csv', scope_table='scope_evidence.csv', exclusion_table='exclusion_candidate_evidence.csv',
            current_rule='docs/label_studio/README_ANNOTATOR.md sections 2.3 and 3.4',
            interim_action='retain_original_exclusion_attribution_pending_no_severe_error_penalty',
            required_only_if='research_will_attribute_this_OOS_exclusion_to_personal_geometry_failure')]))
    source_changed = any((ROOT / name).stat().st_size != stat['bytes'] or (ROOT / name).stat().st_mtime_ns != stat['mtime_ns'] for name, stat in SOURCES.items())
    assert not source_changed, 'consumer source changed during run; rerun against completed producer snapshot'
    save('INPUTS.json', dict(data_release='v1', analysis_revision='worker_v1_pro_integration_20261017', sources=SOURCES,
        Pro_originals_modified=False, Q_models_refit=False, fusion_executed_here=False,
        independent_Q_verification='research/workers/personnel_quality_pro_review_20261017/CHECKS.json',
        adoption='compatible initialization measurements and explicit evidence interfaces; no new universal risk score',
        original_candidate_field_renames=CANDIDATE_NAMES))
    save('CHECKS.json', dict(data_release='v1', records=len(records), workers=records.worker_id.nunique(),
        Q_training=int(records.in_Q_training.sum()), ordinary_compatible_gain_rows=len(ordinary),
        strong_gold_opportunities=156, strong_gold_unchanged=25, strong_gold_edited_unknown=131,
        residual_review_statements=3, residual_review_statements_added_vs_Pro=2,
        old_opportunities=int(bridge.old_opportunity.sum()), old_unrepaired_or_comment=int(bridge.old_unrepaired_or_comment.sum()),
        opportunity_intersection=int((bridge.old_opportunity & bridge.strong_gold_opportunity).sum()),
        team_requests=len(teams), team_completed=int(teams.status.eq('completed').sum()),
        team_failed=int(teams.status.ne('completed').sum()), strategy_pair_rows=len(pairs), reselection_rows=len(reselect),
        source_files_changed_during_run=source_changed, original_eligibility_changed=False,
        full_defect_outcome_review_performed=False, composite_penalty_created=False))
    save('CROSS_MODULE_INPUTS.json', dict(status='ready', data_release='v1', analysis_revision='worker_v1_pro_integration_20261017',
        files={key: str((OUT / name).relative_to(ROOT)) for key, name in dict(
            records='record_evidence.csv', persons='person_profiles_and_evidence.csv',
            semi_measurements='semi_initialization_scores.csv', correction='semi_correction_evidence.csv',
            correction_bridge='correction_definition_bridge.csv', scope='scope_evidence.csv',
            exclusion_candidates='exclusion_candidate_evidence.csv', team_results='team_results.csv',
            strategy_pairs='strategy_vs_random.csv', pure_class_comparisons='pure_group_direct_comparisons.csv',
            metric_reselection='metric_reselection_contrasts.csv', human_cases='HUMAN_REVIEW_CASES.json',
            fields='FIELD_CONTRACT.json').items()},
        joins=dict(record='object_id', person=['worker_id','metric'], team='request_id'),
        adoption='evidence and compatible measurement increment; Q1048 and existing eligibility preserved',
        quality_layers='ordinary Manual Q; ordinary Semi separate; doorway specialist separate; current doorway strategies are ordinary-Q transfer',
        limits='25/68 are candidate text codes; historical scope compatibility is not new gold; no new composite penalty'))
    save('FIELD_CONTRACT.json', dict(data_release='v1', analysis_revision='worker_v1_pro_integration_20261017',
        tables={p.name: dict(rows=len(pd.read_csv(p)), columns=pd.read_csv(p, nrows=0).columns.tolist()) for p in sorted(OUT.glob('*.csv'))},
        joins=dict(record='object_id', person='worker_id', profile=['fold','metric','worker_id'], team='request_id'),
        semantics=dict(candidate='25/68 reviewer text codes, not independent severity gold',
            scope='historical task gold plus current clear compatibility, not fresh current target gold',
            strong_gold='six expert realized-defect tasks, exact deployed initialization; only unchanged certifies persistent raw coordinate defect',
            residual_statement='three usable records, non-specific remaining issue, outside strong gold denominator',
            gain='compatible-ring measurement; worker-attributable and researcher-repaired views separate',
            strategy='class priority differs from pure_class_prefix; fixed members metric change differs from reselection',
            missing='CSV blank is unknown/not applicable; no zero filling or restoration of excluded workers')))
    print(json.dumps(read_output('CHECKS.json'), ensure_ascii=False))


def objects_source(bundle, object_id):
    return next(o['source'] for o in bundle['data']['objects'] if o['object_id'] == object_id)


def read_output(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))


if __name__ == '__main__':
    main()
