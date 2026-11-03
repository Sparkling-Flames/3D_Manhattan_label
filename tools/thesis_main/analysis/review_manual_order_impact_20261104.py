"""Read-only, cross-module numerical/identity review of the targeted order overlay.

This deliberately does not import the producer scripts.  It rederives selected
mathematical identities, support counts and aggregations from saved artifacts.
The reviewer implemented same_room, so that module is explicitly self-validation.
Only INDEPENDENT_REVIEW_CHECKS.json is written by this script.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'research/fusion/manual_order_impact_20261104'
COMMIT = 'ac395e703d1fef573d1ef3e105df0286d62a0468'
CHECKS = []
EVIDENCE = {}
READ_FILES = set()


def csv(path, **kwargs):
    p = BASE / path
    READ_FILES.add(p)
    return pd.read_csv(p, low_memory=False, **kwargs)


def js(path):
    p = BASE / path
    READ_FILES.add(p)
    return json.loads(p.read_text())


def check(name, passed, **details):
    CHECKS.append(dict(check=name, passed=bool(passed), **details))


def close(a, b, tol=1e-8):
    x, y = np.asarray(a, float), np.asarray(b, float)
    return bool(np.isclose(x, y, atol=tol, rtol=0, equal_nan=True).all())


def maxdiff(a, b):
    x, y = np.asarray(a, float), np.asarray(b, float)
    mask = np.isfinite(x) & np.isfinite(y)
    return float(np.max(np.abs(x[mask] - y[mask]))) if mask.any() else None


def same(a, b):
    return bool((a.eq(b) | (a.isna() & b.isna())).to_numpy().all())


def hierarchical_images(frame, columns):
    keys = ['n', 'building', 'image', 'pool_id', 'block_id', 'background_id']
    z = frame.groupby(keys, dropna=False)[columns].mean()
    for keys2 in [keys[:-1], keys[:-2], keys[:3]]:
        z = z.groupby(level=keys2, dropna=False).mean()
    return z.reset_index()


def review_endpoints():
    scores = csv('endpoints/ENDPOINT_SCORES.csv')
    path = BASE / 'endpoints/ENDPOINTS.jsonl.gz'
    READ_FILES.add(path)
    with gzip.open(path, 'rt') as f:
        states = [json.loads(line) for line in f]
    check('endpoint_unique_team_reference_contexts', len(scores) == 57 and
          not scores.duplicated(['team_key', 'reference_id', 'reference_version']).any() and
          scores.team_key.nunique() == 57 and scores.image.nunique() == 22)
    errors, projection_errors, votes_ok, polygon_valid = [], [], [], []
    for row in states:
        nodes = {n['feature_id']: n for n in row['fixed_nodes']}
        order = row['manual_feature_order']
        check('order_exactly_once:' + row['review_id'],
              len(order) == len(nodes) and set(order) == set(nodes))
        points = np.asarray([p for node in order for p in nodes[node]['points']], float)
        errors.append(maxdiff(points, row['geometry']['points']))
        bottom = points[1::2]
        phi = 2 * np.pi * (bottom[:, 0] / 1024 - .5)
        radial = 1 / np.tan(np.pi * (bottom[:, 1] / 512 - .5))
        projected = np.column_stack([radial * np.sin(phi), -radial * np.cos(phi)])
        projection_errors.append(maxdiff(projected, row['geometry']['footprint']))
        polygon_valid.append(Polygon(projected).is_valid)
        for node in nodes.values():
            votes_ok.append(node['support'] == len(node['members']) ==
                            len({m['worker'] for m in node['members']}) and
                            node['support'] >= np.ceil(row['k'] / 2))
    check('fixed_coordinates_reconstruct_without_mutation', max(errors) == 0,
          nodes=sum(len(x['fixed_nodes']) for x in states), max_coordinate_error=max(errors))
    check('panorama_projection_independently_reproduced', max(projection_errors) < 1e-10,
          max_footprint_error=max(projection_errors))
    check('votes_and_selected_support_preserved', all(votes_ok), nodes=len(votes_ok))
    check('independent_polygon_validity_56_of_57', sum(polygon_valid) == 56,
          valid=sum(polygon_valid), invalid=57-sum(polygon_valid))
    check('missing_automatic_Q_not_zero', scores.automatic_B8L2.isna().all() and
          scores.paired_Q_change.isna().all() and scores.B8L2.notna().sum() == 56 and
          scores.human_labor_seconds.isna().all())
    bindings = csv('endpoints/ENDPOINT_REFERENCE_BINDINGS.csv')
    bound = bindings.merge(scores[['team_key', 'reference_id', 'reference_version']],
                           on='team_key', validate='many_to_one', suffixes=('_source', '_score'))
    check('all_536_references_bind_exact_team_and_reference', len(bound) == 536 and
          same(bound.resolved_reference_id, bound.reference_id_score) and
          same(bound.resolved_reference_version, bound.reference_version_score))
    fixed = csv('endpoints/FIXED_INPUT_CHECKS.csv')
    cols = ['nodes_fixed', 'coordinates_fixed', 'votes_fixed', 'team_fixed',
            'source_records_fixed', 'reference_fixed', 'order_exactly_once',
            'current_pool_raw_coordinates_exact', 'current_pool_reference_coordinates_exact',
            'automatic_no_connection_reproduced']
    check('producer_fixed_input_receipts_all_true', fixed[cols].all().all(),
          rows=len(fixed), fields=cols)
    EVIDENCE['endpoint_support'] = dict(teams=57, images=22, nodes=len(votes_ok),
        originally_scored=0, manually_scored=56,
        visible_kernel=int(scores.geometry_camera_in_visible_kernel.eq(True).sum()),
        conditional_visibility=int(((scores.geometry_polygon_valid == True) &
                                     (scores.geometry_camera_in_visible_kernel == False)).sum()))
    return scores


def review_candidate(scores):
    path = BASE / 'coordinate_candidate/CANDIDATE_FULL_STATE.json.gz'
    READ_FILES.add(path)
    with gzip.open(path, 'rt') as f:
        old, new = json.load(f)
    a = {n['feature_id']: n for n in old['nodes']}
    b = {n['feature_id']: n for n in new['nodes']}
    changed, changes, ychanges = [], 0, 0
    exact_x = True
    for key in a:
        x, y = np.asarray(a[key]['points']), np.asarray(b[key]['points'])
        diff = x != y
        if diff.any(): changed.append(key)
        changes += int(diff.sum())
        ychanges += int(diff[:, 1].sum())
        exact_x &= bool((y[diff] == 438.8037).all())
    check('coordinate_candidate_exactly_four_explicit_x_edits',
          set(changed) == {'node_001', 'node_010'} and changes == 4 and ychanges == 0 and exact_x,
          changed_nodes=changed, changed_scalars=changes, changed_y=ychanges)
    check('coordinate_candidate_other_identity_fields_fixed',
          set(a) == set(b) and old['source_records'] == new['source_records'] and
          old['manual_feature_order'] == new['manual_feature_order'] and
          old['reference'] == new['reference'] and
          all(a[k]['support'] == b[k]['support'] and a[k]['members'] == b[k]['members'] for k in a))
    receipt = js('coordinate_candidate/CHECKS.json')
    target = scores[scores.team_key == receipt['team_key']]
    refs = csv('coordinate_candidate/ACTUAL_DOWNSTREAM_REFERENCES.csv')
    check('coordinate_candidate_not_promoted_into_main57', len(target) == 1 and
          target.B8L2.isna().all() and (target.score_status == 'invalid_floor').all() and
          receipt['candidate_not_promoted_to_fixed_coordinate_branch'])
    check('coordinate_candidate_actual_references_only_AC_alliances',
          refs.module.value_counts().to_dict() == {'ac_registered': 50, 'changed_alliances': 2})
    EVIDENCE['coordinate_candidate'] = dict(main_branch_scored=False,
        candidate_Q=receipt['B8L2'], candidate_D10=receipt['D10'], references=52,
        visible_kernel=receipt['camera_in_visible_kernel'], adopted=False)


def review_half(scores):
    old, new = [csv('half_qonly/HALF_' + v + '_EVENTS.csv.gz') for v in ['AUTOMATIC', 'ASSISTED']]
    check('half_event_identities_fixed', len(old) == len(new) == 279 and
          old.event_id.is_unique and same(old.event_id, new.event_id))
    touched = old[['A_team_key', 'B_team_key', 'C_team_key']].isin(set(scores.team_key)).any(axis=1)
    current = old.updated_class_legal.eq(True)
    receipt = js('half_qonly/CHECKS.json')
    counts = [int(old.loc[touched, 'event_id'].nunique()),
              int(old.loc[touched & current, 'event_id'].nunique())]
    check('half_receipt_corrected_unique_affected_events', counts == [13, 13] and
          receipt['affected_frozen_half_events'] == 13 and receipt['affected_current_half_events'] == 13,
          frozen_affected=counts[0], current_affected=counts[1], original_current_events=int(current.sum()))
    fixed_cols = [c for c in old if c in new and
                  ('time' in c or 'labor' in c or 'class' in c or c.endswith('_workers') or
                   c.endswith('_team_key') or c.endswith('reference_id') or c.endswith('reference_version'))]
    check('half_original_time_labels_members_references_unchanged',
          same(old[fixed_cols], new[fixed_cols]), fields=len(fixed_cols))
    preserved, compared = [], 0
    for arm in ['A', 'B', 'C']:
        c = arm + '__B8L2'
        mask = old[c].notna()
        preserved.append(close(old.loc[mask, c], new.loc[mask, c]))
        compared += int(mask.sum())
    check('half_old_scored_endpoint_values_preserved', all(preserved), endpoint_references=compared)
    summary = csv('half_qonly/HALF_SUMMARY.csv')
    details = []
    for version, frame in [('automatic', old), ('assisted_expanded', new)]:
        a, b, c = [frame[arm + '__B8L2'] for arm in ['A', 'B', 'C']]
        calculations = {'gap_A': (c-a).abs()-(b-a).abs(),
                        'gap_sym': ((c-a).abs()+(c-b).abs())/2-(b-a).abs(), 'CB': c-b}
        for metric, values in calculations.items():
            check('half_contrast_formula:' + version + ':' + metric, close(values, frame[metric]))
            for n in [14, 20]:
                valid = frame[current & frame.n.eq(n) & frame[metric].notna()]
                images = hierarchical_images(valid, [metric])
                target = summary[(summary.scope == 'updated_labels_legal_subset') &
                    (summary.version == version) & (summary.n == n) & (summary.metric == metric)].iloc[0]
                value = float(images[metric].mean())
                check('half_image_weighted_summary:' + version + ':' + str(n) + ':' + metric,
                      close([value], [target['mean']]) and len(valid) == target.valid_events and
                      len(images) == target.images, mean=value, events=len(valid), images=len(images))
                details.append(dict(version=version, n=n, metric=metric, mean=value,
                                    events=len(valid), images=len(images)))
    EVIDENCE['half_current_summary_independent'] = details
    correction = js('half_qonly/RECEIPT_CORRECTION_20261104.json')
    hashes = correction['science_csv_sha256_before_and_after']
    hash_parity = {}
    for filename, expected in hashes.items():
        path = BASE / 'half_qonly' / filename
        READ_FILES.add(path)
        hash_parity[filename] = hashlib.sha256(path.read_bytes()).hexdigest() == expected
    check('half_receipt_correction_did_not_change_25_scientific_CSVs',
          len(hash_parity) == 25 and all(hash_parity.values()), file_hash_parity=hash_parity)
    EVIDENCE['receipt_correction'] = correction


def review_qonly():
    summary = csv('half_qonly/QONLY_SUMMARY.csv')
    values = []
    frames = {}
    for version, name in [('automatic', 'AUTOMATIC'), ('assisted_original_support', 'ASSISTED_ORIGINAL_SUPPORT'),
                          ('assisted_expanded', 'ASSISTED_EXPANDED')]:
        frame = csv('half_qonly/QONLY_' + name + '_PAIRED_EVENTS.csv.gz')
        frames[version] = frame
        check('qonly_pair_delta:' + version,
              close(frame.B8L2_structure-frame.B8L2_comparator, frame.B8L2_delta))
        for (n, comparator), group in frame.groupby(['n', 'comparator']):
            if comparator not in ['Q_RAW', 'Q_PEER']: continue
            cols = ['B8L2_structure', 'B8L2_comparator', 'B8L2_delta']
            valid = group.dropna(subset=cols)
            images = hierarchical_images(valid, cols)
            building = images.groupby('building').B8L2_delta.agg(['sum', 'count'])
            rng = np.random.default_rng(20261031)
            ix = rng.integers(0, len(building), (2000, len(building)))
            draws = building['sum'].to_numpy()[ix].sum(axis=1)/building['count'].to_numpy()[ix].sum(axis=1)
            lo, hi = np.quantile(draws, [.025, .975])
            mean = float(images.B8L2_delta.mean())
            target = summary[(summary.version == version) & (summary.subset == 'all_registered') &
                             (summary.n == n) & (summary.comparator == comparator) &
                             (summary.metric == 'B8L2')].iloc[0]
            check('qonly_building_bootstrap:' + version + ':' + str(n) + ':' + comparator,
                  close([mean, lo, hi], [target.effect, target.ci_low, target.ci_high]) and
                  len(valid) == target.events and len(images) == target.images,
                  mean=mean, lo=float(lo), hi=float(hi), events=len(valid), images=len(images))
            values.append(dict(version=version, n=int(n), comparator=comparator, mean=mean,
                               lo=float(lo), hi=float(hi), events=len(valid), images=len(images)))
    old = frames['automatic']; common = frames['assisted_original_support']
    check('qonly_original_quality_support_unchanged',
          same(old[['event_id', 'comparator']], common[['event_id', 'comparator']]) and
          close(old[['B8L2_structure', 'B8L2_comparator', 'B8L2_delta']],
                common[['B8L2_structure', 'B8L2_comparator', 'B8L2_delta']]))
    EVIDENCE['qonly_bootstrap_independent'] = values


def review_preprocessing_and_dependencies(scores):
    table = csv('preprocessing_audit/ALL_INVENTORY_PREPROCESSING_CHECKS.csv.gz')
    ready = table[table.ready.eq(True)]
    zero = ['preprocessing_max_difference', 'shared_x_max_difference',
            'idempotence_max_difference', 'ordered_view_max_difference']
    flags = ['y_unchanged', 'point_count_unchanged', 'source_point_mapping_complete']
    check('preprocessing_all_available_inputs_replay', len(table) == 10730 and len(ready) == 10597 and
          ready[zero].eq(0).all().all() and ready[flags].eq(True).all().all(),
          total=len(table), ready=len(ready), unavailable=len(table)-len(ready))
    nodes = csv('preprocessing_audit/57_TEAM_NODE_CENTER_CHECKS.csv')
    check('436_frozen_node_centres_preprocessed', len(nodes) == 436 and
          nodes.center_max_difference.eq(0).all() and nodes.vote_threshold_valid.all() and
          nodes.unique_workers_valid.all() and nodes.own_pair_shared_x.all() and not nodes.recentered.any())
    deps = csv('dependencies/CURRENT_EXACT_REFERENCES.csv.gz')
    check('actual_reference_intersection_536_57', len(deps) == 536 and deps.team_key.nunique() == 57 and
          set(deps.team_key) == set(scores.team_key))
    training_path = ROOT / 'research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/rfuse/NATURAL_TRAINING_ENDPOINTS.csv.gz'
    READ_FILES.add(training_path)
    training = pd.read_csv(training_path, usecols=['team_key'])
    check('RFUSE_actual_training_intersection_zero', len(training) == 28312 and
          not training.team_key.isin(set(scores.team_key)).any(), training_rows=len(training))
    EVIDENCE['module_references'] = deps.groupby('module').agg(
        refs=('team_key', 'size'), teams=('team_key', 'nunique')).reset_index().to_dict('records')


def review_composition():
    table = csv('composition/ALL_METHOD_COMPARISON.csv')
    identity = maxdiff(table.total_variance, table.within_variance+table.between_variance)
    mask = table.total_variance.gt(1e-12) & table.between_share.notna()
    ratio = maxdiff(table.loc[mask, 'between_share'],
                    table.loc[mask, 'between_variance']/table.loc[mask, 'total_variance'])
    check('composition_variance_decomposition_and_macro_ratio', identity < 1e-7 and ratio < 1e-8,
          rows=len(table), max_variance_identity_error=identity, max_macro_ratio_error=ratio)
    keys = ['method', 'condition', 'support', 'metric', 'time_source', 'summary_axis', 'summary_value']
    q = table[table.metric.isin(['B8L2', 'D10', 'IoU3D100'])]
    old = q[q.version.eq('automatic')].set_index(keys).sort_index()
    common = q[q.version.eq('assisted_original_support')].set_index(keys).sort_index()
    cols = ['total_variance', 'within_variance', 'between_variance', 'between_share', 'valid_team_links']
    check('composition_original_quality_support_unchanged', old.index.equals(common.index) and
          close(old[cols], common[cols]))
    selection = table[(table.method == 'TARGET_DSTRUCT_K3') & (table.metric == 'B8L2') &
        (table.support == 'method_known') & (table.summary_axis == 'all')]
    EVIDENCE['composition_macro'] = selection[['version', 'between_share', 'valid_team_links',
        'panels', 'images', 'buildings']].to_dict('records')


def review_natural_policy_alliances():
    old = csv('natural/aggregate_automatic/PRIMARY_SMALL_CHANGE_ONSETS.csv')
    new = csv('natural/stage03_response/manual/PRIMARY_SMALL_CHANGE_ONSETS.csv')
    keys = ['pool_id', 'metric', 'tolerance']
    old = old.set_index(keys).sort_index(); new = new.set_index(keys).sort_index()
    check('natural_formal_onsets_preserved', old.index.equals(new.index) and
          close(old.onset_k, new.onset_k))
    col = 'first_small_range_without_followup_gate'
    changed = ~(old[col].eq(new[col]) | (old[col].isna() & new[col].isna()))
    diagnostics = []
    for key in old.index[changed]:
        diagnostics.append(dict(pool_id=key[0], metric=key[1], tolerance=key[2],
                                old=float(old.at[key, col]), new=float(new.at[key, col])))
    check('natural_two_ungated_diagnostic_onsets_change', len(diagnostics) == 2 and
          all(x['old'] == 4 and x['new'] == 3 for x in diagnostics), changes=diagnostics)
    change_table = csv('natural/AGGREGATE_NUMERIC_CHANGES.csv.gz')
    check('natural_aggregate_1069_changed_cells', len(change_table) == 1069)
    policy = csv('policy/LATE_GLOBAL_COMPARISON.csv')
    keys = ['version', 'policy', 'difficulty', 'phase', 'metric', 'weighting']
    oldp = policy[policy.connection_version.eq('automatic')].set_index(keys).sort_index()
    newp = policy[policy.connection_version.eq('manual_assisted')].set_index(keys).sort_index()
    if newp.empty:
        newp = policy[policy.connection_version.ne('automatic')].set_index(keys).sort_index()
    signflip = int((np.sign(oldp.estimate) != np.sign(newp.estimate)).sum())
    intervals = {}
    for field in ['path', 'building']:
        relation_old = np.where(oldp[field+'_lo'] > 0, 1, np.where(oldp[field+'_hi'] < 0, -1, 0))
        relation_new = np.where(newp[field+'_lo'] > 0, 1, np.where(newp[field+'_hi'] < 0, -1, 0))
        intervals[field] = int((relation_old != relation_new).sum())
    numeric = int((np.abs(oldp.estimate-newp.estimate) > 1e-9).sum())
    check('policy_352_groups_104_changed_points_no_sign_CI_change',
          oldp.index.equals(newp.index) and len(oldp) == 352 and numeric == 104 and
          signflip == 0 and all(x == 0 for x in intervals.values()),
          groups=len(oldp), changed_points=numeric, sign_flips=signflip, interval_changes=intervals)
    alliances = csv('alliances/FULL_VS_BEST_PURE_CONNECTION_COMPARISON.csv')
    selected = alliances[(alliances.scope == 'primary') & (alliances.version == 'updated') &
                          (alliances.unknown_background_included == False)]
    check('alliances_main205_direction_counts_unchanged', len(selected) == 2 and
          selected.images.eq(205).all() and selected.pure_better_images.eq(169).all() and
          selected.full_better_images.eq(36).all())
    other = alliances[(alliances.scope == 'other_admitted') & (alliances.version == 'updated') &
                       (alliances.unknown_background_included == False)]
    EVIDENCE['alliances_other_updated'] = other.to_dict('records')
    check('alliances_other_support_expansion_not_new_images', len(other) == 2 and
          other.images.eq(23).all() and sorted(other.pools.tolist()) == [24, 25])
    rows = csv('alliances/AFFECTED_ALLIANCE_ROWS.csv')
    check('alliances_19_rows_17_newly_scored_no_old_zero', len(rows) == 19 and
          rows.team_key.nunique() == 12 and rows.old_Q.isna().all() and rows.new_Q.notna().sum() == 17)
    resolved = csv('alliances/ALLIANCE_414_RESOLUTION_ASSISTED.csv')
    check('alliances_current_resolution_uses_resolved_team_key', len(resolved) == 414 and
          same(resolved.team_key, resolved.assisted_team_key) and
          resolved.assisted_status.eq('capacity_only').sum() == 11)


def review_ac():
    support = csv('ac/AFFECTED_EVENT_SUPPORT_BY_METRIC.csv')
    q = support[support.metric.eq('B8L2_CA')].iloc[0]
    check('AC_Q_support_0_to257_not_0_score_improvement', q.affected_events == 339 and
          q.original_valid == 0 and q.assisted_valid == 257 and q.common_valid == 0 and
          q.newly_valid == 257 and q.lost_valid == 0 and q.changed_on_common == 0 and
          pd.isna(q.original_mean_on_common))
    marker_fields = {'A_single_time_source', 'C_single_time_source', 'actual_D_members',
                     'actual_X_members', 'actual_Z_members'}
    automatic = csv('ac/AFFECTED_EVENT_METRICS_AUTOMATIC.csv.gz', keep_default_na=False)
    assisted = csv('ac/AFFECTED_EVENT_METRICS_ASSISTED.csv.gz')
    source_empty_checks = []
    for name in ['EVENT_AND_UNTOUCHED_PARITY.csv', 'MAIN_AGGREGATION_PARITY.csv']:
        parity = csv('ac/' + name)
        markers = parity[parity.missing_disagreements.ne(0)]
        explained = markers.empty
        if not markers.empty and set(markers.field).issubset(marker_fields):
            explained = True
            for context, rows in markers.groupby('context'):
                pid = context.split(':', 1)[1]
                original_path = ROOT / 'research/workers/personnel_ac_v21_20261030/stage04_metrics/metric_shards' / (pid+'.csv.gz')
                READ_FILES.add(original_path)
                columns = ['event_id'] + rows.field.tolist()
                original = pd.read_csv(original_path, usecols=columns, keep_default_na=False)
                replay = automatic[automatic.pool_id.eq(pid)].set_index('event_id')
                original = original[original.event_id.isin(replay.index)].set_index('event_id').loc[replay.index]
                for row in rows.itertuples():
                    identical = same(original[row.field], replay[row.field])
                    empty_count = int(original[row.field].eq('').sum())
                    explained &= identical and empty_count == row.missing_disagreements
                    source_empty_checks.append(dict(context=context, field=row.field,
                        equal_raw_text=identical, empty_cells=empty_count,
                        marker_disagreements=int(row.missing_disagreements)))
        check('AC_baseline_receipt:' + name, parity.mismatches.eq(0).all() and
              explained, rows=len(parity), maximum_error=float(parity.maximum_absolute_difference.max()),
              text_marker_disagreements=int(parity.missing_disagreements.sum()),
              text_marker_differences_verified_against_original_raw_CSV=bool(explained))
    EVIDENCE['AC_text_empty_marker_verification'] = source_empty_checks
    check('AC_method_rows_and_unique_physical_pairs_separated',
          len(automatic) == 339 and automatic.physical_pair_id.nunique() == 245 and
          assisted.B8L2_CA.notna().sum() == 257 and
          assisted.loc[assisted.B8L2_CA.notna(), 'physical_pair_id'].nunique() == 193,
          method_events=len(automatic), physical_pairs=int(automatic.physical_pair_id.nunique()),
          assisted_method_Q=int(assisted.B8L2_CA.notna().sum()),
          assisted_physical_Q=int(assisted.loc[assisted.B8L2_CA.notna(), 'physical_pair_id'].nunique()))
    EVIDENCE['AC_receipt'] = js('ac/AC_IMPACT_RECEIPT.json')


def review_versions_and_gzip():
    modules = ['endpoints', 'coordinate_candidate', 'preprocessing_audit', 'dependencies',
               'half_qonly', 'composition', 'natural', 'policy', 'alliances', 'ac']
    versions = {}
    for module in modules:
        receipt = js(module + '/CHECKS.json')
        commit = receipt.get('source_commit', receipt.get('source_repository_commit'))
        if commit is not None: versions[module] = commit
    check('producer_source_commits_consistent', all(v == COMMIT for v in versions.values()),
          commits=versions)
    validated = []
    errors = []
    for path in sorted(BASE.rglob('*.gz')):
        try:
            size = 0
            with gzip.open(path, 'rb') as f:
                for chunk in iter(lambda: f.read(4*1024*1024), b''):
                    size += len(chunk)
            validated.append(dict(path=path.relative_to(ROOT).as_posix(),
                                  compressed_bytes=path.stat().st_size, uncompressed_bytes=size))
        except Exception as error:
            errors.append(dict(path=str(path), error=str(error)))
    check('all_current_gzip_outputs_read_to_EOF_CRC', not errors,
          files=len(validated), errors=errors)
    EVIDENCE['gzip_validation'] = validated
    # Same-room was produced by this reviewer: do not mislabel it independent.
    same_room = js('same_room/CHECKS.json')
    EVIDENCE['same_room_review_status'] = dict(
        independence='producer self-validation, not a second independent implementation',
        receipt=same_room,
        external_readonly_spotcheck={
            'reviewer': '/root/release_and_geometry_inputs',
            'review_received': True,
            'scope': 'Independent reading of saved K3 support, directions, summary, geometry and report; not a second full computation.',
            'result': 'pass',
            'Q_common6': [295, 318], 'registered_events': 322,
            'geometry_common6': [240, 240], 'pairs': 19, 'buildings': 7,
            'positive_pair_means_GA_GS_CB': [17, 16, 19],
            'CB_both_views_positive': 18,
            'GA_opposite_view_signs': [5, 4], 'GA_both_views_negative': [0, 1],
            'source_tables': ['same_room/SUPPORT_CHANGES.csv',
                'same_room/QUALITY_COMPONENT_REPETITION_SUMMARY.csv',
                'same_room/PAIR_DIRECTION_STATES.csv', 'same_room/geometry/CURRENT_SUPPORT.csv']})


def main():
    scores = review_endpoints()
    review_candidate(scores)
    review_half(scores)
    review_qonly()
    review_preprocessing_and_dependencies(scores)
    review_composition()
    review_natural_policy_alliances()
    review_ac()
    review_versions_and_gzip()
    hashes = []
    for path in sorted(READ_FILES):
        hashes.append(dict(path=path.relative_to(ROOT).as_posix(),
                           bytes=path.stat().st_size,
                           sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    result = dict(review_version='independent_cross_module_review_20261104_v1',
                  source_repository_commit=COMMIT,
                  scope='Saved-artifact cross-checks, selected independent math and bootstrap; no matching/fusion rerun',
                  same_room_independence='This reviewer implemented same_room; its baseline checks are self-validation.',
                  later_addendum_scope={'complete_stop_replay_nodes': {
                      'owner': '/root/final_statistics_review',
                      'included_in_this_review': False,
                      'final_receipt': 'FINAL_CHECKS.json',
                      'requirement': 'Read complete frozen replay_nodes source, not only the 1534-row patch.'}},
                  passed=all(c['passed'] for c in CHECKS),
                  checks_count=len(CHECKS), failures=[c for c in CHECKS if not c['passed']],
                  checks=CHECKS, evidence=EVIDENCE, input_hashes=hashes)
    (BASE / 'INDEPENDENT_REVIEW_CHECKS.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps(dict(passed=result['passed'], checks=len(CHECKS),
                          failures=result['failures'], input_files=len(hashes)), ensure_ascii=False))


if __name__ == '__main__':
    main()
