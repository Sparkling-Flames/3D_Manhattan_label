"""当前图片来源池人数门：有效作答人数、图级暂停和普通难度资格分别保留。"""
from collections import Counter, defaultdict

CONDITIONS = ('manual', 'semi', 'oos')
RULE_VERSION = 'retained_independent_humans_by_image_condition_min3_20261015_v1'
RULE = ('仅annotation且cleaning_disposition=retained、independent_vote_eligible=true，'
        '既有作答excluded门不纳入；同image_id/condition按worker_id去重。'
        '图级GT/范围/既有暂停不抹去真实人数；人数>=3仍须图级门及各指标参考/时间资格。'
        '本门不读取质量分数，不修改合格来源池内k=1/2轨迹。')
IMAGE_CONSENSUS_HOLDS = {'hold_all_analysis', 'hold_main_analysis', 'inner_space_only_reference_hold'}
IMAGE_QUALITY_HOLDS = {'hold_all_analysis', 'hold_main_analysis', 'hold_reference_quality'}


def build_pool_gate(bundle, difficulty_records):
    """返回(source_pool, record_gate)两个list[dict]；图级门不是正式资格授予。

    source_pool覆盖难度入口每图×manual/semi/oos，包括零人池；纯GT图不建池。
    record_gate仅包含annotation，按object_id连接；重复提交只贡献一名人员。
    图级暂停从当前全部作答门及research.images继承，不限于新版难度排除表。
    """
    difficulty = {row['image_id']: row for row in difficulty_records}
    if len(difficulty) != len(difficulty_records):
        raise ValueError('duplicate difficulty image_id')
    images = {row['image_id']: row for row in bundle['data']['images']}
    research_images = {row['image_id']: row for row in bundle['research']['images']}
    if not set(difficulty) <= set(images):
        raise ValueError('difficulty image absent from current bundle')
    grouped, records, holds = defaultdict(list), [], defaultdict(dict)
    seen = set()
    for obj in bundle['data']['objects']:
        if obj['object_kind'] != 'annotation':
            continue
        oid, image, worker, condition = (obj[k] for k in ('object_id', 'image_id', 'worker_id', 'condition'))
        if oid in seen or not oid or not worker:
            raise ValueError('duplicate/empty annotation object_id or worker_id')
        seen.add(oid)
        if image not in difficulty or condition not in CONDITIONS:
            raise ValueError('annotation image/condition outside declared source pools')
        reasons = []
        if obj['cleaning_disposition'] != 'retained':
            reasons.append('cleaning:' + obj['cleaning_disposition'])
        if not obj['independent_vote_eligible']:
            reasons.extend('independent:' + reason for reason in obj['independent_vote_reasons'])
            if not obj['independent_vote_reasons']:
                reasons.append('independent_vote_ineligible')
        for field, image_holds in [('main_consensus_gate', IMAGE_CONSENSUS_HOLDS),
                                   ('main_quality_gate', IMAGE_QUALITY_HOLDS)]:
            gate = obj[field]
            if gate['status'] == 'excluded':
                reasons.append(field + ':excluded')
            if gate['status'] in image_holds:
                key = (field, gate['status'])
                evidence = holds[image].setdefault(key, dict(source_field=field, status=gate['status'],
                                                            source_object_ids=[], source_reasons=[]))
                evidence['source_object_ids'].append(oid)
                evidence['source_reasons'] = sorted(set(evidence['source_reasons']) | set(gate['reasons']))
        row = dict(object_id=oid, image_id=image, condition=condition, worker_id=worker,
                   pool_rule_version=RULE_VERSION, pool_vote_eligible=not reasons,
                   pool_vote_exclusion_reasons=sorted(set(reasons)))
        records.append(row)
        grouped[image, condition].append((obj, row))
    pools = []
    for image, current in sorted(difficulty.items()):
        image_reasons = set()
        evidence = list(holds[image].values())
        for hold in evidence:
            prefix = 'historical_consensus:' if hold['source_field'] == 'main_consensus_gate' else 'historical_quality:'
            image_reasons.add(prefix + hold['status'])
        if research_images.get(image, {}).get('gt_substantive_error_mark', False):
            image_reasons.add('historical_gt_substantive_error')
        if current['gt_error_excluded']:
            image_reasons.add('current_gt_error')
        current_exclusion = current['difficulty_analysis_exclusion']
        if current_exclusion == 'target_scope_unresolved':
            image_reasons.add('current_target_scope_unresolved')
        # 特殊/待核类别本身不全局排除专项；显式GT、范围和旧暂停仍先于专项。
        ordinary = current['difficulty_analysis_eligible']
        for condition in CONDITIONS:
            entries = grouped[image, condition]
            eligible = [row for _, row in entries if row['pool_vote_eligible']]
            workers = Counter(row['worker_id'] for row in eligible)
            min3 = len(workers) >= 3
            pool_reasons = sorted(image_reasons | (set() if min3 else {'effective_workers_below_3'}))
            person_reasons = Counter(reason for _, row in entries for reason in row['pool_vote_exclusion_reasons'])
            pool = dict(image_id=image, image_code=images[image]['image_code'],
                        building_id=images[image]['building_id'], condition=condition,
                        pool_rule_version=RULE_VERSION, n_annotation_records=len(entries),
                        n_independent_vote_records=sum(obj['independent_vote_eligible'] for obj, _ in entries),
                        n_effective_records=len(eligible), n_effective_workers=len(workers),
                        effective_worker_ids=sorted(workers),
                        duplicate_effective_worker_ids=sorted(w for w, n in workers.items() if n > 1),
                        n_excluded_records=len(entries)-len(eligible),
                        record_exclusion_reason_counts=dict(sorted(person_reasons.items())),
                        pool_min3_pass=min3, image_exclusion_reasons=sorted(image_reasons),
                        image_hold_evidence=evidence,
                        current_class=current['current_class'],
                        difficulty_analysis_exclusion=current_exclusion,
                        ordinary_difficulty_candidate=ordinary,
                        pool_analysis_eligible=not pool_reasons,
                        pool_exclusion_reasons=pool_reasons,
                        ordinary_difficulty_eligible=not pool_reasons and ordinary)
            pools.append(pool)
            for _, row in entries:
                row.update(pool_source_workers=len(workers), pool_min3_pass=min3,
                           duplicate_effective_worker=workers[row['worker_id']] > 1,
                           pool_image_exclusion_reasons=pool['image_exclusion_reasons'],
                           pool_analysis_eligible=row['pool_vote_eligible'] and pool['pool_analysis_eligible'],
                           pool_analysis_exclusion_reasons=sorted(set(row['pool_vote_exclusion_reasons'] + pool_reasons)),
                           ordinary_difficulty_eligible=row['pool_vote_eligible'] and pool['ordinary_difficulty_eligible'])
    return pools, records
