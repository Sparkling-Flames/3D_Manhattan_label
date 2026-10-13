"""复用冻结处理后指标；来源与原始输入诊断不参与数值评分。"""
import csv
import importlib.util
import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'research/quality_pro_joint_archive_20261013/source'
ADMISSION = ROOT / 'research/quality_data_admission_audit_20261013/FULL_ADMISSION.json'
OUT = ROOT / 'research/quality_current_candidate_view_20261013'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def load_inputs():
    spec = importlib.util.spec_from_file_location('frozen_joint_score', SOURCE / 'calibration/score.py')
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)
    configs = {'baseline_quad08': scorer.BASELINE,
               **read(SOURCE / 'calibration/recommended_parameters.json')['candidates']}
    search = read(SOURCE / 'calibration/inputs/search_inputs.json')
    admission = {r['record_id']: r for r in read(ADMISSION)['records']}
    return scorer, configs, search, admission


def candidate_row(row, admission, scorer, configs):
    if row['object_id'] != admission['object_id']:
        raise ValueError('record/object binding mismatch: ' + row['id'])
    return {
        'record_id': row['id'], 'object_id': row['object_id'],
        'image_code': row['image_code'], 'worker_id': row['worker_id'],
        'reference_object_id': row['reference_object_id'],
        'reference_version': row['reference_version'],
        'scored_input': 'processed_mean_x_geometry', 'raw_input_penalty_included': False,
        'formal_eligibility_newly_granted': False, 'conditional_diagnostic_use': True,
        'old_applicability_confirmed': row['applicability_confirmed'],
        'old_conditional_personnel_eligible': row['conditional_personnel_eligible'],
        'strict_old_admission_subset': admission['full_q_calibration_ready'] and row['applicability_confirmed'],
        'admission': {k: admission[k] for k in ('condition', 'source_cohort',
            'current_personnel_gate', 'role', 'personnel_barriers', 'context_barriers',
            'numeric_barriers', 'original_holdout', 'severe_exception')},
        'metrics': row['metrics'], 'raw_alignment': row['raw_alignment'],
        'scores': {name: scorer.score_metrics(row['metrics'], config, row['descriptor'])
                   for name, config in configs.items()},
    }


def describe(rows, names):
    out = {'records': len(rows), 'candidates': {}}
    for name in names:
        valid = [r for r in rows if r['scores'][name]['score'] is not None]
        values = [r['scores'][name]['score'] for r in valid]
        deltas = [r['scores'][name]['score'] - r['scores']['baseline_quad08']['score']
                  for r in valid if r['scores']['baseline_quad08']['score'] is not None]
        out['candidates'][name] = {'complete': len(valid),
            'mean': mean(values) if values else None, 'median': median(values) if values else None,
            'mean_delta_from_baseline': mean(deltas) if deltas else None,
            'minimum_delta': min(deltas) if deltas else None,
            'maximum_delta': max(deltas) if deltas else None}
    return out


