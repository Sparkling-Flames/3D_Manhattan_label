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
    result['historical_source_audit'] = dict(**audit, calculation_index=str(HISTORY.relative_to(ROOT)),
        definition='既有canonical计算快照，经任务/标注/人员/图像ID回查18份原导出；未重扫所有新导出。0仅指快照未找到。',
        high_people_threshold=19, threshold_note='沿用旧高人数探索展示门槛；不是足以收敛的判据。',
        source_paths=sorted({r['raw_export_path'] for r in rows}))
    result['ranking_rules'] = dict(status='探索性候选顺序，非最终派发或验证样本冻结',
        low_ambiguity='已满足可比性且无OOS疑问：优先+相近且>=3图为批次1；优先+小幅歧义/评论问题且>=3图为批次2；基础>=3图与优先2图并列批次3；基础2图为批次4。',
        within_batch='先已有>=19人图数，再组图数、已标图数、相近/小幅歧义、评论问题；这是无加权分数的暂定安排。',
        alternative_order='room_size_order独立按图数排序，保留可比性与OOS待定标记；不能将排序条目数视为独立房间数。',
        uncertainty='小幅歧义描述预期比较差异，不等于绝对低难度；难图单列分歧研究，不认定持续增簇。',
        review_scope='旧粗类只亲审cross_reviews有非支持意见的41图；38图保留旧讨论；其他569图不声称亲审。本次260组全部已看，状态空白不等于漏审，待定不自动转确认。')
    result['input_integrity'] = dict(original_spatial_source_unchanged=True, original_pair_evidence_unchanged=True,
        user_review_snapshot=str(args.review.relative_to(ROOT)) if args.review.is_relative_to(ROOT) else str(args.review),
        comment_interpretation='group_comment_interpretation_20260912.json')
    (OUT / 'same_room_selection_registry_20260912.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
    print(json.dumps(result['summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()
