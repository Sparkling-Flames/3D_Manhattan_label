"""数据v1统计消费修订；保存旧r1，逐键接入已发布的来源，不重算融合。"""
import argparse
import csv
import hashlib
import io
import json
import zipfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT/'research/statistics/v1_integrated_analysis_20261017'
OUT = ROOT/'research/statistics/v1_integrated_analysis_20261017_r2'
REVISION = 'v1_integrated_analysis_20261017_r2'
EXPLORER = ROOT/'research/statistics/research_explorer_v1_r2_20261017'
KEY = ['pool_id', 'path_id', 'k']
AUXILIARY = ['floor_WQ_upper_bound', 'iou_3d_corner_mean', 'height_mean_ratio',
    'floor_WQ', 'boundary_loss', 'direction_loss', 'global_height_loss',
    'local_height_loss', 'height_loss', 'height_drop_WQ', 'height_drop_current',
    'WQ_no_D', 'WQ_no_B', 'WQ_no_H', 'iou2d100']


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def equal_values(left, right):
    if pd.api.types.is_numeric_dtype(left) and pd.api.types.is_numeric_dtype(right):
        return pd.Series(np.isclose(left, right, rtol=1e-12, atol=1e-12, equal_nan=True), index=left.index)
    return left.eq(right) | (left.isna() & right.isna())


def reconcile_states(old, current, *, require_restored=True):
    """旧状态必须完整保留；浮点CSV往返噪声不视为几何变化。"""
    assert not old.duplicated(KEY).any() and not current.duplicated(KEY).any()
    a, b = old.set_index(KEY), current.set_index(KEY)
    assert a.index.isin(b.index).all(), 'old states disappeared'
    added = b.loc[~b.index.isin(a.index)]
    assert added.path_kind.eq('same_room').all(), 'unexpected state expansion'
    fields = []
    for column in a:
        assert column in b, 'missing source field: '+column
        x, y = a[column], b.loc[a.index, column]
        lost = x.notna() & y.isna()
        changed = ~equal_values(x, y)
        enriched = x.isna() & y.notna()
        if require_restored:
            allowed = enriched if column in AUXILIARY+['reasons'] else pd.Series(False,index=x.index)
            assert not (changed & ~allowed).any(), 'changed old field: '+column
        elif column not in AUXILIARY:
            assert not changed.any(), 'changed old field: '+column
        fields.append(dict(field=column, old_nonmissing=int(x.notna().sum()),
            current_nonmissing_on_old_keys=int(y.notna().sum()), lost=int(lost.sum()),
            changed=int(changed.sum()), supplemented_old_missing=int(enriched.sum()), auxiliary=column in AUXILIARY))
    assert current.B8L2.notna().equals(current.D10.notna())
    return pd.DataFrame(fields), added.reset_index()


def validate_room_prefixes(pairs):
    assert not pairs.duplicated(['request_id', 'replay_id', 'k']).any()
    assert pairs.worker_ids_a.equals(pairs.worker_ids_b), 'different cross-view worker sequence'
    for workers, k in zip(pairs.worker_ids_a, pairs.k):
        ids = json.loads(workers) if workers.startswith('[') else workers.split('|')
        assert len(ids) == k and len(set(ids)) == k
    masks = []
    for side in ['a', 'b']:
        q = pairs['comparison_B8L2_'+side].notna()
        assert q.equals(pairs['comparison_D10_'+side].notna())
        assert (~q | pairs['comparison_quality_allowed_'+side]).all()
        assert (~q | pairs['complete_'+side]).all()
        masks.append(q)
    assert pairs.both_quality.equals(masks[0] & masks[1])
    assert pairs.both_complete.equals(pairs.complete_a & pairs.complete_b)
    return dict(paired_prefixes=len(pairs), both_complete=int(pairs.both_complete.sum()),
        both_primary_quality=int(pairs.both_quality.sum()))


def room_tables(source):
    pairs = pd.read_csv(source/'process_paired_prefixes.csv')
    checks = validate_room_prefixes(pairs)
    meta = read(source/'PROCESS_RESULTS.json')
    assert meta['all_requested_traces_received'] and meta['not_received'] == 0
    assert len(pairs)*2 == meta['validated_side_prefixes'] == meta['planned_side_prefixes']
    assert all(checks[k] == meta[k] for k in checks)
    columns = ['request_id', 'replay_id', 'k', 'worker_ids_a', 'both_complete', 'both_quality']
    for side in ['a', 'b']:
        columns += [name+'_'+side for name in ['image', 'pool_id', 'path_id',
            'reference_id', 'reference_version', 'complete', 'comparison_quality_allowed',
            'comparison_B8L2', 'comparison_D10', 'R_union_normalized', 'R_valid_pairs',
            'R_possible_pairs', 'source_time_complete', 'cumulative_source_seconds',
            'target_time_complete', 'cumulative_target_seconds']]
    curves = pd.read_csv(source/'process_paired_curves.csv')
    stability = pd.read_csv(source/'process_same_k_summary.csv')
    for side in ['a', 'b']:
        d = stability[stability.side.eq(side)].drop(columns='side')
        d = d.rename(columns={c:c+'_'+side for c in d if c not in ['request_id', 'k']})
        curves = curves.merge(d, on=['request_id', 'k'], validate='one_to_one')
    return dict(same_room_process_integration=pairs[columns],
        same_room_curve_integration=curves,
        same_room_common_endpoints=pd.read_csv(source/'common_pool_full_endpoints.csv')), meta


def endpoint_process_status(endpoints, selected, received):
    """模块完成状态不授予每个候选pair真实过程覆盖。"""
    keys = ['image_a', 'image_b']
    assert not selected.duplicated(keys).any()
    expected = set(received.request_id)
    assert expected <= set(selected.request_id)
    out = endpoints.drop(columns=['request_id', 'same_room_process_status'], errors='ignore')
    out = out.merge(selected[keys+['request_id']], on=keys, how='left', validate='one_to_one')
    out['module_upstream_process_complete'] = True
    out['pair_process_received'] = out.request_id.isin(expected)
    out['pair_process_status'] = np.where(out.pair_process_received,
        'real_paired_process_received', 'no_process_for_this_pair')
    return out


def audit_before_repair():
    """只保存修复前损失来源账，不将尚未就绪的源声明为消费快照。"""
    source = ROOT/'research/fusion/wall_consensus_v1_process_20261017/trajectory_scores.csv'
    oldpath = OLD/'inputs/fusion_states.csv'
    before = digest(source)
    old, new = pd.read_csv(oldpath, low_memory=False), pd.read_csv(source, low_memory=False)
    fields, added = reconcile_states(old, new, require_restored=False)
    a, b = old.set_index(KEY), new.set_index(KEY)
    losses = []
    for field in AUXILIARY:
        mask = a[field].notna() & b.loc[a.index, field].isna()
        d = a.loc[mask, [field]].rename(columns={field:'r1_value'}).reset_index()
        d['field'] = field
        losses.append(d)
    assert digest(source) == before, 'source changed while auditing'
    OUT.mkdir(parents=True, exist_ok=True)
    assert not (OUT/'PREPARATION.json').exists(), 'pre-repair evidence already saved; do not overwrite'
    pd.concat(losses, ignore_index=True).to_csv(OUT/'auxiliary_loss_before_repair.csv', index=False)
    fields.to_csv(OUT/'pre_repair_field_audit.csv', index=False)
    write(OUT/'PREPARATION.json', dict(data_release='v1', analysis_revision=REVISION,
        stage='preparation_not_consumed', upstream_ready=False, consumer_complete=False,
        r1_states=len(old), observed_source_states=len(new), added_states=len(added),
        added_same_room_only=True, r1_source=oldpath.relative_to(ROOT).as_posix(),
        r1_sha256=digest(oldpath), pre_repair_source=source.relative_to(ROOT).as_posix(),
        pre_repair_sha256=before, final_snapshot_captured=False,
        auxiliary_loss_cells=sum(int(x.lost) for x in fields.itertuples() if x.auxiliary)))


