"""最终审核的研究解释与交叉机器表；不新增裁决或复审任务。"""
import json
from collections import Counter, defaultdict

from tools.thesis_main.data_prep.materialize_current_research_input import load_current_input, rows, indexed
from .finalize_review_20260928 import ROOT, read, dump
from .final_review_summary_20260929 import geometry_status

OUT = ROOT / 'analysis_results/review_research_tables_20260929'
FINAL = ROOT / 'analysis_results/final_review_summary_20260929'
PURPOSE = '清除明显无效标注，保留真实的空间选择、细节表达和定位差异；通过图片适用性、参考状态和模型辅助因素，避免把图片本身的问题全部归到人员质量。随后研究多人共识如何变化、怎样偏离或接近参考GT，而不是强求共识一定正确。'
TERMS = {
    'cylinder': ['圆柱'], 'window_frame_or_sill': ['窗框', '窗台'], 'door_frame': ['门框'],
    'mislocation': ['错位', '错地方', '偏移'], 'point_count': ['只有4点', '只有6点', '奇数点', '补点', '点数'],
    'other_space': ['其他空间', '门外的空间'], 'scene_difficulty': ['遮挡', '难标', '拍摄'],
    'multiple_stops': ['停止区域', '停止点', '停止边界'],
}


def mentions(comments):
    """仅词面命中并附原文，不把否定/疑问/历史意见变为原因裁决。"""
    return [dict(topic=k, comment=c, matched_terms=[w for w in words if w in c])
            for k, words in TERMS.items() for c in comments if any(w in c for w in words)]


def cross(items, fields, id_key='object_id'):
    groups = defaultdict(list)
    for r in items:
        groups[tuple(r[k] for k in fields)].append(r[id_key])
    return [dict(dimensions=dict(zip(fields, key)), n=len(ids), ids=ids)
            for key, ids in sorted(groups.items(), key=lambda kv: str(kv[0]))]


