#!/usr/bin/env python3
"""Compact tables, support checks and readable report for exact-layer response CV."""
from __future__ import annotations
import argparse
from collections import Counter
import gzip
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd

import team_continuous_check as core


def table(df):
    # Keep the deliverable reproducible without an optional tabulate dependency.
    def cell(v):
        if pd.isna(v):return '—'
        s=format(float(v),'.6g') if isinstance(v,(float,np.floating)) else str(v)
        return s.replace('|','\\|').replace('\n','; ')
    lines=['| '+' | '.join(map(str,df.columns))+' |','| '+' | '.join('---' for _ in df.columns)+' |']
    lines+=['| '+' | '.join(cell(v) for v in row)+' |' for row in df.itertuples(index=False,name=None)]
    return '\n'.join(lines)


def class_opportunities(out,summary):
    support=pd.read_csv(out/'TEAM_RESPONSE_TARGET_SUPPORT.csv.gz')
    folds=pd.read_csv(out/'TEAM_RESPONSE_FOLD_MAPS.csv.gz')
    keys=['method_id','condition','heldout_building','support_scope']
    assert folds.groupby(keys).outer_variable_workers.nunique().max()==1
    folds=folds[keys+['outer_variable_workers']].drop_duplicates()
    support=support.merge(folds,on=keys,how='left',validate='many_to_one')
    labelmaps,catalog=core.label_maps(pd.read_csv(core.COMP/'FROZEN_LABELS.csv',keep_default_na=False))
    pools=json.load(gzip.open(core.SNAPSHOT,'rt'))['images']
    members={p['pool_id']:set(r['worker_id'] for r in p['records']) for p in pools}
    rows=[]
    for r in support.itertuples():
        variable=set(str(r.outer_variable_workers).split('|'))&members[r.pool_id]
        assert len(variable)==int(r.variable_workers)
        mapping=labelmaps[r.method_id,r.condition,r.heldout_building]
        counts={tier:Counter(mapping[tier][w] for w in variable) for tier in ['coarse','fine']}
        configs={}
        for tier,c in counts.items():
            configs[tier]=len(c) if r.deletions==1 else math.comb(len(c),2)+sum(n>=2 for n in c.values())
        rows.append({k:getattr(r,k) for k in ['method_id','condition','heldout_building','support_scope','size_stratum','layer','pool_id','image_id','N','n','deletions','variable_workers','fixed_background_workers','restricted_exact_sets']}|
            {'coarse_variable_class_counts':json.dumps(counts['coarse'],sort_keys=True),
             'fine_variable_class_counts':json.dumps(counts['fine'],sort_keys=True),
             'coarse_configuration_count':configs['coarse'],'fine_configuration_count':configs['fine'],
             'coarse_configuration_contrast_exists':configs['coarse']>=2,
             'fine_configuration_contrast_exists':configs['fine']>=2,
             'fine_creates_additional_configurations':configs['fine']>configs['coarse'],
             'configuration_support_scope':'complete_restricted_member_layer_before_outcome_filtering',
             'has_distinct_fine_definition':mapping['has_fine']})
    detail=pd.DataFrame(rows)
    core.save(detail,'TEAM_RESPONSE_CLASS_CONTRAST.csv.gz',out)
    group=['method_id','condition','support_scope','deletions','size_stratum','layer']
    agg=detail.groupby(group,as_index=False).agg(buildings=('heldout_building','nunique'),images=('image_id','nunique'),
        pools=('pool_id','size'),restricted_exact_sets=('restricted_exact_sets','sum'),
        coarse_contrast_pools=('coarse_configuration_contrast_exists','sum'),fine_contrast_pools=('fine_configuration_contrast_exists','sum'),
        additional_fine_configuration_pools=('fine_creates_additional_configurations','sum'))
    core.save(agg,'TEAM_RESPONSE_CLASS_CONTRAST_SUMMARY.csv',out)
    return agg


