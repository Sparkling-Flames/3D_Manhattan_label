"""Update only two affected finite composition panels with fixed labels/teams.

The original aggregation implementation is reused verbatim on the 45 existing
teams in these two panels. Its baseline is checked against the frozen release,
then updated panel statistics replace the corresponding rows in the 67-panel
archive before the original panel -> pool -> image -> building macro average.
"""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from .evaluate_manual_order_half_qonly_20261104 import clean, merge_endpoint, read_rows

ROOT = Path(__file__).resolve().parents[3]
REL = ROOT / 'research/data/releases/v2.1'
UP = REL / 'admitted_space_extension/image_difficulty_20261030'
OLD = UP / 'composition/other'
WORKER = ROOT / 'research/workers/personnel_v21_reselection_20261029'
DESIGN = WORKER / 'additional_delivery/packages/03A/composition/other_targets_design'
ENDPOINTS = WORKER / 'additional_delivery/packages/03A/composition/other_targets_endpoints/ENDPOINT_SCALARS.csv.gz'
BASE = ROOT / 'research/fusion/manual_order_impact_20261104'
OUT = BASE / 'composition'
LABELS = UP / 'composition_other_labels.csv.gz'
CONDITIONS = UP / 'composition_other_conditions.csv'
SOURCE_CODE = WORKER / 'composition/code/aggregate_frozen_panels.py'
FORMATIONS = {'failure', 'connection_available', 'order_tied', 'below_four', 'location_unresolved'}