def selected_sources():
    """只选显示和边界核查所需资料，不重复整套旧统计或原始输入。"""
    roots = {
        'statistics': 'research/statistics/b8l2_d10_statistics_20261017',
        'integrated': 'research/statistics/v1_integrated_analysis_20261017',
        'workers': 'research/workers/worker_v1_composition_20261017',
        'personnel': 'research/workers/worker_v1_pro_integration_20261017',
        'difficulty': 'research/difficulty/difficulty_v1_analysis_20261017',
        'fusion': 'research/fusion/wall_consensus_v1_process_20261017',
        'same_room': 'research/same_room/same_room_v1_process_20261017',
    }
    chosen = {
        'statistics': ['record_lookup', 'worker_inventory', 'image_inventory',
            'worker_condition_stats', 'image_condition_stats', 'difficulty_overview',
            'cleaning_summary', 'calculation_summary', 'time_missing_records',
            'room_group_registry', 'user_original_group_summary', 'room_direct_pair_summary'],
        'integrated': ['worker_mix_adjustment', 'peer_task_evidence',
            'worker_context_relative_effects', 'within_worker_contrasts',
            'team_composition_summary', 'replacement_group_summary',
            'metric_reselection_contrasts', 'strategy_common_pool_summary',
            'strategy_vs_matched_random', 'room_low_tail', 'same_room_weighting_sensitivity'],
        'workers': ['person_profiles', 'statistics_person_evidence', 'statistics_record_profiles',
            'absolute_Q_training_profiles', 'fold_person_profiles',
            'target_pool_group_coverage', 'cross_building_stability', 'disjoint_half_stability'],
        'fusion': ['trajectory_scores', 'by_pool_k', 'completion', 'path_endpoints',
            'pool_eligibility', 'random_matched_changes', 'random_matched_changes_main', 'same_k_stability', 'TEAM_RESULTS',
            'transitions', 'worker_policy_coverage', 'worker_policy_summary',
            'worker_policy_vs_random', 'worker_direct_contrasts'],
        'same_room': ['endpoint_pairs', 'balanced_endpoint_summary', 'selected_process_panel', 'consumer_prefixes',
            'process_paired_prefixes', 'process_paired_curves', 'process_same_k_summary',
            'process_side_completeness', 'common_pool_full_endpoints',
            'consumer_pair_summary', 'control_leave_one_building_out', 'building_controls'],
    }
    selected = []
    for module, root in roots.items():
        paths = sorted((ROOT/root).glob('*.csv')) if module in ['difficulty','personnel'] else [ROOT/root/(n+'.csv') for n in chosen[module]]
        for path in paths:
            assert path.is_file(), str(path)
            selected.append(dict(module=module, path=path.relative_to(ROOT).as_posix(), kind='table'))
        if module == 'difficulty':
            for path in sorted((ROOT/root/'doorway').glob('*.csv')):
                selected.append(dict(module='difficulty', path=path.relative_to(ROOT).as_posix(), kind='table'))
            for path in sorted((ROOT/root/'doorway').glob('*.json')):
                selected.append(dict(module='difficulty', path=path.relative_to(ROOT).as_posix(), kind='document'))
        for name in ['CHECKS.json', 'STATUS.json', 'PROCESS_RESULTS.json', 'CONSUMER_INTERFACE.json',
            'CROSS_MODULE_INPUTS.json', 'CURRENT.json', 'REVISION_CHECKS.json', 'MANIFEST.json',
            'HUMAN_REVIEW_CASES.json', 'INPUTS.json', 'FIELD_CONTRACT.json', 'HANDOFF.md']:
            path = ROOT/root/name
            if path.is_file():
                selected.append(dict(module=module, path=path.relative_to(ROOT).as_posix(), kind='document'))
    for path in ['research/quality/quality_b8l2_d10_20261017/CROSS_MODULE_INPUTS.json',
        'research/data/releases/v1/RELEASE.json']:
        selected.append(dict(module='input', path=path, kind='document'))
    selected.append(dict(module='quality',
        path='research/quality/quality_b8l2_d10_20261017/shared_records.csv', kind='table'))
    return selected


def capture_sources(files, *, sources_ready=False):
    assert sources_ready, 'wait for explicit upstream-ready notice before final capture'
    assert not (OUT/'SNAPSHOT.zip').exists(), 'snapshot already captured; replay it instead'
    before = {f['path']: digest(ROOT/f['path']) for f in files}
    OUT.mkdir(parents=True, exist_ok=True)
    archive = OUT/'SNAPSHOT.pending.zip'
    entries = []
    try:
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
            for f in files:
                data = (ROOT/f['path']).read_bytes()
                assert hashlib.sha256(data).hexdigest() == before[f['path']], 'source changed during capture'
                bundle.writestr(f['path'], data)
                entries.append(dict(f, sha256=before[f['path']], bytes=len(data)))
        assert all(digest(ROOT/f['path']) == before[f['path']] for f in files), 'source changed before publication'
        archive.rename(OUT/'SNAPSHOT.zip')
    except BaseException:
        archive.unlink(missing_ok=True)
        raise
    manifest = dict(schema='v1_statistics_consumer_snapshot_v1', data_release='v1',
        snapshot_id=REVISION, explicit_upstream_ready_notice=True,
        captured_at=datetime.now(timezone.utc).isoformat(), files=entries,
        archive='SNAPSHOT.zip', archive_sha256=digest(OUT/'SNAPSHOT.zip'),
        old_fixed_snapshot_data_unchanged=True,
        shared_frontend_reused_with_revision_branch=True, raw_annotation_blobs_included=False)
    write(OUT/'SOURCE_MANIFEST.json', manifest)
    return manifest


def extract_snapshot(destination):
    manifest = read(OUT/'SOURCE_MANIFEST.json')
    assert manifest['snapshot_id'] == REVISION and manifest['data_release'] == 'v1'
    assert digest(OUT/'SNAPSHOT.zip') == manifest['archive_sha256']
    with zipfile.ZipFile(OUT/'SNAPSHOT.zip') as bundle:
        assert set(bundle.namelist()) == {f['path'] for f in manifest['files']}
        for entry in manifest['files']:
            path = Path(entry['path'])
            assert not path.is_absolute() and '..' not in path.parts
            data = bundle.read(entry['path'])
            assert len(data) == entry['bytes'] and hashlib.sha256(data).hexdigest() == entry['sha256']
            target = destination/path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    return manifest


def publish_local_data(data):
    """从消费JSON生成本地脚本分片，保持数据和按需读取粒度。"""
    for stale in data.rglob('*.js'):
        stale.unlink()
    files = sorted(data.rglob('*.json'))
    for path in files:
        payload = path.read_text(encoding='utf-8')
        json.loads(payload)
        path.with_suffix('.js').write_text(
            "window.researchLocalData[document.currentScript.src.replace(/\\.js$/, '.json')]= "
            + payload + ';\n', encoding='utf-8')
    return len(files)


