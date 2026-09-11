"""uNb历史留一图预测核查；复用已审计曲线，不重分簇或调整正式协议。"""
import argparse
import json
import random
from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from tools.thesis_main.analysis.transfer_multibuilding_stability_20260909 import interval_error, onset

ROOT = Path(__file__).resolve().parents[3]
REVISED = ROOT / 'analysis_results/multibuilding_threshold_stability_20260909_v1/revised'
OUT = ROOT / 'analysis_results/unb_prediction_check_20260909_v1'
BUILDING = 'uNb9QFRL6hY'
MODES = ('with_workers', 'without_workers')
CONFIGS = ('q_0.950', 'ospa30_t6')


def source_prediction(vectors, source_ids):
    if not source_ids or len(set(source_ids)) != len(source_ids):
        raise ValueError('source_identity_empty_or_duplicate')
    curves = np.stack([vectors[key] for key in source_ids])
    counts = [onset(curve[:, 0], curve[:, 1])[2] for curve in curves]
    finite = [value for value in counts if value is not None]
    count, low, high = (float(np.median(finite)), float(min(finite)), float(max(finite))) if finite else (np.nan,) * 3
    return curves.mean(axis=0), count, low, high, len(finite)


def paired_gain_bounds(same, outside, target):
    """楼外绝对误差减同楼误差；每节点共享同一未知目标，正值利于同楼。"""
    same, outside, target = np.broadcast_arrays(same, outside, target)
    for value in (same, outside, target):
        if (value.shape[-1] != 2 or not np.isfinite(value).all()
                or (value[..., 0] > value[..., 1]).any() or (value < 0).any() or (value > 1).any()):
            raise ValueError('invalid_interval')
    points = np.stack([target[..., 0], target[..., 1], same[..., 0], same[..., 1],
                       outside[..., 0], outside[..., 1], same.mean(axis=-1), outside.mean(axis=-1)], axis=-1)
    points = np.clip(points, target[..., 0, None], target[..., 1, None])
    def distances(interval):
        lo, hi = interval[..., 0, None], interval[..., 1, None]
        return np.maximum(0, np.maximum(lo - points, points - hi)), np.maximum(abs(lo - points), abs(hi - points))
    sl, su = distances(same)
    ol, ou = distances(outside)
    return (ol - su).min(axis=-1), (ou - sl).max(axis=-1)


def checked_vectors(frame, images, nodes):
    selected = frame[frame.image_id.isin(images) & frame.k.le(nodes)].copy()
    vectors = {}
    for image in images:
        group = selected[selected.image_id.eq(image)].sort_values('k')
        if group.k.tolist() != list(range(1, nodes + 1)):
            raise ValueError(f'missing_or_duplicate_nodes:{image}')
        counts = group[['stable', 'changing', 'unknown']].to_numpy()
        if (not np.isfinite(counts).all() or (counts < 0).any()
                or not np.equal(counts, np.floor(counts)).all()
                or not (group.replicates == 200).all() or not (counts.sum(axis=1) == 200).all()):
            raise ValueError('invalid_state_counts')
        values = group[['stable_lower', 'stable_upper']].to_numpy()
        expected = np.column_stack([counts[:, 0] / 200, (counts[:, 0] + counts[:, 2]) / 200])
        if not np.allclose(values, expected, atol=1e-12, rtol=0):
            raise ValueError('state_rate_mismatch')
        vectors[image] = values
    return vectors


def balanced_source(source, images, dt_bins, counts):
    """仅按标注前特征段与响应数量配平，完全不读取稳定标签。"""
    for strata in (dt_bins, counts):
        for value in set(strata.values()):
            total = sum(strata[key] == value for key in images)
            observed = sum(strata[key] == value for key in source)
            expected = len(source) * total / len(images)
            if not np.floor(expected) <= observed <= np.ceil(expected):
                return False
    return True


def feature_matched_sources(source, pool, dt):
    """标量特征的最小总绝对差匹配，楼外每图至多使用一次。"""
    if not source or len(pool) < len(source) or set(source) & set(pool):
        raise ValueError('invalid_matching_identity')
    a,b = sorted(source,key=lambda x:(dt[x],x)),sorted(pool,key=lambda x:(dt[x],x))
    if not np.isfinite([dt[key] for key in a+b]).all():
        raise ValueError('invalid_matching_feature')
    costs = np.full((len(a)+1,len(b)+1),np.inf)
    take = np.zeros_like(costs,dtype=bool)
    costs[0,:] = 0
    for i in range(1,len(a)+1):
        for j in range(1,len(b)+1):
            candidate = costs[i-1,j-1] + abs(dt[a[i-1]]-dt[b[j-1]])
            take[i,j] = candidate <= costs[i,j-1]
            costs[i,j] = min(candidate,costs[i,j-1])
    i,j,mapping = len(a),len(b),{}
    while i:
        if take[i,j]:
            mapping[a[i-1]] = b[j-1]
            i -= 1
        j -= 1
    return [mapping[key] for key in source]


def known_state_probability(states, ids):
    known=[states[key] for key in ids if np.isfinite(states[key])]
    if any(value not in (0.,1.) for value in known):
        raise ValueError('invalid_binary_state')
    return (float(np.mean(known)) if known else np.nan),len(known)


