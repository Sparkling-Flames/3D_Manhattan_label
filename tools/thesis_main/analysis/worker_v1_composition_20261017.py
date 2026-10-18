"""数据v1：楼外人员组合请求及可追溯的可靠性证据；不运行融合。"""
import gzip
import json
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

from .worker_wq_integration_20261015 import fit_axis
from ..data_prep.consolidate_research_input import load_current_bundle

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / 'research/workers/worker_b8l2_d10_20261017'
SHARED = ROOT / 'research/quality/quality_b8l2_d10_20261017'
OUT = ROOT / 'research/workers/worker_v1_composition_20261017'
METRICS = ['B8L2', 'D10']


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False,
        indent=None if name == 'TEAM_REQUESTS.json' else 2, allow_nan=False) + '\n', encoding='utf-8')


def table(name, value):
    pd.DataFrame(value).to_csv(OUT / name, index=False, encoding='utf-8-sig')


def group_labels(q, q_supported, t, t_supported):
    qg = ('higher' if q > 0 else 'lower') if q_supported and np.isfinite(q) and q != 0 else 'unclassified'
    tg = ('faster' if t < 0 else 'slower') if t_supported and np.isfinite(t) and t != 0 else 'unclassified'
    return qg, tg, qg + '_' + tg if 'unclassified' not in (qg, tg) else 'unclassified'


def policy_order(workers, profiles, policy, seed):
    shuffled = np.random.default_rng(seed).permutation(sorted(workers)).tolist()
    if policy == 'random':
        return shuffled
    key = 'Q_group' if policy.startswith('Q_') else 'QT_group'
    focus = policy.removeprefix('Q_').removeprefix('QT_').removesuffix('_first')
    return sorted(shuffled, key=lambda w: profiles.get(w, {}).get(key) != focus)


def semi_state(edit, known_wrong, decision):
    if decision == 'not_corrected':
        return 'edited_error_remains_explicit_review' if edit == 'changed_coordinates' else 'error_remains_explicit_review'
    if edit == 'unchanged_coordinates':
        if decision == 'initial_correct':
            return 'correct_initialization_preserved'
        return 'confirmed_wrong_initialization_unrepaired' if known_wrong else 'unchanged_initial_correctness_unknown'
    return 'edited_correction_unknown' if edit == 'changed_coordinates' else 'edit_or_initialization_not_verified'


def reusable_geometry(member_string, pool):
    members = member_string.split('|')
    return len(members) == len(set(members)) and set(members) <= pool