def existing_routed_view(admission):
    routes = read(SOURCE / 'routing/results/routes.json')['rows']
    directives = read(SOURCE / 'routing/inputs/prepared_input.json')
    with (SOURCE / 'integration/results/reference_formula_four_way.csv').open(encoding='utf-8-sig', newline='') as f:
        cells = list(csv.DictReader(f))
    by_id = {r['record_id']: r for r in routes}
    for rid, rule in directives['manual_overrides'].items():
        if by_id[rid]['selected_candidate_id'] != rule['selected_candidate_id']:
            raise ValueError('explicit human reference assignment overridden: ' + rid)
    for rid, rule in directives['manual_family_directives'].items():
        if by_id[rid]['selected_candidate_id'] not in rule['allowed_candidate_ids']:
            raise ValueError('human reference family restriction overridden: ' + rid)
    if any(r.get('quality_or_height_used_for_route') for r in routes):
        raise ValueError('quality must not select reference')
    results = {r['record_id']: {} for r in routes}
    seen = set()
    for cell in cells:
        rid = cell['record_id']
        route = by_id[rid]
        key = (rid, cell['candidate'], cell['score_kind'])
        if key in seen or cell['image_code'] != route['image_code'] or (cell['new_candidate_id'] or None) != route['selected_candidate_id']:
            raise ValueError('duplicate or mismatched routed cell: ' + str(key))
        seen.add(key)
        value = float(cell['new_route_new_formula']) if cell['new_route_new_formula'] else None
        if value is not None and not math.isfinite(value):
            raise ValueError('nonfinite routed score: ' + str(key))
        if value is not None and (route['status'] != 'available' or
                (cell['score_kind'] == 'full' and route['selected_full_status'] != 'available')):
            raise ValueError('score contradicts route availability: ' + str(key))
        results[rid].setdefault(cell['candidate'], {})[cell['score_kind']] = value
    rows = []
    for route in routes:
        rid = route['record_id']
        gate = admission[rid]
        if any(route[k] != gate[k] for k in ('object_id', 'image_code', 'image_id', 'worker_id', 'condition')):
            raise ValueError('routed identity differs from current ledger: ' + rid)
        if len(results[rid]) != 3 or any(set(v) != {'floor', 'full'} for v in results[rid].values()):
            raise ValueError('incomplete routed candidate coverage: ' + rid)
        rows.append({'record_id': rid, 'object_id': route['object_id'],
            'scored_input': 'processed_mean_x_geometry', 'raw_input_penalty_included': False,
            'numerical_provenance': 'reused_pro_existing_results_not_local_geometry_recomputation',
            'formal_eligibility_newly_granted': False, 'independent_calibration_eligibility_granted': False,
            'current_coordinates_recomputed': False, 'in_frozen_922': gate['in_pro_922'],
            'outside_922_ordinary_manual_candidate': not gate['in_pro_922'] and gate['role'] == 'manual_development_candidate',
            'admission': {k: gate[k] for k in ('condition', 'role', 'current_personnel_gate', 'personnel_barriers', 'context_barriers', 'numeric_barriers')},
            'route': route, 'scores_under_selected_reference': results[rid]})
    def coverage(group):
        return dict(Counter('full' if any(v['full'] is not None for v in r['scores_under_selected_reference'].values())
                            else 'floor_only' if any(v['floor'] is not None for v in r['scores_under_selected_reference'].values())
                            else 'unavailable' for r in group))
    return {'schema': 'quality_existing_routed_view_20261013_v1',
        'source': 'quality_pro_joint_archive_20261013/source/integration/results/reference_formula_four_way.csv:new_route_new_formula',
        'summary': {'records': len(rows), 'coverage': coverage(rows),
                    'explicit_human_assignments_preserved': len(directives['manual_overrides']),
                    'human_family_restrictions_preserved': len(directives['manual_family_directives']),
                    'outside_922_ordinary_manual_candidates': coverage([r for r in rows if r['outside_922_ordinary_manual_candidate']]),
                    'outside_922_manual_all_references_restricted': coverage([r for r in rows if not r['in_frozen_922']
                        and r['admission']['condition'] == 'manual'
                        and 'all_existing_full_reference_versions_restricted' in r['admission']['context_barriers']])},
        'rows': rows}


