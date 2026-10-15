"""人员来源覆盖、条件分项画像与独立于最终Q的时间粗类探索。"""
from collections import Counter
from itertools import combinations
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd

from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
from .fit_worker_evidence_strata_20260908 import informative, sufficient, solve

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/workers/worker_classification_progress_20261014'
HISTORY = ROOT / 'analysis_results/worker_four_block_exploration_20260910_v1'
METRICS = ('iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter', 'height_mean_ratio')


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8-sig'))


def csv(name, frame):
    if 'training_buildings' in frame:
        frame = frame.copy()
        frame['training_buildings'] = frame.training_buildings.map(json.dumps)
    frame.to_csv(OUT / name, index=False, encoding='utf-8-sig')


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def historical_worker(value):
    return f'W{int(value):03d}'


def bind_time(obj, row):
    if row is None:
        return dict(time_binding='not_in_historical_table', time_usable=False, time_value=None)
    if (historical_worker(row['worker_id']), historical_worker(row['worker_id_timing']),
        row['image_id'], row['building_id']) != (
        obj['worker_id'], obj['worker_id'], obj['image_id'], obj['building_id']):
        raise ValueError('time identity mismatch: '+str(obj))
    valid = row['time_ok'] if 'time_ok' in row else row['usable_time']
    if not isinstance(valid, (bool, np.bool_)):
        raise ValueError('time eligibility must be boolean')
    value = None
    if valid:
        seconds = float(row['active_time_seconds'])
        if row['active_time_source'] == 'lead_time_fallback' or not row['active_time_source_file'] or seconds <= 0:
            raise ValueError('invalid time source')
        value = float(row['time'])
        if not np.isfinite(value) or not np.isclose(value, np.log1p(seconds), rtol=0, atol=1e-12):
            raise ValueError('frozen active time value mismatch')
    return dict(time_binding='project_task_worker_and_image_matched', time_usable=bool(valid),
        time_value=value, historical_canonical_id=row['canonical_annotation_id'],
        time_seconds=row['active_time_seconds'], time_source=row['active_time_source'],
        time_source_file=row['active_time_source_file'], timing_status=row['timing_status'],
        time_context=row.get('original_context_key', row.get('context_key')), time_stage=row['stage'])


def time_class(effect, supported):
    if not supported or not np.isfinite(effect) or effect == 0:
        return 'unclassified'
    return 'faster' if effect < 0 else 'slower'


def fit_training_effects(data, heldout=None):
    train = informative(data[data.building_id.ne(heldout)].copy())
    if train.empty:
        return pd.DataFrame(columns=['worker_id', 'effect', 'supported', 'fit_status',
            'contexts', 'buildings', 'training_buildings'])
    stat = sufficient(train)
    effects, status, _ = solve(stat, np.ones(len(stat['buildings'])))
    rows = []
    for j, worker in enumerate(stat['workers']):
        part = train[train.worker_id.eq(worker)]
        n, b = part.context_key.nunique(), part.building_id.nunique()
        rows.append(dict(worker_id=worker, effect=effects[j] if effects is not None else np.nan,
            supported=bool(status == 'usable' and n >= 6 and b >= 3), fit_status=status,
            contexts=n, buildings=b, training_buildings=sorted(part.building_id.unique())))
    return pd.DataFrame(rows)


def metric_cells(records, metrics=METRICS):
    rows = []
    for r in records:
        for axis in metrics:
            value = r['metrics'].get(axis)
            if value is None:
                continue
            if not np.isfinite(value):
                raise ValueError('nonfinite metric: '+r['record_id'])
            rows.append(dict(record_id=r['record_id'], worker_id=r['worker_id'],
                image_id=r['image_id'], building_id=r['building_id'],
                reference_object_id=r['reference_object_id'],
                context_key=json.dumps([r['image_id'], r['reference_object_id']], ensure_ascii=False),
                axis=axis, value=float(value)))
    frame = pd.DataFrame(rows)
    if frame.duplicated(['context_key', 'worker_id', 'axis']).any():
        raise ValueError('duplicate worker/reference cell')
    grouped = frame.groupby(['context_key', 'axis']).value
    frame['peer_n'] = grouped.transform('size')
    frame['centered_value'] = frame.value - grouped.transform('mean')
    return frame


