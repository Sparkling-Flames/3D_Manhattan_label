"""只连接已交付结果并复核聚合；不运行融合、评分或分类拟合。"""
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / 'research/workers/personnel_v21_reselection_20261029'
OUT = ROOT / 'research/data/releases/v2.1/personnel_reselection_dependencies'
KEYS = ['method', 'condition', 'scope', 'role_direction', 'n']
ADDITIONAL_SOURCES = {
    'composition_manual': '03B_core/composition/primary_mixture_results/ALL45_ALL_METRICS_BOTH_SUPPORTS.csv',
    'composition_semi': '03C/composition/semi_mixture_results/COMMON_SUPPORT_ALL_METRICS.csv',
    'composition_other_targets': '03A/composition/stage03A_other_targets/ALL45_COMMON_SUPPORT_KEY_METRICS.csv',
    'fixed_XYZ_n_raw': '05B/analysis/global_size_paths/SIZE_PATH_RESULTS.csv.gz',
    'screen_frame': '05B/experiment/global_screen_capacity/SCREEN_POOL_FRAME.csv',
    'screen_events': '05A/experiment/global_screen_design/EVENTS_EXACT.csv.gz',
}


def resolve_saved_source(topic, previous_path, source=SRC):
    """新增包保持独立路径；缺文件时不回退到旧README或不存在的合并目录。"""
    if topic not in ADDITIONAL_SOURCES:
        return source / previous_path
    path = source / 'additional_delivery/packages' / ADDITIONAL_SOURCES[topic]
    if not path.is_file():
        raise FileNotFoundError(f'additional_delivery_source_missing: {topic}: {path}')
    return path


def read(path):
    return pd.read_csv(path, low_memory=False)


def hierarchy(frame, keys, metrics):
    pool = frame.groupby(keys + ['pool_id', 'image', 'building'], dropna=False)[metrics].mean().reset_index()
    image = pool.groupby(keys + ['image', 'building'], dropna=False)[metrics].mean().reset_index()
    building = image.groupby(keys + ['building'], dropna=False)[metrics].mean().reset_index()
    return image, building


def check_summary(frame, keys, mapping, summary):
    """独立按目标→图→楼聚合，并检查均值、有效及正向分母。"""
    errors = []
    image, building = hierarchy(frame, keys, list(mapping.values()))
    for unit, data in [('image', image), ('building', building)]:
        for prefix, metric in mapping.items():
            grouped = data.groupby(keys, dropna=False)[metric]
            calculated = grouped.agg(mean='mean', valid='count', positive=lambda v: (v > 1e-9).sum())
            for stat, suffix in [('mean', 'mean_' + unit), ('valid', 'valid_' + unit + 's'), ('positive', 'positive_' + unit + 's')]:
                col = prefix + '_' + suffix
                joined = calculated[[stat]].reset_index().merge(summary[keys + [col]], on=keys, validate='one_to_one', how='outer', indicator=True)
                assert joined['_merge'].eq('both').all(), col
                assert joined[stat].isna().equals(joined[col].isna()), col
                err = (joined[stat] - joined[col]).abs().max()
                assert pd.isna(err) or err < 1e-8, (col, err)
                errors.append(float(err) if pd.notna(err) else 0.)
    return {'groups': len(summary), 'checked_cells': len(summary) * len(mapping) * 6, 'max_error': max(errors)}