def profiles_and_ranges(shared, workers):
    panels = {name: pd.read_csv(OLD / filename) for name, filename in
              [('Q', 'quality_panel.csv'), ('T_source', 'T_source_panel.csv'), ('T_target', 'T_target_panel.csv')]}
    fit = pd.read_csv(OLD / 'fold_profiles.csv')
    fit = fit[fit.panel.isin(['current', 'T_source', 'T_target'])].copy()
    target_buildings = sorted(shared.building_id.unique())
    for name, d in panels.items():
        panel = 'current' if name == 'Q' else name
        absent = set(target_buildings) - set(fit.loc[fit.panel.eq(panel), 'fold'])
        if absent:
            new = []
            for target in sorted(absent):
                for axis in METRICS if name == 'Q' else [name]:
                    rows = fit_axis(d, axis, target)
                    rows['panel'] = panel
                    rows['training_buildings'] = rows.training_buildings.map(json.dumps)
                    new.append(rows)
            fit = pd.concat([fit, *new], ignore_index=True)
    ranges = {}
    absolute = []
    for building in target_buildings + ['full_descriptive']:
        ranges[building] = {}
        for name, d in panels.items():
            train = d if building == 'full_descriptive' else d[d.building_id.ne(building)]
            ranges[building][name] = dict(training_object_ids=sorted(train.object_id),
                training_buildings=sorted(train.building_id.unique()), rows=len(train),
                source=str((OLD / (name + '_panel.csv' if name != 'Q' else 'quality_panel.csv')).relative_to(ROOT)))
            assert building not in set(train.building_id)
        q = panels['Q'] if building == 'full_descriptive' else panels['Q'][panels['Q'].building_id.ne(building)]
        for metric in METRICS:
            for worker, d in q.groupby('worker_id'):
                absolute.append(dict(fold=building, metric=metric, worker_id=worker, n=len(d), images=d.image_id.nunique(),
                    buildings=d.building_id.nunique(), mean=d[metric].mean(), median=d[metric].median(),
                    q10=d[metric].quantile(.1), sd=d[metric].std(), minimum=d[metric].min()))
    table('absolute_Q_training_profiles.csv', absolute)
    save('fold_training_ranges.json', ranges)
    result = []
    for building in target_buildings + ['full_descriptive']:
        f = fit[fit.fold.eq(building)].set_index(['axis', 'worker_id'])
        for metric in METRICS:
            for worker in workers:
                values = {}
                for prefix, axis in [('Q', metric), ('T_source', 'T_source'), ('T_target', 'T_target')]:
                    key = (axis, worker)
                    if key in f.index:
                        r = f.loc[key]
                        assert not isinstance(r, pd.DataFrame)
                        bs = json.loads(r.training_buildings)
                        assert building not in bs
                        values.update({prefix + '_effect': r.effect, prefix + '_supported': bool(r.supported),
                            prefix + '_contexts': int(r.contexts), prefix + '_buildings': int(r.buildings),
                            prefix + '_training_buildings': json.dumps(bs), prefix + '_fit_status': r.fit_status})
                    else:
                        values.update({prefix + '_effect': np.nan, prefix + '_supported': False, prefix + '_contexts': 0,
                            prefix + '_buildings': 0, prefix + '_training_buildings': '[]', prefix + '_fit_status': 'no_training_records'})
                qg, tg, qt = group_labels(values['Q_effect'], values['Q_supported'], values['T_source_effect'], values['T_source_supported'])
                result.append(dict(data_release='v1', fold=building, worker_id=worker, metric=metric,
                    Q_group=qg, T_group=tg, QT_group=qt,
                    missing_reason=';'.join(k + ':' + (values[k + '_fit_status'] if values[k + '_fit_status'] != 'usable'
                        else 'fewer_than_six_contexts_or_three_buildings') for k in ['Q', 'T_source'] if not values[k + '_supported']),
                    **values))
    result = pd.DataFrame(result)
    table('fold_person_profiles.csv', result)
    full = result[result.fold.eq('full_descriptive')]
    table('person_profiles.csv', full)
    groups = []
    for (metric, grouping, label), d in pd.concat([full.assign(grouping=k, group_label=full[k]) for k in ['Q_group', 'T_group', 'QT_group']]).groupby(['metric', 'grouping', 'group_label']):
        member = panels['Q'][panels['Q'].worker_id.isin(d.worker_id)]
        groups.append(dict(metric=metric, grouping=grouping, group_label=label, workers=len(d),
            worker_ids='|'.join(d.worker_id), Q_training_records=len(member), images=member.image_id.nunique(),
            buildings=member.building_id.nunique(), descriptive_only=True))
    table('group_coverage.csv', groups)
    stability = []
    for (metric, worker), d in result[result.fold.ne('full_descriptive')].groupby(['metric', 'worker_id']):
        own = shared.loc[shared.worker_id.eq(worker), 'building_id'].unique()
        d = d[d.fold.isin(own)]
        for label in ['Q_group', 'T_group', 'QT_group']:
            classified = d[d[label].ne('unclassified')]
            stability.append(dict(metric=metric, worker_id=worker, grouping=label, target_buildings=len(d),
                classified_folds=len(classified), unknown_folds=int(d[label].eq('unclassified').sum()),
                labels=json.dumps(classified[label].value_counts().to_dict()),
                label_variants=classified[label].nunique(),
                min_Q_effect=d.Q_effect.min(), max_Q_effect=d.Q_effect.max(),
                min_T_effect=d.T_source_effect.min(), max_T_effect=d.T_source_effect.max()))
    table('cross_building_stability.csv', stability)
    halves = pd.read_csv(OLD / 'disjoint_halves.csv')
    table('disjoint_half_stability.csv', halves.groupby(['axis', 'worker_id']).agg(
        attempted_halves=('repeat', 'size'), comparable_halves=('comparable', 'sum'),
        same_sign_halves=('same_direction', 'sum')).reset_index())
    return result, panels