def source_inventory(objects, admission):
    manual = pd.read_csv(HISTORY / 'manual_with_time.csv.gz', keep_default_na=False,
        dtype={'worker_id': str, 'worker_id_timing': str, 'project_id': str, 'runtime_task_id': str})
    semi = pd.read_csv(HISTORY / 'semi.csv.gz', keep_default_na=False,
        dtype={'worker_id': str, 'worker_id_timing': str, 'project_id': str, 'runtime_task_id': str})
    historical = manual.to_dict('records') + semi.to_dict('records')
    time_by_key = {(r['project_id'], r['runtime_task_id'], historical_worker(r['worker_id'])): r for r in historical}
    if len(time_by_key) != len(historical):
        raise ValueError('duplicate historical task/person timing key')
    scope = pd.read_csv(HISTORY / 'scope_responses.csv', keep_default_na=False, dtype={'worker_id': str})
    scope_by_id = {r['canonical_annotation_id']: r for r in scope.to_dict('records')}
    scope_by_source = {(int(re.search(r'project-(\d+)-', r['raw_export']).group(1)), int(r['raw_annotation_id'])): r
                       for r in scope.to_dict('records')}
    if len(scope_by_id) != len(scope) or len(scope_by_source) != len(scope):
        raise ValueError('duplicate historical scope ID')
    seen, output = set(), []
    for gate in admission:
        obj = objects[gate['object_id']]
        if (obj['worker_id'], obj['image_id'], obj['condition']) != (gate['worker_id'], gate['image_id'], gate['condition']):
            raise ValueError('current admission identity drift: '+gate['record_id'])
        source = obj['source']
        key = str(source['project']), str(source['task']), obj['worker_id']
        old = time_by_key.get(key)
        timing = bind_time(obj, old)
        s = scope_by_id.get(timing.get('historical_canonical_id'))
        scope_binding = 'canonical_via_timing' if s else 'unbound'
        direct = scope_by_source.get((int(source['project']), int(source['annotation'])))
        if s and direct and s['canonical_annotation_id'] != direct['canonical_annotation_id']:
            raise ValueError('scope source and canonical disagree')
        if s is None and direct:
            s, scope_binding = direct, 'source_project_and_annotation'
        if s and (s['image_id'], historical_worker(s['worker_id'])) != (obj['image_id'], obj['worker_id']):
            raise ValueError('historical scope identity mismatch')
        eligible = (gate['condition'] == 'manual' and gate['role'] == 'manual_development_candidate'
                    and not gate['original_holdout'] and obj['independent_vote_eligible'])
        if eligible and timing['time_usable']:
            if key in seen:
                raise ValueError('duplicate training task/person source')
            seen.add(key)
        output.append(dict(record_id=gate['record_id'], object_id=gate['object_id'],
            image_id=gate['image_id'], image_code=gate['image_code'], building_id=obj['building_id'],
            worker_id=gate['worker_id'], condition=gate['condition'], source_cohort=gate['source_cohort'],
            current_role=gate['role'], original_holdout=gate['original_holdout'],
            independent_vote_eligible=obj['independent_vote_eligible'],
            personnel_barriers='|'.join(gate['personnel_barriers']),
            context_barriers='|'.join(gate['context_barriers']),
            project_id=source['project'], runtime_task_id=source['task'], raw_annotation_id=source['annotation'],
            source_path=source['path'], **timing, time_training_eligible=bool(eligible and timing['time_usable']),
            scope_historical_bound=s is not None,
            scope_binding=scope_binding,
            scope_historical_final=s['final_scope'] if s else '', scope_historical_answer=s['worker_scope'] if s else '',
            scope_historical_later_hold=s['later_hold'] if s else '',
            semi_historical_edit=old['edit_ospa30'] if old and 'edit_ospa30' in old else None,
            semi_historical_gain=old['gain_ospa30'] if old and 'gain_ospa30' in old else None,
            semi_initialization_evidence=old['initialization_evidence_status'] if old and 'initialization_evidence_status' in old else '',
            current_scene=json.dumps(gate['current_scene_review'], ensure_ascii=False)))
    return pd.DataFrame(output), dict(historical_timing_records=len(historical),
        bound_timing_records=sum(r['time_binding'].startswith('project') for r in output),
        historical_scope_records=len(scope), scope_bound_current=sum(r['scope_historical_bound'] for r in output),
        scope_binding_counts=dict(Counter(r['scope_binding'] for r in output)),
        scope_binding_limit='Historical adjudications are not recertified current labels; any unmatched records remain in source.')


