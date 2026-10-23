#!/usr/bin/env python3
"""Check the six report topics against saved schemas, without using sample effects.

Formal files may be pending. A technical one-event table supplies a schema only;
its values are never copied into a report. This is a document-field check, not a
second research analysis or a gate for finishing the frozen fusion experiment.
"""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path
import pandas as pd


def main(root):
    root=Path(root).resolve();out=root/'integration';rows=[]
    def add(topic,purpose,file,fields,filters='',schema=None,code=None,identity='new_ABC_analysis'):
        file=Path(file);formal=root/file
        schema_path=formal if formal.exists() else root/schema if schema else None
        needed=fields.split('|');missing=[]
        if schema_path is not None and schema_path.exists() and schema_path.stat().st_size:
            if schema_path.suffix=='.json':
                available=set(json.loads(schema_path.read_text()))
            else:available=set(pd.read_csv(schema_path,nrows=0).columns)
            if file.name=='EXCLUDE_UNB_SPECIFIC.csv' and not formal.exists():
                # The one-building smoke sample has no leave-one-building rows.
                # Production reuses overall_row and appends excluded_building.
                common=schema_path.with_name('OVERALL_CONDITIONS.csv')
                available |= set(pd.read_csv(common,nrows=0).columns)
            missing=[x for x in needed if x not in available]
            status='formal_saved_header' if schema_path==formal else 'technical_schema_only_formal_pending'
            origin=str(schema_path.relative_to(root))
        elif code:
            text=(root/code).read_text()
            missing=[x for x in needed if x not in text]
            status='declared_in_implementation_formal_pending';origin=code
        else:
            missing=needed;status='unresolved';origin=''
        rows.append(dict(topic=topic,purpose=purpose,source_file=str(file),row_filters=filters,
            required_fields=fields,result_identity=identity,formal_file_present=formal.exists(),
            schema_check_source=origin,schema_status=status,missing_fields='|'.join(missing),
            schema_complete=not missing))

    sample='analysis/first_event_check/summaries/'
    add('1_纯混合与比例','主效应、支持与正向比例','results/OVERALL_CONDITIONS.csv',
        'subset|method|condition|pairs|Q_pairs|buildings|attempted_events|common6_Q_events|joint_QT_events|pair_equal__B8L2_within|pair_equal__B8L2_cross|pair_equal__B8L2_extra|building_equal__B8L2_extra|positive_Q_extra_pair_fraction|pair_equal__B8L2_CA|pair_equal__B8L2_CB',
        'V3_BEHAVIOR/manual; ordinary_all,pure,mixed,mixed_less_half,mixed_half,mixed_more_half',sample+'OVERALL_CONDITIONS.csv')
    add('1_纯混合与比例','真实n/m配置及共同支持','results/N_M_CONDITIONS.csv',
        'n|m|m_over_n|pairs|buildings|common6_Q_events|pair_equal__B8L2_extra|pair_equal__CA_loss_gt5_fraction|pair_equal__score_failure_fraction',
        '按subset/method/condition/n/m分别读取',sample+'N_M_CONDITIONS.csv')
    add('1_纯混合与比例','质量分项、结构与同语义时间','results/OVERALL_CONDITIONS.csv',
        'pair_equal__D10_CA|pair_equal__fusion_turn_n_CA|pair_equal__fusion_short_turn_edges_CA|pair_equal__fusion_redundancy_n_CA|pair_equal__S_bottom_deg_CA|pair_equal__dir_CA|pair_equal__height_mean_ratio_CA|pair_equal__QT_Q_CA|pair_equal__QT_time_ratio_CA|pair_equal__new_score_failure_CA|pair_equal__recovered_score_CA',
        '与主Q表同层；各分项使用自身共同支持',sample+'OVERALL_CONDITIONS.csv')
    add('1_纯混合与比例','对应角点距离、异数、失败','geometry_summary/GEOMETRY_CONDITIONS.csv',
        'support|six_unique_geometry_events|six_Q_and_geometry_events|pair_equal__geometry_bev_mean_h_extra|pair_equal__geometry_top_mean_h_extra|pair_equal__geometry_different_corner_count_extra',
        'all_geometry_diagnostics与joint_Q_and_geometry分开','analysis/first_event_check/geometry/GEOMETRY_CONDITIONS.csv')
    add('2_中文方向','方向贡献及实际人员覆盖','results/DIRECTION_RESULTS.csv',
        'source_role_key|target_role_key|source_role|target_role|source_workers|target_workers|actual_n_m|attempted_events|common6_Q_events|pair_equal__B8L2_CA|pair_equal__B8L2_CB|pair_equal__B8L2_extra|pair_equal__fusion_turn_n_CA|pair_equal__QT_time_ratio_CA',
        'method/condition/subset/role_key方向',sample+'DIRECTION_RESULTS.csv')
    add('2_中文方向','每折历史中心与成员','direction_tables/FOLD_DIRECTION_ROLES_MEMBERS.csv',
        'building|source_class|target_class|source_role_key|target_role_key|source_workers|target_workers|source_turn_history_mean|target_turn_history_mean|source_q_history_mean|target_q_history_mean|actual_n_m',
        '每楼外折原类；成员并集不是单队',identity='frozen_design_derived')
    add('2_中文方向','D组成、精确事件及成员','direction_tables/DIRECTION_BACKGROUND_MEMBER_INDEX.csv.gz',
        'background_coverage_id|n|m|D_class_counts|D_semantic_counts|D_exact_sets_json|event_ids|X_member_union|Y_member_union|Z_member_union',
        '同fold/方向/n/m/背景构成',identity='frozen_design_derived')
    add('3_固定锚点','固定A与背景路径的精确转移','anchor_paths/ANCHOR_PATH_TRANSITIONS.csv.gz',
        'path_transition_id|study_type|comparison_tags|fixed_A_endpoint_verified|m_small|m_large|n_small|n_large',
        'fixed_A_scale或fixed_XYZ_background',identity='frozen_design_derived')
    add('3_固定锚点','C变化、B变化、净变化及支持','anchor_paths/PATH_OVERALL_RESULTS.csv',
        'metric|study_type|comparison|source_role_key|target_role_key|pairs|buildings|attempted_transitions|common_transitions|pair_equal__C_change|pair_equal__B_change|pair_equal__net_C_minus_B_change|building_equal__net_C_minus_B_change|positive_pair_fraction__net_C_minus_B_change',
        'metric=B8L2等；ordinary_comparable=true','anchor_paths/validation/PATH_OVERALL_RESULTS.csv')
    add('3_固定锚点','失败与低尾真实分母','anchor_paths/PATH_FAILURE_LOWTAIL_PAIR_CONFIG.csv.gz',
        'm_small|m_large|n_small|n_large|score_failure_fraction12|incomplete_fraction12|Q_common12|QT_common12|B_Q_loss_gt5_fraction|C_Q_loss_gt5_fraction|C_new_score_failure_fraction|C_recovered_score_fraction|attempted_transitions',
        '全尝试与质量共同支持分开','anchor_paths/validation/PATH_FAILURE_LOWTAIL_PAIR_CONFIG.csv.gz')
    add('4_建筑成员','逐栋留一及uNb单列','results/EXCLUDE_UNB_SPECIFIC.csv',
        'excluded_building|subset|pairs|buildings|Q_pairs|pair_equal__B8L2_extra|building_equal__B8L2_extra|positive_Q_extra_pair_fraction',
        'excluded_building=uNb9QFRL6hY; mixed与mixed_less_half',sample+'EXCLUDE_UNB_SPECIFIC.csv')
    add('4_建筑成员','物理图对与声明组计权','results/OVERALL_CONDITIONS.csv',
        'pair_equal__B8L2_extra|building_equal__B8L2_extra|declaration_building__B8L2_extra|pairs|declared_groups',
        '每物理图对只一次；声明组按既有重叠事实',sample+'OVERALL_CONDITIONS.csv')
    add('4_建筑成员','逐人合法匹配支持与结果','sensitivity/MEMBER_MATCHED_SUMMARY.csv',
        'worker_id|matching|relevant_events|relevant_pairs|relevant_buildings|matched_pairs|matched_buildings|matched_Q_pairs|matched_Q_buildings|event_retention_fraction|status|matched_absent_positive_pair_fraction',
        'class_composition_background与exact_D分开',code='analysis/member_sensitivity.py')
    add('4_建筑成员','角色成员编号','sensitivity/MEMBER_FOLD_ROLES.csv',
        'worker_id|building|source_class|target_class|source_role|target_role',
        '接CLASS_ROLES_AND_MEMBERS保存family key',code='analysis/member_sensitivity.py')
    add('5_历史Q近域','子域真实人员重复量','history_q/HISTORY_Q_DOMAIN_SUPPORT.csv',
        'method|condition|threshold|matching|near_events|all_on_support_events|near_Q_events|all_on_support_Q_events|pairs|buildings|configurations|matched_strata|unique_near_Z_blocks|unique_near_XYZ_blocks|unique_near_D_sets',
        'threshold2/5; same_configuration与same_configuration_exact_D',code='analysis/history_q_common_support.py')
    add('5_历史Q近域','共同支持条件比较','history_q/HISTORY_Q_COMMON_SUPPORT_RESULTS.csv',
        'metric|valid_strata|configurations|pairs|buildings|near_events|all_on_support_events|positive_near_pair_fraction',
        'Q/结构/位置/几何各自有效支持；near与all_on_support嵌套',code='analysis/history_q_common_support.py')
    add('6_人数路径','自然曲线两种重抽','population_stability/results/KEY_NATURAL_INTERVALS.csv',
        'condition|layer|difficulty|panel|interval|metric|weighting|resampling|estimate|percentile_2_5|percentile_97_5|observed_images|observed_buildings|valid_bootstrap_draws',
        'manual/ordinary_manual/困难/fixed_pool_N_ge_20/10_to_20；均Q、P10、SD、failure',identity='saved_population_paths_reanalysis')
    add('6_人数路径','前段策略配对及建筑重抽','population_stability/results/KEY_POLICY_EARLY_EFFECTS.csv',
        'condition|layer|difficulty|policy|policy_support|panel|phase|metric|weighting|resampling|estimate|percentile_2_5|percentile_97_5|positive_image_fraction|observed_images|observed_buildings',
        'common_four_policy_pools；Manual/Semi分开',identity='saved_population_paths_reanalysis')
    add('6_人数路径','四策略同语义时间共同支持','population_stability/results/time_semantics/FOUR_POLICY_COMMON_TIME_EFFECTS.csv',
        'condition|layer|time_source_kind|policy|domain|metric|image_equal|building_equal|images|buildings|positive_image_fraction',
        '新来源普通Manual；本窄共同域未新bootstrap',identity='saved_population_paths_time_semantics_reaggregation')
    with (out/'REPORT_EVIDENCE_BINDINGS.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    # Existing personnel insert bindings are checked against actual table headers.
    checks=[]
    for r in csv.DictReader((out/'PERSONNEL_INSERTION_VALUE_BINDINGS.csv').open(encoding='utf-8-sig')):
        p=root/r['source_file'];actual=p.exists()
        if not actual:
            p=root/'analysis/first_event_check'/('summaries/'+p.name if p.suffix!='.json' else p.name)
        if p.exists():
            cols=set(json.loads(p.read_text())) if p.suffix=='.json' else set(pd.read_csv(p,nrows=0).columns)
            if p.name=='EXCLUDE_UNB_SPECIFIC.csv' and not actual:
                cols |= set(pd.read_csv(p.with_name('OVERALL_CONDITIONS.csv'),nrows=0).columns)
            ok=r['column_or_json_key'] in cols
        else:ok=False
        checks.append(dict(placeholder=r['placeholder'],source=r['source_file'],field=r['column_or_json_key'],
                           schema_verified=ok,formal_file_present=actual))
    receipt={'status':'schema_contract_only_not_formal_result_values','evidence_rows':len(rows),
      'all_report_fields_resolved':all(r['schema_complete'] for r in rows),
      'unresolved_report_fields':[r for r in rows if not r['schema_complete']],
      'personnel_insert_bindings':checks,'all_personnel_fields_resolved':all(r['schema_verified'] for r in checks),
      'pending_formal_files':sorted(set(r['source_file'] for r in rows if not r['formal_file_present'])),
      'no_sample_effect_values_used':True,'formal_output_paths_checked_against':'analysis/run_saved_analysis.py',
      'empty_technical_exclusion_schema':'One-building smoke input cannot have leave-one-building rows; its shared overall_row schema supplies the production columns. No effect value is inferred.',
      'new_fusion_calls':0}
    (out/'TEMPLATE_SCHEMA_CHECK.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['personnel_insert_bindings','pending_formal_files']},ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default=Path(__file__).resolve().parents[2])
    main(p.parse_args().root)
