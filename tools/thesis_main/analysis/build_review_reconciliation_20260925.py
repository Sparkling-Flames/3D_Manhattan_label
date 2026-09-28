"""合并审核证据而不合并裁决；复用Studio生成独立二审页面。"""
import argparse
from collections import Counter, defaultdict
import gzip
import json
import os
from pathlib import Path
import shutil

from tools.label_studio.panorama_studio.geometry import analyze
from tools.label_studio.panorama_studio.build import data_image

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent
OUT = ROOT / 'analysis_results/review_reconciliation_20260925'
VERSION = 'consensus_research_20260923_v1'
REF_NAMES = {'gt_original': '原始 MP3D GT', 'gt_revised': '人工修订 GT',
             'hohonet': 'HoHoNet', 'bilayout_enclosed': 'BiLayout enclosed',
             'bilayout_extended': 'BiLayout extended'}
VERDICTS = {'retain': '保留', 'invalid': '无效', 'pending': '待定',
            'gt_scope': 'GT与范围争议', 'representation': '表示问题'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def read_js(path):
    return json.JSONDecoder().raw_decode(Path(path).read_text(encoding='utf-8').split('=', 1)[1].lstrip())[0]


def write(path, value):
    Path(path).write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8'))


def collect_events(documents, index, notes):
    events = []
    for reviewer, doc in documents.items():
        if doc['schema'] != 'consensus_visual_review_decisions_v1' or doc['contract_version'] != VERSION:
            raise ValueError('审核schema/合同不匹配')
        for cid, d in doc['decisions'].items():
            row = index[cid]
            expected = dict(image_id=row['image_id'], code=row['code'], worker_id=row['worker'], condition=row['condition'])
            if any(d.get(k) != v for k, v in expected.items()) or d['verdict'] not in VERDICTS:
                raise ValueError('审核身份或选项不匹配: ' + cid)
            key = reviewer + ':' + cid
            if d['comment'].strip() and key not in notes:
                raise ValueError('缺少逐条评论释义: ' + key)
            events.append(dict(d, canonical_annotation_id=cid, event_id=key, reviewer=reviewer,
                reviewer_label='你' if reviewer == 'user' else '一正', interpretation=notes.get(key),
                source_file='evidence/' + reviewer + '_review.json',
                original_view_context='unknown_not_saved_in_original_export'))
    keys = {e['event_id'] for e in events}
    if not set(notes) <= keys:
        raise ValueError('释义含未知审核ID')
    for note in notes.values():
        if not set(note['anchor_event_ids']) <= keys:
            raise ValueError('同图释义引用未知审核ID')
    return events


def supported_rooms(registry, image_ids):
    rooms, by_image = [], {}
    for room in registry['candidates']:
        if not room['physical_same_supported']:
            continue
        hits = sorted(set(room['image_ids']) & image_ids)
        if not hits:
            continue
        if any(iid in by_image for iid in hits):
            raise ValueError('支持同房登记存在重复，必须先核对')
        rid = room['candidate_id']
        by_image.update(dict.fromkeys(hits, rid))
        rooms.append(dict(id=rid, label=rid + ' · 已有同房支持', image_ids=hits,
            registered_image_ids=room['image_ids'], source_group_codes=room['source_group_codes'],
            comparable_for_prediction=room['comparable_for_prediction'],
            review_state=room.get('review_state'), oos_status=room.get('oos_status'),
            issue_tags=room.get('issue_tags', [])))
    return rooms, by_image


def historical_evidence(root):
    by_image = defaultdict(list)

    def add(iid, path, original, context):
        by_image[iid].append(dict(source=path, quote=json.dumps(original, ensure_ascii=False),
            interpretation=context + '；仅作历史证据，不覆盖本轮裁决。'))

    path = 'analysis_results/human_review_reconciliation_20260907_v1/原始问卷备份.json'
    for r in read(root / path)['records']:
        add(r['image_id'], path, r, '50图原问卷，reviewed仅表示已填写，不代表争议已解决')
    for author in ('用户_39图文字审核_原始.json', '一正_39图审核_原始.json'):
        path = 'analysis_results/human_review_reconciliation_20260918/' + author
        doc = read(root / path)
        for r in doc['reviews']:
            if r['review']['status'] == '已审核':
                add(r['image_id'], path, r, '当时特定条件的分簇审核；旧簇编号不可直接对应当前簇')
        for r in doc['image_notes']:
            if r['note'].strip(): add(r['image_id'], path, r, '当时的图片级说明')
    path = 'analysis_results/human_review_reconciliation_20260918/用户_39图最终裁决_原始.json'
    for r in read(root / path)['decisions']:
        add(r['image_id'], path, r, '保留当时问题与采集条件的裁决，不扩展到所有作答')
    for path in ('analysis_results/cluster_review_extra_20260919/用户_12图审核_原始.json',
                 'analysis_results/cluster_screen_reviewed_20260922/用户审核_原始.json'):
        for key, r in read(root / path)['decisions'].items():
            add(key.split('|')[0], path, dict(evidence_key=key, decision=r),
                '当时展示成员或簇的比较；defer保留，旧簇编号不是当前簇编号')
    path = 'analysis_results/scene_image_exploration_20260910_v1/门洞人工与AI历轮核对_20260913.json'
    for r in read(root / path)['rows']:
        doorway = r['doorway']
        related = any(doorway[k] in ('确认', '疑似', '无法判断')
                      for k in ('initial_label', 'post_dispute_label', 'current_working_label'))
        add(r['image_id'], path, dict(doorway=doorway, human_original=r['human_original'],
            human_comments=r['human_comments'], latest_selection_comment=r['latest_selection_comment']),
            '历史门洞工作分类，保留否定或反转；暂缓不等于本轮确认门洞')
        by_image[r['image_id']][-1]['doorway_related'] = related
    return by_image


def derive_image_review(rows, events, note, audit_rows):
    flags = set()
    if note.get('doorway_hold'): flags.add('doorway')
    if note.get('oos_hold') or any(r['condition'] == 'oos' for r in rows): flags.add('oos')
    if note.get('reference_concern'): flags.add('reference')
    if any(e['reviewer'] == 'yizheng' for e in events): flags.add('yizheng')
    if any(e['verdict'] == 'pending' for e in events): flags.add('pending')
    by_id = defaultdict(set)
    for e in events: by_id[e['canonical_annotation_id']].add(e['verdict'])
    questions = [q for q in note.get('questions', [])
                 if not (q['kind'] == 'cross_reviewer' and '原选项分别为' in q['title'])]
    if any(q['kind'] in ('same_pattern', 'cross_reviewer') for q in questions): flags.add('same_pattern')
    history = list(note.get('historical_notes', []))
    if history or any(q['kind'] == 'historical' for q in questions): flags.add('historical')
    if (any(q['kind'] == 'repair' for q in questions)
        or any('修复核查' in (e.get('interpretation') or {}).get('topics', []) for e in events)
        or any(audit_rows[r['id']].get('repairs') for r in rows)):
        flags.add('repair')
    # 待定只是入口之一；其他具体复核要求在下游按证据追加。
    followup = {e['canonical_annotation_id'] for e in events if e['verdict'] == 'pending'}
    image_followup = False
    if questions: flags.add('comment_questions')
    if any(e['verdict'] == 'representation' for e in events): flags.add('representation')
    if followup or image_followup: flags.add('followup')
    geometry_hold = bool(flags & {'doorway', 'oos'})
    return dict(flags=sorted(flags), summary=note.get('summary', '暂无整图结论；请结合逐份作答和原评论审查。'),
        questions=questions, history=history, annotation_ids=[r['id'] for r in rows],
        reviewed_ids=sorted(by_id), event_count=len(events), geometry_hold=geometry_hold,
        followup_ids=sorted(followup), image_followup=image_followup,
        quality_hold=geometry_hold or 'reference' in flags,
        hold_interpretation='本轮人员GT质量评价暂缓线索；不是确认OOS或确认人员错误。')


def geometry(pairs, labels, hold):
    if hold:
        return None, '门洞／OOS相关图片按本轮约定不启动3D重建。'
    if pairs is None:
        return None, '没有已接受的完整配对；二维原图和全部点仍可审查。'
    payload = dict(width=1024, height=512, coordinate_mode='pixels', ordered_pairs=[
        dict(source_pair_id=f'{labels[2*i]}/{labels[2*i+1]}', top=dict(zip(('x', 'y'), p[0])),
             bottom=dict(zip(('x', 'y'), p[1]))) for i, p in enumerate(pairs)])
    try:
        return analyze(payload, compute_fit=False), None
    except ValueError as exc:
        return None, str(exc)


def add_comment_and_cluster_questions(review, annotations, events):
    """用具体评论和现有点集分区召回复核对象，不把代码差异当裁决冲突。"""
    by_id = defaultdict(list)
    by_event = {e['event_id']: e for e in events}
    for e in events: by_id[e['canonical_annotation_id']].append(e)
    followup = set(review['followup_ids'])
    reasons = []
    def require(kind, title, selected, flag):
        ids = sorted({e['canonical_annotation_id'] for e in selected})
        followup.update(ids); review['flags'].append(flag)
        reasons.append(dict(kind=kind, title=title, annotation_ids=ids))
        review['questions'].append(dict(kind=kind, title=title, workers=[],
            evidence_event_ids=[e['event_id'] for e in selected]))
    excluded = [e for e in events if e['verdict'] == 'invalid']
    if excluded:
        require('exclusion_review', '所有曾选排除的作答都再核对：先看漏点/补点、图片适用性，再决定是否确实无效。', excluded, 'excluded')
    if events and all(e['reviewer'] == 'yizheng' for e in events):
        require('yizheng_only', '你未审过此图：复核一正的整体判断，并先确认是否门洞交界或OOS。', events, 'recheck_yizheng')
        review['yizheng_only'] = True
    user_scene = [e for e in events if e['reviewer']=='user' and e['verdict'] in ('gt_scope','pending')
                  and ('门洞' in e.get('comment','') or 'oos' in e.get('comment','').lower())]
    user_retained = [e for e in events if e['reviewer']=='user' and e['verdict']=='retain']
    if user_scene and user_retained:
        require('user_scene_retention', '仅你的审核：同图有门洞/OOS背景与保留记录。确认是否属可标门洞、困难图中勉强可用的作答，或前后口径变化；不自动认定矛盾，也不恢复人员主质量资格。',
                user_scene + user_retained, 'consistency')
    pending_ids = {e['canonical_annotation_id'] for e in events if e['verdict'] == 'pending'}
    if pending_ids:
        reasons.append(dict(kind='pending', title='原审核明确选了待定', annotation_ids=sorted(pending_ids)))
    # 逐图人工整理的问题包含评论含义，不是单凭选项异同生成。
    for q in review['questions']:
        if q['kind'] in ('exclusion_review', 'yizheng_only', 'user_scene_retention'): continue
        related = [by_event[key] for key in q['evidence_event_ids'] if key in by_event]
        ids = {e['canonical_annotation_id'] for e in related}
        conditions = {e['condition'] for e in related}
        ids.update(a['canonical_annotation_id'] for a in annotations
                   if a['worker_id'] in q['workers'] and a['raw_condition'] in conditions)
        followup.update(ids)
        reasons.append(dict(kind='comment', title=q['title'], annotation_ids=sorted(ids)))
    historical_background = any('oos' in h['quote'].lower() or any(word in h['quote'] for word in ('严重遮挡', '暂缓')) for h in review['history'])
    specific_background = bool(set(review['flags']) & {'doorway', 'oos'}) or historical_background
    context = [e for e in events if specific_background and e['reviewer'] == 'user'
        and 'image' in (e.get('interpretation') or {}).get('targets', [])
        and set((e.get('interpretation') or {}).get('topics', [])) & {'图片条件', '图片范围待统一'}]
    others = [e for e in events if e['reviewer'] == 'yizheng']
    if others and (context or historical_background):
        ids = {e['canonical_annotation_id'] for e in others}
        followup.update(ids)
        title = '本图有门洞／OOS或历史暂缓背景：结合你的同图特别说明复核一正的判断，不预设一正判错。'
        review['questions'].append(dict(kind='cross_reviewer', title=title,
            evidence_event_ids=[e['event_id'] for e in context], workers=sorted({e['worker_id'] for e in others})))
        reasons.append(dict(kind='reviewer_context', title=title, annotation_ids=sorted(ids)))
        review['flags'].append('reviewer_context')
        review['flags'].append('recheck_yizheng')
    if any(e['reviewer'] == 'yizheng' for e in excluded): review['flags'].append('recheck_yizheng')
    groups = defaultdict(list)
    for a in annotations:
        if a['screening']['cluster_coverage'] != 'matched_effective_points': continue
        for cluster in a['screening']['clusters']:
            groups[(a['raw_condition'], cluster['method'], cluster['label'])].append(a['canonical_annotation_id'])
    seen = set()
    for (condition, method, label), members in groups.items():
        excluded = {cid for cid in members if any(e['verdict'] == 'invalid' for e in by_id[cid])}
        other = {cid for cid in members if any(e['verdict'] in ('retain', 'gt_scope') for e in by_id[cid])}
        if not any(a != b for a in excluded for b in other): continue
        ids = excluded | other
        key = tuple(sorted(ids))
        if key in seen: continue
        seen.add(key); followup.update(ids)
        title = f'{condition} · {method}簇{label}有相似点集：部分作答选了无效，其他作答选了保留／范围争议。核对评论与局部错误，不能据同簇自动改判。'
        review['questions'].append(dict(kind='same_pattern', title=title, workers=[],
            evidence_event_ids=[e['event_id'] for cid in sorted(ids) for e in by_id[cid]]))
        reasons.append(dict(kind='similar_exclusion', title=title, annotation_ids=sorted(ids)))
    for e in events:
        if '修复核查' in (e.get('interpretation') or {}).get('topics', []):
            cid = e['canonical_annotation_id']; followup.add(cid)
            reasons.append(dict(kind='repair', title=e['comment'], annotation_ids=[cid]))
            review['flags'].append('repair')
    # “同图”分享的是图片说明；保留具体来源，不共享某人的排除结论。
    context_events = [e for e in events if e['reviewer'] == 'user' and e.get('comment', '').strip()
        and '同图' not in e['comment']
        and set((e.get('interpretation') or {}).get('targets', [])) & {'image', 'reference'}]
    review['shared_image_context_event_ids'] = [e['event_id'] for e in context_events]
    review['same_image_links'] = []
    for e in events:
        if e['reviewer'] != 'user' or '同图' not in e.get('comment', ''): continue
        candidates = [x['event_id'] for x in context_events if x['event_id'] != e['event_id']]
        review['same_image_links'].append(dict(event_id=e['event_id'], context_event_ids=candidates,
            status='shared_context_candidates' if candidates else 'missing_current_json_context',
            interpretation='同图图片说明候选；具体指代可复核，不继承其他人员有效性，时间为最后编辑时间。'))
    review['followup_ids'] = sorted(followup)
    review['image_followup'] = any(not r['annotation_ids'] for r in reasons)
    review['followup_reasons'] = reasons
    if reasons and 'followup' not in review['flags']: review['flags'].append('followup')
    if seen and 'same_pattern' not in review['flags']: review['flags'].append('same_pattern')
    if any(r['kind'] in ('comment', 'similar_exclusion') for r in reasons): review['flags'].append('consistency')
    if set(review['flags']) & {'doorway', 'oos'}: review['flags'].append('scene_rule')
    review['flags'] = sorted(set(review['flags']))


def worker_summary(index, events, image_reviews, audit_rows):
    by_id = defaultdict(list)
    for event in events: by_id[event['canonical_annotation_id']].append(event)
    result = []
    for worker in sorted({r['worker'] for r in index.values()}):
        for stratum in ('doorway_oos', 'other_review_images', 'outside_review_images'):
            for condition in ('manual', 'oos', 'semi'):
                rows = []
                for r in index.values():
                    if r['worker'] != worker or r['condition'] != condition: continue
                    review = image_reviews.get(r['image_id'])
                    s = 'outside_review_images' if review is None else 'doorway_oos' if review['geometry_hold'] else 'other_review_images'
                    if s == stratum: rows.append(r)
                if not rows: continue
                reviewed = [r for r in rows if r['id'] in by_id]
                result.append(dict(worker=worker, stratum=stratum, condition=condition, accepted_responses=len(rows),
                    old_reviewed_responses=len(reviewed), not_in_old_review=len(rows)-len(reviewed),
                    reviewer_options={who: dict(Counter(e['verdict'] for r in reviewed for e in by_id[r['id']] if e['reviewer'] == who))
                                      for who in ('user', 'yizheng')},
                    repair_review_candidates=sum(bool(audit_rows[r['id']].get('current_review_questions')) or
                        any(p['status'] == 'proposed_not_applied' for p in audit_rows[r['id']]['repairs']) for r in rows),
                    final_confirmed_invalid=0, final_repair_needed=0, second_review_resolved=0,
                    second_review_unresolved=sum(r['id'] in image_reviews.get(r['image_id'], {}).get('followup_ids', []) for r in rows),
                    inference_guard='候选队列有选择性；不是总体人员错误率。最终裁决尚未导入计算。'))
    return result


def add_scene_point_checks(review, audit_rows):
    if not review['geometry_hold']: return
    ids = []
    for cid in review['reviewed_ids']:
        a = audit_rows[cid]; n = len(a['effective_point_labels'])
        if n < 8 or n % 2 or a['pairing']['status'] == 'unavailable': ids.append(cid)
    if not ids: return
    title = '本图有门洞/OOS线索：先确认图片属性，再复核少点、奇数或配对未定的作答；不能把线索或算法失败直接当作排除。'
    review['questions'].append(dict(kind='scene_rule', title=title, workers=[], evidence_event_ids=[]))
    review['followup_reasons'].append(dict(kind='scene_rule', title=title, annotation_ids=ids))
    review['followup_ids'] = sorted(set(review['followup_ids']) | set(ids))
    review['flags'] = sorted(set(review['flags']) | {'followup', 'consistency', 'scene_rule'})


def reports(out, summary, cases, events, rooms, workers, audit):
    lines = ['# 逐图疑问与审核原文', '', '原选项不是统一后的有效性标准。以下释义与问题均供二审，不替代用户裁决。', '']
    by_image = defaultdict(list)
    for e in events: by_image[e['image_id']].append(e)
    for case in cases:
        r = case['review']
        lines += [f"## {case['code']} · {r['room_label']}", '', r['summary'], '', '本轮线索：' + '、'.join(r['flags']), '']
        lines += ['- 待确认：' + q['title'] for q in r['questions']]
        for h in r['history']:
            lines += ['', f"历史原文（{h['source']}）：{h['quote']}", h.get('interpretation', '')]
        for e in by_image[case['image_id']]:
            note = e['interpretation']
            lines += ['', f"### {e['reviewer_label']} / {e['worker_id']} / {e['condition']} / {VERDICTS[e['verdict']]}",
                f"作答 `{e['canonical_annotation_id']}`；最后修改 `{e['updated_at']}`。", '', '原文：' + (e['comment'] or '（未写评论）')]
            if note:
                lines += ['释义：' + note['summary'], '对象：' + '、'.join(note['targets']),
                    '相关原话：' + ('；'.join(note['anchor_event_ids']) or '未指定；不自动继承同图裁决')]
    (out / '逐图疑问汇总.md').write_bytes(('\n'.join(lines) + '\n').encode('utf-8'))
    room_lines = ['# 同房疑问汇总', '', '只使用已有 physical_same_supported 支持组；同房不自动代表同范围、同难度或可用于预测。', '']
    lookup = {c['image_id']: c for c in cases}
    for room in rooms:
        room_lines += [f"## {room['id']}", '', '预测可比性：' + str(room['comparable_for_prediction']),
                       '历史问题：' + '、'.join(room['issue_tags']), '']
        room_lines += [f"- {lookup[i]['code']}：{lookup[i]['review']['summary']}" for i in room['image_ids']]
    room_lines += ['', '## 同房未确认', ''] + [f"- {c['code']}" for c in cases if c['review']['room_id'] is None]
    (out / '同房疑问汇总.md').write_bytes(('\n'.join(room_lines) + '\n').encode('utf-8'))
    repair_rows = {cid: dict(repairs=a['repairs'], pairing=a['pairing'], history=a.get('history', []),
                            current_review_questions=a.get('current_review_questions', []))
                   for cid, a in audit['annotations'].items()
                   if a['repairs'] or a.get('current_review_questions') or a['pairing']['status'] not in ('existing_accepted_pairing', 'ok')}
    write(out / 'repair_history.json', repair_rows)
    audit_lines = ['# 原始核验与修复说明', '', '原始导出与GT未改。修复提议、历史已执行修复和本轮询问分开保留。',
                   '', '```json', json.dumps(audit['summary'], ensure_ascii=False, indent=2), '```', '']
    identities = {r['id']: r for r in read_js(ROOT / 'analysis_results/consensus_visual_review_20260923/data.js')['rows']}
    for cid, r in repair_rows.items():
        identity = identities[cid]
        audit_lines += [f"## {identity['code']} · {identity['worker']} · {identity['condition']}", '',
                       f"作答 `{cid}`", '', '配对：' + (r['pairing'].get('description') or r['pairing']['status'])]
        for repair in r['repairs']:
            audit_lines += ['- ' + repair['status'] + '：' + repair['description'],
                           '  来源：' + repair['evidence_source']]
        for question in r['current_review_questions']:
            audit_lines += ['- 本轮询问（未应用）：' + question['comment'] + '；来源 ' + question['event_id']]
        for h in r['history']:
            audit_lines += ['- 历史原话：' + h['quote'] + '；来源 ' + h['source']]
        audit_lines += ['']
    (out / '原始核验与修复说明.md').write_bytes(('\n'.join(audit_lines) + '\n').encode('utf-8'))
    worker_lines = ['# 人员原选项分作者统计', '', '两人的选项含义不同，不能合并为人员有效性或错误率。同一采用分母重复展示，不能跨作者求和；复审只涉及具体未决问题。', '',
                    '| 人员 | 图片分层 | 条件 | 作者 | 采用分母 | 该作者原选项计数 |',
                    '|---|---|---|---|---:|---|']
    strata = dict(doorway_oos='门洞/OOS单列', other_review_images='其他复审图', outside_review_images='本轮未覆盖图')
    for w in workers:
        for who in ('user', 'yizheng'):
            worker_lines.append('| ' + ' | '.join([w['worker'], strata[w['stratum']], w['condition'],
                '你' if who == 'user' else '一正', str(w['accepted_responses']),
                json.dumps(w['reviewer_options'][who], ensure_ascii=False)]) + ' |')
    (out / '人员候选统计.md').write_bytes(('\n'.join(worker_lines) + '\n').encode('utf-8'))
    readme = f'''# 两人审核整理与二次复审

打开 [复审页面](index.html)。原图通过仓库相对路径读取，保持目录结构；不需要网络、不提供ZIP。

当前执行规则：[两人审核归并与二次复核SOP](../../docs/thesis_main/两人审核归并与二次复核SOP_20260925.md)。一正独审69图与双方全部曾选排除126份必须复核；本轮以两份JSON为主，历史材料辅助。

配套报告：[逐图疑问](逐图疑问汇总.md)、[同房疑问](同房疑问汇总.md)、[原始核验与修复](原始核验与修复说明.md)、[人员候选统计](人员候选统计.md)。

## 已核验范围

- 两份审核共{summary['events']}条记录，对应{summary['reviewed_annotations']}份作答、{summary['images']}图；{summary['nonempty_comments']}条非空评论均有逐条释义。
- 同作答交叠{summary['overlap_annotations']}份，选项代码不同{summary['verdict_disagreements']}份，不能解释为意见冲突。两位作者的原选项分别统计，不合并为有效性判断。
- 默认仅{summary['followup_images']}张有具体未决问题的图片、{summary['followup_annotations']}份相关作答进入复核提示；239张是完整查阅库，不是全部重审任务。
- 当前全部3019份原始导出核验结果见 [source_audit.json](source_audit.json)。当前页面可核验，不代表能还原旧浏览器缓存与当时选择的参考层。
- 同房支持覆盖{summary['room_supported_images']}图；其余{summary['room_unknown_images']}图不推测房间归属。

## 研究与裁决边界

门洞相关图先全部单列；已有OOS条件或评论线索同样单列，含疑似或反转意见的保持待确认。暂不做这些图的人员GT-IoU／质心评价或3D。图片范围、参考可信性、具体作答执行质量、计算失败分开记录。所有保留都不自动等于符合GT；GT存疑也不自动等于每一种标法都合理。原始及人工修订GT不改。

共识稳定和靠近GT是不同问题；无法形成有效区域时保留失败，不能硬造共识。分簇默认共享x后的全局亲近度，完整链接仅对照；沿现有25.6px阈值和同点数门，属于探索性几何分区，不是合理空间的真值。仅点集匹配者复用。该层不随临时裁决自动重算。

原始／有效／共享x点分层。共享x点的3D仅沿已有配对环，不拟合Manhattan，不代表正确顺序；本轮顺序编辑禁用。修复确认只记录意见，绝不立即补删点；借用补点注明供体，不恢复为独立票。新旧冲突交用户确认，历史结果不追改。

人员统计见 [workers.json](workers.json)，按图片单列状态与manual/oos/semi分层；reviewer_options按作者分别保留原选项，不跨作者合并。你的“待定”表示不确定且想复核；GT问题或不同标法可能选“GT与范围争议”或“保留”（后期保留较多）；门洞/OOS通常选范围争议或待定；部分配对/顺序问题选“配对”。一正的GT与范围争议表示标注本身可接受、只是范围不同，不能解释为GT错误。不能将定向可疑队列比例解释为人员总体错误率。

## 数据与接口

- `evidence/user_review.json`、`evidence/yizheng_review.json`：用户附件原字节；任何构建不会把旧选项导入新最终裁决。
- `commentary.json`：1544审核事件，event_id=reviewer:canonical_id；原评论及逐条释义、对象层次、跨人/同图引用和未决指代。人工整理的释义不是新增标注真值。
- `images.json`、`rooms.json`：每图一次，图级疑问、历史来源及受支持同房映射；`geometry_hold/quality_hold`仅本轮暂缓标志。
- `source_audit.json`、`repair_history.json`：原始task/annotation/region与点坐标对应；已执行、提出未应用的修复及真实配对失败原因。
- 页面数据 `review_reconciliation_v1`；本轮裁决 `review_reconciliation_decisions_v1`，binding.id=`review_reconciliation_20260925_v1`。新image_decisions和annotation_decisions独立保存，初始为空。
- 图级记录status(pending/resolved)、category(doorway/doorway_difficult/doorway_annotatable/oos/reference_concern/ordinary/undetermined)、comment、updated_at；旧doorway保留难度未分。作答记录status、verdict(usable/invalid/repair_needed/undetermined)、comment、repair_confirmation(unreviewed/confirm_existing/needs_followup/reject_proposal)、updated_at、view_context。待修复/未确定保持未解决。
- shared_image_context_event_ids和same_image_links保留同图图片说明与引用候选；含“同图”的引用评论不互相充当背景来源，其原文仍保留，缺失明确记录，不传播个人排除。scene_rule只召回条件核查，不确认OOS或自动排除。
- 新记录导入严格核对版本、ID及字段；旧文件只读查看，不能覆盖新结论。浏览器localStorage独立保存，跨浏览器请导出备份。

## 使用

先按复核任务选择：全部、一正复核、全部排除、补点修复、标准一致性、资料库；再用图片线索筛门洞/OOS/配对/待定。默认队列完整覆盖一正独审图、双方所有排除作答，并保留明确待定、具体评论、相似排除差异、修复询问和场景点数核对。followup_reasons逐条记录入选依据和相关作答，followup_ids是对照对象，不要求全部重新打标签。确认OOS少于8有效点会预选排除建议但不自动保存；跨门槛修复先核验，难标门洞不直接套阈值。图级确认不改成员有效性。新判断独立保存，旧数据不覆盖。

复建：`python -m tools.thesis_main.analysis.build_review_reconciliation_20260925`。首建需Downloads中两份原件；之后优先使用本目录evidence原件，可用--user-review/--yizheng-review显式指定。审核证据与逐条释义不匹配时中止，不猜测继承。
'''
    (out / 'README.md').write_bytes(readme.encode('utf-8'))


def build(out=OUT, user_review=None, yizheng_review=None):
    from .review_reconciliation_audit_20260925 import audit
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / 'evidence').mkdir(exist_ok=True)
    (out / 'cases').mkdir(exist_ok=True)
    paths = {'user': user_review, 'yizheng': yizheng_review}
    names = {'user': '全历史标注_我的审核_20260923(1).json', 'yizheng': '全历史标注_我的审核_20260923 一正.json'}
    documents = {}
    for who, specified in paths.items():
        target = out / 'evidence' / (who + '_review.json')
        source = Path(specified) if specified else target if target.exists() else Path.home() / 'Downloads' / names[who]
        original = source.read_bytes()
        if target.exists() and target.read_bytes() != original:
            raise ValueError('本轮证据原件已存在且内容不同，请使用新输出目录：' + who)
        documents[who] = json.loads(original.decode('utf-8-sig'))
        if not target.exists(): target.write_bytes(original)
    old = ROOT / 'analysis_results/consensus_visual_review_20260923'
    index = {r['id']: r for r in read_js(old / 'data.js')['rows']}
    notes = read(HERE / 'review_reconciliation_notes_20260925.json')
    if notes['schema'] != 'review_reconciliation_notes_v1': raise ValueError('评论释义schema漂移')
    events = collect_events(documents, index, notes['events'])
    write(out / 'commentary.json', events)
    write(out / 'evidence/comment_interpretations.json', notes)
    source_audit = audit(ROOT)
    write(out / 'source_audit.json', source_audit)
    if source_audit['failures']: raise ValueError('原始核验失败；详情见source_audit.json，不生成审查页')
    print('原始核验完成，接入图片与Studio。', flush=True)
    image_ids = {e['image_id'] for e in events}
    if len(events) != 1544 or len(image_ids) != 239: raise ValueError('本轮审核数量漂移')
    registry = json.load(gzip.open(ROOT / 'analysis_results/consensus_research_20260923/inputs/room_registry.json.gz', 'rt', encoding='utf-8'))
    rooms, room_map = supported_rooms(registry, image_ids)
    historical = historical_evidence(ROOT)
    by_image, by_id = defaultdict(list), defaultdict(list)
    for e in events: by_image[e['image_id']].append(e); by_id[e['canonical_annotation_id']].append(e)
    cases, image_reviews, variant_count = [], {}, 0
    for iid in sorted(image_ids, key=lambda i: next(e['code'] for e in by_image[i])):
        old_case = read_js(old / 'cases' / (iid + '.js'))
        rows = [index[a['canonical_annotation_id']] for a in old_case['annotations']]
        review = derive_image_review(rows, by_image[iid], notes['images'].get(old_case['code'], {}), source_audit['annotations'])
        add_comment_and_cluster_questions(review, old_case['annotations'], by_image[iid])
        existing = {(h['source'], h['quote']) for h in review['history']}
        review['history'].extend(h for h in historical[iid] if (h['source'], h['quote']) not in existing)
        if any(h.get('doorway_related') for h in historical[iid]):
            if 'doorway' not in review['flags']: review['flags'].append('doorway')
            if 'historical' not in review['flags']: review['flags'].append('historical')
            review['geometry_hold'] = review['quality_hold'] = True
            review['questions'].append(dict(title='历史记录含门洞确认、疑似或无法判断；与本轮原话一起确认是否继续单列，暂不恢复人员评价。',
                kind='historical', workers=[], evidence_event_ids=[]))
        add_scene_point_checks(review, source_audit['annotations'])
        review.update(room_id=room_map.get(iid), room_label=room_map.get(iid, '同房尚未确认'))
        image_reviews[iid] = review
        variants = []
        for a in old_case['annotations']:
            cid = a['canonical_annotation_id']; au = source_audit['annotations'][cid]
            pairs = a['pairs_shared_x']
            shared = [p for pair in pairs for p in pair] if pairs is not None else []
            geom, error = geometry(pairs, au['shared_x_point_labels'], review['geometry_hold'])
            for event in by_id[cid]:
                if '修复核查' in (event.get('interpretation') or {}).get('topics', []):
                    au.setdefault('current_review_questions', []).append(dict(event_id=event['event_id'], comment=event['comment']))
                    au['history'].append(dict(source=event['source_file'], quote=event['comment'],
                        interpretation='本轮修复询问或建议；请对照已执行修复记录确认，不重复修复、不自动应用。', event_id=event['event_id']))
            source = dict(canonical_annotation_id=cid, worker_id=a['worker_id'], condition=a['raw_condition'], role='annotation',
                raw_points=a['raw_points_1024x512'], effective_points=a['effective_points_1024x512'] or [],
                shared_x_points=shared, raw_point_labels=au['raw_point_labels'], effective_point_labels=au['effective_point_labels'],
                shared_x_point_labels=au['shared_x_point_labels'], events=by_id[cid], audit=au,
                clusters={m['method']: m['label'] for m in a['screening']['clusters']},
                cluster_coverage=a['screening']['cluster_coverage'],
                geometry_basis='既有上下配对共享x；保持当前环序，非已确认连接顺序',
                imputed_point=a['imputed_point'], known_wrong_history=a['known_wrong'],
                known_wrong_source=a['known_wrong_source'])
            variants.append(dict(name=f"{a['worker_id']} · {a['raw_condition']}", source=source, geometry=geom, error=error))
        for ref in old_case['references']:
            raw = ref['raw_points'] or []
            pairs = ref['pairs_shared_x']; shared = [p for pair in pairs for p in pair] if pairs is not None else []
            labels = ['p' + str(i+1) for i in range(len(raw))]
            shared_labels = ['参考配对点' + str(i+1) for i in range(len(shared))]
            geom, error = geometry(pairs, shared_labels, review['geometry_hold'])
            variants.append(dict(name=REF_NAMES[ref['name']], geometry=geom, error=error,
                source=dict(role='dataset_reference', reference_name=ref['name'], worker_id='', condition='reference',
                    raw_points=raw, effective_points=raw, shared_x_points=shared, raw_point_labels=labels,
                    effective_point_labels=labels, shared_x_point_labels=shared_labels, events=[],
                    audit=dict(source=ref['source'], repairs=[], history=[], pairing=dict(status=ref['pairing_status'], description=ref.get('reason'))),
                    clusters={}, cluster_coverage='reference_not_participant', geometry_basis=ref['pairing_basis'])))
        case = dict(image_id=iid, code=old_case['code'], title=old_case['code'], category='两人审核 · 问题导向二审',
            review=review, history_script='cases/' + iid + '.js', history_loaded=False, variants=[])
        idx = len(cases); cases.append(case)
        payload = dict(history_loaded=True, variants=variants, review=review)
        image_path = (old / old_case['image_src']).resolve()
        image = dict(original=Path(os.path.relpath(image_path, out)).as_posix(), texture=data_image(image_path, texture=True))
        script = f'window.STUDIO_IMAGES[{idx}]=' + json.dumps(image, ensure_ascii=False, separators=(',', ':')) + ';\n'
        script += f'Object.assign(window.STUDIO_DATA.cases[{idx}],' + json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + ');\n'
        (out / 'cases' / (iid + '.js')).write_bytes(script.encode('utf-8'))
        variant_count += len(variants)
        if len(cases) % 50 == 0: print(f'已构建{len(cases)}/{len(image_ids)}张图。', flush=True)
    counts = Counter(e['canonical_annotation_id'] for e in events)
    disagreements = sum(len({e['verdict'] for e in by_id[cid]}) > 1 for cid in counts)
    summary = dict(events=len(events), reviewed_annotations=len(counts), images=len(cases),
        nonempty_comments=sum(bool(e['comment'].strip()) for e in events), overlap_annotations=sum(v > 1 for v in counts.values()),
        verdict_disagreements=disagreements, pending_annotations=sum(any(e['verdict'] == 'pending' for e in v) for v in by_id.values()),
        reviewer_options={who: dict(Counter(e['verdict'] for e in events if e['reviewer'] == who)) for who in ('user', 'yizheng')},
        followup_images=sum('followup' in c['review']['flags'] for c in cases),
        followup_annotations=sum(len(c['review']['followup_ids']) for c in cases),
        room_supported_images=len(room_map), room_unknown_images=len(cases)-len(room_map),
        doorway_hold_images=sum('doorway' in c['review']['flags'] for c in cases),
        oos_hold_images=sum('oos' in c['review']['flags'] for c in cases),
        final_decisions_applied=0, raw_or_gt_changes=0)
    workers = worker_summary(index, events, image_reviews, source_audit['annotations'])
    data = dict(schema='review_reconciliation_v1', binding=dict(id='review_reconciliation_20260925_v1'),
        counts=dict(cases=len(cases), variants=variant_count),
        cases=cases, reconciliation=dict(summary=summary, rooms=rooms, workers=workers))
    (out / 'data.js').write_bytes(('window.STUDIO_DATA=' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) +
        ';\nwindow.STUDIO_IMAGES={};\n').encode('utf-8'))
    for name, value in [('images.json', cases), ('rooms.json', rooms), ('workers.json', workers), ('MANIFEST.json', summary)]: write(out / name, value)
    write(out / 'source_audit.json', source_audit)
    reports(out, summary, cases, events, rooms, workers, source_audit)
    studio = ROOT / 'tools/label_studio/panorama_studio'
    for name in ['studio.js', 'studio.css']: shutil.copyfile(studio / name, out / name)
    vendor = ROOT / 'analysis_results/panorama_studio_20260907_v3'
    for name in ['three.min.js', 'OrbitControls.js']: shutil.copyfile(vendor / name, out / name)
    for ext in ['js', 'css']: shutil.copyfile(HERE / ('review_reconciliation_panel_20260925.' + ext), out / ('review.' + ext))
    html = (studio / 'index.html').read_text(encoding='utf-8')
    html = html.replace('<title>空间标本 · 全景布局审查</title>', '<title>两人审核 · 二次复审</title>')
    html = html.replace('</head>', '<link rel="stylesheet" href="review.css"></head>')
    html = html.replace('</body>', '<script defer src="review.js"></script></body>')
    (out / 'index.html').write_bytes(html.encode('utf-8'))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--user-review', type=Path)
    parser.add_argument('--yizheng-review', type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.out, args.user_review, args.yizheng_review), ensure_ascii=False))