def validate(out,summary,ledger,stage1):
    keys=['method_id','condition','support_scope','family','deletions','size_stratum','layer','outcome']
    cohort=summary.groupby(keys)[['buildings','images','pools','endpoints','variable_pools']].nunique()
    assert cohort.max().max()==1,'different model comparison supports'
    common=summary[summary.support_scope.ne('own_supported')]
    q=common[common.model.isin(['source','QT_source','QT_moments_source'])]
    k=['condition','support_scope','family','deletions','size_stratum','layer','outcome','model']
    spread=q.groupby(k).mse.agg(lambda v:float(v.max()-v.min()))
    assert spread.max()<1e-11,'common-family continuous baselines differ'
    evaluated=ledger[ledger.status.eq('evaluated')].copy()
    expected=evaluated.groupby([v for v in keys if v!='method_id'],as_index=False).agg(
        endpoints=('outcome_available_member_sets','sum'),pools=('pool_id','size'),
        images=('image_id','nunique'),buildings=('heldout_building','nunique'),variable_pools=('target_outcome_varies','sum'))
    group=[v for v in keys if v!='method_id']
    actual=summary[summary.model.eq('QT_source')].drop_duplicates(group)
    matched=expected.merge(actual,on=group,how='outer',suffixes=('_expected','_actual'),indicator=True)
    assert matched._merge.eq('both').all(),'evaluated ledger and fitted population differ'
    for c in ['endpoints','pools','images','buildings','variable_pools']:
        assert np.allclose(matched[c+'_expected'],matched[c+'_actual']),c
    folds=pd.read_csv(out/'TEAM_RESPONSE_FOLD_MAPS.csv.gz',keep_default_na=False)
    assert all(r.heldout_building not in r.available_train_buildings.split('|') for r in folds.itertuples())
    assert folds.label_map_applied_to_train_and_test.eq('same_target_building_excluded_map').all()
    fits=pd.read_csv(out/'TEAM_RESPONSE_FIT_SUPPORT.csv.gz')
    assert not fits.target_outcome_used_for_fit.any() and not fits.target_feature_scale_used.any()
    oldcheck=None
    if stage1.exists():
        old=pd.read_csv(stage1);new=summary[summary.deletions.eq(1)]
        joint=old.merge(new,on=keys+['model'],how='outer',suffixes=('_stage1','_final'),indicator=True)
        assert joint._merge.eq('both').all()
        discrepancy=float(abs(joint.mse_stage1-joint.mse_final).max())
        assert discrepancy<1e-10,'N-1 result changed after appending N-2 endpoints'
        oldcheck={'matched_rows':len(joint),'maximum_absolute_mse_change':discrepancy}
    receipt={'all_model_supports_equal':True,'common_support_QT_maximum_absolute_mse_spread':float(spread.max()),
        'eligibility_ledger_matches_all_actual_evaluated_denominators':True,'denominator_comparisons':len(matched),
        'target_building_never_in_coefficient_training':True,'one_b_excluded_map_for_all_source_and_target_pools':True,
        'no_target_outcome_or_target_scaling_fit':True,'N1_reproduction_after_N2_append':oldcheck}
    core.js(out/'TEAM_RESPONSE_CHECKS.json',receipt)
    return receipt


