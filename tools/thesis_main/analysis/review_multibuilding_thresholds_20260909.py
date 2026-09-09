"""多楼高人数支持与 q 阈值回读；黑灰图，不将几何子集冒充完整图。"""
import argparse
import gzip
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'analysis_results/multibuilding_threshold_stability_20260909_v1'
CURVE_KEYS = ['image_id', 'building_id', 'config', 'lookahead', 'min_support', 'epsilon']
MODES = ['with_workers', 'without_workers']
MODE_LABELS = {'with_workers': '含W19/W26', 'without_workers': '不含W19/W26'}


def checked_curves(inventory, curves):
    """全量校验节点与状态计数；缺节点不能由两侧 inner join 静默掩盖。"""
    inventory = inventory[['image_id', 'building_id', 'usable_n']]
    if inventory.image_id.duplicated().any() or curves.duplicated(CURVE_KEYS + ['k']).any():
        raise ValueError('duplicate_image_or_curve_node')
    if (inventory.usable_n < 0).any() or not np.equal(inventory.usable_n, np.floor(inventory.usable_n)).all():
        raise ValueError('invalid_people_count')
    result = curves.merge(inventory, on='image_id', suffixes=('', '_inventory'), how='left', validate='many_to_one')
    if result.usable_n.isna().any() or not result.building_id.eq(result.building_id_inventory).all():
        raise ValueError('building_identity_mismatch')
    counts = result[['stable', 'changing', 'unknown']].to_numpy()
    if not (np.isfinite(counts).all() and (counts >= 0).all() and np.equal(counts, np.floor(counts)).all()
            and result.replicates.eq(200).all() and np.equal(counts.sum(axis=1), 200).all()):
        raise ValueError('invalid_replicate_counts')
    if not (np.allclose(result.stable_lower, result.stable / 200, rtol=0, atol=1e-12)
            and np.allclose(result.stable_upper, (result.stable + result.unknown) / 200, rtol=0, atol=1e-12)):
        raise ValueError('invalid_rate_bounds')
    groups = result.groupby(CURVE_KEYS, sort=False).k.agg(['min', 'max', 'count']).reset_index()
    expected = inventory.merge(result[CURVE_KEYS[2:]].drop_duplicates(), how='cross')
    expected = expected[expected.usable_n > expected.lookahead]
    groups = expected.merge(groups, on=CURVE_KEYS, how='outer', validate='one_to_one')
    if not (groups['min'].eq(1).all() and groups['max'].eq(groups.usable_n - groups.lookahead).all()
            and groups['count'].eq(groups['max']).all()):
        raise ValueError('incomplete_curve_nodes')
    return result.drop(columns='building_id_inventory')


def common_budget_curves(left_inventory, right_inventory, left, right):
    left = checked_curves(left_inventory, left)
    right = checked_curves(right_inventory, right)
    columns = ['image_id', 'building_id', 'usable_n']
    images = left_inventory[columns].merge(right_inventory[columns], on='image_id', how='outer',
        suffixes=('_with_workers', '_without_workers'), validate='one_to_one')
    if not images.building_id_with_workers.eq(images.building_id_without_workers).all():
        raise ValueError('building_identity_mismatch')
    images = images.rename(columns={'building_id_with_workers': 'building_id'}).drop(columns='building_id_without_workers')
    images['common_n'] = images[['usable_n_with_workers', 'usable_n_without_workers']].min(axis=1).astype(int)
    paired = left.drop(columns='usable_n').merge(right.drop(columns='usable_n'), on=CURVE_KEYS + ['k'],
        how='outer', suffixes=('_with_workers', '_without_workers'), validate='one_to_one')
    paired = paired.merge(images, on=['image_id', 'building_id'], validate='many_to_one')
    paired['common_k_max'] = paired.common_n - paired.lookahead
    paired = paired[paired.k <= paired.common_k_max].copy()
    if paired[['stable_lower_' + mode for mode in MODES]].isna().any().any():
        raise ValueError('missing_shared_curve_node')
    for mode in MODES:
        for name in ['replicates', 'stable', 'changing', 'unknown']:
            paired[name + '_' + mode] = paired[name + '_' + mode].astype(int)
    for bound in ['lower', 'upper']:
        paired[bound + '_difference'] = paired['stable_' + bound + '_without_workers'] - paired['stable_' + bound + '_with_workers']
    paired['difference_possible_lower'] = paired.stable_lower_without_workers - paired.stable_upper_with_workers
    paired['difference_possible_upper'] = paired.stable_upper_without_workers - paired.stable_lower_with_workers
    return images, paired.sort_values(CURVE_KEYS + ['k']).reset_index(drop=True)


def curve_onsets(curves):
    from tools.thesis_main.analysis.transfer_multibuilding_stability_20260909 import onset
    rows = []
    for key, group in curves.groupby(CURVE_KEYS, sort=False):
        group = group.sort_values('k')
        if group.k.tolist() != list(range(1, int(group.k.max()) + 1)):
            raise ValueError('incomplete_onset_nodes')
        possible, conservative, identified, status = onset(group.stable_lower, group.stable_upper)
        rows.append(dict(zip(CURVE_KEYS, key), people_budget=int(group.people_budget.iloc[0]),
            k_max=int(group.k.max()), possible_onset=possible, conservative_onset=conservative,
            identified_onset=identified, onset_status=status,
            onset_detail=('finite_interval' if status == 'unknown' and conservative is not None else status),
            mean_unknown_width=float((group.stable_upper - group.stable_lower).mean())))
    result = pd.DataFrame(rows)
    for column in ['possible_onset', 'conservative_onset', 'identified_onset']:
        result[column] = pd.to_numeric(result[column])
    return result


