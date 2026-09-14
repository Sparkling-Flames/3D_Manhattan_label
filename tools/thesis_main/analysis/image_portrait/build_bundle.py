"""Build the nonvisual portrait bundle; verify cached facts against their sources."""
import argparse
import csv
import gzip
import json
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'analysis_results/image_portrait_20260914_v1'
SCENE = 'analysis_results/scene_image_exploration_20260910_v1/'
SPATIAL = 'analysis_results/spatial_dimensions_review_20260913_v2/空间描述与历轮人工记录.json'
VIEW = 'analysis_results/confirmed_point_calculation_view_20260909_v1/reviewed/calculation_view.jsonl.gz'
EVIDENCE = 'analysis_results/annotation_research_prework_20260905_v2/evidence/record_evidence.csv'
FACTS = 'analysis_results/uncertainty_cloud_inputs_20260906_v1/facts/'
BAD_GT = 'zsNo4HB9uLZ_4c0aab63a4434cf4878e6f5b3ce9a70b'
SEED = 20260914


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def rows(path):
    path = Path(path)
    with (gzip.open(path, 'rt', encoding='utf-8-sig') if path.suffix == '.gz'
          else path.open(encoding='utf-8-sig')) as stream:
        return list(csv.DictReader(stream)) if '.csv' in path.name else [json.loads(s) for s in stream if s.strip()]