def reverse_matched_existing(out):
    """Reuse already fitted rows when full outer variable maps match exactly.

    Adding F01 can destroy the Rnew2 contrast. The modern joint panel and
    Rnew2's own panel instead match on 11 original target buildings. The
    unmatched fold is retained explicitly, not treated as matched or refitted.
    """
    folds=pd.read_csv(out/'TEAM_RESPONSE_FOLD_MAPS.csv.gz')
    cols=['heldout_building','outer_variable_workers']
    modern=folds[folds.method_id.eq('M_structure')&folds.support_scope.eq('common_modern')][cols].drop_duplicates()
    reverse=folds[folds.method_id.eq('Rnew2')&folds.support_scope.eq('own_supported')][cols].drop_duplicates()
    check=reverse.merge(modern,on='heldout_building',how='left',suffixes=('_reverse','_modern'),validate='one_to_one')
    check['identical_full_outer_variable_map']=check.outer_variable_workers_reverse.eq(check.outer_variable_workers_modern)
    check['reason']=np.where(check.identical_full_outer_variable_map,'exact_existing_fit_support_match','outer_worker_map_differs;excluded_from_paired_comparison')
    core.save(check,'TEAM_RESPONSE_RNEW2_MATCHING_LEDGER.csv',out)
    allowed=set(check.loc[check.identical_full_outer_variable_map,'heldout_building'])
    d=pd.read_csv(out/'TEAM_RESPONSE_BUILDINGS.csv.gz')
    take=((d.support_scope.eq('common_modern')&d.method_id.isin(core.MODERN_MANUAL))|
          (d.support_scope.eq('own_supported')&d.method_id.eq('Rnew2')))
    d=d[take&d.condition.eq('manual')&d.layer.eq('ordinary_manual')&d.heldout_building.isin(allowed)].copy()
    q=d[d.model.isin(['source','QT_source','QT_moments_source'])]
    k=['heldout_building','deletions','size_stratum','outcome','model']
    assert q.groupby(k).method_id.nunique().eq(len(core.MODERN_MANUAL)+1).all()
    assert q.groupby(k).endpoints.nunique().eq(1).all()
    maxspread=float(q.groupby(k).mse.agg(lambda v:v.max()-v.min()).max())
    assert maxspread<1e-11
    d['original_support_scope']=d.support_scope;d['support_scope']='matched_existing_Rnew2'
    d['family']='|'.join(core.MODERN_MANUAL+['Rnew2'])
    core.save(d,'TEAM_RESPONSE_RNEW2_MATCHED_BUILDINGS.csv.gz',out)
    group=['method_id','condition','support_scope','family','deletions','size_stratum','layer','outcome','model','has_distinct_fine_definition']
    s=d.groupby(group,as_index=False).agg(mse=('mse','mean'),mae=('mae','mean'),null_mse=('null_mse','mean'),
        buildings=('heldout_building','size'),endpoints=('endpoints','sum'),pools=('pools','sum'),images=('images','sum'),variable_pools=('variable_pools','sum'))
    s['R2_vs_finite_pool_mean']=np.where(s.null_mse>1e-12,1-s.mse/s.null_mse,np.nan)
    core.save(s,'TEAM_RESPONSE_RNEW2_MATCHED_SUMMARY.csv',out)
    core.js(out/'TEAM_RESPONSE_RNEW2_MATCHING_RECEIPT.json',{
        'matched_target_buildings':sorted(allowed),'unmatched_target_buildings':check.loc[~check.identical_full_outer_variable_map,'heldout_building'].tolist(),
        'matching_rule':'Exact full outer variable-worker mapping; same b-excluded features, training pools, target endpoints, weights and fixed model parameters.',
        'baseline_maximum_absolute_mse_spread':maxspread,'models_refitted':0,'endpoints_recomputed':0,
        'legacy_training_budget_warning':'Frozen Rnew2 class fit uses original10 history buildings; other personnel features use current b-excluded history. Available-artifact comparison, not equal training-budget algorithm contest.'})
    return s