def original_module():
    spec = importlib.util.spec_from_file_location('manual_order_original_composition', SOURCE_CODE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(path):
    return pd.read_csv(path, low_memory=False)


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(obj), ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def parity(a, b, keys, label, checks, numeric=None):
    """Align exact rows, check missingness, numeric values and design categories."""
    assert not a.duplicated(keys).any() and not b.duplicated(keys).any(), label
    aa, bb = a.set_index(keys).sort_index(), b.set_index(keys).sort_index()
    assert aa.index.equals(bb.index), (label, 'row keys')
    if numeric is None:
        numeric = [c for c in aa.select_dtypes(include=['number', 'bool']) if c in bb]
    maximum = 0.0
    for column in numeric:
        x, y = pd.to_numeric(aa[column]), pd.to_numeric(bb[column])
        assert x.isna().equals(y.isna()), (label, column, 'missingness')
        mask = x.notna()
        xv, yv = x[mask].astype(float).to_numpy(), y[mask].astype(float).to_numpy()
        assert np.allclose(xv, yv, rtol=1e-10, atol=1e-8), (label, column, np.max(np.abs(xv-yv)))
        maximum = max(maximum, float(np.max(np.abs(xv-yv))) if len(xv) else 0.0)
    checks.append(dict(check=label, rows=len(aa), numeric_columns=len(numeric), maximum_absolute_error=maximum))


def invoke_original(module, endpoints, version, methods):
    argv = sys.argv
    sys.argv = [str(SOURCE_CODE), '--inputs', str(OUT/'affected_inputs'), '--endpoints', str(endpoints),
                '--labels', str(LABELS), '--out', str(OUT/'replay'/version), '--methods', ','.join(methods),
                '--condition', 'manual', '--target-conditions', str(CONDITIONS)]
    try:
        module.main()
    finally:
        sys.argv = argv


def prepare(module, checks):
    refs = read(ROOT / 'research/fusion/missing_ring_review_20261104/user_order_return/AFFECTED_CURRENT_REFERENCES.csv.gz')
    refs = refs[refs.module.eq('composition_other')]
    keys, affected_panels = set(refs.team_key), set(refs.event_id)
    assert len(keys) == len(affected_panels) == 2
    auxiliary = {row['team_key']: row for row in read_rows(BASE / 'endpoints/ENDPOINTS.jsonl.gz') if row['team_key'] in keys}
    assert set(auxiliary) == keys
    panels = read(DESIGN/'PANELS_USED.csv')
    panels = panels[panels.panel_id.isin(affected_panels)]
    links = read(DESIGN/'PANEL_TEAMS.csv.gz')
    links = links[links.panel_id.isin(affected_panels)]
    assert len(panels) == 2 and len(links) == 45
    wanted = set(links.team_key)
    members = read(DESIGN/'TEAM_REQUESTS.csv.gz')
    members = members[members.team_key.isin(wanted)]
    old = read(ENDPOINTS)
    old = old[old.team_key.isin(wanted)].copy().reset_index(drop=True)
    assert len(old) == len(members) == 45 and old.team_key.is_unique
    for filename, frame in [('PANELS_USED.csv', panels), ('PANEL_TEAMS.csv.gz', links), ('TEAM_REQUESTS.csv.gz', members)]:
        module.save_csv(OUT/'affected_inputs'/filename, frame)
    revised = []
    for row in old.to_dict('records'):
        changed = merge_endpoint(row, auxiliary[row['team_key']]) if row['team_key'] in auxiliary else row.copy()
        # Preserve the original scalar member-list encoding as well as membership.
        # The generic endpoint JSON uses lists; this CSV contract uses pipes.
        for field in ('member_workers', 'member_object_ids'):
            changed[field] = row[field]
        # Retain exactly the existing scalar schema; the original aggregator derives failure.
        revised.append({column: changed.get(column) for column in old})
    revised = pd.DataFrame(revised, columns=old.columns)
    unchanged = ~old.team_key.isin(keys)
    pd.testing.assert_frame_equal(old.loc[unchanged], revised.loc[unchanged], check_dtype=False)
    time_columns = [c for c in old if 'time' in c]
    for column in time_columns:
        pd.testing.assert_series_equal(old[column], revised[column], check_dtype=False)
    metrics = [c for c in module.METRICS if c in old and c not in FORMATIONS]
    for metric in metrics:
        mask = pd.to_numeric(old[metric], errors='coerce').notna()
        assert np.allclose(pd.to_numeric(old.loc[mask, metric]), pd.to_numeric(revised.loc[mask, metric]),
                           rtol=1e-10, atol=1e-8), ('original endpoint support', metric)
    common = revised.copy()
    for metric in metrics:
        common.loc[pd.to_numeric(old[metric], errors='coerce').isna(), metric] = np.nan
    for version, frame in [('automatic', old), ('assisted_original_support', common), ('assisted_expanded', revised)]:
        module.save_csv(OUT/'affected_inputs'/(version+'_ENDPOINT_SCALARS.csv.gz'), frame)
    statuses = []
    for key in sorted(keys):
        a, b = old.set_index('team_key').loc[key], revised.set_index('team_key').loc[key]
        statuses.append(dict(team_key=key, image=a.image, k=a.k, nodes=a.nodes,
                             reference_id=a.reference_id, reference_version=a.reference_version,
                             automatic_Q=a.B8L2, assisted_Q=b.B8L2,
                             automatic_status=a.score_status, assisted_status=b.score_status,
                             original_Q_missing=True, numerical_improvement_from_zero=None))
    module.save_csv(OUT/'AFFECTED_ENDPOINT_STATUS.csv', pd.DataFrame(statuses))
    checks.append(dict(check='endpoint_identity_and_original_common_support', affected_endpoints=2,
                       retained_panel_teams=45, unchanged_teams=43, time_columns=len(time_columns),
                       fixed_metrics=len(metrics), passed=True))
    return affected_panels, keys, old, revised


def merged_panels(archive, replacement, affected, keys):
    assert set(replacement.panel_id) == affected
    result = pd.concat([archive[~archive.panel_id.isin(affected)], replacement], ignore_index=True)
    assert not result.duplicated(keys).any()
    assert set(result.panel_id) == set(archive.panel_id)
    return result


def report(comparison, panel_variance, statuses, checks, methods):
    conclusions = []
    rows = comparison[comparison.summary_axis.eq('all') & comparison.metric.eq('B8L2')]
    text = ['# 人工辅助顺序对完整有限配比的影响', '',
            '只对已有的2个其它目标Manual面板补入2个固定节点人工顺序端点；35队与10队的成员全集、类别标签、参考和人数均保持。'
            '原67面板、28图、9楼的其它65面板统计直接沿用。11种既有冻结标签仅用于保留原方法映射，不开展分类重选。', '',
            '## 两个新增可评端点', '', '|图片|团队人数|融合节点|原状态|辅助Q|', '|---|---:|---:|---|---:|']
    for row in statuses.itertuples():
        text.append(f'|{row.image}|{row.k}|{row.nodes}|{row.automatic_status}|{row.assisted_Q:.6f}|')
    text += ['', '原Q为空，新增Q不是从0提高。来源：[AFFECTED_ENDPOINT_STATUS.csv](AFFECTED_ENDPOINT_STATUS.csv)。', '',
             '## 全部原面板上的质量方差分解', '',
             '每个面板按完整团队类别计数向量分组，保留method_known与11方法共享shared_known两种支持。'
             '按原实现分解总方差=同配比成员内方差+配比间方差；再按面板→目标池→图片→建筑等权汇总，'
             '最后以宏观配比间方差除以宏观总方差。不会先对各面板比例直接平均。', '',
             '|冻结方法|标签支持|原配比间占比|辅助后占比|原可评团队链接→新链接|', '|---|---|---:|---:|---:|']
    for method in methods:
        for support in ['method_known', 'shared_known']:
            part = rows[rows.method.eq(method) & rows.support.eq(support)].set_index('version')
            a, b = part.loc['automatic'], part.loc['assisted_expanded']
            text.append(f'|{method}|{support}|{a.between_share:.6%}|{b.between_share:.6%}|'
                        f'{int(a.valid_team_links)}→{int(b.valid_team_links)}|')
            status = '保持' if abs(a.between_share-b.between_share) < 1e-10 else '幅度变化'
            conclusions.append(dict(topic=method+'/'+support+'/全局Q配比间占比', status=status,
                                    automatic=a.between_share, assisted=b.between_share,
                                    source='ALL_METHOD_COMPARISON.csv', explanation='原共同Q支持保持；新增可评成员改变原配比组的分布与方差'))
    text += ['', '来源：[ALL_METHOD_COMPARISON.csv](ALL_METHOD_COMPARISON.csv)。表中方法顺序沿冻结方法名称，未根据辅助结果选择分类。', '',
             '## TARGET_DSTRUCT_K3的受影响面板', '',
             '|图片/人数|支持|原Q可评队→新队|原同配比方差→新|原配比间方差→新|原配比间占比→新|',
             '|---|---|---:|---:|---:|---:|']
    target = panel_variance[panel_variance.method.eq('TARGET_DSTRUCT_K3') & panel_variance.metric.eq('B8L2')]
    for (panel, support), group in target.groupby(['panel_id', 'support']):
        part = group.set_index('version')
        a, b = part.loc['automatic'], part.loc['assisted_expanded']
        text.append(f'|{a.image}/{int(a.n)}|{support}|{int(a.valid_teams)}→{int(b.valid_teams)}|'
                    f'{a.within_variance:.6f}→{b.within_variance:.6f}|{a.between_variance:.6f}→{b.between_variance:.6f}|'
                    f'{a.between_share:.6%}→{b.between_share:.6%}|')
        dominant_flip = (a.within_variance > a.between_variance) != (b.within_variance > b.between_variance)
        status = '需改写' if dominant_flip else '幅度变化' if abs(a.total_variance-b.total_variance) > 1e-10 else '保持'
        conclusions.append(dict(topic=f'{a.image}/n{int(a.n)}/{support}/成员与配比波动', status=status,
                                automatic=a.between_share, assisted=b.between_share,
                                source='AFFECTED_PANEL_VARIANCE.csv.gz',
                                explanation='原有限成员全集固定；比较现有可评队，缺失Q没有计为0'))
    text += ['', '来源：[AFFECTED_PANEL_VARIANCE.csv.gz](AFFECTED_PANEL_VARIANCE.csv.gz)。分布、分位数、标准差、IQR、范围与失败支持见'
             '[AFFECTED_CONFIGURATION_DISTRIBUTIONS.csv.gz](AFFECTED_CONFIGURATION_DISTRIBUTIONS.csv.gz)、'
             '[AFFECTED_CONFIGURATION_COUNTS.csv.gz](AFFECTED_CONFIGURATION_COUNTS.csv.gz)。'
             '同配比仍有成员波动时，不能用一个配比均值代替成员分布。', '',
             '这两个新增可评端点在TARGET_DSTRUCT_K3下恰好各自属于一个只有1队的配比：'
             'rPc6-06为C1:2、C2:2、C3:0的混合配比，uNb9-88为C1:0、C2:3、C3:0的纯C2配比。'
             '各自由0队可评变为1队可评，其同配比成员波动仍不可估。'
             '面板整体同配比方差下降包含新增单队配比所带来的分母变化，不表示原有成员组合变得更稳定。', '',
             '## 原共同支持与未变项', '',
             '辅助版另在每一指标原有可评团队上重算：全部原质量/几何支持与方差保持。失败、连接可用性等形成指标单独更新，'
             '不当作旧Q改善。标签、团队类别计数、已知/共享已知支持、组合容量与完整成员穷举判断逐项校验保持。'
             '原标注时间字段及其按来源拆分的分布和方差均保持；人工排序劳动没有计时，不能计算包含介入成本的总效益。', '',
             '57组人工处理为定向选择；这里2队不能外推到所有无环团队，也不能作为分类选型的新样本。', '',
             '## 复现与来源', '',
             '`python -m tools.thesis_main.analysis.evaluate_manual_order_composition_20261104`', '',
             '原聚合函数：`research/workers/personnel_v21_reselection_20261029/composition/code/aggregate_frozen_panels.py`。'
             '本脚本先精确复现原2面板的方差、配置计数和分布，再逐面板替换原全表并重跑原macro；'
             '固定标签来源`composition_other_labels.csv.gz`与难度/范围来源`composition_other_conditions.csv`均保留散列。'
             '检查与来源见[CHECKS.json](CHECKS.json)、[INPUT_MANIFEST.json](INPUT_MANIFEST.json)。']
    conclusions += [dict(topic='冻结分类/团队/标签支持/组合容量', status='保持', source='CHECKS.json',
                         explanation='固定11标签映射；method_known/shared_known、完整成员向量及配比配置不变'),
                    dict(topic='原共同质量/几何支持', status='保持', source='ALL_METHOD_COMPARISON.csv;CHECKS.json',
                         explanation='assisted_original_support按原有限值支持重算，与自动统计对齐'),
                    dict(topic='原标注劳动', status='保持', source='CHECKS.json', explanation='所有记录时间及原时间分层统计不变'),
                    dict(topic='含人工排序的成本效益', status='尚不能判断', source='AFFECTED_ENDPOINT_STATUS.csv',
                         explanation='没有人工排序计时，不将原劳动当作完整辅助成本'),
                    dict(topic='TARGET_DSTRUCT_K3新增混合/纯类配比可评支持', status='条件变化',
                         source='AFFECTED_CONFIGURATION_COUNTS.csv.gz',
                         explanation='rPc的2:2:0混合配比、uNb的0:3:0纯类配比各从0队可评变为1队可评'),
                    dict(topic='两种新增可评配比的同配比成员稳定性', status='尚不能判断',
                         source='AFFECTED_CONFIGURATION_DISTRIBUTIONS.csv.gz',
                         explanation='两种配比各只有1个实际成员组合，sd/IQR/range与成员变动不可估，不用单队证明稳定')]
    (OUT/'REPORT_ZH.md').write_text('\n'.join(text)+'\n', encoding='utf-8')
    return pd.DataFrame(conclusions)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    module = original_module()
    checks = []
    methods = json.loads((OLD/'COMPLETE.json').read_text())['methods']
    assert len(methods) == 11
    labels, maps = module.load_labels([LABELS], methods)
    assert set(maps) == set(methods)
    affected, keys, endpoints_old, endpoints_new = prepare(module, checks)
    versions = ['automatic', 'assisted_original_support', 'assisted_expanded']
    for version in versions:
        invoke_original(module, OUT/'affected_inputs'/(version+'_ENDPOINT_SCALARS.csv.gz'), version, methods)
    summaries, variances, counts, distributions, full_variances, design_invariants = [], [], [], [], [], []
    source_files = [SOURCE_CODE, LABELS, CONDITIONS, ENDPOINTS, BASE/'endpoints/ENDPOINTS.jsonl.gz',
                    DESIGN/'PANELS_USED.csv', DESIGN/'PANEL_TEAMS.csv.gz', DESIGN/'TEAM_REQUESTS.csv.gz', OLD/'COMPLETE.json']
    variance_keys = ['panel_id', 'method', 'support', 'metric', 'time_source']
    configuration_keys = ['panel_id', 'method', 'support', 'class_counts']
    distribution_keys = configuration_keys+['metric', 'time_source']
    summary_keys = ['method', 'condition', 'support', 'metric', 'time_source', 'summary_axis', 'summary_value']
    for method in methods:
        archive = OLD/'by_method'/method
        old_var = read(archive/'PANEL_VARIANCE.csv.gz')
        old_count = read(archive/'CONFIGURATION_COUNTS.csv.gz')
        old_dist = read(archive/'CONFIGURATION_DISTRIBUTIONS.csv.gz')
        old_summary = read(archive/'SUMMARY.csv')
        source_files += [archive/name for name in ['PANEL_VARIANCE.csv.gz', 'CONFIGURATION_COUNTS.csv.gz',
                         'CONFIGURATION_DISTRIBUTIONS.csv.gz', 'TEAM_CLASS_VECTORS.csv.gz', 'PANEL_COVERAGE.csv.gz', 'SUMMARY.csv']]
        baseline = OUT/'replay/automatic/by_method'/method
        parity(old_var[old_var.panel_id.isin(affected)], read(baseline/'PANEL_VARIANCE.csv.gz'), variance_keys,
               method+'/affected_original_variance', checks)
        parity(old_count[old_count.panel_id.isin(affected)], read(baseline/'CONFIGURATION_COUNTS.csv.gz'), configuration_keys,
               method+'/affected_original_configurations', checks)
        parity(old_dist[old_dist.panel_id.isin(affected)], read(baseline/'CONFIGURATION_DISTRIBUTIONS.csv.gz'), distribution_keys,
               method+'/affected_original_distributions', checks)
        parity(old_summary, module.macro(old_var), summary_keys, method+'/original_macro', checks)
        original_vectors = read(archive/'TEAM_CLASS_VECTORS.csv.gz')
        original_vectors = original_vectors[original_vectors.panel_id.isin(affected)]
        original_coverage = read(archive/'PANEL_COVERAGE.csv.gz')
        original_coverage = original_coverage[original_coverage.panel_id.isin(affected)]
        method_summaries = {}
        for version in versions:
            directory = OUT/'replay'/version/'by_method'/method
            new_var, new_count, new_dist = (read(directory/name) for name in
                                           ['PANEL_VARIANCE.csv.gz', 'CONFIGURATION_COUNTS.csv.gz', 'CONFIGURATION_DISTRIBUTIONS.csv.gz'])
            vectors = read(directory/'TEAM_CLASS_VECTORS.csv.gz')
            coverage = read(directory/'PANEL_COVERAGE.csv.gz')
            pd.testing.assert_frame_equal(original_vectors.sort_values(['panel_id', 'team_key']).reset_index(drop=True),
                                          vectors.sort_values(['panel_id', 'team_key']).reset_index(drop=True), check_dtype=False)
            parity(original_coverage, coverage, ['panel_id', 'method'], method+'/'+version+'/label_coverage', checks)
            for column in ['background_class_counts', 'selected_variable_counts', 'variable_class_capacity',
                           'teams', 'possible_member_sets_on_label_support', 'member_census_complete',
                           'member_variation_estimable', 'pure_class_team', 'maximum_class_fraction']:
                aa = old_count[old_count.panel_id.isin(affected)].set_index(configuration_keys)[column].sort_index()
                bb = new_count.set_index(configuration_keys)[column].sort_index()
                pd.testing.assert_series_equal(aa, bb, check_dtype=False)
            combined = merged_panels(old_var, new_var, affected, variance_keys)
            summary = module.macro(combined)
            method_summaries[version] = summary
            for frame, store in [(summary, summaries), (new_var, variances), (new_count, counts),
                                 (new_dist, distributions), (combined, full_variances)]:
                frame = frame.copy(); frame['version'] = version; store.append(frame)
            design_invariants.append(dict(method=method, version=version, affected_panels=2,
                                          affected_team_links=len(vectors), known_teams=int(module.truth(vectors.known).sum()),
                                          shared_known_teams=int(module.truth(vectors.shared_known).sum()),
                                          classifications_fixed=True, team_compositions_fixed=True))
        old_s, common_s = method_summaries['automatic'], method_summaries['assisted_original_support']
        parity(old_s[~old_s.metric.isin(FORMATIONS)], common_s[~common_s.metric.isin(FORMATIONS)], summary_keys,
               method+'/original_metric_support_macro_invariance', checks)
        new_s = method_summaries['assisted_expanded']
        parity(old_s[old_s.metric.isin(module.TIME_METRICS)], new_s[new_s.metric.isin(module.TIME_METRICS)], summary_keys,
               method+'/annotation_labour_macro_invariance', checks)
    comparison, affected_var = pd.concat(summaries, ignore_index=True), pd.concat(variances, ignore_index=True)
    for name, frame in [('ALL_METHOD_COMPARISON.csv', comparison), ('AFFECTED_PANEL_VARIANCE.csv.gz', affected_var),
                        ('AFFECTED_CONFIGURATION_COUNTS.csv.gz', pd.concat(counts, ignore_index=True)),
                        ('AFFECTED_CONFIGURATION_DISTRIBUTIONS.csv.gz', pd.concat(distributions, ignore_index=True)),
                        ('ALL_PANEL_VARIANCE.csv.gz', pd.concat(full_variances, ignore_index=True)),
                        ('DESIGN_INVARIANTS.csv', pd.DataFrame(design_invariants))]:
        module.save_csv(OUT/name, frame)
    manifest = []
    for path in dict.fromkeys(source_files):
        with path.open('rb') as handle: digest = hashlib.file_digest(handle, 'sha256').hexdigest()
        manifest.append(dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size, sha256=digest))
    write_json(OUT/'INPUT_MANIFEST.json', dict(source_commit='ac395e703d1fef573d1ef3e105df0286d62a0468', files=manifest))
    receipt = dict(source_commit='ac395e703d1fef573d1ef3e105df0286d62a0468', affected_endpoints=2,
                   affected_panels=sorted(affected), affected_panel_teams=45, original_panels=67,
                   original_images=28, original_buildings=9, frozen_methods=methods,
                   original_team_links=8935, no_new_teams=True, no_classification_reselection=True,
                   original_common_metric_support_preserved=True, label_support_preserved=True,
                   original_annotation_time_preserved=True, human_sorting_time=None,
                   missing_Q_imputed=False, original_files_overwritten=False,
                   original_fuse_calls=0, new_scoring_calls=0,
                   weighting='panel -> target pool -> image -> building; ratio formed after variance macro average',
                   checks=checks)
    write_json(OUT/'CHECKS.json', receipt)
    conclusions = report(comparison, affected_var, read(OUT/'AFFECTED_ENDPOINT_STATUS.csv'), checks, methods)
    module.save_csv(OUT/'CONCLUSIONS.csv', conclusions)
    (OUT/'README.md').write_text('''# 完整有限配比人工辅助敏感性补算\n\n主报告：[REPORT_ZH.md](REPORT_ZH.md)。逐条结论：[CONCLUSIONS.csv](CONCLUSIONS.csv)。\n\n只更新2端点所在的2个有限面板（35+10队），固定11种现有标签与method_known/shared_known支持。原其它65面板统计复用后，按原panel→pool→image→building计权重新汇总。没有分类训练、重新选型、添加团队或新的融合计算。\n\n- `affected_inputs/`：精确2面板、45队的固定设计及原/辅助端点标量。\n- `replay/automatic/`：复现的原2面板输出，必须与冻结结果逐项对齐。\n- `replay/assisted_expanded/`：扩展可评支持下的2面板输出。\n- `replay/assisted_original_support/`：逐指标遮罩到原有限值支持的敏感性对照，形成指标单独允许变化。\n- `AFFECTED_PANEL_VARIANCE.csv.gz`：受影响面板各质量/几何/形成/劳动指标的方差分解。\n- `AFFECTED_CONFIGURATION_COUNTS.csv.gz` / `AFFECTED_CONFIGURATION_DISTRIBUTIONS.csv.gz`：同配比的原、新可评队数、失败、完整成员穷举、分位数和成员波动。\n- `ALL_PANEL_VARIANCE.csv.gz` / `ALL_METHOD_COMPARISON.csv`：原67面板的各版本全表与按原层级的宏统计。\n- `DESIGN_INVARIANTS.csv`、`CHECKS.json`、`INPUT_MANIFEST.json`：固定标签/成员/时间、原基线parity和来源版本散列。\n\n运行 `python -m tools.thesis_main.analysis.evaluate_manual_order_composition_20261104` 复现。原自动数据不覆盖；原缺失Q不能按0分计收益；人工排序未计时；2队属于57个定向案例，不能推广为所有无环结果的修复率。\n''', encoding='utf-8')
    print(json.dumps(clean({k: v for k, v in receipt.items() if k != 'checks'}), ensure_ascii=False, indent=2))
    print('parity checks', len(checks))


if __name__ == '__main__':
    main()