def publish_explorer(source_root, manifest, derived, overview):
    """复用原浏览台字段/隐私规则；新目录按需分片，不重建旧195表。"""
    from . import build_research_explorer_20261017 as display
    data = EXPLORER/'explorer-data'
    assert not data.exists() or not any(data.iterdir()), 'choose a fresh display output'
    entries = [f for f in manifest['files'] if f['kind'] == 'table']
    for name, frame in derived.items():
        path = OUT/(name+'.csv')
        frame.to_csv(path, index=False)
        entries.append(dict(module='same_room' if name.startswith('same_room') else 'statistics',
            path=path.relative_to(ROOT).as_posix(), kind='derived', sha256=digest(path)))
    index = dict(schema_version='research_explorer_v1', snapshot_id=REVISION,
        data_release='v1', source_commit=None, overview_path='overview.json',
        source_manifest='research/statistics/v1_integrated_analysis_20261017_r2/SOURCE_MANIFEST.json',
        source_repository='local-owner-private-consumer-snapshot', tables=[], modules=[], documents=[], warnings=[],
        privacy=dict(raw_annotation_blobs_included=False, personal_name_contact_fields_omitted=True))
    for entry in entries:
        path = (ROOT if entry['kind'] == 'derived' else source_root)/entry['path']
        rawbytes = path.read_bytes()
        assert hashlib.sha256(rawbytes).hexdigest() == entry['sha256']
        reader = csv.reader(io.StringIO(rawbytes.decode('utf-8-sig'), newline=''))
        original = next(reader)
        keep = [i for i, c in enumerate(original) if not display.PERSONAL_FIELDS.search(c)]
        columns = [original[i] for i in keep]
        module = {'integrated':'statistics','personnel':'workers'}.get(entry['module'],entry['module'])
        stem = Path(entry['path']).stem
        if '/doorway/' in entry['path']: stem = 'doorway__'+stem
        tid = module+'__'+stem
        assert not any(t['id'] == tid for t in index['tables']), tid
        parts, chunk, start, size = [], [], 0, 0
        types = [set() for _ in columns]

        def flush():
            nonlocal chunk, start, size
            name = f'tables/{tid}.{len(parts)}.json'
            nbytes = display.dump(data/name, dict(table_id=tid, columns=columns, rows=chunk))
            assert nbytes < 20*1024*1024
            parts.append(dict(path=name, row_start=start, row_count=len(chunk), bytes=nbytes))
            start += len(chunk)
            chunk, size = [], 0

        for raw in reader:
            assert len(raw) == len(original), entry['path']
            row = [display.parse_cell(raw[i], original[i]) for i in keep]
            for j, value in enumerate(row):
                if value is not None: types[j].add(type(value).__name__)
            nbytes = len(json.dumps(row, ensure_ascii=False, separators=(',', ':')).encode())+1
            if chunk and size+nbytes > 14*1024*1024: flush()
            chunk.append(row); size += nbytes
        if chunk or not parts: flush()
        ctype = ['null' if not t else 'number' if t <= {'int','float'} else
            'boolean' if t == {'bool'} else 'string' if t == {'str'} else 'mixed' for t in types]
        caveats = ['数据v1分析修订r2；行数不是独立样本数。缺失不补0。',
            'B8L2主线；D10仅同输入、参考、资格下的方向尺度敏感性。']
        if entry['module'] == 'integrated':
            caveats.append('继承未变r1派生表；来源、捕获时刻及原用途保留，不冒充新实验。')
        baseline_evidence = entry['module']=='workers' and stem in ['statistics_person_evidence','statistics_record_profiles']
        if baseline_evidence:
            caveats.append('旧人员证据接口基线；新强gold、审核漏项与scope兼容请读worker_v1_pro_integration接口，不覆盖旧分母。')
        index['tables'].append(dict(id=tid, module=module, path=entry['path'], label=stem,
            columns=columns, column_types=ctype, row_count=start, parts=parts,
            field_map=display.field_map(columns), grain=display.infer_grain(stem, columns),
            status='superseded' if baseline_evidence else 'current', sha256=entry['sha256'], caveats=caveats,
            source_url='../v1_integrated_analysis_20261017_r2/SOURCE_MANIFEST.json',
            redacted_columns=[c for c in original if display.PERSONAL_FIELDS.search(c)],
            condition_fields=[c for c in columns if c in ['condition','metric','selection_metric',
                'path_kind','layer','difficulty','scene_axis','quality_use','policy','axis','fold']],
            validity_fields=[c for c in columns if any(v in c for v in ['eligible','allowed','complete','missing','status','support'])]))
    for module in sorted({t['module'] for t in index['tables']}):
        index['modules'].append(dict(id=module, label=module, path='', status='current'))
    for entry in manifest['files']:
        if entry['kind'] != 'document': continue
        path = source_root/entry['path']
        content = path.read_text(encoding='utf-8-sig')
        content = display.EMAIL.sub('[redacted email]', content)
        index['documents'].append(dict(path=entry['path'], module=entry['module'],
            kind=path.suffix[1:], sha256=entry['sha256'],
            content=json.loads(content) if path.suffix == '.json' else content))
    index.update(table_count=len(index['tables']), current_table_count=sum(t['status']=='current' for t in index['tables']),
        total_row_count=sum(t['row_count'] for t in index['tables']))
    display.dump(data/'overview.json', overview)
    display.dump(data/'index.json', index)
    publish_local_data(data)
    write(EXPLORER/'data-inventory.json', [{k:v for k,v in t.items() if k != 'parts'} for t in index['tables']])
    write(EXPLORER/'source-manifest.json', manifest)
    return index


def validate_person_links(persons, records, inventory):
    assert not persons.duplicated(['worker_id','metric']).any()
    assert not records.duplicated(['object_id','metric']).any()
    assert set(persons.metric) == set(records.metric) == {'B8L2','D10'}
    assert not inventory.object_id.duplicated().any()
    for metric in ['B8L2','D10']:
        d = records[records.metric.eq(metric)].set_index('object_id')
        target = inventory.set_index('object_id')
        assert set(d.index) == set(target.index)
        d = d.loc[target.index]
        assert d.worker_id.equals(target.worker_id)
        assert d.quality_usable.equals(target.quality_usable)
        assert equal_values(d.score, target[metric]).all()
    return dict(person_metric_rows=len(persons), record_metric_rows=len(records),
        identities_matched=True, quality_masks_matched=True, score_values_matched=True)


def validate_room_consumer(prefixes, pairs, states):
    keys = ['request_id','replay_id','side','k']
    assert not prefixes.duplicated(keys).any()
    assert not pairs.request_id.duplicated().any()
    available = prefixes.comparison_B8L2.notna()
    assert available.equals(prefixes.comparison_D10.notna())
    assert available.equals(prefixes.primary_quality_available)
    assert (~available | prefixes.primary_quality_eligible).all()
    assert (~available | prefixes.complete_evaluable).all()
    invalid = set(pairs.loc[~pairs.primary_design_eligible, 'request_id'])
    assert prefixes.loc[prefixes.request_id.isin(invalid),'comparison_B8L2'].isna().all()
    producer = states[states.path_kind.eq('same_room')].set_index(KEY)
    d = prefixes.set_index(KEY)
    assert set(d.index) == set(producer.index)
    producer = producer.loc[d.index]
    assert d.member_workers.equals(producer.member_workers)
    assert d.reference_id.equals(producer.reference_id)
    assert d.reference_version.equals(producer.reference_version)
    assert equal_values(d.loc[available.to_numpy(),'comparison_B8L2'],
        producer.loc[available.to_numpy(),'B8L2']).all()
    assert equal_values(d.loc[available.to_numpy(),'comparison_D10'],
        producer.loc[available.to_numpy(),'D10']).all()
    return dict(side_prefixes=len(prefixes), primary_numeric=int(available.sum()),
        pairs=len(pairs), buildings=pairs.building.nunique(),
        diagnostic_pairs=len(invalid), producer_keys_members_reference_matched=True)