def run():
    scorer, configs, search, admission = load_inputs()
    rows = [candidate_row(r, admission[r['id']], scorer, configs) for r in search['rows']]
    with (SOURCE / 'calibration/results/selected_scores_wide.csv').open(encoding='utf-8-sig', newline='') as f:
        expected = {r['record_id']: r for r in csv.DictReader(f)}
    if len(rows) != 922 or {r['record_id'] for r in rows} != set(expected):
        raise ValueError('frozen 922 coverage differs')
    max_delta = max(abs(r['scores'][name]['score'] - float(expected[r['record_id']][name]))
                    for r in rows for name in configs)
    if max_delta > 1e-9:
        raise ValueError('frozen score parity failed')
    summary = {
        'diagnostic_all_922': describe(rows, configs),
        'strict_old_admission_subset': describe([r for r in rows if r['strict_old_admission_subset']], configs),
        'old_applicability_counts': dict(Counter(str(r['old_applicability_confirmed']) for r in rows)),
        'by_condition': {k: describe([r for r in rows if r['admission']['condition'] == k], configs)
                         for k in sorted({r['admission']['condition'] for r in rows})},
        'by_current_role': {k: describe([r for r in rows if r['admission']['role'] == k], configs)
                            for k in sorted({r['admission']['role'] for r in rows})},
        'max_absolute_difference_from_archived_csv': max_delta,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    routed = existing_routed_view(admission)
    payload = {'schema': 'quality_current_candidate_view_20261013_v1',
        'policy': {'scored_input': 'processed_mean_x_geometry', 'raw_input_penalty_included': False,
                   'formal_eligibility_newly_granted': False,
                   'unconfirmed_old_applicability_is_not_reference_error': True,
                   'new_calibration_labels_created': False},
        'inputs': [str(SOURCE.relative_to(ROOT)), str(ADMISSION.relative_to(ROOT))],
        'summary': summary, 'rows': rows}
    for filename, obj in [('CANDIDATE_VIEW.json', payload), ('SUMMARY.json', summary), ('ROUTED_EXISTING_VIEW.json', routed)]:
        (OUT / filename).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    counts = summary['by_condition']
    lines = [
        '# 冻结质量候选的当前条件数值视图', '',
        '后续已完成[全量数据收尾及路由几何复算](../quality_data_closeout_20261013/README.md)。本页保留接入时的数值来源定义，不将后续复算冒称原接入步骤。', '',
        '本视图只接入 Pro 已冻结的处理后几何指标和四个候选，不重建几何、不调参、不恢复人员资格。', '',
        f"覆盖922份旧输入（manual {counts['manual']['records']}份，semi {counts['semi']['records']}份）；与旧逐份CSV四候选最大差值为 {max_delta:.3g}。",
        '全量manual仍为2344份；本输出不代表新增了包外manual评分。', '',
        '## 评价对象与使用边界', '',
        '- `scored_input=processed_mean_x_geometry`：评分对象为已有平均x处理后的条件几何；原始坐标、配对语义不由Q认证。',
        '- `raw_input_penalty_included=false`：`raw_alignment`保留原始上下点经度差诊断，不加权进Q；大经度差本身也不等于语义配对错误。',
        '- `conditional_diagnostic_use=true`：922份可在各自冻结参考条件下比较数值，并非都可作主校准、人员评级或独立检验。',
        '- `old_applicability_confirmed=false`仅表示旧显式适用子层未确认，不自动等价于参考错误。当前账本numeric_barriers按原值留存，不能仅据其中这一状态封禁条件数值分析。',
        '- `strict_old_admission_subset`要求当前账本full_q_calibration_ready且旧applicability_confirmed=true，供复核旧显式适用子层。它不是本工具重新授予资格。',
        '- `admission`保留来源、人员gate、当前role、人员/上下文/数值限制及原留出。限制不改分；使用范围必须另行遵守，留出不能回流调参。',
        '- 缺高度时完整score与高度损失为null，floor_score单列；不能将缺项补零或当完整质量。', '',
        '## 分项与结果', '',
        '`scores`下四候选均给出底面分、完整分、边界/方向/整体高度/局部高度损失及高度引起的降分。`SUMMARY.json`按来源和当前role描述分数变化；它们是同样本数值变化，不是有效性排名。', '',
        '| 候选 | 922份均分 | 相对baseline均值变化 |', '|---|---:|---:|',
    ]
    for name, stats in summary['diagnostic_all_922']['candidates'].items():
        lines.append(f"| {name} | {stats['mean']:.3f} | {stats['mean_delta_from_baseline']:+.3f} |")
    lines += ['', f"旧严格视图共{summary['strict_old_admission_subset']['records']}份，仅保留历史筛选口径。",
        '', '## 已有多空间路由结果的独立接入', '',
        '`ROUTED_EXISTING_VIEW.json`原样复用Pro四方比较表的new_route_new_formula，按record_id/candidate/score_kind绑定routes中的selected_candidate_id。三个J候选分别保留floor/full，空值不补零，不移植其他参考的顶部。', '',
        f"路由共{routed['summary']['records']}份，覆盖：{routed['summary']['coverage']}。其中原922之外的普通manual开发候选覆盖：{routed['summary']['outside_922_ordinary_manual_candidates']}。",
        '此输出与922份冻结参考视图分开：两者参考可能不同，不覆盖或拼接为统一的完整分。保留原路由版本、人工影响、参考不确定性、当前用途限制与原始诊断。',
        '参考沿用已有人工作答指定、候选族限制与局部结构优先/底面接近兜底；不按最高Q重选。执行时核对5项人工指定和2项候选族限制。四参考T30/R02962保留人工D；W031/W034仅限A/B族，不能称人工指定B。旧原始/修订GT的双版本敏感性列不等于此处多空间路由。',
        f"另有包外manual因原完整参考受限而单列：{routed['summary']['outside_922_manual_all_references_restricted']}。q9vSo1VnCiC-16的5份替代底面结果不自动被原GT限制否定，但不能移植顶面或恢复原完整GT；原318份覆盖现分为313份普通候选与这5份参考条件不同的诊断。该summary历史字段名只统计现有完整参考限制，不表示所有替代底面也被禁用。",
        '`numerical_provenance`明确这些是已有Pro结果，未在本地重建几何；核对的是记录身份、所选参考标识和空值边界，不授予正式资格或独立拟合资格。',
        '[原始标注与处理后几何的证据核对](../quality_processed_input_20261013/README.md)。',
        '', '## 复现与检查', '',
        '`python -B -m tools.thesis_main.analysis.quality_current_candidate_view_20261013`', '',
        '`python -B -m pytest tests/test_quality_current_candidate_view_20261013.py -q`', '',
        '四个边界检查：原始诊断/资格变化不改变固定几何分数；缺高度不补零；旧适用子层未确认不取消条件计算；复用路由缺顶部仍为null。执行时另逐份核对922份与旧CSV和路由身份/参考绑定。', '',
        '未重跑网格、未改变正式算法或历史输入；参考是否适合当前研究与指标是否符合人评，仍需独立证据。']
    (OUT / 'README.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    run()
