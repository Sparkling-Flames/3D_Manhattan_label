"""Small wide result tables, figures and explicit delivery inventory."""
import sys as _delivery_sys
from pathlib import Path as _DeliveryPath
_delivery_root = next((p for p in _DeliveryPath(__file__).resolve().parents if (p / 'direct_io.py').is_file()))
_delivery_sys.path.insert(0, str(_delivery_root))
from direct_io import read_csv as _read_csv, open_data as _open_data, write_csv as _write_csv, write_bytes as _write_bytes, data_exists as _data_exists
from pathlib import Path
import argparse, json
import numpy as np, pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
MAIN = ['external_abs', 'own_source', 'public_source', 'public_external', 'public_external_halfown', 'public_external_halfclass', 'ridge_basic', 'hgb_continuous_own']
RISK = ['p_low_basic', 'p_low_calibrated_Q', 'p_low_basic_own', 'p_low_basic_class', 'p_low_basic_own_class']

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--out', type=Path, default=Path(__file__).parent)
    a = ap.parse_args()
    o = a.out
    pred = _read_csv(o / 'prediction_rows.csv.gz')
    keys = ['row_id', 'metric', 'budget', 'group_id', 'split_id', 'building', 'm', 'N', 'target_image', 'worker_id', 'target_object_id', 'source_n', 'actual']
    design = _read_csv(o / 'prediction_design.csv.gz')
    coverage = []
    missing = []
    for (metric, budget), g in pred.groupby(['metric', 'budget']):
        plan = design[design.budget == budget]
        bad = plan[~plan.row_id.isin(g.row_id)].copy()
        bad['metric'] = metric
        bad['missing_reason'] = 'external_person_history_unavailable_on_matched_support'
        missing.append(bad)
        coverage.append(dict(metric=metric, budget=budget, planned_rows=len(plan), evaluated_rows=len(g), missing_rows=len(bad), planned_target_answers=plan.target_object_id.nunique(), evaluated_target_answers=g.target_object_id.nunique(), images=g.target_image.nunique(), workers=g.worker_id.nunique(), buildings=g.building.nunique()))
    _write_csv(pd.DataFrame(coverage), o / 'prediction_coverage.csv', index=False)
    _write_csv(pd.concat(missing), o / 'prediction_missing_rows.csv', index=False)
    catalog = []
    for metric in ['B8L2', 'D10']:
        for method in [c for c in pred if c.startswith(('ridge_', 'hgb_', 'p_low_')) or c in MAIN]:
            fit = pred[pred.metric == metric][method].notna().any()
            catalog.append(dict(metric=metric, method=method, status='evaluated' if fit else 'not_run_for_this_metric_by_design', output='probability_Q_below50' if method.startswith('p_low_') else 'quality_score', missing_is_failure=False))
    _write_csv(pd.DataFrame(catalog), o / 'model_catalog.csv', index=False)
    _write_csv(pred[keys + MAIN + [c for c in RISK if c in pred]], o / 'main_prediction_rows_wide.csv.gz', index=False, float_format='%.7g')
    wt = _read_csv(o / 'prediction_worker_targets.csv.gz')
    keys = ['metric', 'budget', 'group_id', 'building', 'm', 'N', 'target_image', 'worker_id', 'target_object_id']
    selected = wt[wt.method.isin(MAIN)]
    wide = selected.pivot(index=keys, columns='method', values=['predicted', 'mae', 'bias', 'error_gt20'])
    wide.columns = ['__'.join(c) for c in wide.columns]
    common = selected.groupby(keys).agg(actual=('actual', 'first'), n_histories=('n_histories', 'first'), source_count=('source_count', 'first'))
    wide = common.join(wide).reset_index()
    _write_csv(wide, o / 'worker_target_all_budgets_wide.csv.gz', index=False, float_format='%.7g')
    parts = []
    for stage in ['minimum_majority', 'maximum_history', 'single_matched', 'single_direct']:
        if stage in ['minimum_majority', 'maximum_history']:
            z = wide[(wide.budget == 'majority') & (wide.m == (wide.N // 2 + 1 if stage == 'minimum_majority' else wide.N - 1))].copy()
        else:
            z = wide[wide.budget == stage].copy()
        z['stage'] = stage
        parts.append(z)
    _write_csv(pd.concat(parts), o / 'worker_target_endpoints_and_single_wide.csv.gz', index=False, float_format='%.7g')
    low = _read_csv(o / 'lowtail_worker_targets.csv.gz')
    lp = low.pivot(index=keys, columns='method', values=['prob', 'brier', 'logloss'])
    lp.columns = ['__'.join(c) for c in lp.columns]
    lp = low.groupby(keys).actual_low.first().to_frame().join(lp).reset_index()
    _write_csv(lp, o / 'lowtail_worker_budgets_wide.csv.gz', index=False, float_format='%.7g')
    groups = json.loads((a.repo / 'research/same_room/same_room_multiview_20261020/GROUPS.json').read_text())
    groups = [g for g in groups if g['metric'] == 'B8L2' and g['origin'] == 'all' and (g['layer'] == 'ordinary')]
    gmap = {g['group_id']: '|'.join((s[9:] for s in g['sources'] if s.startswith('original:'))) for g in groups}
    gi = pd.DataFrame([dict(group_id=g['group_id'], original_groups=gmap[g['group_id']], building=g['building'], N=g['N'], images='|'.join(g['images']), sources='|'.join(g['sources'])) for g in groups])
    _write_csv(gi, o / 'majority_group_index.csv', index=False)
    targets = _read_csv(o / 'prediction_targets.csv')
    target_main = targets[targets.method.isin(MAIN)]
    _write_csv(target_main, o / 'main_prediction_image_budgets.csv', index=False, float_format='%.7g')
    rec = _read_csv(o / 'formal_record_index.csv.gz')
    codes = rec.set_index('image_id').image_code.to_dict()
    z = target_main[(target_main.metric == 'B8L2') & (target_main.budget == 'majority') & (target_main.m == target_main.N - 1) & target_main.group_id.isin(['MV0001', 'MV0003', 'MV0007'])].copy()
    z['image_code'] = z.target_image.map(codes)
    z['original_group'] = z.group_id.map(gmap)
    _write_csv(z, o / 'selected_group_target_comparisons.csv', index=False)
    font = o.parent / 'NotoSansCJKsc-Regular.otf'
    if _data_exists(font):
        font_manager.fontManager.addfont(str(font))
        plt.rcParams['font.family'] = font_manager.FontProperties(fname=str(font)).get_name()
    sm = _read_csv(o / 'prediction_summary.csv')
    sm = sm[(sm.metric == 'B8L2') & (sm.budget == 'majority') & (sm.stage == 'maximum_history')].set_index('method')
    tail = _read_csv(o / 'actual_low_quality_diagnostic.csv')
    tail = tail[(tail.metric == 'B8L2') & (tail.budget == 'majority')].groupby('method').mae.mean()
    methods = ['external_abs', 'own_source', 'public_external', 'public_external_halfown', 'public_external_halfclass', 'ridge_basic', 'hgb_continuous_own']
    names = ['仅楼外个人 Q', '本人源 Q 均值', '公共源水平 + 楼外个人相对 Q', '再加半个本人剩余项', '再加半个同类剩余项', '楼外拟合的两项校准', '丰富连续画像 + 本人项（浅树）']
    colors = ['#aaa', '#6d99ad', '#1f6c88', '#ce8d3e', '#9e697d', '#76a4a1', '#8b8fbb']
    fig, axes = plt.subplots(1, 3, figsize=(14, 5.3), gridspec_kw={'width_ratios': [1.4, 1, 1.2]}, constrained_layout=True)
    for ax, values, title, lim in zip(axes, [sm.loc[methods].mae, sm.loc[methods].rho, tail.reindex(methods)], ['整体绝对 Q：MAE 越小越好', '每次实际历史：排序相关', '目标 Q<50：MAE 越小越好'], [(0, 18), (0, 0.5), (0, 32)]):
        ax.barh(range(len(methods)), values, color=colors)
        ax.set_yticks(range(len(methods)), names if ax is axes[0] else [''] * len(methods))
        ax.invert_yaxis()
        ax.set_xlim(*lim)
        ax.set_title(title, fontsize=11)
        ax.grid(axis='x', alpha=0.2)
        ax.set_axisbelow(True)
        for i, v in enumerate(values):
            ax.text(v + lim[1] * 0.012, i, f'{v:.3f}' if lim[1] < 1 else f'{v:.2f}', va='center', fontsize=9)
    fig.suptitle('同一目标支持，最高历史：平均精度、排序与低尾的收益不同\n普通 Manual，44 图，1385 份目标原答，7 栋建筑；仅内部留建筑检查', fontsize=13)
    fig.savefig(o / 'personal_prediction_tradeoffs_zh.png', dpi=180)
    plt.close(fig)
    ps = _read_csv(o / 'prediction_group_budget.csv')
    ps = ps[(ps.metric == 'B8L2') & (ps.budget == 'majority') & (ps.m == ps.N - 1)].pivot(index='group_id', columns='method', values='mae')
    fig, ax = plt.subplots(figsize=(9, 5), constrained_layout=True)
    y = np.arange(len(ps))
    ax.barh(y - 0.17, ps.public_external_halfown - ps.public_external, height=0.32, label='加入半个本人剩余项', color='#ce8d3e')
    ax.barh(y + 0.17, ps.public_external_halfclass - ps.public_external, height=0.32, label='加入半个同类剩余项', color='#9e697d')
    ax.set_yticks(y, [gmap.get(i, i) for i in ps.index])
    ax.axvline(0, color='#333', lw=0.8)
    ax.set_xlabel('相对公共源水平 + 楼外个人相对 Q 的 MAE 变化；负值为改善')
    ax.set_title('局部增量可以保留：G178/G057 与 G046/G205 的方向不同')
    ax.legend()
    fig.savefig(o / 'group_information_increment_zh.png', dpi=180)
    plt.close(fig)
    mat = _read_csv(o / 'declaration_common_matrix.csv.gz')
    focus = ['G046', 'G057', 'G090', 'G124', 'G178', 'G205']
    fig, axes = plt.subplots(2, 3, figsize=(16, 10), constrained_layout=True)
    for ax, gid in zip(axes.flat, focus):
        z = mat[(mat.condition == 'manual') & (mat.layer == 'ordinary') & (mat.group == gid)]
        pv = z.pivot(index='worker_id', columns='image_code', values='relative')
        pv = pv.reindex(z.groupby('worker_id').Q.mean().sort_values().index)
        im = ax.imshow(pv, vmin=-35, vmax=35, cmap='RdBu', aspect='auto')
        ax.set_xticks(range(len(pv.columns)), [c.split('-')[-1] for c in pv.columns])
        ax.set_yticks(range(len(pv)), pv.index, fontsize=7)
        ax.set_title(gid + '：个人 Q 减固定共同池的视角均 Q')
        ax.set_xlabel('视角编号')
    fig.colorbar(im, ax=axes, shrink=0.7, label='B8L2 相对差（完整数值见逐份矩阵）')
    fig.savefig(o / 'common_worker_view_relative_heatmap.png', dpi=170)
    plt.close(fig)
    include = ['REPORT_ZH.md', 'FIELD_CONTRACT.md', 'REPRODUCE.md', 'DESIGN_PRE_DATA.json', 'PROVENANCE.json', 'LOWTAIL_EXTENSION.json', 'analyze.py', 'summarize_descriptive.py', 'lowtail_competitors.py', 'lowtail_class_increment.py', 'finalize_outputs.py', 'extract_examples.py', 'direct_pair_index.csv', 'direct_pair_similarity.csv', 'direct_pair_workers_with_class.csv.gz', 'worker_repeatability.csv', 'information_decomposition_summary.csv', 'personal_similarity_by_building.csv', 'class_repetition_summary.csv', 'low_quality_transitions.csv', 'declaration_support.csv', 'declaration_variation_partition.csv', 'declaration_common_matrix.csv.gz', 'declaration_worker_effects.csv', 'prediction_design.csv.gz', 'main_prediction_rows_wide.csv.gz', 'worker_target_all_budgets_wide.csv.gz', 'lowtail_worker_budgets_wide.csv.gz', 'main_prediction_image_budgets.csv', 'prediction_group_budget.csv', 'prediction_buildings.csv', 'prediction_summary.csv', 'model_folds.csv', 'model_catalog.csv', 'prediction_coverage.csv', 'prediction_missing_rows.csv', 'ridge_parameters.json', 'lowtail_simple_parameters.json', 'lowtail_summary.csv', 'lowtail_buildings.csv', 'actual_low_quality_diagnostic.csv', 'majority_group_index.csv', 'selected_group_target_comparisons.csv', 'selected_person_cases.csv', 'selected_person_geometry.json', 'selected_worker_stability.csv', 'selected_worker_buildings.csv', 'personal_information_decomposition_zh.png', 'personal_prediction_tradeoffs_zh.png', 'group_information_increment_zh.png', 'common_worker_view_relative_heatmap.png']
    optional = ['prediction_rows.csv.gz', 'heldout_information.csv.gz', 'formal_record_index.csv.gz', 'prediction_worker_targets.csv.gz', 'prediction_targets.csv', 'lowtail_worker_targets.csv.gz', 'worker_target_endpoints_and_single_wide.csv.gz']
    manifest = dict(primary_files=include, optional_rebuildable_large_or_duplicate_files=optional, primary_total_MiB=sum(((o / f).stat().st_size for f in include if _data_exists(o / f))) / 1024 ** 2, note='Only primary_files should be integrated into the compact deliverable. Optional files are reproducible caches or duplicate layouts.')
    (o / 'DELIVERY_MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(manifest['primary_total_MiB'])
if __name__ == '__main__':
    main()
