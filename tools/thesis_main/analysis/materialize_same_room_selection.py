"""整组复核的评论解释、空间来源与历史人数关联；仅用于探索性选图。"""
import argparse
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/scene_image_exploration_20260910_v1'
HISTORY = ROOT / 'analysis_results/confirmed_point_calculation_view_20260909_v1/reviewed/calculation_view.jsonl.gz'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def reconcile_spatial_history(result, review, initial_audit, semantics):
    """只让有来源的人工作答更新采用值；后期AI预填永不抹去早期分类。"""
    later = {r['image_id']: r for r in review['source_user']['rows']}
    earlier = {r['image_id']: r for r in review['source_user']['source_user']['rows']}
    initial = {r['image_id']: r for r in initial_audit['source_user']['rows']}
    ids = {r['image_id'] for r in result['images']}
    if any(len(v) != len(ids) for v in (review['source_user']['rows'], review['source_user']['source_user']['rows'], initial_audit['source_user']['rows'])):
        raise ValueError('历轮记录重复或缺失')
    if any(set(x) != ids or len(x) != len(result['images']) for x in (later, earlier, initial)):
        raise ValueError('历轮648图身份覆盖不一致')
    comment_by_id = {r['image_id']: r for r in semantics['rows']}
    if len(comment_by_id) != len(semantics['rows']) or set(comment_by_id) != {i for i, r in earlier.items() if r['user_note'].strip()}:
        raise ValueError('早期评论解释覆盖不完整')
    cases = defaultdict(list)
    for c in initial_audit['cases']:
        cases[c['image_id']].append(dict(case_id=c.get('case_id'), dimension=c['dimension'],
                                        severity=c.get('severity'), reason=c['reason']))
    earlier_oos = {('UwV83HsGsw3', 3): '用户称OOS', ('X7HyMhZNoso', 1): '用户称OOS',
                   ('b8cTxDM8gDG', 13): '用户讨论称OOS', ('pRbA3pwrgk9', 1): '用户称OOS',
                   ('pRbA3pwrgk9', 3): '疑似OOS', ('pRbA3pwrgk9', 16): '用户称OOS',
                   ('pa4otMbVnkk', 8): '疑似OOS'}
    alias = {'客厅': '起居与休闲', '工作': '工作与学习', '连接': '通行与连接',
             '按摩房': '特殊用途', '特殊用途（暂不合并分析）': '特殊用途'}
    allowed = {'卧室', '卫浴', '起居与休闲', '厨房与用餐', '通行与连接', '工作与学习',
               '储藏与家务辅助', '特殊用途', '开放复合空间', '无法判断'}
    group_by_code = {r['review_code']: r for r in result['groups']}
    for r in result['images']:
        i, number = r['image_id'], r['number']
        first, post, last = initial[i], earlier[i], later[i]
        for key in ('building', 'split'):
            if key in first and any(x.get(key) != r.get(key) for x in (first, post, last)):
                raise ValueError('历轮图片building/split不一致')
        if last['source_user'] != post:
            raise ValueError('后续行嵌套源与争议复核源不一致')
        if i in comment_by_id and comment_by_id[i]['original_comment'] != post['user_note']:
            raise ValueError('早期评论原文改变')
        delta = {k: v for k, v in post.items() if first.get(k) != v}
        in_cross = r['in_previous_disagreement_filter']
        raw_type = post['user_type']
        normalized = alias.get(raw_type, raw_type if raw_type in allowed else None)
        adopted = dict(coarse_type=normalized, functions=None, focus=None, boundary=None)
        origins = {k: '未有人工作答' for k in adopted}
        origins['coarse_type'] = '早期争议复核导出.user_type'
        if in_cross:
            for field in adopted:
                adopted[field] = last['current_classification'][field]
                origins[field] = '后续41图亲审.current_classification.' + field
        # boundary为较宽泛的空间交界；旧门洞“否”不能推出没有其他空间交界。
        position = post['user_doorway']
        if position not in ('确认', '疑似', '否', '无法判断'):
            raise ValueError('未知早期门洞标签')
        position_origin = '早期争议复核导出.user_doorway'
        events = [dict(stage='initial_648', source='user_visual_audit.json#/source_user',
                       saved_at=initial_audit['source_user']['saved_at'], values=first),
                  dict(stage='user_dispute_review', source='user_review_20260912_v3.json#/source_user',
                       saved_at=review['source_user']['source_user']['saved_at'], values=post,
                       changed_from_initial=delta, target_cases=[c for c in cases.get(i, []) if c['severity'] != '对照记录'],
                       ai_reference_cases=[c for c in cases.get(i, []) if c['severity'] == '对照记录']),
                  dict(stage='later_spatial_review', source='user_review_20260912_v3.json#/rows',
                       saved_at=review['source_user']['saved_at'], personally_reviewed_this_round=in_cross,
                       applied_fields=list(adopted) if in_cross else [], user_revision=last['user_revision'])]
        if adopted['boundary'] is None and position in ('确认', '疑似'):
            adopted['boundary'] = '确认交界（旧门洞口径）' if position == '确认' else '交界候选'
            origins['boundary'] = position_origin + '；仅作交界线索，不推定传统门框形态'
        discussion = last['discussion']
        if discussion:
            events.append(dict(stage='user_discussion', source=discussion['record_path'], values=discussion))
            for item in discussion['batch_records']:
                for decision in item['boundary_decisions']:
                    if decision['image_id'] != i:
                        continue
                    state = decision['state']
                    adopted['boundary'] = state
                    origins['boundary'] = '用户逐组讨论.' + item['case_id']
                    # 暂候选是工作分类的降级，不代表已经证明旧“确认”错误。
                    if state == '低优先级候选':
                        position = '疑似'
                    elif state in ('暂不归入', '近交界但暂不归入'):
                        position = '否'
                    elif state == '待定：用户提问':
                        position = '无法判断'
                    else:
                        raise ValueError('未处理的讨论交界状态: ' + state)
                    position_origin = origins['boundary'] + '；按后续工作分类更新'
            if r['building'] == 'e9zR4mvMWw7' and number in (13, 38):
                adopted['boundary'] = '确认空间交界' if number == 13 else '偏一侧，暂不归入'
                origins['boundary'] = '逐组讨论记录.md：13居中，38偏客厅'
                position = '否'
                position_origin = '早期原评论与后续逐组讨论：非传统门框；不否定13的空间交界'
        # 只处理有明确否定/靠近含义的逐条评论；不以关键词自动裁定空间。
        comment_nontraditional = ((r['building'] == 'UwV83HsGsw3' and number in (3, 6, 9, 16, 23))
                                   or (r['building'] == 'uNb9QFRL6hY' and number == 25)
                                   or (r['building'] == 'e9zR4mvMWw7' and number == 13))
        nearby = ((r['building'] == 'e9zR4mvMWw7' and number in (15, 19, 39))
                  or (r['building'] == 'yqstnuAEVhm' and number == 21)
                  or (r['building'] == 'zsNo4HB9uLZ' and number == 9))
        if nearby and not in_cross and not discussion:
            adopted['boundary'] = '近交界暂不归入'
            origins['boundary'] = '用户原评论：门前/离门近，不是交界确认'
        if in_cross:
            adopted['boundary'] = last['current_classification']['boundary']
            origins['boundary'] = '后续41图亲审.current_classification.boundary'
            if adopted['boundary'] in ('暂不归入', '近交界暂不归入'):
                position = '否'
                position_origin = '后续41图亲审.boundary：暂不归入/近交界'
        for code in r['group_codes']:
            g = group_by_code[code]
            note = g['interpretation']
            events.append(dict(stage='group_review', group_code=code,
                               source='user_group_review_20260912.json#/group_reviews',
                               saved_at=review['saved_at'], raw_current=g['raw_current'], interpretation=note))
            if number in note.get('doorway', []):
                position = '确认'
                adopted['boundary'] = '确认门洞交界'
                position_origin = origins['boundary'] = '最新整组评论.' + code
        meaningful_kind = ('非传统区域分隔' if comment_nontraditional else
                           '非典型开口' if r['building'] == '7y3sRwLe3Va' and number == 18 else '形态未单独核实')
        issues = []
        ai = last['prefill']
        if not in_cross and adopted['coarse_type'] != ai.get('coarse_type') and ai.get('coarse_type'):
            issues.append(dict(field='coarse_type', adopted=adopted['coarse_type'],
                               proposed=ai['coarse_type'], state='AI建议未亲审，保留并列'))
        if normalized is None and not in_cross:
            issues.append(dict(field='coarse_type', raw_value=raw_type, state='旧自由文本/复合待定需拆解，未强行归类'))
        sem = comment_by_id.get(i)
        if sem and sem['option_conflict'] != '无':
            issues.append(dict(field='earlier_comment', state='已有后续意见供核对' if in_cross or discussion or r['group_codes'] else '需保留语义疑点',
                               reason=sem['conflict_reason']))
        r['spatial_ai_proposal'] = ai
        r['spatial_round_display_values'] = last['current_classification']
        r['spatial_ai_evidence'] = dict(main_review=last.get('review'), cross_reviews=last.get('cross_reviews', []),
                                         prior_reviews=last.get('prior_reviews', []))
        r['spatial_classification'] = adopted
        r['spatial_field_sources'] = origins
        r['spatial_review_provenance'] = '历轮字段来源见spatial_field_sources及review_history；非全图本轮亲审'
        r['legacy_room_label'] = post['user_room']
        r['legacy_coarse_type_raw'] = raw_type
        r['legacy_artifact_classification'] = dict(value=post['user_artifact'], source='早期争议复核导出',
                                                  does_not_imply_geometric_verification=True)
        r['earlier_comment_semantics'] = sem
        r['review_history'] = events
        r['spatial_open_layout_status'] = ('人工采用开放复合空间' if adopted['coarse_type'] == '开放复合空间'
            else 'AI提出开放复合空间，待人工采用' if ai.get('coarse_type') == '开放复合空间' else '未单独确定开放性')
        r['doorway_reconciliation'] = dict(initial_label=first['user_doorway'], post_dispute_label=post['user_doorway'],
            current_working_label=position, source=position_origin, form_kind=meaningful_kind,
            coordinate_verified=False, annotation_boundary_only_codes=r['annotation_boundary_comment_codes'],
            note='沿用用户工作分类词汇；确认可包含非传统开口，不等于实测传统门框中心。')
        r['review_coverage'] = dict(early_dispute_target=any(c['severity'] != '对照记录' for c in cases.get(i, [])),
            early_dispute_dimensions=sorted({c['dimension'] for c in cases.get(i, []) if c['severity'] != '对照记录'}),
            early_user_input_changed=bool(delta), initial_submitter_review_status=first['user_status'],
            later_spatial_personally_reviewed=in_cross, group_personally_reviewed=bool(r['group_codes']),
            note='旧提交中的已复核可能来自初分类者；记录被采纳不等于用户逐张逐字段重看。')
        r['spatial_conflicts'] = issues
        oos = []
        if (r['building'], number) in earlier_oos:
            oos.append(dict(source='早期用户评论/逐组讨论', state=earlier_oos[r['building'], number],
                            scope='image', evidence=discussion if earlier_oos[r['building'], number] == '用户讨论称OOS' else post['user_note']))
        if r['building'] == 'q9vSo1VnCiC' and number == 18:
            oos.append(dict(source='后续41图亲审评论', state='疑似OOS', scope='image', evidence=last['current_classification'].get('note')))
        for code in r['group_codes']:
            note = group_by_code[code]['interpretation']
            if note.get('oos') and (not note.get('oos_numbers') or number in note['oos_numbers']):
                oos.append(dict(source='最新整组评论.' + code, state=note['oos'],
                                scope='image' if note.get('oos_numbers') else 'group_unspecified_individual',
                                evidence=note['original_note']))
        r['oos_evidence'] = oos
        r['oos_eligibility'] = '未作正式裁决；无记录不等于in-scope'
        r['all_user_notes'] = ([dict(source='早期争议复核', text=post['user_note'])] if post['user_note'] else []) + (
            [dict(source='后续空间复核', text=last['current_classification']['note'])] if last['current_classification'].get('note') else []) + [
            dict(source='最新整组评论.' + code, text=group_by_code[code]['raw_current']['note'], scope='whole_group_see_interpretation')
            for code in r['group_codes'] if group_by_code[code]['raw_current']['note']]
        if discussion:
            r['all_user_notes'].append(dict(source='此前逐组讨论', values=discussion))
        r['later_round_spatial_human_reviewed_fields'] = r.pop('spatial_human_reviewed_fields', [])
    by_id = {r['image_id']: r for r in result['images']}
    for g in result['groups'] + result['candidates']:
        members = [by_id[i] for i in g['image_ids']]
        g['spatial_summary'] = dict(
            coarse_type_counts=dict(Counter(r['spatial_classification']['coarse_type'] or '待定' for r in members)),
            doorway_confirmed_image_ids=[r['image_id'] for r in members if r['doorway_reconciliation']['current_working_label'] == '确认'],
            doorway_pending_image_ids=[r['image_id'] for r in members if r['doorway_reconciliation']['current_working_label'] in ('疑似', '无法判断')],
            annotation_boundary_only_image_ids=[r['image_id'] for r in members if r['annotation_boundary_comment_codes']],
            image_ids_with_oos_evidence=[r['image_id'] for r in members if r['oos_evidence']],
            image_ids_with_spatial_conflicts=[r['image_id'] for r in members if r['spatial_conflicts']])
    result['schema'] = 'same_room_selection_registry_v2'
    if 'summary' in result:
        result['summary']['later_round_spatial_review_counts'] = result['summary'].pop('previous_spatial_review_counts')
    result['spatial_reconciliation_summary'] = dict(total_images=len(ids), initial_dispute_target_images=sum(any(c['severity'] != '对照记录' for c in cc) for cc in cases.values()),
        early_comments=len(comment_by_id), latest_group_comments=sum(bool(g['raw_current']['note']) for g in result['groups']),
        doorway_initial=dict(Counter(r['user_doorway'] for r in initial.values())),
        doorway_post_dispute=dict(Counter(r['user_doorway'] for r in earlier.values())),
        doorway_current_working=dict(Counter(r['doorway_reconciliation']['current_working_label'] for r in result['images'])),
        coarse_types=dict(Counter(r['spatial_classification']['coarse_type'] or '待定' for r in result['images'])),
        images_with_unresolved_spatial_issues=sum(bool(r['spatial_conflicts']) for r in result['images']),
        interpretation='完整接续各轮记录；门洞确认数是用户工作分类数，非精确几何确认或全部个人亲审证明。')
    result['spatial_source_policy'] = dict(order=['初始648分类', '用户争议复核完整导出', '明确逐组讨论', '后续41图空间亲审', '最新整组评论的逐图明确意见'],
        fields='后阶段仅覆盖自己明确处理的字段。旧房号不生成同房关系；门洞否不等于没有一般空间交界。',
        ai='未亲审的AI预填只放spatial_ai_proposal，不得覆盖人工作答；未拆解自由文本保留raw并列待定。')
    return result