def time_analysis(data, all_workers):
    buildings = sorted(data.building_id.unique())
    assignments, predictions, coverage = [], [], []
    for target in [None] + buildings:
        profile = fit_training_effects(data, target)
        profile['label'] = [time_class(r.effect, r.supported) for r in profile.itertuples()]
        profile['fold'] = target if target is not None else 'full_descriptive'
        for worker in set(all_workers)-set(profile.worker_id):
            profile.loc[len(profile)] = dict(worker_id=worker, effect=np.nan, supported=False,
                fit_status='no_informative_training', contexts=0, buildings=0, training_buildings=[],
                label='unclassified', fold=profile['fold'].iloc[0] if len(profile) else target)
        assignments.extend(profile.to_dict('records'))
        if target is None:
            continue
        p = profile[profile.label.ne('unclassified')].copy()
        p['class_effect'] = p.groupby('label').effect.transform('mean')
        test = data[data.building_id.eq(target)].merge(p[['worker_id', 'effect', 'class_effect', 'label']], on='worker_id')
        test = informative(test)
        coverage.append(dict(building_id=target, target_rows=int(data.building_id.eq(target).sum()),
            evaluated_rows=len(test), evaluated_workers=test.worker_id.nunique(), evaluated_contexts=test.context_key.nunique()))
        if test.empty:
            continue
        test['target'] = test.value - test.groupby('context_key').value.transform('mean')
        test['continuous_prediction'] = test.effect - test.groupby('context_key').effect.transform('mean')
        test['class_prediction'] = test.class_effect - test.groupby('context_key').class_effect.transform('mean')
        test['baseline_sqerr'] = test.target**2
        for name in ['continuous', 'class']:
            test[name+'_sqerr'] = (test.target-test[name+'_prediction'])**2
        predictions.extend(test[['record_id', 'worker_id', 'building_id', 'context_key', 'value',
            'effect', 'label', 'class_effect', 'target', 'continuous_prediction', 'class_prediction',
            'baseline_sqerr', 'continuous_sqerr', 'class_sqerr']].to_dict('records'))
    predictions = pd.DataFrame(predictions)
    by_building = predictions.groupby('building_id')[['baseline_sqerr', 'continuous_sqerr', 'class_sqerr']].mean().reset_index()
    summaries = {}
    for name in ['continuous', 'class']:
        by_building[name+'_improvement'] = 1-by_building[name+'_sqerr']/by_building.baseline_sqerr
        summaries[name] = dict(pooled_sse_reduction=float(1-predictions[name+'_sqerr'].sum()/predictions.baseline_sqerr.sum()),
            building_equal_mse_reduction=float(1-by_building[name+'_sqerr'].mean()/by_building.baseline_sqerr.mean()),
            improved_buildings=int((by_building[name+'_sqerr'] < by_building.baseline_sqerr).sum()))
    return pd.DataFrame(assignments), predictions, by_building, pd.DataFrame(coverage), summaries