def main():
    receipt = json.loads((SRC / 'IMPORT_RECEIPT.json').read_text(encoding='utf-8'))
    assert receipt['all_other_csv_cells_preserved'] and not receipt['quality_values_changed']
    OUT.mkdir(parents=True, exist_ok=True)
    labels = read(SRC / 'classification/MAIN45_LABELS_ALL_LOBO.csv.gz')
    assert not labels.duplicated(['method', 'heldout_building', 'worker_id']).any()
    assert len(labels) == 64170 and labels.method.nunique() == 45
    folds = labels.groupby(['method', 'heldout_building'], dropna=False).agg(workers=('worker_id', 'nunique'), known=('known', 'sum')).reset_index()
    assert folds.workers.eq(62).all() and len(folds) == 45 * 23
    folds.to_csv(OUT / 'METHOD_FOLD_SUPPORT.csv', index=False)
    roles = read(SRC / 'classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz')
    assert not roles.duplicated(['method', 'heldout_building', 'class_id']).any()
    known = labels[labels.known.eq(True)]
    joined = known.merge(roles[['method', 'heldout_building', 'class_id']], on=['method', 'heldout_building', 'class_id'], how='left', validate='many_to_one', indicator=True)
    assert joined['_merge'].eq('both').all()
    checks = {'release': 'v2.1', 'label_rows': len(labels), 'role_join_rows': len(joined), 'native_fusion_runs': 0, 'scoring_runs': 0, 'classification_fits': 0}
    base = SRC / 'analysis/scale_background_summary'
    increments = read(base / 'FIXED_A_ALL_M_INCREMENT_METRICS.csv.gz')
    assert len(increments) == 10184 and not increments.duplicated(['path_id', 'm_small', 'm_large']).any()
    cap = increments[increments.m_small.eq(increments.min_registered_m) & increments.m_large.eq(increments.max_m)]
    assert len(cap) == 1947 and cap.path_id.is_unique
    mapping = {'Q_delta_' + name: 'B8L2_' + field + '_increment_matched_CB' for name, field in [('C', 'C'), ('B', 'B'), ('net_CB', 'net')]}
    for name, frame, keys in [('FIXED_M_PAIR', increments, KEYS + ['m_small', 'm_large']), ('CAPACITY_POLICY', cap, KEYS)]:
        checks[name] = check_summary(frame, keys, mapping, read(base / (name + '_CORE_SUMMARY.csv')))
    background = read(SRC / 'analysis/focused_contexts/FIXED_XYZ_BACKGROUND_CONTRASTS.csv.gz')
    checks['TARGET_BACKGROUND'] = check_summary(background, KEYS + ['m'], {'Q_delta_C': 'C_Q_change_matched_CB', 'Q_delta_B': 'B_Q_change_matched_CB', 'Q_delta_net_CB': 'net_CB_Q_change_matched_CB'}, read(base / 'TARGET_BACKGROUND_CORE_SUMMARY.csv'))
    policy_dir = SRC / 'composition/exact_small_pool_policies_OPPJOINT_K4'
    pairs = read(policy_dir / 'PAIRED_SAME_POOL_PREFIX_DIFFERENCES.csv.gz')
    pre = pairs[pairs.n.lt(pairs.pool_n)]
    policy_keys = ['method', 'policy', 'condition', 'metric', 'time_source']
    summary = read(policy_dir / 'POLICY_SUMMARY.csv').rename(columns={'mean_image': 'delta_mean_image', 'mean_building': 'delta_mean_building', 'images': 'delta_valid_images', 'buildings': 'delta_valid_buildings', 'positive_images': 'delta_positive_images', 'positive_buildings': 'delta_positive_buildings'})
    checks['SMALL_POOL_POLICY'] = check_summary(pre, policy_keys, {'delta': 'mean_minus_natural'}, summary)
    final = pairs[pairs.n.eq(pairs.pool_n)]
    assert final.mean_minus_natural.dropna().abs().lt(1e-8).all()
    checks['policy_full_pool_equal_rows'] = len(final)

    # 阶段03/05现已单独归档，不把新包代码覆盖到原07A执行目录。
    dependencies = []
    def add(topic, path, status, identity, action):
        p = resolve_saved_source(topic, path)
        dependencies.append(dict(topic=topic, source_path=p.relative_to(ROOT).as_posix(), delivered=p.exists(), status=status, method_identity=identity, next_action=action))
    for topic, path, status, identity, action in [
        ('labels', 'classification/MAIN45_LABELS_ALL_LOBO.csv.gz', 'ready', '45 methods; ALL descriptive + 22 LOBO folds', 'join by method/heldout_building/worker_id'),
        ('roles', 'classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz', 'ready', 'fold-specific role semantics', 'join by method/heldout_building/class_id; never align raw class IDs across folds'),
        ('composition_manual', '', 'ready_numeric_tables', '231 panels; shared-known 182 panels/38 images/22 buildings', 'consume stage03B_core tables; recomputation evidence in simulated_population_evidence/composition'),
        ('composition_semi', '', 'ready_numeric_tables', 'Semi own-label results separate from Manual', 'consume stage03C numeric tables and separate support'),
        ('composition_other_targets', '', 'ready_numeric_tables', 'other legal targets kept separate from primary targets', 'consume stage03A tables with target-specific support'),
        ('strict_ABC', 'experiment/focused_design/EVENTS_EXACT.csv.gz', 'ready', 'focused registered methods/n/m', 'use focused_summary with actual fold labels'),
        ('fixed_A_m', 'analysis/scale_background_summary/FIXED_A_ALL_M_INCREMENT_METRICS.csv.gz', 'ready_verified_aggregation', '1947 paths; 10184 increments; three methods', 'reuse fixed-A scalars; capacity mixture is not a single m pair'),
        ('background', 'analysis/focused_contexts/FIXED_XYZ_BACKGROUND_CONTRASTS.csv.gz', 'ready_verified_aggregation', 'same XYZ/n/m; actual D changes', 'use target-background tables separately'),
        ('fixed_XYZ_n_summary', 'analysis/scale_background_summary/FIXED_XYZ_N_PATH_CONTEXT.csv', 'ready_registered_summary', 'selected 166 method/condition/size rows', 'join registered stage05B paths; full evidence in simulated_population_evidence/exchange'),
        ('fixed_XYZ_n_raw', '', 'ready_registered_paths', 'all45 global size paths', 'consume stage05B saved paths; preserve fixed XYZ and changing background/n'),
        ('large_AC', 'analysis/direct_AC_combined_summary/EXACT_EVENTS_WITH_ROLES.csv.gz', 'ready', 'direct AC has no matched B requirement', 'keep separate from strict ABC'),
        ('within_parent', 'analysis/fine_increment/FIXED_PARENT_EVENT_METRICS.csv.gz', 'ready', 'fixed parent counts and fine-role exchanges', 'use exact parent map, actual common support'),
        ('small_policy', 'composition/exact_small_pool_policies_OPPJOINT_K4/POLICY_SUMMARY.csv', 'ready_verified_aggregation', 'OPPJOINT K4 exact small-pool marginal; not historical policy32', 'retain 14-image process support; full-pool equality'),
        ('screen_frame', '', 'ready_archived_frame', 'stage05B original screen frame', 'use exact frame for screen-membership checks; retain internal selection identity'),
        ('screen_events', '', 'ready_registered_events', 'stage05A exact global events', 'consume saved events; no new screen search'),
    ]:
        add(topic, path, status, identity, action)
    for part in range(1, 6):
        add(f'composition_manual_part_{part:02}',
            f'additional_delivery/packages/03B_{part:02}/composition/primary_manual45/by_method',
            'ready_numeric_tables', f'part {part} of 5; all 45 methods across the five parts',
            'read per-method counts/distributions/panel variance; paths indexed in composition SOURCE_INDEX')
    for topic, path, status, identity, action in [
        ('composition_manual_detail', 'simulated_population_evidence/composition/SOURCE_INDEX.csv', 'ready_source_index', 'actual per-method source paths, including all 45 Manual methods', 'select primary_manual45 rows; all paths point to independent stage03 package directories'),
        ('historical_policy32', 'current_policy_results/README.md', 'ready_historical_family', 'V3_BEHAVIOR/V3_JOINT_QT, not OPPJOINT', 'keep historical identity; new OPP ordering requires registered design and cache lookup'),
        ('same_room', 'same_room_current_results/README.md', 'ready_historical_family', 'current structure/joint labels preceding OPP adoption', 'retain original design; OPP strict blocks need new capacity check/design'),
        ('same_room_OPP_fixed_panels', 'same_room_oppjoint_fixed_panels/README.md', 'ready_fixed_panel_reaggregation', 'OPPJOINT K3/K4 on unchanged V3-selected finite teams', 'use common known and two-view outcome support; not newly selected strict ABC'),
        ('natural256', 'README.md', 'reuse_label_independent', 'natural arrival orders and fixed team Q/geometry', 'no rerun for classification-only change; regroup existing outputs if requested'),
    ]:
        p = OUT.parent / path
        dependencies.append(dict(topic=topic, source_path=p.relative_to(ROOT).as_posix(), delivered=p.exists(), status=status, method_identity=identity, next_action=action))
    dependencies.append(dict(topic='large_pool_OPP_policy', source_path='', delivered=False, status='new_design_required_no_result_found', method_identity='OPPJOINT LOBO priorities on fixed natural base orders', next_action='freeze folds/role order/common support; derive team keys; reuse endpoint cache; compute only missing teams; do not rename V3 policy32'))
    dependency_frame = pd.DataFrame(dependencies)
    with_source = dependency_frame.source_path.ne('')
    assert dependency_frame.loc[with_source, 'delivered'].all(), 'declared_source_not_delivered'
    dependency_frame.to_csv(OUT / 'DEPENDENCIES.csv', index=False)
    checks['dependency_source_rows'] = int(with_source.sum())
    checks['additional_source_files'] = len(ADDITIONAL_SOURCES)
    coverage = []
    for topic, path in [('strict_ABC', 'experiment/focused_design/EVENTS_EXACT.csv.gz'), ('fixed_A_m', 'analysis/scale_background_summary/FIXED_A_ALL_M_INCREMENT_METRICS.csv.gz'), ('large_AC', 'analysis/direct_AC_combined_summary/EXACT_EVENTS_WITH_ROLES.csv.gz'), ('within_parent', 'analysis/fine_increment/FIXED_PARENT_EVENT_METRICS.csv.gz'), ('background', 'analysis/focused_contexts/FIXED_XYZ_BACKGROUND_CONTRASTS.csv.gz')]:
        data = read(SRC / path)
        keys = [c for c in ['method', 'condition', 'scope', 'n', 'm'] if c in data]
        for values, group in data.groupby(keys, dropna=False):
            row = dict(zip(keys, values))
            row.update(topic=topic, source_path=(SRC / path).relative_to(ROOT).as_posix(), rows=len(group))
            for col in ['pool_id', 'image', 'building', 'path_id', 'event_id']:
                if col in group: row[col + '_count'] = group[col].nunique()
            coverage.append(row)
    pd.DataFrame(coverage).to_csv(OUT / 'SAVED_DESIGN_COVERAGE.csv', index=False)
    focused = read(SRC / 'analysis/focused_summary/ALL_DIRECTION_N_M_RESULTS.csv.gz')
    selections = [('OPPJOINT_K4', 12, 6, 'primary_joint'), ('OPPJOINT_K4', 20, 5, 'primary_joint'), ('TARGET_DSTRUCT_K3', 14, 7, 'structure_supplement'), ('RFUSE_GEOM_K2', 12, 4, 'reverse_inference_comparator')]
    adopted = []
    for method, n, m, use in selections:
        part = focused[focused.method.eq(method) & focused.n.eq(n) & focused.m.eq(m) & focused.condition.eq('manual') & focused.scope.eq('primary')].copy()
        assert len(part) == 1, (method, n, m)
        part['adopted_use'] = use
        part['source_path'] = (SRC / 'analysis/focused_summary/ALL_DIRECTION_N_M_RESULTS.csv.gz').relative_to(ROOT).as_posix()
        adopted.append(part)
    pd.concat(adopted).to_csv(OUT / 'ADOPTED_CONDITION_RESULTS.csv', index=False)
    checks['passed'] = True
    (OUT / 'CHECKS.json').write_text(json.dumps(checks, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(checks, ensure_ascii=False))


if __name__ == '__main__':
    main()