def annotation_coverage(result, rows):
    """人数为集合并集；人图数为每图人数之和；Manual与Semi可能是同一人。"""
    by_image = defaultdict(list)
    for r in rows:
        if r['assistance_exposure'] not in ('none', 'model_preannotation'):
            raise ValueError('未知辅助条件')
        by_image[r['image_id']].append(r)

    def summarize(image_ids):
        if len(image_ids) != len(set(image_ids)):
            raise ValueError('统计成员重复')
        sets = {k: [] for k in ('any', 'manual', 'manual_included', 'semi')}
        for image_id in image_ids:
            rr = by_image[image_id]
            sets['any'].append({str(r['worker_id']) for r in rr})
            sets['manual'].append({str(r['worker_id']) for r in rr if r['assistance_exposure'] == 'none'})
            sets['manual_included'].append({str(r['worker_id']) for r in rr if r['unassisted_manual_included']})
            sets['semi'].append({str(r['worker_id']) for r in rr if r['assistance_exposure'] == 'model_preannotation'})
        unions = {k: set().union(*v) for k, v in sets.items()}
        return dict(n_images=len(image_ids),
            n_annotated_images=sum(bool(v) for v in sets['any']),
            n_manual_images=sum(bool(v) for v in sets['manual']),
            n_semi_images=sum(bool(v) for v in sets['semi']),
            n_both_mode_images=sum(bool(a and b) for a, b in zip(sets['manual'], sets['semi'])),
            n_semi_only_images=sum(bool(b) and not a for a, b in zip(sets['manual'], sets['semi'])),
            n_people={k: len(v) for k, v in unions.items()},
            n_person_images={k: sum(map(len, v)) for k, v in sets.items()},
            worker_ids={k: sorted(v) for k, v in unions.items()},
            n_people_both_modes=len(unions['manual'] & unions['semi']),
            n_canonical_records=sum(len(by_image[i]) for i in image_ids),
            per_image={i: {k: len(v[j]) for k, v in sets.items()} for j, i in enumerate(image_ids)})

    for r in result['images']:
        r['annotation_counts'] = summarize([r['image_id']])
    for r in result['groups'] + result['candidates']:
        r['annotation_counts'] = summarize(r['image_ids'])
    result['annotation_coverage'] = summarize([r['image_id'] for r in result['images']])
    result['annotation_count_rules'] = dict(
        scope='既有canonical快照，非全仓库最新导出的重新普查；未找到不等于从未标注。',
        modes='manual=assistance_exposure:none；semi=model_preannotation；manual_included为已有无辅助计算纳入标记。',
        units='n_people为成员图之间人员ID去重人数；n_person_images为各图去重人数之和；n_canonical_records为记录数，不能替代人数。',
        overlap='同一人跨图只计一个组内人；同一人参与两种模式可同时出现在两列，any为并集，不是Manual+Semi。',
        groups='原260展示组与合并/拆分后的259候选分别统计；含不同房或待定组。组间可重叠，禁止汇总各组人数作为总人数。',
        ranking='已有优先级不变；低歧义排序中的高人数特指manual_included>=19，Semi历史单列，不冒充无辅助证据。')
    return result