def imputation_sensitivity(mode_root, curves, inventory):
    """仅两图重算，其余图在几何完全相同的回读证据下复用。"""
    alternate = mode_root / 'no_imputation'
    affected = pd.read_csv(alternate / 'affected_replay/stability_curves.csv')
    affected_ids = set(affected.image_id)
    if affected_ids != {'q9vSo1VnCiC_9c9fb1fccf4e46a597a9510a1938c8b4',
                        'uNb9QFRL6hY_978d7a8eb0794936bd8fd092306e1dc5'}:
        raise ValueError('unexpected_imputation_sensitivity_images')
    alternate_inventory = pd.read_csv(alternate / 'image_inventory.csv')
    identity = ['image_id', 'building_id', 'usable_n']
    pd.testing.assert_frame_equal(inventory[identity].sort_values('image_id').reset_index(drop=True),
        alternate_inventory[identity].sort_values('image_id').reset_index(drop=True))
    reused_geometry = {}
    for filename, keys in [('response_geometry.csv', ['canonical_annotation_id']),
                           ('pairwise_q.csv.gz', ['image_id', 'left_canonical', 'right_canonical'])]:
        a = pd.read_csv(mode_root / 'geometry' / filename)
        b = pd.read_csv(alternate / 'geometry' / filename)
        a = a[~a.image_id.isin(affected_ids)].sort_values(keys).reset_index(drop=True)
        b = b[~b.image_id.isin(affected_ids)].sort_values(keys).reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b, check_exact=True)
        reused_geometry[filename] = len(a)
    if set(affected.columns) != set(curves.columns):
        raise ValueError('imputation_curve_schema_drift')
    unchanged = curves[~curves.image_id.isin(affected_ids)]
    merged = pd.concat([unchanged, affected[curves.columns]], ignore_index=True).sort_values(CURVE_KEYS + ['k'])
    checked_curves(alternate_inventory, merged)
    out = alternate / 'replay'; out.mkdir(exist_ok=True)
    merged.to_csv(out / 'stability_curves.csv', index=False)
    qa = dict(status='passed', operation='reuse_unchanged_geometry_and_replace_two_recomputed_images',
        full_image_n=int(inventory.usable_n.gt(0).sum()), recomputed_image_n=len(affected_ids),
        recomputed_image_ids=sorted(affected_ids), unchanged_geometry_image_n=int(inventory.usable_n.gt(0).sum())-len(affected_ids),
        reused_replay_image_n=unchanged.image_id.nunique(), reused_curve_rows=len(unchanged),
        recomputed_curve_rows=len(affected), combined_curve_rows=len(merged),
        exact_equal_unchanged_geometry_rows=reused_geometry,
        reused_curve_source=str(mode_root / 'replay/stability_curves.csv'),
        recomputed_curve_source=str(alternate / 'affected_replay/stability_curves.csv'),
        note='仅两张补点图重新执行全部配置和前缀。其余图几何响应字段和成对量逐值相同后复用曲线；无后续窗口图不产生曲线。此合并不是全部图重算。')
    (out / 'REUSE_QA.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    onset_rows, geometry_rows = [], []
    for point_view, source, frame in [('confirmed_additions', mode_root, curves), ('no_imputation', alternate, merged)]:
        selected = frame[frame.image_id.isin(affected_ids)].merge(inventory[identity],
            on=['image_id', 'building_id'], validate='many_to_one').rename(columns={'usable_n': 'people_budget'})
        onset_rows.append(curve_onsets(selected).assign(point_view=point_view))
        parts = pd.read_csv(source / 'geometry/full_q_partitions.csv')
        geometry_rows.append(parts[parts.image_id.isin(affected_ids)].assign(point_view=point_view))
    return pd.concat(onset_rows, ignore_index=True), pd.concat(geometry_rows, ignore_index=True), qa


def paired_review(paired_root):
    """对称回读两口径；重新截断共同预算，并复用原 transfer 计算共同预算对照。"""
    from tools.thesis_main.analysis.transfer_multibuilding_stability_20260909 import transfer
    paired_root = Path(paired_root)
    out = paired_root / 'comparison'; out.mkdir(parents=True, exist_ok=True)
    figs = out / 'figures'; figs.mkdir(exist_ok=True)
    inventories = {mode: pd.read_csv(paired_root / mode / 'image_inventory.csv') for mode in MODES}
    curves = {mode: pd.read_csv(paired_root / mode / 'replay/stability_curves.csv') for mode in MODES}
    images, paired = common_budget_curves(inventories[MODES[0]], inventories[MODES[1]], curves[MODES[0]], curves[MODES[1]])
    images.to_csv(out / 'image_support_comparison.csv', index=False)
    paired.to_csv(out / 'common_budget_curves.csv.gz', index=False)
    overview, thresholds, full_onsets, common_onsets, low_curves, transfer_summaries = [], [], [], [], [], []
    imputation_onsets, imputation_geometry, reuse_qa = [], [], {}
    common_inventory = images[['image_id', 'building_id', 'common_n']].rename(columns={'common_n': 'usable_n'})
    common_inventory['dense_ge16'] = common_inventory.usable_n.ge(16)
    for mode in MODES:
        inventory = inventories[mode]
        response = pd.read_csv(paired_root / mode / 'geometry/response_geometry.csv', dtype={'worker_id': str})
        parts = pd.read_csv(paired_root / mode / 'geometry/full_q_partitions.csv')
        if not (len(response) == inventory.usable_n.sum()
                and set(response.image_id) == set(inventory.loc[inventory.usable_n.gt(0), 'image_id'])):
            raise ValueError('geometry_inventory_mismatch')
        expected_n = inventory.set_index('image_id').usable_n
        observed_n = response.groupby('image_id').size()
        if not observed_n.eq(expected_n.loc[observed_n.index]).all():
            raise ValueError('geometry_image_count_mismatch')
        if (parts.duplicated(['image_id', 'threshold']).any() or parts.threshold.nunique() != 6
                or not parts.groupby('image_id').size().eq(6).all()
                or set(parts.image_id) != set(observed_n.index)
                or not parts.pointset_n.eq(parts.image_id.map(expected_n)).all()
                or not parts.pointset_n.eq(parts.q_valid_n + parts.q_invalid_n).all()
                or not parts.full_image_status.isin(['unique', 'non_unique', 'truncated', 'unknown_invalid_geometry']).all()):
            raise ValueError('partition_inventory_mismatch')
        if mode == 'without_workers' and response.worker_id.isin(['19', '26']).any():
            raise ValueError('excluded_worker_present')
        overview.append(dict(mode=mode, image_n=len(inventory), usable_image_n=int(inventory.usable_n.gt(0).sum()),
            usable_response_n=len(response), worker_n=response.worker_id.nunique(),
            dense_image_n=int(inventory.usable_n.ge(16).sum()), low_n_image_n=int(inventory.usable_n.between(1, 15).sum()),
            q_valid_n=int(response.q_geometry_valid.sum()), q_invalid_n=int((~response.q_geometry_valid).sum()),
            replay_image_n=curves[mode].image_id.nunique(), replay_curve_nodes=len(curves[mode])))
        for q, group in parts.groupby('threshold', sort=False):
            thresholds.append(dict(mode=mode, threshold=q, image_n=len(group), pointset_n=int(group.pointset_n.sum()),
                q_valid_n=int(group.q_valid_n.sum()), q_invalid_n=int(group.q_invalid_n.sum()),
                unique_images=int(group.full_image_status.eq('unique').sum()),
                nonunique_images=int(group.full_image_status.eq('non_unique').sum()),
                truncated_images=int(group.full_image_status.eq('truncated').sum()),
                invalid_geometry_images=int(group.full_image_status.eq('unknown_invalid_geometry').sum())))
        full = checked_curves(inventory, curves[mode]).rename(columns={'usable_n': 'people_budget'})
        imp_onsets, imp_geometry, reuse_qa[mode] = imputation_sensitivity(paired_root / mode, curves[mode], inventory)
        imputation_onsets.append(imp_onsets.assign(mode=mode)); imputation_geometry.append(imp_geometry.assign(mode=mode))
        full_onsets.append(curve_onsets(full).assign(mode=mode, budget_scope='own_full_n'))
        shared = paired[CURVE_KEYS + ['k', 'common_n'] + [name + '_' + mode for name in
            ['stable_lower', 'stable_upper', 'replicates', 'stable', 'changing', 'unknown']]].rename(columns={
                **{name + '_' + mode: name for name in ['stable_lower', 'stable_upper', 'replicates', 'stable', 'changing', 'unknown']},
                'common_n': 'people_budget'})
        common_onsets.append(curve_onsets(shared).assign(mode=mode, budget_scope='paired_common_n'))
        low = full[full.people_budget.between(1, 15) & full.lookahead.isin([1, 2, 3])
            & full.min_support.eq(2) & np.isclose(full.epsilon, .1)]
        low_summary = low.groupby(['people_budget', 'config', 'lookahead', 'k'], sort=False).agg(
            image_n=('image_id', 'nunique'), stable_lower=('stable_lower', 'mean'),
            stable_upper=('stable_upper', 'mean')).reset_index()
        low_curves.append(low_summary.assign(mode=mode, min_support=2, epsilon=.1))
        # Reuse the exact transfer rule with identical image inventory and budgets in both arms.
        transfer(common_inventory, shared[shared.image_id.isin(common_inventory.loc[
            common_inventory.dense_ge16, 'image_id'])], out / ('common_transfer_' + mode))
        transfer_summaries.append(pd.read_csv(out / ('common_transfer_' + mode) / 'building_summary.csv').assign(mode=mode))
        print(f'paired review {mode}: {len(full)} nodes; {len(common_onsets[-1])} common-budget onsets', flush=True)
    overview = pd.DataFrame(overview); overview.to_csv(out / 'overview.csv', index=False)
    pd.DataFrame(thresholds).to_csv(out / 'threshold_summary.csv', index=False)
    pd.concat(imputation_onsets, ignore_index=True).to_csv(out / 'imputation_affected_image_onsets.csv', index=False)
    pd.concat(imputation_geometry, ignore_index=True).to_csv(out / 'imputation_affected_q_partitions.csv', index=False)
    full_onsets = pd.concat(full_onsets, ignore_index=True); full_onsets.to_csv(out / 'own_budget_onsets.csv', index=False)
    common_onsets = pd.concat(common_onsets, ignore_index=True); common_onsets.to_csv(out / 'common_budget_onsets.csv', index=False)
    state_rows = []
    for (scope, mode, *params), group in pd.concat([full_onsets, common_onsets], ignore_index=True).groupby(
            ['budget_scope', 'mode'] + CURVE_KEYS[2:], sort=False):
        counts = inventories[mode].usable_n if scope == 'own_full_n' else images.common_n
        for cohort, valid in [('all_positive', counts.gt(0)), ('dense_ge16', counts.ge(16)), ('low_n_1_to15', counts.between(1, 15))]:
            subset = group if cohort == 'all_positive' else group[group.people_budget.ge(16)] if cohort == 'dense_ge16' else group[group.people_budget.between(1, 15)]
            row = dict(zip(CURVE_KEYS[2:], params), budget_scope=scope, mode=mode, cohort=cohort,
                inventory_image_n=int(valid.sum()), evaluable_window_image_n=len(subset),
                no_future_window_images=int(valid.sum())-len(subset))
            row.update({state + '_images': int(subset.onset_detail.eq(state).sum())
                for state in ['identified', 'finite_interval', 'unknown', 'not_reached']})
            assert sum(row[state + '_images'] for state in ['identified', 'finite_interval', 'unknown', 'not_reached']) == len(subset)
            assert row['no_future_window_images'] >= 0
            state_rows.append(row)
    pd.DataFrame(state_rows).to_csv(out / 'onset_state_summary.csv', index=False)
    onset_pair = common_onsets[common_onsets['mode'].eq(MODES[0])].drop(columns='mode').merge(
        common_onsets[common_onsets['mode'].eq(MODES[1])].drop(columns='mode'),
        on=CURVE_KEYS + ['people_budget', 'k_max', 'budget_scope'], suffixes=('_with_workers', '_without_workers'), validate='one_to_one')
    onset_pair.to_csv(out / 'common_onset_comparison.csv', index=False)
    pd.concat(low_curves, ignore_index=True).to_csv(out / 'low_n_short_window_curves.csv', index=False)
    support = pd.concat([inventory.groupby('usable_n').size().rename('image_n').reset_index().assign(mode=mode)
        for mode, inventory in inventories.items()], ignore_index=True)
    support.to_csv(out / 'people_count_distribution.csv', index=False)
    transfer_summary = pd.concat(transfer_summaries, ignore_index=True)
    transfer_summary.to_csv(out / 'common_transfer_summary.csv', index=False)
    for filename in ['baseline_groups.csv', 'target_image_onsets.csv']:
        a = pd.read_csv(out / ('common_transfer_' + MODES[0]) / filename)
        b = pd.read_csv(out / ('common_transfer_' + MODES[1]) / filename)
        cols = list(a.columns) if filename.startswith('baseline') else ['image_id', 'building_id', 'config', 'common_people_budget', 'k_max']
        pd.testing.assert_frame_equal(a[cols], b[cols])
    own_transfer_rows = []
    for mode in MODES:
        transfer_dir = paired_root / mode / 'transfer'
        completed = json.loads((transfer_dir / 'QA.json').read_text(encoding='utf-8'))
        summary = pd.read_csv(transfer_dir / 'building_summary.csv')
        if completed['status'] != 'passed' or len(summary) != completed['summary_rows']:
            raise ValueError('own_transfer_not_complete')
        own_transfer_rows.append(summary.assign(mode=mode))
    own_transfers = pd.concat(own_transfer_rows, ignore_index=True)
    own_transfers.to_csv(out / 'own_budget_transfer_summary.csv', index=False)
    low_paired = paired[paired.common_n.between(1, 15)]
    low_identical = all(low_paired[name + '_with_workers'].eq(low_paired[name + '_without_workers']).all()
        for name in ['stable', 'changing', 'unknown', 'stable_lower', 'stable_upper'])
    _paired_figures(images, paired, common_onsets, transfer_summary, pd.concat(low_curves, ignore_index=True), figs, low_identical)
    qa = dict(status='passed', modes=MODES, common_image_n=int(images.common_n.gt(0).sum()),
        common_curve_rows=len(paired), common_onset_rows=len(common_onsets), own_onset_rows=len(full_onsets),
        common_dense_image_n=int(common_inventory.dense_ge16.sum()), figures_generated=4, figures_visually_reviewed=0,
        no_imputation_curve_reuse=reuse_qa,
        low_n_common_curve_values_identical=low_identical,
        checks=['两侧原始曲线完整连续、各节点200次状态计数及上下界算术',
            '逐图共同预算=min(两侧人数)，仅比较k+h<=共同预算，并重新计算持续过线起点',
            '共同高人数图和相同楼内预算重新计算transfer，外楼组身份逐行相同',
            'N不足h+1时无窗口，人数库存仍保存；几何不可评价未静默删除'],
        definitions={'lower_difference': '不含两人下界−含两人下界；是边界之差，不能单独视为真实稳定率变化。',
            'difference_possible_lower_upper': '[不含两人下界−含两人上界，不含两人上界−含两人下界]；非置信区间。',
            'own_budget': '每侧使用自己的全部可观察人数；只描述，不据此直接声称排人改善。',
            'common_budget': '同图使用相同总人数预算；不同人员池仍不同，不能解释成已隔离个人因果效应。',
            'low_n': '各自N=1..15的支持分布；h1/2/3仅有限短窗口描述，N=1无后续验证。',
            'onset': '从该k起所有保存节点持续达到80%；有限窗口事后摘要，并非现实停止保证。'},
        files={'image_support_comparison.csv': '每张图一行，两侧N和共同N，包含无可用人数图。',
            'common_budget_curves.csv.gz': '共同可观察图×配置×h×m×epsilon×k；两侧状态计数、稳定上下界和差范围。',
            'own_budget_onsets.csv': '各口径×可观察图×配置×h×m×epsilon，各自全N下候选人数。',
            'common_budget_onsets.csv': '相同粒度，共同N截断后重新计算人数；mode对称呈现。',
            'common_onset_comparison.csv': '每图×参数同预算人数并列；无值保持空，不补零。',
            'onset_state_summary.csv': '预算口径×人员口径×参数×全正人数/高人数/低人数；库存分母、无后续窗口和四种人数状态单列。',
            'common_transfer_summary.csv': '共同高人数图、共同预算和外楼身份的楼×配置×源图数（含all）×口径。',
            'own_budget_transfer_summary.csv': '两侧各自原transfer汇总，可能预算不同。',
            'low_n_short_window_curves.csv': '口径×实际N(1..15)×配置×h1/2/3×k；m2/eps.1下图等权上下界。',
            'people_count_distribution.csv': '口径×可用N一行；包括N0和N1，没有窗口的图也保留。',
            'imputation_affected_image_onsets.csv': '两张补点图×人员口径×有/无补点×全部配置与h/m/epsilon；各自全N人数摘要。',
            'imputation_affected_q_partitions.csv': '两张补点图×人员口径×有/无补点×6q；完整与q有效子集状态、簇成员均保留。'},
        limits=['两侧没有预先指定主次，不以排人后更早稳定选口径或q。',
            '共同预算控制可观察长度，不控制人员组成；历史排列与图划分大量重叠。',
            '补点使用同图其他人信息，须另读无补点敏感性，不能算独立原始标注证据。',
            '低人数稳定仅检查很短的未来范围，不能等同于高人数h5或长期稳定。'])
    (out / 'QA.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(overview.to_string(index=False), flush=True)


def _paired_figures(images, paired, onsets, transfer_summary, low, figs, low_identical):
    plt.rcParams.update({'font.family': 'Microsoft YaHei', 'axes.unicode_minus': False, 'font.size': 10})
    main = paired[paired.config.eq('q_0.950') & paired.lookahead.eq(5)
        & paired.min_support.eq(2) & np.isclose(paired.epsilon, .1)]
    dense = images[images.common_n.ge(16)]
    groups = [(building, group) for building, group in dense.groupby('building_id') if len(group) >= 2]
    fig, axes = plt.subplots((len(groups)+1)//2, 2, figsize=(13, 3.1*((len(groups)+1)//2)), layout='constrained', squeeze=False)
    for ax, (building, group) in zip(axes.flat, groups):
        maximum = int(group.common_n.min()) - 5
        nodes = main[main.image_id.isin(group.image_id) & main.k.le(maximum)]
        assert nodes.groupby('k').size().eq(len(group)).all()
        for mode, linestyle, shade in zip(MODES, ['-', '--'], ['.1', '.5']):
            mean = nodes.groupby('k')[['stable_lower_' + mode, 'stable_upper_' + mode]].mean()
            ax.plot(mean.index, mean.iloc[:, 0], color=shade, linestyle=linestyle, label=MODE_LABELS[mode]+'下界')
            ax.fill_between(mean.index, mean.iloc[:, 0], mean.iloc[:, 1], color=shade, alpha=.12)
        ax.set(title=f'{building} · {len(group)}图 · 共同N={maximum+5}', ylim=(-.02, 1.02), xlabel='当前人数k', ylabel='稳定率范围')
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.grid(alpha=.15)
    for ax in list(axes.flat)[len(groups):]: ax.axis('off')
    axes.flat[0].legend(fontsize=8)
    fig.suptitle('含与不含W19/W26：共同图、共同人数预算的稳定曲线\nq=.95，h=5，m=2，容差10%；阴影表示未知范围，不是置信区间')
    fig.savefig(figs / 'paired_building_curves.png', dpi=160); plt.close(fig)
    select = onsets[onsets.config.eq('q_0.950') & onsets.lookahead.eq(5) & onsets.min_support.eq(2)
        & np.isclose(onsets.epsilon, .1) & onsets.people_budget.ge(16)]
    fig, ax = plt.subplots(figsize=(10, 4), layout='constrained')
    starts = np.zeros(2)
    for state, label, color, hatch in [('identified', '单一起点', '.25', ''), ('finite_interval', '有限非单点区间', '.5', '..'),
            ('unknown', '至少一端未定', '.8', '//'), ('not_reached', '窗口内未达到', '.95', '')]:
        values = [int(((select['mode'] == mode) & (select.onset_detail == state)).sum()) for mode in MODES]
        ax.barh(range(2), values, left=starts, color=color, edgecolor='.4', hatch=hatch, label=label)
        for y, n in enumerate(values):
            if n: ax.text(starts[y]+n/2, y, str(n), ha='center', va='center', color='white' if color == '.25' else 'black')
        starts += values
    ax.set(yticks=range(2), yticklabels=[MODE_LABELS[m] for m in MODES], xlabel='共同高人数图数')
    ax.legend(loc='upper center', bbox_to_anchor=(.5, -.15), ncol=2)
    fig.suptitle('相同逐图人数预算下的候选起点状态\nq=.95，h=5，m=2，容差10%；有限历史观察范围')
    fig.savefig(figs / 'paired_onset_states.png', dpi=170); plt.close(fig)
    select = transfer_summary[transfer_summary.config.eq('q_0.950') & transfer_summary.source_n.astype(str).eq('all')]
    buildings = sorted(select.building_id.unique())
    fig, ax = plt.subplots(figsize=(11, max(5, len(buildings)*.65)), layout='constrained')
    for mode, offset, color in zip(MODES, [-.15, .15], ['black', '.55']):
        group = select[select['mode'].eq(mode)].set_index('building_id').loc[buildings]
        ax.hlines(np.arange(len(buildings))+offset, group.same_error_lower, group.same_error_upper,
            color=color, linewidth=3, label=MODE_LABELS[mode])
        ax.scatter(group.same_error_lower, np.arange(len(buildings))+offset, color=color, s=13)
        ax.scatter(group.same_error_upper, np.arange(len(buildings))+offset, color=color, s=13)
    ax.set(yticks=range(len(buildings)), yticklabels=buildings, xlim=(0, 1), xlabel='同楼来源预测目标稳定曲线：绝对误差可行范围')
    ax.legend(); ax.grid(axis='x', alpha=.15)
    fig.suptitle('共同高人数图与共同楼内预算下的同楼预测误差\nq=.95，h=5，m=2，容差10%；范围不是置信区间，误差下界为0不表示准确')
    fig.savefig(figs / 'paired_transfer_errors.png', dpi=170); plt.close(fig)
    low = low[low.config.eq('q_0.950')]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.6), sharey=True, layout='constrained')
    for ax, h in zip(axes, [1, 2, 3]):
        # Only first eligible repeated-support prefix, with the exact N cohort held constant within each line.
        selected = low[low.lookahead.eq(h) & low.k.eq(2)]
        for mode, linestyle, shade in zip(MODES, ['-', '--'], ['.1', '.5']):
            group = selected[selected['mode'].eq(mode)].sort_values('people_budget')
            ax.plot(group.people_budget, group.stable_lower, linestyle=linestyle, marker='o', color=shade, label=MODE_LABELS[mode])
            ax.fill_between(group.people_budget, group.stable_lower, group.stable_upper, color=shade, alpha=.12)
        ax.set(title=f'已有k=2人，再看h={h}人', xlabel='该组图片实际总人数N', ylim=(-.02, 1.02))
        ax.set_xticks(sorted(selected.people_budget.unique()))
        ax.grid(alpha=.15)
    axes[0].set_ylabel('各N组内逐图平均稳定率范围'); axes[0].legend(fontsize=8)
    equality = '本轮两口径曲线相同；' if low_identical else '两口径分别按各自实际N分组；'
    fig.suptitle('低人数图的短窗口描述：q=.95，m=2，容差10%\n' + equality +
        '横轴是不同图片组，非同图加人轨迹；N<k+h不画点，不作长期稳定判断')
    fig.savefig(figs / 'low_n_short_windows.png', dpi=170); plt.close(fig)


def accepted_pairs(pairs, threshold):
    return (pairs.count_compatible & pairs.metric_compatible
            & pairs.pointwise_correspondence_compatible
            & pairs.q_boundary.ge(threshold - 1e-12)
            & pairs.q_wallwall.ge(threshold - 1e-12))


def visual_pairs(edges, out, figs):
    """按距离分位附近固定选三对；只显示原图与有效点，不构造墙线。"""
    with gzip.open(ROOT / 'analysis_results/confirmed_point_calculation_view_20260909_v1/calculation_view.jsonl.gz',
                   'rt', encoding='utf-8') as stream:
        records = {r['canonical_annotation_id']: r for r in map(json.loads, stream)}
    selected = []
    for number, (threshold, quantile) in enumerate([(.925, .5), (.925, .95), (.9, .5)], 1):
        pool = edges[edges.threshold_entered.eq(threshold)].copy()
        target = pool.ospa30.quantile(quantile)
        pool['selection_distance_gap'] = abs(pool.ospa30 - target)
        row = pool.sort_values(['selection_distance_gap', 'image_id', 'left_canonical', 'right_canonical']).iloc[0]
        a, b = records[row.left_canonical], records[row.right_canonical]
        assert a['image_id'] == b['image_id'] == row.image_id
        assert a['effective_point_count'] == b['effective_point_count']
        assert a['unassisted_manual_included'] and b['unassisted_manual_included']
        source = ROOT / 'data/mp3d_layout/img_v' / f'{row.image_id}.jpg'
        panorama = np.asarray(Image.open(source).convert('RGB'))
        fig = plt.figure(figsize=(14, 11.7), layout='constrained')
        grid = fig.add_gridspec(2, 2, height_ratios=[2, 1.15])
        axes = [fig.add_subplot(grid[0, :]), fig.add_subplot(grid[1, 0]), fig.add_subplot(grid[1, 1])]
        for ax in axes:
            ax.imshow(panorama, extent=[0, 1024, 512, 0]); ax.set(xlim=(0, 1024), ylim=(512, 0)); ax.axis('off')
        axes[0].set_title(f'示例{number} · 原图：{row.image_id}\n'
                          f'qBoundary={row.q_boundary:.5f}；qWallwall={row.q_wallwall:.5f}；OSPA30={row.ospa30:.3f}°\n'
                          f'{row.previous_stricter_threshold:g}→{threshold:g} 新兼容响应对，接近其距离分布{quantile:.0%}分位', fontsize=11)
        for ax, record, marker, label in zip(axes[1:], [a, b], ['o', 's'], ['A', 'B']):
            points = np.asarray(record['effective_points_1024x512'])
            ax.scatter(points[:, 0], points[:, 1], s=60, marker=marker, facecolors='white', edgecolors='black', linewidths=1.1)
            for index, (xx, yy) in enumerate(points):
                ax.annotate(str(index), (xx, yy), xytext=(4, 4), textcoords='offset points', fontsize=8,
                            bbox={'facecolor': 'white', 'edgecolor': 'none', 'pad': .3, 'alpha': .85})
            ax.set_title(f'{label} · W{record["worker_id"]} · 有效{len(points)}点\n'
                         f'{record["canonical_annotation_id"]}；点旁数字为有效点序的0基索引', fontsize=9)
        fig.suptitle('原图与两份有效点集；没有墙线、3D或布局对错判断', fontsize=13)
        filename = f'q_relaxation_pair_{number:02d}.png'
        fig.savefig(figs / filename, dpi=170); plt.close(fig)
        item = row.drop(labels=['selection_distance_gap']).to_dict()
        item.update(example_number=number, selected_quantile=quantile, target_ospa30=target,
                    selection_distance_gap=row.selection_distance_gap, pool_pair_n=len(pool),
                    selection_rule='新兼容区间内OSPA30最接近指定分位；相同差值按image/left/right canonical字典序，不按视觉选择。',
                    image_source=str(source.relative_to(ROOT)), image_width=panorama.shape[1], image_height=panorama.shape[0],
                    figure='figures/' + filename, left_effective_points_json=json.dumps(a['effective_points_1024x512']),
                    right_effective_points_json=json.dumps(b['effective_points_1024x512']),
                    left_raw_points_json=json.dumps(a['raw_points_1024x512']), right_raw_points_json=json.dumps(b['raw_points_1024x512']),
                    left_processing_status=a['processing_status'], right_processing_status=b['processing_status'],
                    visual_observation='pending', final_judgment='')
        selected.append(item)
    pd.DataFrame(selected).to_csv(out / 'visual_pair_examples.csv', index=False)
    return len(selected)


def replay_review():
    from tools.thesis_main.analysis.transfer_multibuilding_stability_20260909 import CONFIGS, onset
    out = BASE / 'review'; figs = out / 'figures'
    curves = pd.read_csv(BASE / 'replay/stability_curves.csv')
    inventory = pd.read_csv(BASE / 'image_inventory.csv').set_index('image_id')
    buildings = pd.read_csv(BASE / 'building_inventory.csv')
    keys = ['image_id', 'building_id', 'config', 'lookahead', 'min_support', 'epsilon']
    assert not curves.duplicated(keys + ['k']).any()
    assert curves.replicates.eq(200).all()
    assert curves[['stable', 'changing', 'unknown']].sum(axis=1).eq(200).all()
    assert np.allclose(curves.stable_lower, curves.stable / 200, atol=1e-12, rtol=0)
    assert np.allclose(curves.stable_upper, (curves.stable + curves.unknown) / 200, atol=1e-12, rtol=0)
    onset_rows = []
    for key, group in curves.groupby(keys, sort=False):
        group = group.sort_values('k')
        total = int(inventory.loc[key[0], 'usable_n'])
        assert group.k.tolist() == list(range(1, total - int(key[3]) + 1))
        possible, guaranteed, identified, status = onset(group.stable_lower, group.stable_upper)
        both_finite = possible is not None and guaranteed is not None
        assert not both_finite or possible <= guaranteed
        detailed = ('identified' if status == 'identified' else 'not_reached' if status == 'not_reached'
                    else 'finite_interval' if both_finite else 'endpoint_unknown')
        onset_rows.append(dict(zip(keys, key), pointset_n=total, rate=.8,
            k_max=int(group.k.max()), possible_onset=possible, guaranteed_onset=guaranteed,
            identified_onset=identified, onset_status=status, onset_detail_status=detailed,
            both_onset_endpoints_finite=both_finite,
            onset_interval_width=guaranteed - possible if both_finite else None,
            mean_unknown_width=float((group.stable_upper - group.stable_lower).mean())))
    onsets = pd.DataFrame(onset_rows)
    assert len(onsets) == 55 * 7 * 2 * 3 * 3
    assert set(onsets.image_id) == set(inventory[inventory.dense_ge16].index)
    assert set(onsets.config) == set(CONFIGS)
    onsets.to_csv(out / 'image_stability_onsets.csv', index=False)
    parameter_keys = ['config', 'lookahead', 'min_support', 'epsilon']
    summary_rows = []
    for key, group in onsets.groupby(parameter_keys, sort=False):
        identified = group.loc[group.onset_status.eq('identified'), 'identified_onset']
        summary_rows.append(dict(zip(parameter_keys, key), rate=.8, image_n=len(group),
            identified_images=int(group.onset_status.eq('identified').sum()),
            not_reached_images=int(group.onset_status.eq('not_reached').sum()),
            unknown_images=int(group.onset_status.eq('unknown').sum()),
            identified_onset_median=identified.median(), identified_onset_min=identified.min(),
            identified_onset_max=identified.max(), identified_onset_lt5_images=int(identified.lt(5).sum()),
            both_onset_endpoints_finite_images=int(group.both_onset_endpoints_finite.sum()),
            finite_interval_unknown_images=int(group.onset_detail_status.eq('finite_interval').sum()),
            endpoint_unknown_images=int(group.onset_detail_status.eq('endpoint_unknown').sum()),
            onset_interval_width_le2_images=int(group.onset_interval_width.le(2).sum()),
            guaranteed_onset_lt5_images=int(group.guaranteed_onset.lt(5).sum()),
            possible_onset_median=group.possible_onset.median(),
            guaranteed_onset_median=group.guaranteed_onset.median(),
            guaranteed_onset_min=group.guaranteed_onset.min(), guaranteed_onset_max=group.guaranteed_onset.max(),
            mean_unknown_width=group.mean_unknown_width.mean()))
    summary = pd.DataFrame(summary_rows)
    assert summary.image_n.eq(55).all()
    assert summary[['identified_images', 'not_reached_images', 'unknown_images']].sum(axis=1).eq(55).all()
    assert (summary.unknown_images == summary.finite_interval_unknown_images + summary.endpoint_unknown_images).all()
    assert (summary.both_onset_endpoints_finite_images == summary.identified_images + summary.finite_interval_unknown_images).all()
    summary.to_csv(out / 'stability_parameter_summary.csv', index=False)
    plt.rcParams.update({'font.family': 'Microsoft YaHei', 'axes.unicode_minus': False, 'font.size': 10})
    main = summary[(summary.lookahead == 5) & (summary.min_support == 2) & np.isclose(summary.epsilon, .1)]
    main = main.set_index('config').loc[CONFIGS]
    fig, ax = plt.subplots(figsize=(11.5, 5.8), layout='constrained')
    y = np.arange(len(CONFIGS)); left = np.zeros(len(y))
    for column, label, color, hatch in [('identified_images', '两端相同：单一起点', '.25', ''),
            ('finite_interval_unknown_images', '两端有限：起点区间', '.55', '..'),
            ('not_reached_images', '观察范围内未达到', '.8', '//'), ('endpoint_unknown_images', '保守端仍未定', '.95', '')]:
        values = main[column].to_numpy()
        ax.barh(y, values, left=left, label=label, color=color, edgecolor='.45', hatch=hatch)
        for yy, start, value in zip(y, left, values):
            if value: ax.text(start + value / 2, yy, str(value), va='center', ha='center',
                              color='white' if color == '.25' else 'black')
        left += values
    ax.set(yticks=y, yticklabels=[x.replace('q_', 'q=') if x.startswith('q_') else '无序点集 OSPA30≤6°' for x in CONFIGS],
           xlabel='图片数（每行固定55图）', xlim=(0, 55))
    ax.invert_yaxis(); ax.legend(loc='upper center', bbox_to_anchor=(.5, -.13), ncol=2)
    fig.suptitle('持续达到80%回放稳定率的候选人数与不确定范围\n后续窗口5人；支持门槛m=2；变化容差10%；有限区间另报，不等同于缺少上限')
    fig.savefig(figs / 'stability_onset_states.png', dpi=180); plt.close(fig)
    selected = curves[(curves.config == 'q_0.950') & (curves.lookahead == 5)
                      & (curves.min_support == 2) & np.isclose(curves.epsilon, .1)]
    eligible = buildings[buildings.cross_image_eligible].sort_values(['dense_image_n', 'building_id'], ascending=[False, True])
    assert len(eligible) == 10
    fig, axes = plt.subplots(5, 2, figsize=(13, 16), sharex=True, sharey=True, layout='constrained')
    building_curves = []
    for ax, row in zip(axes.flat, eligible.itertuples()):
        image_ids = json.loads(row.dense_image_ids_json)
        maximum = int(inventory.loc[image_ids, 'usable_n'].min()) - 5
        group = selected[selected.image_id.isin(image_ids) & selected.k.le(maximum)]
        assert group.groupby('k').size().eq(len(image_ids)).all()
        for _, image in group.groupby('image_id'):
            ax.plot(image.k, image.stable_lower, color='.7', linewidth=.7, alpha=.65)
        mean = group.groupby('k')[['stable_lower', 'stable_upper']].mean()
        ax.fill_between(mean.index, mean.stable_lower, mean.stable_upper, color='.8', alpha=.5)
        ax.plot(mean.index, mean.stable_lower, color='black', linewidth=2, label='逐图等权平均下界')
        ax.plot(mean.index, mean.stable_upper, color='black', linewidth=1.6, linestyle='--', label='逐图等权平均上界')
        ax.axhline(.8, color='.5', linestyle=':', linewidth=.8)
        ax.set_title(f'{row.building_id} · {len(image_ids)}图 · k≤{maximum}')
        ax.set(ylim=(-.025, 1.025), xticks=[1, 5, 10, 15, 20]); ax.grid(alpha=.15)
        mean = mean.reset_index(); mean['building_id'] = row.building_id; mean['image_n'] = len(image_ids)
        mean['common_k_max'] = maximum; building_curves.append(mean)
    for ax in axes[-1]: ax.set_xlabel('当前人数k（每个节点检查接下来5人）')
    for ax in axes[:, 0]: ax.set_ylabel('200次人员排列的稳定比例')
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='outside lower center', ncol=2)
    fig.suptitle('10栋楼的稳定率曲线：q=0.95，m=2，变化容差10%\n细灰线为各图下界；灰带为平均上下界差，表示未判定幅度，不是置信区间\n各楼始终保留全部高人数图，横轴截至楼内最小人数−5；楼间复用同一人员名单', fontsize=12)
    fig.savefig(figs / 'building_stability_curves_q095.png', dpi=180); plt.close(fig)
    pd.concat(building_curves, ignore_index=True).to_csv(out / 'building_stability_curves_q095.csv', index=False)
    qa_path = out / 'REVIEW_QA.json'
    qa = json.loads(qa_path.read_text(encoding='utf-8'))
    qa['replay_review'] = dict(status='passed', curve_rows=len(curves), onset_rows=len(onsets), parameter_rows=len(summary),
        rate=.8, onset_rule='从k开始所有后续保存节点均达到80%；upper与lower同一有限起点才identified；upper不存在起点为not_reached，其余unknown。',
        figures_generated=2, figures_visually_reviewed=0,
        schema={'image_stability_onsets.csv': '每图×7配置×2后续窗口×3支持门槛×3变化容差；6930行，未识别人数为空而非0。',
                'stability_parameter_summary.csv': '每配置×窗口×支持门槛×容差一行；状态数分母固定55图。原unknown拆有限但不同端点和保守端未定；宽<=2包含宽0；guaranteed<5统计保守端有限且<5的所有图，不限exact。',
                'building_stability_curves_q095.csv': '10楼，q.95/h5/m2/eps.1，每楼各k逐图等权平均L/U；固定楼内高人数图及共同k范围。'},
        checks=['完整140742节点状态数和L/U算术', '每图每配置参数的连续1..N-h节点', '55图×126参数组合覆盖', '126汇总行状态守恒55', '10楼共同节点均保留同一批图'],
        limits=['有限旧人员池回放，不证明新标注者在同一人数稳定。', 'k=1没有旧人对证据，早起点仍为后见窗口候选。',
                '不把unknown算作changing，不把上界当真实稳定率；平均带不是置信区间。'])
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(main[['identified_images', 'finite_interval_unknown_images', 'not_reached_images', 'endpoint_unknown_images',
                'both_onset_endpoints_finite_images', 'onset_interval_width_le2_images', 'guaranteed_onset_lt5_images',
                'guaranteed_onset_median', 'guaranteed_onset_min', 'guaranteed_onset_max']].to_string())


