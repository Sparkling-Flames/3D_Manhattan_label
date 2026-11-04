"""Propagate the 57 exact human-order endpoints through saved ABC and Q-only designs.

This is an auxiliary sensitivity analysis. Original teams, labels, scores and
source files are never overwritten. Event replicates -> background -> block ->
pool -> image weighting is retained; buildings are the bootstrap clusters.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
REL = ROOT / 'research/data/releases/v2.1'
UP = REL / 'admitted_space_extension/image_difficulty_20261030'
PRO = ROOT / 'research/workers/personnel_full_chain_v21_20261030/HOHONET_v21_full_chain_20261030'
QONLY = REL / 'q_only_exchange_20261031'
CASE = REL / 'half_team_current_exceptions_20261031'
BASE = ROOT / 'research/fusion/manual_order_impact_20261104'
OUT = BASE / 'half_qonly'
GROUP_KEYS = ['n', 'building', 'image', 'pool_id', 'block_id', 'background_id']
SCALAR_METRICS = [
    'B8L2', 'D10', 'IoU3D100', 'iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter',
    'omission', 'extension', 'height_mean_ratio', 'nodes', 'fusion_turn_n',
    'fusion_short_turn_edges', 'fusion_redundancy_n', 'geometry_area_h2',
    'height_mean_h', 'height_min_h', 'height_max_h', 'centroid_x_h', 'centroid_z_h',
    'ref_node_recall_5', 'ref_node_recall_9', 'ref_edge_recall_5', 'ref_edge_recall_9',
    'reference_node_shortfall', 'reference_node_excess', 'top_y_mean_px', 'bottom_y_mean_px',
    'matched_ref_top_abs_deg', 'matched_ref_bottom_abs_deg', 'matched_ref_horizontal_abs_deg',
    'matched_ref_pair_fraction', 'boundary_loss', 'direction_loss', 'global_height_loss',
    'local_height_loss', 'height_loss', 'floor_WQ', 'WQ', 'WQ_no_D', 'WQ_no_B',
    'WQ_no_H', 'height_drop_current', 'diag_wall_coverage_03', 'diag_wall_coverage_05',
    'diag_corner_recall_05', 'source_time_total_seconds', 'recorded_time_total_seconds',
    'minimum_support', 'identity_groups_n', 'unselected_groups_n', 'half_vote_nodes',
    'selected_support_min', 'target_individual_B8L2_mean', 'target_individual_B8L2_min',
]
Q_METRICS = ['B8L2', 'D10', 'IoU3D100', 'fusion_turn_n', 'fusion_short_turn_edges',
             'boundary_loss', 'direction_loss', 'height_loss', 'omission', 'extension',
             'ref_node_recall_5']
GEOMETRY_METRICS = ['geometry_bev_distance', 'geometry_centroid_distance',
                    'geometry_log_area_distance', 'geometry_pair_angle']
MECHANISM_METRICS = ['B8L2', 'D10', 'IoU3D100', 'S_bottom_deg', 'dir', 'Hmean',
                     'omission', 'extension', 'fusion_turn_n', 'fusion_short_turn_edges',
                     'fusion_redundancy_n', 'ref_node_recall_5', 'ref_edge_recall_5',
                     'geometry_area_h2', 'height_mean_h', 'centroid_x_h', 'centroid_z_h',
                     'boundary_loss', 'direction_loss', 'height_loss',
                     'selected_support_min', 'half_vote_nodes']


def read_json(path):
    path = Path(path)
    with (gzip.open(path, 'rt', encoding='utf-8-sig') if path.suffix == '.gz'
          else path.open(encoding='utf-8-sig')) as handle:
        return json.load(handle)


def read_rows(path):
    path = Path(path)
    with (gzip.open(path, 'rt', encoding='utf-8-sig') if path.suffix == '.gz'
          else path.open(encoding='utf-8-sig')) as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def csv(frame, name):
    OUT.mkdir(parents=True, exist_ok=True)
    destination = OUT / name
    temporary = destination.with_name(destination.name+'.tmp')
    pd.DataFrame(frame).to_csv(temporary, index=False, encoding='utf-8-sig',
                              compression='gzip' if name.endswith('.gz') else None)
    temporary.replace(destination)


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if math.isfinite(value) else None
    return value


def json_out(value, name):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(clean(value), ensure_ascii=False, indent=2,
                                     allow_nan=False) + '\n', encoding='utf-8')


def number(value):
    return float(value) if isinstance(value, (float, int, np.number)) and not pd.isna(value) else np.nan


def finite(value):
    return np.isfinite(number(value))


def as_members(value):
    if isinstance(value, (list, tuple)):
        return set(value)
    return set(value.split('|')) if isinstance(value, str) and value else set()


def image_means(events, columns):
    """Exact original hierarchy, including uneven replicate/background counts."""
    if events.empty:
        return pd.DataFrame(columns=GROUP_KEYS[:3] + list(columns))
    result = events.groupby(GROUP_KEYS, dropna=False)[columns].mean()
    for keys in [GROUP_KEYS[:-1], GROUP_KEYS[:-2], GROUP_KEYS[:3]]:
        result = result.groupby(level=keys, dropna=False).mean()
    return result.reset_index()


def cluster_interval(images, column):
    """Original Q-only bootstrap: image-equal mean, 2,000 building resamples."""
    grouped = images.groupby('building')[column].agg(['sum', 'count'])
    if grouped.empty:
        return [np.nan, np.nan]
    rng = np.random.default_rng(20261031)
    sample = rng.integers(0, len(grouped), size=(2000, len(grouped)))
    values = grouped['sum'].to_numpy()[sample].sum(axis=1) / grouped['count'].to_numpy()[sample].sum(axis=1)
    return np.quantile(values, [.025, .975]).tolist()


def scalar_contrasts(a, b, c):
    """Never infer a numerical improvement from an unscored endpoint."""
    a, b, c = map(number, (a, b, c))
    out = {'BA': b-a, 'CA': c-a, 'CB': c-b}
    if np.isfinite([a, b, c]).all():
        within, direct, symmetric = abs(b-a), abs(c-a), (abs(c-a)+abs(c-b))/2
        out.update(within=within, cross=symmetric, gap=symmetric-within,
                   AC_absolute=direct, AC_gap=direct-within,
                   cross_direct=direct, cross_symmetric=symmetric)
    else:
        out.update({k: np.nan for k in ['within', 'cross', 'gap', 'AC_absolute', 'AC_gap',
                                       'cross_direct', 'cross_symmetric']})
    return out


def labor(row):
    value = row.get('record_time_by_kind_json')
    if not isinstance(value, str):
        return None, None
    kinds = json.loads(value)
    signature = tuple(sorted((key, v['n']) for key, v in kinds.items()))
    if not kinds or any(v['known_n'] != v['n'] or v['total_seconds'] is None for v in kinds.values()):
        return signature, None
    return signature, sum(v['total_seconds'] for v in kinds.values())


def merge_endpoint(old, new):
    """Keep endpoint identity and original annotation labour, patch computed outputs."""
    assert old['team_key'] == new['team_key']
    for key in ['pool_id', 'reference_id', 'reference_version']:
        if isinstance(old.get(key), str) and old[key] and isinstance(new.get(key), str):
            assert old[key] == new[key], (old['team_key'], key, old[key], new[key])
    for key in ['member_workers', 'member_object_ids']:
        if as_members(old.get(key)) and as_members(new.get(key)):
            assert as_members(old[key]) == as_members(new[key]), (old['team_key'], key)
    for key in ['nodes', 'minimum_support', 'half_vote_nodes', 'selected_support_min']:
        if finite(old.get(key)) and finite(new.get(key)):
            assert abs(float(old[key])-float(new[key])) < 1e-9, (old['team_key'], key)
    if finite(old.get('B8L2')):
        assert finite(new.get('B8L2')) and abs(old['B8L2']-new['B8L2']) < 1e-8, old['team_key']
    result = copy.deepcopy(old)
    for key, value in new.items():
        if not key.startswith('automatic_') and key not in ['automatic', 'assisted', 'fixed_nodes', 'provenance']:
            result[key] = value
    # Sorting labour has no recorded duration. It must not overwrite source labour.
    for key in old:
        if 'time' in key or key.startswith('target_individual_'):
            result[key] = old[key]
    return result


def scalar_rows(path):
    return {row['team_key']: row for row in pd.read_csv(path, low_memory=False).to_dict('records')}


def endpoint_index(aux_path, geometry_paths):
    from research.workers.personnel_v21_reselection_20261029.analysis.legacy_geometry_diagnostics import refdiagnostic
    auxiliary = {row['team_key']: row for row in read_rows(aux_path)}
    assert len(auxiliary) == 57, len(auxiliary)
    for row in auxiliary.values():
        refdiagnostic(row, {'reference': row['reference_snapshot']})
        row['reference_node_shortfall'] = max(0, len(row['reference_snapshot']['points_1024x512'])//2-row['nodes'])
        row['reference_node_excess'] = max(0, row['nodes']-len(row['reference_snapshot']['points_1024x512'])//2)
    csv([{key: row.get(key) for key in ['team_key', 'reference_id', 'reference_version',
         'matched_ref_pair_fraction', 'matched_ref_top_abs_deg', 'matched_ref_bottom_abs_deg',
         'matched_ref_horizontal_abs_deg', 'reference_node_shortfall', 'reference_node_excess']}
         for row in auxiliary.values()], 'AUXILIARY_LEGACY_REFERENCE_DIAGNOSTICS.csv')
    q_endpoints = {row['team_key']: row for row in read_rows(QONLY / 'ENDPOINTS.jsonl.gz')}
    old = scalar_rows(PRO / 'stage01_half_team/SAVED_ENDPOINT_SCALARS.csv.gz')
    for key, row in q_endpoints.items():
        if key in old:
            for metric in ['B8L2', 'D10', 'nodes']:
                a, b = number(old[key].get(metric)), number(row.get(metric))
                assert (np.isnan(a) and np.isnan(b)) or abs(a-b) < 1e-8, (key, metric)
            old[key].update(row)
        else:
            old[key] = copy.deepcopy(row)
    pools = {pool['pool_id']: pool for pool in read_json(REL / 'pools/INPUT_SNAPSHOT.json')['images']}
    counterpart_diagnostics = []
    for path in geometry_paths:
        path = Path(path)
        rows = [read_json(path)] if path.name.endswith('.json.gz') else list(read_rows(path))
        for row in rows:
            key = row.get('team_key')
            if key in old and row.get('geometry') is not None:
                for metric in ['B8L2', 'D10']:
                    if finite(old[key].get(metric)) and finite(row.get(metric)):
                        assert abs(float(old[key][metric])-row[metric]) < 1e-8
                old[key]['geometry'] = row['geometry']
                pool = pools[old[key]['pool_id']]
                for field in ['reference_id', 'reference_version']:
                    assert old[key][field] == pool['meta'][field], (key, field)
                diagnostics = refdiagnostic({'geometry': row['geometry']}, pool)
                for field, value in diagnostics.items():
                    if field == 'geometry':
                        continue
                    if finite(old[key].get(field)):
                        assert abs(old[key][field]-value) < 1e-8, (key, field)
                    old[key][field] = value
                counterpart_diagnostics.append({**{field: old[key].get(field) for field in ['team_key', 'reference_id', 'reference_version']},
                                                **{field: value for field, value in diagnostics.items() if field != 'geometry'},
                                                'geometry_source': str(path.relative_to(ROOT))})
    csv(pd.DataFrame(counterpart_diagnostics).drop_duplicates('team_key'),
        'UNCHANGED_AUTOMATIC_LEGACY_REFERENCE_DIAGNOSTICS.csv')
    revised = {key: merge_endpoint(row, auxiliary[key]) if key in auxiliary else copy.deepcopy(row)
               for key, row in old.items()}
    return auxiliary, old, revised, q_endpoints


def counterpart_geometry_sources(geometry_paths):
    """Reuse saved traces; replay only the two specifically missing automatic geometries."""
    auxiliary_keys = set(pd.read_csv(ROOT / 'research/fusion/missing_ring_review_20261104/user_order_return/VALIDATED_ENDPOINT_ORDERS.csv.gz').team_key)
    events = pd.read_csv(PRO / 'stage01_half_team/EVENTS_WITH_ENDPOINTS.csv.gz', low_memory=False)
    touched = events[[arm+'_team_key' for arm in 'ABC']].isin(auxiliary_keys).any(axis=1)
    needed = set(events.loc[touched, [arm+'_team_key' for arm in 'ABC']].values.ravel())-auxiliary_keys
    selected, absent = list(geometry_paths), []
    for key in sorted(needed):
        candidates = [PRO / 'stage01_half_team/trace_endpoints' / (key+'.json.gz'),
                      CASE / 'trace_endpoints' / (key+'.json.gz')]
        found = next((path for path in candidates if path.exists()), None)
        if found is not None:
            selected.append(found)
        else:
            absent.append(key)
    expected = ['x8F5xyUWy9e-08__manual__0b13997fd3__584bedec7fd695840f35',
                'x8F5xyUWy9e-08__manual__0b13997fd3__8e56e839f519ad223003']
    assert absent == expected, ('Unexpected missing counterpart geometry', absent)
    recovery = OUT / 'UNCHANGED_AUTOMATIC_GEOMETRY_RECOVERY.jsonl.gz'
    recovery_checks = OUT / 'UNCHANGED_AUTOMATIC_GEOMETRY_RECOVERY_CHECKS.json'
    if not recovery.exists():
        from .apply_manual_ring_orders_20261104 import diagnostic_modules, evaluate
        from .consensus_delivery_20261008 import fuse, WORKING_GAP
        from .scope_quality_scoring_20261016 import scoring_engine
        pools = {pool['pool_id']: pool for pool in read_json(REL / 'pools/INPUT_SNAPSHOT.json')['images']}
        originals = {row['team_key']: row for row in read_rows(QONLY / 'ENDPOINTS.jsonl.gz')}
        helpers = diagnostic_modules()
        rows, audits = [], []
        fields = ['B8L2', 'D10', 'IoU3D100', 'iou_2d', 'nodes', 'minimum_support', 'S_bottom_deg', 'dir', 'Hmean',
                  'Hcenter', 'omission', 'extension', 'fusion_turn_n', 'fusion_short_turn_edges', 'fusion_redundancy_n',
                  'geometry_area_h2', 'centroid_x_h', 'centroid_z_h', 'height_mean_h', 'height_min_h', 'height_max_h',
                  'boundary_loss', 'direction_loss', 'height_loss', 'ref_node_recall_5', 'ref_edge_recall_5']
        with scoring_engine() as (engine, models):
            for key in expected:
                old = originals[key]
                pool = pools[old['pool_id']]
                workers = as_members(old['member_workers'])
                records = sorted([row for row in pool['records'] if row['worker_id'] in workers], key=lambda row: row['worker_id'])
                assert len(records) == len(workers) == 20
                assert {row['object_id'] for row in records} == as_members(old['member_object_ids'])
                state = fuse(records, gap=WORKING_GAP)['automatic']
                identity = {field: old.get(field) for field in ['team_key', 'pool_id', 'image', 'image_id', 'building',
                            'condition', 'k', 'reference_id', 'reference_version', 'data_release', 'member_workers', 'member_object_ids']}
                new = evaluate(state, pool['reference'], engine, models, helpers, identity)
                differences = {}
                for field in fields:
                    a, b = number(old.get(field)), number(new.get(field))
                    assert np.isnan(a) == np.isnan(b), (key, field, a, b)
                    if np.isfinite(a):
                        differences[field] = abs(a-b)
                        assert differences[field] < 1e-7, (key, field, a, b)
                assert new['score_status'] == old['score_status']
                new['geometry_recovery_reason'] = 'Saved automatic counterpart had scalar-only archive; required for new pair-geometry distances'
                new['old_scalar_source'] = old.get('reuse_source')
                rows.append(new)
                audits.append(dict(team_key=key, members=len(workers), compared_fields=len(differences),
                                   maximum_absolute_difference=max(differences.values()), field_differences=differences,
                                   score_status_preserved=True, existing_team_only=True))
        OUT.mkdir(parents=True, exist_ok=True)
        with gzip.open(recovery, 'wt', encoding='utf-8') as handle:
            for row in rows:
                handle.write(json.dumps(clean(row), ensure_ascii=False, allow_nan=False)+'\n')
        json_out(dict(original_automatic_fuse_calls=2, new_teams=0, original_scores_modified=False,
                      order_policy='original automatic source-ring selection', working_gap=WORKING_GAP,
                      reason='exact missing counterpart geometry, not additional human order', audits=audits), recovery_checks.name)
    else:
        assert {row['team_key'] for row in read_rows(recovery)} == set(expected)
        assert recovery_checks.exists()
    selected.append(recovery)
    return list(dict.fromkeys(selected))


def classify_images(images, events):
    result = images.copy()
    key_count = events.groupby(['n', 'image']).size()
    key_valid = events.groupby(['n', 'image']).gap_A.count()
    result['events'] = [int(key_count.loc[(r.n, r.image)]) for r in result.itertuples()]
    result['scored_events'] = [int(key_valid.loc[(r.n, r.image)]) for r in result.itertuples()]
    result['partial_events'] = result.scored_events.lt(result.events)
    result['GA_nonpositive'] = result.gap_A.le(0)
    result['GS_nonpositive'] = result.gap_sym.le(0)
    result['CB_nonpositive'] = result.CB.le(0)
    result['no_joint_Q'] = result.gap_A.isna()
    result['numeric_exception'] = result[['GA_nonpositive', 'GS_nonpositive', 'CB_nonpositive', 'no_joint_Q']].any(axis=1)
    result['diagnostic'] = result.numeric_exception | result.partial_events
    return result


def add_original_mechanism_derivatives(events):
    """Retain the 22 metric-specific contrasts of analyze_half_mechanisms.py.

    These derive from archived arm scalars and do not fuse or rescore any team.
    Apply to both versions so adding an analysis column cannot look like newly
    acquired evaluability.
    """
    computed = {}
    for metric in MECHANISM_METRICS:
        values = {arm: pd.to_numeric(events[arm+'__'+metric], errors='coerce') for arm in 'ABC'}
        valid = pd.concat(values, axis=1).notna().all(axis=1)
        for pair in ['BA', 'CA', 'CB']:
            computed[metric+'__delta_'+pair] = values[pair[0]]-values[pair[1]]
        within = (values['B']-values['A']).abs()
        ac, bc = (values['C']-values['A']).abs(), (values['C']-values['B']).abs()
        for suffix, value in [('within', within), ('cross_direct', ac), ('cross_symmetric', (ac+bc)/2),
                              ('gap_A', ac-within), ('gap_S', (ac+bc)/2-within)]:
            computed[metric+'__'+suffix] = value.where(valid)
    for arm in 'ABC':
        computed[arm+'_incomplete'] = ~events[arm+'__complete_evaluable'].fillna(False).astype(bool)
    return pd.concat([events.drop(columns=[key for key in computed if key in events]),
                      pd.DataFrame(computed, index=events.index)], axis=1)


def patch_half_events(original, endpoints, auxiliary):
    from research.workers.personnel_v21_reselection_20261029.analysis.legacy_geometry_diagnostics import geometry_metrics
    result, missing_geometry = [], []
    for event in original.to_dict('records'):
        touched = [a for a in 'ABC' if event[a+'_team_key'] in auxiliary]
        if not touched:
            result.append(event)
            continue
        rows = {a: endpoints[event[a+'_team_key']] for a in 'ABC'}
        for arm, row in rows.items():
            if arm not in touched:
                continue
            for key, value in row.items():
                if arm+'__'+key in event and not isinstance(value, (dict, list)):
                    event[arm+'__'+key] = value
            event[arm+'_failed'] = not finite(row.get('B8L2'))
            event[arm+'_incomplete'] = not bool(row.get('complete_evaluable', False))
        for metric in SCALAR_METRICS:
            if not any(metric+'_'+pair in event for pair in ['BA', 'CA', 'CB']):
                continue
            values = [rows[a].get(metric) for a in 'ABC']
            for arm, value in zip('ABC', values):
                if arm in touched and arm+'_'+metric in event:
                    event[arm+'_'+metric] = value
                if arm in touched and arm+'__'+metric in event:
                    event[arm+'__'+metric] = value
            delta = scalar_contrasts(*values)
            for suffix, value in delta.items():
                if suffix in ['BA', 'CA', 'CB'] and not any(arm in touched for arm in suffix):
                    continue
                if metric+'_'+suffix in event:
                    event[metric+'_'+suffix] = value
            for suffix, source in [('same_origin_within', 'within'), ('same_origin_cross', 'cross_direct'),
                                   ('same_origin_gap', 'AC_gap'), ('symmetric_cross', 'cross_symmetric'),
                                   ('symmetric_gap', 'gap')]:
                if metric+'_'+suffix in event:
                    event[metric+'_'+suffix] = delta[source]
            for pair in ['BA', 'CA', 'CB']:
                if any(arm in touched for arm in pair):
                    event[metric+'_'+pair] = delta[pair]
        q = scalar_contrasts(*(rows[a].get('B8L2') for a in 'ABC'))
        ok = all(finite(rows[a].get('B8L2')) for a in 'ABC')
        event.update(gap_A=q['AC_gap'], gap_sym=q['gap'], CB=q['CB'], ABC_scored=ok)
        for pair in ['BA', 'CA', 'CB']:
            event['joint_Q_'+pair] = q[pair] if ok else np.nan
        event['C_between_A_B'] = float(min(number(rows['A'].get('B8L2')), number(rows['B'].get('B8L2')))
                                              <= number(rows['C'].get('B8L2'))
                                              <= max(number(rows['A'].get('B8L2')), number(rows['B'].get('B8L2')))) if ok else np.nan
        losses = [number(event.get(metric+'_CB')) for metric in ['boundary_loss', 'direction_loss', 'height_loss']]
        event['opposed_CB_loss_components'] = float(min(losses) < -1e-10 and max(losses) > 1e-10) if np.isfinite(losses).all() else np.nan
        for threshold in [90, 95]:
            event['all_Q_at_least_'+str(threshold)] = float(min(number(rows[a].get('B8L2')) for a in 'ABC') >= threshold) if ok else np.nan
        for metric in ['B8L2', 'D10']:
            contrasts = scalar_contrasts(*(rows[a].get(metric) for a in 'ABC'))
            for suffix in ['within', 'cross_direct', 'cross_symmetric']:
                event[metric+'_'+suffix] = contrasts[suffix] if ok else np.nan
        for pair, base in [('BA', 'A'), ('CA', 'A'), ('CB', 'B')]:
            top = pair[0]
            value = q[pair]
            event['Q_improved_'+pair] = float(value > 0) if np.isfinite(value) else np.nan
            event['Q_loss10_'+pair] = float(value < -10) if np.isfinite(value) else np.nan
            event['failure_or_loss10_'+pair] = float(not finite(rows[top].get('B8L2')) or value < -10) if finite(rows[base].get('B8L2')) else np.nan
        pair_values = {}
        for pair in ['AB', 'AC', 'BC']:
            a, b = pair
            if not any(arm in touched for arm in pair):
                pair_values[pair] = {metric: number(event.get(metric+'_'+pair)) for metric in GEOMETRY_METRICS}
                continue
            for arm in pair:
                if not rows[arm].get('geometry') and finite(rows[arm].get('B8L2')):
                    missing_geometry.append(dict(event_id=event['event_id'], arm=arm, team_key=rows[arm]['team_key']))
            measured = geometry_metrics(rows[a], rows[b])
            pair_values[pair] = {metric: measured.get(metric, np.nan) for metric in GEOMETRY_METRICS}
            for metric, value in pair_values[pair].items():
                event[metric+'_'+pair] = value
        for metric in GEOMETRY_METRICS:
            ab, ac, bc = [pair_values[pair].get(metric, np.nan) for pair in ['AB', 'AC', 'BC']]
            valid = np.isfinite([ab, ac, bc]).all()
            for suffix, value in [('within', ab), ('cross', (ac+bc)/2), ('gap', (ac+bc)/2-ab), ('AC_gap', ac-ab)]:
                if metric+'_'+suffix in event:
                    event[metric+'_'+suffix] = value if valid else np.nan
            for suffix, value in [('same_origin_within', ab), ('same_origin_cross', ac), ('same_origin_gap', ac-ab),
                                  ('symmetric_cross', (ac+bc)/2), ('symmetric_gap', (ac+bc)/2-ab)]:
                if metric+'_'+suffix in event:
                    event[metric+'_'+suffix] = value if valid else np.nan
        result.append(event)
    if missing_geometry:
        csv(pd.DataFrame(missing_geometry).drop_duplicates(), 'MISSING_UNCHANGED_GEOMETRY.csv')
        raise RuntimeError('Need original saved geometry for counterparts; see MISSING_UNCHANGED_GEOMETRY.csv')
    return pd.DataFrame(result)


def compare_numeric(old, new, keys, columns, label, checks, require_same_missing=True):
    pair = old.set_index(keys)[columns].join(new.set_index(keys)[columns], lsuffix='_old', rsuffix='_new', how='inner')
    assert len(pair) == len(old) == len(new), label
    maximum = 0.0
    for metric in columns:
        a, b = pd.to_numeric(pair[metric+'_old']), pd.to_numeric(pair[metric+'_new'])
        if require_same_missing:
            assert a.isna().equals(b.isna()), (label, metric, 'missingness')
        valid = a.notna() & b.notna()
        error = float((a[valid]-b[valid]).abs().max()) if valid.any() else 0.0
        assert error < 1e-8, (label, metric, error)
        maximum = max(maximum, error)
    checks.append(dict(check=label, rows=len(pair), columns=len(columns), maximum_error=maximum))


def half_metric_columns(events):
    primary = ['gap_A', 'gap_sym', 'CB', 'C_between_A_B', 'opposed_CB_loss_components', 'all_Q_at_least_90', 'all_Q_at_least_95']
    primary += ['B8L2_within', 'B8L2_cross_direct', 'B8L2_cross_symmetric', 'D10_within', 'D10_cross_direct', 'D10_cross_symmetric']
    primary += [metric+'_'+pair for metric in SCALAR_METRICS for pair in ['BA', 'CA', 'CB']]
    primary += [metric+'_'+pair for metric in GEOMETRY_METRICS for pair in ['AB', 'AC', 'BC', 'within', 'cross', 'gap', 'AC_gap']]
    primary += [metric+'_'+suffix for metric in SCALAR_METRICS+GEOMETRY_METRICS
                for suffix in ['same_origin_within', 'same_origin_cross', 'same_origin_gap', 'symmetric_cross', 'symmetric_gap']]
    primary += [metric+'__'+suffix for metric in MECHANISM_METRICS
                for suffix in ['delta_BA', 'delta_CA', 'delta_CB', 'within', 'cross_direct', 'cross_symmetric', 'gap_A', 'gap_S']]
    primary += ['record_time_'+pair+'_pct_source_matched' for pair in ['BA', 'CA', 'CB']]
    primary += [a+'_failed' for a in 'ABC'] + [a+'_incomplete' for a in 'ABC'] + ['ABC_scored']
    return list(dict.fromkeys(c for c in primary if c in events))


def summarize_half(original, revised, checks):
    metrics = half_metric_columns(revised)
    original = original.copy()
    for metric in metrics:
        if metric not in original:
            original[metric] = np.nan
    all_images, summaries, support_rows, buildings, difficulty_rows = [], [], [], [], []
    for scope in ['frozen_design', 'updated_labels_legal_subset']:
        old = original if scope == 'frozen_design' else original[original.updated_class_legal]
        new = revised.loc[old.index]
        for version, events in [('automatic', old), ('assisted_expanded', new)]:
            images = classify_images(image_means(events, metrics), events)
            images['difficulty'] = images.image.map(events.drop_duplicates('image').set_index('image').difficulty)
            images['scope'], images['version'] = scope, version
            all_images.append(images)
            build = images.groupby(['n', 'building'])[metrics].mean().reset_index()
            build['scope'], build['version'] = scope, version
            buildings.append(build)
            for (n, grade), part in images.groupby(['n', 'difficulty']):
                for metric in metrics:
                    values = part[metric].dropna()
                    difficulty_rows.append(dict(scope=scope, version=version, n=n, difficulty=grade, metric=metric,
                                                images=len(values), mean=values.mean(), positive=int(values.gt(1e-10).sum()),
                                                negative=int(values.lt(-1e-10).sum())))
            for n, part in images.groupby('n'):
                for metric in metrics:
                    values = part[metric].dropna()
                    summaries.append(dict(scope=scope, version=version, n=n, m=7, metric=metric,
                                          registered_events=int(events.n.eq(n).sum()),
                                          valid_events=int(events.loc[events.n.eq(n), metric].notna().sum()),
                                          registered_images=len(part), images=len(values),
                                          buildings=part.loc[part[metric].notna(), 'building'].nunique(),
                                          mean=values.mean(), median=values.median(), p10=values.quantile(.1),
                                          p90=values.quantile(.9), positive=int(values.gt(1e-10).sum()),
                                          negative=int(values.lt(-1e-10).sum()), zero=int(values.abs().le(1e-10).sum())))
        # Metric-specific original support prevents new availability from masquerading as score change.
        for n, old_n in old.groupby('n'):
            new_n = new.loc[old_n.index]
            for metric in metrics:
                old_valid, new_valid = old_n[metric].notna(), new_n[metric].notna()
                assert not (old_valid & ~new_valid).any(), (scope, n, metric, 'lost_support')
                original_support = old_n[old_valid]
                assisted_support = new_n.loc[original_support.index]
                common_error = float((original_support[metric].astype(float)-assisted_support[metric].astype(float)).abs().max()) if len(original_support) else 0.0
                is_formation = metric == 'ABC_scored' or metric.endswith(('_failed', '_incomplete'))
                if not is_formation:
                    assert common_error < 1e-8, (scope, n, metric, common_error)
                im = image_means(assisted_support, [metric])
                support_rows.append(dict(scope=scope, n=n, m=7, metric=metric,
                                         old_events=int(old_valid.sum()), new_events=int(new_valid.sum()),
                                         added_events=int((~old_valid & new_valid).sum()), old_images=old_n.loc[old_valid, 'image'].nunique(),
                                         new_images=new_n.loc[new_valid, 'image'].nunique(),
                                         old_buildings=old_n.loc[old_valid, 'building'].nunique(),
                                         new_buildings=new_n.loc[new_valid, 'building'].nunique(),
                                         original_support_mean=im[metric].mean(), original_support_max_difference=common_error,
                                         result_kind='formation' if is_formation else 'metric'))
    csv(pd.concat(all_images, ignore_index=True), 'HALF_IMAGES.csv.gz')
    csv(summaries, 'HALF_SUMMARY.csv')
    csv(support_rows, 'HALF_SUPPORT.csv')
    csv(pd.concat(buildings, ignore_index=True), 'HALF_BUILDINGS.csv')
    csv(difficulty_rows, 'HALF_DIFFICULTY.csv')
    old_summary = pd.read_csv(UP / 'HALF_SUMMARY.csv')
    current = pd.DataFrame(summaries)
    for row in old_summary.itertuples():
        for metric in ['gap_A', 'gap_sym', 'CB']:
            value = current[(current.scope == row.scope) & (current.version == 'automatic') & current.n.eq(row.n) & current.metric.eq(metric)].iloc[0]['mean']
            assert abs(value-getattr(row, metric)) < 1e-8, (row.scope, row.n, metric)
    checks.append(dict(check='original_half_summary_parity', rows=len(old_summary), columns=3, passed=True))
    return pd.concat(all_images, ignore_index=True), pd.DataFrame(summaries)


def q_pair_events(links, endpoints):
    pairs, statuses = [], []
    for event_id, group in links.groupby('event_id', sort=False):
        by = group.set_index('policy')
        base = by.loc['STRUCTURE']
        structure = endpoints[base.team_key]
        for policy in ['A', 'B', 'STRUCTURE', 'Q_RAW', 'Q_PEER']:
            row = endpoints[by.loc[policy, 'team_key']]
            statuses.append(dict(event_id=event_id, n=int(base.n), image=base.image, building=base.building,
                                 policy=policy, team_key=row['team_key'], scored=finite(row.get('B8L2')),
                                 complete=row.get('complete_evaluable'), below_four=row.get('below_four'),
                                 connection_available=row.get('connection_available'), score_status=row.get('score_status')))
        for policy in ['Q_RAW', 'Q_PEER', 'A', 'B']:
            comparator = endpoints[by.loc[policy, 'team_key']]
            result = {key: base[key] for key in GROUP_KEYS}
            result.update(event_id=event_id, comparator=policy)
            for metric in Q_METRICS:
                a, b = number(structure.get(metric)), number(comparator.get(metric))
                valid = np.isfinite([a, b]).all()
                result[metric+'_structure'] = a if valid else np.nan
                result[metric+'_comparator'] = b if valid else np.nan
                result[metric+'_delta'] = a-b if valid else np.nan
            ss, ts = labor(structure)
            sc, tc = labor(comparator)
            valid = ss == sc and ts is not None and tc is not None and tc > 0
            result.update(labor_structure_seconds=ts if valid else np.nan,
                          labor_comparator_seconds=tc if valid else np.nan, labor_ratio=ts/tc if valid else np.nan)
            pairs.append(result)
    return pd.DataFrame(pairs), pd.DataFrame(statuses)


def summarize_q(pairs, version, subset='all_registered'):
    summaries, image_rows = [], []
    for (n, policy), group in pairs.groupby(['n', 'comparator']):
        for metric in Q_METRICS + ['labor']:
            columns = [metric+'_structure', metric+'_comparator', metric+'_delta'] if metric != 'labor' else ['labor_structure_seconds', 'labor_comparator_seconds', 'labor_ratio']
            valid = group.dropna(subset=columns)
            images = image_means(valid, columns)
            if images.empty:
                continue
            effect = columns[-1]
            low, high = cluster_interval(images, effect)
            summaries.append(dict(version=version, subset=subset, n=int(n), m=7, comparator=policy, metric=metric,
                                  events=len(valid), images=len(images), buildings=images.building.nunique(),
                                  structure_mean=images[columns[0]].mean(), comparator_mean=images[columns[1]].mean(),
                                  effect=images[effect].mean(), ci_low=low, ci_high=high,
                                  positive_images=int(images[effect].gt(1 if metric == 'labor' else 1e-9).sum()),
                                  negative_images=int(images[effect].lt(1 if metric == 'labor' else -1e-9).sum()),
                                  structure_p10=images[columns[0]].quantile(.1), comparator_p10=images[columns[1]].quantile(.1)))
            images['version'], images['subset'], images['comparator'], images['metric'] = version, subset, policy, metric
            images = images.rename(columns={columns[0]: 'structure', columns[1]: 'comparator_value', columns[2]: 'effect'})
            image_rows.append(images)
    return pd.DataFrame(summaries), pd.concat(image_rows, ignore_index=True)


def q_original_support(old, new):
    result = new.copy()
    assert old.event_id.tolist() == new.event_id.tolist() and old.comparator.tolist() == new.comparator.tolist()
    for metric in Q_METRICS:
        columns = [metric+'_structure', metric+'_comparator', metric+'_delta']
        mask = old[columns[-1]].isna()
        result.loc[mask, columns] = np.nan
        compare_numeric(old.loc[~mask], new.loc[~mask], ['event_id', 'comparator'], columns,
                        'q_original_support_'+metric, [])
    return result


def different_selections(original_details, pairs, endpoints):
    keys = ['event_id', 'comparator', 'n', 'image', 'building']
    keep = [column for column in original_details if column not in pairs or column in keys]
    result = pairs.merge(original_details[keep], on=keys, validate='one_to_one')
    extra = ['nodes', 'minimum_support', 'S_bottom_deg', 'dir', 'geometry_area_h2', 'centroid_x_h',
             'centroid_z_h', 'height_mean_h', 'height_min_h', 'height_max_h']
    for index, row in result.iterrows():
        a, b = endpoints[row.structure_team], endpoints[row.q_team]
        result.loc[index, 'structure_scored'], result.loc[index, 'q_scored'] = finite(a.get('B8L2')), finite(b.get('B8L2'))
        result.loc[index, 'structure_connection'] = a.get('connection_available')
        result.loc[index, 'q_connection'] = b.get('connection_available')
        for metric in extra:
            x, y = number(a.get(metric)), number(b.get(metric))
            result.loc[index, metric+'_structure'], result.loc[index, metric+'_q'], result.loc[index, metric+'_delta'] = x, y, x-y
        result.loc[index, 'centroid_distance_h'] = np.hypot(result.loc[index, 'centroid_x_h_delta'], result.loc[index, 'centroid_z_h_delta'])
    return result


def counterexamples(images, old_events, new_events):
    scope = images[images.scope.eq('updated_labels_legal_subset') & images.n.eq(14)]
    old = scope[scope.version.eq('automatic')].set_index('image')
    new = scope[scope.version.eq('assisted_expanded')].set_index('image')
    original_cases = set(pd.read_csv(CASE / 'CASE_INDEX.csv').image)
    assert original_cases == set(old[old.diagnostic].index) and len(original_cases) == 30
    index, explanations = [], []
    for image in sorted(original_cases | set(new[new.diagnostic].index)):
        a, b = old.loc[image], new.loc[image]
        old_flags = '|'.join(key for key in ['GA_nonpositive', 'GS_nonpositive', 'CB_nonpositive', 'no_joint_Q', 'partial_events'] if a[key])
        new_flags = '|'.join(key for key in ['GA_nonpositive', 'GS_nonpositive', 'CB_nonpositive', 'no_joint_Q', 'partial_events'] if b[key])
        changed_support = a.scored_events != b.scored_events
        decision = '条件变化' if old_flags != new_flags else '幅度变化' if changed_support else '保持'
        index.append(dict(image=image, original_diagnostic=image in original_cases, assisted_diagnostic=bool(b.diagnostic),
                          old_flags=old_flags, new_flags=new_flags, old_events=a.events, old_scored_events=a.scored_events,
                          new_scored_events=b.scored_events, old_gap_A=a.gap_A, new_gap_A=b.gap_A,
                          old_gap_sym=a.gap_sym, new_gap_sym=b.gap_sym, old_CB=a.CB, new_CB=b.CB,
                          decision=decision, cause='新增可评事件改变图内设计权重；原有分数未改' if changed_support else '原共同支持及数值保持'))
    old_by = old_events.set_index('event_id')
    selected = new_events.updated_class_legal & (new_events.image.isin(original_cases | set(new[new.diagnostic].index))
                                                | new_events.human_order_applied_arms.ne(''))
    for row in new_events[selected].to_dict('records'):
        before = old_by.loc[row['event_id']]
        newly = pd.isna(before.gap_A) and finite(row.get('gap_A'))
        states = {arm: dict(team_key=row[arm+'_team_key'], nodes=row.get(arm+'__nodes'),
                           automatic_score_status=before.get(arm+'__score_status'),
                           assisted_score_status=row.get(arm+'__score_status'),
                           automatic_Q=before.get(arm+'__B8L2'), assisted_Q=row.get(arm+'__B8L2'),
                           automatic_connection=before.get(arm+'__connection_available'),
                           assisted_connection=row.get(arm+'__connection_available')) for arm in 'ABC'}
        if newly:
            reason = '原缺完整来源环的端点经固定节点人工顺序得到可评几何；现在可以评价定位、方向、高度及遗漏/外扩。原缺失Q不与0相减。'
        elif not finite(row.get('gap_A')):
            absent = [f"{arm}臂{states[arm]['nodes']}节点、{states[arm]['assisted_score_status']}"
                      for arm in 'ABC' if not finite(states[arm]['assisted_Q'])]
            reason = '仍无三队共同可评Q：'+'；'.join(absent)+'。不补节点，也不以人工确认代替完整性。'
        else:
            reason = '原三队共同可评支持保持；人工接入未改此事件的分数。'
        if finite(row.get('gap_A')):
            reason += f" GA={row['gap_A']:+.6f}，GS={row['gap_sym']:+.6f}，C−B={row['CB']:+.6f}。"
            if row.get('C_between_A_B') == 1:
                reason += ' C位于A/B分数之间，因此对称跨类幅度不超过同类幅度。'
            elif row['gap_sym'] <= 0 and row['CB'] > 0:
                reason += ' C虽比B升质，但跨类对称幅度仍未超过同类换人幅度。'
            worse = [label for field, label in [('boundary_loss_CB', '边界'), ('direction_loss_CB', '方向'), ('height_loss_CB', '高度')] if finite(row.get(field)) and row[field] > 0]
            better = [label for field, label in [('boundary_loss_CB', '边界'), ('direction_loss_CB', '方向'), ('height_loss_CB', '高度')] if finite(row.get(field)) and row[field] < 0]
            reason += ' C−B损失下降：'+('、'.join(better) or '无')+'；上升：'+('、'.join(worse) or '无')+'。'
        explanations.append(dict(event_id=row['event_id'], image=row['image'], n=row['n'],
                                 human_order_applied_arms=row['human_order_applied_arms'],
                                 newly_joint_scored=newly, automatic_joint_Q=finite(before.gap_A),
                                 assisted_joint_Q=finite(row.get('gap_A')),
                                 automatic_gap_A=before.gap_A, assisted_gap_A=row.get('gap_A'),
                                 automatic_gap_sym=before.gap_sym, assisted_gap_sym=row.get('gap_sym'),
                                 automatic_CB=before.CB, assisted_CB=row.get('CB'),
                                 arm_states_json=json.dumps(clean(states), ensure_ascii=False, allow_nan=False),
                                 explanation=reason))
    csv(index, 'COUNTEREXAMPLE_TRANSITIONS.csv')
    csv(explanations, 'COUNTEREXAMPLE_EVENT_EXPLANATIONS.csv')
    return pd.DataFrame(index)


def matched_background(original, revised, checks):
    links = pd.read_csv(PRO / 'stage01_half_team/EXACT_XYZ_14_7_TO_20_7.csv')
    metrics = ['gap_A', 'gap_sym', 'CB', 'B8L2_within', 'B8L2_cross_direct', 'B8L2_cross_symmetric']
    old_by, new_by = original.set_index('event_id'), revised.set_index('event_id')
    legal = set(original.loc[original.updated_class_legal, 'event_id'])
    summaries, saved_links = [], []
    for label_scope in ['frozen_design', 'updated_labels_legal_subset']:
        selection = links if label_scope == 'frozen_design' else links[links.event_id_14.isin(legal) & links.event_id_20.isin(legal)]
        for version, source in [('automatic', old_by), ('assisted_expanded', new_by)]:
            changed = selection.copy()
            for n in [14, 20]:
                for metric in metrics:
                    changed[metric+'_'+str(n)] = changed['event_id_'+str(n)].map(source[metric])
            for metric in metrics:
                changed[metric+'_20_minus_14'] = changed[metric+'_20']-changed[metric+'_14']
            changed['label_scope'], changed['version'] = label_scope, version
            saved_links.append(changed)
            keys = ['building_14', 'image_14', 'pool_id', 'X', 'Y', 'Z']
            for scope, part in [('all_exact_XYZ', changed), ('D14_subset_D20', changed[changed.D14_subset_D20]),
                                ('D_also_replaced', changed[~changed.D14_subset_D20])]:
                for metric in metrics:
                    columns = [metric+'_14', metric+'_20']
                    valid = part.dropna(subset=columns)
                    im = valid.groupby(keys)[columns].mean().groupby(level=keys[:3]).mean().groupby(level=keys[:2]).mean().reset_index()
                    delta = im[columns[1]]-im[columns[0]]
                    summaries.append(dict(label_scope=label_scope, version=version, scope=scope, metric=metric,
                                          registered_links=len(part), valid_links=len(valid), images=len(im),
                                          buildings=im.building_14.nunique(), mean_14=im[columns[0]].mean(),
                                          mean_20=im[columns[1]].mean(), mean_delta=delta.mean(),
                                          positive=int(delta.gt(0).sum()), negative=int(delta.lt(0).sum())))
    csv(pd.concat(saved_links, ignore_index=True), 'HALF_MATCHED_BACKGROUND_LINKS.csv.gz')
    summary = pd.DataFrame(summaries)
    csv(summary, 'HALF_MATCHED_BACKGROUND_SUMMARY.csv')
    prior = pd.read_csv(UP / 'MATCHED_BACKGROUND_SUMMARY.csv')
    baseline = summary[summary.label_scope.eq('updated_labels_legal_subset') & summary.version.eq('automatic')]
    compare_numeric(prior, baseline, ['scope', 'metric'],
                    ['registered_links', 'valid_links', 'images', 'buildings', 'mean_14', 'mean_20', 'mean_delta', 'positive', 'negative'],
                    'original_matched_background_parity', checks)
    return summary


def conditional_labor(original, revised, old_pairs, new_pairs):
    summaries = []
    half_metrics = ['record_time_'+pair+'_pct_source_matched' for pair in ['BA', 'CA', 'CB']]
    for scope in ['frozen_design', 'updated_labels_legal_subset']:
        old = original if scope == 'frozen_design' else original[original.updated_class_legal]
        new = revised.loc[old.index]
        for version, frame in [('automatic', old), ('assisted_original_Q_support', new[old.gap_A.notna()]),
                               ('assisted_expanded_Q_support', new)]:
            part = frame[frame.gap_A.notna()]
            for n, group in part.groupby('n'):
                for metric in half_metrics:
                    valid = group.dropna(subset=[metric])
                    im = image_means(valid, [metric])
                    summaries.append(dict(module='half', scope=scope, version=version, n=n, comparator=metric[12:14],
                                          metric=metric, events=len(valid), images=len(im), buildings=im.building.nunique(),
                                          mean=im[metric].mean(), labour_changed=False,
                                          support_definition='original annotation time restricted to three-endpoint Q availability'))
    for version, frame in [('automatic', old_pairs), ('assisted_expanded_Q_support', new_pairs)]:
        for (n, comparator), group in frame.groupby(['n', 'comparator']):
            valid = group.dropna(subset=['B8L2_delta', 'labor_ratio'])
            im = image_means(valid, ['labor_ratio'])
            summaries.append(dict(module='q_only', scope='all_registered', version=version, n=n, comparator=comparator,
                                  metric='labor_ratio', events=len(valid), images=len(im), buildings=im.building.nunique(),
                                  mean=im.labor_ratio.mean(), labour_changed=False,
                                  support_definition='original annotation time restricted to paired Q availability'))
    csv(summaries, 'QUALITY_CONDITIONED_ANNOTATION_LABOR.csv')


def summarize_different(details, version):
    rows = []
    for (n, policy), group in details.groupby(['n', 'comparator']):
        row = dict(version=version, n=int(n), comparator=policy, events=len(group), images=group.image.nunique(),
                   buildings=group.building.nunique(), same_class_composition=int(group.class_composition_same.sum()),
                   different_class_composition=int((~group.class_composition_same).sum()),
                   scored_events=int(group.B8L2_delta.notna().sum()), scored_images=group.loc[group.B8L2_delta.notna(), 'image'].nunique(),
                   same_turn_events=int(group.fusion_turn_n_delta.eq(0).sum()), Q_positive=int(group.B8L2_delta.gt(1e-8).sum()),
                   Q_negative=int(group.B8L2_delta.lt(-1e-8).sum()), Q_tie=int(group.B8L2_delta.abs().le(1e-8).sum()),
                   structure_only=int((group.structure_scored & ~group.q_scored).sum()),
                   q_only=int((~group.structure_scored & group.q_scored).sum()),
                   both_unscored=int((~group.structure_scored & ~group.q_scored).sum()))
        for metric in ['B8L2_delta', 'IoU3D100_delta', 'fusion_turn_n_delta', 'boundary_loss_delta', 'direction_loss_delta', 'centroid_distance_h']:
            im = image_means(group.dropna(subset=[metric]), [metric])
            row[metric+'_image_mean'], row[metric+'_images'] = im[metric].mean(), len(im)
        rows.append(row)
    return pd.DataFrame(rows)


def write_report(half_summary, q_summary, q_status, counter, receipt):
    conclusions = []
    lines = ['# 人工融合顺序：严格ABC、Q-only与反例影响', '',
             '本报告为定向人工辅助敏感性版本。原自动实验及其分母均保留；辅助版仅对确认的精确团队和参考身份补入连接。'
             '缺失Q保持缺失，新增可评分数没有“从0提高”的含义。', '',
             '## 严格ABC及50%换人', '',
             '计权沿原实现：事件重复先在背景内平均，再依次背景、替换块、池、图片等权。建筑表是分层描述；'
             '不把建筑等权均值替换原图片等权主估计。', '',
             '|条件|指标|原自动|人工辅助扩展支持|原有效事件→新有效事件|原有效图→新有效图|',
             '|---|---|---:|---:|---:|---:|']
    for n in [14, 20]:
        for metric in ['gap_A', 'gap_sym', 'CB', 'B8L2_within', 'B8L2_cross_direct', 'B8L2_cross_symmetric']:
            part = half_summary[(half_summary.scope == 'updated_labels_legal_subset') & half_summary.n.eq(n) & half_summary.metric.eq(metric)].set_index('version')
            a, b = part.loc['automatic'], part.loc['assisted_expanded']
            lines.append(f'|{n}/7|{metric}|{a["mean"]:+.6f}|{b["mean"]:+.6f}|{int(a.valid_events)}→{int(b.valid_events)}|{int(a.images)}→{int(b.images)}|')
            status = '保持' if abs(a['mean']-b['mean']) < 1e-9 else '幅度变化' if a['mean']*b['mean'] > 0 else '需改写'
            conclusions.append(dict(topic=f'{n}/7 {metric}', status=status, automatic=a['mean'], assisted=b['mean'],
                                    source='HALF_SUMMARY.csv', explanation='原已评分支持未改；总均值差来自新增可评事件及原层级内支持变化'))
    lines += ['', '指标：GA=|C−A|−|B−A|；GS=(|C−A|+|C−B|)/2−|B−A|；C−B按两队自身共同可评支持。'
              'GA/GS需要三队共同可评；不能用C−B较大的支持分母替代。完整分项、原冻结对照、逐图/逐楼与难度见配套表。'
              '来源：[HALF_SUMMARY.csv](HALF_SUMMARY.csv)、[HALF_SUPPORT.csv](HALF_SUPPORT.csv)。', '',
              '当前14/7仍有S9hNv5qa7GM-12一条事件的A、B均仅3节点；20/7仍有x8F5xyUWy9e-08一条事件的A仅3节点。'
              '后者人工B端点虽然变得可评，三队GA/GS仍缺失，而C−B可以评价。因此20/7三队支持是60/61，C−B支持是61/61。', '',
              '### 相同X/Y/Z下的14→20对照', '',
              '下表为20人条件减14人条件的图等权均值。总人数、实际背景D及MV50门槛同时改变；'
              '即便D14包含于D20，也不能解释为只改变人数的因果效应。', '',
              '|背景关系|指标|原20−14|新20−14|原有效配对→新有效配对|结论状态|',
              '|---|---|---:|---:|---:|---|']
    matched = pd.read_csv(OUT / 'HALF_MATCHED_BACKGROUND_SUMMARY.csv')
    matched = matched[matched.label_scope.eq('updated_labels_legal_subset')]
    for scope in ['all_exact_XYZ', 'D14_subset_D20', 'D_also_replaced']:
        for metric in ['gap_A', 'gap_sym', 'CB']:
            part = matched[matched.scope.eq(scope) & matched.metric.eq(metric)].set_index('version')
            a, b = part.loc['automatic'], part.loc['assisted_expanded']
            status = '保持' if abs(a.mean_delta-b.mean_delta) < 1e-9 else '幅度变化' if a.mean_delta*b.mean_delta > 0 else '需改写'
            lines.append(f'|{scope}|{metric}|{a.mean_delta:+.6f}|{b.mean_delta:+.6f}|{int(a.valid_links)}→{int(b.valid_links)}|{status}|')
            conclusions.append(dict(topic=f'14→20相同XYZ/{scope}/{metric}', status=status,
                                    automatic=a.mean_delta, assisted=b.mean_delta,
                                    source='HALF_MATCHED_BACKGROUND_SUMMARY.csv',
                                    explanation='新增可评配对改变图片支持；背景、人数和投票门槛联合变化，不识别纯人数效应'))
    lines += ['', '全集GA由负变正；D也替换子集的GA、GS均翻向，需改写“一律随人数增加而减弱”类结论。'
              'D14包含于D20子集的GA、GS仍为负。来源：[HALF_MATCHED_BACKGROUND_SUMMARY.csv](HALF_MATCHED_BACKGROUND_SUMMARY.csv)。', '',
              '### 难度分层', '',
              '难度标签来自冻结的difficulty_records.json；本分析不因辅助融合质量重定难度。'
              '分层支持扩展会改变图均值，不能把这种变化写成难度分类本身变化。', '',
              '|规模|难度|GA原→新|GS原→新|C−B原→新|', '|---|---|---:|---:|---:|']
    difficulty = pd.read_csv(OUT / 'HALF_DIFFICULTY.csv')
    difficulty = difficulty[difficulty.scope.eq('updated_labels_legal_subset')]
    for n in [14, 20]:
        for grade in ['简单', '中等', '困难']:
            values = []
            for metric in ['gap_A', 'gap_sym', 'CB']:
                part = difficulty[difficulty.n.eq(n) & difficulty.difficulty.eq(grade) & difficulty.metric.eq(metric)].set_index('version')
                a, b = part.loc['automatic'], part.loc['assisted_expanded']
                values.append(f'{a["mean"]:+.6f}→{b["mean"]:+.6f}')
                status = '保持' if abs(a['mean']-b['mean']) < 1e-9 else '幅度变化' if a['mean']*b['mean'] > 0 else '需改写'
                conclusions.append(dict(topic=f'{n}/7 {grade}/{metric}', status=status, automatic=a['mean'], assisted=b['mean'],
                                        source='HALF_DIFFICULTY.csv', explanation='固定难度分层，按各指标真实可评支持重算'))
            lines.append(f'|{n}/7|{grade}|'+ '|'.join(values)+'|')
    lines += ['', '20/7中等层C−B由正变负（9→10图）；20/7困难层仍仅2图，三个指标均保持。'
              '来源：[HALF_DIFFICULTY.csv](HALF_DIFFICULTY.csv)。', '',
              '## DSTRUCT与Q-only', '',
              '五臂A/B/STRUCTURE/Q_RAW/Q_PEER均应用同一精确端点补丁。同一团队在不同政策臂和事件中复用同一个辅助结果。'
              '下表为结构政策减Q-only政策，沿原图均值及建筑簇bootstrap（2000次、原种子）计算。', '',
              '|规模|对照|原均值差（95%区间）|新均值差（95%区间）|共同可评事件|共同可评图|',
              '|---|---|---:|---:|---:|---:|']
    for n in [14, 20]:
        for policy in ['Q_RAW', 'Q_PEER']:
            part = q_summary[q_summary.subset.eq('all_registered') & q_summary.n.eq(n) & q_summary.comparator.eq(policy) & q_summary.metric.eq('B8L2')].set_index('version')
            a, b = part.loc['automatic'], part.loc['assisted_expanded']
            lines.append(f'|{n}/7|{policy}|{a.effect:+.6f} [{a.ci_low:+.6f}, {a.ci_high:+.6f}]|{b.effect:+.6f} [{b.ci_low:+.6f}, {b.ci_high:+.6f}]|{int(a.events)}→{int(b.events)}|{int(a.images)}→{int(b.images)}|')
            old_state = 1 if a.ci_low > 0 else -1 if a.ci_high < 0 else 0
            new_state = 1 if b.ci_low > 0 else -1 if b.ci_high < 0 else 0
            status = '需改写' if old_state != new_state else '保持' if abs(a.effect-b.effect) < 1e-9 else '幅度变化'
            explanation = ('辅助扩展支持仍未给出结构选员的额外平均Q优势；不据此宣称两政策等效。' if new_state == 0 else
                           '辅助扩展支持的95%区间全负，出现Q-only更高的证据；上界仅略低于0，限于定向人工辅助支持，不追改自动结果。' if new_state == -1 else
                           '辅助扩展支持的区间下界大于0，需独立注明这是人工辅助条件下的优势，不能追改自动结论。')
            conclusions.append(dict(topic=f'DSTRUCT vs {policy}, {n}/7', status=status, automatic=a.effect,
                                    assisted=b.effect, source='QONLY_SUMMARY.csv', explanation=explanation))
    original = q_summary[q_summary.version.eq('automatic') & q_summary.subset.eq('all_registered')]
    original_support = q_summary[q_summary.version.eq('assisted_original_support') & q_summary.subset.eq('all_registered')]
    compare_numeric(original, original_support, ['n', 'comparator', 'metric'], ['effect', 'events', 'images'], 'report_common_support_check', [])
    lines += ['', '**20/7的判定需改写。** 原区间跨0，辅助扩展支持的上界为−0.000866，刚刚低于0；'
              '在原bootstrap定义下出现Q-only平均Q更高的证据。两政策的20/7选员相同，故数值相同。'
              '这不构成原自动DSTRUCT已经被重新实验推翻的结论，辅助处理与支持条件必须一起陈述。', '',
              '原共同支持上的政策差完全保持；扩展均值不能解释为原已评分团队本身提高。'
              '来源：[QONLY_SUMMARY.csv](QONLY_SUMMARY.csv)、[QONLY_SUPPORT.csv](QONLY_SUPPORT.csv)。', '',
              '### 只比较实际不同选员事件', '',
              '|规模|Q-only对照|原差值（95%区间）|新差值（95%区间）|可评事件原→新|',
              '|---|---|---:|---:|---:|']
    for n in [14, 20]:
        for policy in ['Q_RAW', 'Q_PEER']:
            part = q_summary[q_summary.subset.eq('different_selection') & q_summary.n.eq(n)
                             & q_summary.comparator.eq(policy) & q_summary.metric.eq('B8L2')].set_index('version')
            a, b = part.loc['automatic'], part.loc['assisted_expanded']
            lines.append(f'|{n}/7|{policy}|{a.effect:+.6f} [{a.ci_low:+.6f}, {a.ci_high:+.6f}]|'
                         f'{b.effect:+.6f} [{b.ci_low:+.6f}, {b.ci_high:+.6f}]|{int(a.events)}→{int(b.events)}|')
    lines += ['', '20/7新增的实际不同选员事件位于S9hNv5qa7GM-09：结构政策Q=39.914405，Q-only为79.988704，差−40.074298。'
              '其边界、方向损失差分别为+0.586679、+0.815306，高度损失差−0.001094；'
              '这是补连接后新可评价的低质量结构结果，不能写成“从0提高39.9”。'
              '来源：[QONLY_DIFFERENT_SELECTION_EVENTS.csv.gz](QONLY_DIFFERENT_SELECTION_EVENTS.csv.gz)，event_id=154d5aebcb8aaffc968f1e09。', '',
              '## 30图反例解释', '',
              f'原30图诊断集合逐一保留。辅助版诊断集合有{int(counter.assisted_diagnostic.sum())}图；'
              f'原30图中{int((counter.original_diagnostic & ~counter.assisted_diagnostic).sum())}图不再满足原诊断条件，'
              f'{int((~counter.original_diagnostic & counter.assisted_diagnostic).sum())}图新进入诊断集合。'
              '具体标志变化、原/新GA、GS、C−B及逐事件机制见COUNTEREXAMPLE_TRANSITIONS和COUNTEREXAMPLE_EVENT_EXPLANATIONS。', '',
              '|图片|原诊断标志|辅助后标志|状态|', '|---|---|---|---|']
    for row in counter[counter.decision.ne('保持')].itertuples():
        lines.append(f'|{row.image}|{row.old_flags.replace("|", "、") or "无"}|{row.new_flags.replace("|", "、") or "无"}|{row.decision}|')
        conclusions.append(dict(topic='原30图反例/'+row.image, status=row.decision,
                                source='COUNTEREXAMPLE_TRANSITIONS.csv;COUNTEREXAMPLE_EVENT_EXPLANATIONS.csv',
                                explanation='诊断标志由'+(row.old_flags or '无')+'变为'+(row.new_flags or '无')))
    lines += ['', '其余24图的原诊断条件和数值保持。S9hNv5qa7GM-04、VFuaQ6m2Qom-01退出当前诊断集合；'
              'VFuaQ6m2Qom-04从无共同Q变为C−B为负；pa4otMbVnkk-14由部分事件缺Q变为GA、GS非正；'
              'zsNo4HB9uLZ-16由部分事件缺Q变为GA非正。来源：[COUNTEREXAMPLE_TRANSITIONS.csv](COUNTEREXAMPLE_TRANSITIONS.csv)。', '',
              '由“无完整来源环”变为可评分，不表示定位正确。重新解释只依据固定参考下的边界、方向、高度、遗漏/外扩及几何差；'
              '不会把镜面、柜体等未做新判断的物体语义当作数值原因。', '',
              '## 劳动、支持与适用范围', '',
              '原标注时间、来源种类及其记录数向量未变。质量共同可评支持扩展后，按该支持计算的劳动比较可变化；'
              'QUALITY_CONDITIONED_ANNOTATION_LABOR逐项列明。人工排序劳动未计时，无法从当前数据计算含人工介入的总成本效益。', '',
              '57组为定向案例；本报告不估计所有自动无环结果的可修复率。分类、历史Q选员、参考、团队、投票与节点位置均固定，'
              '未开展分类重选。原3节点不完整结果仍不靠排序补点。', '',
              '## 复现与检查', '',
              '`python -m tools.thesis_main.analysis.evaluate_manual_order_half_qonly_20261104`', '',
              '如使用额外原几何缓存，添加CHECKS.json记录的--geometry-cache参数。原半队summary、Q-only逐事件和summary、'
              '同XYZ背景对照及差异选员基线均要求数值对齐；关键身份、缺失与计权检查详见CHECKS.json。']
    conclusions += [dict(topic='原共同可评分数与指标', status='保持', source='HALF_SUPPORT.csv;QONLY_SUPPORT.csv',
                         explanation='所有原已评分支持数值不变；形成率变化独立于质量变化报告'),
                    dict(topic='人工辅助全成本效益', status='尚不能判断', source='QUALITY_CONDITIONED_ANNOTATION_LABOR.csv',
                         explanation='原标注劳动保持；人工排序无计时，不虚构新增劳动成本')]
    csv(conclusions, 'CONCLUSIONS.csv')
    (OUT / 'REPORT_ZH.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    (OUT / 'README.md').write_text('''# 第二批：严格ABC、Q-only及30图反例\n\n主报告：[REPORT_ZH.md](REPORT_ZH.md)。逐条结论：[CONCLUSIONS.csv](CONCLUSIONS.csv)。\n\n本目录保留原自动版、人工辅助扩展版及原共同支持的对照。固定57组人工顺序中的精确团队/参考，未重新选员、分类或改变任何节点坐标。\n\n## 文件入口\n\n- `HALF_AUTOMATIC_EVENTS.csv.gz` / `HALF_ASSISTED_EVENTS.csv.gz`：279条原冻结ABC事件及其对应辅助版本；`updated_class_legal`标出当前208条合法事件。\n- `HALF_SUMMARY.csv` / `HALF_SUPPORT.csv`：原冻结与当前合法两种设计范围，质量及原机制分项、旧新支持、原共同支持数值差。形成/失败状态单列。\n- `HALF_IMAGES.csv.gz` / `HALF_BUILDINGS.csv` / `HALF_DIFFICULTY.csv`：按原背景→替换块→池→图计权后的描述表；建筑不取代图片主估计。\n- `HALF_MATCHED_BACKGROUND_LINKS.csv.gz` / `HALF_MATCHED_BACKGROUND_SUMMARY.csv`：精确XYZ的14/7与20/7配对；保留D包含关系，联合变化不可当纯人数效应。\n- `QONLY_*PAIRED_EVENTS.csv.gz` / `QONLY_SUMMARY.csv` / `QONLY_IMAGE_EFFECTS.csv.gz`：五政策臂同步修补、原支持与扩展支持；沿原种子20261031的2000次建筑簇bootstrap。\n- `QONLY_OUTPUT_STATUS.csv` / `QONLY_STATUS_SUMMARY.csv` / `QONLY_SUPPORT.csv`：逐臂形成/可评状态及指标特定共同支持。\n- `QONLY_DIFFERENT_SELECTION_*`：保留原选员差集、固定类别构成，只更新受影响质量/结构/几何。\n- `COUNTEREXAMPLE_TRANSITIONS.csv` / `COUNTEREXAMPLE_EVENT_EXPLANATIONS.csv`：原30图逐条状态和相关14/7、20/7事件解释，含旧新逐臂Q、节点数和状态。\n- `QUALITY_CONDITIONED_ANNOTATION_LABOR.csv`：原劳动固定，质量支持扩展所导致的条件统计变化；人工排序劳动未计时。\n- `AUXILIARY_LEGACY_REFERENCE_DIAGNOSTICS.csv` / `UNCHANGED_AUTOMATIC_LEGACY_REFERENCE_DIAGNOSTICS.csv`：按原refdiagnostic补足实际消费的4项诊断；不改中央首批端点文件。\n- `UNCHANGED_AUTOMATIC_GEOMETRY_RECOVERY*`：仅2个原20人对手丢失几何的定向原自动重放，原已有标量parity最大1.42e-14；不是新增团队或人工重排。\n- `CHECKS.json` / `INPUT_MANIFEST.json`：版本、来源散列、原基线parity与支持检查。\n\n## 复现\n\n在仓库根运行 `python -m tools.thesis_main.analysis.evaluate_manual_order_half_qonly_20261104`。已有2队几何恢复档案会直接复用；仅当该档案不存在才精确恢复这2队。原自动来源文件不覆盖。运行 `python -m pytest tests/test_manual_order_half_qonly_20261104.py -q` 检查缺失分数、计权和身份不变量。\n\n57组是定向案例，不据此估计所有自动无环结果的修复率。新出现的Q不能与原缺失值0相减；原共同支持上的质量和几何数值完全保持。\n''', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--aux-endpoints', type=Path, default=BASE / 'endpoints/ENDPOINTS.jsonl.gz')
    parser.add_argument('--geometry-cache', type=Path, action='append', default=[])
    args = parser.parse_args()
    checks = []
    args.geometry_cache = counterpart_geometry_sources(args.geometry_cache)
    auxiliary, old_endpoints, new_endpoints, q_old_endpoints = endpoint_index(args.aux_endpoints, args.geometry_cache)
    original = pd.read_csv(PRO / 'stage01_half_team/EVENTS_WITH_ENDPOINTS.csv.gz', low_memory=False)
    legality = pd.read_csv(UP / 'HALF_EVENT_LEGALITY.csv.gz', low_memory=False).set_index('event_id')
    assert original.event_id.is_unique and set(original.event_id) == set(legality.index)
    for column in ['updated_class_legal', 'updated_direction']:
        original[column] = original.event_id.map(legality[column])
    grades = {row['image']: row['current_class'] for row in read_json(REL / 'difficulty_records.json')['records']}
    original['difficulty'] = original.image.map(grades)
    assert original.difficulty.isin(['简单', '中等', '困难']).all()
    original['result_variant'] = 'original_automatic'
    original['human_order_applied_arms'] = ''
    original = add_original_mechanism_derivatives(original)
    revised = add_original_mechanism_derivatives(patch_half_events(original, new_endpoints, auxiliary))
    revised['result_variant'] = 'automatic_with_targeted_human_orders'
    revised['human_order_applied_arms'] = revised.apply(
        lambda row: '|'.join(a for a in 'ABC' if row[a+'_team_key'] in auxiliary), axis=1)
    csv(original, 'HALF_AUTOMATIC_EVENTS.csv.gz')
    csv(revised, 'HALF_ASSISTED_EVENTS.csv.gz')
    images, half_summary = summarize_half(original, revised, checks)
    counter = counterexamples(images, original, revised)
    matched_background(original, revised, checks)
    links = pd.read_csv(QONLY / 'DESIGN_LINKS.csv')
    old_pairs, old_status = q_pair_events(links, q_old_endpoints)
    new_pairs, new_status = q_pair_events(links, new_endpoints)
    saved_pairs = pd.read_csv(QONLY / 'PAIRED_EVENTS.csv')
    numeric = [c for c in old_pairs if c.endswith(('_structure', '_comparator', '_delta', '_seconds', '_ratio'))]
    compare_numeric(saved_pairs, old_pairs, ['event_id', 'comparator'], numeric, 'original_q_pairs_parity', checks)
    original_support = q_original_support(old_pairs, new_pairs)
    summaries, q_images = [], []
    for version, pair in [('automatic', old_pairs), ('assisted_original_support', original_support), ('assisted_expanded', new_pairs)]:
        summary, im = summarize_q(pair, version)
        summaries.append(summary)
        q_images.append(im)
        pair = pair.copy()
        pair['version'] = version
        csv(pair, 'QONLY_'+version.upper()+'_PAIRED_EVENTS.csv.gz')
    saved_summary = pd.read_csv(QONLY / 'SUMMARY.csv')
    compare_numeric(saved_summary, summaries[0], ['n', 'comparator', 'metric'],
                    ['events', 'images', 'buildings', 'structure_mean', 'comparator_mean', 'effect',
                     'ci_low', 'ci_high', 'positive_images', 'negative_images', 'structure_p10', 'comparator_p10'],
                    'original_q_summary_parity', checks)
    original_details = pd.read_csv(QONLY / 'diagnostic_20261031/DIFFERENT_SELECTION_EVENTS.csv')
    different_frames, different_summaries = [], []
    for version, pairs, endpoints in [('automatic', old_pairs, old_endpoints), ('assisted_expanded', new_pairs, new_endpoints)]:
        detail = different_selections(original_details, pairs, endpoints)
        summary, im = summarize_q(detail, version, 'different_selection')
        summaries.append(summary)
        q_images.append(im)
        detail['version'] = version
        different_frames.append(detail)
        different_summaries.append(summarize_different(detail, version))
    saved_different = pd.read_csv(QONLY / 'diagnostic_20261031/DIFFERENT_SELECTION_SUMMARY.csv')
    numeric_different = [c for c in saved_different.select_dtypes(include='number') if c != 'n']
    compare_numeric(saved_different, different_summaries[0], ['n', 'comparator'], numeric_different,
                    'original_different_selection_parity', checks)
    csv(pd.concat(different_summaries, ignore_index=True), 'QONLY_DIFFERENT_SELECTION_SUMMARY.csv')
    csv(pd.concat(different_frames, ignore_index=True), 'QONLY_DIFFERENT_SELECTION_EVENTS.csv.gz')
    csv(pd.concat(summaries, ignore_index=True), 'QONLY_SUMMARY.csv')
    csv(pd.concat(q_images, ignore_index=True), 'QONLY_IMAGE_EFFECTS.csv.gz')
    old_status['version'], new_status['version'] = 'automatic', 'assisted_expanded'
    status = pd.concat([old_status, new_status], ignore_index=True)
    csv(status, 'QONLY_OUTPUT_STATUS.csv')
    csv(status.groupby(['version', 'n', 'policy']).agg(events=('event_id', 'size'), scored=('scored', 'sum'),
        complete=('complete', 'sum'), below_four=('below_four', 'sum'), connection_available=('connection_available', 'sum')).reset_index(), 'QONLY_STATUS_SUMMARY.csv')
    support = []
    for (n, comparator), group in old_pairs.groupby(['n', 'comparator']):
        new = new_pairs.loc[group.index]
        for metric in Q_METRICS:
            field = metric+'_delta'
            old_ok, new_ok = group[field].notna(), new[field].notna()
            assert not (old_ok & ~new_ok).any()
            support.append(dict(n=n, comparator=comparator, metric=metric, old_events=int(old_ok.sum()),
                                new_events=int(new_ok.sum()), added_events=int((~old_ok & new_ok).sum()),
                                old_images=group.loc[old_ok, 'image'].nunique(), new_images=new.loc[new_ok, 'image'].nunique(),
                                original_support_max_difference=float((group.loc[old_ok, field]-new.loc[old_ok, field]).abs().max())))
    csv(support, 'QONLY_SUPPORT.csv')
    conditional_labor(original, revised, old_pairs, new_pairs)
    input_paths = [args.aux_endpoints,
                   ROOT / 'research/fusion/missing_ring_review_20261104/user_order_return/VALIDATED_ENDPOINT_ORDERS.csv.gz',
                   PRO / 'stage01_half_team/EVENTS_WITH_ENDPOINTS.csv.gz',
                   PRO / 'stage01_half_team/SAVED_ENDPOINT_SCALARS.csv.gz',
                   PRO / 'stage01_half_team/EXACT_XYZ_14_7_TO_20_7.csv',
                   UP / 'HALF_EVENT_LEGALITY.csv.gz', UP / 'HALF_SUMMARY.csv', UP / 'MATCHED_BACKGROUND_SUMMARY.csv',
                   REL / 'difficulty_records.json', REL / 'pools/INPUT_SNAPSHOT.json',
                   QONLY / 'ENDPOINTS.jsonl.gz', QONLY / 'DESIGN_LINKS.csv', QONLY / 'PAIRED_EVENTS.csv',
                   QONLY / 'SUMMARY.csv', QONLY / 'diagnostic_20261031/DIFFERENT_SELECTION_EVENTS.csv',
                   QONLY / 'diagnostic_20261031/DIFFERENT_SELECTION_SUMMARY.csv', CASE / 'CASE_INDEX.csv',
                   *args.geometry_cache]
    manifest = []
    for path in dict.fromkeys(input_paths):
        with path.open('rb') as handle:
            digest = hashlib.file_digest(handle, 'sha256').hexdigest()
        manifest.append(dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size, sha256=digest))
    json_out(dict(source_commit='ac395e703d1fef573d1ef3e105df0286d62a0468', files=manifest), 'INPUT_MANIFEST.json')
    half_support = pd.read_csv(OUT / 'HALF_SUPPORT.csv')
    quality_support = half_support[half_support.result_kind.eq('metric')]
    checks.append(dict(check='all_half_original_metric_support_values_preserved', rows=len(quality_support),
                       maximum_error=quality_support.original_support_max_difference.max()))
    checks.append(dict(check='all_q_original_metric_support_values_preserved', rows=len(support),
                       maximum_error=max(row['original_support_max_difference'] for row in support)))
    # Verify saved gzip completion and event identity after the numerical work.
    saved_old = pd.read_csv(OUT / 'HALF_AUTOMATIC_EVENTS.csv.gz', low_memory=False)
    saved_new = pd.read_csv(OUT / 'HALF_ASSISTED_EVENTS.csv.gz', low_memory=False)
    assert saved_old.event_id.tolist() == saved_new.event_id.tolist() == original.event_id.tolist()
    fixed_columns = ['event_id', 'n', 'm', 'pool_id', 'building', 'image', 'block_id', 'background_id', 'D', 'X', 'Y', 'Z']
    fixed_columns += [arm+'_team_key' for arm in 'ABC']
    for column in fixed_columns:
        assert saved_old[column].equals(saved_new[column]), ('fixed_design', column)
    labour_columns = [column for column in original if 'time' in column and not column.startswith('target')]
    for column in labour_columns:
        assert saved_old[column].equals(saved_new[column]), ('fixed_labour', column)
    checks.append(dict(check='saved_event_identity_and_labour_preserved', rows=len(saved_old),
                       identity_columns=len(fixed_columns), labour_columns=len(labour_columns), passed=True))
    # DataFrame.isin(dict) aligns dictionary keys to column names.  The
    # auxiliary dictionary is keyed by team identity, so explicitly use its
    # key set for membership; this is receipt accounting only.
    touched = original[[a+'_team_key' for a in 'ABC']].isin(set(auxiliary)).any(axis=1)
    receipt = dict(source_commit='ac395e703d1fef573d1ef3e105df0286d62a0468',
                   auxiliary_input=str(args.aux_endpoints.relative_to(ROOT)),
                   geometry_caches=[str(p.relative_to(ROOT)) for p in args.geometry_cache],
                   auxiliary_endpoint_identities=len(auxiliary), frozen_half_events=len(original),
                   unchanged_automatic_geometry_recovery_calls=2,
                   unchanged_automatic_geometry_recovery_checks='UNCHANGED_AUTOMATIC_GEOMETRY_RECOVERY_CHECKS.json',
                   human_order_geometry_fusion_calls=0,
                   current_half_events=int(original.updated_class_legal.sum()),
                   affected_frozen_half_events=int(original.loc[touched, 'event_id'].nunique()),
                   affected_current_half_events=int(original.loc[touched & original.updated_class_legal, 'event_id'].nunique()),
                   q_only_design_events=links.event_id.nunique(), q_only_affected_references=int(links.team_key.isin(auxiliary).sum()),
                   original_counterexample_images=30, assisted_counterexample_images=int(counter.assisted_diagnostic.sum()),
                   original_support_unchanged=True, original_annotation_labour_unchanged=True,
                   original_support_invariance_scope='quality and geometry values; formation/failed indicators reported separately',
                   metric_specific_mechanism_source=str((PRO / 'scripts/analyze_half_mechanisms.py').relative_to(ROOT)),
                   input_manifest='INPUT_MANIFEST.json',
                   human_sorting_labour_seconds=None, no_missing_Q_imputed=True,
                   no_refit_or_reselection=True, original_files_overwritten=False,
                   weighting='event replicate -> background -> block -> pool -> image; buildings are bootstrap clusters',
                   checks=checks)
    json_out(receipt, 'CHECKS.json')
    write_report(half_summary, pd.concat(summaries, ignore_index=True), status, counter, receipt)
    print(json.dumps(clean(receipt), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