def historical_counts(rows, root):
    """核对既有canonical清单到原始导出；人数按图内人员去重，不混合辅助条件。"""
    source_rows, people = defaultdict(list), defaultdict(list)
    ids = set()
    for r in rows:
        if r['canonical_annotation_id'] in ids:
            raise ValueError('重复canonical记录')
        ids.add(r['canonical_annotation_id'])
        if not isinstance(r['unassisted_manual_included'], bool):
            raise ValueError('纳入字段不是布尔值')
        source_rows[r['raw_export_path']].append(r)
        people[r['image_id']].append(r)
    verified = 0
    for source, rr in source_rows.items():
        tasks = read(root / source)
        idx = {}
        for t in tasks:
            for a in t['annotations']:
                key = (str(t['id']), str(a['id']))
                if key in idx:
                    raise ValueError('原导出重复任务/标注编号')
                idx[key] = (t, a)
        for r in rr:
            _, _, task, worker, annotation = r['raw_annotation_version_id'].split('|')
            t, a = idx[(task, annotation)]
            completed = a['completed_by']
            if isinstance(completed, dict):
                completed = completed['id']
            if str(completed) != worker or worker != str(r['worker_id']):
                raise ValueError('原导出人员不匹配')
            if r['image_id'] not in json.dumps(t['data']):
                raise ValueError('原导出图像绑定不匹配')
            if r['assistance_exposure'] not in ('none', 'model_preannotation'):
                raise ValueError('未知辅助条件')
            verified += 1
    counts = {}
    for image_id, rr in people.items():
        manual = {str(r['worker_id']) for r in rr if r['unassisted_manual_included']}
        if any(r['unassisted_manual_included'] and r['assistance_exposure'] != 'none' for r in rr):
            raise ValueError('无辅助纳入标记与辅助条件冲突')
        counts[image_id] = dict(
            n_people_any=len({str(r['worker_id']) for r in rr}),
            n_people_unassisted=len({str(r['worker_id']) for r in rr if r['assistance_exposure'] == 'none'}),
            n_people_manual_included=len(manual),
            n_people_model_assisted=len({str(r['worker_id']) for r in rr if r['assistance_exposure'] == 'model_preannotation'}),
            canonical_annotation_ids=[r['canonical_annotation_id'] for r in rr],
            raw_export_paths=sorted({r['raw_export_path'] for r in rr}),
            stages=dict(Counter(r['stage'] for r in rr)))
    return counts, dict(canonical_records=verified, raw_export_files=len(source_rows), snapshot_images=len(counts))