def validate_difficulty_process(source, fusion, states):
    fixed = pd.read_csv(source/'fusion_fixed_pool_k.csv')
    full = pd.read_csv(fusion/'by_pool_k.csv')
    assert fixed.path_kind.eq('random').all()
    full = full[full.path_kind.eq('random')]
    keys = ['pool_id','path_kind','k']
    assert not fixed.duplicated(keys).any() and not full.duplicated(keys).any()
    a, b = fixed.set_index(keys), full.set_index(keys)
    assert a.index.isin(b.index).all()
    b = b.loc[a.index]
    compared = [c for c in a if c in b]
    for field in compared: assert equal_values(a[field],b[field]).all(), field
    nodes = pd.read_csv(source/'doorway/random_nodes.csv',low_memory=False)
    a, b = nodes.set_index(KEY), states.set_index(KEY)
    assert a.index.is_unique and a.index.isin(b.index).all()
    b = b.loc[a.index]
    columns = [c for c in a if c in b]
    for field in columns: assert equal_values(a[field],b[field]).all(), 'doorway: '+field
    panels = pd.read_csv(source/'doorway/panel_summary.csv')
    primary = panels[panels.panel.eq('primary15')].sort_values('k')
    assert primary.k.tolist()==[1,3,4,6] and primary.opportunities.eq(60).all()
    assert primary.quality.tolist()==[60,57,46,53]
    metadata = read(source/'CROSS_MODULE_INPUTS.json')
    producer = read(fusion/'CURRENT.json')
    assert metadata['fusion_analysis_revision'] == producer['analysis_revision']
    return dict(ordinary_rows=len(fixed),ordinary_images=fixed.image.nunique(),
        ordinary_fields_compared=compared,doorway_states=len(nodes),doorway_images=nodes.image.nunique(),
        doorway_fields_compared=columns,doorway_complete=int(nodes.complete_evaluable.sum()),
        doorway_primary_numeric=int(nodes.primary_score_usable.sum()),
        primary15_opportunities=primary.opportunities.tolist(),primary15_quality=primary.quality.tolist(),
        producer_revision=producer['analysis_revision'])


def validate_person_pro(source, baseline, inventory, fusion):
    interface = read(source/'CROSS_MODULE_INPUTS.json')
    assert interface['status'] == 'ready' and interface['data_release'] == 'v1'
    records = pd.read_csv(source/'record_evidence.csv').set_index('object_id')
    target = inventory.set_index('object_id')
    assert records.index.is_unique and set(records.index)==set(target.index)
    records = records.loc[target.index]
    for field in ['worker_id','image_id','condition','quality_usable','B8L2','D10']:
        assert equal_values(records[field],target[field]).all(), field
    assert records.in_Q_training.sum()==1048
    persons = pd.read_csv(source/'person_profiles_and_evidence.csv').set_index(['worker_id','metric'])
    old = pd.read_csv(baseline/'person_profiles.csv').set_index(persons.index.names)
    assert persons.index.is_unique and set(persons.index)==set(old.index)
    for field in old:
        assert equal_values(persons.loc[old.index,field],old[field]).all(), field
    correction = pd.read_csv(source/'semi_correction_evidence.csv')
    bridge = pd.read_csv(source/'correction_definition_bridge.csv')
    strong = correction.confirmed_initialization_error_opportunity
    assert strong.sum()==156 and correction.known_error_unchanged.sum()==25
    assert correction.changed_error_specific_residual_unknown.sum()==131
    assert correction.reviewer_residual_after_edit_statement.sum()==3
    assert bridge.old_opportunity.sum()==288 and bridge.strong_gold_opportunity.sum()==156
    assert (bridge.old_opportunity & bridge.strong_gold_opportunity).sum()==144
    residual = correction[correction.reviewer_residual_after_edit_statement]
    assert set(residual.object_id)=={'b62a4df9e1645fe7','717840fe8221eba6','28935ccbb578589d'}
    assert residual.source_verdict.eq('usable').all()
    assert not residual.confirmed_initialization_error_opportunity.any()
    exclusions = pd.read_csv(source/'exclusion_candidate_evidence.csv')
    assert len(exclusions)==85 and not exclusions.independent_severity_adjudicated_here.any()
    scope = pd.read_csv(source/'scope_evidence.csv')
    assert scope.object_id.is_unique and len(scope)==3222
    assert not scope.current_target_gold_independently_adjudicated_here.any()
    gains = pd.read_csv(source/'semi_initialization_scores.csv')
    ordinary = gains[gains.current_qualified_gain_available & gains.current_quality_use.eq('ordinary_primary')]
    assert len(ordinary)==437 and ordinary.semi_ordinary_profile_training_candidate.sum()==409
    teams = pd.read_csv(source/'team_results.csv')
    produced = pd.read_csv(fusion/'TEAM_RESULTS.csv')
    assert teams.request_id.is_unique and produced.request_id.is_unique
    assert set(teams.request_id)==set(produced.request_id)
    a,b = teams.set_index('request_id'),produced.set_index('request_id')
    b = b.loc[a.index]
    for field in ['status','k','worker_ids','B8L2','D10','main_comparison_allowed']:
        assert equal_values(a[field],b[field]).all(),field
    return dict(records=len(records),person_metric_rows=len(persons),Q_training=1048,
        old_opportunities=288,strong_gold_opportunities=156,opportunity_intersection=144,
        strong_unchanged=25,strong_edited_outcome_unknown=131,residual_statements=3,
        candidate_specific=int(exclusions.pro_candidate_specific_reason.sum()),
        candidate_broad=int(exclusions.pro_candidate_broad_nonacceptance.sum()),
        ordinary_compatible_gains=437,ordinary_semi_training=409,original_holdout_gains=int(ordinary.original_holdout.sum()),
        teams=len(teams),team_completed=int(teams.status.eq('completed').sum()),
        B8L2_mean_gain=ordinary.worker_attributable_gain_B8L2.mean(),
        D10_mean_gain=ordinary.worker_attributable_gain_D10.mean(),
        no_new_severity_or_scope_gold=True,manual_profiles_unchanged=True)


def json_ready(value):
    if isinstance(value, dict): return {k:json_ready(v) for k,v in value.items()}
    if isinstance(value, (list, tuple)): return [json_ready(v) for v in value]
    if isinstance(value, np.generic): value = value.item()
    return None if isinstance(value, float) and not np.isfinite(value) else value