def run(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    plan = dict(building=BUILDING, status='exploratory_historical_check_not_preregistered',
        configs=list(CONFIGS), modes=list(MODES), point_views=['confirmed_additions', 'no_imputation'],
        design='每次留1张uNb目标，用另外11张作源；每目标等权。目标结果不进入该折预测。',
        parameters=dict(lookahead=5, min_support=2, epsilon=.1, replicate_rate=.8),
        predictors=['所有源图平均稳定曲线，沿用SOP', '只用源图已identified人数的中位数；min/max仅经验范围'],
        outside='复用既存50组、每组11张楼外源图及相同共同N，全部组等权；不按效果选组。',
        count_evaluation='双方均有点预测且目标identified才计算配对MAE；其余目标状态及覆盖保留。',
        tolerance='附加报告绝对误差<=2人；示例容差，不作为成功门槛，也不据结果选容差。',
        unknown='不补成稳定/未稳定；曲线评价使用误差界，比较共享同一未知目标。',
        independence='12图/1楼；同一人员池，50楼外组及留图有重叠，不作独立样本显著性检验。',
        provenance='消费revised已审计历史派生曲线；原始运行时来源仍为export_label，未重读所有原始点或重分簇。')
    (out / 'METHOD_PLAN.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    inventory = pd.read_csv(REVISED / 'comparison/image_support_comparison.csv')
    local = inventory[inventory.building_id.eq(BUILDING) & inventory.common_n.ge(16)]
    images = sorted(local.image_id)
    if len(images) != 12 or inventory.image_id.duplicated().any():
        raise ValueError('inventory_identity_drift')
    budget = int(local.common_n.min())
    if budget != 23:
        raise ValueError('unexpected_unb_common_budget')
    nodes = budget - 5
    pool = sorted(inventory.loc[~inventory.building_id.eq(BUILDING) & inventory.common_n.ge(budget), 'image_id'])
    if len(pool) != 38:
        raise ValueError('outside_pool_drift')
    groups = None
    for mode in MODES:
        saved = pd.read_csv(REVISED / f'comparison/common_transfer_{mode}/baseline_groups.csv')
        saved = saved[saved.building_id.eq(BUILDING) & saved.source_n.eq(11)].sort_values('group_id')
        current = [json.loads(value) for value in saved.source_images_json]
        if len(current) != 50 or any(len(set(group)) != 11 or not set(group) <= set(pool) for group in current):
            raise ValueError('outside_group_identity_drift')
        if groups is not None and groups != current:
            raise ValueError('worker_scopes_have_different_baselines')
        groups = current
    paired = pd.read_csv(REVISED / 'comparison/common_budget_curves.csv.gz')
    selected = paired[paired.config.isin(CONFIGS) & paired.lookahead.eq(5)
                      & paired.min_support.eq(2) & np.isclose(paired.epsilon, .1)]
    targets, comparisons, curve_rows, summaries = [], [], [], []
    checked_old_folds = 0
    sensitivity_curve_nodes_changed = {}
    for mode in MODES:
        original = selected[['image_id', 'config', 'k'] + [f'{name}_{mode}' for name in
            ['replicates', 'stable', 'changing', 'unknown', 'stable_lower', 'stable_upper']]].rename(
            columns={f'{name}_{mode}': name for name in ['replicates', 'stable', 'changing', 'unknown', 'stable_lower', 'stable_upper']})
        affected = pd.read_csv(REVISED / mode / 'no_imputation/affected_replay/stability_curves.csv')
        affected = affected[affected.config.isin(CONFIGS) & affected.lookahead.eq(5)
                            & affected.min_support.eq(2) & np.isclose(affected.epsilon, .1)]
        alt = pd.concat([original[~original.image_id.isin(affected.image_id)], affected[original.columns]], ignore_index=True)
        old_folds = pd.read_csv(REVISED / f'comparison/common_transfer_{mode}/folds.csv.gz')
        old_folds = old_folds[old_folds.building_id.eq(BUILDING) & old_folds.source_n.eq(11) & old_folds.config.isin(CONFIGS)]
        for config in CONFIGS:
            main_vectors = checked_vectors(original[original.config.eq(config)], images + pool, nodes)
            alt_vectors = checked_vectors(alt[alt.config.eq(config)], images + pool, nodes)
            sensitivity_curve_nodes_changed[f'{mode}/{config}'] = sum(int(np.any(main_vectors[key] != alt_vectors[key], axis=1).sum()) for key in main_vectors)
            for view, vectors in [('confirmed_additions', main_vectors), ('no_imputation', alt_vectors)]:
                tag = dict(mode=mode, config=config, point_view=view)
                bases = [source_prediction(vectors, group) for group in groups]
                baseline_curves = np.stack([base[0] for base in bases])
                case_targets, case_pairs = [], []
                for target in images:
                    source = [key for key in images if key != target]
                    assert target not in source and len(source) == 11 and target not in pool
                    prediction, count, range_low, range_high, source_identified = source_prediction(vectors, source)
                    truth = vectors[target]
                    tp, tc, exact, target_status = onset(truth[:, 0], truth[:, 1])
                    pp, pc, pi, prediction_status = onset(prediction[:, 0], prediction[:, 1])
                    sl, su = interval_error(prediction[:, 0], prediction[:, 1], truth[:, 0], truth[:, 1])
                    ol, ou = interval_error(baseline_curves[:, :, 0], baseline_curves[:, :, 1], truth[:, 0], truth[:, 1])
                    gl, gu = paired_gain_bounds(prediction, baseline_curves, truth)
                    row = dict(**tag, target_image_id=target, source_images_json=json.dumps(source), source_n=11,
                        common_n=budget, k_max=nodes, target_status=target_status, target_possible=tp,
                        target_conservative=tc, target_identified=exact, predicted_curve_status=prediction_status,
                        predicted_curve_possible=pp, predicted_curve_conservative=pc, predicted_curve_identified=pi,
                        source_identified_n=source_identified, median_prediction=count, empirical_range_low=range_low,
                        empirical_range_high=range_high, empirical_range_width=range_high-range_low,
                        count_absolute_error=abs(count-exact) if exact is not None else np.nan,
                        within_two_people=float(abs(count-exact) <= 2) if exact is not None else np.nan,
                        range_hit=float(range_low <= exact <= range_high) if exact is not None else np.nan,
                        not_reached_count_error_lower=max(0., nodes + 1 - count) if target_status == 'not_reached' else np.nan,
                        same_curve_error_lower=float(sl.mean()), same_curve_error_upper=float(su.mean()),
                        outside_curve_error_lower=float(ol.mean()), outside_curve_error_upper=float(ou.mean()),
                        shared_target_gain_lower=float(gl.mean()), shared_target_gain_upper=float(gu.mean()),
                        target_unknown_width=float(np.diff(truth, axis=1).mean()))
                    if view == 'confirmed_additions':
                        match = old_folds[old_folds.config.eq(config) & old_folds.target_images_json.eq(json.dumps([target]))]
                        if len(match) != 1:
                            raise ValueError('saved_loo_fold_identity_mismatch')
                        prior = match.iloc[0]
                        for new_name, old_name in [('same_curve_error_lower','same_error_lower'), ('same_curve_error_upper','same_error_upper'),
                                                   ('outside_curve_error_lower','outside_error_lower'), ('outside_curve_error_upper','outside_error_upper')]:
                            if not np.isclose(row[new_name], prior[old_name], atol=1e-12, rtol=0):
                                raise ValueError(f'saved_fold_value_mismatch:{new_name}')
                        assert prediction_status == prior.predicted_N_status
                        checked_old_folds += 1
                    case_targets.append(row)
                    for group_id, (group, base) in enumerate(zip(groups, bases), 1):
                        bc, bn, bl, bh, bn_support = base
                        comparable = exact is not None and np.isfinite(count) and np.isfinite(bn)
                        case_pairs.append(dict(**tag, target_image_id=target, baseline_group_id=group_id,
                            outside_source_images_json=json.dumps(group), target_status=target_status, target_identified=exact,
                            same_prediction=count, outside_prediction=bn, outside_identified_source_n=bn_support,
                            paired_count_evaluable=comparable, same_error=abs(count-exact) if comparable else np.nan,
                            outside_error=abs(bn-exact) if comparable else np.nan,
                            outside_range_width=bh-bl, outside_range_hit=float(bl <= exact <= bh) if comparable else np.nan))
                    for k in range(nodes):
                        curve_rows.append(dict(**tag, target_image_id=target, k=k+1, target_lower=truth[k,0], target_upper=truth[k,1],
                            same_lower=prediction[k,0], same_upper=prediction[k,1], outside_lower=float(baseline_curves[:,k,0].mean()),
                            outside_upper=float(baseline_curves[:,k,1].mean()), gain_lower=float(gl[:,k].mean()), gain_upper=float(gu[:,k].mean())))
                frame, pairs = pd.DataFrame(case_targets), pd.DataFrame(case_pairs)
                comparable = pairs[pairs.paired_count_evaluable]
                # 每个目标先平均楼外组，再平均目标；不把重叠组当作独立目标。
                by_target = comparable.groupby('target_image_id')[['same_error','outside_error','outside_range_width','outside_range_hit']].mean()
                exact_rows = frame[frame.target_identified.notna()]
                summary = dict(**tag, target_n=len(frame), target_states=dict(Counter(frame.target_status)),
                    curve_prediction_states=dict(Counter(frame.predicted_curve_status)),
                    paired_count_targets=len(by_target), paired_count_group_target_pairs=len(comparable),
                    same_count_mae=float(by_target.same_error.mean()), outside_count_mae=float(by_target.outside_error.mean()),
                    count_mae_gain=float((by_target.outside_error-by_target.same_error).mean()),
                    same_within_two_n=int(exact_rows.within_two_people.sum()), same_within_two_denominator=len(exact_rows),
                    same_empirical_range_hit_n=int(exact_rows.range_hit.sum()), same_empirical_range_width=float(exact_rows.empirical_range_width.mean()),
                    outside_empirical_range_hit_fraction=float(by_target.outside_range_hit.mean()),
                    outside_empirical_range_width=float(by_target.outside_range_width.mean()),
                    not_reached_error_lower_mean=float(frame.not_reached_count_error_lower.mean()))
                for field in ['same_curve_error_lower','same_curve_error_upper','outside_curve_error_lower','outside_curve_error_upper',
                              'shared_target_gain_lower','shared_target_gain_upper','target_unknown_width']:
                    summary[field] = float(frame[field].mean())
                summaries.append(summary)
                targets.extend(case_targets)
                comparisons.extend(case_pairs)
                print(json.dumps(summary, ensure_ascii=False), flush=True)
    outputs = {'target_predictions.csv': pd.DataFrame(targets), 'outside_paired_count_comparisons.csv': pd.DataFrame(comparisons),
               'prediction_curves.csv': pd.DataFrame(curve_rows)}
    for name, frame in outputs.items():
        frame.to_csv(out / name, index=False, encoding='utf-8-sig')
    (out / 'summary.json').write_text(json.dumps(summaries, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    if len(targets) != 96 or len(comparisons) != 4800 or checked_old_folds != 48:
        raise ValueError('output_cardinality_drift')
    assert not outputs['target_predictions.csv'].duplicated(['mode','config','point_view','target_image_id']).any()
    qa = dict(status='passed', target_images=12, buildings=1, common_n=budget, nodes=nodes, outside_pool_n=len(pool),
        outside_groups=len(groups), source_images_per_prediction=11, existing_fold_rows_reproduced=checked_old_folds,
        sensitivity_changed_curve_nodes=sensitivity_curve_nodes_changed,
        output_rows={name: len(frame) for name, frame in outputs.items()}, summary_rows=len(summaries),
        original_exports_changed=False, formal_protocol_changed=False, new_clustering=False, new_hohonet_fit=False,
        source_target_overlap=False, scope='历史留图探索；不是独立新人员、新building或前瞻采集验证。')
    (out / 'QA.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return qa


def run_splits(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    feature_path = ROOT / 'analysis_results/stage3_test_preparation_20260804_v1/test_task_risk_candidate.csv'
    plan = dict(status='exploratory_feature_balanced_splits', source_n=[6, 7], target_n=[6, 5],
        rationale='用户要求约50/50、60/40并兼顾高标注数量、DT类似；12图对应6/6及7/5。',
        features=dict(path=str(feature_path.relative_to(ROOT)), field='d_model_feat',
                      meaning='HoHoNet共享特征到固定训练参考空间的距离；不是旧版d_t，也不是人类难度真值。'),
        assignment='按12图d_model_feat及image_id排序分成3段，每段4图；每段及每个common_n档的源图数在比例期望的floor/ceil内。',
        comparison='枚举所有6/6和7/5划分，再标记满足DT及人数配平的子集；不依收敛标签选择。',
        predictor='源图平均稳定曲线；补充源图identified人数中位数及经验min/max范围。',
        baseline='同源图数、共同N=23的既存50组楼外来源；另加按源图d_model_feat最小总绝对差匹配的楼外组，两者使用相同中位数规则。',
        scope='DT只用于分配，没有拟合DT到收敛人数的回归模型；曲线配置不变。',
        point_view='confirmed_additions；另由留一图检查报告不补点敏感性；本次多图曲线不冒称已做不补点比较。',
        aggregation='先在每张目标图内平均其可比出现，再等权平均不同目标；同时给覆盖。划分、组、出现均非独立样本。')
    (out / 'SPLIT_PLAN.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    inventory = pd.read_csv(REVISED / 'comparison/image_support_comparison.csv')
    local = inventory[inventory.building_id.eq(BUILDING) & inventory.common_n.ge(16)].sort_values('image_id')
    images = local.image_id.tolist()
    assert len(images) == 12 and local.common_n.min() == 23
    counts = dict(zip(images, local.common_n.astype(int)))
    all_features = pd.read_csv(feature_path)
    if all_features.image_id.duplicated().any():
        raise ValueError('duplicate_feature_identity')
    features = all_features[all_features.image_id.isin(images)]
    if (features.image_id.duplicated().any() or set(features.image_id) != set(images)
            or not np.isfinite(features.d_model_feat).all() or not features.feature_status.eq('ready').all()
            or not features.feature_audit_status.eq('approved').all()):
        raise ValueError('incomplete_or_invalid_feature_input')
    ordered = features.sort_values(['d_model_feat','image_id']).image_id.tolist()
    dt_bins = {key: rank // 4 for rank, key in enumerate(ordered)}
    pool = sorted(inventory.loc[~inventory.building_id.eq(BUILDING) & inventory.common_n.ge(23),'image_id'])
    outside_features=all_features[all_features.image_id.isin(pool)]
    if (set(outside_features.image_id)!=set(pool) or not outside_features.feature_status.eq('ready').all()
            or not outside_features.feature_audit_status.eq('approved').all()):
        raise ValueError('outside_feature_coverage_missing')
    dt = all_features.set_index('image_id').d_model_feat.to_dict()
    manifest = []
    for n in (6, 7):
        for source in combinations(images, n):
            target = [key for key in images if key not in source]
            manifest.append(dict(fold_id=sum(1 << images.index(key) for key in source), source_n=n, target_n=12-n,
                source_images_json=json.dumps(source), target_images_json=json.dumps(target),
                matched_outside_source_images_json=json.dumps(feature_matched_sources(source,pool,dt)),
                feature_count_balanced=balanced_source(source, images, dt_bins, counts),
                source_mean_dt=float(np.mean([dt[key] for key in source])), target_mean_dt=float(np.mean([dt[key] for key in target])),
                source_min_n=min(counts[key] for key in source), target_min_n=min(counts[key] for key in target),
                source_dt_bins=json.dumps(dict(Counter(dt_bins[key] for key in source))),
                target_dt_bins=json.dumps(dict(Counter(dt_bins[key] for key in target)))))
    manifest = pd.DataFrame(manifest)
    manifest['absolute_dt_mean_gap'] = abs(manifest.source_mean_dt-manifest.target_mean_dt)
    manifest.to_csv(out / 'split_manifest.csv', index=False, encoding='utf-8-sig')
    feature_rows = local.merge(features[['image_id','d_model_feat','feature_status','feature_audit_status']], on='image_id', validate='one_to_one')
    feature_rows['dt_rank_stratum'] = feature_rows.image_id.map(dt_bins)
    feature_rows.to_csv(out / 'split_features.csv', index=False, encoding='utf-8-sig')
    paired = pd.read_csv(REVISED / 'comparison/common_budget_curves.csv.gz')
    paired = paired[paired.config.isin(CONFIGS) & paired.lookahead.eq(5) & paired.min_support.eq(2) & np.isclose(paired.epsilon,.1)]
    pool = sorted(inventory.loc[~inventory.building_id.eq(BUILDING) & inventory.common_n.ge(23),'image_id'])
    all_targets, all_folds, summaries = [], [], []
    for mode in MODES:
        prefix = REVISED / f'comparison/common_transfer_{mode}'
        bases = pd.read_csv(prefix / 'baseline_groups.csv')
        bases = bases[bases.building_id.eq(BUILDING) & bases.source_n.isin([6, 7])]
        folds = pd.read_csv(prefix / 'folds.csv.gz')
        folds = folds[folds.building_id.eq(BUILDING) & folds.source_n.isin([6,7]) & folds.config.isin(CONFIGS)]
        columns = ['replicates','stable','changing','unknown','stable_lower','stable_upper']
        frame = paired[['image_id','config','k'] + [f'{name}_{mode}' for name in columns]].rename(columns={f'{name}_{mode}':name for name in columns})
        for config in CONFIGS:
            vectors = checked_vectors(frame[frame.config.eq(config)], images + pool, 18)
            onsets = {key: onset(value[:,0],value[:,1]) for key,value in vectors.items()}
            case_targets = []
            case_folds = []
            outside = {}
            for n in (6,7):
                group_ids = [json.loads(value) for value in bases[bases.source_n.eq(n)].sort_values('group_id').source_images_json]
                if len(group_ids) != 50 or any(len(set(group)) != n or not set(group) <= set(pool) for group in group_ids):
                    raise ValueError('split_baseline_groups_invalid')
                values = [source_prediction(vectors, group)[1] for group in group_ids]
                outside[n] = np.asarray(values)[np.isfinite(values)]
            selected = folds[folds.config.eq(config)].merge(manifest, on=['fold_id','source_n','target_n'], validate='one_to_one', suffixes=('','_manifest'))
            if len(selected) != 1716:
                raise ValueError('split_fold_coverage')
            for fold in selected.itertuples():
                if fold.source_images_json != fold.source_images_json_manifest or fold.target_images_json != fold.target_images_json_manifest:
                    raise ValueError('split_identity_mismatch')
                source, target_ids = json.loads(fold.source_images_json), json.loads(fold.target_images_json)
                assert not set(source) & set(target_ids) and set(source + target_ids) == set(images)
                curve, number, low, high, known_n = source_prediction(vectors, source)
                matched_ids = json.loads(fold.matched_outside_source_images_json)
                matched_curve,matched_number,*_ = source_prediction(vectors,matched_ids)
                actual_curves = np.stack([vectors[key] for key in target_ids])
                ml,mu = interval_error(matched_curve[:,0],matched_curve[:,1],actual_curves[:,:,0],actual_curves[:,:,1])
                if onset(curve[:,0],curve[:,1])[3] != fold.predicted_N_status:
                    raise ValueError('split_curve_onset_replay_mismatch')
                fold_row = dict(mode=mode,config=config,fold_id=fold.fold_id,source_n=fold.source_n,target_n=fold.target_n,
                    balanced=fold.feature_count_balanced,prediction_status=fold.predicted_N_status,median_prediction=number,
                    identified_source_n=known_n,absolute_dt_mean_gap=fold.absolute_dt_mean_gap,
                    dtmatched_curve_error_lower=float(ml.mean()),dtmatched_curve_error_upper=float(mu.mean()),
                    dtmatched_gain_lower=float(ml.mean()-fold.same_error_upper),dtmatched_gain_upper=float(mu.mean()-fold.same_error_lower))
                for name in ['same_error_lower','same_error_upper','outside_error_lower','outside_error_upper','benefit_lower','benefit_upper']:
                    fold_row[name] = getattr(fold,name)
                case_folds.append(fold_row)
                for target in target_ids:
                    tp,tc,exact,status = onsets[target]
                    base_numbers = outside[fold.source_n]
                    comparable = exact is not None and np.isfinite(number) and len(base_numbers) > 0
                    matched_comparable = exact is not None and np.isfinite(number) and np.isfinite(matched_number)
                    case_targets.append(dict(mode=mode,config=config,fold_id=fold.fold_id,source_n=fold.source_n,
                        balanced=fold.feature_count_balanced,target_image_id=target,target_status=status,target_identified=exact,
                        same_prediction=number,source_identified_n=known_n,empirical_range_low=low,empirical_range_high=high,
                        paired_evaluable=comparable,outside_prediction_available_groups=len(base_numbers),
                        dtmatched_prediction=matched_number,dtmatched_paired_evaluable=matched_comparable,
                        same_error_dtmatched=abs(number-exact) if matched_comparable else np.nan,
                        dtmatched_error=abs(matched_number-exact) if matched_comparable else np.nan,
                        same_error=abs(number-exact) if comparable else np.nan,
                        outside_error=float(abs(base_numbers-exact).mean()) if comparable else np.nan,
                        same_within_two=float(abs(number-exact)<=2) if comparable else np.nan,
                        outside_within_two=float((abs(base_numbers-exact)<=2).mean()) if comparable else np.nan,
                        empirical_range_hit=float(low<=exact<=high) if comparable else np.nan,
                        empirical_range_width=high-low,
                        not_reached_error_lower=max(0.,19-number) if status=='not_reached' and np.isfinite(number) else np.nan))
            target_frame, fold_frame = pd.DataFrame(case_targets),pd.DataFrame(case_folds)
            for n in (6,7):
                for design in ('all_splits','dt_and_count_balanced'):
                    f = fold_frame[fold_frame.source_n.eq(n)]
                    t = target_frame[target_frame.source_n.eq(n)]
                    if design == 'dt_and_count_balanced':
                        f,t = f[f.balanced],t[t.balanced]
                    comparable = t[t.paired_evaluable]
                    # 目标图等权；没有预测的出现不会被写成零误差。
                    per_image = comparable.groupby('target_image_id')[['same_error','outside_error','same_within_two','outside_within_two',
                        'empirical_range_hit','empirical_range_width']].mean()
                    matched_pairs = t[t.dtmatched_paired_evaluable]
                    matched_per_image = matched_pairs.groupby('target_image_id')[['same_error_dtmatched','dtmatched_error']].mean()
                    unknown = t[t.target_status.eq('unknown')].target_image_id.nunique()
                    late = t[t.target_status.eq('not_reached')].groupby('target_image_id').not_reached_error_lower.mean()
                    identified_appearances = int(t.target_status.eq('identified').sum())
                    summary = dict(mode=mode,config=config,source_n=n,target_n=12-n,design=design,fold_n=len(f),
                        distinct_target_n=t.target_image_id.nunique(),target_appearances=len(t),
                        identified_target_n=t[t.target_status.eq('identified')].target_image_id.nunique(),
                        not_reached_target_n=t[t.target_status.eq('not_reached')].target_image_id.nunique(),unknown_target_n=unknown,
                        count_paired_target_n=len(per_image),count_paired_appearances=len(comparable),
                        identified_target_appearances=identified_appearances,
                        exact_target_prediction_coverage=len(comparable)/identified_appearances if identified_appearances else None,
                        overall_target_prediction_fraction=float(t.same_prediction.notna().mean()),
                        same_count_mae=float(per_image.same_error.mean()),outside_count_mae=float(per_image.outside_error.mean()),
                        dtmatched_paired_targets=len(matched_per_image),dtmatched_paired_appearances=len(matched_pairs),
                        same_count_mae_dtmatched_pairs=float(matched_per_image.same_error_dtmatched.mean()),
                        dtmatched_count_mae=float(matched_per_image.dtmatched_error.mean()),
                        dtmatched_count_gain=float((matched_per_image.dtmatched_error-matched_per_image.same_error_dtmatched).mean()),
                        count_mae_gain=float((per_image.outside_error-per_image.same_error).mean()),
                        same_within_two_fraction=float(per_image.same_within_two.mean()),outside_within_two_fraction=float(per_image.outside_within_two.mean()),
                        same_empirical_range_hit_fraction=float(per_image.empirical_range_hit.mean()),
                        same_empirical_range_width=float(per_image.empirical_range_width.mean()),
                        not_reached_error_lower_mean=float(late.mean()),curve_prediction_states=dict(Counter(f.prediction_status)),
                        absolute_dt_mean_gap=float(f.absolute_dt_mean_gap.mean()))
                    summary.update({name:float(f[name].mean()) for name in ['same_error_lower','same_error_upper','outside_error_lower','outside_error_upper','benefit_lower','benefit_upper',
                        'dtmatched_curve_error_lower','dtmatched_curve_error_upper','dtmatched_gain_lower','dtmatched_gain_upper']})
                    summaries.append(summary)
                    print(json.dumps(summary,ensure_ascii=False),flush=True)
            all_targets.extend(case_targets)
            all_folds.extend(case_folds)
    pd.DataFrame(all_targets).to_csv(out / 'split_target_predictions.csv.gz',index=False)
    pd.DataFrame(all_folds).to_csv(out / 'split_fold_scores.csv',index=False,encoding='utf-8-sig')
    (out / 'split_summary.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    qa = dict(status='passed',feature_rows=len(feature_rows),feature_name='d_model_feat',old_d_t_used=False,
        source_n_counts=manifest.groupby('source_n').size().to_dict(),
        balanced_source_n_counts=manifest[manifest.feature_count_balanced].groupby('source_n').size().to_dict(),
        target_rows=len(all_targets),fold_rows=len(all_folds),summary_rows=len(summaries),
        source_target_disjoint=True,outcome_used_for_allocation=False,new_feature_regression=False,
        common_n=23,configs=list(CONFIGS),modes=list(MODES),scope='同楼多图划分历史探索，未做新人验证。')
    assert len(all_targets)==38016 and len(all_folds)==6864 and len(summaries)==16
    (out / 'SPLIT_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return qa


def run_short_windows(out):
    """同一h1/k2..4窗口下，对照12张高人数图与27张高低混合图。"""
    out = Path(out)
    inventory = pd.read_csv(REVISED / 'comparison/image_support_comparison.csv')
    counts = inventory.set_index('image_id').common_n.astype(int).to_dict()
    local = inventory[inventory.building_id.eq(BUILDING)]
    all_images = sorted(local.loc[local.common_n.ge(5),'image_id'])
    dense_images = [key for key in all_images if counts[key]>=16]
    assert len(all_images)==27 and len(dense_images)==12
    feature_path = ROOT / 'analysis_results/stage3_test_preparation_20260804_v1/test_task_risk_candidate.csv'
    features = pd.read_csv(feature_path)
    if features.image_id.duplicated().any():
        raise ValueError('duplicate_feature_identity')
    valid = features.feature_status.eq('ready') & features.feature_audit_status.eq('approved') & np.isfinite(features.d_model_feat)
    dt = features[valid].set_index('image_id').d_model_feat.to_dict()
    if not set(all_images)<=set(dt):
        raise ValueError('low_n_feature_coverage_missing')
    pool = sorted(inventory.loc[~inventory.building_id.eq(BUILDING) & inventory.common_n.ge(5)
                               & inventory.image_id.isin(dt),'image_id'])
    plan = dict(status='exploratory_short_window_comparison',cohorts={'high_only':12,'high_and_low':27},
        excluded='uNb只有1张零响应图排除；没有N=1/2/3/4图。15张低人数图为12张N5、3张N6。',
        horizon='共同截断到前5份响应；h1，在k2/3/4评价；k1不满足m2支持，不作可行起点。',
        endpoint='主要比较到k4、随后1份响应内是否达到80%排列稳定；不是长期收敛。',
        predictor='源图中短窗状态已知图的稳定比例预测目标短窗稳定概率；同时保留平均曲线未知边界。',
        baseline='楼外同数量且逐一匹配高/低响应密度、d_model_feat总绝对差最小；不使用收敛结果匹配。',
        splits='高人数6/6和7/5枚举；混合14/13和16/11，各抽200个不配平及200个DT+人数档配平划分。固定种子。',
        balance='DT排序三等段，高人数每段4图、混合每段9图；各段及N5/6/23/24档在比例期望floor/ceil内。',
        comparison_limit='高人数短窗控制用于区分窗口变化；混合包含新增目标，组间差异不是低人数图的因果效果。',
        missing='目标未知不计Brier但留覆盖；源未知不计成功/失败，另报曲线区间。',
        brier='(预测概率-实际0/1短窗状态)^2，越低越好；先每目标平均出现，再平均目标。',
        count='短窗候选人数仅2..4；不报告±2命中率，以免这个狭窄范围机械产生100%。',
        original_protocol_changed=False,new_feature_regression=False)
    (out/'SHORT_WINDOW_PLAN.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    designs=[]
    for cohort,images,source_sizes in [('high_only',dense_images,(6,7)),('high_and_low',all_images,(14,16))]:
        ranked=sorted(images,key=lambda x:(dt[x],x))
        bins={key:i//(len(images)//3) for i,key in enumerate(ranked)}
        for n in source_sizes:
            for design in ('unbalanced','dt_and_count_balanced'):
                if cohort=='high_only':
                    sources=list(combinations(images,n))
                    if design!='unbalanced':
                        sources=[s for s in sources if balanced_source(s,images,bins,counts)]
                else:
                    rng=random.Random(f'20260909|{n}|{design}')
                    sources=set()
                    attempts=0
                    while len(sources)<200:
                        source=tuple(sorted(rng.sample(images,n)))
                        attempts+=1
                        if attempts>1000000:
                            raise ValueError('balanced_sampling_exhausted')
                        if design=='unbalanced' or balanced_source(source,images,bins,counts):
                            sources.add(source)
                    sources=sorted(sources)
                for source in sources:
                    target=[key for key in images if key not in source]
                    matched=[]
                    for dense in (False,True):
                        part=[key for key in source if (counts[key]>=16)==dense]
                        candidates=[key for key in pool if (counts[key]>=16)==dense]
                        if part:
                            matched.extend(feature_matched_sources(part,candidates,dt))
                    assert len(set(matched))==n and not set(source)&set(target)
                    designs.append(dict(cohort=cohort,design=design,source_n=n,target_n=len(target),
                        fold_id=sum(1<<images.index(key) for key in source),source_images_json=json.dumps(source),
                        target_images_json=json.dumps(target),outside_images_json=json.dumps(matched),
                        source_high_n=sum(counts[key]>=16 for key in source),target_high_n=sum(counts[key]>=16 for key in target)))
    pd.DataFrame(designs).to_csv(out/'short_window_split_manifest.csv.gz',index=False)
    pd.DataFrame([dict(image_id=key,common_n=counts[key],d_model_feat=dt[key],high_n=counts[key]>=16) for key in all_images]).to_csv(out/'short_window_inventory.csv',index=False,encoding='utf-8-sig')
    paired=pd.read_csv(REVISED/'comparison/common_budget_curves.csv.gz')
    paired=paired[paired.config.isin(CONFIGS)&paired.lookahead.eq(1)&paired.min_support.eq(2)&np.isclose(paired.epsilon,.1)]
    target_rows,fold_rows,summaries=[],[],[]
    for mode in MODES:
        columns=['replicates','stable','changing','unknown','stable_lower','stable_upper']
        frame=paired[['image_id','config','k']+[f'{name}_{mode}' for name in columns]].rename(columns={f'{name}_{mode}':name for name in columns})
        for config in CONFIGS:
            vectors=checked_vectors(frame[frame.config.eq(config)],all_images+pool,4)
            vectors={key:value[1:] for key,value in vectors.items()}
            states={key:(1. if value[-1,0]>=.8-1e-12 else 0. if value[-1,1]<.8-1e-12 else np.nan) for key,value in vectors.items()}
            case_targets,case_folds=[],[]
            for fold in designs:
                source,target,external=[json.loads(fold[name]) for name in ('source_images_json','target_images_json','outside_images_json')]
                p,pn=known_state_probability(states,source)
                b,bn=known_state_probability(states,external)
                prediction=np.mean([vectors[key] for key in source],axis=0)
                baseline=np.mean([vectors[key] for key in external],axis=0)
                truth=np.stack([vectors[key] for key in target])
                sl,su=interval_error(prediction[:,0],prediction[:,1],truth[:,:,0],truth[:,:,1])
                bl,bu=interval_error(baseline[:,0],baseline[:,1],truth[:,:,0],truth[:,:,1])
                gl,gu=paired_gain_bounds(prediction,baseline,truth)
                tag={name:fold[name] for name in ('cohort','design','source_n','target_n','fold_id')}
                tag.update(mode=mode,config=config)
                case_folds.append(dict(**tag,source_known_n=pn,outside_known_n=bn,
                    same_curve_error_lower=float(sl.mean()),same_curve_error_upper=float(su.mean()),
                    outside_curve_error_lower=float(bl.mean()),outside_curve_error_upper=float(bu.mean()),
                    curve_gain_lower=float(gl.mean()),curve_gain_upper=float(gu.mean())))
                for key in target:
                    y=states[key]
                    comparable=bool(np.isfinite([y,p,b]).all())
                    case_targets.append(dict(**tag,target_image_id=key,target_high_n=counts[key]>=16,actual_short_stable=y,
                        same_probability=p,outside_probability=b,paired_evaluable=comparable,
                        same_brier=(p-y)**2 if comparable else np.nan,outside_brier=(b-y)**2 if comparable else np.nan))
            t,f=pd.DataFrame(case_targets),pd.DataFrame(case_folds)
            for (cohort,design,n),group in t.groupby(['cohort','design','source_n']):
                fold_group=f[f.cohort.eq(cohort)&f.design.eq(design)&f.source_n.eq(n)]
                comparable=group[group.paired_evaluable]
                per_image=comparable.groupby('target_image_id')[['same_brier','outside_brier']].mean()
                high=comparable[comparable.target_high_n].groupby('target_image_id')[['same_brier','outside_brier']].mean()
                low=comparable[~comparable.target_high_n].groupby('target_image_id')[['same_brier','outside_brier']].mean()
                distinct=group.drop_duplicates('target_image_id')
                s=dict(mode=mode,config=config,cohort=cohort,design=design,source_n=int(n),target_n=int(group.target_n.iloc[0]),
                    fold_n=len(fold_group),distinct_target_n=len(distinct),known_stable_n=int(distinct.actual_short_stable.eq(1).sum()),
                    known_changing_n=int(distinct.actual_short_stable.eq(0).sum()),unknown_n=int(distinct.actual_short_stable.isna().sum()),
                    paired_target_n=len(per_image),paired_appearances=len(comparable),target_appearances=len(group),
                    same_brier=float(per_image.same_brier.mean()),outside_brier=float(per_image.outside_brier.mean()),
                    brier_gain=float((per_image.outside_brier-per_image.same_brier).mean()),
                    high_target_brier_gain=float((high.outside_brier-high.same_brier).mean()) if len(high) else None,
                    low_target_brier_gain=float((low.outside_brier-low.same_brier).mean()) if len(low) else None)
                s.update({name:float(fold_group[name].mean()) for name in ['same_curve_error_lower','same_curve_error_upper',
                    'outside_curve_error_lower','outside_curve_error_upper','curve_gain_lower','curve_gain_upper']})
                summaries.append(s)
            target_rows.extend(case_targets)
            fold_rows.extend(case_folds)
    pd.DataFrame(target_rows).to_csv(out/'short_window_target_predictions.csv.gz',index=False)
    pd.DataFrame(fold_rows).to_csv(out/'short_window_fold_scores.csv.gz',index=False)
    (out/'short_window_summary.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    qa=dict(status='passed',high_images=12,low_images=15,total_images=27,excluded_zero_response=1,
        outside_pool_images=len(pool),split_design_rows=len(designs),target_rows=len(target_rows),fold_rows=len(fold_rows),
        summary_rows=len(summaries),high_source_and_target_present=all(d['source_high_n']>0 and d['target_high_n']>0 for d in designs),
        fixed_horizon=1,common_prefix_n=5,k_evaluated=[2,3,4],feature_complete=True,source_target_disjoint=True,
        old_d_t_used=False,formal_protocol_changed=False,interpretation='短窗口稳定可预测性，不是高人数收敛验证。')
    assert qa['high_source_and_target_present']
    (out/'SHORT_WINDOW_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(qa,ensure_ascii=False),flush=True)
    return qa


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--split-only', action='store_true')
    parser.add_argument('--short-only', action='store_true')
    args = parser.parse_args()
    if not args.split_only and not args.short_only:
        print(json.dumps(run(args.out), ensure_ascii=False, indent=2))
    if not args.short_only:
        print(json.dumps(run_splits(args.out), ensure_ascii=False, indent=2))
    print(json.dumps(run_short_windows(args.out), ensure_ascii=False, indent=2))