def write(path, value, lines=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = ('\n'.join(json.dumps(v, ensure_ascii=False, allow_nan=False) for v in value) + '\n'
            if lines else json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n')
    if path.suffix == '.gz':
        # Fixed gzip timestamp makes repeated source checks leave identical artifacts.
        path.write_bytes(gzip.compress(text.encode('utf-8'), mtime=0))
    else:
        path.write_text(text, encoding='utf-8', newline='\n')


def unique(records, key):
    index = {r[key]: r for r in records}
    if len(index) != len(records) or not all(index):
        raise ValueError('Missing or duplicate identity: ' + key)
    return index


def worker(value):
    return f'W{int(str(value).removeprefix("W")):03d}'


def clean(value):
    """Retain provenance, remove byte digests and normalize person identifiers."""
    if isinstance(value, list):
        return [clean(x) for x in value]
    if not isinstance(value, dict):
        return value
    return {k: (worker(v) if k in {'worker_id', 'raw_worker_id', 'annotator_id'} and v else clean(v))
            for k, v in value.items() if not k.endswith(('_sha256', '_hash'))}


def components(ids, groups):
    parent = {i: i for i in ids}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for group in groups:
        members = group['image_ids']
        for member in members:
            if member not in parent:
                raise ValueError('Unknown relationship image: ' + member)
        for member in members[1:]:
            parent[find(member)] = find(members[0])
    result = defaultdict(list)
    for image_id in sorted(ids):
        result[find(image_id)].append(image_id)
    return list(result.values())


def make_folds(images, groups):
    by_id = unique(images, 'image_id')
    supported = [g for g in groups if g['relation_status'] == 'supported']
    uncertain = {i for g in groups if g['relation_status'] != 'supported' for i in g['image_ids']}
    supported_ids = {i for g in supported for i in g['image_ids']}
    rooms, folds = [], []
    rng = random.Random(SEED)
    buildings = sorted({r['building'] for r in images})
    rng.shuffle(buildings)
    for building in buildings:
        test = sorted(i for i in by_id if by_id[i]['building'] == building)
        folds.append(dict(fold_id='building:' + building, design='leave_building',
                          train=sorted(set(by_id) - set(test)), test=test, excluded=[]))
    for members in components(by_id, supported):
        if len(members) < 2 or not set(members) <= supported_ids:
            continue
        room_id = 'supported_component:' + members[0]
        blocked = bool(set(members) & uncertain)
        rooms.append(dict(room_id=room_id, image_ids=members,
                          status='overlap_with_pending_or_unsupported' if blocked else 'supported_component',
                          physical_room_census=False))
        if blocked:
            continue
        building_set = {by_id[i]['building'] for i in members}
        if len(building_set) != 1:
            raise ValueError('Supported same-room links cross buildings')
        order = members[:]
        rng.shuffle(order)
        for image_id in order:
            folds.append(dict(fold_id='view:' + image_id, design='same_room_leave_view',
                              room_id=room_id, train=sorted(set(members)-{image_id}), test=[image_id],
                              excluded=sorted(set(by_id)-set(members))))
        # Other views in this building may be unrecognized same-room images.
        # Exclude them rather than silently declaring separate display groups distinct rooms.
        train = sorted(i for i in by_id if by_id[i]['building'] not in building_set)
        folds.append(dict(fold_id='room:' + room_id, design='leave_supported_room_conservative',
                          room_id=room_id, train=train, test=members,
                          excluded=sorted(set(by_id)-set(train)-set(members))))
    validate_folds(images, folds)
    return rooms, folds


def validate_folds(images, folds):
    by_id = unique(images, 'image_id')
    unique(folds, 'fold_id')
    for f in folds:
        train, test, excluded = (set(f[k]) for k in ('train', 'test', 'excluded'))
        if not train or not test or train & test or train & excluded or test & excluded:
            raise ValueError('Empty or overlapping fold: ' + f['fold_id'])
        if train | test | excluded != set(by_id):
            raise ValueError('Fold inventory mismatch')
        if f['design'] != 'same_room_leave_view':
            if {by_id[i]['building'] for i in train} & {by_id[i]['building'] for i in test}:
                raise ValueError('Potential unknown-room leakage')


def verify_bundle(out=OUT):
    """Cloud-side check: reads bundle only, without images or source exports."""
    images = rows(out / 'metadata/images.jsonl')
    ids = unique(images, 'image_id')
    responses = rows(out / 'human/responses.jsonl.gz')
    canonical = unique(responses, 'canonical_annotation_id')
    if len(ids) != 648 or len(canonical) != 2501:
        raise ValueError('Snapshot count drift')
    for r in responses:
        if r['image_id'] not in ids or r['main_worker_included'] != (r['worker_id'] not in {'W019','W026'}):
            raise ValueError('Response identity or worker eligibility drift')
        if r['raw_point_count'] != len(r['raw_points_1024x512']):
            raise ValueError('Raw point count drift')
    for r in rows(out / 'human/semi_initializations.jsonl.gz'):
        c = canonical[r['canonical_annotation_id']]
        if (c['image_id'], c['worker_id']) != (r['image_id'], r['worker_id']):
            raise ValueError('Semi identity drift')
        if r['trace']['initial_import_match_status'] != 'all_matching':
            raise ValueError('Unverified Semi initialization')
    if set(unique(rows(out / 'human/time_source_checks.jsonl'), 'canonical_annotation_id')) != set(canonical):
        raise ValueError('Time coverage drift')
    refs = unique(rows(out / 'human/references.jsonl.gz'), 'image_id')
    if set(refs) != set(ids) or refs[BAD_GT]['current_quality_status'] != 'not_evaluable_bad_gt':
        raise ValueError('Reference coverage/policy drift')
    validate_folds(images, rows(out / 'evaluation/folds.jsonl.gz'))
    return dict(status='passed', images=len(ids), responses=len(canonical), original_images_required=False)


def build_history(out=OUT):
    """Export verified historical candidates, never rename another risk score d_t."""
    import numpy as np
    from tools.thesis_main.analysis.materialize_c2_task_risk import _apply_whitener, _knn
    dest = out / 'history'
    dest.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'analysis_results/research_validation_20260909_v2/features'
    cache = ROOT / 'analysis_results/c2b_validation_static_20260802_v16/static/c2_feature_reference_cache.npz'
    features = np.load(source / 'image_features.npz', allow_pickle=False)
    reference = np.load(cache, allow_pickle=False)
    archived = unique(rows(source / 'image_feature_audit.csv'), 'image_id')
    measurements, max_delta = [], 0.0
    for index, image_id in enumerate(features['image_ids'].tolist()):
        row = dict(image_id=image_id, source='analysis_results/research_validation_20260909_v2/features/image_feature_audit.csv',
                   historical_only=True, labels_used_for_extraction=False)
        for mode, key in [('global', 'shared'), ('local', 'shared_local')]:
            vector = _apply_whitener(features[key][index], reference[mode+'_mean'], reference[mode+'_components'], reference[mode+'_scale'])
            value = _knn(vector, reference['reference_'+mode])
            column = 'd_model_feat_recomputed' if mode == 'global' else 'd_model_feat_local_recomputed'
            delta = abs(value - float(archived[image_id][column]))
            if not np.isfinite(value) or not np.isclose(value, float(archived[image_id][column]), rtol=1e-4, atol=1e-5):
                raise ValueError('Historical feature distance no longer reproduces')
            max_delta = max(max_delta, delta)
            row[column] = float(archived[image_id][column])
            row[column+'_current_cpu_check'] = value
            row[column+'_absolute_delta'] = delta
        measurements.append(row)
    write(dest / 'd_model_feat.jsonl', measurements, True)
    shutil.copyfile(source / 'image_features.npz', dest / 'historical_image_features.npz')
    shutil.copyfile(cache, dest / 'historical_feature_reference.npz')
    feature_plan = read(source / 'FEATURE_PLAN.json')
    for k in ('checkpoint', 'config'):
        feature_plan[k] = Path(feature_plan[k]).relative_to(ROOT).as_posix()
    write(dest / 'historical_feature_plan.json', feature_plan)
    write(dest / 'legacy_dt_rule.json', read(ROOT / 'analysis_results/c_manifests_20260310/embedding_ood_protocol_v1.json'))
    base = ROOT / 'analysis_results/worker_four_block_exploration_20260910_v1'
    plan = read(base / 'PLAN.json')
    extension = read(base / 'group_count_extension/PLAN_AND_QA.json')
    if len(plan['combinations']) != 15 or extension['information_combinations'] != 15:
        raise ValueError('Worker candidate contract drift')
    write(dest / 'worker_candidate_plan.json', dict(historical=plan, group_count_extension=extension,
        current_group_count_rule='2 through floor(training-qualified workers/2); retain singleton groups, no forced balance',
        additional_candidate={'name': 'quality_time_edit', 'axes': ['quality', 'time', 'edit']},
        current_worker_policy='Retain W011 history; exclude W019/W026 main; old all26/current20 are historical cohorts only',
        reuse_policy='Use historical candidate definitions; refit within current training split. Whole-dataset memberships are descriptive only.'))
    canonical = unique(rows(out / 'human/responses.jsonl.gz'), 'canonical_annotation_id')
    axes = []
    for r in rows(base / 'axes_primary.csv.gz'):
        c = canonical[r['canonical_annotation_id']]
        if c['image_id'] != r['image_id'] or c['worker_id'] != worker(r['worker_id']):
            raise ValueError('Historical worker axis identity mismatch')
        axes.append(dict(clean(r), source='analysis_results/worker_four_block_exploration_20260910_v1/axes_primary.csv.gz',
                         metric_version='historical_ospa30_primary; not new d_mask', main_worker_included=c['main_worker_included']))
    write(dest / 'worker_axes_historical.jsonl.gz', axes, True)
    members = rows(base / 'members.csv')
    write(dest / 'worker_memberships_descriptive_only.jsonl.gz', clean(members), True)
    counts = rows(base / 'group_count_extension/group_counts.csv')
    write(dest / 'worker_group_counts_historical.jsonl', counts, True)
    summary = dict(historical_feature_images=len(measurements), max_distance_recompute_delta=max_delta,
        reference_images=reference['reference_global'].shape[0], worker_axis_rows=len(axes),
        worker_axis_counts=dict(Counter(r['axis'] for r in axes)), historical_membership_rows=len(members),
        group_count_configs=len(counts), group_count_rule='2..floor(eligible_workers/2)',
        legacy_d_t_status='missing_verified_realized_scores_and_calibration_reference_pool',
        legacy_d_t_explanation='Only frozen rule and 214 single-phase mean vectors located; reference manifest still declares blocked_by_runtime_bridge. Do not compute replacement using risk reference or all648.',
        d_model_feat_status='214 archived descriptors reprojected against exact saved 1647-reference cache; both distances reproduce',
        d_model_feat_limits='Historical frozen projection, not PCA fit on current training fold; report separately from train-only PCA comparison. No new inference claimed.',
        worker_axis_limits='Canonical identities verified; historical metrics retained with their original OSPA/reference/time definitions, not silently substituted for current metrics. Fit classes using current training only.',
        geometry_code='tools/thesis_main/analysis/audit_annotation_research_data_20260905.py and imported repository modules are Git-tracked; helper invocation needs numpy and existing dependencies, no image files.')
    write(dest / 'coverage.json', summary)
    return summary


def build(out=OUT):
    from tools.thesis_main.analysis.audit_building_convergence_20260908 import (
        ordered_points, require_same_points, source_annotation_index)
    from tools.thesis_main.data_prep.materialize_annotation_research_prework_evidence_20260905 import initialization_trace
    from tools.thesis_main.analysis.audit_annotation_research_data_20260905 import _load_gt_pairs
    images = [dict(r, source_split=r['split'], inventory_source=SCENE+'inventory.json')
              for r in read(ROOT / SCENE / 'inventory.json')]
    image_map = unique(images, 'image_id')
    if len(images) != 648:
        raise ValueError('Expected 648 classified images')
    for r in images:
        p = (ROOT / r['path']).resolve()
        if not p.is_relative_to(ROOT) or not p.is_file() or p.stem != r['image_id']:
            raise ValueError('Image source mismatch: ' + r['image_id'])
    write(out / 'metadata/images.jsonl', images, True)
    spatial = read(ROOT / SPATIAL)
    if set(unique(spatial['images'], 'image_id')) != set(image_map):
        raise ValueError('Spatial inventory drift')
    feature_rows = [{k: v for k, v in r.items() if k not in {'historical', 'annotation_counts', 'historical_coverage'}}
                    for r in spatial['images']]
    write(out / 'metadata/spatial_history.jsonl.gz', clean(feature_rows), True)
    write(out / 'metadata/spatial_provenance.json', {k: clean(v) for k, v in spatial.items() if k != 'images'})
    groups = []
    for r in read(ROOT / SCENE / 'same_room_selection_registry_v2_20260912.json')['groups']:
        status = {'支持': 'supported', '待定': 'pending', '不支持': 'unsupported'}[r['raw_current']['physical_same']]
        groups.append(dict(review_code=r['review_code'], image_ids=r['image_ids'], building=r['building'],
                           relation_status=status, raw_current=r['raw_current'], review_state=r['review_state'],
                           source_pair_ids=r['source_pair_ids'], source=SCENE+'same_room_selection_registry_v2_20260912.json'))
    write(out / 'metadata/relationships.jsonl', groups, True)
    rooms, folds = make_folds(images, groups)
    write(out / 'evaluation/room_components.jsonl', rooms, True)
    write(out / 'evaluation/folds.jsonl.gz', folds, True)

    evidence = unique(rows(ROOT / EVIDENCE), 'canonical_annotation_id')
    reviewed = rows(ROOT / VIEW)
    if set(unique(reviewed, 'canonical_annotation_id')) != set(evidence):
        raise ValueError('Human evidence coverage drift')
    exports = {p: source_annotation_index(read(ROOT / p)) for p in {r['raw_export_path'] for r in reviewed}}
    proposals = unique(rows(ROOT / FACTS / 'proposal_response.csv.gz'), 'canonical_annotation_id')
    responses, initializations = [], []
    for r in reviewed:
        cid = r['canonical_annotation_id']
        e = evidence[cid]
        for k in ('image_id', 'worker_id', 'annotation_identity', 'raw_export_path'):
            if str(r[k]) != e[k]:
                raise ValueError('Human identity drift: ' + k)
        _, _, task_id, wid, annotation_id = r['raw_annotation_version_id'].split('|')
        task, annotation = exports[r['raw_export_path']][task_id, wid, annotation_id]
        image_id = Path(unquote(urlparse(task['data']['image']).path)).stem
        if image_id != r['image_id'] or image_id not in image_map:
            raise ValueError('Raw image identity mismatch')
        require_same_points(ordered_points(annotation['result']), r['raw_points_1024x512'])
        response = clean(r)
        response.update(main_worker_included=worker(wid) not in {'W019', 'W026'},
                        raw_identity_and_points_verified=True,
                        choices=[{'from_name': x.get('from_name'), 'choices': x['value']['choices']}
                                 for x in annotation['result'] if x.get('type') == 'choices'],
                        evidence={k: clean(v) for k, v in e.items() if k.startswith(('active_time_', 'time_', 'reference_', 'quality_reference', 'lead_time', 'scope_', 'initial_')) and not k.endswith('_sha256')})
        responses.append(response)
        if cid in proposals:
            p = proposals[cid]
            require_same_points(json.loads(p['final_points_json']), r['raw_points_1024x512'])
            trace = initialization_trace(e, task, p)
            if trace['initial_import_match_status'] != 'all_matching':
                raise ValueError('Semi initialization source conflict: ' + cid)
            initializations.append(dict(canonical_annotation_id=cid, image_id=image_id, worker_id=worker(wid),
                initial_points_1024x512=json.loads(p['initial_points_json']), trace=trace,
                initialization_source_kind=e['initialization_source_kind'], reference_type=p['reference_type'],
                source=FACTS+'proposal_response.csv.gz', historical_checkpoint_status='not_bound_to_exact_checkpoint'))
    write(out / 'human/responses.jsonl.gz', responses, True)
    write(out / 'human/semi_initializations.jsonl.gz', initializations, True)
    references = _load_gt_pairs()
    write(out / 'human/references.jsonl.gz', [dict(image_id=i, **references.get(i, {'reference_status': 'missing'}),
          current_quality_status='not_evaluable_bad_gt' if i == BAD_GT else references.get(i, {}).get('reference_status', 'missing'))
          for i in image_map], True)
    # Events are audit evidence, never sums used to replace historical frozen active time.
    events = []
    source_lines = {}
    identities = {(e['project_id'], e['runtime_task_id'], e['worker_id']) for e in evidence.values()}
    for e in rows(ROOT / FACTS / 'active_event_observed.csv.gz'):
        key = (e['project_id'], e['runtime_task_id'], e['annotator_id'])
        if key not in identities:
            continue
        path = e['source_path']
        if path not in source_lines:
            source_lines[path] = (ROOT / path).read_text(encoding='utf-8-sig').splitlines()
        raw = json.loads(source_lines[path][int(e['source_line'])-1])
        if tuple(str(raw.get(k, '')) for k in ('project_id', 'task_id', 'annotator_id')) != key:
            raise ValueError('Active-time raw owner mismatch')
        if str(raw.get('session_id', '')) != e['session_id']:
            raise ValueError('Active-time raw session mismatch')
        if 'active_seconds_fragment' in raw and float(raw['active_seconds_fragment']) != float(e['active_seconds_fragment']):
            raise ValueError('Active-time raw fragment mismatch')
        events.append(clean(e))
    write(out / 'human/active_events_audit.jsonl.gz', events, True)
    event_sources = defaultdict(set)
    for e in events:
        event_sources[e['project_id'], e['runtime_task_id'], e['annotator_id']].add(e['source_path'])
    time_checks = []
    frozen_tables = {}
    for cid, e in evidence.items():
        key = (e['project_id'], e['runtime_task_id'], worker(e['worker_id']))
        expected = [p for p in e['time_active_time_source_file'].split(';') if p]
        matched = bool(expected) and all(any(p == actual or Path(actual).name == p or actual.startswith(p.rstrip('/')+'/')
                                            for actual in event_sources[key]) for p in expected)
        frozen_matched = False
        if e['time_active_time_source'] == 'frozen_c1_task_worker_active_time':
            if len(expected) != 1:
                raise ValueError('Unexpected C1 frozen timing source')
            path = expected[0]
            if path not in frozen_tables:
                frozen_tables[path] = {(r['project_id'], r['runtime_task_id'], worker(r['worker_id'])): r for r in rows(ROOT / path)}
            frozen = frozen_tables[path].get(key)
            if frozen is None or frozen['base_task_id'] != e['image_id']:
                raise ValueError('Frozen timing identity mismatch')
            if e['active_time_seconds'] and float(frozen['task_worker_active_seconds']) != float(e['active_time_seconds']):
                raise ValueError('Frozen active time value mismatch')
            frozen_matched = any(p.startswith('active_logs/c1/') for p in event_sources[key])
            matched = frozen_matched
        status = ('raw_owner_and_source_events_found' if matched else
                  'source_file_mismatch' if event_sources[key] and expected else 'missing_matching_raw_owner_events')
        if frozen_matched:
            status = 'frozen_C1_identity_and_value_verified_with_raw_owner_events'
        time_checks.append(dict(canonical_annotation_id=cid, worker_id=worker(e['worker_id']),
                               historical_time_status=e['active_time_owner_valid_status'], raw_trace_status=status,
                               historical_source_files=expected, verified_owner_source_files=sorted(event_sources[key]),
                               cross_collection_events_present=frozen_matched and any(not p.startswith('active_logs/c1/') for p in event_sources[key]),
                               speed_usable=e['active_time_owner_valid_status'].startswith('owner_valid_complete') and matched))
    write(out / 'human/time_source_checks.jsonl', time_checks, True)
    config = dict(schema='image_portrait_exploration_v1', seed=SEED, frozen_visual_models=True,
        model_candidates={'knn_k': [1, 3, 5], 'ridge_alpha': [0.1, 1, 10, 100], 'pca_components': [None, 16, 32]},
        preprocessing='Fit standardization and PCA within each inner training fold only; cap PCA at min(n_train-1,n_features).',
        inner_validation='Leave-building inside outer training; same-room small folds use fixed ridge alpha=10, k=1 and PCA=None without tuning.',
        selection='Minimize image-macro MAE on inner folds; ties choose PCA=None first, then smaller finite PCA dimension, then larger ridge alpha/smaller k; never use outer outcomes.',
        endpoints=['reference_geometry_error', 'owner_valid_active_seconds', 'point_count_disagreement', 'within_topology_geometry_dispersion', 'scope_choice_distribution'],
        quality='Use references with explicit source and scope; exclude missing, not-geometry-ready and known bad GT. Public reference is not assumed adjudicated.',
        time='Use time_source_checks.speed_usable; never replace with lead_time or sum audit events.',
        clustering='Point counts separate; supported cluster requires two distinct workers; q=.95 remains exploration, final convergence not frozen.',
        denominators='Manual/Semi separate; W019/W026 excluded main, W011 history retained; failures and missing separate; macro images then rooms/buildings.',
        room_policy='Supported connected components are analysis units, not a complete independent-room census. Pending/unsupported overlap excluded from room/view folds. All same-building nonmembers excluded from cross-room training because unknown same-room links may remain.',
        evaluation='Report same-coverage paired comparisons and all-available coverage; outer image MAE and building/room macro MAE, rank correlation secondary; no annotation-level independent significance claims.',
        semi='Verified planned payload, not proof of participant view event; historical checkpoint remains unknown.',
        missing='No imputation of targets or empty geometries; exclude missing predictors per candidate with explicit coverage; no-image cloud uses bundled arrays only.')
    write(out / 'evaluation/config.json', config)
    (out / 'evaluation/metrics.md').write_text('''# 探索评价口径 v1

本合同只约束本图片画像探索，不替代正式 Paper A 合同。seed=20260914。

- 身份：以 image_id 关联，canonical_annotation_id 标记真实作答。同人同图多条件分开；重复版本不增加独立人数。
- 几何：raw_points 保留原点序；effective_points 是已确认派生视图。主计算报告 reviewed 与不使用 imputed_point 两种覆盖。奇数点不能自动修复；无效和空响应单列。
- 参考质量：复用 tools/thesis_main/analysis/audit_annotation_research_data_20260905.py 的 normalize_geometry、_dense_boundaries、_d_mask；d_mask=1-布局区域交并比，越低越接近参考。解析失败记不可计算。公共数据参考不是人工最终真值，单列来源；reference_not_geometry_ready、missing 和已知坏 GT 不计算质量。
- 结构分歧：同图同条件不同人员之间点数不一致的配对比例；分母仅结构可计算人员对，另报失败比例。点数不同不得进入同一几何簇。
- 簇内波动：先按有效点数分层，计算不同人员对 d_mask 的中位数及各层人数；不把跨点数配对混入。当前名称是 within_topology_geometry_dispersion，不据此宣称最终收敛。
- 范围选择：以 choices 中实际 Scope 字段的类别频数/比例描述，未知或缺失单列；不把少数类别编码成错误。规则正确性必须有独立适用参考。
- 时间：仅 time_source_checks.speed_usable=true 且 main_worker_included=true；目标按图同条件取人员有效秒数中位数，同时报告样本数。lead_time 永不替代 active_time；原始事件仅追溯、不求和回填。
- 预测：每目标独立训练并报告图级 MAE、房/楼宏平均 MAE；Spearman 为次要描述。总体历史常数预测用训练图目标中位数；场景基线用同类训练图目标中位数，未见类型用总体训练中位数并标记。
- 模型选择：采用 config.json 候选；每次外层训练内部再按楼划分选择。PCA/标准化只能在内层训练侧拟合。PCA=None 表示不降维；同分优先更少变换（None）、较小有限维数、较大 ridge alpha、较小 k。训练不足或目标常数明确报告，不补造分数。
- 同房 leave-view 仅用该支持组其他图作为历史依据；人员分型使用组外资料，不能用目标图。没有足够内部组时固定 ridge alpha=10、k=1、PCA=None，不能偷看目标选参。
- 统计单位：648图是输入覆盖，214图有历史响应；条件分别算。统一比较先在候选共同可评价图上配对，再各报全部覆盖。重排和抽人均不增加独立样本。
- 房间：room_components 是支持关系连通分量，绝非完整物理房间普查。待定/不支持重叠整组件不进入同房评价；保守跨房训练排除目标楼所有其他图，因此不能把该结果说成纯同楼跨房泛化。
- 收敛：最终判据未冻结；本包不新增终点人数标签。q=.95 等历史值只作带版本敏感性，不据结果筛阈值。
''', encoding='utf-8')
    summary = dict(images=len(images), buildings=len({r['building'] for r in images}), responses=len(responses),
        human_images=len({r['image_id'] for r in responses}), workers=len({r['worker_id'] for r in responses}),
        raw_exports_verified=len(exports), semi_initializations=len(initializations),
        raw_active_events_verified=len(events), speed_usable=sum(r['speed_usable'] for r in time_checks),
        relationships=dict(Counter(g['relation_status'] for g in groups)), room_components=dict(Counter(r['status'] for r in rooms)),
        folds=dict(Counter(f['design'] for f in folds)), sources=[SCENE+'inventory.json', SPATIAL, VIEW, EVIDENCE, FACTS],
        limits=['No new visual ratings in this bundle; historical human and AI provenance retained separately.',
                'Same-building unknown relationships excluded conservatively; room evaluation overlaps building exclusion policy.',
                'Active time frozen historical totals retained; raw event provenance checked, totals not recomputed.',
                'Known bad GT unusable for quality; model source GT independence must be examined.'])
    write(out / 'evaluation/coverage.json', summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--check', action='store_true', help='Check only bundled numerical files; cloud-safe')
    parser.add_argument('--history', action='store_true', help='Build historical feature/worker candidate supplement only')
    args = parser.parse_args()
    print(json.dumps(verify_bundle(args.output) if args.check else build_history(args.output) if args.history else build(args.output), ensure_ascii=False, indent=2))
