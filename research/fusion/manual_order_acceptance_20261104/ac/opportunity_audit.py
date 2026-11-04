"""Targeted registered-cohort opportunity audit for the 60 existing Q reversals.

Default execution is offline and reads the exact small input subsets delivered
with this audit.  --prepare-inputs downloads frozen metric shards only for the
named cohorts' residual failures and extracts those subsets.  This never scores,
fuses, creates an order, selects a team, or alters the accepted numerical tables.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import gzip
import hashlib
import importlib.util
import json
import sys
import urllib.request
from functools import lru_cache

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
OLD = ROOT / 'research/fusion/manual_order_impact_20261104/ac'
CACHE = OUT / 'source_cache'
DATA = OUT / 'inputs/opportunity'
COMMIT = 'ac395e703d1fef573d1ef3e105df0286d62a0468'
REPO = 'Sparkling-Flames/3D_Manhattan_label'
spec = importlib.util.spec_from_file_location('ac_audit', ROOT / 'tools/thesis_main/analysis/audit_manual_order_ac_acceptance_20261104.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)

spec = importlib.util.spec_from_file_location('ac_membership', CACHE / 'summarize_ac_effects.py')
membership = importlib.util.module_from_spec(spec)
spec.loader.exec_module(membership)

RAW_KEYS = {
    'COMPLETE_COALITIONS': ['event_id', 'analysis_orientation_sign'],
    'FIXED_BLOCK_BACKGROUND_STEPS': ['pool_id', 'path_id', 'event_from', 'event_to'],
    'MEMBER_PANELS': ['pool_id', 'panel_id'],
    'SAMPLING_BATCHES': ['pool_id', 'cell_id'],
    'EXACT_NEUTRAL_OUTSIDE_BACKGROUND_PAIRS': ['background_comparison_id'],
}
META = set(membership.META) | {
    'X_workers', 'Z_workers', 'D_workers', 'equal_team_size', 'pure_cross_class_blocks',
    'B8L2_CA', 'A_B8L2', 'C_B8L2', 'A_output_state', 'C_output_state',
    'A_score_status', 'C_score_status', 'A_geometry_status', 'C_geometry_status',
    'A_order_status', 'C_order_status', 'A_nodes', 'C_nodes',
    'A_insufficient_nodes', 'C_insufficient_nodes', 'A_connection_failure', 'C_connection_failure',
    'A_output_invalid_geometry', 'C_output_invalid_geometry',
    'A_complete_evaluable', 'C_complete_evaluable',
}
READ_INPUTS = {Path(__file__).resolve(),
               ROOT/'tools/thesis_main/analysis/audit_manual_order_ac_acceptance_20261104.py',
               CACHE/'summarize_ac_effects.py'}
DENOMINATOR_CHECKS = []


def load(path):
    READ_INPUTS.add(Path(path))
    return pd.read_csv(path, low_memory=False)


@lru_cache(maxsize=40)
def cached(path):
    return load(path)


def count_check(rid, name, observed, expected, source):
    observed, expected = int(observed), int(expected)
    DENOMINATOR_CHECKS.append(dict(reversal_id=rid, check=name, observed=observed,
                                  expected=expected, passed=observed==expected, source=str(Path(source).relative_to(ROOT))))
    assert observed == expected, (rid, name, observed, expected)


def denominator_checks(r, old, new):
    """Registration and validity counts against independent published consumers."""
    for side, d in [('automatic', old), ('assisted', new)]:
        family = r['family']
        if family == 'main':
            folder = 'main_automatic_reproduced' if side == 'automatic' else 'main_assisted_affected_conditions'
            source = OLD / folder / 'CONDITION_METRIC_SUMMARY.csv.gz'
            record = a.pick(cached(source), r, a.GROUP+['metric']).iloc[0]
            count_check(r['reversal_id'], side+'_registered_main_events', len(d), record.registered_pairs, source)
            count_check(r['reversal_id'], side+'_valid_main_events', d.value.notna().sum(), record.valid_pairs, source)
        elif family == 'sensitivity':
            name = r['analysis_table']
            source = OLD / f'sensitivity/{side}_affected_conditions/pool_summaries/affected/{name}.csv.gz'
            expected = a.pick(cached(source), r, a.SPECS[name])
            # Legacy unequal output first averages alternate middle teams
            # within a registered parent. Its exported panel_rows counts
            # parents, whereas SOURCE_ROWS retains all middle paths.
            scalar = d.groupby(['pool_id','parent_contrast_id'], dropna=False).value.mean() if name == 'UNEQUAL_DECOMPOSITION' else d.value
            count_check(r['reversal_id'], side+'_registered_sensitivity_published_atoms', len(scalar), expected.panel_rows.sum(), source)
            count_check(r['reversal_id'], side+'_valid_sensitivity_published_atoms', scalar.notna().sum(), expected[r['metric']+'__valid'].sum(), source)
        elif family == 'three_leg':
            source = OLD / f'sensitivity/three_leg_common_support_v2/{side}/COMMON_VALID_THREE_LEG_IMAGE_SUMMARY.csv.gz'
            record = a.pick(cached(source), r, a.THREE+['metric']).iloc[0]
            count_check(r['reversal_id'], side+'_registered_middle_paths', len(d), record.registered_paths, source)
            count_check(r['reversal_id'], side+'_joint_valid_middle_paths', d.value.notna().sum(), record.valid_paths, source)
        elif family == 'exact_background':
            source = OLD / f'sensitivity/exact_outside_background/{side}/EXACT_NEUTRAL_OUTSIDE_POOL_SUMMARY.csv.gz'
            expected = a.pick(cached(source), r, a.EXACT)
            count_check(r['reversal_id'], side+'_registered_exact_background_pairs', len(d), expected.matched_background_pairs.sum(), source)
            blocks = d.groupby(['pool_id','X_workers','Z_workers'], dropna=False).value.mean()
            count_check(r['reversal_id'], side+'_valid_exact_XZ_blocks', blocks.notna().sum(), expected[r['metric']+'__valid_blocks'].sum(), source)


def key(frame, columns):
    return frame[columns].apply(lambda r: '|'.join(a.norm(v) for v in r), axis=1)


def patched_raw(name):
    original = load(DATA / f'{name}.csv.gz')
    if name == 'EXACT_NEUTRAL_OUTSIDE_BACKGROUND_PAIRS':
        update = load(OLD / 'sensitivity/exact_outside_background/assisted_pairs.csv.gz')
    else:
        update = load(OLD / f'sensitivity/raw_assisted/{name}.csv.gz')
    keys = RAW_KEYS[name]
    original['_id'] = key(original, keys)
    update['_id'] = key(update, keys)
    assert original._id.is_unique and update._id.is_unique
    before = original.set_index('_id', drop=False)
    after = before.copy()
    update = update.set_index('_id', drop=False)
    common = after.index.intersection(update.index)
    columns = after.columns.intersection(update.columns)
    after.loc[common, columns] = update.loc[common, columns]
    return before.reset_index(drop=True), after.reset_index(drop=True)


def three_raw():
    cap = load(CACHE / 'POOL_METHOD_CAPACITY.csv.gz').drop_duplicates('pool_id').set_index('pool_id').pool_n
    result = []
    for side in ['automatic', 'assisted']:
        d = load(OLD / f'sensitivity/three_leg_common_support_v2/{side}/SOURCE_ROWS.csv.gz')
        nd = d.parent_D_workers.fillna('').map(lambda x: len(x.split('|')) if x else 0)
        outside = d.pool_id.map(cap) - d.n_small - d.n_large + 2 * nd
        d['parent_background_stratum'] = np.where(nd.eq(0), 'zero_D', np.where(nd.eq(outside), 'all_outside_D', 'partial_outside_D'))
        result.append(d)
    return result


class Cohorts:
    def __init__(self, with_main=True):
        self.raw = {name: patched_raw(name) for name in RAW_KEYS}
        self.three = three_raw()
        self.main = [load(DATA / f'MAIN_REGISTERED_{side}.csv.gz') for side in ['AUTOMATIC', 'ASSISTED']] if with_main else None

    def atoms(self, r, side):
        family = r['family']
        name = r.get('analysis_table')
        metric = r['metric']
        if family == 'main':
            d = a.pick(self.main[side], r, a.GROUP)
            d['atom_id'] = d.event_id
            d['event_ids'] = d.event_id
            d['value'] = d[metric]
            d['atom_kind'] = 'registered_method_event'
        elif family == 'three_leg' or (family == 'sensitivity' and name == 'UNEQUAL_DECOMPOSITION'):
            keys = a.THREE if family == 'three_leg' else a.SPECS[name]
            d = a.pick(self.three[side], r, keys)
            leg = r['statistic'].split('_')[0] if family == 'three_leg' else metric.rsplit('__', 1)[1]
            d['atom_id'] = key(d, ['pool_id', 'parent_contrast_id', 'member_rep'])
            d['event_ids'] = d.total_event_id + '|' + d.equal_event_id + '|' + d.addition_event_id if family == 'three_leg' else d[leg + '_event_id']
            d['value'] = d['B8L2_CA__' + leg]
            if family == 'three_leg':
                d['value'] = d['value'].where(d[['B8L2_CA__total', 'B8L2_CA__equal', 'B8L2_CA__addition']].notna().all(axis=1))
            d['atom_kind'] = 'joint_three_leg_middle_path' if family == 'three_leg' else 'legacy_single_leg_path'
        elif family == 'exact_background':
            d = a.pick(self.raw['EXACT_NEUTRAL_OUTSIDE_BACKGROUND_PAIRS'][side], r, a.EXACT)
            d['atom_id'] = d.background_comparison_id
            d['event_ids'] = d.neutral_event_id + '|' + d.outside_event_id
            d['value'] = d[metric]
            d['atom_kind'] = 'exact_XZ_A_background_pair' if metric.startswith('A_') else 'exact_XZ_AC_background_pair'
        elif family == 'sensitivity':
            d = a.pick(self.raw[name][side], r, a.SPECS[name])
            d['value'] = d[metric]
            if name == 'MEMBER_PANELS':
                d = d[d.unique_pairs.gt(1)].copy()
                d['atom_id'] = key(d, ['pool_id', 'panel_id'])
                d['atom_kind'] = 'registered_member_panel'
            elif name == 'SAMPLING_BATCHES':
                d['atom_id'] = key(d, ['pool_id', 'cell_id'])
                d['event_ids'] = d.batch0_event_ids.fillna('') + '|' + d.batch1_event_ids.fillna('')
                d['atom_kind'] = 'registered_two_batch_cell'
            elif name == 'FIXED_BLOCK_BACKGROUND_STEPS':
                d['atom_id'] = key(d, ['pool_id', 'path_id', 'event_from', 'event_to'])
                d['event_ids'] = d.event_from + '|' + d.event_to
                d['atom_kind'] = 'registered_two_effect_background_step'
            elif name == 'COMPLETE_COALITIONS':
                d['atom_id'] = key(d, ['event_id', 'analysis_orientation_sign'])
                d['event_ids'] = d.event_id
                d['atom_kind'] = 'registered_oriented_coalition_event'
            else: raise ValueError(name)
        else: raise ValueError(family)
        assert d.atom_id.is_unique, (r['reversal_id'], 'duplicate registered atoms')
        return d


def direct_event_values(row, r):
    """Raw event Q masks; None denotes an aggregate needing its event shard."""
    family, name = r['family'], r.get('analysis_table')
    if family == 'main': return [(row.event_id, row.B8L2_CA)]
    if family == 'three_leg': return [(row[leg + '_event_id'], row['B8L2_CA__' + leg]) for leg in ['total', 'equal', 'addition']]
    if family == 'exact_background':
        return [(row.neutral_event_id, row.B8L2_CA__neutral_AC), (row.outside_event_id, row.B8L2_CA__outside_AC)]
    if name == 'COMPLETE_COALITIONS': return [(row.event_id, row.B8L2_CA)]
    if name == 'FIXED_BLOCK_BACKGROUND_STEPS': return [(row.event_from, row.B8L2_CA__from), (row.event_to, row.B8L2_CA__to)]
    if name == 'UNEQUAL_DECOMPOSITION':
        leg = r['metric'].rsplit('__', 1)[1]
        return [(row[leg + '_event_id'], row['B8L2_CA__' + leg])]
    if name == 'MEMBER_PANELS':
        complete = row.B8L2_CA__valid == row.unique_pairs
        return [(eid, 1.0 if complete else None) for eid in a.pipe(row.event_ids)]
    if name == 'SAMPLING_BATCHES':
        result = []
        for batch in ['batch0', 'batch1']:
            complete = row['B8L2_CA__' + batch + '_valid'] == row[batch + '_pairs']
            result.extend((eid, 1.0 if complete else None) for eid in a.pipe(row[batch + '_event_ids']))
        return result
    raise ValueError((family, name))


def endpoint_index():
    path = ROOT / 'research/fusion/manual_order_impact_20261104/endpoints/ENDPOINTS.jsonl.gz'
    READ_INPUTS.add(path)
    with gzip.open(path, 'rt', encoding='utf-8-sig') as stream:
        return {r['team_key']: r for r in map(json.loads, stream)}


def metric_shards(pools):
    """Preparation only; immutable HTTP reads and isolated cached copies."""
    dest = CACHE / 'opportunity_shards'
    dest.mkdir(parents=True, exist_ok=True)
    peer = OUT.parent / 'ac_peer/source_cache'
    receipts = []
    def one(pid):
        source = f'research/workers/personnel_ac_v21_20261030/stage04_metrics/metric_shards/{pid}.csv.gz'
        url = f'https://raw.githubusercontent.com/{REPO}/{COMMIT}/{source}'
        candidates = [CACHE / 'original_metric_shards' / (pid + '.csv.gz'), peer / (pid + '.csv.gz'), dest / (pid + '.csv.gz')]
        path = next((p for p in candidates if p.exists()), candidates[-1])
        if not path.exists():
            with urllib.request.urlopen(url, timeout=120) as response, path.open('wb') as f:
                while data := response.read(1024 * 1024): f.write(data)
        raw = load(path)
        d = raw[[c for c in raw if c in META]].copy()
        assisted_path = OLD / 'metric_shards' / path.name
        if assisted_path.exists():
            nd = load(assisted_path).reindex(columns=d.columns)
            assert set(d.event_id) == set(nd.event_id)
        else: nd = d.copy()
        record = dict(pool_id=pid, source=source, url=url, source_repository_commit=COMMIT,
                      source_bytes=path.stat().st_size, source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                      source_rows=len(raw), cached_path=str(path.relative_to(ROOT)),
                      assisted_source=str(assisted_path.relative_to(ROOT)) if assisted_path.exists() else 'unchanged frozen source')
        return d, nd, record
    with ThreadPoolExecutor(max_workers=5) as executor:
        entries = list(executor.map(one, sorted(pools)))
    before, after = [], []
    for d, nd, record in entries:
        before.append(d); after.append(nd); receipts.append(record)
    return pd.concat(before, ignore_index=True), pd.concat(after, ignore_index=True), receipts


def prepare_inputs():
    q = load(OUT / 'Q_REVERSALS.csv')
    own = q[~q.family.isin(['funnel', 'method_comparison'])]
    fullpools = load(OUT / 'inputs/MAIN_ORIGINAL_SELECTED_POOLS.csv.gz')
    main_conditions = q[q.family.eq('main')].drop_duplicates(a.GROUP)
    pool_ids = set()
    for r in main_conditions.to_dict('records'):
        pool_ids.update(a.pick(fullpools, r, a.GROUP).pool_id)
    before, after, receipts = metric_shards(pool_ids)
    # Frozen full links identify complete registered main cohorts, not only
    # the original nine affected pools or the already-supported event subset.
    link_source = CACHE / 'DESIGN_LINKS.csv.gz'
    chunks = []
    for chunk in pd.read_csv(link_source, chunksize=100000, low_memory=False, usecols=membership.LINK_COLS):
        chunks.append(chunk[chunk.pool_id.isin(pool_ids)])
    links = pd.concat(chunks, ignore_index=True)
    main_ids = set()
    for d, side in [(before, 'AUTOMATIC'), (after, 'ASSISTED')]:
        known = d.source_role_rank.notna() & d.target_role_rank.notna()
        d = d.copy()
        d['role_direction'] = np.where(known, d.source_role_rank.map(a.norm) + '->' + d.target_role_rank.map(a.norm), d.source_class.astype(str) + '->' + d.target_class.astype(str))
        views = membership.views(d, links)
        parts = [a.pick(views, r, a.GROUP) for r in main_conditions.to_dict('records')]
        complete = pd.concat(parts, ignore_index=True)
        main_ids.update(complete.event_id)
        a.save(complete, DATA / f'MAIN_REGISTERED_{side}.csv.gz')
    cohorts = Cohorts()
    needed = {(r.pool_id, r.event_id) for r in before[before.event_id.isin(main_ids)].itertuples()}
    # In an aggregated panel, even a finite panel mean can hide a missing
    # registered event. Query its complete event list whenever counts differ.
    for r in own.to_dict('records'):
        for side in [0, 1]:
            for row in cohorts.atoms(r, side).itertuples(index=False):
                sr = pd.Series(row._asdict())
                for eid, value in direct_event_values(sr, r):
                    if value is None or pd.isna(value) or (r['family'] == 'exact_background' and r['metric'].startswith('A_')):
                        needed.add((sr.pool_id, eid))
    affected = load(OLD / 'AFFECTED_EVENT_METRICS_ASSISTED.csv.gz')
    needed.update(zip(affected.pool_id, affected.event_id))
    additional = {pid for pid, eid in needed} - pool_ids
    if additional:
        b, n, extra = metric_shards(additional)
        before = pd.concat([before, b], ignore_index=True)
        after = pd.concat([after, n], ignore_index=True)
        receipts += extra
    ids = {eid for pid, eid in needed}
    before = before[before.event_id.isin(ids)].copy()
    after = after[after.event_id.isin(ids)].copy()
    assert before.event_id.is_unique and set(before.event_id) == ids and set(after.event_id) == ids
    for d, side in [(before, 'AUTOMATIC'), (after, 'ASSISTED')]: a.save(d, DATA / f'EVENT_STATUS_{side}.csv.gz')
    a.jsave(OUT / 'OPPORTUNITY_EVENT_SOURCE_MANIFEST.json', receipts)
    selected = dict(source_repository_commit=COMMIT, registered_main_conditions=main_conditions[a.GROUP].to_dict('records'),
                    link_source='research/workers/personnel_ac_v21_20261030/stage01_registered/DESIGN_LINKS.csv.gz',
                    link_cache_sha256=hashlib.sha256(link_source.read_bytes()).hexdigest(),
                    selected_main_event_ids=sorted(main_ids), selected_status_event_ids=sorted(ids),
                    event_filter='all registered main Q reversal events; all registered Q reversal missing events, partially supported panel events, required single-arm events; all original 339 affected AC events',
                    events=len(ids), pools=before.pool_id.nunique())
    a.jsave(OUT / 'OPPORTUNITY_EVENT_EXTRACTION.json', selected)
    print('OPPORTUNITY_INPUTS_PREPARED', len(ids), 'events', before.pool_id.nunique(), 'pools', flush=True)


def audit_own():
    q = load(OUT / 'Q_REVERSALS.csv')
    own = q[~q.family.isin(['funnel', 'method_comparison'])]
    cohorts = Cohorts()
    status = [load(DATA / f'EVENT_STATUS_{side}.csv.gz').set_index('event_id') for side in ['AUTOMATIC', 'ASSISTED']]
    endpoints = endpoint_index()
    conditions, atoms, dependencies, failures = [], [], [], []
    for r in own.to_dict('records'):
        old, new = [cohorts.atoms(r, side).set_index('atom_id', drop=False) for side in [0, 1]]
        assert set(old.index) == set(new.index)
        new = new.reindex(old.index)
        denominator_checks(r, old, new)
        event_before, event_after = {}, {}
        requirements = {}
        for aid in old.index:
            ro, rn = old.loc[aid], new.loc[aid]
            roles = ['A'] if r['family'] == 'exact_background' and r['metric'].startswith('A_') else ['A', 'C']
            vals = [direct_event_values(x, r) for x in [ro, rn]]
            for side, ls in enumerate(vals):
                target = event_before if side == 0 else event_after
                for eid, v in ls:
                    if eid in status[side].index:
                        ev = status[side].loc[eid]
                        valid = all(pd.notna(ev[arm + '_B8L2']) for arm in roles)
                    else:
                        assert v is not None, (r['reversal_id'], eid, 'aggregate event unresolved')
                        valid = pd.notna(v)
                    if eid in target: assert target[eid] == valid
                    target[eid] = valid
                    requirements.setdefault(eid, set()).update(roles)
            atoms.append(dict(reversal_id=r['reversal_id'], family=r['family'], analysis_table=r.get('analysis_table'),
                              atom_id=aid, atom_kind=rn.atom_kind, pool_id=rn.pool_id, image=rn.image, building=rn.building,
                              event_ids=rn.event_ids, old_value=ro.value, expanded_value=rn.value,
                              original_atom_evaluable=pd.notna(ro.value), expanded_atom_evaluable=pd.notna(rn.value)))
        assert set(event_before) == set(event_after)
        residual = [eid for eid, valid in event_after.items() if not valid]
        condition_failures = []
        for eid in event_before:
            dependencies.append(dict(reversal_id=r['reversal_id'], event_id=eid,
                                     required_arms='|'.join(sorted(requirements[eid])),
                                     original_required_Q_evaluable=event_before[eid], expanded_required_Q_evaluable=event_after[eid],
                                     status_source='frozen event status subset' if eid in status[1].index else 'finite registered event scalar in complete frozen raw table'))
        for eid in residual:
            assert eid in status[1].index, ('residual event has no exact endpoint evidence', r['reversal_id'], eid)
            ev, ev0 = status[1].loc[eid], status[0].loc[eid]
            for arm in requirements[eid]:
                if pd.notna(ev[arm + '_B8L2']): continue
                other = 'C' if arm == 'A' else 'A'
                team = ev[arm + '_team_key']
                confirmed = team in endpoints
                opponent_confirmed = ev[other + '_team_key'] in endpoints
                state = ev[arm + '_output_state']
                nodes = ev[arm + '_nodes']
                eligible = state == 'no_connection' and pd.notna(nodes) and nodes >= 4
                opportunity_gap = not confirmed and not (pd.notna(nodes) and nodes < 4)
                category = ('confirmed57_fixed_geometry_invalid' if confirmed else
                            'outside57_no_connection_at_least_four_nodes' if eligible else
                            'below_four_not_repairable_by_order' if pd.notna(nodes) and nodes < 4 else
                            'outside57_other_unscored_state')
                rec = dict(reversal_id=r['reversal_id'], event_id=eid, physical_pair_id=ev.physical_pair_id,
                           pool_id=ev.pool_id, image=ev.image, building=ev.building, method=ev.method,
                           failed_arm=arm, failed_team_key=team, opponent_team_key=ev[other + '_team_key'],
                           original_failed_Q=ev0[arm + '_B8L2'], expanded_failed_Q=ev[arm + '_B8L2'],
                           original_opponent_Q=ev0[other + '_B8L2'], expanded_opponent_Q=ev[other + '_B8L2'],
                           selected_nodes=nodes, output_state=state, score_status=ev[arm + '_score_status'],
                           geometry_status=ev[arm + '_geometry_status'], order_status=ev[arm + '_order_status'],
                           failed_endpoint_in_confirmed57=confirmed, opponent_in_confirmed57=opponent_confirmed,
                           failed_review_id=endpoints.get(team, {}).get('review_id', ''),
                           opponent_review_id=endpoints.get(ev[other + '_team_key'], {}).get('review_id', ''),
                           potential_order_opportunity_not_covered=eligible and not confirmed,
                           unreviewed_geometry_opportunity_not_covered=opportunity_gap,
                           category=category, confirmed57_propagation_bug=False,
                           existing_order_reuse_status='not assumed; exact frozen-geometry match required',
                           new_order_generated=False)
                failures.append(rec); condition_failures.append(rec)
        valid_new = new.value.notna()
        valid_old = old.value.notna()
        registered_events = len(event_after)
        old_valid_events = sum(event_before.values())
        new_valid_events = sum(event_after.values())
        parent_atoms = [d.groupby(['pool_id','parent_contrast_id'], dropna=False).value.mean() for d in [old,new]] if r.get('analysis_table') == 'UNEQUAL_DECOMPOSITION' else [old.value,new.value]
        # Mean/path/panel row denominators are not the same as underlying event
        # denominators; retain both and never promote a finite pool to complete.
        conditions.append(dict(reversal_id=r['reversal_id'], family=r['family'], analysis_table=r.get('analysis_table'),
            statistic=r['statistic'], metric=r['metric'], source_keys=r['source_keys'],
            registered_atoms=len(new), original_evaluable_atoms=int(valid_old.sum()), expanded_evaluable_atoms=int(valid_new.sum()),
            registered_atom_kind=new.atom_kind.iloc[0], published_atom_kind='parent contrast after averaging registered middle paths' if r.get('analysis_table')=='UNEQUAL_DECOMPOSITION' else new.atom_kind.iloc[0],
            published_registered_atoms=len(parent_atoms[1]), published_original_evaluable_atoms=int(parent_atoms[0].notna().sum()), published_expanded_evaluable_atoms=int(parent_atoms[1].notna().sum()),
            residual_unevaluable_atoms=int((~valid_new).sum()), registered_events=registered_events,
            original_evaluable_required_events=old_valid_events, expanded_evaluable_required_events=new_valid_events,
            residual_unevaluable_required_events=registered_events-new_valid_events,
            registered_pools=int(new.pool_id.nunique()), registered_images=int(new.image.nunique()),
            original_evaluable_pools=int(old.loc[valid_old, 'pool_id'].nunique()), expanded_evaluable_pools=int(new.loc[valid_new, 'pool_id'].nunique()),
            original_evaluable_images=int(old.loc[valid_old, 'image'].nunique()), expanded_evaluable_images=int(new.loc[valid_new, 'image'].nunique()),
            required_Q_contract='A arm only for A-background metric' if r['metric'].startswith('A_') else 'both AC arms on each metric-required registered event',
            residual_failed_endpoints=len({x['failed_team_key'] for x in condition_failures}),
            outside57_order_eligible_failed_endpoints=len({x['failed_team_key'] for x in condition_failures if x['potential_order_opportunity_not_covered']}),
            outside57_order_eligible_with_confirmed57_opponent=len({x['failed_team_key'] for x in condition_failures if x['potential_order_opportunity_not_covered'] and x['opponent_in_confirmed57']}),
            confirmed57_propagation_complete=True,
            all_registered_required_Q_evaluable=registered_events==new_valid_events,
            all_registered_order_opportunities_covered=not any(x['unreviewed_geometry_opportunity_not_covered'] for x in condition_failures),
            audit_completed=True, audited_scope='complete registered named condition; no expansion to new teams',
            conclusion_boundary='已验收当前可评支持；全注册同等人工处理机会仍不完整' if any(x['unreviewed_geometry_opportunity_not_covered'] for x in condition_failures) else '当前条件无未处理的无连接/无效底面端点；不足四节点仍不可评，不能声称完整Q支持'))
    a.save(pd.DataFrame(conditions), OUT / 'Q_OPPORTUNITY_CONDITIONS_OWN.csv')
    a.save(pd.DataFrame(atoms), OUT / 'Q_REGISTERED_ANALYSIS_ATOMS_OWN.csv.gz')
    a.save(pd.DataFrame(dependencies), OUT / 'Q_REGISTERED_EVENT_SUPPORT_OWN.csv.gz')
    a.save(pd.DataFrame(failures), OUT / 'Q_RESIDUAL_ENDPOINTS_OWN.csv.gz')
    # All 82 affected but still-unevaluable method events are also explicitly
    # indexed, without suggesting that they all enter a Q-reversal estimand.
    affected = load(OLD / 'AFFECTED_EVENT_METRICS_ASSISTED.csv.gz')
    affected = affected[affected.B8L2_CA.isna()].copy()
    affected['A_in_confirmed57'] = affected.A_team_key.isin(endpoints)
    affected['C_in_confirmed57'] = affected.C_team_key.isin(endpoints)
    affected['touches_fixed_invalid_pa4'] = affected.pool_id.str.startswith('pa4otMbVnkk-18')
    cols = ['event_id','physical_pair_id','pool_id','image','method','A_team_key','C_team_key','A_B8L2','C_B8L2','A_nodes','C_nodes','A_output_state','C_output_state','A_in_confirmed57','C_in_confirmed57','touches_fixed_invalid_pa4']
    a.save(affected[cols], OUT / 'ALL_AFFECTED_RESIDUAL_EVENT_STATES.csv.gz')
    a.save(pd.DataFrame(DENOMINATOR_CHECKS), OUT / 'OPPORTUNITY_DENOMINATOR_CHECKS.csv')
    print('OPPORTUNITY_OWN_COMPLETE', len(conditions), 'rows', len(atoms), 'atoms', len(dependencies), 'event links', len(failures), 'residual endpoint links', flush=True)
    return pd.DataFrame(conditions), pd.DataFrame(failures)


def finalize():
    """Join the disjoint 55-row and 5-row audits, preserving scope contracts."""
    own = load(OUT / 'Q_OPPORTUNITY_CONDITIONS_OWN.csv').rename(columns={
        'original_evaluable_required_events':'original_required_events',
        'expanded_evaluable_required_events':'expanded_required_events',
        'residual_unevaluable_required_events':'residual_required_events',
        'all_registered_order_opportunities_covered':'all_registered_opportunities_covered'})
    secondary = OUT.parent / 'ac_opportunity_secondary'
    more = load(secondary / 'CONDITION_OPPORTUNITY_AUDIT.csv')
    q = load(OUT / 'Q_REVERSALS.csv').set_index('reversal_id', drop=False)
    sr = []
    for r in more.to_dict('records'):
        qr = q.loc[r['reversal_id']]
        sr.append(dict(reversal_id=r['reversal_id'],family=r['family'],analysis_table='',
            statistic=qr.statistic,metric=qr.metric,source_keys=qr.source_keys,
            registered_atoms=r['registered_events'],original_evaluable_atoms=r['automatic_valid_events'],
            expanded_evaluable_atoms=r['assisted_valid_events'],residual_unevaluable_atoms=r['residual_events'],
            registered_atom_kind='registered_method_event',
            published_atom_kind='common registered method pool' if r['family']=='method_comparison' else 'pool after exact XZ block and direction means',
            published_registered_atoms=r['registered_pools'],published_original_evaluable_atoms=r['automatic_valid_pools'],published_expanded_evaluable_atoms=r['assisted_valid_pools'],
            registered_events=r['registered_events'],original_required_events=r['automatic_valid_events'],
            expanded_required_events=r['assisted_valid_events'],residual_required_events=r['residual_events'],
            registered_pools=r['registered_pools'],original_evaluable_pools=r['automatic_valid_pools'],expanded_evaluable_pools=r['assisted_valid_pools'],
            required_Q_contract='both AC arms of the two methods\' registered event-ID union; method-specific directions then common pools' if r['family']=='method_comparison' else 'both AC arms on each registered equal-size pure-block event',
            residual_failed_endpoints=r['residual_distinct_endpoints'],outside57_order_eligible_failed_endpoints=r['residual_no_connection_endpoints'],
            outside57_order_eligible_with_confirmed57_opponent=r['no_connection_endpoints_with_confirmed_counterpart'],
            confirmed57_propagation_complete=r['confirmed_order_propagation_complete'],
            all_registered_required_Q_evaluable=r['all_registered_events_Q_evaluable'],
            all_registered_opportunities_covered=r['all_registered_opportunities_covered'],audit_completed=r['audit_completed'],
            audited_scope='complete registered named condition; no expansion to new teams',
            conclusion_boundary=r['judgment_scope']))
    combined = pd.concat([own,pd.DataFrame(sr)], ignore_index=True).sort_values('reversal_id')
    assert len(combined)==60 and combined.reversal_id.is_unique and set(combined.reversal_id)==set(q.index)
    combined['event_count_contract'] = 'unique registered method-event IDs needed by this estimand; reuse across methods/views is not an independent physical trial'
    combined['opportunity_contract'] = 'all residual endpoints received their confirmed order or are documented below four frozen nodes; unreviewed no_connection/invalid_floor do not count as covered'
    combined['current_evaluable_support_numeric_acceptance'] = 'PASS'
    combined['original_same_event_support_judgment'] = '保持'
    combined['full_registered_numeric_or_fairness_judgment'] = np.where(combined.all_registered_opportunities_covered,
        np.where(combined.all_registered_required_Q_evaluable, '该条件完整注册所需Q已覆盖', '固定节点下残余结构不合格；保留当前可评支持'),
        '尚不能判断完整同等处理后的精确幅度或公平性；当前支持结果已验收')

    # Only the two independently proven full-cohort/weight aliases are merged.
    # Shared *new* event IDs are not a complete-evidence alias test.
    raw3_ids = set(q[(q.method.eq('V21_DSTRUCT_RAW3_K3') & q.scope.eq('other_admitted')) & (
        (q.family.eq('main') & q.analysis_view.isin(['A_fixed_n_pure_class','whole_equal_fixed_n_pure_class','whole_equal_fixed_n_all_m_pure_class'])) |
        q.analysis_table.eq('MEMBER_PANELS') | (q.family.eq('funnel') & q.n.eq(4) & q.m.eq(4)))].index)
    assert len(raw3_ids)==9
    bound_path = OUT.parent / 'ac_peer/RAW3_RESIDUAL_AND_BOUNDS_CHECKS.json'
    READ_INPUTS.add(bound_path)
    READ_INPUTS.add(secondary/'CHECKS.json')
    bounds = json.loads(bound_path.read_text())
    combined['legal_completion_effect_lower'] = np.nan
    combined['legal_completion_effect_upper'] = np.nan
    combined['completion_direction_proof'] = ''
    mask = combined.reversal_id.isin(raw3_ids)
    combined.loc[mask,'legal_completion_effect_lower'] = bounds['complete16_effect_lower']
    combined.loc[mask,'legal_completion_effect_upper'] = bounds['complete16_effect_upper']
    combined.loc[mask,'completion_direction_proof'] = 'RAW3 fixed16: every legal missing-Q completion or retained-missing subset remains negative; exact amplitude and equal opportunity not established'
    combined.loc[mask,'full_registered_numeric_or_fairness_judgment'] = '方向保持为负（合法界限证明）；精确幅度和同等人工机会尚不能判断'
    a.save(combined, OUT / 'Q_OPPORTUNITY_CONDITIONS.csv')

    failures = load(OUT / 'Q_RESIDUAL_ENDPOINTS_OWN.csv.gz')
    foreign = load(secondary / 'RESIDUAL_ENDPOINTS.csv')
    events = load(secondary / 'RESIDUAL_EVENTS.csv.gz').drop_duplicates(['reversal_id','event_id']).set_index(['reversal_id','event_id'])
    endpoints = endpoint_index()
    fs = []
    for row in foreign.to_dict('records'):
        ev = events.loc[(row['reversal_id'],row['event_id'])]
        arm = row['arm']; other='C' if arm=='A' else 'A'
        cat = ('outside57_no_connection_at_least_four_nodes' if row['score_status']=='no_connection' else
               'below_four_not_repairable_by_order' if row['nodes']<4 else 'outside57_other_unscored_state')
        fs.append(dict(reversal_id=row['reversal_id'],event_id=row['event_id'],physical_pair_id=row['physical_pair_id'],
            pool_id=row['pool_id'],image=row['image'],building=row['building'],method=row['method'],failed_arm=arm,
            failed_team_key=row['team_key'],opponent_team_key=row['counterpart_team_key'],
            original_failed_Q=row['automatic_Q'],expanded_failed_Q=row['assisted_Q'],
            original_opponent_Q=ev['automatic_'+other+'_B8L2'],expanded_opponent_Q=row['counterpart_Q'],
            selected_nodes=row['nodes'],output_state=row['score_status'],score_status=row['score_status'],
            geometry_status=ev[arm+'_geometry_status'],order_status=row['order_status'],
            failed_endpoint_in_confirmed57=row['in_confirmed57'],opponent_in_confirmed57=row['counterpart_in_confirmed57'],
            failed_review_id=endpoints.get(row['team_key'],{}).get('review_id',''),opponent_review_id=endpoints.get(row['counterpart_team_key'],{}).get('review_id',''),
            potential_order_opportunity_not_covered=row['score_status']=='no_connection' and row['nodes']>=4 and not row['in_confirmed57'],
            unreviewed_geometry_opportunity_not_covered=row['nodes']>=4 and not row['in_confirmed57'],
            category=cat,confirmed57_propagation_bug=row['confirmed_score_missing_from_consumer'],
            existing_order_reuse_status='not assumed; exact frozen-geometry match required',new_order_generated=False))
    failures = pd.concat([failures,pd.DataFrame(fs)], ignore_index=True).sort_values(['reversal_id','event_id','failed_arm'])
    assert not failures.duplicated(['reversal_id','event_id','failed_arm']).any()
    assert not failures.confirmed57_propagation_bug.any()
    a.save(failures, OUT / 'Q_RESIDUAL_ENDPOINT_REFERENCES.csv.gz')
    distinct=[]
    for team,d in failures.groupby('failed_team_key',sort=True):
        base=d.iloc[0].to_dict()
        for col in ['reversal_id','event_id','physical_pair_id','method','failed_arm','opponent_team_key','opponent_review_id']:
            base[col+'s']='|'.join(sorted(set(d[col].dropna().astype(str))))
        base['condition_rows']=d.reversal_id.nunique();base['registered_method_events']=d.event_id.nunique()
        base['registered_physical_pairs']=d.physical_pair_id.nunique()
        base['any_opponent_in_confirmed57']=bool(d.opponent_in_confirmed57.any())
        base['opponent_in_confirmed57']=bool(d.opponent_in_confirmed57.any())
        base['all_referenced_opponent_Q_available']=bool(d.expanded_opponent_Q.notna().all())
        distinct.append(base)
    distinct=pd.DataFrame(distinct)
    # Exact peer matches are evidence, not an assumption based on a shared image.
    reuse=load(OUT.parent/'ac_peer/RAW3_RESIDUAL_ORDER_REUSE_CHECK.csv').set_index('team_key')
    for i,d in distinct.iterrows():
        if d.failed_team_key in reuse.index:
            rr=reuse.loc[d.failed_team_key]
            distinct.loc[i,'existing_order_reuse_status']='exact frozen coordinates checked: 0 confirmed57 matches and 0 legacy33 matches'
            distinct.loc[i,'order_reuse_evidence']='../ac_peer/RAW3_RESIDUAL_ORDER_REUSE_CHECK.csv'
    addition_path=OUT.parent/'ac_peer_addendum/SIX_ENDPOINT_REUSE_RESULTS.csv'
    additional=load(addition_path).set_index('team_key')
    assert len(additional)==6 and additional.exact_coordinates_confirmed57.eq(0).all() and additional.exact_coordinates_legacy33.eq(0).all()
    for i,d in distinct.iterrows():
        if d.failed_team_key in additional.index:
            distinct.loc[i,'existing_order_reuse_status']='exact frozen coordinates checked: 0 confirmed57 matches and 0 legacy33 matches'
            distinct.loc[i,'order_reuse_evidence']='../ac_peer_addendum/SIX_ENDPOINT_REUSE_RESULTS.csv'
    a.save(distinct,OUT/'Q_DISTINCT_RESIDUAL_ENDPOINTS.csv')
    direct=distinct[distinct.any_opponent_in_confirmed57].copy()
    assert direct.loc[direct.potential_order_opportunity_not_covered,'order_reuse_evidence'].notna().all()
    a.save(direct,OUT/'DIRECT_CONFIRMED57_OPPONENT_RESIDUALS.csv')

    # Verify the accepted score reached every exact confirmed57 reference in
    # the targeted status input, including the known invalid pa4 endpoint.
    status=load(DATA/'EVENT_STATUS_ASSISTED.csv.gz')
    propagation=[]
    for r in status.to_dict('records'):
        for arm in ['A','C']:
            team=r[arm+'_team_key']
            if team not in endpoints: continue
            expected=endpoints[team]['B8L2']; actual=r[arm+'_B8L2']
            ok=(pd.isna(expected) and pd.isna(actual)) or (pd.notna(expected) and pd.notna(actual) and abs(expected-actual)<=1e-7)
            assert ok, ('confirmed order score absent',r['event_id'],arm,team)
            assert r[arm+'_nodes']==endpoints[team]['nodes']
            propagation.append(dict(event_id=r['event_id'],arm=arm,team_key=team,review_id=endpoints[team]['review_id'],
                endpoint_Q=expected,consumer_Q=actual,passed=ok,expected_Q_missing=pd.isna(expected)))
    a.save(pd.DataFrame(propagation),OUT/'CONFIRMED57_AC_PROPAGATION_RECHECK.csv')

    # Build 37 named scientific conditions from 42 literal condition/leg keys.
    named=[]
    allq=q.reset_index(drop=True).merge(combined,on='reversal_id',how='left',validate='one_to_one',suffixes=('','_opportunity'))
    allq['literal_condition_key']=allq.apply(lambda r:r.source_keys+('|leg:'+r.statistic.split('_')[0] if r.family=='three_leg' else ''),axis=1)
    assert allq.literal_condition_key.nunique()==42
    allq['named_condition_key']=allq.literal_condition_key
    allq.loc[allq.reversal_id.isin(raw3_ids),'named_condition_key']='proven_alias:RAW3_other_n4_m4_pure_class_complete16'
    allq.loc[allq.reversal_id.isin(['c6ead94a1c5a3ce5','8a0360c4464167ec']),'named_condition_key']='proven_alias:OPPSTRUCT_primary_n28_m1_complete14'
    assert allq.named_condition_key.nunique()==37
    for nk,d in allq.groupby('named_condition_key',sort=True):
        named.append(dict(named_condition_id=hashlib.sha256(nk.encode()).hexdigest()[:16],
            named_condition_key=nk,reversal_rows=len(d),reversal_ids='|'.join(d.reversal_id),
            original_registered_condition_definitions=json.dumps([json.loads(x) for x in sorted(set(d.source_keys))],ensure_ascii=False),
            statistics='|'.join(sorted(set(d.statistic))),metric_semantics='|'.join(sorted(set(d.metric_semantics))),
            original_common_support_judgment='保持',current_support_judgment='条件变化；相应旧方向叙述需改写',
            complete_opportunity_covered=bool(d.all_registered_opportunities_covered.all()),
            complete_required_Q_evaluable=bool(d.all_registered_required_Q_evaluable.all()),
            full_registered_judgment='|'.join(sorted(set(d.full_registered_numeric_or_fairness_judgment))),
            independent_new_experiments=0,
            alias_proof='../ac_peer/RAW3_PURE_CLASS_EXACT_ALIAS_VERIFICATION.csv' if nk.startswith('proven_alias:RAW3') else '../ac_peer/FUNNEL_N28_M1_EXACT_ALIAS_COHORT.csv' if nk.startswith('proven_alias:OPP') else 'same literal condition and same leg; image/building weights retained as separate statistics'))
    a.save(pd.DataFrame(named),OUT/'NAMED_Q_REVERSAL_CONDITIONS.csv')
    concise=allq[['reversal_id','family','analysis_table','source_keys','statistic','metric','metric_semantics','old_effect','expanded_effect',
                 'aggregation_unit','registered_events','original_required_events','expanded_required_events','residual_required_events',
                 'registered_atoms','original_evaluable_atoms','expanded_evaluable_atoms','registered_atom_kind','published_atom_kind',
                 'published_registered_atoms','published_original_evaluable_atoms','published_expanded_evaluable_atoms',
                 'all_registered_opportunities_covered','all_registered_required_Q_evaluable','required_Q_contract','original_same_event_support_judgment',
                 'full_registered_numeric_or_fairness_judgment','legal_completion_effect_lower','legal_completion_effect_upper','source']].copy()
    concise['current_evaluable_result_judgment']='条件变化'
    concise['expanded_direction_statement_judgment']='需改写为新可评支持及原计权范围内的方向'
    a.save(concise,OUT/'CONCLUSIONS.csv')
    checks=dict(status='PASS_WITH_EXPLICIT_OPPORTUNITY_LIMIT',audit_completed=True,
        source_repository_commit=COMMIT,Q_reversal_rows=60,literal_named_condition_legs=42,
        exact_alias_deduplicated_named_conditions=37,independent_new_experiments=0,
        confirmed57_propagation_complete=True,confirmed57_propagation_failures=0,
        all_registered_opportunities_covered=bool(combined.all_registered_opportunities_covered.all()),
        all_registered_required_Q_evaluable=bool(combined.all_registered_required_Q_evaluable.all()),
        condition_rows_with_opportunity_gap=int((~combined.all_registered_opportunities_covered).sum()),
        condition_rows_with_residual_required_Q=int((~combined.all_registered_required_Q_evaluable).sum()),
        distinct_residual_endpoints=len(distinct),distinct_residual_method_events=failures.event_id.nunique(),
        distinct_residual_physical_pairs=failures.physical_pair_id.nunique(),residual_endpoint_reference_rows=len(failures),
        distinct_residual_categories=distinct.category.value_counts().to_dict(),
        distinct_failed_endpoints_in_confirmed57=int(distinct.failed_endpoint_in_confirmed57.sum()),
        distinct_residual_endpoints_with_confirmed57_opponent=len(direct),
        distinct_no_connection_endpoints_with_confirmed57_opponent=int(direct.potential_order_opportunity_not_covered.sum()),
        specific_direct_no_connection_opponent_reuse_audit_completed=True,
        specific_direct_no_connection_opponents_with_reusable_order=0,
        reuse_check_boundary='The eight no_connection residual endpoints with a confirmed57 opponent were exactly checked against confirmed57 and legacy33 frozen coordinates; the other outside57 inventory is not claimed to have undergone full geometric matching.',
        registered_cohort_denominator_checks=len(DENOMINATOR_CHECKS),registered_cohort_denominator_mismatches=0,
        secondary_opportunity_checks=json.loads((secondary/'CHECKS.json').read_text()),
        original_numerical_acceptance='CHECKS.json; 5767 completed checks retained, not rerun for the opportunity audit',
        RAW3_fixed16_all_legal_completions_still_negative=True,RAW3_full16_legal_effect_bounds=[bounds['complete16_effect_lower'],bounds['complete16_effect_upper']],
        missing_Q_imputed=False,new_orders=0,new_teams=0,new_fusions=0,new_endpoint_scores=0,new_classifications=0,
        mandatory_new_human_queue_created=False,
        boundary='No missed propagation of confirmed57 was found. Outside57 failures limit complete-cohort treatment opportunity and exact amplitudes. Current supported estimands remain valid; no new orders are invented. Unproved complete-cohort directions are not asserted; the fixed RAW3 negative direction is separately bounded.',
        event_count_contract='Method-event IDs are not deduplicated physical experiments. Method comparisons count the union of both method-specific registered event sets; rows and endpoint references across views/metrics overlap.',
        complete_table='Q_OPPORTUNITY_CONDITIONS.csv',residual_table='Q_RESIDUAL_ENDPOINT_REFERENCES.csv.gz',
        distinct_residual_table='Q_DISTINCT_RESIDUAL_ENDPOINTS.csv',direct_counterpart_table='DIRECT_CONFIRMED57_OPPONENT_RESIDUALS.csv')
    a.jsave(OUT/'OPPORTUNITY_CHECKS.json',checks)
    print(json.dumps({k:checks[k] for k in ['status','Q_reversal_rows','condition_rows_with_opportunity_gap','distinct_residual_endpoints','distinct_residual_categories','distinct_residual_endpoints_with_confirmed57_opponent']},ensure_ascii=False),flush=True)

    # Small exact source subsets are the default runtime inputs. All large
    # immutable downloads below are only refresh/extraction caches.
    exclusion_path=OUT/'DELIVERY_EXCLUSIONS.json'
    exclusions=json.loads(exclusion_path.read_text())
    extra=[str(p.relative_to(OUT)) for folder in [CACHE/'opportunity_full_downloads',CACHE/'opportunity_shards'] for p in sorted(folder.glob('*')) if p.is_file()]
    exclusions['safe_to_exclude']=sorted(set(exclusions['safe_to_exclude']+extra))
    exclusions['opportunity_cache_reason']='Default opportunity_audit.py reads bundled exact condition and event-status subsets. Full immutable URLs/SHA256 and selection definitions are preserved in OPPORTUNITY_INPUT_MANIFEST.json and OPPORTUNITY_EVENT_SOURCE_MANIFEST.json / OPPORTUNITY_EVENT_EXTRACTION.json. --prepare-inputs refreshes those subsets if desired.'
    a.jsave(exclusion_path,exclusions)
    subset_receipts=[]
    for p in sorted(DATA.glob('*.csv.gz')):
        subset_receipts.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    a.jsave(OUT/'OPPORTUNITY_SUBSET_SHA256.json',subset_receipts)
    extraction_path=OUT/'OPPORTUNITY_EVENT_EXTRACTION.json'
    extraction=json.loads(extraction_path.read_text())
    extraction['link_source']='research/workers/personnel_ac_v21_20261030/stage01_registered/DESIGN_LINKS.csv.gz'
    extraction['subset_sha_manifest']='OPPORTUNITY_SUBSET_SHA256.json'
    a.jsave(extraction_path,extraction)
    used=[]
    for p in sorted(READ_INPUTS):
        used.append(dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size))
    a.save(pd.DataFrame(used),OUT/'OPPORTUNITY_RUNTIME_INPUTS.csv')


if __name__ == '__main__':
    if '--prepare-inputs' in sys.argv: prepare_inputs()
    audit_own()
    finalize()