def field_schema(out):
    units={
      'B8L2':'Frozen primary 0..100 composite score.',
      'D10':'Frozen sensitivity 0..100 composite score, only directional scale differs from B8L2.',
      'nodes':'Number of selected output nodes; count, not a semantic correctness label.',
      'failure':'1-complete_evaluable; full-geometry evaluability failure, not all types of inaccuracy.',
      'iou_2d':'Floor footprint IoU, 0..1.',
      'S_bottom_deg':'Symmetric spherical bottom-boundary discrepancy to reference; degrees.',
      'dir':'Residual to the output floor own best orthogonal axis; degrees. Not a global heading error against GT.',
      'Hmean':'Absolute perimeter-mean height ratio residual to reference; dimensionless.',
      'Hcenter':'Centered local height residual; dimensionless.',
      'IoU3D100':'100 times vertex-mean-height prism IoU proxy; not measured true room volume.',
      'height_mean_ratio':'Perimeter-mean height divided by reference perimeter-mean height, dimensionless.',
      'height_mean_h':'Mean reconstructed corner height in camera-height units, computed by native endpoint enrichment; distinct from perimeter-mean height ratio.',
      'ref_node_recall_9':'Reference node coverage from upper/lower paired angular assignment within9deg, 0..1. Diagnostic, not semantic truth.',
      'ref_edge_recall_9':'Reference adjacency coverage induced by that paired assignment, 0..1.',
      'log_source_time_total':'Natural log of summed source active seconds, only complete and single time_source_kind endpoints; not wall-clock completion.'}
    core.js(out/'TEAM_RESPONSE_FIELD_SCHEMA.json',{
      'primary_key_pool_result':['method_id','condition','support_scope','deletions','size_stratum','layer','outcome','model','pool_id'],
      'method_identity':'Use method_id plus condition and heldout_building; never compare bare cluster numbers across methods or use ALL labels as validation labels.',
      'deletions':'N-n, either1 or2. All actual member sets at this near-census layer are complete before method support restriction.',
      'support_scope':'own_supported, common_modern, common_with_legacy. matched_existing_Rnew2 is a postprocessed exact-support alias of already fitted rows; no refit.',
      'fixed_background':'Workers outside the joint class/continuous support are retained in every compared endpoint. Their unknown feature contributions cancel algebraically; they are not given numerical zero or an unknown class.',
      'centering':'Both outcome and team aggregate features centered within actual common usable reference-pool/n population. Each outcome can have a different valid population; model comparisons within an outcome cannot.',
      'mse':'Mean squared prediction error in original outcome units squared; reference pools→image→building equal weighting. Never compare raw MSE across differently scaled outcomes.',
      'R2_vs_finite_pool_mean':'1 - aggregate held-building MSE / aggregate centered null MSE. Relative within-pool response, not absolute unseen-image prediction; undefined when null variance≤1e-12.',
      'mse_reduction':'baseline model held-building MSE minus new model MSE, positive improves; median and sign counts are paired building statistics.',
      'class_configuration_contrast':'coarse_configuration_contrast_exists and fine_configuration_contrast_exists refer to complete restricted member layers BEFORE outcome availability filtering. They do not alone certify a quality-outcome class contrast.',
      'unknown_values':'Unknown restricted population size stays missing; actual empty supported deletion population can be0. Failure scores remain missing for quality, not zero.',
      'metrics':units,
      'angular_thresholds':'ref_*_9 is an endpoint diagnostic. It is separate from original whole-answer9/12deg clusters and internal fusion correspondence parameters; none changed.',
      'source_contracts':[
        'tools/thesis_main/analysis/wall_consensus_quality_20261015.py',
        'tools/thesis_main/analysis/quality_b8l2_d10_20261017.py',
        'research/workers/personnel_interchangeability_20261020/analysis/composition/fusion_runner.py',
        'research/workers/personnel_global_composition_20261021/composition/run_endpoints.py'],
      'scope_qualification':'All formal pools/records/references/fusion and scoring qualifications are inherited unchanged. Behavioral labels do not restore historical voting eligibility.'})