def make_overview(source, room, checks):
    stats = source/'research/statistics/b8l2_d10_statistics_20261017'
    fusion = source/'research/fusion/wall_consensus_v1_process_20261017'
    workers = source/'research/workers/worker_v1_composition_20261017'
    pro = source/'research/workers/worker_v1_pro_integration_20261017'
    rooms = source/'research/same_room/same_room_v1_process_20261017'
    inventory = pd.read_csv(stats/'record_lookup.csv', low_memory=False)
    quality = inventory[inventory.quality_usable]
    manual = quality[quality.condition.eq('manual')]
    train = pd.read_csv(workers/'statistics_record_profiles.csv')
    training = train[train.metric.eq('B8L2') & train.in_Q_training]
    persons = pd.read_csv(workers/'person_profiles.csv')
    persons = persons[persons.metric.eq('B8L2')]
    mix = pd.read_csv(source/'research/statistics/v1_integrated_analysis_20261017/worker_mix_adjustment.csv')
    mix = mix[mix.metric.eq('B8L2')]
    paired = pd.read_csv(rooms/'consumer_pair_summary.csv')
    sections = []

    def links(*names):
        return [dict(id=n, label=label) for n,label in names]

    def points(frame, x, y, label=None, support=None):
        return [dict(x=r[x], y=r[y], label=r[label] if label else r[x],
            n=r[support] if support else None) for r in frame.to_dict('records')]

    coverage = [dict(x=i+1, y=n, label=label) for i,(label,n) in enumerate([
        ('全库存',len(inventory)),('当前质量',len(quality)),
        ('质量×来源时间',quality.source_active_time_seconds.notna().sum()),
        ('质量×同目标时间',quality.target_matched_time_seconds.notna().sum())])]
    sections.append(dict(id='coverage', title='库存与可用覆盖', status='supported',
        expectation='现有v1能够支持分条件、场景与用途的有限比较。',
        finding=f'库存{len(inventory)}份，当前质量{len(quality)}份；可用覆盖足以开始分层分析，时间交集与主用途仍须各自计数。',
        support=f'{inventory.image_id.nunique()}图 / {inventory.building_id.nunique()}楼 / {inventory.worker_id.nunique()}来源身份；质量{quality.image_id.nunique()}图 / {quality.building_id.nunique()}楼。',
        counterexample='来源时间齐全不代表选定空间的时间齐全。低人数、GT错误及OOS仍按原门保留；库存总数不能代替各层分母。',
        charts=[dict(title='各用途的真实非空交集',x_label='1 库存 · 2 质量 · 3 来源时间 · 4 同目标时间',
            type='scatter',series=[dict(label='作答份数',points=coverage)],note='时间点只在质量合格记录内计数；交集不能相加。')],
        tables=links(('statistics__record_lookup','逐份资格与缺失'),('statistics__calculation_summary','计算状态'))))

    effect_col, raw_col = 'relative_Q_effect', 'raw_mean'
    sections.append(dict(id='people',title='人员：绝对Q、相对Q与时间',status='supported',
        expectation='人员原始均值会受到任务组成影响，质量与效率需要分别解释。',
        finding='同一训练面板上的原始Q与任务调整相对Q并列；调整后的位置变化说明任务组成影响解释，不能由此认定一种画像全面胜出。',
        support=f'普通Manual训练{len(training)}份 / {training.image_id.nunique()}图 / {training.building_id.nunique()}楼 / {training.worker_id.nunique()}人；Q/T画像的各自支持见详情。',
        counterexample='相对Q的0是当前池参照，时间效应0也不是效率合格线。区间跨零及稀疏人员仍保留，不建立通用总分。',
        charts=[dict(title='同面板原始均值与调整Q',type='scatter',x_label='原始B8L2均值',
            series=[dict(label='人员（悬停看编号）',points=points(mix,raw_col,effect_col,'worker_id'))],note='横轴绝对Q，纵轴任务调整相对Q；不是两个可直接相加的分量。'),
            dict(title='质量与来源时间的调整效应',type='scatter',x_label='Q效应（池内相对）',
            series=[dict(label='人员',points=points(persons,'Q_effect','T_source_effect','worker_id','Q_contexts'))],
            note='纵轴为来源时间模型效应，负值表示相对更快；源时间和同目标时间不互换。')],
        tables=links(('statistics__worker_mix_adjustment','同面板绝对/相对Q'),
            ('workers__person_profiles_and_evidence','画像与可靠性'),('workers__record_evidence','逐记录证据连接'))))

    gains = pd.read_csv(pro/'semi_initialization_scores.csv')
    gain = gains[gains.current_qualified_gain_available & gains.current_quality_use.eq('ordinary_primary')]
    correction = pd.read_csv(pro/'semi_correction_evidence.csv')
    strong = correction[correction.confirmed_initialization_error_opportunity]
    gain_workers = gain.groupby('worker_id').agg(initial=('initial_B8L2','mean'),
        final=('final_B8L2','mean'),n=('object_id','size')).reset_index()
    sections.append(dict(id='reliability',title='Semi增益、纠错与严重失误证据',status='insufficient',
        expectation='Semi最终分较高，能够说明人工修好了初始化错误并产生净改善。',
        finding=f'普通兼容同参考的{len(gain)}份中，B8L2平均人工可归因净变化为{gain.worker_attributable_gain_B8L2.mean():.2f}。156次实际强缺陷机会有25次未改、131次编辑后语义未知；最终高分不能代替纠错结局。',
        support=f'兼容增益{gain.image_id.nunique()}图/{gain.building_id.nunique()}楼/{gain.worker_id.nunique()}人，含409开发训练及28原留出；强gold {strong.image_id.nunique()}图/{strong.building_id.nunique()}楼/{strong.worker_id.nunique()}人，历史排除不恢复资格。',
        counterexample='没有同任务Manual反事实，负净变化不能证明Semi辅助有害。3条“修改后仍有问题”均为usable且不属于156分母。25具体/68宽剔除编码仍是文本候选；W001/Uw-08只在要归因为个人几何错误时需历史政策裁决。',
        charts=[dict(title='同一兼容集合的初始化与最终Q',type='scatter',x_label='初始B8L2均值',
            series=[dict(label='人员，纵轴最终Q',points=points(gain_workers,'initial','final','worker_id','n'))],
            note='人员每个点使用同一组兼容作答；实际观看事件、原生环序未确认和研究者修订限制仍在底表。'),
            dict(title='两套纠错定义不互相替代',type='scatter',x_label='1 旧机会 · 2 强gold机会 · 3 已知未改 · 4 编辑后未知',
                series=[dict(label='证据份数',points=[dict(x=i+1,y=n,label=label) for i,(label,n) in enumerate([
                    ('旧trap机会',288),('强gold机会',156),('强gold未改',25),('强gold编辑后未知',131)])])],
                note='旧288与强gold156共同144；旧独有144、新独有12。未改25与未知131构成156，未知不算成功。')],
        tables=links(('workers__semi_initialization_scores','初始化与兼容净变化'),
            ('workers__semi_correction_evidence','纠错机会与修改后未知'),
            ('workers__correction_definition_bridge','288/156逐对象桥接'),
            ('workers__exclusion_candidate_evidence','剔除候选与归因边界'),('workers__scope_evidence','历史scope与当前兼容'))))

    scene = manual.groupby('quality_use').agg(n=('object_id','size'),images=('image_id','nunique'),
        buildings=('building_id','nunique'),B8L2=('B8L2','mean')).reset_index()
    ordinary = manual[manual.quality_use.eq('ordinary_primary')]
    difficulty = ordinary.groupby('difficulty_class').agg(n=('object_id','size'),B8L2=('B8L2','mean')).reset_index()
    difficulty['position'] = range(1,len(difficulty)+1)
    doorway = manual[manual.quality_use.eq('doorway_quality')]
    scene['position'] = range(1,len(scene)+1)
    sections.append(dict(id='scenes',title='普通、门洞与难度',status='insufficient',
        expectation='难度与门洞条件能够解释质量差异，并可由普通场景画像直接迁移。',
        finding=f'普通Manual有{len(ordinary)}份，门洞有{len(doorway)}份/{doorway.image_id.nunique()}图。分布差异可描述；任务、人群及参考范围共同变化，尚不能把差异归为单一难度效应。',
        support=f'普通{ordinary.image_id.nunique()}图/{ordinary.building_id.nunique()}楼；门洞{doorway.image_id.nunique()}图/{doorway.building_id.nunique()}楼。门洞固定17图与15图主资格过程另列。',
        counterexample='门洞低均值不自动证明人员差或GT错误；难度标签不能用自身质量均值循环验证。OOS交叉层不进入主质量。',
        charts=[dict(title='Manual各用途的作答等权均值',type='scatter',x_label='用途序号（具体名称与支持见数值）',
            series=[dict(label='B8L2',points=points(scene,'position','B8L2','quality_use','n'))],note='与图等权均值分开；专项不混入普通。'),
            dict(title='普通Manual难度分层',type='scatter',x_label='难度类别序号（悬停看类别）',
            series=[dict(label='B8L2',points=points(difficulty,'position','B8L2','difficulty_class','n'))],note='固定当前评分与人工粗难度；不由得分重分标签。')],
        examples=dict(columns=scene.columns.tolist(),rows=scene.values.tolist()),
        tables=links(('difficulty__strata_summary','场景与难度分布'),('difficulty__fusion_fixed_panel_summary','普通固定面板人数过程'))))

    doorway_root = source/'research/difficulty/difficulty_v1_analysis_20261017/doorway'
    door_summary = pd.read_csv(doorway_root/'panel_summary.csv')
    primary15 = door_summary[door_summary.panel.eq('primary15')].sort_values('k')
    door_members = pd.read_csv(doorway_root/'panels.csv')
    door_members = door_members[door_members.panel.eq('primary15')]
    sections.append(dict(id='doorway',title='门洞交界：固定面板人数过程',status='unsupported',
        expectation='在同一批门洞图中，人数增加会持续提高完整率与参考质量。',
        finding='15图主资格面板每个k均保留60次机会；k=1/3/4/6的主质量可用为60/57/46/53。过程并非单调改善，成功条件Q与全机会可用率必须一起看。',
        support=f'固定15图/{door_members.image.str.split("-").str[0].nunique()}楼，4次相关随机重放；17图机会面板另有808状态、703完整、655主质量、59来源时间齐全。',
        counterexample='k=4的失完整不能被较高成功条件Q掩盖。k=8只有14图、k=12只有4图，另列固定面板，不能接在15图曲线后冒充同一批图。q9-24/B6-43混目标与7y-06终点缺完整Q分别保留。',
        charts=[dict(title='15图主资格：成功条件Q',type='line',x_label='人数k',series=[
            dict(label='B8L2图等权',points=points(primary15,'k','B8L2_image_equal_mean',support='quality_images')),
            dict(label='D10图等权',points=points(primary15,'k','D10_image_equal_mean',support='quality_images'))],
            note='各k数值只在成功条件下计算，支持图片数可能变化；对照右图的60次固定机会。'),
            dict(title='15图主资格：完整率与质量可用率',type='line',x_label='人数k',series=[
                dict(label='完整率',points=points(primary15,'k','complete_rate',support='opportunities')),
                dict(label='主质量可用率',points=points(primary15,'k','quality_rate',support='opportunities'))],note='两个比率可能重合；分母始终为60。'),
            dict(title='15图原答分歧R',type='line',x_label='人数k',series=[
                dict(label='原答R',points=points(primary15,'k','R_image_equal_mean',support='R_images'))],note='k=1没有原答两两R，不填0；R支持图片数单列。'),
            dict(title='15图同人数融合波动V',type='line',x_label='人数k',series=[
                dict(label='不同成员子集V',points=points(primary15,'k','V_different_subset_image_mean',support='V_images'))],note='V与原答R及参考Q不同；有效对数与重复全员集合见底表。')],
        tables=links(('difficulty__doorway__panel_summary','固定17/15及高人数面板'),
            ('difficulty__doorway__random_nodes','808条真实门洞状态'),('difficulty__doorway__cases','失败与混范围案例'))))

    changes = pd.read_csv(fusion/'random_matched_changes_main.csv')
    changes = changes[changes.condition.eq('manual') & changes.layer.eq('ordinary') & changes.k_from.eq(8) & changes.k_to.eq(16)]
    valid = changes[changes.B8L2_change.notna() & changes.V_strict_from.notna() & changes.V_strict_to.notna()]
    counter = valid[(valid.V_strict_to < valid.V_strict_from) & (valid.B8L2_change < 0)]
    sections.append(dict(id='process',title='增人：稳定性、参考质量与完整率',status='unsupported',
        expectation='增人使融合趋稳时，也会更接近参考。',
        finding=f'主比较普通Manual的8→16人面板有{len(changes)}图；在Q及严格同一重放对V均可用的{len(valid)}图中，{len(counter)}图V下降而Q下降。趋稳与准确性不是同一结果。',
        support=f'{len(changes)}独立图 / {changes.image.str.split("-").str[0].nunique()}楼；每图最多4条相关随机重放。失败和完整率以机会分母报告。',
        counterexample='散点只画两端可比较部分，缺失仍在明细。这里的严格V只用两端共同有效的重放对，不能与边际有效对数变化的V混称同一估计量。',
        charts=[dict(title='严格同一重放对的V变化与Q变化',type='scatter',x_label='V(16人) − V(8人)',
            series=[dict(label='图',points=[dict(x=r.V_strict_to-r.V_strict_from,y=r.B8L2_change,label=r.image,n=r.V_strict_pairs) for r in valid.itertuples()])],
            note='纵轴B8L2变化；左下区域是趋稳但Q下降的反例。'),
            dict(title='机会面板上的完整结果数',type='scatter',x_label='图序号',series=[
                dict(label='8人完整路径',points=[dict(x=i+1,y=r.complete_from,label=r.image,n=r.paths) for i,r in enumerate(changes.itertuples())]),
                dict(label='16人完整路径',points=[dict(x=i+1,y=r.complete_to,label=r.image,n=r.paths) for i,r in enumerate(changes.itertuples())])],note='每图4次计划重放；不把成功条件均值当全机会结果。')],
        examples=dict(columns=['image','B8L2_change','V_strict_from','V_strict_to','complete_from','complete_to'],
            rows=counter[['image','B8L2_change','V_strict_from','V_strict_to','complete_from','complete_to']].head(8).values.tolist()),
        tables=links(('fusion__random_matched_changes_main','主用途匹配变化'),('fusion__random_matched_changes','含留出描述'),('fusion__trajectory_scores','全41859真实状态'))))

    strategy = pd.read_csv(fusion/'worker_policy_vs_random.csv')
    strategy = strategy[strategy.k.eq(3)&strategy.selection_metric.eq('B8L2')&strategy.both_main]
    policy = strategy.groupby('policy').agg(images=('image','nunique'),buildings=('building','nunique'),
        B8L2_delta=('B8L2_difference','mean'),negative=('B8L2_difference',lambda x:(x<0).sum())).reset_index()
    policy['position'] = range(1,len(policy)+1)
    sections.append(dict(id='strategy',title='人员策略与具体成员',status='insufficient',
        expectation='按较高Q或Q/T优先进入，能在同图同人数下稳定优于随机。',
        finding='同图k=3、共同主质量的策略—随机对照已接入。各策略的图集合、可支持成员和相对收益不同，不能从优先顺序推成纯类别团队的普遍胜者。',
        support=f'当前k=3对照覆盖{strategy.image.nunique()}独立图/{strategy.building.nunique()}楼；每策略的支持和负向例见数值。',
        counterexample='固定成员改B8L2→D10与按D10重新选人分别记录。成员重叠、路径重放与图内多策略相关，不能按比较行数当独立重复。',
        charts=[dict(title='策略相对配对随机的B8L2差',type='scatter',x_label='策略序号（悬停看名称）',
            series=[dict(label='策略均值',points=points(policy,'position','B8L2_delta','policy','images'))],note='选择标签固定B8L2、终点评价也固定B8L2；同图同k，支持集合可能不同。')],
        examples=dict(columns=policy.columns.tolist(),rows=policy.values.tolist()),
        tables=links(('fusion__worker_policy_vs_random','逐图策略与随机'),('statistics__metric_reselection_contrasts','固定团队换指标/重选分解'),('statistics__strategy_common_pool_summary','纯类别共同图片比较'))))

    primary = paired[paired.primary_design_eligible]
    endpoints = room['same_room_common_endpoints'].merge(paired[['request_id','image_a','image_b']],on='request_id',validate='one_to_one')
    gap = primary[['request_id','B8L2_gap_k1','B8L2_gap_full']].copy();gap['position']=range(1,len(gap)+1)
    smaller = primary.B8L2_gap_full_minus_k1.lt(0).sum()
    sections.append(dict(id='same_room',title='同房：相同成员的跨视角过程',status='insufficient',
        expectation='同房相同人员随人数增加，两视角的参考质量差距普遍缩小。',
        finding=f'9对/7楼的536条单侧状态已接入；7对主质量中，k=1到全共同池差距{smaller}缩小、{len(primary)-smaller}扩大。当前证据不支持普遍趋同或已完成预测验证。',
        support='268双侧前缀，228双侧完整、196双侧主质量；4次相关重放。G036缺完整参考、G202混目标整对诊断，9对全为普通场景。',
        counterexample='G172/uNb-01与45由相同15人构成，全共同池各自参考B8L2约49.05与92.00；几何趋稳仍可质量分离。没有跨相机BEV直接相减。',
        charts=[dict(title='7对各自参考Q的绝对差',type='scatter',x_label='主资格图对序号',series=[
            dict(label='k=1',points=points(gap,'position','B8L2_gap_k1','request_id')),
            dict(label='全共同池',points=points(gap,'position','B8L2_gap_full','request_id'))],note='两端均为相同共同人员池内过程；不是原图全部来源人员终点。')],
        examples=dict(columns=['image_a','image_b','N','full_B8L2_a','full_B8L2_b'],
            rows=endpoints[['image_a','image_b','N','full_B8L2_a','full_B8L2_b']].values.tolist()),
        tables=links(('same_room__consumer_prefixes','536条窄接口与掩码'),('same_room__consumer_pair_summary','9对过程摘要'),('same_room__same_room_endpoint_integration','217候选的逐对覆盖状态'))))
    questions = {
        'inventory': [['库存与资格','record_lookup','B8L2','','histogram']],
        'quality': [['质量分布','^quality__shared_records$','B8L2','','histogram'],
            ['固定记录换方向尺度','^quality__shared_records$','B8L2','D10','scatter']],
        'workers': [['同面板绝对与相对Q','worker_mix_adjustment','raw_mean','relative_Q_effect','scatter'],
            ['Q与来源时间','^workers__person_profiles$','Q_effect','T_source_effect','scatter']],
        'difficulty': [['难度与分布','^difficulty__image_condition$','B8L2_mean','','histogram'],
            ['门洞固定机会完整率','doorway__panel_summary','k','complete_rate','scatter']],
        'fusion': [['同图同k真实状态','^fusion__trajectory_scores$','k','B8L2','scatter'],
            ['严格匹配变化','^fusion__random_matched_changes_main$','V_strict_to','B8L2_change','scatter']],
        'same_room': [['同房主掩码过程','^same_room__consumer_prefixes$','k','comparison_B8L2','scatter'],
            ['同成员跨视角差距','^same_room__consumer_pair_summary$','B8L2_gap_k1','B8L2_gap_full','scatter']],
        'time': [['来源时间和质量','^statistics__record_lookup$','source_active_time_seconds','B8L2','scatter'],
            ['同目标时间和质量','^statistics__record_lookup$','target_matched_time_seconds','B8L2','scatter']],
    }
    return json_ready(dict(metadata=dict(snapshot_id=REVISION,data_release='v1',primary_metric='B8L2',sensitivity_metric='D10'),
        headline_counts=[dict(label='库存作答',value=len(inventory),note=f'{inventory.image_id.nunique()}图，所有排除仍保留'),
            dict(label='质量可用',value=len(quality),note='1699普通 + 188门洞 + 24其它'),
            dict(label='已消费真实过程状态',value=checks['current_states'],note='包含新增536同房；不是独立样本数'),
            dict(label='同房过程',value=9,note='7楼；196个双侧主质量前缀')],
        sections=sections,module_warnings=dict(fusion='208图，233成功来源池及1整池失败；人数、Q、V与完整率分别解释。',
            same_room='仅9对有真实成对过程；217候选不等于217过程。G036/G202整对诊断。',
            workers='Q1048普通训练面板；连续画像、时间和可靠性证据并列，不形成通用总分。',
            time='来源任务时间与同目标时间分别解释；Semi兼容初始化增益是条件诊断。'),
        tables={},presets={m:[q[1:] for q in qs] for m,qs in questions.items()},
        default_tables=dict(inventory='statistics__record_lookup',quality='quality__shared_records',
            difficulty='difficulty__strata_summary',workers='workers__person_profiles_and_evidence',
            fusion='fusion__by_pool_k',same_room='same_room__consumer_pair_summary',time='statistics__record_lookup'),
        navigation={m:dict(questions=qs,**(dict(title='人员画像 · Q / T 与可靠性',
            desc='连续任务调整Q、绝对Q、时间和带机会分母的可靠性并列；主观候选不升级为严重失误率。')
            if m=='workers' else {})) for m,qs in questions.items()}))


