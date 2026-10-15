"""同房平均质量、既有曲线覆盖及固定共同人员Lee曲线；不调参或推定同房。"""
import argparse
from collections import defaultdict
from itertools import combinations
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd
from shapely.geometry import Polygon

from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle
from .lee_tile_precision_20261003 import integration_basis, measure_masks, subset_mask
from .research_round_20260929 import prepare_record, reconstruct
from .same_room_similarity_20261003 import relation_index, correlation

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'research/same_room/same_room_quality_curves_20261015'
DIFF = ROOT/'research/difficulty/difficulty_target_integration_20261015'
QUALITY = ROOT/'research/quality/quality_joint_closeout_review_20261015'
POP = ROOT/'research/fusion/wall_consensus_population_20261014'
LEE = ROOT/'analysis_results/lee_expanded_20261003'
REGISTRY = ROOT/'analysis_results/research_input_20260929/final_review/同房分类_原始完整记录.json'
METRICS = ['WQ', 'IoU3D100', 'iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter']


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(out, name, value):
    if isinstance(value, pd.DataFrame):
        value.to_csv(out/name, index=False, encoding='utf-8-sig')
    else:
        (out/name).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                       allow_nan=False)+'\n', encoding='utf-8')


def common_profile(a, b, metric):
    joint = a.set_index('worker_id')[[metric]].join(
        b.set_index('worker_id')[[metric]], how='inner', lsuffix='_a', rsuffix='_b').sort_index()
    observed = joint.dropna()
    x, y = observed[metric+'_a'], observed[metric+'_b']
    return dict(workers=list(joint.index), n_common=len(joint), n_evaluable=len(observed),
                mean_a=float(x.mean()) if len(x) else None,
                mean_b=float(y.mean()) if len(y) else None,
                absolute_gap=float(abs(x.mean()-y.mean())) if len(x) else None,
                worker_spearman=correlation(x, y))


def curve_distance(a, b):
    """相同实际人数的标量曲线；缺失和起点都不补造。"""
    joined = pd.concat([a.rename('a'), b.rename('b')], axis=1, join='inner').sort_index()
    valid = joined.dropna()
    anchored = 1 in valid.index
    return dict(planned_k=len(joined), evaluated_k=len(valid),
        first_evaluated_k=int(valid.index.min()) if len(valid) else None,
        last_evaluated_k=int(valid.index.max()) if len(valid) else None,
        level_mae=float(abs(valid.a-valid.b).mean()) if len(valid) else None,
        gain_mae=float(abs((valid.a-valid.loc[1, 'a'])-(valid.b-valid.loc[1, 'b'])).mean())
                 if anchored else None,
        spearman=correlation(valid.a.to_numpy(), valid.b.to_numpy()))


def information_block(image, relations):
    # 连通块仅作防泄漏屏障，不据此增加任何已确认同房图对。
    graph = defaultdict(set)
    for a, b in relations:
        graph[a].add(b)
        graph[b].add(a)
    reached, todo = {image}, [image]
    while todo:
        for other in graph[todo.pop()]-reached:
            reached.add(other)
            todo.append(other)
    return reached


def control_sources(target, source, workers, images, people, relations, *, external=False):
    forbidden = information_block(target, relations) | information_block(source, relations)
    building, grade = images[target][0], images[source][1]
    return sorted(i for i, (b, d) in images.items() if i not in forbidden
                  and (b != building if external else b == building)
                  and d == grade and set(workers).issubset(people[i]))