def main():
    out = BASE / 'review'; out.mkdir(exist_ok=True)
    figs = out / 'figures'; figs.mkdir(exist_ok=True)
    images = pd.read_csv(BASE / 'image_inventory.csv')
    buildings = pd.read_csv(BASE / 'building_inventory.csv')
    parts = pd.read_csv(BASE / 'geometry/full_q_partitions.csv')
    pairs = pd.read_csv(BASE / 'geometry/pairwise_q.csv.gz')
    responses = pd.read_csv(BASE / 'geometry/response_geometry.csv')
    thresholds = sorted(parts.threshold.unique(), reverse=True)
    assert len(thresholds) == 6 and not parts.duplicated(['image_id', 'threshold']).any()
    assert parts.groupby('image_id').size().eq(len(thresholds)).all()
    assert set(parts.image_id) == set(images.loc[images.dense_ge16, 'image_id'])
    assert len(responses) == images.loc[images.dense_ge16, 'usable_n'].sum()
    assert parts.groupby('image_id').pointset_n.nunique().eq(1).all()
    assert parts.groupby('image_id').q_valid_n.nunique().eq(1).all()
    assert (parts.pointset_n == parts.q_valid_n + parts.q_invalid_n).all()
    assert parts.complete_q_coverage.equals(parts.q_invalid_n.eq(0))
    complete_unique = parts.full_image_status.eq('unique')
    assert (~complete_unique | parts.complete_q_coverage).all()
    common_ids = parts.groupby('image_id').full_image_status.apply(lambda x: x.eq('unique').all())
    common_ids = sorted(common_ids[common_ids].index)
    common = parts[parts.image_id.isin(common_ids)].copy()
    common['singleton_share'] = common.singleton_clusters / common.pointset_n
    common['cluster_sizes_json'] = common.cluster_membership_json.map(
        lambda x: json.dumps(sorted(map(len, json.loads(x)), reverse=True)))
    for row in common.itertuples():
        groups = json.loads(row.cluster_membership_json)
        assert sum(map(len, groups)) == row.pointset_n
        assert row.cluster_count == len(groups)
        assert row.singleton_clusters == sum(len(g) == 1 for g in groups)
        assert row.supported_m2_clusters == sum(len(g) >= 2 for g in groups)
        assert row.supported_m3_clusters == sum(len(g) >= 3 for g in groups)
    common[['image_id', 'building_id', 'threshold', 'pointset_n', 'cluster_count',
            'supported_m2_clusters', 'supported_m3_clusters', 'singleton_clusters',
            'singleton_share', 'cluster_sizes_json']].to_csv(out / 'common_image_clusters.csv', index=False)
    full_summary = []
    for q, g in parts.groupby('threshold', sort=False):
        full_summary.append(dict(threshold=q, image_n=len(g), pointset_n=int(g.pointset_n.sum()),
            q_valid_n=int(g.q_valid_n.sum()), q_invalid_n=int(g.q_invalid_n.sum()),
            complete_geometry_images=int(g.complete_q_coverage.sum()),
            full_unique_images=int(g.full_image_status.eq('unique').sum()),
            full_nonunique_images=int(g.full_image_status.eq('non_unique').sum()),
            full_truncated_images=int(g.full_image_status.eq('truncated').sum()),
            geometry_unknown_images=int(g.full_image_status.eq('unknown_invalid_geometry').sum()),
            unique_q_subset_images=int(g.partition_status.eq('unique').sum()),
            accepted_pair_n=int(accepted_pairs(pairs, q).sum())))
    summary = pd.DataFrame(full_summary).sort_values('threshold', ascending=False)
    assert summary[['full_unique_images', 'full_nonunique_images', 'full_truncated_images',
                    'geometry_unknown_images']].sum(axis=1).eq(summary.image_n).all()
    summary.to_csv(out / 'full_threshold_summary.csv', index=False)
    metrics = ['cluster_count', 'supported_m2_clusters', 'supported_m3_clusters', 'singleton_share']
    common_summary = []
    for q, g in common.groupby('threshold', sort=False):
        row = dict(threshold=q, common_image_n=len(g), common_pointset_n=int(g.pointset_n.sum()))
        for col in metrics:
            row.update({col + '_mean': g[col].mean(), col + '_median': g[col].median(),
                        col + '_q25': g[col].quantile(.25), col + '_q75': g[col].quantile(.75)})
        row['singleton_response_fraction'] = g.singleton_clusters.sum() / g.pointset_n.sum()
        common_summary.append(row)
    common_summary = pd.DataFrame(common_summary).sort_values('threshold', ascending=False)
    common_summary.to_csv(out / 'common_image_summary.csv', index=False)
    edge_rows = []; edge_values = []; previous = pd.Series(False, index=pairs.index)
    for j, q in enumerate(thresholds):
        accepted = accepted_pairs(pairs, q)
        assert (~previous | accepted).all()
        added = pairs[accepted & ~previous].copy()
        added['threshold_entered'] = q
        added['previous_stricter_threshold'] = thresholds[j - 1] if j else np.nan
        edge_rows.append(added)
        distances = added.ospa30
        edge_values.append(dict(threshold=q, previous_stricter_threshold=thresholds[j - 1] if j else np.nan,
            added_pair_n=len(added), represented_image_n=added.image_id.nunique(),
            ospa30_mean=distances.mean(), ospa30_median=distances.median(),
            ospa30_p05=distances.quantile(.05), ospa30_p25=distances.quantile(.25),
            ospa30_p75=distances.quantile(.75), ospa30_p95=distances.quantile(.95),
            ospa30_max=distances.max(), image_mean_ospa30_mean=added.groupby('image_id').ospa30.mean().mean()))
        previous = accepted
    edges = pd.concat(edge_rows, ignore_index=True)
    assert not edges.duplicated(['image_id', 'left_canonical', 'right_canonical']).any()
    assert len(edges) == accepted_pairs(pairs, min(thresholds)).sum()
    edges.to_csv(out / 'newly_compatible_pairs.csv.gz', index=False)
    edge_summary = pd.DataFrame(edge_values)
    edge_summary.to_csv(out / 'newly_compatible_pair_summary.csv', index=False)
    plt.rcParams.update({'font.family': 'Microsoft YaHei', 'axes.unicode_minus': False, 'font.size': 10})
    b = buildings.sort_values(['dense_image_n', 'usable_n'], ascending=False)
    fig, axes = plt.subplots(1, 2, figsize=(12, 9), sharey=True, layout='constrained')
    y = np.arange(len(b))
    for ax, total, dense, title in [(axes[0], 'unassisted_image_n', 'dense_image_n', '无辅助图片数'),
                                  (axes[1], 'usable_n', 'dense_usable_n', '可用无辅助响应数')]:
        ax.barh(y, b[total], color='.85', edgecolor='.5', label='全部无辅助')
        ax.barh(y, b[dense], color='.25', label='每图至少16份可用响应')
        for yy, a, d in zip(y, b[total], b[dense]):
            ax.text(a + max(b[total]) * .02, yy, f'{d} / {a}', va='center', fontsize=9)
        ax.set_xlim(0, max(b[total]) * 1.25); ax.set_xlabel(title); ax.grid(axis='x', alpha=.15)
    axes[0].set_yticks(y, b.building_id); axes[0].invert_yaxis(); axes[0].legend(loc='lower right')
    fig.suptitle('22栋楼的无辅助标注支持（数字：高人数图部分 / 全部）\n高人数仅作样本支持筛选，所有阶段统一纳入')
    fig.savefig(figs / 'building_support.png', dpi=180); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout='constrained')
    x = np.arange(len(thresholds)); bottom = np.zeros(len(x))
    for col, label, color, hatch in [('full_unique_images', '完整图：唯一分区', '.25', ''),
            ('full_nonunique_images', '完整图：分区不唯一', '.6', '//'),
            ('full_truncated_images', '完整图：搜索截断', '.8', 'xx'),
            ('geometry_unknown_images', '含几何不可评价响应', '.93', '')]:
        v = summary[col].to_numpy()
        axes[0].bar(x, v, bottom=bottom, label=label, color=color, edgecolor='.4', hatch=hatch)
        for xx, low, height in zip(x, bottom, v):
            if height: axes[0].text(xx, low + height / 2, str(height), ha='center', va='center',
                                     color='white' if color == '.25' else 'black')
        bottom += v
    axes[0].set(xticks=x, xticklabels=[f'{q:g}' for q in thresholds], ylabel='图片数 / 55', xlabel='q门槛（向右放宽）', ylim=(0, 61))
    axes[0].legend(fontsize=8, loc='upper center', bbox_to_anchor=(.5, -.18), ncol=2)
    axes[1].barh([0], [len(responses)], color='.9', edgecolor='.5')
    axes[1].barh([0], [responses.q_geometry_valid.sum()], color='.35')
    axes[1].set(yticks=[], xlabel='可用无辅助响应数', xlim=(0, len(responses) * 1.03), ylim=(-1, 1))
    axes[1].text(0, .6, f'q几何可评价：{responses.q_geometry_valid.sum()} / {len(responses)}份\n完整几何覆盖：{summary.complete_geometry_images.iloc[0]} / 55图', fontsize=12)
    axes[1].text(0, -.65, '点集可计算，但q几何不可评价的响应仍保留在分母；\n仅可评价子集的唯一分区不能算整张图可判定。', fontsize=10)
    fig.suptitle('放宽q后的完整图分区状态与几何覆盖')
    fig.savefig(figs / 'threshold_coverage.png', dpi=180); plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.8), layout='constrained')
    for j, col in enumerate(metrics):
        ax = axes[0] if j == 0 else axes[1] if j in (1, 2) else axes[2]
        scale = 100 if col == 'singleton_share' else 1
        label = ['全部簇', '至少2人支持的簇', '至少3人支持的簇', '单例响应占比'][j]
        linestyle = '--' if j == 2 else '-'
        ax.plot(x, common_summary[col + '_median'] * scale, color='.05' if j != 2 else '.55',
                linestyle=linestyle, marker='o' if j != 2 else 's', label=label)
        ax.fill_between(x, common_summary[col + '_q25'] * scale, common_summary[col + '_q75'] * scale,
                        color='.8' if j != 2 else '.55', alpha=.3)
    for ax, ylabel in zip(axes, ['簇数', '得到重复支持的簇数', '单例响应占比（%）']):
        ax.set(xticks=x, xticklabels=[f'{q:g}' for q in thresholds], xlabel='q门槛（向右放宽）', ylabel=ylabel)
        ax.grid(alpha=.15); ax.legend(fontsize=9)
    fig.suptitle(f'固定{len(common_ids)}张图比较：六个q均具完整覆盖和唯一分区\n线为逐图中位数，阴影为逐图四分位范围；不代表全部55图')
    fig.savefig(figs / 'common_image_clusters.png', dpi=180); plt.close(fig)
    fig, ax = plt.subplots(figsize=(11, 5), layout='constrained')
    values = [edges.loc[edges.threshold_entered.eq(q), 'ospa30'].to_numpy() for q in thresholds]
    bp = ax.boxplot(values, whis=(5, 95), showfliers=False, patch_artist=True,
                    medianprops={'color': 'black'}, boxprops={'facecolor': '.8', 'edgecolor': '.3'},
                    whiskerprops={'color': '.3'}, capprops={'color': '.3'})
    labels = [f'≥{thresholds[0]:g}\n原有连边'] + [f'{q:g}≤q<{thresholds[j - 1]:g}' for j, q in enumerate(thresholds) if j]
    ax.set(xticks=np.arange(1, 7), xticklabels=labels, ylabel='无序球面点距 OSPA30（度）', xlabel='两项q的较小值区间；其余兼容条件均已满足')
    for j, row in enumerate(edge_summary.itertuples(), 1):
        ax.text(j, .98, f'{row.added_pair_n}对\n{row.represented_image_n}图', transform=ax.get_xaxis_transform(), ha='center', va='top', fontsize=9)
    ax.set_ylim(0, max(v.max() for v in values if len(v)) * 1.15); ax.grid(axis='y', alpha=.15)
    fig.suptitle('逐次放宽q新接纳的响应对：无序点集距离\n箱为25%–75%，须为5%–95%；连边不等于一定合入同一簇')
    fig.savefig(figs / 'newly_compatible_distances.png', dpi=180); plt.close(fig)
    example_n = visual_pairs(edges, out, figs)
    qa = dict(status='passed', source_image_n=55, common_complete_unique_image_n=len(common_ids),
        common_image_ids=common_ids, pointset_response_n=len(responses), q_valid_n=int(responses.q_geometry_valid.sum()),
        thresholds=thresholds, newly_compatible_pair_n=len(edges), figures_generated=4 + example_n, figures_visually_reviewed=0,
        pair_examples_generated=example_n, pair_examples_visually_reviewed=0,
        checks=['330分区的完整55图与6参数覆盖', '点集人数=可评价+不可评价人数', '完整唯一分区未使用缺失几何图',
                '共同图逐簇成员数、单例、m2/m3数量独立核对', '放宽q连边集合单调且始终要求硬点数/唯一对应', '新增连边首次进入区间唯一'],
        schema={'full_threshold_summary.csv': '每个q一行；full_*以55完整图为分母；unique_q_subset_images仅作子集状态描述，不是整图成功数。',
                'common_image_clusters.csv': '六参数全部完整唯一的固定图集，每图每q一行；singleton_share=单例响应数/该图全部可用响应数。',
                'common_image_summary.csv': '共同图逐图指标等权汇总，mean/median/q25/q75；singleton_response_fraction另按响应加权。',
                'newly_compatible_pairs.csv.gz': '每对响应只在首次通过六个q中某门槛时出现一次；第一档是最严q原有连边。',
                'newly_compatible_pair_summary.csv': '每个进入区间的OSPA30描述分布；所有点对等权，image_mean_ospa30_mean另对图等权。',
                'visual_pair_examples.csv': '3个机械选择的响应对，含分位/差值/源图/身份/原始和有效坐标；final_judgment留空，实际阅读记录另存VISUAL_NOTES.json。'},
        limits=['q仍依赖历史配对/边界连接假设，原始最终点序未保存。', '辅助OSPA距离不判断语义解释正确性，不据更少簇或更早稳定选择q。',
                '共同18图是可判定子集，不能推广至55图；重复点对/图/人员不是独立样本。'])
    (out / 'REVIEW_QA.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(summary.to_string(index=False))
    print(edge_summary.to_string(index=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replay-only', action='store_true')
    parser.add_argument('--paired-root', type=Path, help='包含with_workers和without_workers的修订输出目录')
    args = parser.parse_args()
    if args.paired_root:
        paired_review(args.paired_root)
    else:
        replay_review() if args.replay_only else main()
