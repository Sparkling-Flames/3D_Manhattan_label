"""Freeze compact reader-facing views of already completed experiments.

No team is fused and no model is fit. All rows retain their source stage,
population, direction, outcome denominator and building-bootstrap interval.
"""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
from multin_design import HERE, gs, sha, write_csv


def run():
    out = HERE / 'final_summary'
    out.mkdir(exist_ok=True)
    files, inputs = [], {}

    def source(relative):
        p = HERE / relative
        inputs[relative] = sha(p)
        return pd.read_csv(p, low_memory=False)

    def save(name, table):
        p = out / name
        write_csv(p, table)
        files.append(dict(path=str(p.relative_to(HERE)), rows=len(table),
                          columns=len(table.columns), bytes=p.stat().st_size,
                          sha256=sha(p)))

    main = source('matched/PANEL_OVERALL_CHECKPOINT.csv')
    main['stage'] = 'PANEL'
    strict = source('matched/STRICT_MATCHED_OVERVIEW.csv')
    all_strict = pd.concat([main, strict], ignore_index=True)
    selected_metrics = [
        'common_quality_within_abs', 'common_quality_cross_abs',
        'abs_Q_change_advantage', 'stable_advantage',
        'stable_D10_advantage', 'same_loss_gt10', 'cross_loss_gt10',
        'B_failure', 'C_failure', 'net_failure_difference',
        'common_geometry_advantage_floor_jaccard_difference',
        'common_geometry_advantage_mean_height_prism_pair_difference',
        'common_geometry_advantage_structure_bound_cyclic_deg',
        'common_geometry_advantage_centroid_distance_h',
        'common_expression_advantage_fusion_turn_n',
        'common_expression_advantage_fusion_short_turn_edges',
        'time_variation_advantage', 'same_recorded_time_pct',
        'cross_recorded_time_pct', 'same_B8L2', 'cross_B8L2',
        'same_D10', 'cross_D10',
    ]
    selected = all_strict[all_strict.metric.isin(selected_metrics)].copy()
    save('STRICT_MATCHED_COMPARISONS_LONG.csv', selected)
    keys = ['stage', 'method_id', 'tier', 'condition', 'source_domain',
            'design_scope', 'sensitivity']
    support = ['events', 'all_complete_events', 'all_scored_events', 'panels',
               'pools', 'images', 'buildings', 'n_min', 'n_max', 'm_min', 'm_max']
    rows = []
    for key, group in selected.groupby(keys, dropna=False):
        row = dict(zip(keys, key))
        row.update({k: group.iloc[0].get(k) for k in support})
        for _, record in group.iterrows():
            for value in ['mean', 'lo95', 'hi95', 'valid_events', 'valid_buildings']:
                row[record.metric + '__' + value] = record.get(value)
        rows.append(row)
    save('STRICT_MATCHED_COMPARISONS_WIDE.csv', pd.DataFrame(rows))

    directions = []
    for stage in ['PANEL', 'LARGE', 'PURE', 'PURE_CROSS']:
        d = source(f'direction/{stage}_DIRECTED_CORE_SUMMARY.csv')
        d['matched_same_class_arm'] = stage != 'PURE_CROSS'
        d['estimation_source_file'] = f'direction/{stage}_DIRECTED_CORE_SUMMARY.csv'
        directions.append(d)
    direction = pd.concat(directions, ignore_index=True)
    overall = direction[direction.view.eq('overall')].copy()
    save('DIRECTION_ALL_AXES_OVERALL.csv.gz', overall)
    axes = ((overall.method_id.eq('SP_scale') &
             overall.history_axis.isin(['area_history', 'height_history'])) |
            (~overall.method_id.eq('SP_scale') &
             overall.history_axis.isin(['turn_history', 'short_history'])))
    save('DIRECTION_MAIN_AXES_OVERALL.csv', overall[axes])
    focus = direction[
        direction.stage.isin(['pure', 'pure_cross']) &
        direction.method_id.eq('V3_BEHAVIOR') &
        direction.tier.eq('coarse') &
        direction.condition.eq('manual') &
        direction.source_domain.eq('all_formal') &
        direction.history_axis.eq('turn_history')
    ].copy()
    save('MANUAL_BEHAVIOR_PURE_DIRECTION_SUPPORT.csv', focus)

    path = source('paths/PATH_SUMMARY.csv')
    save('PATH_SUMMARY.csv', path)
    save('PATH_REGISTERED_STEP_SUMMARY.csv', path[path.scope.eq('registered_step')])

    contract = [
        ('B8L2 / D10', '分', '高更好', '沿用冻结评分及原有评分资格；失败不填零分。'),
        ('common_quality_within_abs / cross_abs', '分', '小表示变化小',
         'A/B/C均可评分的共同支持；不能将小变化解释为准确。'),
        ('abs_Q_change_advantage', '分', '正表示同构成变化较小',
         '同背景、同n、同实际m；跨构成绝对变化减同构成绝对变化。'),
        ('cross_B8L2 / cross_D10', '分', '正表示C比A高',
         '只在A、C均可评分时有效；方向均值与失败分别报告。'),
        ('B_failure / C_failure', '比例', '小更好',
         '分母为全部登记事件，包含below_four/invalid_floor/no_connection等；按层级建筑等权。'),
        ('cross_failure_difference', '比例', '负表示失败减少',
         'C_failure-A_failure，分母为全部事件；不是C失败率。'),
        ('same_loss_gt10 / cross_loss_gt10', '比例', '小更好',
         '分别仅AB或AC可评分配对为分母；不能和全失败率直接相加。'),
        ('stable_advantage', '比例', '正表示同构成联合稳定率高',
         '完整输出、|ΔQ|≤2、节点数相同、底面差≤.05、环序角差≤3度；稳定不代表正确。'),
        ('ref_node_recall_5 / ref_edge_recall_5', '比例', '高为参考结构召回更多',
         '冻结参考绑定和5度诊断；参考省略的真实细节不自动等同错误。'),
        ('omission / extension', '比例', '小表示参考遗漏或扩展误差少',
         '按冻结参考定义，正的cross变化为更多误差，不能反向解释。'),
        ('IoU3D100', '0至100代理分', '高更好',
         '沿用适用三维代理，不等于完整真实三维重建精度。'),
        ('fusion_turn_n', '个', '表达量，不定好坏',
         '输出节点减去近共线冗余（≤5度）；无GT正确性含义。'),
        ('fusion_short_turn_edges', '个', '表达量，不定好坏',
         '边长/周长<.04且两端转折≥15度；不改变融合或评分。'),
        ('common_geometry_*', '按字段', '小表示两份输出接近',
         'A/B/C均完整的共同支持；底面Jaccard、平均高棱柱、质心、环序、面积分别保留。'),
        ('*_recorded_time_pct / *_abs_log_time', '百分比 / 对数比', '按质量时间取舍解释',
         '只有全员时间已知、单一且可比来源才有效；ABC比较还要求三臂同样具备资格。'),
        ('source_time_increase_pct / comparable_source_time_difference_seconds', '百分比 / 秒',
         '路径记录时间代价', '仅time_comparable路径；不是由模型误差改善推算工时。'),
        ('raw *_source_time_total_seconds / *_target_time_total_seconds / *_source_parallel_active_seconds / *_source_log_time_ratio',
         '秒 / 对数比', '原始来源字段',
         '完整事件及旧式全分项汇总保留来源字段；若未套全员时间已知与同源资格，不作效率结论。最终报告只用qualified时间字段。'),
        ('history_*_change', '楼外标准表达', '换入减换出',
         '同条件其他建筑历史特征，缺机会未知；不把跨楼S/J数字标签当作同一角色。'),
    ]
    save('METRIC_CONTRACT.csv', pd.DataFrame(contract, columns=[
        'field_family', 'unit', 'interpretation', 'denominator_and_scope']))

    scope = dict(
        status='frozen_completed_experiments',
        endpoint_stage_references=360681, global_unique_endpoint_sets=360676,
        cross_stage_duplicate_references=5, historically_unseen_new_sets=360621,
        historical_geometry_restored_sets=6, unique_old_exact_reused_sets=49,
        requested_endpoint_results_missing=0,
        main_panels=336, complete_member_sets_per_main_panel=924,
        main_unique_teams=310458, main_strict_events=65371,
        original_large_unique_teams=38957, original_large_strict_events=16244,
        pure_stage_unique_teams=9392, pure_strict_events=1899,
        pure_cross_only_events=2056, f01_finite_census_teams=1874,
        f01_finite_census_images=14, f01_no_choice_singleton_images=2,
        nested_path_edges=195888, nested_variable_paths=114576,
        canonical_class_count_configurations=386587,
        canonical_domain_n_strata=4016, all_n_ledger_rows=24661,
        all_n_actual_known_domains=869,
        selected_full_formal_pool_nonempty_member_set_universe='916199492812738',
        selected_full_formal_pool_historical_plus_new_computed_sets=506993,
        full_global_member_enumeration=False, all_joining_orders_enumerated=False,
        principal_completion_receipts=[
            'delivery/ENDPOINT_DELIVERY_MANIFEST.json',
            'configuration_union/COMPLETION.json',
            'configuration_union/ALL_N_LEDGER_COMPLETE.json',
            'paths/PATH_COMPLETION.json',
        ],
        no_new_native_calls_or_candidate_selection_in_this_freeze=True,
        whole_class_seats='PURE and PURE_CROSS have class seat transfer equal to actual m; LARGE need not.',
        uncertainty='Hierarchical equal building means, 2000 building-bootstrap draws where at least three valid buildings. Repeatedly explored data, not a new external blind test.',
    )
    gs.save(out / 'FINAL_SCOPE.json', scope)
    files.append(dict(path='final_summary/FINAL_SCOPE.json', sha256=sha(out/'FINAL_SCOPE.json'),
                      bytes=(out/'FINAL_SCOPE.json').stat().st_size))
    receipt = dict(status='complete', inputs=inputs, files=files,
                   native_calls=0, new_statistical_fits=0,
                   raw_timing_columns_excluded_from_efficiency_claims=True)
    gs.save(out/'SUMMARY_FREEZE.json', receipt)
    print(json.dumps(receipt, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    run()