def team_requests(shared, profiles, manifest, bundle):
    candidates = shared[shared.condition.eq('manual') & shared.pool_analysis_eligible & shared.pool_vote_eligible
        & shared.independent_vote_eligible & ~shared.is_oos].copy()
    assert not candidates.worker_id.isin(['W019', 'W026']).any()
    catalog = read(SHARED / 'reference_catalog.json')
    cached = pd.read_csv(OLD / 'team_scores.csv')
    snapshot = read(ROOT / 'research/fusion/wall_consensus_b8l2_20261016/input_snapshot.json')
    objects = {x['object_id']: x for x in bundle['data']['objects']}
    state_lookup, input_equal = {}, {}
    for image in snapshot['images']:
        if image['image'] not in set(cached.image):
            continue
        aliases = {m['public_worker']: m['worker_id'] for m in image['members']}
        for member in image['members']:
            old = next(r['points'] for r in image['records'] if r['worker'] == member['public_worker'])
            current = objects[member['object_id']]['points_1024x512']
            input_equal[(image['image'], member['worker_id'])] = np.array_equal(old, current)
        state_paths = [ROOT / image['state_source'], ROOT / 'research/workers/worker_wq_integration_20261015/new_states' / (image['image'] + '.json.gz')]
        for state_path in state_paths:
            if not state_path.exists():
                continue
            with gzip.open(state_path, 'rt', encoding='utf-8') as stream:
                states = json.load(stream)['states']
            for j, state in enumerate(states):
                key = (image['image'], tuple(sorted(aliases[w] for w in state['workers'])))
                state_lookup[key] = dict(path=str(state_path.relative_to(ROOT)), pointer='/states/' + str(j) + '/automatic')
    pool_map = candidates.groupby('image_id').worker_id.agg(set).to_dict()
    pool_status = pd.read_csv(SHARED / 'source_pools.csv')
    pool_status = pool_status[pool_status.condition.eq('manual')].copy()
    pool_status['requested'] = pool_status.image_id.isin(pool_map)
    pool_status['request_status'] = np.where(pool_status.requested, 'eligible_manual_nonOOS_pool',
        np.where(~pool_status.pool_min3_pass, 'fewer_than_three_effective_workers',
            np.where(~pool_status.pool_analysis_eligible, 'published_image_or_pool_hold', 'OOS_diagnostic_only')))
    table('source_pool_request_status.csv', pool_status)
    image_map = dict(zip(shared.image_code, shared.image_id))
    reuse = []
    cache = {}
    for i, row in cached.iterrows():
        image_id = image_map[row.image]
        allowed = reusable_geometry(row.workers, pool_map.get(image_id, set()))
        matched_input = all(input_equal[(row.image, w)] for w in row.workers.split('|'))
        complete = pd.notna(row.B8L2)
        geometry_reusable = allowed and matched_input and complete
        state_source = state_lookup[(row.image, tuple(sorted(row.workers.split('|'))))]
        reuse.append(dict(cache_row=i, image_id=image_id, image_code=row.image, workers=row.workers,
            k=row.k, membership_eligible=allowed, current_prepared_input_exact=matched_input,
            geometry_reuse_eligible=geometry_reusable, B8L2=row.B8L2, D10=row.D10,
            geometry_state_source=state_source['path'], geometry_state_pointer=state_source['pointer'],
            fusion_version=snapshot['fusion_version'],
            cached_reference_id=row.reference_id, cached_reference_version=row.reference_version,
            cached_use=row.use, cached_score_status=row.score_status,
            reason='exact_real_member_geometry_only_recheck_evaluation_reference' if geometry_reusable else
                'outside_current_eligible_manual_pool' if not allowed else
                'prepared_ring_order_differs_recheck_fusion_context' if not matched_input else 'recorded_failure_no_complete_geometry'))
        if geometry_reusable:
            cache[(image_id, tuple(sorted(row.workers.split('|'))))] = dict(row=i, **state_source)
    table('existing_team_reuse.csv', reuse)
    teams, paths, coverage, contrasts = {}, [], [], []
    profile_index = profiles.set_index(['fold', 'metric', 'worker_id'])
    for image_id, pool in candidates.groupby('image_id', sort=True):
        assert not pool.worker_id.duplicated().any()
        workers = sorted(pool.worker_id)
        assert len(workers) >= 3
        first = pool.iloc[0]
        refs = [dict(reference_id=r['target_id'], reference_version=r['reference_version'], role=r['role'],
            full_reference_available=r['full_reference_available']) for r in catalog if r['image_id'] == image_id and r['current_target']]
        if not refs:
            refs = [dict(reference_id=a, reference_version=b, role='published_record_binding',
                full_reference_available=False) for a, b in pool[['reference_id', 'reference_version']].drop_duplicates().itertuples(index=False, name=None) if pd.notna(a)]
        def register(members):
            key = (image_id, tuple(sorted(members)))
            if key not in teams:
                request_id = 'TEAM%06d' % (len(teams) + 1)
                rows = pool.set_index('worker_id').loc[sorted(members)]
                teams[key] = dict(request_id=request_id, data_release='v1', image_id=image_id, image_code=first.image_code,
                    building_id=first.building_id, condition='manual', scene_bucket=first.scene_bucket,
                    k=len(members), worker_ids=sorted(members), object_ids=rows.object_id.tolist(),
                    evaluation_references=refs,
                    member_reference_bindings=[dict(worker_id=w, reference_id=r.reference_id if pd.notna(r.reference_id) else None,
                        reference_version=r.reference_version if pd.notna(r.reference_version) else None) for w, r in rows.iterrows()],
                    existing_geometry_cache_row=cache[key]['row'] if key in cache else None,
                    geometry_action='reuse_exact_members_then_verify_context' if key in cache else 'fusion_thread_compute_true_subset',
                    outcome_metrics=METRICS, quality_missing_member_n=int((~rows.quality_usable).sum()),
                    source_time_known_sum=float(rows.source_active_time_seconds.sum(min_count=1)) if rows.source_active_time_seconds.notna().any() else None,
                    source_time_missing_n=int(rows.source_active_time_seconds.isna().sum()),
                    target_time_known_sum=float(rows.target_matched_time_seconds.sum(min_count=1)) if rows.target_matched_time_seconds.notna().any() else None,
                    target_time_missing_n=int(rows.target_matched_time_seconds.isna().sum()),
                    original_holdout_member_n=int(rows.admission_original_holdout.eq(True).sum()),
                    geometry_source=cache[key]['path'] if key in cache else None,
                    geometry_state_pointer=cache[key]['pointer'] if key in cache else None)
            return teams[key]['request_id']
        base_seed = 20261017 + zlib.crc32(image_id.encode())
        random_orders = [policy_order(workers, {}, 'random', base_seed + j) for j in range(3)]
        baseline = [register(random_orders[0][:k]) for k in range(1, len(workers) + 1)]
        strategies = [('none', 'random', j, order) for j, order in enumerate(random_orders)]
        by_metric = {}
        for metric in METRICS:
            info = {w: profile_index.loc[(first.building_id, metric, w)].to_dict() for w in workers}
            by_metric[metric] = info
            for policy in ['Q_higher_first', 'Q_lower_first', 'QT_higher_faster_first', 'QT_higher_slower_first', 'QT_lower_faster_first', 'QT_lower_slower_first']:
                strategies.append((metric, policy, 0, policy_order(workers, info, policy, base_seed)))
            for grouping in ['Q_group', 'T_group', 'QT_group']:
                counts = pd.Series([info[w][grouping] for w in workers]).value_counts().to_dict()
                coverage.append(dict(image_id=image_id, image_code=first.image_code, building_id=first.building_id,
                    metric=metric, grouping=grouping, source_pool_n=len(workers), counts=json.dumps(counts),
                    classified_n=sum(v for k, v in counts.items() if k != 'unclassified'),
                    has_both_Q_groups=all(any(info[w]['Q_group'] == g for w in workers) for g in ['higher', 'lower']),
                    has_all_QT_groups=all(any(info[w]['QT_group'] == g for w in workers) for g in ['higher_faster', 'higher_slower', 'lower_faster', 'lower_slower'])))
        image_paths = {}
        for metric, policy, replicate, order in strategies:
            ids = [register(order[:k]) for k in range(1, len(order) + 1)]
            path_id = 'PATH%06d' % (len(paths) + 1)
            image_paths[(metric, policy)] = (path_id, ids)
            focus = policy.removeprefix('Q_').removeprefix('QT_').removesuffix('_first')
            focus_n = None if policy == 'random' else sum(by_metric[metric][w]['Q_group' if policy.startswith('Q_') else 'QT_group'] == focus for w in workers)
            paths.append(dict(path_id=path_id, data_release='v1', image_id=image_id, image_code=first.image_code,
                building_id=first.building_id, source_pool_worker_ids=workers, source_pool_n=len(workers),
                selection_metric=metric, policy=policy, seed=int(base_seed + replicate), random_replicate=replicate,
                selection_metric_version=manifest['parameters'][metric]['version'] if metric in METRICS else 'metric_independent_random',
                focus_group_available_n=focus_n, policy_has_focus_support=focus_n is None or focus_n > 0,
                ordered_worker_ids=order, prefix_request_ids=ids, matched_random_prefix_request_ids=baseline,
                grouping_rule='Q sign and log1p active-time effect sign; target building excluded; random within focused class',
                fold_profile_table='fold_person_profiles.csv', training_range_key=first.building_id,
                time_interpretation='source_task_worker_not_target_specific',
                endpoint_note='same_full_pool_all_policies; k1_k2_valid_prefixes_of_admitted_pool'))
        for policy in ['Q_higher_first', 'Q_lower_first', 'QT_higher_faster_first', 'QT_higher_slower_first', 'QT_lower_faster_first', 'QT_lower_slower_first']:
            a, b = image_paths[('B8L2', policy)], image_paths[('D10', policy)]
            for k, (ta, tb) in enumerate(zip(a[1], b[1]), 1):
                contrasts.append(dict(image_id=image_id, image_code=first.image_code, building_id=first.building_id,
                    policy=policy, k=k, B8L2_selected_team=ta, D10_reselected_team=tb, members_changed=ta != tb,
                    fixed_member_metric_comparison='evaluate_each_same_request_in_B8L2_and_D10',
                    reselection_comparison='compare_B8L2_selected_with_D10_selected_at_each_fixed_outcome_metric'))
    table('target_pool_group_coverage.csv', coverage)
    table('metric_selection_contrasts.csv', contrasts)
    save('TEAM_REQUESTS.json', dict(schema='worker_v1_team_requests_20261017_v1', data_release='v1',
        analysis_revision='worker_v1_composition_20261017', shared_input_version=manifest['version'],
        metric_parameters=manifest['parameters'], selection_reads_target_scores=False,
        eligibility='published independent manual source pools >=3, no OOS, no excluded workers; no score-based member filtering',
        evaluation='each team fixed members evaluated by both metrics; ref alternatives explicit, no best-score target selection',
        dependence='paths and overlapping subsets are not independent images/buildings; three fixed random permutations per image',
        geometry_implementation='fusion thread owns true-prefix reconstruction; never borrow full-pool identities',
        teams=list(teams.values()), paths=paths))
    return len(pool_map), len(teams), len(paths)


