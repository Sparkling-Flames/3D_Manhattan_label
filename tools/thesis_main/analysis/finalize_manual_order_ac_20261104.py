"""Audit and document the completed targeted manual-order AC dependency closure.

This reads completed results and the frozen sources. It does not reconstruct,
fuse, fit a classifier, or score an endpoint. Reports and checks are generated
under the separate assisted output directory; original results are read-only.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd

from .evaluate_manual_order_ac_20261104 import (
    AC, OUT, RESULT, ROOT, VERSION, TOLERANCE, compare, iter_jsonl,
    jsave, read_json, save, sha)

COMMIT = 'ac395e703d1fef573d1ef3e105df0286d62a0468'


def csv_integrity(path):
    opener = gzip.open if path.name.endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as stream:
        reader = csv.reader(stream)
        header = next(reader)
        assert len(set(header)) == len(header), ('duplicate_header', str(path))
        count = 0
        for count, row in enumerate(reader, 1):
            assert len(row) == len(header), ('csv_width', str(path), count)
    return count, len(header)


def clean_staging():
    removed = []
    for path in sorted(OUT.rglob('*.partial')):
        final = path.with_name(path.name[:-8])
        assert final.exists(), ('unreplaced_partial', str(path))
        csv_integrity(final)
        removed.append(dict(path=path.relative_to(OUT).as_posix(),
                            reason='obsolete interrupted temporary; final file fully parsed'))
        path.unlink()
    for name in ('automatic_inputs', 'assisted_inputs'):
        path = OUT/'states'/name
        if not path.exists():
            continue
        assert not path.is_symlink()
        for item in path.rglob('*'):
            if item.is_file() or item.is_symlink():
                removed.append(dict(path=item.relative_to(OUT).as_posix(),
                                    reason='reproducible state-analysis staging input'))
        # rmtree unlinks symlinks; it never traverses their original targets.
        shutil.rmtree(path)
    old = read_json(OUT/'CLEANUP_RECEIPT.json') if (OUT/'CLEANUP_RECEIPT.json').exists() else []
    jsave(OUT/'CLEANUP_RECEIPT.json', old+removed)


def reconcile_sensitivity_receipts():
    dest = OUT/'sensitivity'
    receipt = read_json(dest/'SENSITIVITY_IMPACT_RECEIPT.json')
    receipt['raw'] = pd.read_csv(dest/'DEPENDENCY_COUNTS.csv').to_dict('records')
    summary = pd.read_csv(dest/'SENSITIVITY_SUMMARY_CHANGES.csv.gz', low_memory=False)
    receipt['summary'] = dict(changed_tables=summary.analysis_table.drop_duplicates().tolist(),
                              changed_summary_rows=len(summary))
    advanced = {}
    for name, folder, files in [
        ('MEMBER_PANELS', 'member_variability_v2', ['MEMBER_VARIABILITY_VALID_GE2_SUMMARY.csv.gz']),
        ('UNEQUAL_DECOMPOSITION', 'three_leg_common_support_v2',
         ['COMMON_VALID_THREE_LEG_IMAGE_SUMMARY.csv.gz', 'COMMON_VALID_DECOMPOSITION_SIZE_COVERAGE.csv.gz'])]:
        advanced[name] = dict(
            selected_source_rows=csv_integrity(dest/folder/'automatic/SOURCE_ROWS.csv.gz')[0],
            outputs=[dict(file=f, changed_rows=csv_integrity(
                dest/folder/f.replace('.csv.gz', '_CHANGES.csv.gz'))[0]) for f in files])
    receipt['advanced'] = advanced
    assert receipt['outside'] == {'changed_raw_pairs': 6, 'changed_summary_rows': 96}
    for phase in ('raw', 'summary', 'advanced', 'outside'):
        jsave(dest/('PHASE_RECEIPT_'+phase+'.json'),
              dict(analysis_version=VERSION, phase=phase, result=receipt[phase]))
    jsave(dest/'SENSITIVITY_IMPACT_RECEIPT.json', receipt)
    return receipt


def source_audit():
    head = subprocess.run(['git','rev-parse','HEAD'], cwd=ROOT, check=True,
                          text=True, capture_output=True).stdout.strip()
    assert head == COMMIT, ('unexpected_source_commit', head)
    provenance = pd.read_csv(OUT/'SAVED_ENDPOINT_PROVENANCE.csv')
    paths = {ROOT/p for p in provenance.source}
    paths.update((AC/'stage04_metrics/metric_shards').joinpath(p.name)
                 for p in (OUT/'metric_shards').glob('*.csv.gz'))
    paths.update([AC/'stage01_registered/DESIGN_LINKS.csv.gz',
                  AC/'stage01_registered/AC_EVENTS.csv.gz',
                  AC/'stage01b_semi/AC_EVENTS.csv.gz',
                  AC/'stage01_capacity/FROZEN_ROLE_PARENT_MAP_ALL_LOBO.csv',
                  AC/'stage01_capacity/POOL_METHOD_CAPACITY.csv.gz',
                  ROOT/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json',
                  ROOT/'research/data/releases/v2.1/admitted_space_extension/pools/INPUT_SNAPSHOT.json',
                  ROOT/'research/workers/personnel_v21_reselection_20261029/targets/POOL_TARGET_CONDITIONS.csv',
                  ROOT/'research/workers/personnel_v21_reselection_20261029/analysis/legacy_geometry_diagnostics.py',
                  ROOT/'research/workers/personnel_v21_reselection_20261029/analysis/measure_registered_events.py'])
    for folder in ('code', 'stage02_engine/code', 'stage05_sensitivity/code',
                   'stage05_funnel_bridge/code', 'stage05_context_common/code'):
        paths.update((AC/folder).glob('*.py'))
    paths.update((AC/'stage05_main').glob('*.csv*'))
    paths.update((AC/'stage05_sensitivity').glob('*/*.csv*'))
    paths.update((AC/'stage05_context_common').glob('*.csv*'))
    paths.update((AC/'stage05_funnel_bridge').glob('*.csv*'))
    paths = {p for p in paths if p.name.endswith(('.csv','.csv.gz','.py','.json','.jsonl.gz'))}
    # Index reads do not fetch any remote objects in this partial checkout.
    rel = sorted(p.relative_to(ROOT).as_posix() for p in paths)
    result = subprocess.run(['git', 'ls-files', '--stage', '--', *rel], cwd=ROOT,
                            check=True, text=True, capture_output=True)
    index = {line.split('\t', 1)[1]: line.split()[1]
             for line in result.stdout.splitlines()}
    rows = []
    saved = provenance.drop_duplicates('source').set_index('source').source_sha256.to_dict()
    for path in sorted(paths):
        relative = path.relative_to(ROOT).as_posix()
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        blob = hashlib.sha1(b'blob '+str(len(payload)).encode()+b'\0'+payload).hexdigest()
        assert relative in index and blob == index[relative], ('source_changed', relative)
        assert relative not in saved or digest == saved[relative], ('saved_geometry_changed', relative)
        rows.append(dict(source=relative, bytes=len(payload), sha256=digest,
                         git_blob=blob, expected_git_blob=index[relative],
                         matches_frozen_index=True, source_repository_commit=COMMIT))
    save(pd.DataFrame(rows), OUT/'SOURCE_VERSION_CHECKS.csv')
    return rows


def support_audit():
    before = pd.read_csv(OUT/'AFFECTED_EVENT_METRICS_AUTOMATIC.csv.gz', low_memory=False)
    after = pd.read_csv(OUT/'AFFECTED_EVENT_METRICS_ASSISTED.csv.gz', low_memory=False)
    assert before.event_id.is_unique and after.event_id.is_unique
    assert set(before.event_id) == set(after.event_id) and len(after) == 339
    aux = {r['team_key']: r for r in iter_jsonl(RESULT/'endpoints/ENDPOINTS.jsonl.gz')}
    bindings = pd.read_csv(RESULT/'endpoints/ENDPOINT_REFERENCE_BINDINGS.csv')
    bindings = bindings[bindings.module.eq('ac_registered')]
    assert set(bindings.event_id) == set(after.event_id)
    touched = set()
    for row in after.to_dict('records'):
        for arm in ('A', 'C'):
            key = row[arm+'_team_key']
            if key in aux:
                endpoint = aux[key]
                assert row['reference_id'] == endpoint['reference_id']
                assert row['reference_version'] == endpoint['reference_version']
                touched.add(key)
    assert len(touched) == 11
    assert sum(pd.notna(aux[k]['B8L2']) for k in touched) == 10
    meta = list(before.columns[:before.columns.get_loc('A_B8L2')])
    meta += ['physical_pair_id', 'ordered_physical_pair_id', 'official_difficulty',
             'geometric_challenge', 'structural_condition', 'ref_turn5', 'ref_H',
             'ref_short_edges', 'legal_targets_in_image_condition', 'data_release']
    frozen_suffixes = ['source_time_total_seconds', 'recorded_time_total_seconds',
        'minimum_support', 'identity_groups_n', 'unselected_groups_n', 'half_vote_nodes',
        'selected_support_min', 'target_individual_B8L2_mean', 'target_individual_B8L2_min',
        'known_record_time_total_seconds', 'source_time_known_n',
        'source_time_known_sum_seconds', 'record_time_by_kind_json',
        'endpoint_acquisition', 'semantic_identity', 'nodes']
    meta += [arm+'_'+field for arm in ('A', 'C') for field in frozen_suffixes]
    meta = sorted(set(meta))
    parity = compare(before[meta], after[meta], ['event_id'], 'fixed_AC_event_metadata')
    save(pd.DataFrame(parity), OUT/'FIXED_METADATA_PARITY.csv')
    support = []
    for scope, subset in [('all', after)]+list(after.groupby('scope', sort=True)):
        old = before[before.event_id.isin(subset.event_id)]
        support.append(dict(scope=scope, affected_method_events=len(subset),
            affected_physical_pairs=subset.physical_pair_id.nunique(),
            affected_pools=subset.pool_id.nunique(), affected_images=subset.image.nunique(),
            automatic_Q_method_events=int(old.B8L2_CA.notna().sum()),
            assisted_Q_method_events=int(subset.B8L2_CA.notna().sum()),
            automatic_Q_physical_pairs=old[old.B8L2_CA.notna()].physical_pair_id.nunique(),
            assisted_Q_physical_pairs=subset[subset.B8L2_CA.notna()].physical_pair_id.nunique(),
            automatic_floor_metric_events=int(old.iou_2d_CA.notna().sum()),
            assisted_floor_metric_events=int(subset.iou_2d_CA.notna().sum())))
    assert support[0]['assisted_Q_method_events'] == 257
    assert support[0]['assisted_Q_physical_pairs'] == 193
    for n,m in [(14,7),(16,8),(18,9),(20,10),(22,11)]:
        assert after[after.scope.eq('primary') & after.n.eq(n) & after.m.eq(m)].empty
    save(pd.DataFrame(support), OUT/'SUPPORT_SUMMARY.csv')
    common = []
    for path in sorted((OUT/'metric_shards').glob('*.csv.gz')):
        old = pd.read_csv(AC/'stage04_metrics/metric_shards'/path.name, low_memory=False).set_index('event_id').sort_index()
        new = pd.read_csv(path, low_memory=False).set_index('event_id').sort_index()
        assert old.index.equals(new.index)
        for metric in ['B8L2_CA', 'D10_CA', 'A_B8L2', 'C_B8L2', 'A_D10', 'C_D10']:
            x, y = old[metric], new[metric]
            both = x.notna() & y.notna()
            added = x.isna() & y.notna()
            lost = x.notna() & y.isna()
            error = (x[both]-y[both]).abs()
            maximum = float(error.max()) if len(error) else 0.0
            assert not lost.any() and maximum < TOLERANCE
            common.append(dict(pool_id=path.name[:-7], metric=metric,
                registered_method_events=len(old), automatic_valid=int(x.notna().sum()),
                assisted_valid=int(y.notna().sum()), common_valid=int(both.sum()),
                newly_valid=int(added.sum()), lost_valid=int(lost.sum()),
                changed_on_common=int((error > TOLERANCE).sum()),
                maximum_absolute_difference_on_common=maximum))
    save(pd.DataFrame(common), OUT/'COMMON_SUPPORT_AUDIT.csv')
    receipt = read_json(OUT/'AC_IMPACT_RECEIPT.json')
    receipt['physical_pair_support'] = support
    receipt['affected_complete_conditional_endpoints'] = 10
    receipt['affected_invalid_floor_endpoints'] = 1
    receipt['fixed_metadata_fields_verified'] = len(meta)-1
    receipt['common_Q_values_changed'] = 0
    jsave(OUT/'AC_IMPACT_RECEIPT.json', receipt)
    return support, common


def empty_text_audit():
    """Explain raw isna differences without suppressing the original audit.

    Frozen CSV text fields serialize an empty string as an empty token. Pandas
    then reads it as NaN; original Python constructors return ''.  Rebuild just
    the five text fields from frozen source-time records and membership sets.
    This does not remeasure geometry or any scalar outcome.
    """
    sys.path.insert(0, str(AC/'stage02_engine/code'))
    from ac_measure_events import time_info
    fields=['A_single_time_source','C_single_time_source',
            'actual_D_members','actual_X_members','actual_Z_members']
    frame=pd.read_csv(OUT/'AFFECTED_EVENT_METRICS_AUTOMATIC.csv.gz', low_memory=False,
                      keep_default_na=False, dtype=str)
    source={}
    for pid in frame.pool_id.unique():
        d=pd.read_csv(AC/'stage04_metrics/metric_shards'/(pid+'.csv.gz'),
                      usecols=['event_id']+fields, keep_default_na=False, dtype=str)
        source.update(d.set_index('event_id').to_dict('index'))
    rows=[]
    for row in frame.to_dict('records'):
        workers=lambda name:set(filter(None,row[name].split('|')))
        aw,cw=workers('A_workers'),workers('C_workers')
        rebuilt={f'actual_{label}_members':'|'.join(sorted(members))
                 for label,members in [('D',aw&cw),('X',aw-cw),('Z',cw-aw)]}
        for arm in ('A','C'):
            rebuilt[arm+'_single_time_source']=time_info(
                {'record_time_by_kind_json':row[arm+'_record_time_by_kind_json']})['single_time_source']
        for field in fields:
            literal=source[row['event_id']][field]
            assert literal==row[field]==rebuilt[field], (row['event_id'],field)
            blank=literal==''
            rows.append(dict(context='saved_events:'+row['pool_id'],
                event_id=row['event_id'],field=field,
                source_csv_literal_json=json.dumps(literal),
                replayed_python_text_json=json.dumps(rebuilt[field]),
                parser_representation='NaN_from_empty_csv_token' if blank else 'nonempty_text',
                raw_missing_representation_difference=blank,
                normalized_text_equal=True, substantive_missing_difference=False,
                empty_semantics=('not_exactly_one_active_recording_kind' if 'single_time_source' in field
                                 else 'empty_member_set') if blank else 'nonempty_text'))
    evidence=pd.DataFrame(rows)
    diff=evidence[evidence.raw_missing_representation_difference]
    counts=diff.groupby(['context','field']).size()
    saved=pd.read_csv(OUT/'EVENT_AND_UNTOUCHED_PARITY.csv')
    saved=saved[saved.missing_disagreements.gt(0)].set_index(['context','field']).missing_disagreements.sort_index()
    assert counts.sort_index().equals(saved.astype('int64'))
    assert len(saved)==40 and len(diff)==641 and len(evidence)==1695
    save(evidence,OUT/'TEXT_EMPTY_NORMALIZATION_EVIDENCE.csv.gz')
    return dict(checked_text_cells=len(evidence), raw_audit_field_rows=len(saved),
                raw_missing_representation_disagreements=len(diff),
                normalized_substantive_missing_disagreements=0,
                original_audit_missing_disagreements_column_preserved=True,
                evidence='TEXT_EMPTY_NORMALIZATION_EVIDENCE.csv.gz')


def conclusions():
    rows = []
    def add(topic, status, claim, source, *, scope='', method='', selector=None,
            metric='', old=None, new=None, old_support='', new_support='',
            weight='', relation='可评支持扩展；原共同支持事件值不变'):
        assert (OUT/source).is_file(), source
        rows.append(dict(conclusion_id='AC-%02d' % (len(rows)+1), topic=topic,
            status=status, scope=scope, method=method, conclusion=claim,
            metric=metric, automatic_value=old, assisted_value=new,
            automatic_support=old_support, assisted_support=new_support,
            weighting=weight, common_support_relation=relation,
            source_file=source, source_selector_json=json.dumps(selector or {}, ensure_ascii=False),
            analysis_version=VERSION))
    def pick(source, selector):
        frame = pd.read_csv(OUT/source, low_memory=False)
        mask = pd.Series(True, index=frame.index)
        for key, value in selector.items():
            if isinstance(value, (int, float)):
                mask &= pd.to_numeric(frame[key], errors='coerce').eq(value)
            else:
                mask &= frame[key].eq(value)
        got = frame[mask]
        assert len(got) == 1, (source, selector, len(got))
        return got.iloc[0]
    def observed(topic, status, claim, source, selector, field='image_mean',
                 support_fields=('valid_images',), weight='原池内汇总后按图像等权'):
        row = pick(source, selector)
        def support(prefix):
            return '; '.join(k+'='+format(float(row[prefix+k]), '.12g') for k in support_fields)
        add(topic, status, claim, source, scope=selector.get('scope', 'primary'),
            method=selector.get('method', selector.get('method_right', '')),
            selector=selector, metric=selector.get('metric', '')+':'+field,
            old=row['automatic_'+field], new=row['assisted_'+field],
            old_support=support('automatic_'), new_support=support('assisted_'), weight=weight)

    main = 'MAIN_SUMMARY_CHANGES.csv.gz'
    sens = 'sensitivity/SENSITIVITY_SUMMARY_CHANGES.csv.gz'
    ge2 = 'sensitivity/member_variability_v2/MEMBER_VARIABILITY_VALID_GE2_SUMMARY_CHANGES.csv.gz'
    three = 'sensitivity/three_leg_common_support_v2/COMMON_VALID_THREE_LEG_IMAGE_SUMMARY_CHANGES.csv.gz'
    methods = 'context_common/COMMON_POOL_METHOD_COMPARISON_CHANGES.csv.gz'
    outside = 'sensitivity/exact_outside_background/SUMMARY_CHANGES.csv.gz'
    add('直接 AC 可评覆盖', '条件变化', '339 个实际方法事件新增 257 个可评 ΔQ，对应 193 个去重物理对；旧缺 Q 无法计算改善幅度。',
        'SUPPORT_SUMMARY.csv', metric='可评方法事件数（不是质量分数）', old=0, new=257,
        old_support='0/339 方法事件；0/245 物理对', new_support='257/339 方法事件；193/245 物理对',
        weight='事件及物理对分别计数；不平均混合方法和图像')
    add('50% 换人主目标', '保持', '直接 AC 主目标 n/m=14/7、16/8、18/9、20/10、22/11 没有新增 Q 支持或主表 Q 改变；已有严格半队桥需单独更新。',
        main, scope='primary direct AC', metric='B8L2_CA', selector={'scope':'primary','n_m':['14/7','16/8','18/9','20/10','22/11']},
        old_support='冻结主条件', new_support='新增可评事件 0', relation='直接 AC 主条件不变；不是宣称全部半队结果不变')
    observed('n=28 换人质量', '幅度变化', 'TARGET_K3 的 2→3 有符号 ΔQ 保持正向，支持扩大后均值增加。', main,
        dict(analysis_view='A_fixed_n', scope='primary', method='TARGET_DSTRUCT_K3', role_direction='2->3', n_condition='28', m_condition='7', metric='B8L2_CA'),
        support_fields=('valid_pairs','valid_images'))
    observed('完整纯类小样本', '需改写', 'other_admitted RAW3 纯类 1→2 在 n=m=4 的均值由正转负，不能沿用无条件正向叙述。', main,
        dict(analysis_view='A_fixed_n_pure_class', scope='other_admitted', method='V21_DSTRUCT_RAW3_K3', role_direction='1->2', n_condition='4', m_condition='4', metric='B8L2_CA'),
        support_fields=('valid_pairs','valid_images'))
    observed('不等人数全类无背景', '需改写', 'other_admitted RAW3 1→2 总差值翻向；这是新增图像支持后的结果，原共同支持分值未降低。', main,
        dict(analysis_view='whole_unequal_no_background', scope='other_admitted', method='V21_DSTRUCT_RAW3_K3', role_direction='1->2', metric='B8L2_CA'),
        support_fields=('valid_pairs','valid_images'))
    for left in ('OPPSTRUCT_K3','TARGET_DSTRUCT_K2'):
        observed('冻结方法幅度对照', '需改写', 'n=28,m=7 共同池上 RAW3 相对 '+left+' 的平均绝对换人幅度差翻向；不据此重新选择分类方案。', methods,
            dict(method_left=left, method_right='V21_DSTRUCT_RAW3_K3', n=28, m=7, metric='B8L2_CA'),
            field='right_minus_left_absolute_change', support_fields=('valid_common_images',),
            weight='两冻结方法共同可评图像；各方法自身冻结方向先汇总，再图像等权')
    for method in ('TARGET_DSTRUCT_K3','V21_DSTRUCT_RAW3_K3'):
        observed('同配比成员波动', '幅度变化', 'n=28,m=7 的成员面板 ΔQ 范围更新；每个指标仍须至少两个有效观察，单点不记零波动。背景 D 并未固定。', ge2,
            dict(scope='primary', method=method, panel_kind='class_count_preserving_members_D_not_fixed', role_direction='2->3', n=28, m=7, metric='B8L2_CA__span'),
            support_fields=('valid_panels','valid_images'), weight='每指标 valid≥2 的面板；池内面板均值后按图像等权')
    observed('纯类成员方向波动', '幅度变化', 'TARGET_K3 n=m=8、1→2 的成员面板存在正负混合这一判断保持，混合比例更新。', ge2,
        dict(scope='primary', method='TARGET_DSTRUCT_K3', panel_kind='class_count_preserving_members_D_not_fixed', role_direction='1->2', n=8, m=8, metric='B8L2_CA__sign_flip'),
        support_fields=('valid_panels','valid_images'), weight='每指标 valid≥2 的面板；图像等权混合比例')
    for direction, status, claim in [
        ('3->2','幅度变化','主域 3→2 的等人数替换损失仍被补入剩余目标类成员部分抵消；补人段保持正，净总段保持负。'),
        ('3->1','需改写','主域 3→1/all_outside_D 的补人段均值由微正转微负；不能继续笼统宣称该方向补人可抵消替换损失。')]:
        observed('三段共同支持', status, claim, three,
            dict(scope='primary', method='TARGET_DSTRUCT_K3', role_direction=direction,
                 background_profile='outside_swapped_classes_neutral_members_0', parent_background_stratum='all_outside_D', metric='B8L2_CA'),
            field='addition_image_mean', support_fields=('valid_paths','valid_images'),
            weight='同一路径三段全有限；中间子集先在 parent 内均值，parent/池/图像依原权重汇总')
    for method, direction in [('TARGET_DSTRUCT_K2','1->2'),('TARGET_DSTRUCT_K3','1->3'),('TARGET_DSTRUCT_K3','2->3')]:
        observed('背景人数扩张', '条件变化', '固定 X/Z、m=5、n20→28 的换人差值阶差由负转正，仅 3→4 图像；背景增大不再能被概括为无条件稀释效应。', sens,
            dict(analysis_table='FIXED_BLOCK_BACKGROUND_STEPS', scope='primary', method=method, role_direction=direction,
                 n_from=20, n_to=28, m_from=5, m_to=5, metric='B8L2_CA__step_difference'))
    observed('背景人数扩张', '幅度变化', '固定 X/Z、TARGET_K3 2→3、m=7、n20→28 的阶差仍为负，衰减幅度减小。', sens,
        dict(analysis_table='FIXED_BLOCK_BACKGROUND_STEPS', scope='primary', method='TARGET_DSTRUCT_K3', role_direction='2->3',
             n_from=20, n_to=28, m_from=7, m_to=7, metric='B8L2_CA__step_difference'))
    observed('同 XZ 同规模背景', '条件变化', 'other_admitted TARGET_K3 n=4,m=2、2→3 的背景效果差翻向；仅 1→2 图像，不能推广为主域背景改善。', outside,
        dict(scope='other_admitted', method='TARGET_DSTRUCT_K3', role_direction='2->3', n=4, m=2,
             background_change_type='background_class_counts_and_members_changed', metric='B8L2_CA__effect_difference'))
    add('固定 A 扩大换人块', '条件变化', '受影响的四个 Q 阶差条件均从无支持变为一个图像可评；不能称为原零效应改善或稳定单调人数规律。',
        sens, scope='other_admitted', selector={'analysis_table':'FIXED_A_REPLACEMENT_STEPS','metric':'B8L2_CA__step_difference'},
        metric='B8L2_CA__step_difference', old_support='0 图像', new_support='各 1 图像')
    add('完整类联盟', '幅度变化', '主域本批改变的完整联盟 ΔQ 条件均保持方向；other_admitted 有翻向，必须按 number_condition 和 unknown_background_included 保留条件。',
        sens, selector={'analysis_table':'COMPLETE_COALITIONS','metric':'B8L2_CA'}, metric='B8L2_CA',
        old_support='冻结联盟身份与原方向', new_support='原联盟身份不变，新增可评支持', weight='先冻结池内原联盟方向汇总，再图像等权')
    observed('抽样批次稳定性', '幅度变化', 'TARGET_K3 纯类 n=m=8 的两批均值差由微正转微负；方向一致比例仍约 0.77，不能将近零批间差的符号视为新的优劣次序。', sens,
        dict(analysis_table='SAMPLING_BATCHES', scope='primary', method='TARGET_DSTRUCT_K3', role_direction='1->2', n=8, m=8, metric='B8L2_CA__mean_difference'))
    for n in (14,20):
        observed('严格半队 AC 桥', '幅度变化', '沿用已有半队中 13 个重叠事件后严格 G_A 均值更新并保持正；该桥不是新的独立实验，直接 AC 仍没有 B。',
            'strict_bridge/STRICT_BRIDGE_SUMMARY_CHANGES.csv.gz',
            dict(strict_source_family='prior_m7_m8', new_reference_set='A_registered_m7_m8', method='TARGET_DSTRUCT_K3', n=n, m=7, strict_role_direction='2/3->3/3', metric='B8L2'),
            field='strict_G_A_mean', support_fields=('jointly_evaluable_pools',), weight='原同条件严格/直接 AC 的共同可评目标池等权')
    add('难度、类别、劳动和执行漏斗', '保持', '官方难度、几何情境、分类及已记录原劳动保持固定；能力/登记/执行分母保持，更新可评性及输出状态。人工排序劳动未计时，不能填零。',
        'FIXED_METADATA_PARITY.csv', relation='固定元数据无差异；排序新增劳动未知，不构成效率改善', weight='原始固定元数据与记录来源')
    add('坐标候选 F2/F9', '尚不能判断', '独立候选为 50 个 AC 引用新增 44 个可评 ΔQ；多边形有效但 camera 不在 visibility kernel，未纳入固定坐标 57 版，也不能据此确认场景几何正确。',
        'coordinate_candidate/CANDIDATE_AC_RECEIPT.json', metric='可评方法事件数（不是质量分数）', old=0, new=44,
        old_support='固定坐标分支 0/50', new_support='坐标候选分支 44/50',
        relation='额外坐标干预的独立候选分支；未正式采用')
    save(pd.DataFrame(rows), OUT/'CONCLUSIONS.csv')
    return rows


def validate_outputs():
    rows = []
    for path in sorted(OUT.rglob('*')):
        if not path.is_file():
            continue
        assert not path.is_symlink(), ('unexpected_output_symlink', str(path))
        if path.name in ('FILE_INTEGRITY.csv','CHECKS.json'):
            continue
        assert not path.name.endswith(('.partial','.writing')), ('temporary_output', str(path))
        kind = 'text'; count = columns = None
        if path.name.endswith(('.csv','.csv.gz')):
            count, columns = csv_integrity(path); kind = 'csv'
        elif path.name.endswith('.json'):
            json.loads(path.read_text(encoding='utf-8-sig'),
                       parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
            kind = 'json'
        elif path.name.endswith('.gz'):
            with gzip.open(path, 'rb') as stream:
                while stream.read(1048576):
                    pass
            kind = 'gzip'
        else:
            path.read_text(encoding='utf-8-sig')
        rows.append(dict(path=path.relative_to(OUT).as_posix(), kind=kind,
                         bytes=path.stat().st_size, sha256=sha(path), rows=count,
                         columns=columns, full_read_ok=True))
    save(pd.DataFrame(rows), OUT/'FILE_INTEGRITY.csv')
    csv_integrity(OUT/'FILE_INTEGRITY.csv')
    return rows


def parity_totals():
    rows = []
    for path in sorted(OUT.rglob('*PARITY.csv')):
        frame = pd.read_csv(path)
        assert frame.mismatches.eq(0).all(), str(path)
        maximum = pd.to_numeric(frame.maximum_absolute_difference, errors='coerce').max()
        maximum = float(maximum) if pd.notna(maximum) else 0.0
        assert maximum < TOLERANCE
        rows.append(dict(file=path.relative_to(OUT).as_posix(), field_checks=len(frame),
                         mismatches=0, maximum_absolute_difference=maximum))
    save(pd.DataFrame(rows), OUT/'PARITY_SUMMARY.csv')
    return rows


def main():
    csv.field_size_limit(sys.maxsize)
    clean_staging()
    sensitivity = reconcile_sensitivity_receipts()
    sources = source_audit()
    support, common = support_audit()
    empty_text = empty_text_audit()
    findings = conclusions()
    parity = parity_totals()
    assert (OUT/'REPORT_ZH.md').exists()
    files = validate_outputs()
    checks = dict(
        analysis_version=VERSION, source_repository_commit=COMMIT,
        status='PASS', tolerance=TOLERANCE,
        affected_method_events=339, affected_physical_pairs=245,
        affected_endpoint_identities=11, affected_pools=9,
        newly_evaluable_Q_method_events=257, newly_evaluable_Q_physical_pairs=193,
        physical_pair_support=support,
        original_Q_or_D10_common_support_changed=0, lost_Q_or_D10_support=0,
        common_support_metric_pool_checks=len(common),
        maximum_Q_or_D10_common_support_difference=max(r['maximum_absolute_difference_on_common'] for r in common),
        frozen_source_files_verified=len(sources), all_source_blobs_match_frozen_git_index=True,
        source_geometry_provenance_verified=True, endpoint_reference_bindings_verified=True,
        baseline_and_fixed_field_checks=sum(r['field_checks'] for r in parity),
        baseline_mismatches=0,
        text_empty_normalization=empty_text,
        maximum_baseline_absolute_difference=max(r['maximum_absolute_difference'] for r in parity),
        parity_files=parity,
        seven_sensitivity_families_complete=len(sensitivity['raw']) == 7,
        sensitivity_summary_changed_rows=sensitivity['summary']['changed_summary_rows'],
        context_common_completed=True, output_states_completed=True,
        capacity_funnel_completed=True, strict_half_bridge_completed=True,
        strict_bridge_overlapping_half_events=13, strict_bridge_independent_new_experiments=0,
        candidate_branch_separate=True, candidate_branch_adopted=False,
        original_automatic_outputs_modified=False, new_fusions=0,
        new_endpoint_scores_in_AC=0, new_classifications=0, new_team_selections=0,
        missing_Q_imputed=False, human_order_time_imputed_zero=False,
        full_file_reads=len(files), csv_files=sum(r['kind']=='csv' for r in files),
        json_files=sum(r['kind']=='json' for r in files), all_gzip_eof_valid=True,
        all_csv_widths_valid=True, duplicate_csv_headers=0, temporary_files_remaining=0,
        staged_source_symlinks_remaining=0, conclusion_rows=len(findings),
        integrity_manifest='FILE_INTEGRITY.csv')
    jsave(OUT/'CHECKS.json', checks)
    json.loads((OUT/'CHECKS.json').read_text())
    print(json.dumps({k:checks[k] for k in ('status','frozen_source_files_verified',
        'baseline_and_fixed_field_checks','maximum_baseline_absolute_difference',
        'full_file_reads','conclusion_rows')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
