"""用途版本的全库存覆盖计数；不改资格，不汇总OOS诊断分数均值。"""
import pandas as pd

CALCULATION_STATUSES = ('full_computed', 'floor_only_computed', 'input_uncomputable',
                        'pending_target', 'pending_reference', 'measurement_failed', 'not_run')
FULL_SCORE_STATES = ('computed', 'input_uncomputable', 'pending_target', 'pending_reference',
                     'measurement_failed', 'not_run')
SCENE_BUCKETS = ('doorway_only', 'oos_only', 'both', 'neither_flagged')


def scene_flags(row):
    """只读图片场景/门洞/OOS轴；来源condition=oos不代替场景事实。"""
    doorway = ('doorway' in row['scene'] or row['doorway_status'] in
               ('annotatable', 'difficult', 'suspected_user_review'))
    oos = ('oos' in row['scene'] or row['oos_subtype'] in
           ('nonorthogonal_annotatable', 'subtype_not_resolved', 'suspected_user_review'))
    return dict(is_doorway=doorway, is_oos=oos,
                scene_bucket='both' if doorway and oos else 'doorway_only' if doorway else
                             'oos_only' if oos else 'neither_flagged',
                worker_unmarkable_choice='unknown_not_independently_recorded')


PRIMARY_REASON_ORDER = (
    'old_cleaning_excluded', 'cleaning_pending', 'independent_response_ineligible',
    'source_pool_below3', 'gt_error', 'target_unresolved', 'reference_unavailable',
    'full_input_unavailable', 'oos_diagnostic_only', 'other_quality_restriction',
    'measurement_failed', 'not_run', 'floor_only_no_full_score', 'calculated_not_usable',
    'quality_usable',
)


def _counts(frame):
    """只计数；诊断数值不能被此入口汇总为质量均值。"""
    n = len(frame)
    values = dict(n_submissions=n, n_workers=frame.worker_id.nunique(), n_images=frame.image_id.nunique(),
                  n_quality_usable=int(frame.quality_usable.sum()),
                  n_full_diagnostic_available=int(frame.diagnostic_B8L2.notna().sum()),
                  n_computed_not_quality_usable=int((frame.calculation_status.isin(
                      ['full_computed', 'floor_only_computed']) & ~frame.quality_usable).sum()),
                  n_oos_submissions=int(frame.is_oos.sum()),
                  n_source_condition_oos=int(frame.condition.eq('oos').sum()),
                  n_oos_full_diagnostic=int((frame.is_oos & frame.diagnostic_B8L2.notna()).sum()),
                  n_full_computable_inputs=int((frame.full_input_available &
                      frame.reference_full_available & frame.target_binding_unique).sum()))
    for status in CALCULATION_STATUSES:
        values['n_' + status] = int(frame.calculation_status.eq(status).sum())
    for state in FULL_SCORE_STATES:
        values['n_full_score_' + state] = int(frame.full_score_state.eq(state).sum())
    for reason in PRIMARY_REASON_ORDER:
        if 'hit_' + reason in frame:
            values['n_' + reason] = int(frame['hit_' + reason].sum())
    ref = frame[['hit_gt_error', 'hit_target_unresolved', 'hit_reference_unavailable']].any(axis=1)
    values['n_gt_or_reference_unresolved'] = int(ref.sum())
    values.update({'ratio_' + key[2:]: value/n if n else None for key, value in list(values.items())
                   if key.startswith('n_') and key not in ('n_submissions', 'n_workers', 'n_images')})
    return values


def _summary(frame, dimensions):
    result = []
    groups = frame.groupby(dimensions, sort=True, dropna=False) if dimensions else [((), frame)]
    for key, cell in groups:
        key = key if isinstance(key, tuple) else (key,)
        result.append(dict(zip(dimensions, key), **_counts(cell)))
    return pd.DataFrame(result)


