"""全量审核台账：最新复核优先；原件不变，修复与研究资格分列。"""
import csv
import copy
import gzip
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/review_final_20260928'
DOWNLOADS = Path('C:/Users/ASUS/Downloads')
FILES = {
    'user': '全历史标注_我的审核_20260923(1).json',
    'yizheng': '全历史标注_我的审核_20260923 一正.json',
    'second': '全历史标注_二次复核_20260925(2).json',
    'previous_return': '全历史标注_定向补审_20260927.json',
    'latest': '全历史标注_定向补审_20260927(1).json',
    'continuation': '全历史标注_未决续审_20260928.json',
    'coverage': '全历史标注_图片覆盖补审_20260928.json',
}
COVERAGE_HOLD = 'pRbA3pwrgk9_bc9ae89832854c19a69741f97291efad'
WC61 = 'wc2JMjhGNzB_e6693f97b36545f7a76e03c3fe32ba8c'
IMPROVEMENT = {'f8c20f06811c7321e708', 'new_95_3663_7443_W028', '1623fbedf957f0be9421'}
SUPPLEMENTED = {'6c4eb5c014ae5538', 'd0df2148541db2cf', 'new_94_3628_7046_W037'}
CONTINUATION_IMAGES = {
    'S9hNv5qa7GM_2ea5348654d24115bba3dcdb21fa655e': '最终确定存在空间范围的歧义',
    'uNb9QFRL6hY_6a500a9a43a340eb817c58bb084327fe': '先不进入主分析,因为gt也不太对,这图也很怪',
    'uNb9QFRL6hY_a372582c11864f31a9dd174e4a0ae6ad': '只标内侧空间,类似簇1',
    'rPc6DW4iMge_1f14902595544e389c9c910c444e79e7': '直接排除,这些都是错误的标注,但是竟然有三个人是出现了同一个问题,得额外记录',
    'wc2JMjhGNzB_ec04ef10a0664e94878aa2d0f1720c2f': '直接排除',
}
EXCLUDED_BY_ISSUE = {'4a1158da9bd83ef9','6aed1eb1185c1318','6d192755ca096a2c','032cd152706166629e82'}
MIXED_SCENES = {
    'pRbA3pwrgk9_0350fc96e88c4a52886d4eb50b2d52c6': '严格来说也是oos,gt的标注空间是整个房间,簇2只标了 左边的厕所区域',
    'pRbA3pwrgk9_8b07a4b08cf447abb246769d8dce8494': '门洞交界且oos',
}


def scene_dimensions(category, mixed=False):
    """未记录不是否定；OOS适用性与门洞位置分别存储。"""
    return dict(oos_status='confirmed' if mixed or category in {'oos','oos_stable_nonorthogonal'} else 'not_recorded',
                doorway_status={'doorway_difficult':'difficult','doorway_annotatable':'annotatable','doorway':'confirmed_unspecified'}.get(category,'not_recorded'))


def read(path):
    path = Path(path)
    with (gzip.open(path, 'rt', encoding='utf-8-sig') if path.suffix == '.gz' else path.open(encoding='utf-8-sig')) as f:
        return [json.loads(s) for s in f if s.strip()] if '.jsonl' in path.name else json.load(f)


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def choose_decision(latest, second, old):
    for source, value in [('latest', latest), ('second', second), ('historical_user', old)]:
        if value is not None:
            return value, source
    return {}, 'not_individually_reviewed'


def repair_authorized(decision):
    return decision.get('verdict') == 'repair_needed'


def coverage_decision(iid, record):
    """补审以图片为对象；view_context不是个人裁决。只显式更正wc-61漏选。"""
    if (record['status'] not in {'resolved','pending','draft'} or
        record['oos'] not in {'','in_scope','oos','stable_nonorthogonal','pending'} or
        record['doorway'] not in {'','none','annotatable','difficult','pending'} or
        not isinstance(record['comment'],str) or not isinstance(record['tags'],list) or
        not set(record['tags']) <= {'reference_error','reference_omission','detail','scope','reference_uncertain'}):
        raise ValueError('invalid_coverage_decision:'+iid)
    tags = ['scope'] if iid == WC61 else list(record['tags'])
    category = {'in_scope':'ordinary','oos':'oos','stable_nonorthogonal':'oos_stable_nonorthogonal'}.get(record['oos'],'unconfirmed')
    if category == 'ordinary' and record['doorway'] in {'annotatable','difficult','pending'}:
        category = {'annotatable':'doorway_annotatable','difficult':'doorway_difficult','pending':'doorway'}[record['doorway']]
    evidence=dict(source='evidence/coverage.json#/decisions/'+iid,raw_record=record,
                  effective_tags=tags,user_clarification='用户本轮明确：wc-61只勾选空间范围不同，先前漏选。' if iid==WC61 else '')
    return (dict(status=record['status'],category=category,comment=record['comment'],updated_at=record['updated_at'] if 'updated_at' in record else ''),
            dict(tags=tags,status=record['status']), evidence)


def write_csv(path, rows):
    if not rows:
        raise ValueError('empty_report:'+str(path))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list,bool)) else v for k,v in row.items()})


def worker_report(rows):
    groups=defaultdict(list)
    for row in rows:
        groups[row['worker_id']].append(row)
    result=[]
    for worker,group in sorted(groups.items()):
        excluded=[r for r in group if r['cleaning_disposition']=='excluded_by_review']
        special=lambda r: r['scene_oos_status']=='confirmed' or r['scene_doorway_status']=='difficult'
        normal=lambda r: r['scene_category']=='ordinary' and not special(r)
        result.append(dict(worker_id=worker,total_responses=len(group),individually_reviewed=sum(r['individual_review_covered'] for r in group),
            explicitly_excluded=len(excluded),excluded_manual=sum(r['condition']=='manual' for r in excluded),
            excluded_semi=sum(r['condition']=='semi' for r in excluded),
            excluded_condition_oos=sum(r['condition']=='oos' for r in excluded),
            normal_total=sum(normal(r) for r in group),normal_excluded=sum(normal(r) for r in excluded),
            oos_difficult_doorway_total=sum(special(r) for r in group),oos_difficult_doorway_excluded=sum(special(r) for r in excluded),
            other_or_unclassified_total=sum(not normal(r) and not special(r) for r in group),
            other_or_unclassified_excluded=sum(not normal(r) and not special(r) for r in excluded),
            historical_not_accepted=sum(r['cleaning_disposition']=='historical_not_accepted' for r in group),
            scene_or_analysis_restricted=sum(r['worker_quality_gate'] in {'hold_all_analysis','hold_main_analysis','out_of_primary_scene','hold_scene_or_reference','hold_reference_quality'} for r in group),
            awaiting_decision=sum(r['needs_user_review'] for r in group),
            retained_representation_or_history=sum(r['cleaning_disposition']=='retained_pending' for r in group),
            repair_needed_not_applied=sum(r['verdict']=='repair_needed' and r['repair_status']!='applied' and r['cleaning_disposition'] not in {'excluded_by_review','historical_not_accepted'} for r in group),
            excluded_annotation_ids=[r['canonical_annotation_id'] for r in excluded]))
    return sorted(result,key=lambda r:(-r['explicitly_excluded'],r['worker_id']))