def assemble(review, interpretations, history):
    if review['schema'] != 'same_room_pair_user_review_v1' or review['form_version'] != 3:
        raise ValueError('整组导出版本错误')
    images = {r['image_id']: r for r in review['images']}
    source = {r['image_id']: r for r in review['source_user']['rows']}
    pairs = {r['pair_id']: r for r in review['pairs']}
    if len(images) != len(review['images']) or set(images) != set(source):
        raise ValueError('图像覆盖不一致')
    gs = review['group_reviews']
    ledger = {r['group_id']: r for r in interpretations['rows']}
    if len(ledger) != len(interpretations['rows']) or set(ledger) != {g['group_id'] for g in gs if g['current']['note'].strip()}:
        raise ValueError('非空评论必须逐条解释且不可重复')
    records, image_groups = [], defaultdict(list)
    for index, g in enumerate(gs, 1):
        code = f'G{index:03}'
        members = g['image_ids']
        if len(members) != len(set(members)) or not set(members) <= set(images):
            raise ValueError('组内图像重复或缺失')
        if len({images[i]['building'] for i in members}) != 1:
            raise ValueError('同房组跨楼')
        if g['group_id'] != '|'.join(sorted(members)):
            raise ValueError('组ID与成员不一致')
        for p in g['pair_ids']:
            if p not in pairs or not set(pairs[p]['image_ids']) <= set(members):
                raise ValueError('组配对来源错误')
        current = {**g['prefill'], **g['user_revision']}
        if current != g['current'] or set(g['changed_fields']) != {k for k in current if current[k] != g['prefill'][k]}:
            raise ValueError('组填写与合成值不一致')
        comment = ledger.get(g['group_id'], {})
        if comment and (comment['original_note'] != current['note'] or comment['review_code'] != code):
            raise ValueError('评论解释来源不一致')
        numbers = {images[i]['number']: i for i in members}
        for key in ('affected_numbers', 'core', 'proposed_core', 'doorway', 'annotation_boundary', 'oos_numbers'):
            if not set(comment.get(key, [])) <= set(numbers):
                raise ValueError('解释引用组外图号: ' + code + ':' + key)
        for nums in comment.get('subgroups', []):
            if not set(nums) <= set(numbers):
                raise ValueError('拆分图号不在原组')
        status = ('explicit_discussion' if current['status'] == '仍需讨论' else
                  'explicit_confirmed' if current['status'] == '已确认' else 'viewed_per_user_statement')
        record = dict(review_code=code, group_id=g['group_id'], building=images[members[0]]['building'],
                      image_ids=members, numbers=[images[i]['number'] for i in members],
                      raw_current=current, original_status=current['status'], review_state=status,
                      viewed=True, viewed_basis='本次用户明确全部同房组看完；不等于所有字段确定或旧粗类全审',
                      interpretation=comment, issue_tags=comment.get('issue_tags', []),
                      oos_status=comment.get('oos', 'not_mentioned_not_in_scope_proof'),
                      outcome_exposure=comment.get('outcome_exposed', False),
                      source_pair_ids=g['pair_ids'])
        records.append(record)
        for image_id in members:
            image_groups[image_id].append(code)
    by_code = {r['review_code']: r for r in records}
    candidates, consumed = [], set()
    for r in records:
        code, note = r['review_code'], r['interpretation']
        if code in consumed:
            continue
        source_codes = [f'G{i:03}' for i in note.get('merge', [])] or [code]
        consumed.update(source_codes)
        members = list(dict.fromkeys(i for c in source_codes for i in by_code[c]['image_ids']))
        num_map = {images[i]['number']: i for i in members}
        if len({images[i]['building'] for i in members}) != 1:
            raise ValueError('合组跨building')
        if len(source_codes) > 1:
            subsets = [sorted(num_map)]
            scope = 'merged_physical_room_cross_subgroup_comparability_pending'
        else:
            subsets = note.get('subgroups') or [note.get('core', r['numbers'])]
            scope = note.get('scope', 'whole_group')
        for sub_index, nums in enumerate(subsets, 1):
            ids = [num_map[n] for n in nums]
            current = r['raw_current']
            ks = [history.get(i, {}).get('n_people_manual_included', 0) for i in ids]
            supported = current['physical_same'] == '支持'
            unresolved = scope in ('unclear_subset', 'inferred_subset', 'outcome_condition_unresolved',
                                   'information_mismatch', 'merged_physical_room_cross_subgroup_comparability_pending')
            # 子集评论不能自动把未填写的维度升级成“预期相近”。
            comparable = (supported and current['main_visual_alignment'] == '一致'
                          and current['extent_alignment'] == '预期相近' and not unresolved)
            oos_on_subset = note.get('oos', '') and (not note.get('oos_numbers') or bool(set(nums) & set(note['oos_numbers'])))
            difficulty = current['difficulty_similarity']
            issues_outside_subset = bool(note.get('affected_numbers')) and not set(nums) & set(note['affected_numbers'])
            subset_issues = [] if issues_outside_subset else r['issue_tags']
            tier = None
            if comparable and not oos_on_subset and difficulty in ('预期相近', '可能出现小幅歧义'):
                if current['decision'] == '优先候选':
                    tier = (1 if difficulty == '预期相近' and not subset_issues else 2) if len(ids) >= 3 else 3
                elif current['decision'] == '基础候选':
                    tier = 3 if len(ids) >= 3 else 4
            candidates.append(dict(candidate_id=code + (f'-S{sub_index}' if len(subsets) > 1 else ''),
                source_group_codes=source_codes, building=r['building'], image_ids=ids,
                numbers=nums, n_images=len(ids), excluded_from_this_subset=[images[i]['number'] for i in members if i not in ids],
                subset_scope=scope, proposed_core_numbers=note.get('proposed_core'),
                raw_decision=current['decision'], difficulty_similarity=difficulty,
                physical_same_supported=supported, comparable_for_prediction=comparable,
                oos_pending=bool(oos_on_subset), oos_status=note.get('oos', ''),
                low_ambiguity_batch=tier, issue_tags=subset_issues, original_group_issue_tags=r['issue_tags'],
                disagreement_research_candidate=bool(r['issue_tags'] or difficulty == '存在明显差异'),
                disagreement_basis='用户评论/信息差异的定性线索；未判定实际持续增簇',
                disagreement_comparison_image_ids=members,
                observed_new_cluster_status='not_computed_this_step',
                review_state=r['review_state'], outcome_exposure=r['outcome_exposure'],
                n_historically_annotated=sum(history.get(i, {}).get('n_people_any', 0) > 0 for i in ids),
                n_manual_k_ge_3=sum(k >= 3 for k in ks), n_manual_k_ge_19=sum(k >= 19 for k in ks),
                manual_k_by_image=dict(zip(ids, ks)), max_manual_k=max(ks, default=0),
                selection_hold_reasons=([scope] if unresolved else []) +
                    (['OOS待定单列'] if oos_on_subset else []) +
                    (['主空间或范围可比性未满足'] if not comparable else []),
                similar_scene_links=[f"G{note['similar_to']:03}"] if 'similar_to' in note else []))
    image_records = []
    for image_id, image in images.items():
        old = source[image_id]
        in_cross = any(x['verdict'] != '支持' for x in old['cross_reviews'])
        provenance = 'user_reviewed_disagreement_subset' if in_cross else ('prior_discussion' if old['discussion'] else 'ai_or_legacy_not_personally_reviewed_this_round')
        if not in_cross and old['user_revision']:
            raise ValueError('复核范围外存在人工填写，需单独解释')
        links = [by_code[c] for c in image_groups.get(image_id, [])]
        image_notes = [dict(group_code=r['review_code'], note=r['interpretation']['original_note'],
                            interpretation=r['interpretation']['interpretation']) for r in links
                       if image['number'] in r['interpretation'].get('affected_numbers', [])]
        door_refs = [r['review_code'] for r in links if image['number'] in r['interpretation'].get('doorway', [])]
        image_records.append(dict(**image, group_codes=image_groups.get(image_id, []),
            same_room_group_review_viewed=bool(image_groups.get(image_id)),
            spatial_classification=old['current_classification'], spatial_review_provenance=provenance,
            spatial_human_reviewed_fields=['coarse_type', 'functions', 'focus', 'boundary'] if in_cross else [],
            in_previous_disagreement_filter=in_cross, spatial_changed_fields=old['changed_fields'],
            spatial_user_revision=old['user_revision'], spatial_prior_user=old['source_user'],
            prior_discussion=old['discussion'],
            doorway_user_comment_codes=door_refs,
            annotation_boundary_comment_codes=[r['review_code'] for r in links if image['number'] in r['interpretation'].get('annotation_boundary', [])],
            group_oos_mentions=[dict(group_code=r['review_code'], status=r['oos_status'],
                                   scope_numbers=r['interpretation'].get('oos_numbers', [])) for r in links if r['interpretation'].get('oos')],
            specific_user_issues=image_notes,
            historical=history.get(image_id, dict(n_people_any=0, n_people_unassisted=0,
                n_people_manual_included=0, n_people_model_assisted=0, canonical_annotation_ids=[], raw_export_paths=[], stages={})),
            historical_coverage='matched_canonical_snapshot' if image_id in history else 'not_found_in_this_snapshot_not_never_annotated'))
    low = sorted([c for c in candidates if c['low_ambiguity_batch'] is not None], key=lambda c:(
        c['low_ambiguity_batch'], -c['n_manual_k_ge_19'], -c['n_images'], -c['n_historically_annotated'],
        0 if c['difficulty_similarity'] == '预期相近' else 1, bool(c['issue_tags']), c['candidate_id']))
    sizes = sorted([c for c in candidates if c['physical_same_supported']], key=lambda c:(-c['n_images'], -c['n_manual_k_ge_19'], c['candidate_id']))
    for name, seq in [('low_ambiguity_rank', low), ('room_size_rank', sizes)]:
        for rank, c in enumerate(seq, 1):
            c[name] = rank
    return dict(schema='same_room_selection_registry_v1', source_saved_at=review['saved_at'],
        groups=records, candidates=candidates, images=image_records,
        views=dict(low_ambiguity_order=[c['candidate_id'] for c in low], room_size_order=[c['candidate_id'] for c in sizes],
                   disagreement_candidates=[c['candidate_id'] for c in sizes if c['disagreement_research_candidate']],
                   oos_source_groups=[r['review_code'] for r in records if r['interpretation'].get('oos')],
                   oos_pending=[c['candidate_id'] for c in candidates if c['oos_pending']]),
        summary=dict(images=len(images), submitted_groups=len(gs), interpreted_comments=len(ledger),
                     images_shown_in_group_review=len(image_groups), images_not_shown_in_group_review=len(images)-len(image_groups),
                     original_status_counts=dict(Counter(r['original_status'] for r in records)),
                     previous_spatial_review_counts=dict(Counter(r['spatial_review_provenance'] for r in image_records)),
                     candidate_units=len(candidates), low_ambiguity_candidates=len(low),
                     oos_pending_units=sum(c['oos_pending'] for c in candidates),
                     matched_history_images=sum(i in history for i in images)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--review', type=Path, default=OUT / 'user_group_review_20260912.json')
    args = parser.parse_args()
    review = read(args.review)
    original = read(OUT / 'same_room_pair_audit_20260912.json')
    if review['source_user'] != original['source_user'] or review['images'] != original['images']:
        raise ValueError('整组导出的原图/空间来源被改写')
    submitted_pairs = {p['pair_id']: p for p in review['pairs']}
    if len(submitted_pairs) != len(review['pairs']) or set(submitted_pairs) != {p['pair_id'] for p in original['pairs']}:
        raise ValueError('原配对覆盖改变')
    for p in original['pairs']:
        if any(submitted_pairs[p['pair_id']][k] != v for k, v in p.items()):
            raise ValueError('原配对建议被改写')
    with gzip.open(HISTORY, 'rt', encoding='utf-8') as stream:
        rows = [json.loads(line) for line in stream]
    counts, audit = historical_counts(rows, ROOT)
    result = annotation_coverage(assemble(review, read(OUT / 'group_comment_interpretation_20260912.json'), counts), rows)
    result = reconcile_spatial_history(result, review, read(OUT / 'user_visual_audit.json'),
                                       read(OUT / 'comment_semantics_review.json'))
    result['historical_source_audit'] = dict(**audit, calculation_index=str(HISTORY.relative_to(ROOT)),
        definition='既有canonical计算快照，经任务/标注/人员/图像ID回查18份原导出；未重扫所有新导出。0仅指快照未找到。',
        high_people_threshold=19, threshold_note='沿用旧高人数探索展示门槛；不是足以收敛的判据。',
        source_paths=sorted({r['raw_export_path'] for r in rows}))
    result['ranking_rules'] = dict(status='探索性候选顺序，非最终派发或验证样本冻结',
        low_ambiguity='已满足可比性且无OOS疑问：优先+相近且>=3图为批次1；优先+小幅歧义/评论问题且>=3图为批次2；基础>=3图与优先2图并列批次3；基础2图为批次4。',
        within_batch='先已有>=19人图数，再组图数、已标图数、相近/小幅歧义、评论问题；这是无加权分数的暂定安排。',
        alternative_order='room_size_order独立按图数排序，保留可比性与OOS待定标记；不能将排序条目数视为独立房间数。',
        uncertainty='小幅歧义描述预期比较差异，不等于绝对低难度；难图单列分歧研究，不认定持续增簇。',
        review_scope='早期648图分类与用户争议复核完整接续；后续空间轮亲审41图，不是累计只亲审41图。260同房组已看，状态空白不等于漏审。',
        current_planning_status='保留旧低歧义排序作为一个视图；另可按room_size_order查看多视点及困难组。SOP v6优先4—5及更多视点的新安排未据此冻结派发，W11退出后续不删历史，W19/W26主分析状态未定。')
    result['input_integrity'] = dict(original_spatial_source_unchanged=True, original_pair_evidence_unchanged=True,
        user_review_snapshot=str(args.review.relative_to(ROOT)) if args.review.is_relative_to(ROOT) else str(args.review),
        comment_interpretation='group_comment_interpretation_20260912.json')
    result['source_manifest'] = [dict(path=name, schema=source.get('schema'), saved_at=source.get('saved_at'), role=role)
        for name, source, role in [
            ('user_visual_audit.json#/source_user', read(OUT / 'user_visual_audit.json')['source_user'], '初始648图分类'),
            ('user_review_20260912_v3.json#/source_user', review['source_user']['source_user'], '早期用户争议复核完整导出'),
            ('user_review_20260912_v3.json', review['source_user'], '后续空间复核；该轮亲审41图'),
            ('user_group_review_20260912.json', review, '最新整组复核'),
            ('comment_semantics_review.json', read(OUT / 'comment_semantics_review.json'), '早期47条评论解释'),
            ('group_comment_interpretation_20260912.json', read(OUT / 'group_comment_interpretation_20260912.json'), '最新55条组评论解释'),
            ('batch_user_decisions_20260911_v1.json', read(OUT / 'batch_user_decisions_20260911_v1.json'), '逐组讨论结构化决定')]]
    (OUT / 'same_room_selection_registry_v2_20260912.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
    print(json.dumps(result['spatial_reconciliation_summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()