def write_report(out,summary,increment,ledger,contrast,receipt,reverse):
    ordinary=summary[summary.layer.str.startswith('ordinary_')&summary.size_stratum.eq('n_ge20')]
    common=ordinary[ordinary.support_scope.eq('common_modern')]
    selection=common[common.outcome.isin(['B8L2','D10','nodes','failure','Hmean','Hcenter','height_mean_ratio','log_source_time_total'])]
    core.save(selection,'TEAM_RESPONSE_MAIN_COMPARISON.csv',out)
    primary=common[common.deletions.eq(2)]
    comp=primary[primary.outcome.eq('B8L2')].pivot(index=['condition','method_id'],columns='model',values='mse').reset_index()
    shown=['condition','method_id','source','QT_source','coarse_source','fine_source','QT_plus_fine_source','QT_moments_source']
    comp=comp[[c for c in shown if c in comp]]
    direction=primary[primary.method_id.isin(['M_structure','MV_QTD_manual_new','SP_scale','MV_QTScopeSemi_semi_new'])&
        primary.outcome.isin(['B8L2','D10','nodes','failure','Hmean','Hcenter','height_mean_ratio','log_source_time_total'])&
        primary.model.isin(['QT_source','coarse_source','fine_source'])]
    direction=direction.pivot(index=['condition','method_id','outcome'],columns='model',values='R2_vs_finite_pool_mean').reset_index()
    core.save(direction,'TEAM_RESPONSE_EFFECT_SIZE_COMPARISON.csv',out)
    gain=increment[increment.support_scope.eq('common_modern')&increment.size_stratum.eq('n_ge20')&
        increment.layer.str.startswith('ordinary_')&increment.deletions.eq(2)&
        increment.method_id.isin(['M_structure','MV_QTD_manual_new','SP_scale','MV_QTScopeSemi_semi_new'])&
        increment.outcome.isin(['B8L2','D10','nodes','log_source_time_total'])&
        ((increment.new_model.eq('fine_source')&increment.baseline.eq('coarse_source'))|
         (increment.new_model.eq('QT_plus_fine_source')&increment.baseline.eq('QT_source'))|
         (increment.new_model.eq('QT_moments_plus_fine_source')&increment.baseline.eq('QT_moments_source')))]
    core.save(gain,'TEAM_RESPONSE_MAIN_FINE_INCREMENT.csv',out)
    coverage=ledger[ledger.support_scope.eq('common_modern')&ledger.size_stratum.eq('n_ge20')&
        ledger.layer.str.startswith('ordinary_')&ledger.outcome.isin(['B8L2','failure','log_source_time_total'])]
    cov=coverage.groupby(['condition','deletions','outcome','status'],as_index=False).agg(buildings=('heldout_building','nunique'),
        images=('image_id','nunique'),formal_sets=('required_all_member_sets','sum'),
        restricted_sets=('restricted_exact_member_sets',lambda v:v.sum(min_count=1)),
        usable_sets=('outcome_available_member_sets',lambda v:v.sum(min_count=1)))
    core.save(cov,'TEAM_RESPONSE_MAIN_SUPPORT.csv',out)
    legacy=ordinary[ordinary.support_scope.eq('common_with_legacy')&ordinary.deletions.eq(2)&
        ordinary.method_id.isin(['M_structure','A2_relation','Rnew2','F01','MV_QTD_manual_new'])&
        ordinary.outcome.isin(['B8L2','D10','log_source_time_total'])&ordinary.model.isin(['QT_source','coarse_source','fine_source'])]
    contrast_keys=['method_id','condition','support_scope','deletions','size_stratum','layer']
    legacy=legacy.merge(contrast[contrast_keys+['coarse_contrast_pools','fine_contrast_pools']],on=contrast_keys,how='left',validate='many_to_one')
    legacy['class_contrast_interpretation']=np.where(legacy.model.eq('coarse_source')&legacy.coarse_contrast_pools.eq(0),
        'constant_model_not_an_identifiable_class_contrast','available_model_comparison')
    core.save(legacy,'TEAM_RESPONSE_LEGACY_COMPARISON.csv',out)
    buildings=pd.read_csv(out/'TEAM_RESPONSE_BUILDINGS.csv.gz')
    hb=buildings[buildings.support_scope.eq('common_modern')&buildings.size_stratum.eq('n_ge20')&
        buildings.layer.str.startswith('ordinary_')&buildings.model.eq('QT_source')&
        buildings.method_id.isin(['MV_QTD_manual_new','MV_QTScopeSemi_semi_new'])]
    heterogeneity=[]
    for keys,g in hb.groupby(['condition','deletions','outcome']):
        g=g.sort_values('null_mse',ascending=False);total=g.null_mse.sum()
        heterogeneity.append(dict(zip(['condition','deletions','outcome'],keys))|
            {'buildings':len(g),'mean_building_null_mse':g.null_mse.mean(),
             'median_building_null_mse':g.null_mse.median(),'maximum_building_null_mse':g.null_mse.iloc[0],
             'maximum_variance_building':g.heldout_building.iloc[0],
             'largest_building_share_of_summed_variance':g.null_mse.iloc[0]/total if total>1e-12 else np.nan})
    heterogeneity=pd.DataFrame(heterogeneity)
    core.save(heterogeneity,'TEAM_RESPONSE_RESPONSE_HETEROGENEITY.csv',out)
    contract=json.loads((out/'TEAM_RESPONSE_CONTRACT.json').read_text())
    def get(method,outcome,model,delta=2):
        z=common[common.method_id.eq(method)&common.outcome.eq(outcome)&common.model.eq(model)&common.deletions.eq(delta)]
        return z.iloc[0] if len(z) else None
    def r2(method,outcome,model,delta=2):
        z=get(method,outcome,model,delta)
        return f'{z.R2_vs_finite_pool_mean:.4f}' if z is not None else '不可估计'
    selectedgain=gain[gain.outcome.isin(['B8L2','log_source_time_total'])&gain.new_model.eq('fine_source')]
    reverse_table=reverse[reverse.deletions.eq(2)&reverse.size_stratum.eq('n_ge20')&reverse.outcome.eq('B8L2')]
    reverse_table=reverse_table.pivot(index='method_id',columns='model',values='mse').reset_index()
    reverse_table=reverse_table[[c for c in ['method_id','QT_source','coarse_source','fine_source','QT_plus_fine_source'] if c in reverse_table]]
    cols=['method_id','outcome','baseline','mse_reduction','mse_reduction_median','relative_mse_reduction','buildings','positive_buildings','negative_buildings','bootstrap95_low','bootstrap95_high']
    qgain=selectedgain[selectedgain.method_id.eq('MV_QTD_manual_new')&selectedgain.outcome.eq('B8L2')].iloc[0]
    tgain=selectedgain[selectedgain.method_id.eq('MV_QTD_manual_new')&selectedgain.outcome.eq('log_source_time_total')].iloc[0]
    sections=[
      '# 近全员真实团队：类别与连续特征的楼外构成响应检验\n',
      f"**本项的明确细层用途在效率解释；未发现值得采用的统一跨楼质量响应增量。** 同新批 Manual QTD 的细层相对Q父层，在 N−2 大团队时长响应上使MSE下降 {100*tgain.relative_mse_reduction:.2f}%，{int(tgain.positive_buildings)}/{int(tgain.buildings)} 楼改善；连续 Q/T 的预测误差仍更低。B8L2 的细层平均改善仅 {100*qgain.relative_mse_reduction:.4f}%，{int(qgain.positive_buildings)} 楼改善、{int(qgain.negative_buildings)} 楼变差，配对改善中位数 {qgain.mse_reduction_median:.6f}；D10没有支持这一微小均值改善。Semi 的 SP 与新行为细层也未改善共同支持的大团队质量响应。这个判断针对本检验的近全员、共享线性响应，不替代同图成员泛化或局部关键票机制。\n",
      '本项新增实验回答：对已经完整枚举的真实成员集合，用目标建筑之外形成的人员标签和连续历史，能否预测同一图片、固定人数下的相对构成响应；细层是否提高粗层或连续 Q/T 的预测。它与主研究的大块换人、完整配比网格互补。其用途是检验跨建筑共享的响应方向，不将局部可解释案例或同图成员泛化等同于跨建筑可预测。\n',
      '## 1. 实际覆盖与固定设计\n',
      f"原始快照含 {contract['source_data']['scalars_rows']:,} 个去重真实成员集合；本分析完整核验 {contract['source_data']['complete_layers']} 个 N−1/N−2 层（229 个冻结正式池×2层），没有重算融合终点。全员 N 集合仅有一个，完全不进入本检验。每层必须满足 choose(N,删除人数)、有效成员子集及不同删除集合数三项一致。主表报告 n≥20，完整表另含 all_n；普通、门洞、特殊范围分别评估。\n",
      '每个目标建筑 b 的所有训练图片和目标图片都使用**同一套排除 b 的人员映射**。系数、变量尺度只用其他建筑；不将各训练图自身的 LOBO 标签拼到一起。新旧方法各自支持及共同支持分别报告。共同现代 Manual 为 M/A2/混来源QTD/同新批QTD/无Q四域；共同现代 Semi 为 SP/A2/新Semi四域。未知类别或缺 Q/T 的人固定留在每个团队，仅删除共同可用人员；未知不成为类别，不填零。\n',
      '以每个参考池、固定人数的共同可用端点均值为中心，同时中心化结果和人员聚合变量。故结果是**有限成员总体内的相对响应**，不是尚未见过图片的绝对质量预测。每个模型在同一分项使用完全相同的成员端点。质量不可评分仍保留在失败风险分项，质量值不填0。\n',
      '模型包含来源比例；连续对照是个人 Q 水平/Q低尾/T水平/T尾部的团队均值，并加入固定的二阶矩敏感性。类别模型使用完整粗/细人数比例；另比较 Q/T+粗类、Q/T+细类。所有模型固定 ridge=0.01，无参数搜索，训练侧加权 RMS 缩放。端点→参考池→图片→建筑逐层均等；结果汇总也按建筑均等。训练R²不作证据。\n',
      '## 2. B8L2 主结果：N−2、大团队、共同人员\n',
      '表中为外楼 MSE，越小越好。source 在此可变成员均来自新批的共同面板中是恒定列，等于有限池均值的零响应基线。单层 A2 没有细类，不制造 fine 比较。\n',
      table(comp)+'\n',
      '## 3. 细类增量与效率用途\n',
      '下表以相同建筑上“基线MSE−新增模型MSE”为改善量，正值改善。置信区间是探索后的配对建筑 bootstrap 描述，不是新盲测或多重检验校正后的确认。\n',
      table(selectedgain[cols])+'\n',
      f"普通 Manual 的同新批 QTD 在总源时长上，粗/细/QT/QT二阶矩的相对池均值 R² 分别为 {r2('MV_QTD_manual_new','log_source_time_total','coarse_source')} / {r2('MV_QTD_manual_new','log_source_time_total','fine_source')} / {r2('MV_QTD_manual_new','log_source_time_total','QT_source')} / {r2('MV_QTD_manual_new','log_source_time_total','QT_moments_source')}。细层对 Q 父层可以增加可读的效率区分；是否超出连续特征以 QT+fine 及二阶矩敏感性列为准，不能因细类优于粗类就称它超越连续画像。\n",
      '时间是全员记录齐全、且 time_source_kind 一致时的源活动秒总和的 log 响应，不是团队墙钟耗时。混合时钟不可直接相加比较。Semi 共同支持下的时间预测因可用训练建筑不足而不估，不能写成零效应。\n',
      '## 4. 分项、几何和失败\n',
      '完整 15 项包含 B8L2、D10、底面 IoU、底部偏差、方向、Hmean/Hcenter、3D代理、平均高度、参考节点/边覆盖、输出节点数、失败和时间。下面的 R² 以各有限池均值为基线；负值意味着该跨楼模型比零响应更差。结构节点/失败恒定的池仍计入均方误差，但 variable_pools 独立保存；全员零波动未参与。质量稳定不等于正确，几何相近也不由 Q 接近替代。\n',
      '`dir` 是输出自身最优正交轴残差（度），不是相对GT的全局朝向误差；Hmean/Hcenter为冻结高度残差；IoU3D100为角点均高棱柱代理，不是真实房间体积。`height_mean_h` 是平均角点高度/相机高度，`height_mean_ratio` 则沿用质量引擎的周长平均高度与参考之比。参考节点/边的9°匹配仅为终点诊断，未改原答9°/12°分簇或融合内部对应参数。单位及连接键详见 FIELD_SCHEMA。\n',
      table(direction)+'\n',
      '响应方差在建筑之间很不均。下表展示 N−2 的B8方差集中程度；不能仅凭整体接近0的R²把所有图片说成无差异。细层表同时给配对建筑改善中位数与正负楼数，保留条件性作用。\n',
      table(heterogeneity[heterogeneity.deletions.eq(2)&heterogeneity.outcome.eq('B8L2')])+'\n',
      '## 5. 精确机会与未估计范围\n',
      '每个条件、删除层、结果分项均保留全部正式池分母。formal_sets 是冻结正式池的完整成员集合数；restricted_sets 是固定所有未知成员、仅在共同可用人群中删除后的全部集合；usable_sets 是该分项实际可用集合。不同结果及方法行高度重叠，不能相加成新增融合次数。缺映射时 restricted 数量留空。\n',
      table(cov)+'\n',
      '特别是 Semi 的一个普通大团队池没有共同可变成员，不能将其固定唯一集合解释成同类可互换。某些 N−1 层全部不可评分但 N−2 出现可评分端点，这是实际资格/失败表现的变化，未改变评分合同。门洞、特殊范围与旧法适用域的所有排除保留在 eligibility 明细。\n',
      '## 6. Rnew2、F01 与共同支持退化\n',
      '旧 Rnew2、F01 只在其原 12 个目标建筑有合法映射；固定10楼训练历史不包含这12楼，允许将同一映射用于当前训练和目标池。历史10楼没有合法目标排除旧标签，本轮明确不估；它们也仅适用于普通 Manual。旧标签的10楼训练预算与当前连续特征的21楼训练预算不同，这是可用研究工件的实际对照，不是同训练预算的算法竞赛。\n',
      '加上 F01 高Q域再取共同支持，会让 Rnew2 的可变人员只剩同一类别。此时 coarse 模型只能返回零构成响应，**不能据此判定 Rnew2 分类无效**；自己的支持面板仍单独报告。逐池 class_contrast 表明确完整限定成员层的粗/细配置数量，避免将无机会误写成负结果。该表计算在分项评分筛选之前；配置数大于1不单独保证 B8 等分项剔除失败后仍有类别对比。分项可用端点另见 ELIGIBILITY 与 FIT_SUPPORT。\n',
      table(legacy[['method_id','outcome','model','mse','R2_vs_finite_pool_mean','buildings','images','endpoints','coarse_contrast_pools','class_contrast_interpretation']])+'\n',
      '另一个有意义的比较无需重算：去掉 F01 的高Q限制后，Rnew2 自身面板与现代共同面板在原12目标楼的11楼具有完全相同的外楼可变人员集合；这些楼的 QT 基线、端点和加权训练支持逐项一致，因此直接复用已拟合结果，形成下表。B6ByNegPMKs 的现代面板少 W108，明确排除配对比较并保留原因。这避免因七法交集退化而取消 Rnew2 对照，也不重复计算模型或融合终点。\n',
      table(reverse_table)+'\n',
      '## 7. 如何使用结论\n',
      '类别的解释价值、同图成员泛化、跨楼响应预测是不同用途。本检验采用 pooled 线性方向和近全员 n；不把其结果外推为所有人数、所有局部结构或大块替换都无效。反过来，个别关键票带来的明显提升不能代替本项跨楼增量。主报告的同一 fine 网格、同一留出具体成员集合实验回答另一问题：既定图片内，细类是否比父类更好地概括成员波动。应并列阅读，保持估计对象和分母。\n',
      '## 8. 文件与复现\n',
      '- `TEAM_RESPONSE_SUMMARY.csv`：全部层、分项、模型汇总；`TEAM_RESPONSE_BUILDINGS.csv.gz`：逐建筑结果。\n- `TEAM_RESPONSE_POOL_RESULTS.csv.gz`：逐参考池模型结果；原始实际成员端点键见 composition 的正式清单，不另复制大几何缓存。\n- `TEAM_RESPONSE_INCREMENT.csv`：细层及连续基线的逐比较改善；MAIN 系列表为主报告小表。\n- `TEAM_RESPONSE_ELIGIBILITY_LEDGER.csv.gz` / SUMMARY：包括没有映射、成员不足、评分不足、训练建筑不足的全部机会。\n- `TEAM_RESPONSE_CLASS_CONTRAST.csv.gz`：每个目标池的实际可变粗细类和完整配置数量。\n- `TEAM_RESPONSE_FOLD_MAPS.csv.gz`、FIT_SUPPORT、CONTRACT：楼外映射、训练支持、固定参数与输入哈希；CHECKS：关键一致性核验。\n',
      '从仓库根目录执行：\n\n```bash\nOPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/workers/personnel_global_composition_20261021/analysis/team_continuous_check.py --deletions 1 2\nOPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/workers/personnel_global_composition_20261021/analysis/summarize_team_continuous_check.py\n```\n\n默认读取已交付的合并 `composition/TEAMS_SCALARS.csv.gz`，只使用精确 N−1/N−2 层；本次运行的不可变 stage2 快照哈希见 CONTRACT。之后附加的配比/ABC终点不会改变这些层。`runtime/` 是可删除的分段分析检查点，不进入精简交付。\n',
      f"核验：共同支持 QT 的最大MSE差={receipt['common_support_QT_maximum_absolute_mse_spread']:.3g}；全部 {receipt['denominator_comparisons']} 组实际结果分母与独立机会账一致；N−1 在加入 N−2 后重现情况见 CHECKS。\n"
    ]
    (out/'REPORT_ZH.md').write_text('\n'.join(sections),encoding='utf-8')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=core.HERE/'team_response');args=ap.parse_args();out=args.out
    summary=pd.read_csv(out/'TEAM_RESPONSE_SUMMARY.csv')
    increment=pd.read_csv(out/'TEAM_RESPONSE_INCREMENT.csv')
    ledger=pd.read_csv(out/'TEAM_RESPONSE_ELIGIBILITY_LEDGER.csv.gz',low_memory=False)
    receipt=validate(out,summary,ledger,core.HERE/'team_response_stage1/TEAM_RESPONSE_SUMMARY.csv')
    contrast=class_opportunities(out,summary)
    reverse=reverse_matched_existing(out)
    field_schema(out)
    write_report(out,summary,increment,ledger,contrast,receipt,reverse)
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
