"""Prepare canonical worker evidence, without fitting or assigning worker strata."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from tools.thesis_main.analysis.prepare_human_bi_comparisons_20260908 import READINGS, evaluated
from tools.thesis_main.analysis.analyze_uncertainty_handoff import historical_pair_ids
from tools.thesis_main.analysis.prepare_uncertainty_visual_review import ROOT, helpers

BASE = ROOT / 'analysis_results/uncertainty_cloud_inputs_20260906_v1'
GEOMETRY = ROOT / 'analysis_results/uncertainty_decision_ready_20260908_v1/geometry'
OUTPUT = ROOT / 'analysis_results/worker_evidence_strata_20260908_v1/inputs'
META = ['canonical_annotation_id', 'context_key', 'image_id', 'worker_id', 'stage',
        'block_index', 'raw_condition', 'building_id', 'current20_member',
        'assistance_exposure', 'scope_status', 'canonical_selection_status',
        'historical_primary_eligibility_status', 'legacy_exclusion_reason']


def pair_count(points):
    """Count exported endpoint pairs, not verified architectural corners."""
    p = np.asarray(points, float)
    if p.ndim != 2 or p.shape[1] != 2 or not len(p):
        return np.nan, 'missing_or_invalid_point_array'
    if len(p) % 2:
        return np.nan, 'odd_point_count'
    # Coordinate validity belongs to geometry; an even exported count survives it.
    return len(p) / 2, 'computable'


def validate_index(annotations):
    assert annotations.canonical_annotation_id.is_unique, 'canonical revisions duplicated'
    assert not annotations.duplicated(['context_key', 'worker_id']).any(), 'same worker/context repeated'
    assert annotations[META[:9]].notna().all().all(), 'missing identity fields'


def attach_identity(frame, annotations):
    """Canonical identity is authoritative; verify shared provenance rather than guessing."""
    index = annotations.set_index('canonical_annotation_id')
    ids = frame.canonical_annotation_id
    assert ids.notna().all() and ids.isin(index.index).all()
    out = frame.copy()
    for col in META[1:]:
        authoritative = ids.map(index[col])
        if col in out:
            present = out[col].notna() & authoritative.notna()
            assert (out.loc[present, col].astype(str) == authoritative[present].astype(str)).all(), col
        else:
            out[col] = authoritative
    return out


def reference_dispute_status(quality_status):
    # Only an explicit source adjudication establishes this flag.
    return 'source_researcher_confirmed_bad_gt' if quality_status == 'researcher_confirmed_bad_gt' else 'unknown_not_adjudicated'


def summarize_auxiliary(frame, group_columns, value_column, family, metric):
    rows = []
    keys = ['worker_id','stage','raw_condition', *group_columns]
    for group, g in frame.groupby(keys, dropna=False):
        values = pd.to_numeric(g[value_column], errors='raise')
        values = values[np.isfinite(values)]
        rows.append(dict(zip(keys, group), family=family, metric=metric,
                         source_rows=len(g), canonical_responses=g.canonical_annotation_id.nunique(),
                         contexts=g.context_key.nunique(), buildings=g.building_id.nunique(),
                         observed_values=len(values), missing_values=len(g)-len(values),
                         mean=values.mean(), median=values.median(),
                         minimum=values.min(), maximum=values.max()))
    return pd.DataFrame(rows)


def auxiliary_summaries(out):
    ref = pd.read_csv(out / 'reference_measurement.csv.gz')
    timing = pd.read_csv(out / 'active_time_context.csv.gz')
    proposal = pd.read_csv(out / 'proposal_response.csv.gz')
    frames = [summarize_auxiliary(ref, ['measurement_role','metric_name','source_path',
                 'reference_type','reference_quality_status','reference_dispute_status','measurement_status'],
                 'measurement_value', 'reference', 'source_metric_name'),
              summarize_auxiliary(timing, ['active_time_formal_available','timing_status',
                 'timing_rule_version','active_time_source'], 'active_time_seconds', 'active_time', 'seconds')]
    for column in ['exact_geometry_equal','topology_changed','initial_to_final_rmse_diagonal_normalized']:
        frames.append(summarize_auxiliary(proposal, ['initialization_source_kind','source_path'],
                                         column, 'initialization', column))
    result = pd.concat(frames, ignore_index=True)
    coverage = pd.read_csv(out / 'worker_stage_condition_coverage.csv')
    result = result.merge(coverage[['worker_id','stage','raw_condition','canonical_responses']].rename(
        columns={'canonical_responses':'stage_condition_total_canonical'}),
        on=['worker_id','stage','raw_condition'], validate='many_to_one')
    result.to_csv(out / 'auxiliary_worker_summary.csv', index=False)
    (out / 'AUXILIARY_README_ZH.md').write_text('''# 独立辅助证据汇总

`auxiliary_worker_summary.csv` 以 worker_id × stage × raw_condition 分层，family 区分 reference、active_time、initialization；每个 family 的进一步分组字段见下文。仅有事实记录的组生成行，无记录的阶段不得补零或借另一阶段代替。

- reference：按 measurement_role、metric_name、source_path、reference_type、reference_quality_status、reference_dispute_status、measurement_status 分开。metric=source_metric_name 表示实际指标名称见 metric_name。原分数可用不代表参考无争议；明确坏 GT 与未知分别保留。均值为描述性原量纲，不用于跨任务质量排序或新综合分数。
- active_time：按 active_time_formal_available、timing_status、timing_rule_version、active_time_source 分开。partial_session_coverage、protocol_deviation、fallback 均不混入无此问题的组。非正式可用但有数值的 fallback 仍作为单列来源资料，不当正式 active_time；lead_time 未参与任何汇总。无值的 mean/median/minimum/maximum 留空。
- initialization：按实际 initialization_source_kind、source_path 分开。exact_geometry_equal 与 topology_changed 的 mean 是已观察布尔响应中的比例，分母 observed_values；RMSE 仅在已有可计算记录中汇总，结构变化后缺失不填零。不把这些指标命名为正确性或新综合保留率。

所有行的 source_rows 是该来源分组记录数；canonical_responses、contexts、buildings 是该组独立身份覆盖；observed_values 是有限数值的分母，missing_values=source_rows−observed_values。stage_condition_total_canonical 是该工人在阶段条件内的完整 canonical 总数，用于覆盖对照。reference 多个指标行不能相加作为人数或样本数。主表的阶段覆盖总入口继续使用 worker_stage_condition_coverage.csv（26人×7条件）；所有无该阶段的人员仍留在总表，分数不填。
''', encoding='utf-8')
    return result


def response_history_flags(annotations, lineage):
    assert lineage.raw_annotation_version_id.is_unique
    assert lineage.canonical_annotation_id.notna().all()
    assert set(lineage.canonical_annotation_id) == set(annotations.canonical_annotation_id)
    counts = lineage.groupby('canonical_annotation_id').size().rename('raw_version_count')
    flags = annotations[META].merge(counts, on='canonical_annotation_id', validate='one_to_one')
    flags['has_revision'] = flags.raw_version_count > 1
    observed = annotations.groupby(['worker_id','image_id']).agg(
        worker_image_context_count=('context_key','nunique'),
        worker_image_condition_count=('raw_condition','nunique')).reset_index()
    flags = flags.merge(observed, on=['worker_id','image_id'], validate='many_to_one')
    flags['multiple_condition_observed'] = flags.worker_image_condition_count > 1
    flags['exposure_history_interpretation'] = 'observed_conditions_only_no_chronological_exposure_inference'
    return flags


def write_response_history(out, annotations):
    lineage = pd.read_csv(BASE / 'facts/annotation_version_lineage.csv.gz')
    flags = response_history_flags(annotations, lineage)
    assert len(lineage) == 2513 and len(flags) == 2501
    assert int(flags.raw_version_count.sum()) == 2513
    assert int(flags.has_revision.sum()) == 9
    assert int((flags.raw_version_count-1).sum()) == 12
    multiple_c1 = flags[(flags.stage == 'C1') & flags.multiple_condition_observed]
    assert len(multiple_c1) == 4
    assert len(multiple_c1[['worker_id','image_id']].drop_duplicates()) == 2
    lineage.to_csv(out / 'annotation_version_lineage.csv.gz', index=False)
    flags.to_csv(out / 'response_history_flags.csv', index=False)


def main(out=OUTPUT):
    out.mkdir(parents=True, exist_ok=True)
    audit, _ = helpers()
    annotations, _, _, _, _, _, _, raw, _ = audit.load()
    validate_index(annotations)
    assert len(annotations) == 2501 and annotations.worker_id.nunique() == 26
    rows = []
    for r in annotations.to_dict('records'):
        meta = {k: r[k] for k in META}
        points = np.asarray(raw[r['canonical_annotation_id']]['points_1024x512'], float)
        value, status = pair_count(points)
        rows.append(dict(**meta, metric='corner_pair_count', reading='raw_point_count',
                         representation='not_applicable', value=value, status=status,
                         raw_point_count=len(points), source='raw_annotation_versions.jsonl'))
        for reading in READINGS:
            try:
                ids = list(range(len(points))) if reading == READINGS[0] else historical_pair_ids(points)
                polygon, status = evaluated(audit.footprint, points[ids])
            except ValueError as exc:
                polygon, status = None, str(exc)
            value = np.log(polygon.area) if polygon is not None else np.nan
            rows.append(dict(**meta, metric='log_floor_area', reading=reading,
                             representation='raw_float_coordinates', value=value, status=status,
                             raw_point_count=len(points), source='raw_annotation_versions.jsonl'))
    bi = attach_identity(pd.read_csv(GEOMETRY / 'human_bi_comparisons.csv.gz'), annotations)
    assert len(bi) == 2501 * 2 * 3
    assert not bi.duplicated(['canonical_annotation_id', 'reading', 'representation']).any()
    bi['metric'] = 'bi_delta'
    bi['value'] = bi.delta_enclosed_minus_extended
    bi['status'] = bi.comparison_status
    bi['source'] = 'uncertainty_decision_ready_20260908_v1/geometry/human_bi_comparisons.csv.gz'
    metrics = pd.concat([pd.DataFrame(rows), bi], ignore_index=True)
    assert not metrics.duplicated(['canonical_annotation_id','metric','reading','representation']).any()
    assert np.isfinite(metrics.loc[metrics.status == 'computable', 'value']).all()
    metrics.to_csv(out / 'worker_metrics.csv.gz', index=False)
    annotations.to_csv(out / 'canonical_index.csv.gz', index=False)
    write_response_history(out, annotations)
    # Complete worker x observed stage/condition grid: no unavailable-stage score imputation.
    strata = annotations[['stage','raw_condition']].drop_duplicates()
    workers = annotations[['worker_id','current20_member']].drop_duplicates()
    observed = annotations.groupby(['worker_id','stage','raw_condition']).agg(
        canonical_responses=('canonical_annotation_id','size'), contexts=('context_key','nunique'),
        buildings=('building_id','nunique'), images=('image_id','nunique')).reset_index()
    coverage = workers.merge(strata, how='cross').merge(observed, how='left', on=['worker_id','stage','raw_condition'])
    for col in ['canonical_responses','contexts','buildings','images']:
        coverage[col] = coverage[col].fillna(0).astype(int)
    coverage.to_csv(out / 'worker_stage_condition_coverage.csv', index=False)
    # Existing measurements remain separate, with their original contracts and provenance.
    for name in ['reference_measurement','active_time_context','proposal_response']:
        frame = attach_identity(pd.read_csv(BASE / 'facts' / (name + '.csv.gz')), annotations)
        frame['fact_input_source'] = 'uncertainty_cloud_inputs_20260906_v1/facts/' + name + '.csv.gz'
        if name == 'reference_measurement':
            frame['reference_dispute_status'] = frame.reference_quality_status.map(reference_dispute_status)
            # Availability of a historical score is never evidence of an undisputed reference.
        if name == 'proposal_response':
            proposals = pd.read_csv(BASE / 'facts/proposal_fact.csv.gz')
            frame = frame.merge(proposals[['proposal_id','initialization_source_kind']], on='proposal_id', validate='many_to_one')
        frame.to_csv(out / (name + '.csv.gz'), index=False)
    auxiliary_summaries(out)
    shutil.copyfile(GEOMETRY / 'user_confirmed_derivatives.csv', out / 'user_confirmed_derivatives.csv')
    confirmations = json.loads((ROOT / 'analysis_results/uncertainty_followup_analysis_20260908_v1/confirmed_20260908/user_confirmations.json').read_text(encoding='utf-8'))
    derived = []
    for c in confirmations:
        polygon, status = evaluated(audit.footprint, c['derived_points'])
        derived.append(dict(case_id=c['case_id'], canonical_annotation_id=c['canonical_annotation_id'],
                            image_id=c['image_id'], source_kind='canonical_response' if c['canonical_annotation_id'] else 'reference',
                            reading='user_confirmed_order', metric='log_floor_area',
                            value=np.log(polygon.area) if polygon is not None else np.nan, status=status,
                            raw_point_ids=json.dumps(c['raw_point_ids']), source=c['source']))
    pd.DataFrame(derived).to_csv(out / 'user_confirmed_area_derivatives.csv', index=False)
    qa = dict(canonical_responses=len(annotations), workers=annotations.worker_id.nunique(),
              metric_rows=len(metrics), geometry_readings=list(READINGS),
              raw_sources_unchanged=True, canonical_duplicates=0,
              computability=metrics.groupby(['metric','reading','representation','status']).size().rename('rows').reset_index().to_dict('records'))
    (out / 'QA.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    (out / 'README_ZH.md').write_text('''# 人员分析指标输入

生成：`.venv/Scripts/python.exe -m tools.thesis_main.analysis.prepare_worker_evidence_metrics_20260908`。

`worker_metrics.csv.gz` 使用 canonical_annotation_id × metric × reading × representation 唯一键；context_key 保留阶段、block、条件。value 缺失与 status 同时保留，不删除失败响应。

- corner_pair_count：原始点数/2，仅完整偶数数组可算；不证明垂直配对或建筑角点正确。坐标无效不消除已知点数。
- log_floor_area：同相机高度单位的地面多边形面积自然对数。原邻接与历史 pairmap 分列，后者不等于作者确认邻接。representation 为 raw_float_coordinates。
- bi_delta：d_enclosed − d_extended，负值相对更近 enclosed；正值相对更近 extended。同时保留 d_bi、minimum_residual、两头距离及失败状态。native_uv 为主要对照，两个整数版本仅敏感性。距离为地面 1−IoU，不是语义类型或正确性。

用户确认派生仅见两个 user_confirmed 文件，不覆盖任何 canonical 原序。source_kind 区分响应和参考。

辅助表保持来源合同：reference_measurement 内 reference_identity/type/quality_status 和 metric_name 原样保留，reference_dispute_status 仅将源文件明确 researcher_confirmed_bad_gt 标为 source_researcher_confirmed_bad_gt，其余为 unknown_not_adjudicated，不能当作无争议；需结合既有语义证据逐个限制。active_time_context 的可靠性沿用 formal_available/timing_status/source，lead_time 永不补 active_time。proposal_response 使用 canonical 身份连接，保留 exact_geometry_equal/topology_changed/RMSE 和自然或合成初始化类别，不定义新的保留率。

worker_stage_condition_coverage 是 26 人 × 已观察阶段条件的完整覆盖；零覆盖不补成绩。本模块不拟合、不分层，不改变旧资格和人工裁决。

response_history_flags.csv 保留 2501 canonical 的 raw_version_count/has_revision，完整谱系见 annotation_version_lineage.csv.gz（2513版本；9份canonical有额外12版本）。worker_image_context_count/worker_image_condition_count 按同人同图统计已观察条件，multiple_condition_observed 与当前响应的 assistance_exposure 分开。C1有4条响应属于2个同人同图多条件配对；这不证明条件时间先后或未观测的模型暴露，不使用提交时间反推暴露史。
''', encoding='utf-8')
    print(json.dumps({k: v for k,v in qa.items() if k != 'computability'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=OUTPUT)
    main(parser.parse_args().out)