def evidence(shared, panels, bundle):
    objects = {x['object_id']: x for x in bundle['data']['objects'] if x['object_kind'] == 'annotation'}
    object_indices = {x['object_id']: i for i, x in enumerate(bundle['data']['objects'])}
    research = {x['object_id']: x for x in bundle['research']['annotations']}
    audit = {x['object_id']: x for x in bundle['data']['model_unchanged_audit']}
    old_semi = pd.read_csv(ROOT / 'research/workers/worker_four_axis_update_20261015/semi_records.csv').set_index('object_id')
    scope = pd.read_csv(OLD / 'scope_response_evidence.csv').set_index('object_id')
    assert scope.index.is_unique
    decisions = read(OUT / 'EVIDENCE_DECISIONS.json')
    exclusions = decisions['confirmed_person_error_exclusions']
    corrections = decisions['explicit_semi_correction_decisions']
    rows = []
    for r in shared.to_dict('records'):
        oid = r['object_id']; obj = objects[oid]; rev = research[oid]
        a = audit.get(oid)
        old = old_semi.loc[oid] if oid in old_semi.index else None
        s = scope.loc[oid] if oid in scope.index else None
        if s is not None:
            assert (s.worker_id, s.image_id) == (r['worker_id'], r['image_id'])
        preview = False
        if a:
            model = json.loads(a['model_evidence']) if isinstance(a['model_evidence'], str) else a['model_evidence']
            preview = (model.get('model_check') or {}).get('preview_initialization_verified') is True
        old_verified = old is not None and old.initialization_evidence_status == 'import_and_runtime_preview_matched'
        known_wrong = (obj['trap_status'] == 'confirmed_trap' and (preview or old_verified))
        edit = obj['model_edit_status']
        state = semi_state(edit, known_wrong, corrections.get(oid, {}).get('decision')) if r['condition'] == 'semi' else 'not_applicable_non_semi'
        confirmed = oid in exclusions
        if confirmed:
            assert r['cleaning_disposition'] == 'excluded_by_review' and rev['review_evidence']['verdict'] == 'invalid'
            assert exclusions[oid]['quote'] in rev['current_comments']
        if oid in corrections:
            assert corrections[oid]['quote'] in rev['current_comments']
        history_excluded = r['worker_id'] in ['W019', 'W026']
        disposition = r['cleaning_disposition']
        attribution = ('confirmed_individual_error_excluded' if confirmed else
            'historical_whole_worker_exclusion_not_per_record_error' if history_excluded else
            'review_exclusion_attribution_unknown' if disposition == 'excluded_by_review' else
            'other_historical_nonacceptance_attribution_unknown' if disposition == 'historical_not_accepted' else
            'no_confirmed_personal_severe_exclusion')
        reviewed = bool(obj.get('final_review', {}).get('individually_reviewed', False))
        accepted = reviewed and rev['review_evidence']['verdict'] in ['usable', 'retained_scope_variation'] and disposition == 'retained'
        severe_assessed = confirmed or accepted
        source = r['source_path']
        comment_events = sorted(set(rev['current_comments']))
        fields = ['object_id', 'worker_id', 'image_id', 'image_code', 'building_id', 'condition', 'reference_id', 'reference_version',
            'quality_usable', 'quality_use', 'is_doorway', 'is_oos', 'pool_analysis_eligible', 'pool_vote_eligible',
            'scene_bucket', 'difficulty_class', 'gt_error_excluded', 'independent_vote_eligible', 'independent_vote_reasons',
            'pool_min3_pass', 'pool_source_workers', 'worker_quality_gate', 'quality_exclusion_reasons',
            'cleaning_disposition', 'calculation_status', 'binding_status', 'primary_reason', 'B8L2', 'D10',
            'source_active_time_seconds', 'target_matched_time_seconds', 'admission_original_holdout', 'in_Q_training']
        row = {k: r[k] for k in fields}
        row.update(data_release='v1', source_path=source, source_project=obj['source']['project'], source_task=obj['source']['task'],
            source_annotation=obj['source']['annotation'], individually_reviewed=reviewed, final_review_verdict=rev['review_evidence']['verdict'],
            historical_worker_exclusion=history_excluded, exclusion_attribution=attribution,
            confirmed_person_error_exclusion=confirmed, severe_assessed_under_explicit_rule=severe_assessed,
            accepted_review_no_severe_exclusion=accepted, severe_attribution_unknown=disposition in ['excluded_by_review', 'historical_not_accepted'] and not confirmed,
            model_edit_status=edit, trap_status=obj['trap_status'], targeted_audit_member=a is not None,
            initialization_preview_verified=preview or old_verified, known_wrong_initialization_opportunity=known_wrong,
            initialization_error_evidence_basis='confirmed_trap_and_verified_actual_initialization' if known_wrong else 'initial_correctness_unknown',
            historical_initialization_kind=old.legacy_initialization_kind if old is not None else None,
            historical_initial_reference_basis=old.reference_basis if old is not None else None,
            historical_initial_reference_hold=old.reference_hold if old is not None else None,
            current_reference_initial_error_recertification='not_performed' if r['condition'] == 'semi' else 'not_applicable',
            semi_error_state=state, explicit_correction_success=False,
            explicit_error_remains=state in ['confirmed_wrong_initialization_unrepaired', 'edited_error_remains_explicit_review', 'error_remains_explicit_review'],
            correction_status_unknown=r['condition'] == 'semi' and state not in ['confirmed_wrong_initialization_unrepaired', 'edited_error_remains_explicit_review', 'error_remains_explicit_review', 'correct_initialization_preserved'],
            error_remains_and_person_exclusion=confirmed and state in ['confirmed_wrong_initialization_unrepaired', 'edited_error_remains_explicit_review'],
            historical_gain_ospa30=old.gain_ospa30 if old is not None else np.nan,
            historical_initial_ospa30=old.initial_ospa30 if old is not None else np.nan,
            historical_final_ospa30=old.final_ospa30 if old is not None else np.nan,
            historical_edit_ospa30=old.edit_ospa30 if old is not None else np.nan,
            current_B8L2_initial_score=np.nan, current_D10_initial_score=np.nan,
            current_metric_net_gain_status='not_recomputed_from_initialization' if r['condition'] == 'semi' else 'not_applicable',
            review_comments_deduplicated=json.dumps(comment_events, ensure_ascii=False),
            review_evidence_json=json.dumps(rev['review_evidence'], ensure_ascii=False),
            S_source_response=s.worker_scope if s is not None else None,
            S_response_source=s.source if s is not None else None,
            S_current_correctness='not_recognized_from_choice_alone',
            failure_overlap_rule='one_object_id_one_event_no_additive_penalty',
            source_pointer='analysis_results/research_input_20261017/data.json#/objects/' + str(object_indices[oid]))
        rows.append(row)
    frame = pd.DataFrame(rows)
    assert len(frame) == 3222 and frame.object_id.is_unique
    assert frame.S_source_response.notna().sum() == len(scope) == 1083
    assert set(frame.loc[frame.condition.eq('semi'), 'object_id']) == set(old_semi.index)
    table('record_evidence.csv', frame)
    table('semi_evidence.csv', frame[frame.condition.eq('semi')])
    table('exclusion_evidence.csv', frame[frame.cleaning_disposition.isin(['excluded_by_review', 'historical_not_accepted'])])
    table('person_evidence_by_condition_scene.csv', frame.groupby(['worker_id', 'condition', 'scene_bucket'], dropna=False).agg(
        canonical_submissions=('object_id', 'size'), reviewed=('individually_reviewed', 'sum'),
        confirmed_person_error_exclusions=('confirmed_person_error_exclusion', 'sum'),
        explicitly_assessed_opportunities=('severe_assessed_under_explicit_rule', 'sum'),
        exclusion_attribution_unknown=('severe_attribution_unknown', 'sum'),
        known_wrong_initialization_opportunities=('known_wrong_initialization_opportunity', 'sum'),
        explicit_error_remains=('explicit_error_remains', 'sum'), correction_unknown=('correction_status_unknown', 'sum')).reset_index())
    save('duplicate_source_versions.json', dict(data_release='v1',
        canonical_denominator=3222, note='历史来源重复版本单列，不增加规范提交人数或作答分母',
        records=bundle['data']['duplicate_versions']))
    summaries = []
    for worker, d in frame.groupby('worker_id'):
        semi = d[d.condition.eq('semi')]
        known = semi[semi.known_wrong_initialization_opportunity]
        summaries.append(dict(worker_id=worker, data_release='v1', canonical_submissions=len(d), images=d.image_id.nunique(), buildings=d.building_id.nunique(),
            individually_reviewed=int(d.individually_reviewed.sum()), review_coverage=d.individually_reviewed.mean(),
            confirmed_person_error_exclusions=int(d.confirmed_person_error_exclusion.sum()),
            known_error_share_all_submissions=d.confirmed_person_error_exclusion.mean(),
            explicitly_assessed_opportunities=int(d.severe_assessed_under_explicit_rule.sum()),
            known_error_fraction_assessed=d.confirmed_person_error_exclusion.sum()/d.severe_assessed_under_explicit_rule.sum() if d.severe_assessed_under_explicit_rule.any() else np.nan,
            accepted_review_no_severe_exclusion=int(d.accepted_review_no_severe_exclusion.sum()),
            exclusion_attribution_unknown=int(d.severe_attribution_unknown.sum()),
            severe_status_not_explicitly_assessed=int((~d.severe_assessed_under_explicit_rule).sum()),
            historical_whole_worker_excluded_records=int(d.historical_worker_exclusion.sum()),
            GT_reference_excluded_records=int(shared.loc[shared.worker_id.eq(worker), 'gt_error_excluded'].sum()),
            OOS_diagnostic_records=int(d.is_oos.sum()), quality_missing=int((~d.quality_usable).sum()),
            S_raw_response_count=int(d.S_source_response.notna().sum()),
            S_raw_choice_counts=json.dumps(d.S_source_response.value_counts().to_dict()),
            source_time_missing=int(d.source_active_time_seconds.isna().sum()), target_time_missing=int(d.target_matched_time_seconds.isna().sum()),
            semi_submissions=len(semi), targeted_audit_records=int(semi.targeted_audit_member.sum()),
            targeted_unchanged=int((semi.targeted_audit_member & semi.model_edit_status.eq('unchanged_coordinates')).sum()),
            known_wrong_initialization_opportunities=len(known), known_wrong_unchanged=int(known.model_edit_status.eq('unchanged_coordinates').sum()),
            explicit_error_remains=int(semi.explicit_error_remains.sum()), explicit_repair_success=int(semi.explicit_correction_success.sum()),
            correction_unknown=int(semi.correction_status_unknown.sum()), historical_net_gain_available=int(semi.historical_gain_ospa30.notna().sum()),
            correction_and_exclusion_overlap=int(d.error_remains_and_person_exclusion.sum())))
    summary = pd.DataFrame(summaries)
    assert summary.canonical_submissions.sum() == len(frame)
    table('person_evidence_summary.csv', summary)
    save('EVIDENCE_COUNTS.json', dict(inventory=len(frame), workers=len(summary), Semi=len(frame[frame.condition.eq('semi')]),
        targeted_audit=len(audit), targeted_unchanged=int((frame.targeted_audit_member & frame.model_edit_status.eq('unchanged_coordinates')).sum()),
        S_raw_responses=int(frame.S_source_response.notna().sum()),
        known_wrong_initialization_opportunities=int(frame.known_wrong_initialization_opportunity.sum()),
        explicit_unrepaired=int(frame.explicit_error_remains.sum()), known_person_error_exclusions=len(exclusions),
        reviewed_exclusions=int(frame.cleaning_disposition.eq('excluded_by_review').sum()),
        historical_nonacceptance=int(frame.cleaning_disposition.eq('historical_not_accepted').sum()),
        correction_success_not_inferred_from_gain=True, no_new_severe_error_labels_beyond_explicit_cited_decisions=True))
    return frame


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = read(SHARED / 'CROSS_MODULE_INPUTS.json')
    bundle = load_current_bundle(ROOT / manifest['input_manifest'])
    shared = pd.read_csv(OLD / 'shared_input_snapshot.csv')
    current_source = pd.read_csv(SHARED / 'shared_records.csv')
    compare = ['object_id', 'worker_id', 'image_id', 'reference_id', 'reference_version', 'quality_usable',
               'pool_analysis_eligible', 'pool_vote_eligible', 'is_oos', 'B8L2', 'D10']
    pd.testing.assert_frame_equal(shared[compare].sort_values('object_id').reset_index(drop=True),
        current_source[compare].sort_values('object_id').reset_index(drop=True))
    ledger = pd.read_csv(OLD / 'personnel_ledger.csv')
    shared = shared.merge(ledger[['object_id', 'primary_reason', 'in_Q_training', 'admission_original_holdout']], on='object_id', validate='one_to_one')
    assert len(shared) == 3222 and shared.worker_id.nunique() == 27
    workers = sorted(shared.worker_id.unique())
    profiles, panels = profiles_and_ranges(shared, workers)
    pool_n, teams, paths = team_requests(shared, profiles, manifest, bundle)
    records = evidence(shared, panels, bundle)
    person_summary = pd.read_csv(OUT / 'person_evidence_summary.csv')
    absolute = pd.read_csv(OUT / 'absolute_Q_training_profiles.csv')
    person = profiles[profiles.fold.eq('full_descriptive')].merge(person_summary, on=['worker_id', 'data_release'], validate='many_to_one')
    person = person.merge(absolute[absolute.fold.eq('full_descriptive')].drop(columns='fold'),
        on=['worker_id', 'metric'], how='left', validate='one_to_one')
    table('statistics_person_evidence.csv', person)
    joined = []
    for metric in METRICS:
        subset = records[['object_id', 'worker_id', 'building_id', 'image_id', 'condition', 'reference_id', 'reference_version',
            'in_Q_training', 'quality_usable', 'is_oos', 'semi_error_state', 'exclusion_attribution',
            'source_active_time_seconds', 'target_matched_time_seconds']].copy()
        subset['metric'] = metric
        subset['score'] = records[metric]
        fold = profiles[profiles.metric.eq(metric) & profiles.fold.ne('full_descriptive')].rename(columns={'fold': 'building_id'})
        subset = subset.merge(fold.drop(columns=['metric']), on=['worker_id', 'building_id'], how='left', validate='many_to_one')
        joined.append(subset)
    table('statistics_record_profiles.csv', pd.concat(joined, ignore_index=True))
    save('INPUTS.json', dict(data_release='v1', analysis_revision='worker_v1_composition_20261017',
        input_revision=bundle['manifest']['effective_input_revision'], shared_manifest=manifest,
        prior_personnel_package=str(OLD.relative_to(ROOT)), no_new_weighted_score=True,
        Semi_history='research/workers/worker_four_axis_update_20261015/semi_records.csv',
        S_raw_evidence='research/workers/worker_b8l2_d10_20261017/scope_response_evidence.csv',
        Q_absolute_relative='two views of same underlying score, not two weighted votes',
        efficiency='T separate from quality/reliability; source and target time separate',
        source_pool_minimum=3, valid_prefix_nodes_include=[1, 2], fusion_geometry_executed=False))
    save('CHECKS.json', dict(data_release='v1', inventory=len(shared), workers=len(workers), Q_training=len(panels['Q']),
        T_source_training=len(panels['T_source']), T_target_training=len(panels['T_target']),
        admitted_target_pools=pool_n, unique_team_requests=teams, strategy_paths=paths,
        target_building_excluded_from_training=True, excluded_workers_restored=False, target_results_used_for_selection=False,
        shared_manifest_unchanged=manifest == read(SHARED / 'CROSS_MODULE_INPUTS.json')))
    save('FIELD_CONTRACT.json', dict(data_release='v1', schema='worker_v1_composition_20261017',
        tables={p.name: dict(rows=len(pd.read_csv(p)), columns=pd.read_csv(p, nrows=0).columns.tolist()) for p in sorted(OUT.glob('*.csv'))},
        joins=dict(record='object_id', person='worker_id', profile=['fold', 'metric', 'worker_id'],
                  geometry='TEAM_REQUESTS request_id, member object_ids, image_id', target='reference_id plus reference_version'),
        missing='CSV empty is unknown/not applicable; never zero-filled',
        source_pointers='object source project/task/annotation plus JSON evidence; comments deduplicated by object event',
        metric_gain='historical OSPA30 initial-final loss only; current B8L2/D10 initial and gain not recomputed'))
    assert read(OUT / 'CHECKS.json')['shared_manifest_unchanged']
    print(json.dumps(read(OUT / 'CHECKS.json')))


if __name__ == '__main__':
    main()
