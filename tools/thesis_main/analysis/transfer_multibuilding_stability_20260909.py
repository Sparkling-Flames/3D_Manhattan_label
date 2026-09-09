"""所选人数范围的同楼互补留图探索；保留未知边界，不把组合当独立实验。"""
import argparse
import json
import math
import random
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / 'analysis_results/multibuilding_threshold_stability_20260909_v1'
CONFIGS = ['q_0.975', 'q_0.950', 'q_0.925', 'q_0.900', 'q_0.850', 'q_0.800', 'ospa30_t6']
LOOKAHEAD, MIN_SUPPORT, EPSILON, RATE = 5, 2, .10, .80


def interval_error(pl, pu, tl, tu):
    """逐点绝对差的可行上下界；不推断未知排列的实际结果。"""
    return np.maximum(0, np.maximum(pl - tu, tl - pu)), np.maximum(abs(pl - tu), abs(pu - tl))


def onset(lower, upper):
    """k 从1开始；要求该点及以后所有可评价节点持续达标。"""
    def first(values):
        indices = np.flatnonzero(np.minimum.accumulate(np.asarray(values)[::-1])[::-1] >= RATE - 1e-12)
        return int(indices[0] + 1) if len(indices) else None
    possible, guaranteed = first(upper), first(lower)
    identified = possible if possible is not None and possible == guaranteed else None
    return possible, guaranteed, identified, ('identified' if identified is not None else
        'not_reached' if possible is None else 'unknown')


def baseline_groups(pool, n, seed):
    total = math.comb(len(pool), n) if n <= len(pool) else 0
    if total <= 50:
        return list(combinations(pool, n)), total, 'exhaustive'
    rng, groups = random.Random(seed), set()
    while len(groups) < 50:
        groups.add(tuple(sorted(rng.sample(pool, n))))
    return sorted(groups), total, 'sampled_50_without_replacement'


def validate(inventory, curves, *, lookahead=LOOKAHEAD, min_workers=16, configs=CONFIGS):
    if not isinstance(lookahead, int) or lookahead < 1 or not isinstance(min_workers, int) or min_workers < 1:
        raise ValueError('lookahead_and_min_workers_must_be_positive_integers')
    if not configs or len(set(configs)) != len(configs) or set(configs) - set(CONFIGS):
        raise ValueError('unknown_or_duplicate_configs')
    if {'image_id', 'building_id', 'usable_n'} - set(inventory):
        raise ValueError('missing_inventory_fields')
    if inventory[['image_id', 'building_id', 'usable_n']].isna().any().any() or inventory.image_id.duplicated().any():
        raise ValueError('invalid_inventory_identity')
    sizes = inventory.usable_n.to_numpy()
    if not np.isfinite(sizes).all() or (sizes < 0).any() or not np.equal(sizes, np.floor(sizes)).all():
        raise ValueError('invalid_inventory_people_counts')
    required = {'image_id', 'building_id', 'config', 'k', 'lookahead', 'min_support', 'epsilon',
        'replicates', 'stable', 'changing', 'unknown', 'stable_lower', 'stable_upper'}
    if required - set(curves):
        raise ValueError(f'missing_curve_fields:{sorted(required - set(curves))}')
    if set(curves.image_id) - set(inventory.image_id):
        raise ValueError('curve_image_absent_from_inventory')
    eligible = inventory[(inventory.usable_n >= min_workers) & (inventory.usable_n > lookahead)].copy()
    if eligible.empty:
        raise ValueError('no_images_with_required_people_and_window')
    selected = curves[(curves.lookahead == lookahead) & (curves.min_support == MIN_SUPPORT) &
        np.isclose(curves.epsilon, EPSILON) & curves.image_id.isin(eligible.image_id) & curves.config.isin(configs)].copy()
    if set(selected.image_id) != set(eligible.image_id) or set(selected.config) != set(configs):
        raise ValueError('incomplete_image_or_config_coverage')
    if selected.duplicated(['image_id', 'config', 'k']).any():
        raise ValueError('duplicate_curve_nodes')
    if not (selected.replicates == 200).all():
        raise ValueError('replicate_count_drift')
    counts = selected[['stable', 'changing', 'unknown']].to_numpy()
    if not np.isfinite(counts).all() or not (counts >= 0).all() or not np.equal(counts, np.floor(counts)).all():
        raise ValueError('invalid_state_counts')
    if not np.equal(counts.sum(axis=1), selected.replicates).all():
        raise ValueError('state_counts_do_not_sum_to_replicates')
    if not np.allclose(selected.stable_lower, selected.stable / selected.replicates, atol=1e-12, rtol=0):
        raise ValueError('lower_rate_mismatch')
    if not np.allclose(selected.stable_upper, (selected.stable + selected.unknown) / selected.replicates, atol=1e-12, rtol=0):
        raise ValueError('upper_rate_mismatch')
    for row in eligible.itertuples():
        for config in configs:
            group = selected[(selected.image_id == row.image_id) & (selected.config == config)]
            if group.k.tolist() != sorted(group.k.tolist()):
                group = group.sort_values('k')
            if group.k.tolist() != list(range(1, int(row.usable_n) - lookahead + 1)):
                raise ValueError(f'incomplete_curve_nodes:{row.image_id}:{config}')
            if set(group.building_id) != {row.building_id}:
                raise ValueError('building_identity_mismatch')
    return eligible.sort_values('image_id'), selected