def half_stability(data, all_workers):
    buildings = sorted(data.building_id.unique())
    rng = np.random.default_rng(20261014)
    rows = []
    for repeat in range(50):
        shuffled = rng.permutation(buildings)
        halves = [set(shuffled[:len(buildings)//2]), set(shuffled[len(buildings)//2:])]
        p = []
        for side, bs in enumerate(halves):
            profile = fit_training_effects(data[data.building_id.isin(bs)])
            profile['label'] = [time_class(r.effect, r.supported) for r in profile.itertuples()]
            p.append(profile.set_index('worker_id'))
        for worker in all_workers:
            labels = [x.loc[worker, 'label'] if worker in x.index else 'unclassified' for x in p]
            rows.append(dict(repeat=repeat, worker_id=worker, half_a='|'.join(sorted(halves[0])),
                half_b='|'.join(sorted(halves[1])), label_a=labels[0], label_b=labels[1],
                comparable='unclassified' not in labels,
                same_direction=labels[0] == labels[1] if 'unclassified' not in labels else None))
    return pd.DataFrame(rows)


def common10_probe(objects, admission, assignments):
    old = read('analysis_results/worker_profiles_20261003/input.json')
    measured = pd.read_csv(ROOT / 'analysis_results/worker_profiles_20261003/answer_metrics.csv')
    ids = set(measured[measured.version.eq('original')].record_id)
    gate = {r['record_id']: r for r in admission}
    binding, aliases, image_buildings = [], {}, {}
    for im in old['images']:
        image_buildings[im['code']] = im['building']
        for row in im['annotations']:
            if row['id'] not in ids:
                continue
            g = gate[row['id']]; obj = objects[g['object_id']]
            previous = aliases.setdefault(row['worker'], obj['worker_id'])
            if previous != obj['worker_id'] or im['code'] != obj['image_code']:
                raise ValueError('historical P/W alias mismatch')
            current = [obj['preprocessed_points'][i] for i in row['source_point_indices']]
            binding.append(dict(record_id=row['id'], object_id=obj['object_id'], worker_alias=row['worker'],
                worker_id=obj['worker_id'], image=im['code'], building_id=im['building'],
                coordinates_match=bool(np.array_equal(current, row['points'])),
                ring_index_match=row['source_point_indices'] == obj['ordered_source_point_indices'],
                current_role=g['role'], original_holdout=g['original_holdout']))
    if len(binding) != 240 or set(r['record_id'] for r in binding) != ids:
        raise ValueError('common10 coverage drift')
    distances = pd.read_csv(ROOT / 'analysis_results/consensus_response_20261006/pairwise_distances.csv')
    result = []
    for image, building in image_buildings.items():
        labels = assignments[assignments.fold.eq(building)].set_index('worker_id').label.to_dict()
        d = distances[distances.image.eq(image) & distances.condition.eq('manual')].copy()
        d['class_a'] = [labels.get(aliases[w], 'unclassified') for w in d.worker_a]
        d['class_b'] = [labels.get(aliases[w], 'unclassified') for w in d.worker_b]
        d['pair_class'] = ['+'.join(sorted([a, b])) for a, b in zip(d.class_a, d.class_b)]
        for name, group in d.groupby('pair_class'):
            result.append(dict(image=image, building_id=building, pair_class=name, pair_n=len(group),
                distance_union_mean=float(group.distance_union.mean()),
                source_pool_n=24, label_source='target_building_excluded_T',
                all_pairs_baseline=float(d.distance_union.mean()),
                classified_workers=sum(labels.get(w, 'unclassified') != 'unclassified' for w in aliases.values())))
    contrasts = pd.read_csv(ROOT / 'analysis_results/consensus_response_20261006/composition/contrasts.csv')
    selected = contrasts[contrasts.image.isin(image_buildings) & contrasts.policy.eq('original')
        & contrasts.version.eq('original') & contrasts.method.eq('mv50') & contrasts.k.eq(8)]
    if len(selected) != 10:
        raise ValueError('historical composition contrast coverage changed')
    counts = {name: int((selected[field] < 0).sum()) for name, field in [
        ('raw_disagreement_lower', 'higher_minus_lower_raw_pairwise_union'),
        ('reference_difference_lower', 'higher_minus_lower_ref_symdiff_ref'),
        ('fusion_member_difference_lower', 'higher_minus_lower_member_symdiff_union')]}
    return pd.DataFrame(binding), pd.DataFrame(result), dict(images=10, k=8, method='mv50',
        calibration='historical_original_GT_IoU_upper_lower_half', reference='original', **counts)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    bundle = load_current_bundle()
    objects = {o['object_id']: o for o in bundle['data']['objects']}
    admission = read('research/quality_data_admission_audit_20261013/FULL_ADMISSION.json')['records']
    inventory, binding_summary = source_inventory(objects, admission)
    csv('source_inventory.csv', inventory)
    selected = inventory[inventory.time_training_eligible].copy()
    times = selected.rename(columns={'time_value': 'value', 'time_context': 'context_key'})
    roster = sorted(inventory[inventory.current_role.eq('manual_development_candidate')].worker_id.unique())
    assignments, predictions, by_building, evaluation_coverage, performance = time_analysis(times, roster)
    csv('time_assignments.csv', assignments)
    csv('time_predictions.csv', predictions)
    csv('time_building_results.csv', by_building)
    csv('time_evaluation_coverage.csv', evaluation_coverage)
    halves = half_stability(times, roster)
    csv('time_disjoint_halves.csv', halves)
    stable = halves.groupby('worker_id').agg(comparable_halves=('comparable', 'sum'),
        same_direction_fraction=('same_direction', 'mean')).reset_index()
    full = assignments[assignments.fold.eq('full_descriptive')].merge(stable, on='worker_id')
    changes = assignments[assignments.fold.ne('full_descriptive')].groupby('worker_id').label.agg(
        lambda x: json.dumps(x.value_counts().to_dict(), sort_keys=True))
    full['leave_building_labels'] = full.worker_id.map(changes)
    csv('time_profiles.csv', full)

    expanded_source = read('research/quality_candidate_disagreement_20261013/RESULTS.json')['records']
    gates = {r['record_id']: r for r in admission}
    expanded = []; expanded_inventory = []
    for row in expanded_source:
        g = gates[row['record_id']]
        if (row['object_id'], row['worker_id'], row['image_id']) != (g['object_id'], g['worker_id'], g['image_id']):
            raise ValueError('expanded metric source mismatch')
        allowed = g['role'] == 'manual_development_candidate' and not g['original_holdout']
        expanded_inventory.append({k: row[k] for k in ['record_id', 'object_id', 'worker_id', 'image_id',
            'building_id', 'image_code', 'reference_object_id', 'reference_basis', 'score_kind', 'selected_candidate_id']}
            | dict(current_role=g['role'], allowed_current_conditional=allowed,
                   reference_scope_note=json.dumps(row['existing_context'], ensure_ascii=False)))
        if allowed:
            if not objects[row['object_id']]['independent_vote_eligible']:
                raise ValueError('expanded condition view contains nonindependent source')
            required = METRICS if row['score_kind'] == 'full' else METRICS[:3]
            if any(row['metrics'].get(k) is None for k in required):
                raise ValueError('expanded required metric missing: '+row['record_id'])
            expanded.append(row)
    csv('expanded_metric_inventory.csv', pd.DataFrame(expanded_inventory))
    cells = metric_cells(expanded)
    csv('metric_cells.csv', cells)
    profiles = []
    for axis, group in cells.groupby('axis'):
        p = fit_training_effects(group)
        p['axis'] = axis
        p = p.merge(group.groupby('worker_id').agg(raw_mean=('value', 'mean'),
            records=('record_id', 'size')), on='worker_id')
        p = p.merge(group[group.peer_n.ge(2)].groupby('worker_id').agg(
            peer_centered_mean=('centered_value', 'mean')), on='worker_id', how='left')
        profiles.extend(p.to_dict('records'))
    csv('metric_profiles.csv', pd.DataFrame(profiles))
    coverage = inventory.groupby(['worker_id', 'condition']).agg(records=('record_id', 'size'),
        images=('image_id', 'nunique'), buildings=('building_id', 'nunique'),
        time_bound=('historical_canonical_id', 'count'), time_usable=('time_usable', 'sum'),
        time_training_rows=('time_training_eligible', 'sum'), scope_historical_bound=('scope_historical_bound', 'sum')).reset_index()
    csv('worker_coverage.csv', coverage)
    panel = pd.DataFrame(expanded_inventory)
    panel['reference_cell'] = list(zip(panel.image_id, panel.reference_object_id))
    pair_rows, panel_summaries = [], []
    for kind, part in [('all_floor_available', panel), ('full', panel[panel.score_kind.eq('full')])]:
        sets = {w: set(g.reference_cell) for w, g in part.groupby('worker_id')}
        for a, b in combinations(sorted(sets), 2):
            shared = sets[a] & sets[b]
            pair_rows.append(dict(panel=kind, worker_a=a, worker_b=b, shared_reference_cells=len(shared)))
        panel_summaries.append(dict(panel=kind, records=len(part), workers=len(sets), images=part.image_id.nunique(),
            reference_cells=part.reference_cell.nunique(), common_all_workers=len(set.intersection(*sets.values())),
            pair_shared_min=min(len(a & b) for a,b in combinations(sets.values(),2)),
            pair_shared_median=float(np.median([len(a & b) for a,b in combinations(sets.values(),2)]))))
    csv('expanded_pair_coverage.csv', pd.DataFrame(pair_rows))
    common, pair_probe, old_counts = common10_probe(objects, admission, assignments)
    csv('common10_current_binding.csv', common)
    csv('time_common10_pair_probe.csv', pair_probe)
    write('historical_composition_recheck.json', old_counts)
    pairs = pair_probe.pivot(index='image', columns='pair_class', values='distance_union_mean')
    contrasts = pd.DataFrame(dict(image=pairs.index,
        fast_minus_slow=(pairs['faster+faster']-pairs['slower+slower']).values,
        cross_minus_fast=(pairs['faster+slower']-pairs['faster+faster']).values,
        cross_minus_slow=(pairs['faster+slower']-pairs['slower+slower']).values))
    holds = common.groupby('image').original_holdout.any()
    contrasts['original_holdout'] = contrasts.image.map(holds)
    csv('time_common10_contrasts.csv', contrasts)
    pair_summary = []
    for name, group in [('historical10', contrasts), ('current_development8', contrasts[~contrasts.original_holdout])]:
        pair_summary.append(dict(panel=name, images=len(group),
            fast_pair_less_disagreement=int((group.fast_minus_slow < 0).sum()),
            fast_pair_more_disagreement=int((group.fast_minus_slow > 0).sum()),
            mean_fast_minus_slow=float(group.fast_minus_slow.mean()),
            cross_exceeds_both=int(((group.cross_minus_fast > 0) & (group.cross_minus_slow > 0)).sum())))
    by_repeat = halves[halves.comparable].groupby('repeat').same_direction.mean()
    summary = dict(schema='worker_classification_progress_20261014_v1', source_binding=binding_summary,
        current_conditions=inventory.condition.value_counts().to_dict(),
        current_roles=inventory.current_role.value_counts().to_dict(), expanded_panels=panel_summaries,
        time_training=dict(records=len(times), workers=times.worker_id.nunique(), images=times.image_id.nunique(),
            contexts=times.context_key.nunique(), buildings=times.building_id.nunique(),
            informative_records=len(informative(times)), current_development_roster=len(roster),
            full_labels=full.label.value_counts().to_dict()),
        time_evaluation=dict(rows=len(predictions), workers=predictions.worker_id.nunique(),
            buildings=predictions.building_id.nunique(), performance=performance),
        time_disjoint_halves=dict(repeats=50, comparable_worker_halves=int(halves.comparable.sum()),
            median_direction_agreement=float(by_repeat.median()), min_direction_agreement=float(by_repeat.min()),
            max_direction_agreement=float(by_repeat.max()), not_independent_samples=True),
        common10_binding=dict(records=len(common), coordinate_match=int(common.coordinates_match.sum()),
            ring_index_match=int(common.ring_index_match.sum()), roles=common.current_role.value_counts().to_dict(),
            original_holdout=int(common.original_holdout.sum())), historical_composition=old_counts,
        time_pair_probe=pair_summary,
        main_Q_used=False, official_labels_changed=False,
        semi_sources=inventory[inventory.condition.eq('semi')].source_cohort.value_counts().to_dict())
    write('SUMMARY.json', summary)
    plot_evidence(full, by_building, contrasts)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def plot_evidence(profiles, buildings, contrasts):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']
    plt.rcParams['axes.unicode_minus'] = False
    fig, axes = plt.subplots(1, 3, figsize=(17, 8), gridspec_kw={'width_ratios': [1, 1.25, 1.2]})
    p = profiles.sort_values('worker_id')
    for y, row in enumerate(p.itertuples()):
        if not row.supported:
            axes[0].text(0, y, '未分类', va='center', fontsize=8, color='#777777')
        else:
            axes[0].scatter(row.effect, y, color='#2171b5' if row.label == 'faster' else '#d95f0e')
    axes[0].set_yticks(range(len(p)), p.worker_id)
    axes[0].invert_yaxis()
    axes[0].axvline(0, color='#aaaaaa', lw=1)
    axes[0].set(title='当前时间画像（按人员编号排列）', xlabel='同任务调整后的 log(1+秒) 相对效应')
    b = buildings.sort_values('building_id')
    y = np.arange(len(b))
    axes[1].barh(y-.17, b.baseline_sqerr-b.continuous_sqerr, height=.32, label='连续画像', color='#2171b5')
    axes[1].barh(y+.17, b.baseline_sqerr-b.class_sqerr, height=.32, label='快慢粗类', color='#d95f0e')
    axes[1].set_yticks(y, b.building_id)
    axes[1].invert_yaxis()
    axes[1].axvline(0, color='#aaaaaa', lw=1)
    axes[1].legend(frameon=False, fontsize=9)
    axes[1].set(title='留建筑预测相对时间', xlabel='基线MSE − 预测MSE（正值改善）')
    c = contrasts.sort_values('image')
    axes[2].barh(range(len(c)), c.fast_minus_slow, color=['#999999' if h else '#238b45' for h in c.original_holdout])
    axes[2].set_yticks(range(len(c)), [i+(' *' if h else '') for i,h in zip(c.image,c.original_holdout)])
    axes[2].invert_yaxis()
    axes[2].axvline(0, color='#aaaaaa', lw=1)
    axes[2].set(title='历史原作答分歧：快组减慢组', xlabel='两两区域差异 / 同图全员并集\n负值为快组更一致；*为原留出诊断')
    fig.suptitle('时间差异可复现，但不直接等于质量或融合稳定性', fontsize=15)
    fig.tight_layout(rect=[0, 0, 1, .96])
    fig.savefig(OUT/'time_evidence.png', dpi=150)
    plt.close(fig)


if __name__ == '__main__':
    main()
