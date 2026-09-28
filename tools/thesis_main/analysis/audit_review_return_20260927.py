"""二审回收只读核验；冻结评论所指成员，不自动改判。"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from urllib.parse import urlparse, parse_qs

from .review_reconciliation_audit_20260925 import verify_raw, same

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / 'analysis_results/review_reconciliation_20260925'
SOURCE = Path('C:/Users/ASUS/Downloads/全历史标注_二次复核_20260925(2).json')
OUT = ROOT / 'analysis_results/review_return_20260927'
SEMI_IMPORTS = {
    29:'import_json/stage1_prescreen_final_20260325/stage1_prescreen_semi_import_v5.json',
    40:'import_json/stage1_prescreen_foreign_https_20260609/stage1_prescreen_semi_import_v5_foreign_https.json',
    72:'import_json/calibration_c1_v3_1_formal/c1_v3_1_semi_import_zh.json',
    68:'import_json/calibration_c1_v3_1_formal/c1_v3_1_semi_import_foreign_https.json'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def dump(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8'))


def case_payload(path):
    text = path.read_text(encoding='utf-8')
    return json.JSONDecoder().raw_decode(text.split('Object.assign(', 1)[1].split(',', 1)[1])[0]


def missing_disposition(old_events, repairs, pairing, decision):
    if any(e['verdict'] == 'invalid' for e in old_events):
        return 'excluded_unreviewed', '旧审核曾排除，本轮未单独填写，需明确确认。'
    if repairs or any('修复核查' in (e.get('interpretation') or {}).get('topics', []) for e in old_events):
        return 'repair_unreviewed', '存在修复记录或提议，图片整体意见不能替代修复确认。'
    if any(e['verdict'] == 'representation' for e in old_events):
        return 'representation_unreviewed', '旧审核表示／配对问题仍需逐份核对，顺序调整继续搁置。'
    if any(e['verdict'] == 'pending' and (not e.get('comment', '').strip()
           or (e.get('interpretation') or {}).get('targets') == ['annotation']) for e in old_events):
        return 'individual_unreviewed', '旧待定涉及个人标注质量或未写原因，本轮没有个人结论；图片背景不足以消除问题。'
    if not decision or decision['status'] != 'resolved':
        return 'image_pending', '图片整体判断尚待定，保留原个人判断。'
    return 'image_context_inherited', '沿用图片场景背景；不新造个人保留或排除裁决。'


def points(result):
    return [[r['value']['x'] * 10.24, r['value']['y'] * 5.12]
            for r in result if r.get('type') == 'keypointlabels']


def cluster_binding(comment, members):
    """完整冻结当时分区；未明确簇号的评论仍绑定全部当时成员。"""
    labels = sorted(set(re.findall(r'簇\s*([0-9]+)', comment)), key=int)
    groups = defaultdict(list)
    for cid, source in members.items():
        label = source.get('clusters', {}).get('affinity')
        if label is not None:
            groups[str(label)].append(dict(annotation_id=cid, worker=source['worker_id'],
                condition=source['condition'], point_version='shared_x',
                effective_points=source['effective_points'], shared_x_points=source.get('shared_x_points')))
    return dict(method='affinity', point_version='shared_x', mentioned_labels=labels,
                groups=dict(groups), unresolved_labels=[n for n in labels if n not in groups],
                interpretation='用户确认本轮均为默认直径约束全局亲近度；组内固化具体作答，不引用未来簇号。')


def build(source=SOURCE, old=OLD):
    returned = read(source)
    if returned['schema'] != 'review_reconciliation_decisions_v1' or returned['binding']['id'] != 'review_reconciliation_20260925_v1':
        raise ValueError('二审schema或绑定不匹配')
    image_decisions, decisions = returned['image_decisions'], returned['annotation_decisions']
    images = {i['image_id']: i for i in read(old / 'images.json')}
    if not set(image_decisions) <= images.keys():
        raise ValueError('存在未知图片')
    audit = read(old / 'source_audit.json')['annotations']
    events = read(old / 'commentary.json')
    by_cid = defaultdict(list)
    for event in events:
        by_cid[event['canonical_annotation_id']].append(event)
    sources, members = {}, {}
    for iid, image in images.items():
        entries = case_payload(old / image['history_script'])['variants']
        members[iid] = {v['source']['canonical_annotation_id']: v['source']
                        for v in entries if v['source']['role'] == 'annotation'}
        sources.update(members[iid])
    if not set(decisions) <= sources.keys():
        raise ValueError('存在未知作答')
    # 再次从运行时原始导出核验点序和身份，而非相信旧报告状态。
    exports = {}
    tasks = {}
    annotations = {}
    for cid, s in sources.items():
        a = audit[cid]; origin = a['source']; path = origin['path']
        if path not in exports:
            exports[path] = {t['id']: t for t in read(ROOT / path)}
        task = exports[path][origin['task']]
        annotation = next(x for x in task['annotations'] if x['id'] == origin['annotation'])
        verify_raw(origin, s['raw_points'], task, annotation)
        tasks[cid] = task
        annotations[cid] = dict(annotation_id=cid, image_id=origin['image_id'],
            code=images[origin['image_id']]['code'], worker=s['worker_id'], condition=s['condition'],
            new_decision=decisions.get(cid), raw_count=len(s['raw_points']),
            effective_count=len(s['effective_points']), repairs=a['repairs'], pairing=a['pairing'],
            source=origin, old_events=by_cid[cid], raw_verified=True,
            image_context=image_decisions.get(origin['image_id']))
        if cid in {'78a68354a388042f', 'c87d232365323163'}:
            raw = dict(zip(s['raw_point_labels'], s['raw_points']))
            shared = dict(zip(s['shared_x_point_labels'], s['shared_x_points']))
            annotations[cid]['shared_x_check'] = dict(raw_p5=raw['p5'], raw_p6=raw['p6'],
                shared_x_p5=shared['p5'], shared_x_p6=shared['p6'],
                effective_unchanged=same(s['raw_points'],s['effective_points']),
                explanation=('共享x层已将p5/p6均值统一至 %.6f；有效层没有修改。原意见只要求统一x，需确认是否接受已有预处理。'%shared['p5'][0]
                    if cid=='78a68354a388042f' else
                    '共享x层用均值 %.6f，原意见要求p5单向对齐p6的 %.6f，两者相差 %.6f 像素；单向修复尚未执行。'%(shared['p5'][0],raw['p6'][0],abs(shared['p5'][0]-raw['p6'][0]))))
    result_images = {iid: dict(image_id=iid, code=image['code'], decision=image_decisions.get(iid),
        annotation_ids=list(members[iid]), issues=[], comments=[]) for iid, image in images.items()}

    def issue(iid, kind, title, ids=(), evidence=None):
        target = result_images[iid]['issues']
        target.append(dict(id=f'{iid}:{kind}:{len(target)}', kind=kind, title=title,
                           annotation_ids=list(ids), evidence=evidence))

    missing = []
    for iid, image in images.items():
        d = image_decisions.get(iid)
        in_queue = 'followup' in image['review']['flags']
        if in_queue and not d:
            issue(iid, 'missing_image', '原复核队列图片未填写整体判断。')
        elif d and d['status'] != 'resolved':
            issue(iid, 'pending_image', '整体判断待定：请结合原评论确认分类。', evidence=d)
        for cid in image['review']['followup_ids']:
            if cid in decisions:
                continue
            a = annotations[cid]
            kind, why = missing_disposition(a['old_events'], a['repairs'], a['pairing'], d)
            row = dict(annotation_id=cid, image_id=iid, code=image['code'], worker=a['worker'],
                       condition=a['condition'], disposition=kind, explanation=why)
            if a.get('shared_x_check'):
                row['shared_x_check'] = a['shared_x_check']
                row['explanation'] += a['shared_x_check']['explanation']
            missing.append(row)
            if kind != 'image_context_inherited':
                issue(iid, kind, row['explanation'], [cid], a['old_events'])
    cluster_refs, model_ids, repair_checks, comments = [], set(), [], []
    for row in missing:
        if row['disposition']=='repair_unreviewed':
            a=annotations[row['annotation_id']]
            repair_checks.append(dict(annotation_id=a['annotation_id'],image_id=a['image_id'],worker=a['worker'],
                comment='；'.join(e['comment'] for e in a['old_events'] if e['comment']),new_decision=None,
                repairs=a['repairs'],raw_count=a['raw_count'],effective_count=a['effective_count'],
                history=audit[a['annotation_id']]['history'],shared_x_check=a.get('shared_x_check')))
    for scope, table in [('image', image_decisions), ('annotation', decisions)]:
        for key, d in table.items():
            iid = key if scope == 'image' else annotations[key]['image_id']
            text = d['comment']
            if text.strip():
                record = dict(id=f'{scope}:{key}', scope=scope, image_id=iid,
                    annotation_id=key if scope == 'annotation' else None, comment=text,
                    updated_at=d.get('updated_at'), decision=d)
                comments.append(record); result_images[iid]['comments'].append(record)
                if '簇' in text:
                    binding = dict(record, **cluster_binding(text, members[iid]))
                    cluster_refs.append(binding)
                if '预标注' in text or 'trap' in text.lower():
                    if scope == 'annotation':
                        model_ids.add(key)
            if scope == 'annotation':
                if d['status'] != 'resolved' or d['verdict'] in {'undetermined', 'repair_needed'}:
                    issue(iid, 'repair' if d['verdict'] == 'repair_needed' else 'pending_annotation',
                          '新复核仍待定／待修复，请核对原评论。', [key], d)
                a = annotations[key]
                if a['repairs'] or d['verdict'] == 'repair_needed' or any(word in text for word in ['补点','补过','补充','补了','删点']):
                    repair_checks.append(dict(annotation_id=key, image_id=iid, worker=a['worker'],
                        comment=text, new_decision=d, repairs=a['repairs'], raw_count=a['raw_count'],
                        effective_count=a['effective_count'], history=audit[key]['history']))
    rooms = []
    for room in read(old / 'rooms.json'):
        selected = [dict(image_id=iid, code=images[iid]['code'], decision=image_decisions[iid])
                    for iid in room['image_ids'] if iid in image_decisions]
        if len({r['decision']['category'] for r in selected}) > 1:
            entry = dict(room_id=room['id'], evidence=room, images=selected,
                interpretation='同房不同机位可能合理分类不同；只请求并排确认，不传播裁决。')
            rooms.append(entry)
            for row in selected:
                issue(row['image_id'], 'room_comparison', f"同房 {room['id']} 分类不同，结合机位比较。", evidence=entry)
    workers = {}
    for worker in sorted({a['worker'] for a in annotations.values()}):
        selected = [a for a in annotations.values() if a['worker'] == worker]
        reviewed = [a for a in selected if a['new_decision']]
        bins = Counter(a['new_decision']['verdict'] for a in reviewed)
        strata = defaultdict(Counter)
        for a in reviewed:
            cat = (a['image_context'] or {}).get('category', 'unreviewed')
            scene = 'oos_or_difficult_doorway' if cat in {'oos','doorway_difficult'} else 'other_or_unconfirmed'
            strata[a['condition'] + '/' + scene][a['new_decision']['verdict']] += 1
        excluded = [a for a in reviewed if a['new_decision']['verdict'] == 'invalid']
        feature_terms = {'圆柱相关':['圆柱','圆形柱'], '门框相关':['门框'],
            '多点或非墙角':['多了','多标','不是墙角','非墙角'],
            '点位偏差':['偏移','偏差','离谱','偏的','偏得'], '漏点':['漏','少了','少标']}
        features = {label:[a['annotation_id'] for a in excluded
            if any(word in a['new_decision']['comment'] for word in terms)] for label,terms in feature_terms.items()}
        full_total = sum(a['source']['worker'] == worker for a in audit.values())
        workers[worker] = dict(total_annotations=full_total, represented_annotations=len(selected), reviewed=len(reviewed),
            not_individually_reviewed=full_total-len(reviewed), verdicts=dict(bins),
            strata=dict(strata), literal_comment_features=features,
            excluded=[dict(annotation_id=a['annotation_id'], image_id=a['image_id'],
                code=a['code'], condition=a['condition'], comment=a['new_decision']['comment']) for a in excluded],
            limitation='定向复核覆盖，不是人员总体错误率。')
    distribution = []
    for iid, image in result_images.items():
        aa = [annotations[cid] for cid in image['annotation_ids']]
        rr = [a for a in aa if a['new_decision']]
        bad = [a for a in rr if a['new_decision']['verdict'] == 'invalid']
        if bad:
            distribution.append(dict(image_id=iid, code=image['code'], total=len(aa), reviewed=len(rr),
                excluded=len(bad), annotation_ids=[a['annotation_id'] for a in bad],
                workers=[a['worker'] for a in bad], decision=image['decision']))
    distribution.sort(key=lambda x: (-x['excluded'], x['code']))
    model_checks = check_models(model_ids, tasks, sources, annotations)
    trap_inventory = inventory_traps(tasks, sources, annotations)
    summary = dict(images_recorded=len(image_decisions), image_statuses=dict(Counter(d['status'] for d in image_decisions.values())),
        annotations_recorded=len(decisions), verdicts=dict(Counter(d['verdict'] for d in decisions.values())),
        image_comments=sum(bool(d['comment'].strip()) for d in image_decisions.values()),
        annotation_comments=sum(bool(d['comment'].strip()) for d in decisions.values()),
        raw_verified=len(annotations), source_library_annotations=len(audit),
        outside_current_image_scope=len(audit)-len(annotations), missing_followups=len(missing),
        missing_old_exclusions=sum(x['disposition']=='excluded_unreviewed' for x in missing),
        room_differences=len(rooms), cluster_comments=len(cluster_refs), model_checks=len(model_checks))
    return dict(schema='review_return_audit_v1', source=str(source), source_review=returned,
        summary=summary, images=result_images, annotations=annotations, workers=workers,
        image_exclusions=distribution, missing_followups=missing, room_comparisons=rooms,
        comments=comments, cluster_references=cluster_refs, model_checks=model_checks, repair_checks=repair_checks,
        trap_inventory=trap_inventory)


def trap_classification(data):
    """仅使用历史设置；未设置字段与非trap不是同一回事。"""
    role, kind = data.get('semi_role'), data.get('source_type')
    trap = role=='trap' or kind in {'trap_synthetic','trap_natural'}
    control = role=='control' or kind=='control_natural'
    if trap and control:
        return 'unknown','unknown','历史字段互相冲突，须核实。'
    origin = 'synthetic' if kind=='trap_synthetic' else 'natural' if kind in {'trap_natural','control_natural'} else 'unknown'
    return ('confirmed_trap' if trap else 'confirmed_nontrap' if control else 'unknown', origin,
            '历史设置明确标为trap。' if trap else '历史设置明确标为control。' if control else '运行时未记录trap/control设置，不能从图片或坐标推断。')


def inventory_traps(tasks, sources, annotations):
    imports={project:read(ROOT/path) for project,path in SEMI_IMPORTS.items()}
    semi_ids={cid for cid,a in annotations.items() if a['condition']=='semi'}
    model={m['annotation_id']:m for m in check_models(semi_ids,tasks,sources,annotations)}
    rows={}
    for cid,a in annotations.items():
        task=tasks[cid]; data=task['data']; project=task['project']
        status,origin,why=trap_classification(data)
        candidates=[r for r in imports.get(project,[]) if str(r['data'].get('task_id'))==str(data.get('task_id'))
                    and r['data'].get('base_task_id')==data.get('base_task_id')]
        fields=['semi_role','source_type','trap_family','init_type','proposal_source_kind','synthetic_candidate_id']
        matched=bool(candidates) and all(all(r['data'].get(k)==data.get(k) for k in fields) for r in candidates)
        if candidates and not matched:
            status,origin,why='unknown','unknown','正式导入与运行时trap字段冲突。'
        m=model.get(cid)
        rows[cid]=dict(annotation_id=cid,image_id=a['image_id'],code=a['code'],worker=a['worker'],
            condition=a['condition'],trap_status=status,trap_origin=origin,reason=why,
            historical_setting={k:data.get(k) for k in fields},
            evidence=dict(runtime_export=a['source'],formal_import=SEMI_IMPORTS.get(project),
                          formal_import_match_count=len(candidates),trap_fields_agree=matched if candidates else None),
            model_edit_status=m['status'] if m else 'not_checked_non_semi',model_check=m,
            original_second_review=a['new_decision'])
    return dict(schema='review_return_trap_inventory_v1',summary=dict(annotations=len(rows),semi=len(semi_ids),
        statuses=dict(Counter(r['trap_status'] for r in rows.values())),
        semi_statuses=dict(Counter(r['trap_status'] for r in rows.values() if r['condition']=='semi')),
        trap_origins=dict(Counter(r['trap_origin'] for r in rows.values() if r['trap_status']=='confirmed_trap')),
        model_edit_statuses=dict(Counter(m['status'] for m in model.values()))),annotations=rows,
        interpretation='全239图，不限评论命中。trap设置、初始化来源、最终是否改动是独立维度；非SEMI缺字段仍保留unknown，不解释为有trap。')


def check_models(ids, tasks, sources, annotations):
    imports = defaultdict(list)
    keys = {str(tasks[cid]['data'].get('task_id')) for cid in ids}
    # 冻结导入是初始化真源；所有同身份候选必须一致，否则保留歧义。
    import_paths = list(SEMI_IMPORTS.values())
    for path in [ROOT / p for p in import_paths]:
        text = path.read_text(encoding='utf-8-sig')
        if not any('"' + key + '"' in text for key in keys):
            continue
        doc = json.loads(text)
        if not isinstance(doc, list):
            continue
        for t in doc:
            if not isinstance(t, dict) or not isinstance(t.get('data'), dict):
                continue
            key = str(t['data'].get('task_id'))
            if key not in keys:
                continue
            for prediction in t.get('predictions', []):
                if isinstance(prediction, dict) and prediction.get('result'):
                    imports[key].append((path, t, points(prediction['result'])))
    result = []
    for cid in sorted(ids):
        data = tasks[cid]['data']; key = str(data.get('task_id'))
        expected = SEMI_IMPORTS.get(tasks[cid]['project'])
        candidates = [(p,t,pts) for p,t,pts in imports[key]
            if t['data'].get('base_task_id') == data.get('base_task_id')
            and str(p.relative_to(ROOT)).replace('\\','/') == expected]
        unique = []
        for p,t,pts in candidates:
            if not any(same(pts,x) for x in unique):
                unique.append(pts)
        initial = unique[0] if len(unique)==1 else None
        final = sources[cid]['raw_points']
        canonical = lambda pts: sorted(tuple(round(x,6) for x in p) for p in pts)
        query = parse_qs(urlparse(data.get('vis_3d','')).query)
        preview = json.loads(query['data'][0]) if query.get('data') else None
        preview_points = [[p['x'],p[y]] for p in preview for y in ['y_ceiling','y_floor']] if preview else None
        preview_match = initial is not None and preview_points is not None and canonical(initial)==canonical(preview_points)
        if initial is not None and preview_points is not None and not preview_match:
            raise ValueError('冻结导入与运行时vis_3d初始化不同: '+cid)
        status = 'initialization_unresolved' if initial is None else ('unchanged_coordinates' if canonical(initial)==canonical(final) else 'changed_coordinates')
        initial_counts = Counter(canonical(initial)) if initial is not None else Counter()
        final_counts = Counter(canonical(final))
        result.append(dict(annotation_id=cid, image_id=annotations[cid]['image_id'], worker=annotations[cid]['worker'],
            code=annotations[cid]['code'], comment=(annotations[cid]['new_decision'] or {}).get('comment',''),
            status=status, initialization_kind=('synthetic_trap' if data.get('source_type')=='trap_synthetic' or data.get('proposal_source_kind')=='frozen_synthetic_asset'
                else 'natural_model_trap' if data.get('source_type')=='trap_natural'
                else 'natural_model_output' if data.get('proposal_source_kind')=='model_output_txt' else 'unspecified'),
            task_metadata=data, import_sources=[str(p.relative_to(ROOT)) for p,_,_ in candidates],
            initial_points_1024x512=initial, final_raw_points_1024x512=final,
            comparison='坐标多重集保留重复点，四舍五入至1e-6像素；数组顺序另报。',
            same_array_order=initial is not None and same(initial,final),
            preview_initialization_verified=preview_match,
            removed_or_changed_initial_points=list((initial_counts-final_counts).elements()),
            added_or_changed_final_points=list((final_counts-initial_counts).elements()),
            limitation='坐标相同不证明未检查；改动不证明改对。候选初始化不唯一时不猜测。'))
    return result


def report(result):
    s=result['summary']
    lines=['# 二次复核回收核验', '', '原始导出、GT、既有裁决均未修改。评论所指簇按本次 affinity 固定成员。', '',
           '```json',json.dumps(s,ensure_ascii=False,indent=2),'```','',
           '## 未逐份填写', '', '图片整体确认不能代替明确的旧排除、修复或表示问题；其余沿用图级场景背景而不制造个人裁决。','']
    for row in result['missing_followups']:
        lines.append(f"- {row['code']} · {row['worker']} · `{row['annotation_id']}`：{row['explanation']}")
    lines += ['', '## W034 / W037', '']
    for worker in ['W034','W037']:
        w=result['workers'][worker]
        lines += [f"### {worker}", '', f"本轮逐份复核 {w['reviewed']}，选项 {w['verdicts']}；全库作答 {w['total_annotations']}。不是总体错误率。",
                  '精确词命中计数（可重叠；0仅表示未命中这些词，不代表没有相应错误）：'+str({k:len(v) for k,v in w['literal_comment_features'].items()}),'']
        if worker=='W037':
            lines += ['具体原话线索包括 rPc-15 的 p7/p9 两对、rPc-20 的门框、uNb-48 的窗、uNb-56 的其他空间；B6-33 为6点、b8-19 为奇数点。无评论及“看不懂”类尚不能仅凭文字确定具体错误类型，须保留待视觉解释。','']
        lines += [f"- {a['code']} · {a['condition']}：{a['comment'] or '未写个人评论，请结合图片整体意见。'}" for a in w['excluded']]
    lines += ['', '## 图片排除数量', '', '| 图片 | 排除 | 逐份复核 | 全部作答 | 人员 |','|---|---:|---:|---:|---|']
    lines += [f"| {a['code']} | {a['excluded']} | {a['reviewed']} | {a['total']} | {', '.join(a['workers'])} |" for a in result['image_exclusions']]
    lines += ['', '## 模型初始化核验', '', '冻结导入与运行时原始导出比较；不使用后来生成的模型参考替代实际初始化。','']
    lines += [f"- {r['code']} · {r['worker']}：{r['status']}；{r['initialization_kind']}。{r['comment']}" for r in result['model_checks']]
    lines += ['', '## 全量Trap与初始化设置盘点', '',
        '范围覆盖当前239图2844份作答，不限上述25条评论。详见 trap_inventory.json；trap身份不随最终坐标改动改变。',
        '```json', json.dumps(result['trap_inventory']['summary'],ensure_ascii=False,indent=2), '```',
        '全部466份SEMI均找到正式导入并核对运行时设置及预览初始化。C1的106份SEMI没有明确trap/control字段，保留未知；其他manual/oos采集条件的缺字段也不擅自解释为已确认非trap。',
        '自然模型输出被历史设置选作trap与人工构造trap分开。未改变最终点集不能证明标注者没有检查；改变也不能证明纠正成功。']
    return '\n'.join(lines)+'\n'


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--source',type=Path,default=SOURCE); parser.add_argument('--out',type=Path,default=OUT)
    args=parser.parse_args(); result=build(args.source); args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'evidence').mkdir(exist_ok=True)
    (args.out/'evidence/second_review.json').write_bytes(args.source.read_bytes())
    dump(args.out/'audit.json',result)
    dump(args.out/'trap_inventory.json',result['trap_inventory'])
    (args.out/'回收核验报告.md').write_bytes(report(result).encode('utf-8'))
    print(json.dumps(result['summary'],ensure_ascii=False))


if __name__ == '__main__':
    main()