def transfer(inventory, curves, out, *, lookahead=LOOKAHEAD, min_workers=16, configs=CONFIGS):
    dense, selected = validate(inventory, curves, lookahead=lookahead, min_workers=min_workers, configs=configs)
    if not (dense.groupby('building_id').size() >= 2).any():
        raise ValueError('no_building_with_two_eligible_images')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    vectors = {(image, config): group.sort_values('k')[['stable_lower', 'stable_upper']].to_numpy()
        for (image, config), group in selected.groupby(['image_id', 'config'])}
    baseline_rows, fold_rows, image_onset_rows = [], [], []
    for building, inventory_group in dense.groupby('building_id'):
        images = inventory_group.image_id.tolist()
        if len(images) < 2:
            continue
        budget = int(inventory_group.usable_n.min())
        nodes = budget - lookahead
        pool = dense.loc[(dense.building_id != building) & (dense.usable_n >= budget), 'image_id'].tolist()
        groups_by_n = {}
        for n in range(1, len(images)):
            groups, total, mode = baseline_groups(pool, n, f'20260909|{building}|{n}')
            groups_by_n[n] = groups
            for j, group in enumerate(groups or [()], 1):
                baseline_rows.append(dict(building_id=building, source_n=n, common_people_budget=budget,
                    outside_pool_n=len(pool), possible_group_n=total, actual_group_n=len(groups),
                    sampling=mode if groups else 'insufficient_pool', group_id=j if groups else '',
                    source_images_json=json.dumps(group)))
        masks = range(1, 2 ** len(images) - 1)
        for config in configs:
            local = np.array([vectors[(image, config)][:nodes] for image in images])
            target_onsets = [onset(v[:, 0], v[:, 1]) for v in local]
            for image, result in zip(images, target_onsets):
                image_onset_rows.append(dict(image_id=image, building_id=building, config=config,
                    common_people_budget=budget, k_max=nodes, lookahead=lookahead, min_support=MIN_SUPPORT,
                    epsilon=EPSILON, repeat_rate=RATE, N_possible=result[0], N_lower_bound_crossing=result[1],
                    N_identified=result[2], N_status=result[3]))
            outside = {}
            for n, groups in groups_by_n.items():
                if not groups:
                    outside[n] = None
                    continue
                predictions = np.array([np.mean([vectors[(image, config)][:nodes] for image in group], axis=0)
                    for group in groups])
                low, high = interval_error(predictions[:, None, :, 0], predictions[:, None, :, 1],
                    local[None, :, :, 0], local[None, :, :, 1])
                identified = [onset(v[:, 0], v[:, 1])[2] for v in predictions]
                errors = [[abs(p - t[2]) for p in identified if p is not None and t[2] is not None]
                    for t in target_onsets]
                outside[n] = dict(low=low.mean(axis=(0, 2)), high=high.mean(axis=(0, 2)),
                    width=float(np.mean(predictions[:, :, 1] - predictions[:, :, 0])),
                    N_count=np.array([len(e) for e in errors]), N_error=np.array([sum(e) for e in errors]),
                    identified_fraction=sum(p is not None for p in identified) / len(groups))
            for mask in masks:
                source_ix = [i for i in range(len(images)) if mask & (1 << i)]
                target_ix = [i for i in range(len(images)) if not mask & (1 << i)]
                source, target = [images[i] for i in source_ix], [images[i] for i in target_ix]
                assert not set(source) & set(target) and set(source + target) == set(images)
                prediction = local[source_ix].mean(axis=0)
                target_curves = local[target_ix]
                low, high = interval_error(prediction[:, 0], prediction[:, 1],
                    target_curves[:, :, 0], target_curves[:, :, 1])
                p = onset(prediction[:, 0], prediction[:, 1])
                targets = [target_onsets[i] for i in target_ix]
                errors = [abs(p[2] - t[2]) for t in targets if p[2] is not None and t[2] is not None]
                base = outside[len(source)]
                baseline_count = int(base['N_count'][target_ix].sum()) if base else 0
                baseline_error = float(base['N_error'][target_ix].sum()) if base else 0
                row = dict(building_id=building, config=config, fold_id=mask,
                    source_n=len(source), target_n=len(target), common_people_budget=budget,
                    k_min=1, k_max=nodes, k_nodes=nodes, lookahead=lookahead, min_support=MIN_SUPPORT,
                    epsilon=EPSILON, repeat_rate=RATE, source_images_json=json.dumps(source),
                    target_images_json=json.dumps(target), same_error_lower=float(low.mean()),
                    same_error_upper=float(high.mean()),
                    same_prediction_unknown_mean=float(np.mean(prediction[:, 1] - prediction[:, 0])),
                    target_unknown_mean=float(np.mean(target_curves[:, :, 1] - target_curves[:, :, 0])),
                    outside_pool_n=len(pool), outside_group_n=len(groups_by_n[len(source)]),
                    outside_error_lower=float(base['low'][target_ix].mean()) if base else np.nan,
                    outside_error_upper=float(base['high'][target_ix].mean()) if base else np.nan,
                    outside_prediction_unknown_mean=base['width'] if base else np.nan,
                    predicted_N_possible=p[0], predicted_N_guaranteed=p[1], predicted_N_identified=p[2],
                    predicted_N_interval_width=p[1] - p[0] if p[1] is not None else np.nan,
                    predicted_N_status=p[3], target_N_identified_n=sum(t[3] == 'identified' for t in targets),
                    target_N_both_finite_n=sum(t[1] is not None for t in targets),
                    target_N_interval_width_le2_n=sum(t[1] is not None and t[1] - t[0] <= 2 for t in targets),
                    target_N_lower_crossing_lt5_n=sum(t[1] is not None and t[1] < 5 for t in targets),
                    target_N_not_reached_n=sum(t[3] == 'not_reached' for t in targets),
                    target_N_unknown_n=sum(t[3] == 'unknown' for t in targets),
                    N_identified_pairs=len(errors), N_absolute_error_sum=sum(errors),
                    N_MAE_identified=float(np.mean(errors)) if errors else np.nan,
                    target_stable_lower_at_prediction=float(target_curves[:, p[2]-1, 0].mean()) if p[2] else np.nan,
                    target_stable_upper_at_prediction=float(target_curves[:, p[2]-1, 1].mean()) if p[2] else np.nan,
                    outside_N_identified_prediction_fraction=base['identified_fraction'] if base else np.nan,
                    outside_N_identified_pairs=baseline_count, outside_N_absolute_error_sum=baseline_error,
                    outside_N_MAE_identified=baseline_error / baseline_count if baseline_count else np.nan)
                row['benefit_lower'] = row['outside_error_lower'] - row['same_error_upper']
                row['benefit_upper'] = row['outside_error_upper'] - row['same_error_lower']
                fold_rows.append(row)
        print(f'{building}: {len(images)} 图，{2 ** len(images)-2} 种划分，共同人数 {budget}', flush=True)
    folds = pd.DataFrame(fold_rows)
    folds.to_csv(out / 'folds.csv.gz', index=False)
    pd.DataFrame(baseline_rows).to_csv(out / 'baseline_groups.csv', index=False)
    pd.DataFrame(image_onset_rows).to_csv(out / 'target_image_onsets.csv', index=False)
    summaries = []
    mean_fields = ['same_error_lower', 'same_error_upper', 'outside_error_lower', 'outside_error_upper',
        'benefit_lower', 'benefit_upper', 'same_prediction_unknown_mean', 'target_unknown_mean',
        'outside_prediction_unknown_mean', 'outside_N_identified_prediction_fraction']
    for (building, config), all_folds in folds.groupby(['building_id', 'config']):
        for source_n, group in [('all', all_folds), *all_folds.groupby('source_n')]:
            row = dict(building_id=building, config=config, source_n=source_n, folds=len(group),
                target_appearances=int(group.target_n.sum()), common_people_budget=int(group.common_people_budget.iloc[0]),
                k_max=int(group.k_max.iloc[0]), outside_pool_n=int(group.outside_pool_n.iloc[0]),
                outside_group_n_min=int(group.outside_group_n.min()), outside_group_n_max=int(group.outside_group_n.max()),
                prediction_identified_folds=int((group.predicted_N_status == 'identified').sum()),
                prediction_not_reached_folds=int((group.predicted_N_status == 'not_reached').sum()),
                prediction_unknown_folds=int((group.predicted_N_status == 'unknown').sum()))
            both = group[group.predicted_N_possible.notna() & group.predicted_N_guaranteed.notna()]
            row.update(prediction_lower_onset_finite_folds=int(group.predicted_N_guaranteed.notna().sum()),
                prediction_both_onsets_finite_folds=len(both),
                prediction_onset_width_le2_folds=int((group.predicted_N_interval_width <= 2).sum()),
                prediction_lower_crossing_lt5_folds=int((group.predicted_N_guaranteed < 5).sum()),
                prediction_onset_width_mean_among_both_finite=float((both.predicted_N_guaranteed - both.predicted_N_possible).mean()),
                prediction_lower_onset_mean_among_finite=float(group.predicted_N_guaranteed.mean()))
            row.update({name: float(group[name].mean()) for name in mean_fields})
            for name in ['target_N_identified_n', 'target_N_not_reached_n', 'target_N_unknown_n',
                         'target_N_both_finite_n', 'target_N_interval_width_le2_n', 'target_N_lower_crossing_lt5_n',
                         'N_identified_pairs', 'N_absolute_error_sum', 'outside_N_identified_pairs',
                         'outside_N_absolute_error_sum']:
                row[name] = float(group[name].sum())
            row['N_MAE_identified'] = row['N_absolute_error_sum'] / row['N_identified_pairs'] if row['N_identified_pairs'] else np.nan
            row['outside_N_MAE_identified'] = row['outside_N_absolute_error_sum'] / row['outside_N_identified_pairs'] if row['outside_N_identified_pairs'] else np.nan
            summaries.append(row)
    pd.DataFrame(summaries).to_csv(out / 'building_summary.csv', index=False)
    qa = dict(status='passed', selected_images=len(dense), dense_images=int((dense.usable_n >= 16).sum()),
        min_workers=min_workers, building_n=folds.building_id.nunique(),
        fold_rows=len(folds), directed_image_folds=len(folds.drop_duplicates(['building_id', 'fold_id'])),
        configs=list(configs), lookahead=lookahead, min_support=MIN_SUPPORT, epsilon=EPSILON, repeat_rate=RATE,
        curve_rows_selected=len(selected), summary_rows=len(summaries), baseline_group_rows=len(baseline_rows),
        target_image_onset_rows=len(image_onset_rows),
        source_target_overlap=False, formal_protocol_changed=False,
        scope='库存所选人数范围图中的楼内留图；相同人员池的历史重排，不是新人员泛化。每图独立类，不预测跨图类ID。',
        selection=f'库存中无辅助可计算不同标注者>={min_workers}且>{lookahead}以支持至少一个完整窗口；不按q或稳定结果删图。楼内>=2图枚举非空互补划分。',
        nodes=f'每楼k=1至该楼所选图最小usable_n-{lookahead}；源与目标共享该评价范围。',
        baseline='外楼图且usable_n>=该楼共同人数预算；匹配源图数量。每楼/源图数固定随机50组，无放回；不足50种则枚举。各q复用身份。',
        error_bounds='对预测及目标的稳定率区间计算每节点绝对差可行上下界，再平均目标图和k；不作置信区间。全未知可为[0,1]，不能解释成准确预测。',
        benefit_bounds='外楼误差下界-同楼误差上界，外楼误差上界-同楼误差下界；并列反映未知导致的不确定。',
        onset='rate=.8，首次且之后所有可评价k均达标。upper给乐观起点，lower给稳定率下界过线起点；二者相等且有限才identified。guaranteed仅指此回放判据的下界过线，绝非真实采集停止保证。起点不精确识别不等于毫无人数信息：同时报告两个候选起点及其宽度。',
        unknown='upper仍未达为not_reached；possible/guaranteed不一致或只有possible为unknown；都不是永不稳定。',
        averaging='curve列先按目标图和k平均，再按外楼组平均。summary为划分等权均值；source_n=all包含全部源图数量。N误差按可识别目标出现计数加权，明确分母。',
        dependence='划分大量重叠；同人跨图；50组外楼源也重叠。行数与目标出现数不是独立样本量，不做显著性检验。',
        files={'folds.csv.gz':'每楼×几何配置×非空互补图划分；身份、共同预算、未知宽度、误差边界、N状态与可识别子集误差。',
               'baseline_groups.csv':'每楼×源图数×外楼组；固定来源身份及抽样数量。',
               'target_image_onsets.csv':'每张目标图×配置，按其building共同人数预算报告乐观起点、稳定率下界过线起点、精确识别与状态；不精确时保留区间。',
               'building_summary.csv':'每楼×配置×源图数，另all为所有划分；误差和覆盖同时汇总。'})
    (out / 'QA.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
    return qa


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, default=PACKAGE / 'image_inventory.csv')
    parser.add_argument('--curves', type=Path, default=PACKAGE / 'replay/stability_curves.csv')
    parser.add_argument('--out', type=Path, default=PACKAGE / 'transfer')
    parser.add_argument('--lookahead', type=int, default=LOOKAHEAD)
    parser.add_argument('--min-workers', type=int, default=16)
    parser.add_argument('--configs', nargs='+', choices=CONFIGS, default=CONFIGS)
    args = parser.parse_args()
    qa = transfer(pd.read_csv(args.inventory), pd.read_csv(args.curves), args.out,
        lookahead=args.lookahead, min_workers=args.min_workers, configs=args.configs)
    print(json.dumps(qa, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