def recover_scene(image_id, decision, comments):
    """仅恢复已逐条阅读确认的旧意见；结构化二审/最新意见绝不被旧评反转。"""
    if decision:
        return decision.get('category', 'unconfirmed'), []
    if image_id == '2t7WUuJeko7_53937db036374126830e0f1203b04ead':
        matches = [e for e in comments if e['event_id'] == 'user:new_95_3649_7457_W030'
                   and e['comment'] == '这图是门洞交界处,不好标']
        if len(matches) != 1:
            raise ValueError('reviewed_scene_evidence_changed:' + image_id)
        return 'doorway_difficult', [dict(source='evidence/user.json#/decisions/new_95_3649_7457_W030',
            quote=matches[0]['comment'], interpretation='原审核明确难标门洞；仅恢复图片属性，不更改个人保留/排除。')]
    return 'unconfirmed', []


def build():
    from .review_reconciliation_audit_20260925 import verify_raw, same
    OUT.mkdir(exist_ok=True)
    evidence = OUT / 'evidence'
    evidence.mkdir(exist_ok=True)
    docs = {}
    for key, name in FILES.items():
        src, dst = DOWNLOADS / name, evidence / (key + '.json')
        if dst.exists() and dst.read_bytes() != src.read_bytes():
            raise ValueError('evidence_changed:' + key)
        shutil.copyfile(src, dst)
        docs[key] = read(dst)
    latest, second = copy.deepcopy(docs['latest']), docs['second']
    if latest['schema'] != 'review_return_decisions_v2' or latest['binding'] != {'id':'review_return_20260927_v1'}:
        raise ValueError('latest_schema_or_binding_changed')
    continuation=docs['continuation']
    manifest=read(ROOT/'analysis_results/review_continue_20260928/manifest.json')
    if continuation['schema']!='review_return_decisions_v2' or continuation['binding']!=manifest['binding']:
        raise ValueError('continuation_binding_mismatch')
    if not set(continuation['image_decisions'])<=CONTINUATION_IMAGES.keys() or not set(continuation['annotation_decisions'])<=set(manifest['annotation_ids']):
        raise ValueError('continuation_outside_five_image_scope')
    if set(continuation['issue_decisions']) != {iid+':continue' for iid in CONTINUATION_IMAGES}:
        raise ValueError('continuation_issue_scope_changed')
    for iid,quote in CONTINUATION_IMAGES.items():
        issue=continuation['issue_decisions'][iid+':continue']
        if issue['status']!='resolved' or issue['comment']!=quote:
            raise ValueError('continuation_requires_new_semantic_review:'+iid)
    for key in ['image_decisions','annotation_decisions','traits']:
        latest[key].update(continuation[key])
    coverage_doc=docs['coverage']
    coverage_manifest=read(ROOT/'analysis_results/review_coverage_followup_20260928/manifest.json')
    if coverage_doc['schema']!='coverage_followup_decisions_v1' or coverage_doc['binding']!=coverage_manifest['binding'] or set(coverage_doc['decisions'])!=set(coverage_manifest['image_ids']):
        raise ValueError('coverage_binding_or_scope_changed')
    coverage_evidence={}
    for iid,record in coverage_doc['decisions'].items():
        decision,traits,ev=coverage_decision(iid,record)
        latest['image_decisions'][iid]=decision
        previous_traits=latest['traits'].get('image:'+iid,{})
        latest['traits']['image:'+iid]={**previous_traits,**traits}
        coverage_evidence[iid]=ev
    applied_coverage=copy.deepcopy(coverage_doc)
    applied_coverage['decisions'][WC61]['tags']=['scope']
    applied_coverage['clarifications']={WC61:coverage_evidence[WC61]['user_clarification']}
    dump(OUT/'图片覆盖补审_已合并.json',applied_coverage)
    for iid,quote in MIXED_SCENES.items():
        if latest['image_decisions'][iid]['comment']!=quote:
            raise ValueError('mixed_scene_evidence_changed:'+iid)
    base = read(ROOT / 'analysis_results/consensus_research_20260923/inputs/annotations.jsonl.gz')
    index = {r['canonical_annotation_id']: r for r in base}
    if len(index) != len(base) or len(base) != 3152:
        raise ValueError('base_population_changed')
    image_ids = {r['image_id'] for r in base}
    for iid,record in coverage_doc['decisions'].items():
        viewed=record.get('view_context',{}).get('annotation_id')
        if viewed not in index or index[viewed]['image_id']!=iid:
            raise ValueError('coverage_view_context_identity_mismatch:'+iid)
    for name, d in docs.items():
        if name!='coverage' and not set(d.get('annotation_decisions', d.get('decisions', {}))) <= index.keys():
            raise ValueError('unknown_annotation:' + name)
        if not set(d.get('image_decisions', {})) <= image_ids:
            raise ValueError('unknown_image:' + name)
    audit = read(ROOT / 'analysis_results/review_reconciliation_20260925/source_audit.json')['annotations']
    images = {r['image_id']:r for r in read(ROOT / 'analysis_results/review_reconciliation_20260925/images.json')}
    events = read(ROOT / 'analysis_results/review_reconciliation_20260925/commentary.json')
    by_ann, by_image = defaultdict(list), defaultdict(list)
    for e in events:
        by_ann[e['canonical_annotation_id']].append(e)
        if e['comment'].strip():
            by_image[e['image_id']].append(e)
    rooms = read(ROOT / 'analysis_results/consensus_research_20260923/inputs/room_registry.json.gz')
    room_map = {}
    for room in rooms['candidates']:
        if room['physical_same_supported']:
            for iid in set(room['image_ids']) & image_ids:
                if iid in room_map:
                    raise ValueError('duplicate_room_binding')
                room_map[iid] = room
    trap = read(ROOT / 'analysis_results/review_return_20260927/trap_inventory.json')['annotations']
    second_notes = read(ROOT / 'tools/thesis_main/analysis/review_return_notes_20260927.json')['comments']
    second_by_image = defaultdict(list)
    for note in second_notes:
        second_by_image[note['image_id']].append(note)
    cluster_refs = defaultdict(list)
    for ref in read(ROOT / 'analysis_results/review_return_20260927/audit.json')['cluster_references']:
        cluster_refs[ref['image_id']].append(dict(comment=ref['comment'],scope=ref['scope'],annotation_id=ref['annotation_id'],
            method=ref['method'],point_version=ref['point_version'],mentioned_labels=ref['mentioned_labels'],
            groups={label:[{k:m[k] for k in ['annotation_id','worker','condition','point_version']} for m in members]
                    for label,members in ref['groups'].items()},unresolved_labels=ref['unresolved_labels']))
    closeout = ROOT / 'analysis_results/review_closeout_20260928'
    old_overrides = read(closeout / 'effective_point_overrides.json')
    # 保留旧执行快照；撤销作为新事件，不删除审计证据。
    prior_path = evidence / 'prior_effective_point_overrides.json'
    if not prior_path.exists():
        dump(prior_path, old_overrides)
    prior = read(prior_path)
    plans = {p['annotation_id']:p for p in read(closeout / 'repair_proposals.json')['plans']}
    overrides = {cid:r for cid,r in prior['annotations'].items() if cid not in IMPROVEMENT}
    repair_events = [dict(annotation_id='f8c20f06811c7321e708', operation='revoke_delete_p9_p10',
                         reason='用户明确：改善建议，非修复指令；恢复修复前14点。', prior=prior['annotations']['f8c20f06811c7321e708'])]
    for cid in ['2559d23544f7b937','af1ada91e5648762','3d1c6d9fda198b1b']:
        if not repair_authorized(latest['annotation_decisions'][cid]):
            raise ValueError('repair_verdict_required:' + cid)
        p = plans[cid]
        option = p['options'][0]
        overrides[cid] = dict(annotation_id=cid, image_id=p['image_id'], code=p['code'], worker=p['worker'],
            source=p['source'], before_points=p['before_points'], before_labels=p['before_labels'],
            effective_points=option['after_points'], effective_point_labels=option['after_labels'],
            operation=option['name'], status='applied_effective_override',
            approval='用户本轮明确选择uNb47删p14，其余已展示补点方案没问题；最新选项repair_needed',
            instruction=latest['annotation_decisions'][cid]['comment'],
            geometry_status='changed_points_not_recomputed')
        repair_events.append(overrides[cid])
    assert len(overrides) == 9
    corrected = dict(schema='review_effective_overrides_20260928_v2', applied=True, annotations=overrides,
        revoked_annotation_ids=['f8c20f06811c7321e708'],
        merge_contract='覆盖canonical ID有效点；撤销项回到本轮修复前基线。原始点和GT不变；变化点集旧几何结果作废。')
    dump(OUT / 'effective_point_overrides.json', corrected)
    dump(OUT / 'repair_events.json', repair_events)
    clarifications = read(closeout / 'clarifications.json')
    holds = {r['image_id'] for r in clarifications['image_analysis_holds']}
    if '暂时先不搞' not in coverage_doc['decisions'][COVERAGE_HOLD]['comment']:
        raise ValueError('coverage_hold_comment_changed')
    holds.add(COVERAGE_HOLD)
    stable = set(clarifications['stable_nonorthogonal_image_ids'])
    semantic_path = OUT / 'semantic_findings.json'
    semantic = read(semantic_path) if semantic_path.exists() else {}
    # 原独立释义仍保存；最新问题卡明确覆盖旧pending，不伪改上传的原选项。
    for iid,quote in CONTINUATION_IMAGES.items():
        si=semantic['image_overrides'].setdefault(iid,{})
        si.update(semantic_status='resolved_by_continuation_issue',summary=quote,reason=quote,
                  needs_user_review=False,classification_resolved=True,source='evidence/continuation.json#/issue_decisions/'+iid+':continue')
        if iid.startswith('S9hNv5qa7GM_'):
            si['tags']=sorted(set(si.get('tags',[]))|{'scope'})
    for cid in EXCLUDED_BY_ISSUE:
        semantic['annotation_overrides'][cid]=dict(semantic_status='excluded_by_explicit_continuation',
            summary='最新问题卡直接排除当前作答；不再以历史补点为前置条件。',reason='用户明确排除',
            needs_user_review=False,conditional_history=False,tags=[],source='evidence/continuation.json#/issue_decisions')
    for iid,ev in coverage_evidence.items():
        record=ev['raw_record'];gt_source=record.get('view_context',{}).get('gt_source','')
        gt_note=('当前查看来源为人工修订文件：'+gt_source if 'groudTruth.json' in gt_source else
                 '当前查看来源为原始Matterport标签：'+gt_source if 'mp3d_layout/' in gt_source else '本次未记录参考来源；不推断GT版本')
        if iid=='e9zR4mvMWw7_409f2a738bf54153b9b77c39e7a4ea45':
            gt_note+='；用户明确原始GT采用不同空间，人工修订GT没有该问题。'
        semantic['image_overrides'][iid]=dict(semantic_status='resolved_by_coverage_followup',summary=record['comment'],
            reason='本次图片补审；pRb-16按原话暂缓全部分析' if iid==COVERAGE_HOLD else '最新图片补审明确选项',
            needs_user_review=record['status']!='resolved',classification_resolved=record['oos'] not in {'','pending'},
            tags=ev['effective_tags'],source=ev['source'],gt_version_note=gt_note)
    dump(OUT/'current_semantic_findings.json',semantic)
    cache, failures, rows = {}, [], []
    for cid, b in index.items():
        iid, pv = b['image_id'], b.get('provenance') or {}
        a = audit.get(cid, {})
        source = a.get('source') or dict(path=b.get('raw_export_path') or pv['source'],
            project=int(pv.get('project') or re.search(r'project-(\d+)', b.get('raw_export_path') or pv['source'])[1]),
            task=int(b.get('runtime_task_id') or pv['task']), annotation=int(b.get('raw_annotation_id') or pv['annotation']),
            worker=b['worker_id'], image_id=iid, condition=b['raw_condition'])
        verified, verify_error = False, ''
        try:
            path = source.get('mirror_path') or source['path']
            if path not in cache:
                cache[path] = {t['id']:t for t in read(ROOT / path)}
            task = cache[path][source['task']]
            matches = [v for v in task['annotations'] if v['id'] == source['annotation']]
            if len(matches) != 1:
                raise ValueError('raw_annotation_not_unique')
            verify_raw(source, b['raw_points_1024x512'], task, matches[0])
            verified = True
        except (ValueError, KeyError, FileNotFoundError) as exc:
            verify_error = str(exc)
            failures.append(dict(annotation_id=cid, error=verify_error, source=source))
        d, ds = choose_decision(latest['annotation_decisions'].get(cid), second['annotation_decisions'].get(cid), docs['user']['decisions'].get(cid))
        if cid in continuation['annotation_decisions']:
            ds='continuation_annotation'
        y = docs['yizheng']['decisions'].get(cid)
        image_d = latest['image_decisions'].get(iid) or second['image_decisions'].get(iid) or {}
        it = latest['traits'].get('image:' + iid, {})
        at = latest['traits'].get('annotation:' + cid, {})
        tags = set(it.get('tags', []))
        individual_tags = set(at.get('tags', []))
        si = semantic.get('image_overrides', {}).get(iid, {})
        sa = semantic.get('annotation_overrides', {}).get(cid, {})
        tags.update(si.get('tags', []))
        individual_tags.update(sa.get('tags', []))
        category, recovered_scene_evidence = recover_scene(iid, image_d, by_image[iid])
        if iid in stable:
            category = 'oos_stable_nonorthogonal'
        verdict = {'retain':'usable','pending':'undetermined','gt_scope':'retained_scope_variation','representation':'representation_pending'}.get(d.get('verdict'), d.get('verdict','not_individually_reviewed'))
        status = d.get('status', 'historical' if d else 'not_individually_reviewed')
        semantic_status = status
        reasons = []
        if cid in SUPPLEMENTED:
            semantic_status = 'resolved_by_latest_and_user_clarification'
        elif cid in IMPROVEMENT:
            semantic_status = 'resolved_improvement_only'
        elif cid in overrides:
            semantic_status = 'repair_applied'
        elif status == 'pending':
            semantic_status = 'pending_recorded_not_missing'
            reasons.append('latest_pending_requires_semantic_check')
        elif verdict in {'undetermined','representation_pending'}:
            reasons.append('unresolved_individual')
        if ds == 'not_individually_reviewed' and y:
            if y['verdict'] in {'retain','gt_scope'}:
                verdict = 'historical_retained_with_latest_image_context' if image_d else 'historical_retained_scene_unrecorded'
                semantic_status = 'historical_yizheng_retained_not_new_user_verdict'
            elif y['verdict'] == 'representation':
                verdict = 'representation_pending'
                semantic_status = 'representation_deferred_not_quality_error'
            else:
                verdict = 'historical_yizheng_only'
        if ds == 'historical_user' and verdict == 'representation_pending':
            semantic_status = 'representation_deferred_not_quality_error'
            reasons = []
        if cid == '78a68354a388042f':
            semantic_status = 'existing_shared_x_meets_requested_alignment'
            reasons = []
        if cid == 'e367c19601f2d8e7823e':
            semantic_status = 'latest_doorway_context_resolves_old_scene_question'
            reasons = []
        if sa:
            if cid not in overrides:
                semantic_status = sa['semantic_status']
            reasons = [sa['reason']] if sa.get('needs_user_review') else []
        issue=continuation['issue_decisions'].get(iid+':continue')
        if cid in EXCLUDED_BY_ISSUE:
            verdict='invalid';ds='continuation_issue';semantic_status='excluded_by_explicit_continuation';reasons=[]
        dim=scene_dimensions(category,iid in MIXED_SCENES)
        scene_evidence=([dict(source='evidence/latest.json#/image_decisions/'+iid,quote=MIXED_SCENES[iid],interpretation='OOS与难标门洞同时成立；单选值不覆盖评论。')] if iid in MIXED_SCENES else []) + recovered_scene_evidence
        if iid in coverage_evidence:
            cr=coverage_doc['decisions'][iid]
            dim=dict(oos_status={'oos':'confirmed','stable_nonorthogonal':'confirmed','in_scope':'not_oos','pending':'pending','':'not_recorded'}[cr['oos']],
                     doorway_status={'none':'none','annotatable':'annotatable','difficult':'difficult','pending':'pending','':'not_recorded'}[cr['doorway']])
            scene_evidence.append(coverage_evidence[iid])
        scope_policy='inner_space_only' if iid=='uNb9QFRL6hY_a372582c11864f31a9dd174e4a0ae6ad' else 'retain_scope_variation'
        historical_reason = b.get('exclusion_reason') or ('existing_worker_exclusion' if b['worker_id'] in {'W019','W026'} else '')
        if not b['accepted_before_new_review'] and not historical_reason:
            historical_reason = pv.get('version_decision') or '|'.join(pv.get('flags', [])) or 'historical_not_accepted_reason_unresolved'
        effective = overrides.get(cid, {}).get('effective_points', b['effective_points_1024x512'])
        labels = overrides.get(cid, {}).get('effective_point_labels', a.get('effective_point_labels', []))
        repaired = cid in overrides
        changed = not same(effective, b['effective_points_1024x512'])
        retained = ('historical_not_accepted' if not b['accepted_before_new_review'] else
                    'excluded_by_review' if verdict == 'invalid' else
                    'retained_pending' if verdict in {'undetermined','repair_needed','representation_pending','historical_yizheng_only'} and not repaired else
                    'retained')
        quality = 'candidate_pending_geometry'
        use_reasons = []
        if retained in {'historical_not_accepted','excluded_by_review'}:
            quality = 'excluded'; use_reasons.append(retained)
        elif iid in holds:
            quality = 'hold_all_analysis'; use_reasons.append('explicit_user_hold')
        elif iid=='uNb9QFRL6hY_6a500a9a43a340eb817c58bb084327fe':
            quality='hold_main_analysis';use_reasons.append('continuation_explicit_hold_main')
        elif category in {'oos','oos_stable_nonorthogonal','doorway_difficult'}:
            quality = 'out_of_primary_scene'; use_reasons.append(category)
        elif 'reference_error' in tags or 'reference_error' in individual_tags:
            quality = 'hold_reference_quality'; use_reasons.append('explicit_reference_error')
        elif si.get('needs_user_review'):
            quality = 'hold_scene_or_reference'; use_reasons.append(si['reason'])
        elif category in {'unconfirmed','doorway','doorway_annotatable'} or (category == 'reference_concern' and not si.get('classification_resolved')) or 'reference_uncertain' in tags:
            quality = 'hold_scene_or_reference'; use_reasons.append(category)
        elif retained == 'retained_pending' or reasons:
            quality = 'hold_individual_review'; use_reasons.extend(reasons or [verdict])
        if not verified:
            quality = 'hold_source_verification'; use_reasons.append(verify_error)
        consensus = ('excluded' if retained in {'historical_not_accepted','excluded_by_review'} else
                     'hold_all_analysis' if iid in holds else
                     'hold_main_analysis' if iid=='uNb9QFRL6hY_6a500a9a43a340eb817c58bb084327fe' else
                     'inner_space_only_reference_hold' if scope_policy=='inner_space_only' else
                     'stable_nonorthogonal_separate' if iid in stable else
                     'oos_doorway_exploratory' if category in {'oos','doorway_difficult'} else 'main_candidate')
        history = []
        for name, doc in docs.items():
            rec = doc.get('annotation_decisions',doc.get('decisions',{})).get(cid)
            if rec is not None:
                history.append(dict(source='evidence/' + name + '.json',record=rec))
        image_history = [dict(source='evidence/' + name + '.json',record=doc['image_decisions'][iid])
                         for name,doc in docs.items() if iid in doc.get('image_decisions',{})]
        if iid in coverage_evidence:
            image_history.append(dict(source=coverage_evidence[iid]['source'],record=coverage_doc['decisions'][iid]))
        t = trap.get(cid, {})
        rows.append(dict(canonical_annotation_id=cid,image_id=iid,image_code=images.get(iid,{}).get('code',pv.get('code','')),
            worker_id=b['worker_id'],condition=b['raw_condition'],stage=b['stage'],room_id=room_map.get(iid,{}).get('candidate_id',''),
            accepted_before_review=b['accepted_before_new_review'],historical_exclusion_reason=historical_reason,
            raw_verified=verified,raw_verification_error=verify_error,raw_source=source,
            latest_decision_source=ds,verdict=verdict,raw_review_status=status,semantic_status=semantic_status,
            semantic_annotation_evidence=sa,semantic_image_evidence=si,
            needs_user_review=bool(reasons or si.get('needs_user_review')),
            pending_history_verification=bool(sa.get('conditional_history')),
            current_comment=d.get('comment',''),review_followup_reasons=reasons,
            continuation_issue=issue or {},current_decision_comment=issue['comment'] if cid in EXCLUDED_BY_ISSUE else d.get('comment',''),
            scene_category=category,scene_status=image_d.get('status','unrecorded'),image_comment=image_d.get('comment',''),
            original_scene_category=image_d.get('category','unconfirmed'),
            individual_review_covered=bool(history),
            structured_image_review_covered=bool(image_history),
            scene_classification_source='coverage_followup' if iid in coverage_evidence else 'structured_review' if image_d else 'explicit_historical_comment' if recovered_scene_evidence else 'not_recorded',
            coverage_review=coverage_evidence.get(iid,{}),
            scene_oos_status=dim['oos_status'],scene_doorway_status=dim['doorway_status'],scene_dimension_evidence=scene_evidence,
            scope_policy=scope_policy,
            inner_scope_exemplar_ids=['103bd0e8ec57eb971857','20512095d53578cdb0d8','793fbf24fd55bb3641aa','ab0fd432ae8aa26071ae'] if scope_policy=='inner_space_only' else [],
            repeated_error_group='rPc09_three_workers_same_omission' if cid in {'4a1158da9bd83ef9','6aed1eb1185c1318','6d192755ca096a2c'} else '',
            image_traits=it,annotation_traits=at,difficulty=it.get('difficulty','unrecorded'),
            gt_substantive_error='reference_error' in tags,gt_detail_omission='reference_omission' in tags,
            gt_version_note=si.get('gt_version_note','未明确参考版本；不自动归到原始或人工修订GT'),
            scope_difference_image='scope' in tags,detail_difference_image='detail' in tags,
            scope_difference_annotation='scope' in individual_tags,detail_difference_annotation='detail' in individual_tags,
            raw_point_count=len(b['raw_points_1024x512']),effective_point_count=len(effective) if effective is not None else None,
            effective_points_1024x512=effective,effective_point_labels=labels,
            repair_status='applied' if repaired else 'revoked_improvement_edit' if cid=='f8c20f06811c7321e708' else 'historical_or_none',
            repair_evidence=overrides.get(cid,a.get('repairs',[])),historical_repair_evidence=a.get('history',[]),
            pairing_status='stale_after_repair' if changed else b['pairing_status'],
            geometry_status='not_recomputed_after_repair' if changed else 'existing_representation_not_revalidated',
            cleaning_disposition=retained,worker_quality_gate=quality,analysis_gate_reasons=use_reasons,consensus_group=consensus,
            points_without_imputation=not bool(b.get('imputed_point') or cid in {'af1ada91e5648762','3d1c6d9fda198b1b'}),
            trap_status=t.get('trap_status','unknown'),trap_origin=t.get('trap_origin','unknown'),
            model_edit_status=t.get('model_edit_status','not_checked'),trap_model_evidence=t,
            review_history=history,image_review_history=image_history,old_comment_interpretations=by_ann[cid],
            second_comment_interpretations=second_by_image[iid],frozen_cluster_references=cluster_refs[iid],
            same_image_comment_context=by_image[iid],room_evidence=room_map.get(iid,{})))
    # 语义核查单独保留；明确说明未完成的项，不让机器猜评论。
    for iid in image_ids:
        matching=[r for r in rows if r['image_id']==iid]
        if not matching[0]['image_code']:
            visual_path=ROOT/'analysis_results/consensus_visual_review_20260923/cases'/f'{iid}.js'
            visual=json.loads(visual_path.read_text(encoding='utf-8').split('=',1)[1].rstrip(';\n'))
            for row in matching:
                row['image_code']=visual['code']
    rows.sort(key=lambda r:(r['image_id'],r['worker_id'],r['condition'],r['canonical_annotation_id']))
    coverage = []
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['image_id']].append(row)
    for iid, group in grouped.items():
        first = group[0]
        covered = sum(r['individual_review_covered'] for r in group)
        coverage.append(dict(image_id=iid,image_code=first['image_code'],response_count=len(group),
            individually_reviewed_count=covered,structured_image_review_covered=first['structured_image_review_covered'],
            original_scene_category=first['original_scene_category'],resolved_scene_category=first['scene_category'],
            coverage_group='structured_image_review' if first['structured_image_review_covered'] else 'individual_review_only' if covered else 'not_in_current_review_files',
            classification_evidence=first['scene_dimension_evidence'],
            original_comments=first['same_image_comment_context'],
            needs_reclassification=False,
            note='缺少分类字段不等于需要再次排除；旧评论完整保留，不推断普通，不改变个人裁决。'))
    workers=worker_report(rows)
    write_csv(OUT/'标注者排除统计.csv',workers)
    detail_keys=['worker_id','image_code','canonical_annotation_id','condition','scene_category','scene_oos_status','scene_doorway_status','current_decision_comment','image_comment','latest_decision_source','raw_source']
    exclusions=[{k:r[k] for k in detail_keys} for r in rows if r['cleaning_disposition']=='excluded_by_review']
    write_csv(OUT/'明确排除作答明细.csv',exclusions)
    # 本轮逐房读取原评论后的对照释义；不传播图片或个人裁决。
    room_notes={
        'G014':'7y3-22本次明确OOS，与同房08/12/17一致。',
        'G047':'S9-06本次合规，与同房10/15/17/19的普通图片判断一致。',
        'G078':'Z6-08本次合规，与同房02一致。',
        'G098':'e9-16区分原始GT范围与人工修订GT；e9-17评论为GT纳入内侧房间。是参考版本/空间方案差异，不将旧reference_concern名称判为矛盾；未标注视角不推定已审核。',
        'G114':'jtcx-22本次合规，与同房23普通图片判断没有明确冲突。',
        'G124':'本次合规与同房pRb-04/06普通图片判断没有明确冲突。',
        'G155':'q9同房意见涉及门后空间是否纳入；12已有具体旧评论，16二审解释了GT的两个外围空间。最新合规不否定范围差异；保留16的具体人员点位问题，不传播为整房错误。',
        'G171':'本次合规与同房rPc-20普通图片判断一致。',
        'G205':'wc-03/22/29/54/61原话均涉及门口区域的取舍；不是因旧选项不同就构成冲突。wc-61用户明确只勾选scope；各作答漏点/排除仍按个人记录。',
        'G207':'本次合规与同房wc-15普通图片判断一致。',
    }
    touched_rooms={room_map[iid]['candidate_id'] for iid in coverage_evidence if iid in room_map}
    room_review=[]
    for iid,group in grouped.items():
        r=group[0]
        if r['room_id'] not in touched_rooms and iid not in coverage_evidence:
            continue
        count=sum(g[0]['room_id']==r['room_id'] for g in grouped.values()) if r['room_id'] else 1
        note=room_notes.get(r['room_id'],'本轮台账中本房仅此已标注视角，无法做跨视角一致性判断。' if count==1 else '需查看逐图证据；未自动统一分类。')
        if not r['room_id']:
            note='物理同房关系未确认；本图单列，不与其他未确认图片合并。'
        room_review.append(dict(room_id=r['room_id'],image_id=iid,image_code=r['image_code'],new_coverage_review=iid in coverage_evidence,
            comparison_group=r['room_id'] or 'unconfirmed:'+iid,
            scene_category=r['scene_category'],oos_status=r['scene_oos_status'],doorway_status=r['scene_doorway_status'],
            scope_difference=r['scope_difference_image'],detail_difference=r['detail_difference_image'],
            gt_version_note=r['gt_version_note'],image_comment=r['image_comment'],
            previous_image_comments=r['image_review_history'],same_image_comments=r['same_image_comment_context'],
            current_quality_gates=sorted({v['worker_quality_gate'] for v in group}),
            comparison_note=note,needs_new_review=False,
            room_evidence_source='consensus_research_20260923/inputs/room_registry.json.gz:physical_same_supported' if r['room_id'] else 'not_confirmed',
            historical_room_oos_status=r['room_evidence'].get('oos_status',''),
            historical_room_status_is_current_image_verdict=False))
    room_review.sort(key=lambda r:(r['room_id'],r['image_code']))
    write_csv(OUT/'同房图片复核对照.csv',room_review)
    with (OUT/'逐图审核覆盖.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(coverage[0]));writer.writeheader()
        for row in coverage:
            writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list,bool)) else v for k,v in row.items()})
    fields = list(rows[0])
    csv_path = OUT / '全量复核.csv'
    with csv_path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v,ensure_ascii=False,allow_nan=False) if isinstance(v,(dict,list,bool)) else v for k,v in row.items()})
    csv.field_size_limit(32*1024*1024)
    with csv_path.open(encoding='utf-8-sig',newline='') as f:
        reread=list(csv.DictReader(f))
    assert len(reread)==3152 and len({r['canonical_annotation_id'] for r in reread})==3152
    for a,b in zip(rows,reread):
        assert a['current_comment']==b['current_comment']
        assert a['review_history']==json.loads(b['review_history'])
    summary=dict(rows=len(rows),images=len(image_ids),raw_verified=sum(r['raw_verified'] for r in rows),raw_failures=failures,
        latest_annotations=len(latest['annotation_decisions']),latest_images=len(latest['image_decisions']),
        repairs=len(overrides),revoked=1,semantic_audit_present=bool(semantic),
        cleaning_counts=dict(Counter(r['cleaning_disposition'] for r in rows)),
        quality_counts=dict(Counter(r['worker_quality_gate'] for r in rows)),
        unresolved_rows=[dict(annotation_id=r['canonical_annotation_id'],code=r['image_code'],worker=r['worker_id'],reasons=r['review_followup_reasons']) for r in rows if r['review_followup_reasons']],
        image_questions=[dict(image_id=iid,**v) for iid,v in semantic.get('image_overrides',{}).items() if v.get('needs_user_review')],
        history_checks=[r['canonical_annotation_id'] for r in rows if r['pending_history_verification']])
    summary['continuation_resolved_issues']=5
    summary['image_coverage_counts']=dict(Counter(r['coverage_group'] for r in coverage))
    summary['historical_scene_recoveries']=[r['image_code'] for r in rows if r['scene_classification_source']=='explicit_historical_comment']
    summary['historical_scene_recoveries']=sorted(set(summary['historical_scene_recoveries']))
    summary['mixed_oos_doorway_images']=sorted({r['image_code'] for r in rows if r['scene_oos_status']=='confirmed' and r['scene_doorway_status'] in {'difficult','annotatable','confirmed_unspecified'}})
    summary['coverage_followup']=dict(images=len(coverage_evidence),resolved=sum(r['status']=='resolved' for r in coverage_doc['decisions'].values()),
        oos_choices=dict(Counter(r['oos'] for r in coverage_doc['decisions'].values())),image_hold=COVERAGE_HOLD,
        room_groups_checked=len(touched_rooms),room_comparison_images=len(room_review),wc61_tags=['scope'])
    dump(OUT / 'summary.json', summary)
    dump(OUT / 'field_contract.json',dict(schema='full_review_csv_20260928_v4',rows=3152,primary_key='canonical_annotation_id',
        precedence=['explicit_current_user_clarification','coverage_followup_image_only','continuation_issue','continuation_annotation','latest','second','historical_user','historical_yizheng_separate'],
        fields={k:dict(type='json' if isinstance(rows[0][k],(dict,list,bool)) else 'integer' if isinstance(rows[0][k],int) else 'string') for k in fields},
        reports={name:dict(primary_key=key,fields={k:'json' if isinstance(v,(dict,list,bool)) else 'integer' if isinstance(v,int) else 'string' for k,v in sample.items()})
                 for name,key,sample in [('标注者排除统计.csv','worker_id',workers[0]),('明确排除作答明细.csv','canonical_annotation_id',exclusions[0]),('同房图片复核对照.csv','image_id',room_review[0])]},
        enum_descriptions={
            'individual_review_covered':'当前各轮上传文件中是否有本份作答的审核记录，不等于所有问题已解决',
            'structured_image_review_covered':'当前上传文件中是否有图片级审核记录',
            'original_scene_category':'原结构化选项；不被历史评论回填覆盖',
            'scene_classification_source':'coverage_followup / structured_review / explicit_historical_comment / not_recorded；缺记录不自动进复审',
            'coverage_review':'本次图片补审原始记录、有效标签及用户wc-61漏选更正；view_context不是个人裁决',
            'scene_oos_status':{'confirmed':'明确确认OOS','not_oos':'本次明确合规','pending':'尚不能确定','not_recorded':'未明确记录，不是否定'},
            'scene_doorway_status':{'difficult':'确认难标门洞','annotatable':'门洞可标','confirmed_unspecified':'门洞但可标性未分','none':'明确非门洞','pending':'门洞属性待定','not_recorded':'未明确记录'},
            'scope_policy':{'inner_space_only':'用户明确仅内侧空间；具体示例见inner_scope_exemplar_ids','retain_scope_variation':'无额外范围限制，保留空间差异'},
            'hold_main_analysis':'暂不进入人员主质量与主共识面板，仍保留资料',
            'current_decision_comment':'当前个人结论原话；具体续审issue优先于旧表单',
            'continuation_issue':'原始最新问题卡，不把旧pending当作当前未决',
            'points_without_imputation':'只描述是否有补入点，不是独立性或分析资格保证'},
        constraints=['false GT flags mean no explicit structured tag, not proof GT correct','unrecorded difficulty is allowed','main_candidate is not computed-region eligibility','raw_review_status is never overwritten','historical_yizheng_only is not auto-invalid']))
    # 旧路径仍可能被读取，因此同步当前派生层；历史7项原件已在evidence保留。
    dump(closeout / 'effective_point_overrides.json', corrected)
    old_page = closeout / 'index.html'
    archived_page = evidence / 'prior_repair_page.html'
    if not archived_page.exists():
        shutil.copyfile(old_page, archived_page)
    old_page.write_text('<!doctype html><meta charset="utf-8"><h1>本轮修复已纠正</h1><p>jtcx-30删除已撤销；jtcx-12和Uw-17不改点。当前9项有效修复及全量复核见新入口。</p><a href="../review_final_20260928/index.html">打开当前结果</a>',encoding='utf-8')
    report = ['# 全量复核结果', '',
        f'全量3152份、259图；原始身份与坐标核验通过{summary["raw_verified"]}份。个人裁决沿用最新复核优先；24张图片覆盖补审仅更新图片维度。当前结构化图片判断{len(latest["image_decisions"])}张。',
        '', '## 修复与撤销', 'jtcx-30恢复14点；jtcx-12与Uw-17保持点集。9项有效修复：原6项保留，uNb-47删p14，wc-56补p10.x/p11.y，rPc-17 W017恢复已展示初始化点。原始导出和GT未改。',
        '', '## 最新五图续审已接入', 'S9-04确认范围歧义；uNb-32暂不进入主分析；uNb-51采用内侧空间、参考问题仍保留，不自动恢复人员主质量。rPc-09三份与wc-67/W034按最新直接排除，历史补点不再阻塞处置。rPc三人同类错误独立记录，不推断串通或因果。',
        '', '## OOS与门洞并存', 'pRb-01和pRb-11最新评论明确两者并存，原单选category原样保留，另列scene_oos_status与scene_doorway_status及原话。uNb-51仅曾疑似门洞/OOS，最新明确内侧空间，不据旧疑似强判两者；q9-30的旧“其他视角可能OOS”不传播为本图确认。',
        '', '## 语义覆盖及使用限制', '独立核查最新435条与二审406条非空评论（含重复），全部89张参考/范围争议按原话细分。最初两份原文及既有逐条释义全部入表；未声称本轮重新逐字视觉审查所有历史记录。难度缺失不算漏审。',
        '', '## 图片覆盖补审合并与同房核对',
        '原62张缺少结构化分类：42张只有逐份旧审核、20张当时未覆盖。本次24张均有resolved记录：22张合规、7y3-22明确OOS，pRb-16适用性仍待定但已明确暂缓全部分析，不能计人员错误。现在221张有结构化图片判断，38张仅旧逐份审核，0张完全不在上传审核中。图片被覆盖不等于所有人员逐份复核完成；38张不因此自动重审。2t7-07明确旧评论仍恢复难标门洞。',
        'wc-61按用户当前明确更正，补充标签仅scope；原上传漏选仍保存。e9-16原始Matterport GT与人工修订GT分别解释。当前查看下拉名gt_revised不证明实际文件是修订版，gt_version_note以view_context.gt_source为依据。',
        '同房图片复核对照.csv按确认物理同房关系逐图保留新旧评论，覆盖本轮涉及的18个房间；不按建筑前缀拼房，不传播个人裁决。wc同房03/22/29/54/61均涉及门口区域取舍；q9同房涉及门后空间取舍。旧reference_concern与新in_scope的名称差异不等于矛盾。历史房间oos_status只是来源记录，不覆盖最新图片判断。',
        '逐图审核覆盖.csv列出259张的覆盖组、原分类、恢复分类、原评论及恢复证据。needs_reclassification=false仅表示本次覆盖核查没有自动发出新的分类任务，不表示原图已视觉复核或其他任务没有疑点。缺少新字段不等于需要再次审核排除。',
        '对20张追查了20260907原始问卷、20260918两份文字/最终裁决、20260919追加审核、20260922簇审核、20260921新收审核/八组采用与20260913选图原件。7y3-旧图和pRb-旧图有早期问卷入口；e9-16、rPc-13有9月18日文字；wc-29、S9-06有版本/父记录入口；部分图有选图采用记录。这些证明“本轮未覆盖”不等于“历史从未看过”，但选图采用、系统给出的候选或版本来源不等于图片适用性/逐份质量裁决，本轮不自动搬成新结论。',
        '模型未改、改后仍错、疑似误导及Trap继续分别保留在annotation_traits、trap_model_evidence与完整review_history中；本次没有关键词提取成因果结论，也没有因恢复场景属性丢弃这些证据。',
        'candidate_pending_geometry/main_candidate表示审核层允许进入后续核验，不是区域已可计算；不由此直接运行人员评分。OOS/难标门洞、GT实质错误、条件式裁决与表示失败分开。GT布尔标签false只表示未明确标记，不能解释成已证明GT正确。',
        '', '## 数量', '```json',json.dumps({k:summary[k] for k in ['cleaning_counts','quality_counts']},ensure_ascii=False,indent=2),'```',
        '', '## 人员统计口径', '标注者排除统计.csv列出每人全部作答、逐份审核覆盖、明确排除、历史未纳入、场景/参考资格限制及待处理数量。85份明确排除与133份历史未纳入分开；普通/OOS或难标门洞/其他三组互斥，OOS与门洞重叠不重复计数。manual/semi单列；不把可疑队列比例当总体错误率。明确排除作答明细.csv可追到每份个人裁决。',
        '', '## 文件', '- 全量复核.csv：一份作答一行；UTF-8 BOM，JSON字段可直接解析。', '- field_contract.json：v4字段类型及枚举；历史无有效点的effective_point_count空白表示null。', '- 逐图审核覆盖.csv：259张图片的覆盖边界及明确历史分类恢复。', '- 图片覆盖补审_已合并.json：保留上传格式，wc-61只补scope，并附用户更正来源。', '- 同房图片复核对照.csv / 标注者排除统计.csv / 明确排除作答明细.csv：本次逐房对照及人员统计。', '- semantic_findings.json：旧独立释义留档；current_semantic_findings.json为接入续审后的当前释义。', '- effective_point_overrides.json / repair_events.json：当前修复与撤销。',
        '- index.html：可筛选CSV查看页；全量CSV包含完整证据，界面展示关键字段。',
        '- 定义、边界和研究用途详见 ../../docs/thesis_main/两人审核归并与二次复核SOP_20260925.md 第12节。',
        '', '## 验证边界', '原始数据3152份核验、CSV往返和唯一键检查已执行。没有重算共识、质心、配对或角点顺序；修复后的旧几何状态明确失效。']
    (OUT / 'README.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    table_keys=['canonical_annotation_id','image_id','image_code','worker_id','condition','room_id','verdict',
        'raw_review_status','semantic_status','current_decision_comment','image_comment','continuation_issue',
        'scene_oos_status','scene_doorway_status','scene_dimension_evidence','scene_category','scope_policy','inner_scope_exemplar_ids',
        'cleaning_disposition','worker_quality_gate','consensus_group','gt_substantive_error','gt_detail_omission','gt_version_note',
        'raw_point_count','effective_point_count','repair_status','repeated_error_group','raw_source','needs_user_review',
        'coverage_review','image_traits','scope_difference_image','detail_difference_image']
    table=dict(summary=summary,workers=workers,rooms=room_review,rows=[{k:r[k] for k in table_keys} for r in rows])
    (OUT/'table_data.js').write_text('window.REVIEW_TABLE='+json.dumps(table,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')+';',encoding='utf-8')
    shutil.copyfile(Path(__file__).with_name('review_final_table_20260928.html'),OUT/'index.html')
    # 已提交的补审页仍可打开比较；只用原记录匹配更新，不能覆盖后续浏览器新改动。
    followup=ROOT/'analysis_results/review_coverage_followup_20260928'
    seed=dict(original=coverage_doc,applied=applied_coverage)
    (followup/'applied_reviews.js').write_text('window.COVERAGE_APPLIED='+json.dumps(seed,ensure_ascii=False).replace('<','\\u003c')+';',encoding='utf-8')
    from .build_review_coverage_followup_20260928 import HTML
    (followup/'index.html').write_text(HTML,encoding='utf-8')
    return summary


if __name__ == '__main__':
    print(json.dumps(build(),ensure_ascii=False,indent=2))