def build():
    data = load_current_input()
    source = indexed(data['objects'], 'object_id')
    ann = [o for o in data['objects'] if o['object_kind'] == 'annotation']
    changes = indexed(rows(FINAL / '逐对象改序及审核来源.csv'), 'object_id')
    influence = indexed(data['explicit_model_influence_comments'], 'object_id')
    annotations = []
    for o in ann:
        e = o['review_evidence']; f = o['final_review']
        comments = list(dict.fromkeys(c for c in (e['current_comment'], e['current_decision_comment']) if c.strip()))
        tags = e['annotation_traits'].get('tags', [])
        reference_uncertain = 'reference_uncertain' in (tags + e['image_traits'].get('tags', []) + e['coverage_review'].get('effective_tags', []))
        r = {k: o[k] for k in ('object_id', 'image_id', 'image_code', 'worker_id', 'condition', 'building_id', 'room_id', 'cleaning_disposition', 'worker_quality_gate', 'consensus_group', 'scene_category', 'scene_oos_status', 'scene_doorway_status', 'trap_status', 'model_edit_status', 'order_status', 'independent_vote_eligible')}
        r.update(geometry_status=o['geometry']['status'], geometry_issues=o['geometry']['issues'],
            method_evaluability=o['method_evaluability'], main_quality_gate=o['main_quality_gate'], main_consensus_gate=o['main_consensus_gate'],
            gt_substantive_error_mark=e['gt_substantive_error'], gt_detail_omission_mark=e['gt_detail_omission'], gt_version_note=e['gt_version_note'],
            gt_uncertainty_explicit_tag=reference_uncertain,
            gt_judgment='existing_problem_mark_not_version_adjudication' if e['gt_substantive_error'] else 'explicit_reference_uncertain_tag' if reference_uncertain else 'detail_omission_mark' if e['gt_detail_omission'] else 'not_marked_not_proven_correct',
            explicit_model_influence=o['object_id'] in influence,
            model_outcome='coordinates_changed_and_final_review_excluded' if o['model_edit_status']=='changed_coordinates' and o['cleaning_disposition']=='excluded_by_review' else 'correction_success_not_established',
            model_influence_evidence=influence.get(o['object_id']), trap_evidence=e['trap_model_evidence'],
            scope_annotation=f['scope_difference_annotation'], detail_annotation=f['detail_difference_annotation'],
            execution_tag='execution' in tags, annotation_traits=e['annotation_traits'],
            current_comments=comments, current_comment_mentions=mentions(comments),
            exclusion_reason_detail='specific_term_mentioned_not_adjudicated' if mentions(comments) else 'unknown_or_nonspecific',
            order_state=f['order_state'], order_change=changes[o['object_id']]['change'] if o['object_id'] in changes else 'not_human_confirmed',
            order_change_evidence=changes.get(o['object_id']), review_evidence=e,
            source=o['source'], point_simplification_applied=False)
        annotations.append(r)
    byimage = defaultdict(list)
    for r in annotations:
        byimage[r['image_id']].append(r)
    images = []
    for im in data['images']:
        if im['population'] != 'research_annotation_image':
            continue
        group = byimage[im['image_id']]
        r = dict(im)
        r.update(gt_substantive_error_mark=any(x['gt_substantive_error_mark'] for x in group),
            gt_uncertainty_explicit_tag=any(x['gt_uncertainty_explicit_tag'] for x in group),
            gt_detail_omission_mark=any(x['gt_detail_omission_mark'] for x in group),
            scene_categories=sorted({x['scene_category'] for x in group}),
            stable_nonorthogonal=any(x['scene_category']=='oos_stable_nonorthogonal' for x in group),
            gt_evidence=[dict(object_id=x['object_id'], substantive_mark=x['gt_substantive_error_mark'], detail_mark=x['gt_detail_omission_mark'], version_note=x['gt_version_note'],
                image_comment=x['review_evidence']['image_comment'], semantic_image_evidence=x['review_evidence']['semantic_image_evidence']) for x in group if x['gt_substantive_error_mark'] or x['gt_detail_omission_mark']],
            quality_gate_counts=dict(Counter(x['worker_quality_gate'] for x in group)),
            consensus_gate_counts=dict(Counter(x['consensus_group'] for x in group)),
            geometry_counts=dict(Counter(x['geometry_status'] for x in group)),
            scene_comment_mentions=mentions(list(dict.fromkeys([im['image_comment']]+[x['review_evidence']['image_comment'] for x in group]))))
        images.append(r)
    focus = [r for r in annotations if r['worker_id'] in {'W034', 'W037'} and r['cleaning_disposition']=='excluded_by_review']
    old = indexed(read(ROOT / 'analysis_results/shared_x_baseline_20260928/preprocessed_source.json')['objects'], 'object_id')
    old_orders = read(ROOT / 'analysis_results/order_completion_audit_20260929/received_orders.json')['records']
    transitions = []
    for trace in rows(ROOT / 'analysis_results/pairing_applied_20260929/本轮34份去向.csv'):
        oid = trace['object_id']; before = old[oid]; after = source[oid]
        record = old_orders.get(oid)
        if record:
            binding = json.loads(record['binding'])
            if binding['points'] != before['preprocessed_points'] or binding['links'] != before['links_zero_based']:
                raise ValueError('historical_geometry_binding_mismatch:' + oid)
        order = record['order'] if record else list(range(len(before['links_zero_based'] or [])))
        # 同一几何诊断器比较历史与最终状态；不把配对、平均x、环序的联合变化归因于单一因素。
        g = geometry_status(before, order)
        transitions.append(dict(object_id=oid, image_code=after['image_code'], worker_id=after['worker_id'],
            before_geometry=g, after_geometry=after['geometry'], before_order_source='confirmed' if record else 'default_unreviewed',
            after_order_source=after['order_status'], pairing_changed=before['links_zero_based']!=after['links_zero_based'],
            restored_current_representation=g['status']!='surface_valid' and after['geometry']['status']=='surface_valid',
            attribution='joint_pairing_preprocessing_order_transition_not_single_factor_causality', preprocessing_trace=trace))
    tables = dict(
        gt_marks=cross(images, ['gt_substantive_error_mark', 'gt_detail_omission_mark', 'gt_uncertainty_explicit_tag'], 'image_id'),
        scene_images=cross(images, ['oos_status', 'doorway_status', 'stable_nonorthogonal'], 'image_id'),
        scene_retention_quality_geometry=cross(annotations, ['scene_category', 'cleaning_disposition', 'worker_quality_gate', 'geometry_status']),
        trap_model_outcomes=cross(annotations, ['trap_status', 'model_edit_status', 'explicit_model_influence', 'model_outcome']),
        scope_detail_execution=cross(annotations, ['scope_annotation', 'detail_annotation', 'execution_tag', 'cleaning_disposition']),
        order_representation=cross(annotations, ['order_status', 'order_change', 'geometry_status']),
        focus_worker_exclusion=cross(focus, ['worker_id', 'exclusion_reason_detail', 'scene_category']),
        order_changes_by_kind=cross(list(changes.values()), ['object_kind', 'change']))
    summary = dict(annotations=len(annotations), research_images=len(images),
        confirmed_order_objects=len(changes),
        gt_mark_images={k:sum(r[k] for r in images) for k in ('gt_substantive_error_mark','gt_detail_omission_mark')},
        focus_worker_excluded=dict(Counter(r['worker_id'] for r in focus)),
        retained_geometry=dict(Counter(r['geometry_status'] for r in annotations if r['cleaning_disposition'] in {'retained','retained_pending'})),
        pairing_review_objects=len(transitions), restored_representation=sum(r['restored_current_representation'] for r in transitions))
    result = dict(schema='review_research_interpretation_v1', purpose=PURPOSE,
        sources=dict(current_input='analysis_results/research_input_20260929/preprocessed_source.json', final_review='analysis_results/final_review_summary_20260929',
                     historical_geometry='analysis_results/shared_x_baseline_20260928/preprocessed_source.json', clarification='本线程用户本轮六项补充及近180度中间点解释'),
        rules=dict(no_new_review=True, no_new_cleaning_verdict=True, no_coordinate_changes=True,
            statistics='交叉表每行附对象ID或图片ID；分母见统计单元。标签可重叠；未记录不是否定。',
            gt='6/20为既有标记覆盖，不等于GT版本全部错误；主质量资格沿既有gate，细节省略不自动退出。共识偏离GT不能直接归于人员错误。',
            scene='非正交稳定可标、门洞难标/可标分开；拍摄/遮挡词面线索不是确诊子类型。清洗保留、主质量资格、方法可计算性独立。',
            model='Trap身份源于历史设置。改过不证明改正；未改不证明误导。改后被排除只说明最终裁决无效，不证明仍是同一模型错误。明确影响仅使用已有4份原话记录。',
            variation='同空间的细节表达、不同范围选择与具体执行错误是不同研究维度。scope/detail共存不能证明同空间；小空间不自动低质量。',
            exclusion='关键词仅当前评论词面命中，保留原话及历史；不把场景困难当个人排除原因，不把W034/W037统一解释为同墙多点。',
            order='1295为定向审核样本，不能估计全体错误率。曲线异常不充分证明顺序错；确认环也不保证当前3D可表示。',
            near_collinear=dict(cases=['同一墙面非墙角被误识别为墙角','两个停止区域同时表达，中间点可为较小空间的停止边界'],
                action='保留中间点及原证据，不按接近180度自动删除；几何角度本身不能判定属于哪一种。',
                known_multiple_stop_object_id='dd72228423710274'),
            completion='既定排序复核队列已完成；不等于3152份逐份人工确认或均可计算。5份不可配对、8份当前3D表示限制保留。'),
        summary=summary, cross_tables=tables, annotations=annotations, images=images,
        focus_worker_exclusions=focus, pairing_representation_transitions=transitions,
        curve_order_examples=[dict(image_code='2t7WUuJeko7-07', worker_id=w, status='user_reports_curve_odd_order_correct', source='用户所附第一/二张截图及后续明确说明') for w in ('W030','W036')]+
            [dict(image_code=None, worker_id='W031', status='user_reports_curve_odd_order_correct', source='第三张截图无图片代码；不猜测绑定')],
        room_registry_source=data['sources']['final_review']+'/同房分类_原始完整记录.json')
    OUT.mkdir(exist_ok=True)
    dump(OUT / 'research_tables.json', result)
    dump(OUT / 'summary.json', summary)
    dump(OUT / 'field_contract.json', dict(schema=result['schema'], entry='research_tables.json',
        read_first=['purpose', 'rules', 'summary'],
        tables=dict(annotations='3152人员记录；object_id唯一；原话和已有裁决分开，source及review_evidence追溯。',
            images='259研究图；image_id唯一；不含2张仅参考GT图；references绑定当前输入GT版本。',
            cross_tables='每行dimensions为交叉维度，n为去重ID数，ids为明细索引。每张表内部互斥分组，不跨表相加。',
            focus_worker_exclusions='W034/W037的46份明确排除记录；词面命中不是新的排除原因判定。',
            pairing_representation_transitions='34份配对复核前后，同一诊断器；历史确认校验绑定，默认环注明未审；联合变化非单因果。',
            curve_order_examples='用户曲线异常但顺序正确的例子；第三张无法绑定图片，保留null。'),
        cross_table_denominators={k:dict(unit='image_id' if k in {'gt_marks','scene_images'} else 'object_id',
            n=sum(r['n'] for r in v)) for k,v in tables.items()},
        unknown='not_marked、unknown、not_recorded均不得改写为正常/不存在。明确GT不确定标签与没有标记不同。',
        semantic_limits='current_comment_mentions仅关键词命中，可能否定/疑问；改后排除不证明模型同一错误持续；scope/detail标签不证明同空间。',
        scene_subtype_coverage='稳定非正交和门洞可标沿已有category；拍摄/遮挡仅保留评语线索，没有全量人工子类型裁决。'))
    return result


if __name__ == '__main__':
    print(build()['summary'])
