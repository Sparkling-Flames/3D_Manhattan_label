"""精简接入外部画像/组合包；不重新评分、分类或运行融合。"""
import argparse
import gzip
import json
from pathlib import Path
import re
import shutil

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
KEY = ['worker_id', 'condition', 'origin', 'panel']


def read(path):
    with (gzip.open(path, 'rt', encoding='utf-8') if path.suffix == '.gz'
          else path.open(encoding='utf-8')) as stream:
        return json.load(stream)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def selected(path):
    name = path.as_posix()
    if path.parts[0] in ('claims', 'design', 'code', 'notes'):
        return True
    if path.parts[0] == 'figures':
        return path.suffix == '.png'
    if path.parts[0] == 'mechanisms':
        return path.parts[1] not in ('images', 'fonts') and path.name != 'MANIFEST.json'
    if path.parts[0] == 'provenance':
        return path.name not in ('quality_RUN_RECEIPT.json', 'speed_RUN_all.json')
    if name.startswith('tables/profiles/'):
        return path.name not in ('worker_exclusion_reasons.csv', 'quality_model_lobo_images.csv')
    if name.startswith('tables/quality/'):
        return path.name in {
            'composition_summary.csv', 'composition_effects.csv', 'pool_inventory.csv',
            'historical_selections.csv.gz', 'discovery_n7_candidate_screen.csv',
            'frozen_candidate_evaluation.csv', 'growth_common_plot_data.csv',
            'growth_same_core_matched_summary.csv', 'block_summary.csv', 'block_status_support.csv',
            'n7_difficulty_effects.csv', 'n7_member_consistency_summary.csv',
            'new_only_n7_labor_summary.csv', 'source_common_image_comparison.csv'}
    if name.startswith('tables/speed/'):
        return path.name in {'main_summary.csv', 'capacity.csv', 'matched_workers.csv',
                            'speed_n5_common_target_domains.csv', 'speed_n5_historical_difficulty_summary.csv'}
    return name in {'HOHONET_personnel_report_20261020.pdf', 'README.txt',
                    'personnel_cards.html', 'requirements.txt'}


def omitted_reason(path):
    if 'images' in path.parts:
        return '原图不重复入库；保留仓库和Release引用'
    if 'fonts' in path.parts:
        return '不复制重复字体；重绘时显式指定现有字体'
    if path.name == 'worker_exclusion_reasons.csv':
        return '逐字审核理由含自由文本；改用结构化处置/原因表，不复制发布'
    if path.name == 'MANIFEST.json':
        return '原包完整清单不冒充本精简包清单；选入/未选入见本地归档账本'
    return '重复矢量图、逐次运行明细或次级搜索/敏感性输出；保留生成代码和精确请求'


def common_pair(index, a, b, condition):
    q = index[index.quality_usable & index.Q_panel.eq(index.panel)
              & index.panel.eq('ordinary') & index.condition.eq(condition)]
    joined = q[q.worker_id.eq(a)].merge(q[q.worker_id.eq(b)],
        on=['task_key', 'condition', 'origin', 'panel'], suffixes=('_a', '_b'), validate='one_to_one')
    return dict(worker_a=a, worker_b=b, condition=condition, origin=joined.origin.iloc[0],
        panel='ordinary', images=joined.image_id_a.nunique(), buildings=joined.building_id_a.nunique(),
        Q_a=joined.B8L2_a.mean(), Q_b=joined.B8L2_b.mean(),
        Q10_a=joined.B8L2_a.quantile(.1), Q10_b=joined.B8L2_b.quantile(.1),
        peer_Q10_a=joined.B8L2_peer_recomputed_a.quantile(.1),
        peer_Q10_b=joined.B8L2_peer_recomputed_b.quantile(.1))