def build_usage_coverage(records):
    """全库存覆盖，不过滤未分析人员；返回7张DataFrame，由主线程落盘。

    主原因按PRIMARY_REASON_ORDER唯一分配；多原因表另列语义hit和原始reason。
    所有ratio均以该表切片的原提交数为分母。condition为来源条件，非场景轴。
    quality_exclusion_reasons必须为已解析list，布尔门必须为bool。
    """
    frame = records.copy()
    required = ['object_id', 'worker_id', 'image_id', 'condition', 'cleaning_disposition',
        'independent_vote_eligible', 'pool_source_workers', 'gt_error_excluded', 'is_doorway', 'is_oos',
        'quality_usable', 'quality_exclusion_reasons', 'diagnostic_B8L2', 'calculation_status',
        'full_score_state', 'full_input_available', 'floor_input_available', 'reference_full_available',
        'target_binding_unique']
    missing = set(required)-set(frame)
    if missing:
        raise ValueError(f'usage coverage missing fields: {sorted(missing)}')
    if frame.object_id.duplicated().any():
        raise ValueError('duplicate object_id in usage coverage')
    if not frame.calculation_status.isin(CALCULATION_STATUSES).all():
        raise ValueError('unknown calculation_status')
    if not frame.full_score_state.isin(FULL_SCORE_STATES).all():
        raise ValueError('unknown full_score_state')
    if not frame.quality_exclusion_reasons.map(lambda x: isinstance(x, list)).all():
        raise ValueError('quality_exclusion_reasons must be parsed lists')
    if (frame.is_oos & frame.quality_usable).any():
        raise ValueError('OOS diagnostic measurements cannot be quality_usable')
    frame['scene_bucket'] = ['both' if door and oos else 'doorway_only' if door else
        'oos_only' if oos else 'neither_flagged' for door, oos in zip(frame.is_doorway, frame.is_oos)]
    frame['source_condition_oos'] = frame.condition.eq('oos')
    frame['hit_old_cleaning_excluded'] = frame.cleaning_disposition.isin(
        ['historical_not_accepted', 'excluded_by_review'])
    frame['hit_cleaning_pending'] = frame.cleaning_disposition.eq('retained_pending')
    frame['hit_independent_response_ineligible'] = ~frame.independent_vote_eligible
    frame['hit_source_pool_below3'] = frame.pool_source_workers.lt(3)
    frame['hit_gt_error'] = frame.gt_error_excluded
    explicit_target_holds = {'current_image_issue_pending', 'legacy:same_target_quality_hold',
                            'legacy:latest_step_reference_pending', 'legacy:original_holdout',
                            'legacy:same_target_unconfirmed'}
    frame['hit_target_unresolved'] = (~frame.target_binding_unique |
        frame.calculation_status.eq('pending_target') | frame.quality_exclusion_reasons.map(
            lambda reasons: bool(set(reasons) & explicit_target_holds)))
    frame['hit_reference_unavailable'] = (~frame.reference_full_available |
                                          frame.calculation_status.eq('pending_reference'))
    frame['hit_full_input_unavailable'] = (~frame.full_input_available |
                                          frame.calculation_status.eq('input_uncomputable'))
    frame['hit_oos_diagnostic_only'] = frame.is_oos
    existing_hits = [c for c in frame if c.startswith('hit_')]
    frame['hit_other_quality_restriction'] = (~frame.quality_usable &
        frame.quality_exclusion_reasons.map(bool) & ~frame[existing_hits].any(axis=1))
    frame['hit_measurement_failed'] = frame.calculation_status.eq('measurement_failed')
    frame['hit_not_run'] = frame.calculation_status.eq('not_run')
    frame['hit_floor_only_no_full_score'] = frame.calculation_status.eq('floor_only_computed')
    frame['hit_calculated_not_usable'] = frame.calculation_status.eq('full_computed') & ~frame.quality_usable
    frame['hit_quality_usable'] = frame.quality_usable
    frame['primary_reason'] = [next(reason for reason in PRIMARY_REASON_ORDER if row['hit_' + reason])
                               for row in frame.to_dict('records')]
    primary, hits, statuses = [], [], []
    for worker, cell in frame.groupby('worker_id', sort=True):
        for reason in PRIMARY_REASON_ORDER:
            n = int(cell.primary_reason.eq(reason).sum())
            primary.append(dict(worker_id=worker, primary_reason=reason, n_records=n,
                                n_submissions=len(cell), ratio=n/len(cell)))
            hit_n = int(cell['hit_' + reason].sum())
            if hit_n and reason != 'quality_usable':
                hits.append(dict(worker_id=worker, reason_kind='semantic_hit', reason=reason,
                                 n_records=hit_n, n_submissions=len(cell), ratio=hit_n/len(cell)))
        raw_reasons = sorted({reason for reasons in cell.quality_exclusion_reasons for reason in reasons})
        for reason in raw_reasons:
            n = int(cell.quality_exclusion_reasons.map(lambda values: reason in values).sum())
            hits.append(dict(worker_id=worker, reason_kind='raw_quality_exclusion', reason=reason,
                             n_records=n, n_submissions=len(cell), ratio=n/len(cell)))
        for condition, part in cell.groupby('condition', sort=True):
            for status in CALCULATION_STATUSES:
                n = int(part.calculation_status.eq(status).sum())
                statuses.append(dict(worker_id=worker, condition=condition, calculation_status=status,
                    n_records=n, n_submissions=len(part), ratio=n/len(part)))
    assert sum(r['n_records'] for r in primary) == len(frame)
    return dict(record_reason_audit=frame, worker_usage_summary=_summary(frame, ['worker_id']),
        worker_primary_reasons=pd.DataFrame(primary), worker_reason_hits=pd.DataFrame(hits),
        worker_scene_usage=_summary(frame, ['worker_id', 'condition', 'scene_bucket']),
        scene_usage=_summary(frame, ['condition', 'scene_bucket']),
        worker_calculation_status=pd.DataFrame(statuses))