def build_revision():
    with tempfile.TemporaryDirectory(prefix='statistics-v1-r2-') as temporary:
        source = Path(temporary)
        manifest = extract_snapshot(source)
        fusion = source/'research/fusion/wall_consensus_v1_process_20261017'
        room_source = source/'research/same_room/same_room_v1_process_20261017'
        person_source = source/'research/workers/worker_v1_composition_20261017'
        pro_source = source/'research/workers/worker_v1_pro_integration_20261017'
        prep = read(OUT/'PREPARATION.json')
        assert digest(OLD/'inputs/fusion_states.csv') == prep['r1_sha256']
        old = pd.read_csv(OLD/'inputs/fusion_states.csv', low_memory=False)
        current = pd.read_csv(fusion/'trajectory_scores.csv', low_memory=False)
        fields, added = reconcile_states(old, current)
        assert len(old) == 41323 and len(current) == 41859 and len(added) == 536
        status = read(fusion/'STATUS.json')
        assert status['path_states'] == len(current)
        losses = pd.read_csv(OUT/'auxiliary_loss_before_repair.csv')
        indexed = current.set_index(KEY)
        losses['current_value'] = np.nan
        for field, group in losses.groupby('field'):
            values = indexed.loc[pd.MultiIndex.from_frame(group[KEY]), field].to_numpy()
            assert np.isclose(values, group.r1_value, rtol=1e-12, atol=1e-12).all()
            losses.loc[group.index, 'current_value'] = values
        losses['restored_from_complete_measurement_cache'] = True
        inventory = pd.read_csv(source/'research/statistics/b8l2_d10_statistics_20261017/record_lookup.csv', low_memory=False)
        shared = pd.read_csv(source/'research/quality/quality_b8l2_d10_20261017/shared_records.csv', low_memory=False)
        assert inventory.object_id.is_unique and shared.object_id.is_unique
        a, b = inventory.set_index('object_id'), shared.set_index('object_id')
        assert set(a.index) == set(b.index)
        b = b.loc[a.index]
        for column in ['worker_id','image_id','quality_usable','B8L2','D10']:
            assert equal_values(a[column],b[column]).all(), column
        assert len(inventory) == 3222 and inventory.quality_usable.sum() == 1911
        assert inventory.B8L2.notna().equals(inventory.D10.notna())
        room, room_meta = room_tables(room_source)
        consumer = pd.read_csv(room_source/'consumer_prefixes.csv')
        consumer_pairs = pd.read_csv(room_source/'consumer_pair_summary.csv')
        room_checks = validate_room_consumer(consumer, consumer_pairs, current)
        room_interface = read(room_source/'CONSUMER_INTERFACE.json')
        assert room_interface['status'] == 'ready_for_statistics'
        assert room_interface['producer_analysis_revision'] == read(fusion/'CURRENT.json')['analysis_revision']
        endpoints = pd.read_csv(OLD/'same_room_endpoint_integration.csv')
        endpoint_status = endpoint_process_status(endpoints,
            pd.read_csv(room_source/'selected_process_panel.csv'), consumer)
        assert endpoint_status.pair_process_received.sum() == 9 and len(endpoint_status) == 217
        person_checks = validate_person_links(pd.read_csv(person_source/'statistics_person_evidence.csv'),
            pd.read_csv(person_source/'statistics_record_profiles.csv'), inventory)
        pro_checks = validate_person_pro(pro_source,person_source,inventory,fusion)
        difficulty_checks = validate_difficulty_process(
            source/'research/difficulty/difficulty_v1_analysis_20261017',fusion,current)
        checks = dict(data_release='v1',analysis_revision=REVISION,
            upstream_ready=True,consumer_complete=True,inventory=len(inventory),quality_rows=int(inventory.quality_usable.sum()),
            r1_states=len(old),current_states=len(current),added_same_room_states=len(added),
            core_old_fields_preserved=True,all_15_auxiliary_fields_preserved=True,
            auxiliary_loss_cells_restored=len(losses),
            same_room=room_checks,same_room_paired=room_meta,person_links=person_checks,
            personnel_pro=pro_checks,difficulty=difficulty_checks,
            endpoint_candidate_pairs=len(endpoint_status),endpoint_pairs_with_real_process=int(endpoint_status.pair_process_received.sum()),
            source_snapshot_id=manifest['snapshot_id'],source_archive_sha256=manifest['archive_sha256'],
            new_geometry_executed=False,raw_inputs_references_eligibility_changed=False)
        derived = dict(room, same_room_endpoint_integration=endpoint_status,
            auxiliary_restoration_ledger=losses, process_field_reconciliation=fields)
        overview = make_overview(source, room, checks)
        index = publish_explorer(source, manifest, derived, overview)
        checks['explorer_tables'] = index['table_count']
        checks['explorer_stored_rows'] = index['total_row_count']
        write(OUT/'CHECKS.json', json_ready(checks))
        write(OUT/'FIELD_CONTRACT.json', dict(data_release='v1',analysis_revision=REVISION,
            tables={name:dict(rows=len(frame),columns=frame.columns.tolist()) for name,frame in derived.items()},
            rules=dict(state_key=KEY,room_primary='comparison_B8L2/comparison_D10; both sides use strict pair masks',
                endpoint_process='module completion does not imply pair coverage; join by actual request ID',
                missing='null is not zero; source and target times separate',
                inheritance='unchanged r1 tables are referenced and source-hashed; old 195-table bundle is separate')))
        write(EXPLORER/'VERIFICATION.json', dict(data_release='v1',snapshot_id=REVISION,
            build_complete=True,tables=index['table_count'],sources=len(manifest['files']),
            missing_values_preserved=True,old_fixed_data_overwritten=False,
            real_browser_checked=False,local_only=True))
        write(OUT/'CONSUMER_INTERFACE.json', dict(schema='statistics_v1_r2_consumer_v1',
            data_release='v1',analysis_revision=REVISION,status='consumed_and_validated',
            machine_checks='CHECKS.json',source_manifest='SOURCE_MANIFEST.json',source_archive='SNAPSHOT.zip',
            explorer='../research_explorer_v1_r2_20261017/index.html',
            handoff='HANDOFF.md',dependencies='DEPENDENCIES.json',
            visual_verification='../research_explorer_v1_r2_20261017/VERIFICATION.json',
            tables={name:name+'.csv' for name in derived},
            inherited_r1_tables=[e['path'] for e in manifest['files'] if e['module']=='integrated' and e['kind']=='table'],
            human_decisions_required=[],
            conditional_attribution_cases=read(pro_source/'HUMAN_REVIEW_CASES.json')['cases']))
        dependencies = []
        for module, path, name in [
            ('fusion',fusion,'CURRENT.json'),
            ('same_room',room_source,'CONSUMER_INTERFACE.json'),
            ('difficulty',source/'research/difficulty/difficulty_v1_analysis_20261017','CROSS_MODULE_INPUTS.json'),
            ('workers',pro_source,'CROSS_MODULE_INPUTS.json')]:
            metadata = read(path/name)
            dependencies.append(dict(module=module,upstream_complete=True,consumer_complete=True,
                snapshot_id=REVISION,source_interface=(path/name).relative_to(source).as_posix(),
                source_interface_sha256=digest(path/name),source_metadata=metadata))
        write(OUT/'DEPENDENCIES.json', dependencies)
        return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit-before-repair', action='store_true')
    parser.add_argument('--capture-ready-sources', action='store_true',
        help='仅在统筹明确全部上游接口就绪后使用；捕获后执行构建')
    parser.add_argument('--build', action='store_true', help='从已捕获快照重放；显示输出目录须为空')
    parser.add_argument('--local-data-only', action='store_true', help='仅从现有消费JSON生成双击HTML所需分片，不重跑统计')
    args = parser.parse_args()
    if args.local_data_only:
        print(f'local data files: {publish_local_data(EXPLORER/"explorer-data")}')
    elif args.audit_before_repair:
        audit_before_repair()
    elif args.capture_ready_sources:
        capture_sources(selected_sources(), sources_ready=True)
        print(json.dumps(json_ready(build_revision()), ensure_ascii=False))
    elif args.build:
        print(json.dumps(json_ready(build_revision()), ensure_ascii=False))
    else:
        parser.error('最终捕获等待统筹明确源就绪；当前可运行 --audit-before-repair')


if __name__ == '__main__':
    main()
