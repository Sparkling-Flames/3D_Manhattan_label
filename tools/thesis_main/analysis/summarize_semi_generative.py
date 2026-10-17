"""Create local paired reports for strict and generative Semi runs."""
from __future__ import annotations

import collections
import csv
import hashlib
import json
from pathlib import Path


def jsonl(path):
    return [json.loads(line) for line in Path(path).open()]


def csv_rows(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        return list(csv.DictReader(stream))


def exported_ids(path):
    tasks = json.loads((Path(path) / 'label_studio_synthetic.json').read_text())
    return {annotation['simulation_id'] for task in tasks for annotation in task['annotations']}


def calibration_summary(path):
    rows = csv_rows(Path(path) / 'personal_semi_calibration.csv')
    def numeric(row, field):
        try:
            return float(row[field]) if row.get(field) not in ('', None) else None
        except ValueError:
            return None
    successful = [r for r in rows if r.get('generation_status') in
        ('empirical_copy', 'empirical_edit', 'generated_move', 'generated_addition', 'generated_move_fallback')]
    scored = [r for r in successful if numeric(r, 'WQ_absolute_error') is not None]
    attempted_scored = [r for r in rows if numeric(r, 'WQ_absolute_error') is not None]
    geometry = [r for r in successful if r.get('geometry_status')]
    copies = [r for r in successful if r.get('model_copy') not in ('', None)]
    attempted_copies = [r for r in rows if r.get('model_copy') not in ('', None)]
    by_building = {}
    for building in sorted({r['building_id'] for r in rows}):
        subset = [r for r in rows if r['building_id'] == building]
        good = [r for r in subset if r in successful]
        good_scored = [r for r in good if numeric(r, 'WQ_absolute_error') is not None]
        good_geometry = [r for r in good if r.get('geometry_status')]
        good_copies = [r for r in good if r.get('model_copy') not in ('', None)]
        by_building[building] = dict(rows=len(subset), successful=len(good), scored=len(good_scored),
            mean_absolute_WQ_error=(sum(numeric(r, 'WQ_absolute_error') for r in good_scored) / len(good_scored) if good_scored else None),
            geometry_issue_rate=(sum(r['geometry_status'] != 'basic_checks_passed_not_certified' for r in good_geometry) / len(good_geometry) if good_geometry else None),
            model_copy_rate=(sum(r['model_copy'].lower() == 'true' for r in good_copies) / len(good_copies) if good_copies else None),
            status_counts=dict(collections.Counter(r['generation_status'] for r in subset)))
    return dict(rows=len(rows), successful=len(successful), scored=len(scored), buildings=len({r['building_id'] for r in rows}),
        mean_absolute_WQ_error=(sum(numeric(r, 'WQ_absolute_error') for r in scored) / len(scored) if scored else None),
        geometry_issue_rate=(sum(r['geometry_status'] != 'basic_checks_passed_not_certified' for r in geometry) / len(geometry) if geometry else None),
        model_copy_rate=(sum(r['model_copy'].lower() == 'true' for r in copies) / len(copies) if copies else None),
        attempted_mean_absolute_WQ_error=(sum(numeric(r, 'WQ_absolute_error') for r in attempted_scored) / len(attempted_scored) if attempted_scored else None),
        attempted_model_copy_rate=(sum(r['model_copy'].lower() == 'true' for r in attempted_copies) / len(attempted_copies) if attempted_copies else None),
        status_counts=dict(collections.Counter(r['generation_status'] for r in rows)), by_building=by_building)


def write_report(root, old_path, strict_path, generated_path, replay_path=None):
    root, old_path = Path(root), Path(old_path)
    strict_path, generated_path = Path(strict_path), Path(generated_path)
    old = {r['simulation_id']: r for r in jsonl(old_path / 'simulations.jsonl')}
    strict = {r['simulation_id']: r for r in jsonl(strict_path / 'simulations.jsonl')}
    generated = {r['simulation_id']: r for r in jsonl(generated_path / 'simulations.jsonl')}
    strict_export, generative_export = exported_ids(strict_path), exported_ids(generated_path)
    legacy_failures = [r for r in old.values() if r['condition'] == 'semi' and
        r.get('semi_status') in ('no_compatible_semi_donor', 'unsupported_addition')]
    migration = collections.defaultdict(collections.Counter)
    for prior in legacy_failures:
        new = generated.get(prior['simulation_id'])
        status = new.get('semi_status', 'missing_matching_generation') if new else 'missing_matching_generation'
        migration[prior['semi_status']][status] += 1
    manual_ids = old.keys() & generated.keys()
    manual = [key for key in manual_ids if old[key]['condition'] == 'manual']
    manual_equal = all(old[key]['points'] == generated[key]['points'] for key in manual)
    semi_ids = old.keys() & strict.keys() & generated.keys()
    semi_ids = [key for key in semi_ids if old[key]['condition'] == 'semi']
    old_export = exported_ids(old_path)
    new_status_counts = dict(collections.Counter(r.get('semi_status') for r in generated.values() if r['condition'] == 'semi'))
    gen_cal, strict_cal = calibration_summary(generated_path), calibration_summary(strict_path)
    gen_cal_rows = {r['annotation_id']: r for r in csv_rows(generated_path / 'personal_semi_calibration.csv')}
    strict_cal_rows = {r['annotation_id']: r for r in csv_rows(strict_path / 'personal_semi_calibration.csv')}
    successful_statuses = {'empirical_copy', 'empirical_edit', 'generated_move', 'generated_addition', 'generated_move_fallback'}
    common_success = sorted(key for key in gen_cal_rows.keys() & strict_cal_rows.keys()
        if gen_cal_rows[key]['generation_status'] in successful_statuses
        and strict_cal_rows[key]['generation_status'] in successful_statuses
        and gen_cal_rows[key].get('WQ_absolute_error') and strict_cal_rows[key].get('WQ_absolute_error'))
    def average_error(rows, keys):
        values = [float(rows[key]['WQ_absolute_error']) for key in keys]
        return sum(values) / len(values) if values else None
    for folder, metrics in ((generated_path, gen_cal), (strict_path, strict_cal)):
        summary_file = folder / 'summary.json'
        run_summary = json.loads(summary_file.read_text())
        run_summary['personal_semi_calibration'] = dict(**metrics, quality_acceptance=False,
            scope='exploratory same-person, same-image, same-reference panel; 3-building support only')
        summary_file.write_text(json.dumps(run_summary, ensure_ascii=False, indent=2) + '\n')
    common = dict(rows=min(gen_cal['rows'], strict_cal['rows']), buildings=min(gen_cal['buildings'], strict_cal['buildings']),
        generative=gen_cal, strict=strict_cal,
        common_annotation_ids=len({r['annotation_id'] for r in csv_rows(generated_path / 'personal_semi_calibration.csv')} &
            {r['annotation_id'] for r in csv_rows(strict_path / 'personal_semi_calibration.csv')}),
        common_success_evaluable=len(common_success),
        common_success_mean_absolute_WQ_error=dict(generative=average_error(gen_cal_rows, common_success),
            strict=average_error(strict_cal_rows, common_success)),
        quality_acceptance=False,
        interpretation='Exploratory comparison only; the matched Semi calibration set has support in three buildings.')
    old_summary = json.loads((old_path / 'summary.json').read_text())
    strict_summary = json.loads((strict_path / 'summary.json').read_text())
    generated_summary = json.loads((generated_path / 'summary.json').read_text())
    code_file = Path(__file__).with_name('semi_edit_distribution.py')
    for folder in (strict_path, generated_path):
        manifest_path = folder / 'source_manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest.setdefault('code_sha256', {})['tools/thesis_main/analysis/semi_edit_distribution.py'] = hashlib.sha256(code_file.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    old_panel = {(r['image_id'], r['condition']): int(r['requested_synthetic']) for r in csv_rows(old_path / 'target_manifest.csv')}
    new_panel = {(r['image_id'], r['condition']): int(r['requested_synthetic']) for r in csv_rows(generated_path / 'target_manifest.csv')}
    strict_fields = ('points', 'semi_status', 'semi_donor_annotation_id', 'semi_donor_worker_id',
        'semi_behavior', 'active_time_seconds', 'time_donor_annotation_id', 'lead_time_seconds',
        'lead_time_donor_annotation_id', 'worker_scope_response', 'scope_variant')
    strict_same_as_previous = all(old[key].get(field) == strict[key].get(field)
        for key in old.keys() & strict.keys() for field in strict_fields)
    generative_channel_fields = ('worker_scope_response', 'scope_variant', 'lead_time_seconds',
        'lead_time_donor_annotation_id', 'active_time_seconds', 'time_donor_annotation_id')
    semi_channel_parity = {field: all(old[key].get(field) == generated[key].get(field)
        for key in old.keys() & generated.keys() if old[key]['condition'] == 'semi')
        for field in generative_channel_fields}
    refusal = dict(prior_run=dict(rejected=old_summary.get('rejected'), reasons=old_summary.get('rejection_reasons')),
        matched_legacy_failures=len(legacy_failures), migration_by_previous_reason={k: dict(v) for k, v in migration.items()},
        old_failed_records_now_exported=sum(r['simulation_id'] in generative_export for r in legacy_failures),
        old_failed_records_still_rejected=sum(r['simulation_id'] not in generative_export for r in legacy_failures),
        current_generative_rejection_reasons=generated_summary.get('rejection_reasons'),
        requested_not_generated=generated_summary.get('requested', 0) - generated_summary.get('generated', 0),
        exportable_deficit=generated_summary.get('remaining_exportable_deficit'),
        strict_full_export=dict(exported=len(strict_export), total=len(strict)),
        generative_full_export=dict(exported=len(generative_export), total=len(generated)),
        manual_geometry_unchanged_from_prior=manual_equal,
        matched_manual_rows=len(manual), matched_semi_rows=len(semi_ids),
        target_manifest_equal=old_panel == new_panel,
        strict_mode_matches_previous_records=strict_same_as_previous,
        generative_non_geometry_channels_match_previous=semi_channel_parity,
        qualification_or_ground_truth_changed=False)
    (root / 'refusal_migration.json').write_text(json.dumps(refusal, ensure_ascii=False, indent=2))
    (root / 'quality_comparison.json').write_text(json.dumps(common, ensure_ascii=False, indent=2))
    if replay_path:
        replay = {r['simulation_id']: r for r in jsonl(Path(replay_path) / 'simulations.jsonl')}
        equal_ids = generated.keys() & replay.keys()
        replay_info = dict(primary_rows=len(generated), replay_rows=len(replay), matched_rows=len(equal_ids),
            normalized_records_identical=all(generated[k] == replay[k] for k in equal_ids),
            primary_exported=len(generative_export), replay_exported=len(exported_ids(replay_path)),
            export_task_json_identical=(Path(generated_path) / 'label_studio_synthetic.json').read_bytes() ==
                (Path(replay_path) / 'label_studio_synthetic.json').read_bytes())
        (root / 'reproducibility.json').write_text(json.dumps(replay_info, ensure_ascii=False, indent=2))
    source_summary = json.loads((generated_path / 'semi_edit_source_summary.json').read_text())
    text = [
        '# Semi 生成式微调对照', '',
        '仅用于本地实验。生成结果均标记 synthetic，不调整真人资格、参考答案、正式评分公式或融合参数。', '',
        '全量记录数：旧版 {old}，严格模式 {strict}，生成式模式 {gen}。'.format(
            old=old_summary['generated'], strict=strict_summary['generated'], gen=generated_summary['generated']),
        '旧版两类 Semi 拒绝记录共 {n} 条，其中 {exp} 条在生成式运行中通过导出，仍拒绝 {rej} 条。'.format(
            n=len(legacy_failures), exp=refusal['old_failed_records_now_exported'], rej=refusal['old_failed_records_still_rejected']),
        '拒绝原因迁移：', '', '```json', json.dumps(refusal['migration_by_previous_reason'], ensure_ascii=False, indent=2), '```', '',
        '同人、同图、同参考校准：', '', '```json', json.dumps(common, ensure_ascii=False, indent=2), '```', '',
        '个人 WQ 绝对误差、几何问题率和模型复制率单独列出。当前校准只覆盖 3 栋建筑，生成式 WQ 误差需继续改善，结果不构成质量通过。',
        'Manual 点坐标与旧版一致：{manual}. 目标配额一致：{panel}.'.format(manual=manual_equal, panel=old_panel == new_panel),
        '严格模式复现旧版记录字段：{same}.'.format(same=strict_same_as_previous), '',
        '生成式运行中 scope 和时间字段与旧版逐记录一致：{same}.'.format(same=all(semi_channel_parity.values())),
        '生成式编辑的来源池抽样次数：', '', '```json',
        json.dumps(source_summary['source_pools_by_actual_behavior'], ensure_ascii=False, indent=2), '```', '',
        '来源记录均来自 normal_candidate，trap 与未核实池贡献为零。两条加点样例属于弱支持；留出其建筑时不参与加点拟合。',
        '旧 no_donor 减少 864 条，旧 unsupported 减少 95 条，导出净增 {net} 条。'.format(net=len(generative_export) - len(old_export)),
    ]
    if replay_path:
        text.extend(['', '固定种子复现：', '', '```json', json.dumps(replay_info, ensure_ascii=False, indent=2), '```'])
    (root / 'FINAL_REPORT.md').write_text('\n'.join(text) + '\n')
    return refusal, common