def build(source):
    archive = HERE / 'source'
    if source == archive.resolve():
        ledger = pd.read_csv(HERE/'CURATION.csv').to_dict('records')
    else:
        ledger = []
        for src in sorted(source.rglob('*')):
            if not src.is_file():
                continue
            rel = src.relative_to(source)
            keep = selected(rel)
            ledger.append(dict(path=rel.as_posix(), bytes=src.stat().st_size,
                               selected=keep, reason='原字节选入' if keep else omitted_reason(rel)))
            if keep:
                dst = archive / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
                assert dst.stat().st_size == src.stat().st_size
        pd.DataFrame(ledger).to_csv(HERE / 'CURATION.csv', index=False, encoding='utf-8-sig')
    tables = HERE / 'tables'
    tables.mkdir(exist_ok=True)
    profile = pd.read_csv(archive / 'tables/profiles/worker_profiles.csv')
    assert not profile.duplicated(KEY).any()
    assert profile.worker_id.str.fullmatch(r'W\d{3}').all()
    fields = KEY + ['n_inventory', 'n_images', 'n_buildings', 'n_quality', 'n_quality_images',
        'n_quality_buildings', 'n_quality_all_uses', 'n_special_quality', 'Q_mean', 'Q_q10',
        'Q_peer', 'Q_peer_q10', 'D10_mean', 'source_time_n', 'source_time_median',
        'n_time', 'n_time_buildings', 'relative_time', 'target_time_n', 'target_time_median',
        'time_source_kind', 'Q_supported', 'T_supported', 'hard_supported',
        'hard_n', 'hard_buildings', 'hard_Q_mean', 'hard_Q_peer', 'hard_minus_easy_peer',
        'n_cleaning_excluded', 'n_excluded_by_review', 'n_historical_not_accepted',
        'n_pending', 'n_pool_only_restricted', 'n_legacy_person_error', 'n_person_error_candidate',
        'n_quality_missing_in_pool', 'n_scope_response', 'n_scope_out', 'n_scope_judged',
        'n_scope_correct', 'confirmed_error_opportunities', 'confirmed_error_unchanged',
        'reported_error_opportunities', 'reported_error_unchanged',
        'semi_edited_error_outcome_unknown_n', 'semi_exact_initializations',
        'n_geometry', 'short_turn_peer', 'pair_peer']
    small = profile[fields]
    assert small.loc[small.n_quality.eq(0), ['Q_mean','Q_q10','Q_peer']].isna().all().all()
    exports = {'profiles':small,
        'profiles_manual':small[small.condition.eq('manual') & small.panel.eq('ordinary')],
        'profiles_semi':small[small.condition.eq('semi') & small.panel.eq('ordinary')],
        'profiles_doorway':small[small.panel.eq('doorway')]}
    history = pd.read_csv(archive / 'tables/profiles/lobo_features.csv')
    assert not history.duplicated(['target_building']+KEY).any()
    exports['history_lobo'] = history[['target_building']+KEY+[
        'n_quality', 'n_quality_images', 'n_quality_buildings', 'Q_mean', 'Q_q10', 'Q_peer',
        'n_time', 'n_time_images', 'n_time_buildings', 'relative_time', 'n_source_time',
        'n_target_time', 'time_source_kind', 'Q_supported_8images_3buildings',
        'T_supported_8images_3buildings', 'selection_history']]
    index = pd.read_csv(archive / 'tables/profiles/record_index.csv.gz')
    assert len(index) == 9217 and index.object_id.is_unique
    q = index[index.quality_usable]
    assert len(q) == 7302 and q.worker_id.nunique() == 60
    exclusions = ['cleaning_disposition', 'quality_use', 'quality_usable',
                  'source_pool_eligible', 'pool_analysis_eligible', 'image_quality_gate']
    exports['eligibility_counts'] = index.groupby(KEY+exclusions, dropna=False).agg(
        records=('object_id','size'), images=('image_id','nunique'), buildings=('building_id','nunique')).reset_index()
    reason_rows = []
    for row in index.itertuples():
        for reason in json.loads(row.quality_exclusion_reasons):
            reason_rows.append({**{k:getattr(row,k) for k in KEY},
                'reason_code':reason, 'cleaning_disposition':row.cleaning_disposition,
                'object_id':row.object_id, 'image_id':row.image_id, 'building_id':row.building_id})
    reasons = pd.DataFrame(reason_rows)
    exports['quality_unavailable_reason_counts'] = reasons.groupby(KEY+['reason_code','cleaning_disposition']).agg(
        records=('object_id','nunique'), images=('image_id','nunique'), buildings=('building_id','nunique')).reset_index()
    exports['selected_common_pairs'] = pd.DataFrame([
        common_pair(index,'W122','W126','manual'), common_pair(index,'W032','W034','manual'),
        common_pair(index,'W006','W011','semi')])
    quality = pd.read_csv(archive / 'tables/quality/composition_effects.csv')
    quality['condition'] = quality.layer.str.rsplit('_', n=1).str[-1]
    quality['panel'] = quality.layer.str.rsplit('_', n=1).str[0]
    exports['quality_n7'] = quality[quality.n.eq(7)&quality.phase.eq('all')]
    speed = pd.read_csv(archive / 'tables/speed/main_summary.csv')
    speed['panel'] = speed.layer.str.rsplit('_', n=1).str[0]
    exports['speed_n5'] = speed[speed.n.eq(5)&speed.contrast.eq('versus_slow')]
    assert len(exports['speed_n5']) == 80
    images = pd.read_csv(archive / 'mechanisms/original_image_manifest.csv')
    refs = images[['image_id','image_code','source_path','archive','release_url']].copy()
    refs['repo_image_available'] = refs.source_path.map(lambda p:(ROOT/p).is_file())
    exports['image_references'] = refs
    cases = []
    for path in sorted((archive/'mechanisms/cases').glob('*.json')):
        case = read(path)
        meta = case['meta']
        workers = {r['object_id']:r['worker_id'] for r in case['records']}
        for i, panel in enumerate(case['panels']):
            score = panel['score']
            cases.append(dict(case_id=case['case_id'], pool_id=case['pool_id'],
                team_key=panel['team_key'], image_id=meta['image_id'], image_code=meta['image'],
                condition=meta['condition'], panel='ordinary',
                reference_id=meta['reference_id'], reference_version=meta['reference_version'],
                label=panel['label'], member_object_ids=json.dumps(panel['object_ids']),
                member_workers=json.dumps([workers[o] for o in panel['object_ids']]),
                B8L2=score['B8L2'], D10=score['D10'],
                geometry_path=path.relative_to(HERE).as_posix(), geometry_pointer=f'/panels/{i}',
                geometry_status='saved_external_replay_not_rerun_here'))
    exports['case_teams'] = pd.DataFrame(cases)
    assert len(cases) == 12
    table_interfaces = []
    for name, frame in exports.items():
        frame.to_csv(tables/f'{name}.csv', index=False, encoding='utf-8-sig')
        table_interfaces.append(dict(id=name, path=f'tables/{name}.csv', rows=len(frame),
            status='prepared_not_dashboard_integrated', columns=frame.columns.tolist()))
    # 不把来源自由文本筛除理由或身份映射加入精简包；只扫描可发布副本。
    findings = []
    for path in archive.rglob('*'):
        if not path.is_file() or path.suffix in ('.png','.pdf'):
            continue
        text = gzip.open(path,'rt',encoding='utf-8').read() if path.suffix=='.gz' else path.read_text(encoding='utf-8')
        for label, pattern in [('private_path', r'C:[/\\]Users[/\\]|Downloads[/\\]|wxid_'),
            ('identity_field',r'"(?:source_account_id|email|real_name|phone|username)"\s*:')]:
            if re.search(pattern,text):
                findings.append(dict(path=path.relative_to(HERE).as_posix(),kind=label))
        if '@' in text and re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',text):
            findings.append(dict(path=path.relative_to(HERE).as_posix(),kind='email'))
    assert not findings, findings
    integration = dict(schema='personnel_profiles_composition_integration_v1',
        kind='profiles_and_composition_not_personnel_classification',
        classification_status='new_classification_not_delivered',
        source_bundle_name='HOHONET_personnel_research_20261020', source_archive='selected_subset_not_complete_original',
        profile_key=KEY, history_key=['target_building']+KEY,
        tables=table_interfaces, source_tables='source/tables',
        report='source/HOHONET_personnel_report_20261020.pdf', cards='source/personnel_cards.html',
        claim_teams='source/claims/claim_teams.json.gz',
        requests=['source/design/quality/requests.json.gz','source/design/speed/requests.json.gz'],
        main_pairs=['source/claims/quality_primary_comparisons.csv.gz','source/claims/speed_n5_comparisons.csv.gz'],
        cases=[p.relative_to(HERE).as_posix() for p in sorted((archive/'mechanisms/cases').glob('*.json'))],
        figures=[p.relative_to(HERE).as_posix() for p in sorted((archive/'figures').glob('*.png'))],
        dashboard_status='prepared_not_integrated', verification='CHECKS.json', field_contract='FIELD_CONTRACT.md')
    write_json(HERE/'INTEGRATION.json',integration)
    write_json(HERE/'CHECKS.json',dict(
        archived_files=sum(x['selected'] for x in ledger), omitted_files=sum(not x['selected'] for x in ledger),
        archived_bytes=sum(x['bytes'] for x in ledger if x['selected']), copied_size_check=True,
        profile_rows=len(profile), unique_profile_key=True, unique_lobo_key=True,
        inventory_records=len(index), inventory_ids=index.worker_id.nunique(),
        ordinary_manual_ids=len(exports['profiles_manual']), ordinary_semi_ids=len(exports['profiles_semi']),
        quality_records=len(q), quality_workers=q.worker_id.nunique(),
        privacy_text_scan_findings=findings, raw_review_text_copied=False, identity_map_copied=False,
        case_teams=len(cases), fusion_rerun_here=False, original_source_modified=False,
        checks='join_keys_denominators_saved_case_paths_structured_reason_counts',
        inherited_checks='coordinator_verified_4_cases_12_teams_80_speed_rows_3_HL_effects_relative_Q',
        not_repeated='88048_team_fusion_and_coordinator_checks', global_indexes='coordinator_owned'))
    print('prepared',len(profile),'profiles,',len(cases),'case teams;',len(table_interfaces),'interface tables')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=HERE/'source')
    build(parser.parse_args().source.resolve())