def exact_curve(records, references):
    # shortcut: 本轮共同池最多9人；更大池需先另定计算精度，不静默改为抽样。
    if len(records) > 9:
        raise ValueError('exact common-worker design requires at most nine people')
    basis = integration_basis(records, references)
    rows = []
    for k in range(1, len(records)+1):
        masks = np.array([subset_mask(c) for c in combinations(range(len(records)), k)], dtype=np.uint32)
        measured = measure_masks(basis, masks, k, 'mv50')
        nonempty = []
        for mask in masks:
            votes = basis['mesh']['votes'][[i for i in range(len(records)) if int(mask) & (1 << i)]].sum(axis=0)
            nonempty.append(bool(np.any(2*votes >= k)))
        for version, values in measured.items():
            rows.append(dict(k=k, reference_version=version, subsets=len(masks),
                evaluable_subsets=int(np.isfinite(values).sum()), nonempty_fraction=float(np.mean(nonempty)),
                iou_mean=float(np.mean(values)), iou_sd=float(np.std(values))))
    return rows


def control_curve_distance(target, controls):
    """每次一张对照源图的平均误差，与多源均值预测分开。"""
    single = [curve_distance(target, c) for c in controls]
    ensemble = curve_distance(target, pd.concat(controls, axis=1).mean(axis=1))
    result = {'ensemble_'+k: v for k, v in ensemble.items()}
    for key in ('level_mae', 'gain_mae'):
        values = [r[key] for r in single]
        result[key] = float(np.mean(values)) if all(v is not None for v in values) else None
    return result


def quality_pairs(frame, images, relations, layer):
    groups = {i: g for i, g in frame.groupby('image_id')}
    rows = []
    for a, b in combinations(sorted(groups), 2):
        if images[a]['building_id'] != images[b]['building_id']:
            continue
        ga, gb = groups[a], groups[b]
        r = relations.get((a, b), dict(tier='same_building_no_room_evidence', candidates=[]))
        for metric in METRICS:
            profile = common_profile(ga, gb, metric)
            workers = profile.pop('workers')
            rows.append(dict(layer=layer, image_a=a, image_b=b,
                code_a=images[a]['image_code'], code_b=images[b]['image_code'],
                building=images[a]['building_id'], relation=r['tier'],
                candidate_ids='|'.join(r['candidates']), metric=metric,
                reference_ids_a='|'.join(sorted(ga.reference_id.unique())),
                reference_ids_b='|'.join(sorted(gb.reference_id.unique())),
                multiple_references_a=ga.reference_id.nunique()>1,
                multiple_references_b=gb.reference_id.nunique()>1,
                workers='|'.join(workers), **profile))
    return pd.DataFrame(rows)


def main(out=OUT):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    bundle = load_current_bundle()
    with zipfile.ZipFile(QUALITY/'pro_closeout_delta.zip') as archive:
        if bundle['data'] != json.loads(archive.read('source/historical_current_formal_loader_data.json')):
            raise ValueError('current source differs from fixed quality geometry snapshot')
    registry = read(REGISTRY)
    if registry != bundle['data']['room_registry']:
        raise ValueError('room evidence differs from current loader')
    relations = relation_index(registry['candidates'])
    images = {i['image_id']: i for i in bundle['data']['images']}
    objects = {o['object_id']: o for o in bundle['data']['objects']}
    projected, aliases = project_bundle(bundle)
    records = {r['id']: r for im in projected['images'] for r in im['annotations']+im['references']}
    quality = pd.read_csv(DIFF/'quality_bindings_1145.csv')
    joint = pd.read_csv(QUALITY/'JOINT_COMPARISON_1145.csv')
    pd.testing.assert_frame_equal(quality[joint.columns], joint, check_dtype=False)
    assert quality.record_id.is_unique
    for r in quality.to_dict('records'):
        o = objects[r['object_id']]
        assert all(o[k] == r[k] for k in ('image_id', 'image_code', 'worker_id', 'condition'))
        assert aliases['records'][r['object_id']] == r['record_id']
    quality['score_version'] = 'WQ-LS08-20261014'
    save(out, 'quality_inventory_1145.csv', quality)
    primary = quality[quality.use_panel.eq('ordinary_same_target_conditional')].copy()
    assert not primary.duplicated(['image_id', 'worker_id']).any()
    assert primary.groupby('image_id').reference_id.nunique().eq(1).all()
    assert primary.condition.eq('manual').all() and primary.reference_id_equal.all()
    assert not primary.new_scope_binding_pending.any()
    assert all(objects[oid]['independent_vote_eligible'] for oid in primary.object_id)
    assert all(objects[oid]['main_consensus_gate']['status'] == 'main_candidate' for oid in primary.object_id)
    gp = {i: g for i, g in primary.groupby('image_id')}
    people = {i: set(g.worker_id) for i, g in gp.items()}
    metadata = {i: (g.building_id.iloc[0], g.difficulty_class.iloc[0]) for i, g in gp.items()}
    all_pairs = quality_pairs(primary, images, relations, 'ordinary_same_target_conditional')
    # 旧明确参考条件下的补充描述，新增范围未决及多参考混合不能进入主面板。
    old_conditional = pd.read_csv(ROOT/'research/workers/worker_wq_integration_20261015/quality_panel.csv')
    prior = quality.set_index('record_id').loc[old_conditional.record_id]
    assert list(prior.reference_id) == list(old_conditional.reference_id)
    assert np.allclose(prior[METRICS], old_conditional[METRICS], rtol=0, atol=1e-10)
    old_pairs = quality_pairs(old_conditional, images, relations, 'old_bound_reference_diagnostic')
    save(out, 'quality_pairs.csv', pd.concat([all_pairs, old_pairs], ignore_index=True))
    group_summary = []
    comparable = all_pairs[all_pairs.relation.eq('confirmed_comparable') & all_pairs.n_common.ge(4)]
    for (candidate, metric, building), g in comparable.groupby(['candidate_ids', 'metric', 'building']):
        group_summary.append(dict(candidate_id=candidate, metric=metric, building=building,
            pairs=len(g), images=len(set(g.image_a) | set(g.image_b)),
            common_n_min=int(g.n_common.min()), common_n_max=int(g.n_common.max()),
            mean_gap=float(g.absolute_gap.mean()), median_gap=float(g.absolute_gap.median()),
            minimum_gap=float(g.absolute_gap.min()), maximum_gap=float(g.absolute_gap.max())))
    save(out, 'quality_group_summary.csv', pd.DataFrame(group_summary))
    views = primary.groupby(['image_id', 'image_code', 'building_id', 'reference_id', 'difficulty_class'],
                            as_index=False).agg(n_workers=('worker_id', 'nunique'), **{m: (m, 'mean') for m in METRICS})
    save(out, 'image_mean_quality.csv', views)
    group_views = []
    for c in registry['candidates']:
        present = sorted(set(c['image_ids']) & set(gp))
        common = sorted(set.intersection(*(people[i] for i in present))) if present else []
        for i in present:
            subset = gp[i][gp[i].worker_id.isin(common)]
            group_views.append(dict(candidate_id=c['candidate_id'], image_id=i,
                image_code=images[i]['image_code'], physical_same_supported=c['physical_same_supported'],
                comparable_for_prediction=c['comparable_for_prediction'], common_workers='|'.join(common),
                n_views_observed=len(present), n_views_recorded=len(c['image_ids']), n_common=len(common),
                **{m: float(subset[m].mean()) if len(subset) else None for m in METRICS}))
    save(out, 'group_common_worker_views.csv', pd.DataFrame(group_views))
    existing = read(POP/'input_snapshot.json')['images']
    point_ids = {i['image_id'] for i in existing}
    old_rosters = {r['image']: r for r in read(LEE/'rosters.json')}
    coverage, evidence = [], []
    for (a, b), r in relations.items():
        ca, cb = images.get(a, {}).get('image_code'), images.get(b, {}).get('image_code')
        old_ready = ca in old_rosters and cb in old_rosters
        old_common = set(old_rosters[ca]['workers']) & set(old_rosters[cb]['workers']) if old_ready else set()
        coverage.append(dict(image_a=a, image_b=b, code_a=ca, code_b=cb, relation=r['tier'],
            candidate_ids='|'.join(r['candidates']), in_research_a=a in images, in_research_b=b in images,
            full_quality_rows_a=int(quality.image_id.eq(a).sum()), full_quality_rows_b=int(quality.image_id.eq(b).sum()),
            primary_n_a=len(people.get(a, [])), primary_n_b=len(people.get(b, [])),
            primary_n_common=len(people.get(a, set()) & people.get(b, set())),
            point_curve_a=a in point_ids, point_curve_b=b in point_ids,
            old_lee_both=old_ready, old_lee_n_common=len(old_common),
            overlapping_candidates=len(r['candidates'])>1))
        evidence.append(dict(image_a=a, image_b=b, **r))
    save(out, 'relation_curve_coverage.csv', pd.DataFrame(coverage))
    save(out, 'direct_relation_evidence.json', evidence)
    candidate_audit = []
    for c in registry['candidates']:
        ids = set(c['image_ids'])
        candidate_audit.append(dict(candidate_id=c['candidate_id'], building=c['building'],
            physical_same_supported=c['physical_same_supported'], comparable_for_prediction=c['comparable_for_prediction'],
            review_state=c['review_state'], oos_pending=c['oos_pending'], recorded_images=len(ids),
            primary_views=len(ids & set(gp)), full_quality_views=len(ids & set(quality.image_id)),
            point_curve_views=len(ids & point_ids), old_lee_views=sum(images.get(i, {}).get('image_code') in old_rosters for i in ids),
            source_group_codes='|'.join(c['source_group_codes']), issue_tags=json.dumps(c['issue_tags'], ensure_ascii=False)))
    save(out, 'candidate_coverage.csv', pd.DataFrame(candidate_audit))
    legacy = pd.read_csv(LEE/'image_curves.csv')
    legacy = legacy[legacy.method.eq('mv50')]
    legacy_rows = []
    for c in coverage:
        if not c['old_lee_both']:
            continue
        a, b = c['code_a'], c['code_b']
        for version in ('original', 'manual_revision'):
            sa, sb = [legacy[legacy.image.eq(code)&legacy.version.eq(version)].set_index('k').iou_mean for code in (a, b)]
            if len(sa) and len(sb):
                legacy_rows.append(dict(image_a=a, image_b=b, relation=c['relation'],
                    candidate_ids=c['candidate_ids'], common_workers=c['old_lee_n_common'], reference_version=version,
                    pool_n_a=len(old_rosters[a]['workers']), pool_n_b=len(old_rosters[b]['workers']),
                    worker_sets_identical=set(old_rosters[a]['workers'])==set(old_rosters[b]['workers']),
                    **curve_distance(sa, sb)))
    save(out, 'legacy_lee_pairs.csv', pd.DataFrame(legacy_rows))
    strict = all_pairs[all_pairs.metric.eq('WQ') & all_pairs.relation.eq('confirmed_comparable') & all_pairs.n_common.ge(4)]
    tasks, mean_rows, contexts = [], [], set()
    for pair in strict.to_dict('records'):
        a, b = pair['image_a'], pair['image_b']
        assert len(relations[(a, b)]['candidates']) == 1, 'overlapping evidence needs explicit reconciliation'
        workers = tuple(pair['workers'].split('|'))
        for target, source in ((a, b), (b, a)):
            controls = control_sources(target, source, workers, metadata, people, relations)
            external = control_sources(target, source, workers, metadata, people, relations, external=True)
            task = dict(task_id=f'T{len(tasks)+1:03d}', target=target, source=source,
                target_code=images[target]['image_code'], source_code=images[source]['image_code'],
                building=metadata[target][0], candidate_id=pair['candidate_ids'], workers=list(workers),
                n_common=len(workers), source_class=metadata[source][1], target_class=metadata[target][1],
                controls=controls, external_controls=external)
            tasks.append(task)
            for image in [target, source]+controls:
                contexts.add((image, workers))
            for metric in METRICS:
                def value(i):
                    return float(gp[i].set_index('worker_id').loc[list(workers), metric].mean())
                target_value, source_value = value(target), value(source)
                for kind, pool in [('same_building_same_source_class', controls), ('other_buildings_same_source_class', external)]:
                    baseline = float(np.mean([value(i) for i in pool])) if pool else None
                    errors = [abs(target_value-value(i)) for i in pool]
                    for policy in ('one_control_view_expected_error', 'all_control_views_mean'):
                        baseline_error = (float(np.mean(errors)) if policy == 'one_control_view_expected_error'
                                          else abs(target_value-baseline)) if pool else None
                        mean_rows.append(dict(task_id=task['task_id'], candidate_id=task['candidate_id'], building=task['building'],
                            target_code=task['target_code'], source_code=task['source_code'], workers='|'.join(workers),
                            metric=metric, n_common=len(workers), target_mean=target_value, source_prediction=source_value,
                            baseline_kind=kind, baseline_policy=policy, baseline_views=1 if policy.startswith('one_') else len(pool),
                            control_images=len(pool), baseline_prediction=baseline if policy == 'all_control_views_mean' else None,
                            same_room_error=abs(target_value-source_value), baseline_error=baseline_error,
                            gain=baseline_error-abs(target_value-source_value) if baseline_error is not None else None))
    save(out, 'transfer_tasks.json', tasks)
    means = pd.DataFrame(mean_rows)
    save(out, 'mean_quality_transfer.csv', means)
    frozen_inputs, curve_rows = [], []
    cached = {}
    for image, workers in sorted(contexts):
        g = gp[image].set_index('worker_id')
        chosen = []
        for worker in workers:
            r = prepare_record(records[g.loc[worker, 'record_id']])
            geometry = reconstruct(r)
            assert geometry['floor'] is not None, 'unavailable current worker floor'
            chosen.append(dict(id=r['id'], object_id=g.loc[worker, 'object_id'], worker=worker,
                points=r['points'], footprint=geometry['floor'].tolist(), ring_confirmed=r['ring_confirmed']))
        reference_id = g.reference_id.iloc[0]
        original = images[image]['references']['gt_original']
        refs, bindings = {}, {}
        for version, oid in [('bound', reference_id), ('original', original)]:
            geo = reconstruct(prepare_record(records[aliases['records'][oid]]))
            assert geo['floor'] is not None
            refs[version], bindings[version] = geo['floor'].tolist(), oid
        revision = images[image]['references'].get('gt_manual_revision')
        if revision:
            geo = reconstruct(prepare_record(records[aliases['records'][revision]]))
            if geo['floor'] is not None and Polygon(geo['floor']).is_valid:
                refs['manual_revision'], bindings['manual_revision'] = geo['floor'].tolist(), revision
        rows = exact_curve(chosen, refs)
        context_id = f'C{len(frozen_inputs)+1:03d}'
        cached[(image, workers)] = pd.DataFrame(rows)
        frozen_inputs.append(dict(context_id=context_id, image_id=image, image_code=images[image]['image_code'],
            workers=list(workers), records=chosen, reference_ids=bindings, reference_floors=refs))
        for r in rows:
            curve_rows.append(dict(context_id=context_id, image_id=image, image_code=images[image]['image_code'],
                workers='|'.join(workers), n=len(workers), reference_id=bindings[r['reference_version']], **r))
        if len(frozen_inputs) % 25 == 0:
            print('exact Lee contexts completed', len(frozen_inputs), '/', len(contexts), flush=True)
    save(out, 'current_common_worker_inputs.json', frozen_inputs)
    curves = pd.DataFrame(curve_rows)
    save(out, 'exact_lee_curves.csv', curves)
    single_errors = []
    for context in frozen_inputs:
        expected = primary[primary.image_id.eq(context['image_id']) & primary.worker_id.isin(context['workers'])].iou_2d.mean()
        actual = curves[curves.context_id.eq(context['context_id']) & curves.reference_version.eq('bound') & curves.k.eq(1)].iou_mean.item()
        single_errors.append(abs(actual-expected))
    assert max(single_errors) < 1e-10, 'current Lee single-person geometry differs from fixed quality floor IoU'
    comparisons, curves_k = [], []
    for task in tasks:
        workers = tuple(task['workers'])
        for version in ('bound', 'original', 'manual_revision'):
            def curve(i):
                d = cached[(i, workers)]
                return d[d.reference_version.eq(version)].set_index('k').iou_mean
            target, source = curve(task['target']), curve(task['source'])
            if target.empty or source.empty:
                continue
            direct = curve_distance(target, source)
            control_curves = [curve(i) for i in task['controls']]
            # 修订GT敏感性仅在全部既定对照也有该版时比较，避免静默更换对照池。
            ready = bool(control_curves) and all(not c.empty for c in control_curves)
            baseline = pd.concat(control_curves, axis=1).mean(axis=1) if ready else pd.Series(dtype=float)
            compare = control_curve_distance(target, control_curves) if ready else dict(level_mae=None, gain_mae=None)
            comparisons.append(dict(task_id=task['task_id'], candidate_id=task['candidate_id'], building=task['building'],
                target_code=task['target_code'], source_code=task['source_code'], n_common=len(workers),
                source_class=task['source_class'], target_class=task['target_class'], reference_version=version,
                control_images=len(control_curves), controls_available=ready,
                **{'same_room_'+k: v for k, v in direct.items()},
                **{'baseline_'+k: v for k, v in compare.items()}))
            for k in target.index.intersection(source.index):
                curves_k.append(dict(task_id=task['task_id'], candidate_id=task['candidate_id'],
                    target_code=task['target_code'], source_code=task['source_code'], reference_version=version,
                    k=int(k), target_iou=float(target[k]), source_iou=float(source[k]),
                    baseline_iou=float(baseline[k]) if ready else None,
                    absolute_gap=float(abs(target[k]-source[k])),
                    gain_gap=float(abs((target[k]-target[1])-(source[k]-source[1])))))
    comparisons = pd.DataFrame(comparisons)
    save(out, 'exact_lee_pair_comparisons.csv', comparisons)
    save(out, 'exact_lee_pairs_by_k.csv', pd.DataFrame(curves_k))
    summaries = []
    valid_means = means[means.control_images.gt(0)]
    for (kind, policy, metric, building), g in valid_means.groupby(['baseline_kind', 'baseline_policy', 'metric', 'building']):
        summaries.append(dict(kind='mean_quality', baseline_kind=kind, baseline_policy=policy, metric=metric, building=building,
            tasks=len(g), target_images=g.target_code.nunique(), source_mae=float(g.same_room_error.mean()),
            baseline_mae=float(g.baseline_error.mean()), gain=float(g.gain.mean())))
    for (version, building), g in comparisons[comparisons.controls_available].groupby(['reference_version', 'building']):
        for metric in ('level_mae', 'gain_mae'):
            summaries.append(dict(kind='exact_lee', baseline_kind='same_building_same_source_class',
                baseline_policy='one_control_view_expected_error', metric=metric, reference_version=version, building=building, tasks=len(g),
                target_images=g.target_code.nunique(), source_mae=float(g['same_room_'+metric].mean()),
                baseline_mae=float(g['baseline_'+metric].mean()),
                gain=float((g['baseline_'+metric]-g['same_room_'+metric]).mean())))
    by_building = pd.DataFrame(summaries).assign(aggregation='directed_task_equal')
    dimensions = ['kind', 'baseline_kind', 'baseline_policy', 'metric', 'reference_version', 'building']
    targets = []
    for keys, g in valid_means.groupby(['baseline_kind', 'baseline_policy', 'metric', 'building', 'target_code']):
        kind, policy, metric, building, target = keys
        targets.append(dict(kind='mean_quality', baseline_kind=kind, baseline_policy=policy,
            metric=metric, reference_version='full_quality_bound', building=building, target_code=target,
            tasks=len(g), source_mae=float(g.same_room_error.mean()),
            baseline_mae=float(g.baseline_error.mean()), gain=float(g.gain.mean())))
    for (version, building, target), g in comparisons[comparisons.controls_available].groupby(['reference_version', 'building', 'target_code']):
        for metric in ('level_mae', 'gain_mae'):
            targets.append(dict(kind='exact_lee', baseline_kind='same_building_same_source_class',
                baseline_policy='one_control_view_expected_error', metric=metric, reference_version=version,
                building=building, target_code=target, tasks=len(g),
                source_mae=float(g['same_room_'+metric].mean()), baseline_mae=float(g['baseline_'+metric].mean()),
                gain=float((g['baseline_'+metric]-g['same_room_'+metric]).mean())))
    target_frame = pd.DataFrame(targets)
    save(out, 'transfer_by_target.csv', target_frame)
    target_building = target_frame.groupby(dimensions, as_index=False).agg(
        tasks=('tasks', 'sum'), target_images=('target_code', 'nunique'),
        source_mae=('source_mae', 'mean'), baseline_mae=('baseline_mae', 'mean'), gain=('gain', 'mean'))
    by_building.reference_version = by_building.reference_version.fillna('full_quality_bound')
    save(out, 'by_building_transfer.csv', pd.concat([by_building, target_building.assign(aggregation='target_image_equal')], ignore_index=True))
    save(out, 'building_equal_transfer.csv', target_building.groupby(dimensions[:-1], as_index=False).agg(
        buildings=('building', 'nunique'), target_images=('target_images', 'sum'),
        source_mae=('source_mae', 'mean'), baseline_mae=('baseline_mae', 'mean'), gain=('gain', 'mean')))
    summary = dict(schema='same_room_quality_curves_v1', native_quality_snapshot_exact=True,
        loader_revisions={k: bundle['data'][k] for k in ('order_update_revision', 'quality_update_revision')},
        source_quality_rows=len(quality), primary_quality_rows=len(primary), primary_images=len(gp),
        primary_workers=primary.worker_id.nunique(), relation_candidates=len(registry['candidates']),
        direct_relations=len(relations), primary_same_room_pairs=len(strict),
        primary_same_room_buildings=strict.building.nunique(), primary_same_room_groups=sorted(strict.candidate_ids.unique()),
        current_point_curve_images=len(point_ids), direct_same_room_pairs_in_point_curves=sum(
            c['point_curve_a'] and c['point_curve_b'] and c['relation'] in ('confirmed_comparable', 'supported_other') for c in coverage),
        exact_lee_contexts=len(contexts), exact_lee_images=curves.image_id.nunique(),
        exact_lee_unique_context_subsets=sum(2**len(w)-1 for _, w in contexts),
        directed_tasks=len(tasks), tasks_with_matched_building_controls=sum(bool(t['controls']) for t in tasks),
        matched_control_buildings=sorted({t['building'] for t in tasks if t['controls']}),
        all_curve_subsets_evaluable=bool(curves.evaluable_subsets.eq(curves.subsets).all()),
        exact_lee_nonempty_fraction_min=float(curves.nonempty_fraction.min()),
        exact_single_person_quality_iou_max_error=float(max(single_errors)),
        inference='Descriptive finite data; no independent-room population CI, significance, causal effect or stopping count.',
        same_room_WQ_fusion_curves='not available; exact supplements are Lee bottom IoU only')
    save(out, 'SUMMARY.json', summary)
    save(out, 'FIELD_CONTRACT.json', dict(schema=summary['schema'],
        table_columns={p.name: list(pd.read_csv(p, nrows=0).columns) for p in sorted(out.glob('*.csv'))},
        quality='WQ-LS08-20261014, IoU3D100 and preserved components; primary exact bound target; no new eligibility.',
        relation='Direct original human records only. Connected blocks exclude controls, never certify new same-room edges.',
        missing='Blank is unobserved/not applicable; no imputation. Legacy curves retain their historical differing worker pools.',
        exact_lee='MV50 >=50%, all real subsets for each fixed 4-9-person pool; all k have fixed views/workers. Empty region has IoU 0, not a removed draw.',
        curve_distance='At identical observed k: level MAE; MAE after subtracting each k=1; Spearman undefined for flat curves.',
        baseline='Equal source budget: expected error of one control image, image-equal. Multi-image mean predictor separately labelled. Identical personnel, same source difficulty; target scores do not fit predictions. No relation is not confirmed different room.',
        dependence='Tasks share views/people/groups; enumerate precision is not independent statistical sample size.',
        references='bound/original/manual_revision scored separately in each camera frame; no alignment or score-max reference selection.'))
    plot(out, all_pairs, comparisons, pd.DataFrame(curves_k))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def plot(out, pairs, comparisons, curves):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'DejaVu Sans']
    selected = pairs[pairs.relation.eq('confirmed_comparable') & pairs.n_common.ge(4)]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
    for ax, metric in zip(axes, ('WQ', 'IoU3D100')):
        for building, g in selected[selected.metric.eq(metric)].groupby('building'):
            ax.scatter(g.mean_a, g.mean_b, label=building[:3], alpha=.8)
        ax.plot([0, 100], [0, 100], color='gray', linewidth=1)
        ax.set(xlabel='视角A：共同人员均值', ylabel='视角B：共同人员均值', title=metric, xlim=(0, 100), ylim=(0, 100))
        ax.legend()
    fig.suptitle('主面板23个直接同房图对；图对非独立样本')
    fig.savefig(out/'mean_quality_pairs.png', dpi=150)
    plt.close(fig)
    direct = comparisons[comparisons.reference_version.eq('bound')].drop_duplicates(['candidate_id', 'n_common', 'target_code', 'source_code'])
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
    for candidate, group in direct.groupby('candidate_id'):
        axes[0].scatter(group.same_room_level_mae, group.same_room_gain_mae, label=candidate)
    axes[0].set(xlabel='绝对水平平均差（IoU）', ylabel='减去各自k=1后的增益差', title='相似水平与相似形状分别衡量')
    axes[0].legend()
    matched = direct[direct.controls_available]
    axes[1].scatter(matched.baseline_level_mae, matched.same_room_level_mae, label='同人员、同源图粗类对照')
    limit = max(matched.baseline_level_mae.max(), matched.same_room_level_mae.max())*1.1
    axes[1].plot([0, limit], [0, limit], color='gray')
    axes[1].set(xlim=(0, limit), ylim=(0, limit), xlabel='单张同建筑对照源曲线的平均误差',
                ylabel='同房源曲线误差', title='uNb：相同单张源图预算；线下同房较近')
    fig.savefig(out/'curve_comparison.png', dpi=150)
    plt.close(fig)
    bound = curves[curves.reference_version.eq('bound')]
    tasks = read(out/'transfer_tasks.json')
    unique = []
    seen = set()
    for t in tasks:
        key = tuple(sorted([t['target_code'], t['source_code']]))
        if key not in seen:
            unique.append(t)
            seen.add(key)
    fig, axes = plt.subplots(6, 4, figsize=(15, 17), layout='constrained')
    for ax, t in zip(axes.flat, unique):
        g = bound[bound.task_id.eq(t['task_id'])]
        for field, label in [('target_iou', t['target_code'].split('-')[-1]),
                             ('source_iou', t['source_code'].split('-')[-1]), ('baseline_iou', '多张对照均值（辅助）')]:
            ax.plot(g.k, g[field], marker='o', markersize=2, label=label)
        ax.set(title=f"{t['candidate_id']}  {t['target_code'].split('-')[-1]}/{t['source_code'].split('-')[-1]}  N={t['n_common']}",
               ylim=(0, 1), xlabel='人数k', ylabel='底面IoU')
        ax.legend(fontsize=7)
    for ax in list(axes.flat)[len(unique):]:
        ax.set_visible(False)
    fig.suptitle('全部23对：固定共同人员、固定参考；精确枚举，不是墙线WQ曲线')
    fig.savefig(out/'all_same_room_lee_curves.png', dpi=130)
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    main(parser.parse_args().out)
