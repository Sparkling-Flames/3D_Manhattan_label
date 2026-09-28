"""更新真人覆盖与16名新人候选安排；不派发、不重算历史几何。"""
import gzip
import json
import math
import re
from collections import Counter, defaultdict
from html import escape
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import maximum_flow

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/collection_plan_20260921'
CN = [1, 2, 6, 8, 10, 12, 13, 15, 17]
APPROVED_EXTRA = {6844, 7137, 7493, 7494, 6926}


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8-sig'))


def allocate(images, seen, newcomer_cap=50, old_cap=20):
    """全量满足图片缺口，搜索最小新人上限；无旧人员重复接触。"""
    slots = [f'W{w:03d}' for w in CN] + [f'新人{i:02d}' for i in range(1, 17)]
    need = sum(r['need_now'] for r in images)
    offset = 1 + len(images)
    sink = offset + len(slots)
    for cap in range(newcomer_cap + 1):
        rr, cc, vv = [], [], []
        def edge(a, b, c):
            rr.append(a); cc.append(b); vv.append(c)
        for i, r in enumerate(images, 1):
            edge(0, i, r['need_now'])
            for j, slot in enumerate(slots):
                if slot.startswith('新人') or int(slot[1:]) not in seen[r['image_id']]:
                    edge(i, offset+j, 1)
        for j, slot in enumerate(slots):
            edge(offset+j, sink, cap if slot.startswith('新人') else old_cap)
        graph = coo_matrix((np.array(vv, dtype=np.int64), (rr, cc)), shape=(sink+1, sink+1)).tocsr()
        flow = maximum_flow(graph, 0, sink)
        if flow.flow_value == need:
            return [dict(slot=slot, worker_id=int(slot[1:]) if slot.startswith('W') else None,
                         image_id=r['image_id'], code=r['code'], room=r['room'], scene=r['scene'],
                         status='候选未派发')
                    for i, r in enumerate(images, 1) for j, slot in enumerate(slots)
                    if flow.flow[i, offset+j] > 0], slots
    raise ValueError('当前人员与负载无法覆盖，不能静默丢弃缺口')


def main():
    old = read('analysis_results/full_history_coverage_20260916/全历史覆盖机器表.json')
    selection = {r['image_id']: r for r in read('analysis_results/candidate_selection_review_20260913_v2/选用复核机器表.json')['images']}
    assignments = read('import_json/scene_stability_stage1_20260913_v2/required_assignments.json')
    history, seen = defaultdict(set), defaultdict(set)
    for r in read('import_json/scene_stability_stage1_20260913_v2/historical_exposure.json'):
        seen[r['image_id']].add(r['worker_id'])
    source = ROOT / 'analysis_results/clustering_release_local_20260920/current/inputs/responses.jsonl.gz'
    with gzip.open(source, 'rt', encoding='utf-8') as f:
        for line in f:
            r = json.loads(line); w = int(r['worker_id'][1:]); iid = r['image_id']
            seen[iid].add(w)
            if r['unassisted_manual_included'] and w not in {19, 26}:
                history[iid].add(w)
    actual = defaultdict(set)
    required = {(r['project_key'], r['worker_id'], r['image_id']) for r in assignments}
    required_done, approved_found = set(), set()
    observations, issues, duplicates, paths = [], [], [], []
    for folder in ['新增中文20图', '新增英文30+20图']:
        files = sorted((ROOT / 'export_label' / folder).glob('*.json'))
        projects = defaultdict(list)
        for path in files:
            tasks = read(path); projects[tasks[0]['project']].append((path, tasks))
        for project, versions in projects.items():
            path, tasks = max(versions, key=lambda item: item[0].name)
            paths.append(str(path.relative_to(ROOT)))
            assert len({t['data']['base_task_id'] for t in tasks}) == len(tasks)
            for t in tasks:
                iid = t['data']['base_task_id']; key = t['data']['project_key']
                byworker = defaultdict(list)
                for d in t['drafts']:
                    m = re.search(r',\s*(\d+)\s*$', d.get('created_username', ''))
                    if not m:
                        raise ValueError('未知草稿人员，不能跳过接触检查')
                    seen[iid].add(int(m[1]))
                for a in t['annotations']:
                    w = a['completed_by']; assert isinstance(w, int)
                    seen[iid].add(w)
                    if a['was_cancelled'] or a['ground_truth'] or not a['result']:
                        continue
                    pair = (key, w, iid)
                    admitted = pair in required or key == 'en_optional' or a['id'] in APPROVED_EXTRA
                    if a['id'] in APPROVED_EXTRA: approved_found.add(a['id'])
                    pts = [r['value'] for r in a['result'] if r['type'] == 'keypointlabels']
                    flags = []
                    if len(pts) % 2: flags.append('奇数点待复核')
                    if not pts: flags.append('无点集')
                    if any(not math.isfinite(p[c]) or not 0 <= p[c] <= 100 for p in pts for c in ['x', 'y']):
                        flags.append('坐标范围异常')
                    if a.get('parent_annotation'): flags.append('父记录关联待核实')
                    row = dict(project=project, task_id=t['id'], annotation_id=a['id'], worker_id=w,
                               image_id=iid, admitted=admitted, flags=flags, parent=a.get('parent_annotation'))
                    observations.append(row); byworker[w].append(a['id'])
                    if flags or not admitted: issues.append(row)
                    if admitted: actual[iid].add(w)
                    if pair in required: required_done.add(pair)
                for w, ids in byworker.items():
                    if len(ids) > 1: duplicates.append(dict(project=project, image_id=iid, worker_id=w, annotation_ids=ids))
    assert approved_found == APPROVED_EXTRA
    expected = defaultdict(set, {iid: set(ws) for iid, ws in actual.items()})
    for r in assignments:
        expected[r['image_id']].add(r['worker_id']); seen[r['image_id']].add(r['worker_id'])
    inventory = []
    deferred_five = {f'uNb9QFRL6hY-{n:02d}' for n in [18, 26, 41, 59, 88]}
    for r in old['images']:
        iid = r['image_id']; h = history[iid]; now = h | actual[iid]; planned = h | expected[iid]
        s = selection.get(iid); user = s['effective_user_record'] if s else None
        adopted = bool(s and s['status'] == '确定采用')
        target = int(s['planned_manual']) if adopted else 0
        collection = user.get('collection') if user else None
        reason = '已采用、补齐稀疏视角；旧人数为预算目标，不是收敛阈值'
        if not adopted or collection == '仅复用历史':
            target = len(planned); reason = '仅复用/未采用，不安排新增'
        if r['code'] in deferred_five:
            target = len(planned); reason = '沿用不为19凑20自动加1人的决定'
        if r['history_manual'] >= 19:
            target = len(planned); reason = '高人数历史优先复用，不恢复统一加16人'
        low = adopted and r['difficulty'] == '简单' and 8 <= r['target'] <= 12 and collection != '仅复用历史'
        end = max(len(planned), target)
        inventory.append(dict(image_id=iid, code=r['code'], room=r['room'], scene=r['scene'],
            difficulty=r['difficulty'], oos=r['oos'], image_path=r['image_path'], adopted=adopted,
            original_decision=user, history_workers=sorted(h), actual_workers=sorted(now),
            planning_workers=sorted(planned), history_n=len(h), actual_n=len(now), planning_n=len(planned),
            target_now=target, need_now=max(0, target-len(planned)), expected_n=end,
            october_low_sample=low, october_target=max(15, end) if low else None,
            october_need=max(0, 15-end) if low else 0, reason=reason))
    pending = sorted([r for r in inventory if r['need_now']], key=lambda r:(r['room'], r['code']))
    assigned, slots = allocate(pending, seen)
    # 新人均未接触：只移动同图的一份安排，保持逐图人数不变并平衡负载。
    new_slots = [s for s in slots if s.startswith('新人')]
    while True:
        counts = Counter(a['slot'] for a in assigned)
        high = max(new_slots, key=lambda s: counts[s])
        low = min(new_slots, key=lambda s: counts[s])
        if counts[high] - counts[low] <= 1:
            break
        low_images = {a['image_id'] for a in assigned if a['slot'] == low}
        move = next(a for a in assigned if a['slot'] == high and a['image_id'] not in low_images)
        move['slot'] = low
    lookup = {r['image_id']: r for r in inventory}
    byslot = defaultdict(list)
    proposed = defaultdict(set)
    for a in assigned:
        byslot[a['slot']].append(a); proposed[a['image_id']].add(a['slot'])
    people = []
    for slot in slots:
        buckets = defaultdict(list)
        for a in byslot[slot]: buckets[a['room']].append(a)
        ordered = []
        while any(buckets.values()):
            for bucket in buckets.values():
                if bucket: ordered.append(bucket.pop(0))
        for i, a in enumerate(ordered, 1): a['order'] = i
        people.append(dict(slot=slot, tasks=len(ordered), rooms=len(buckets), scenes=len({a['scene'] for a in ordered})))
    october = [dict(code=r['code'], image_id=r['image_id'], room=r['room'], difficulty=r['difficulty'],
                    expected_before=r['expected_n'], target=r['october_target'], need=r['october_need'],
                    avoid_workers=r['planning_workers'], avoid_september_slots=sorted(proposed[r['image_id']]))
               for r in inventory if r['october_low_sample']]
    room_pairs = []
    for room in sorted({r['room'] for r in inventory if r['adopted']}):
        rr = [r for r in inventory if r['adopted'] and r['room']==room and r['expected_n']]
        for a,b in combinations(rr,2):
            am = {f'W{w:03d}' for w in a['planning_workers']} | proposed[a['image_id']]
            bm = {f'W{w:03d}' for w in b['planning_workers']} | proposed[b['image_id']]
            room_pairs.append(dict(room=room,left=a['code'],right=b['code'],common_people=len(am&bm),common_newcomers=len({x for x in am&bm if x.startswith('新人')})))
    assert len({(a['slot'],a['image_id']) for a in assigned}) == len(assigned)
    assert all(a['worker_id'] is None or a['worker_id'] not in seen[a['image_id']] for a in assigned)
    assert all(len(proposed[r['image_id']])==r['need_now'] for r in inventory)
    assert all(p['tasks'] <= (50 if p['slot'].startswith('新人') else 20) for p in people)
    assert all(r['expected_n']+r['october_need']>=15 for r in inventory if r['october_low_sample'])
    def stock(field):
        return dict(images=sum(r[field]>0 for r in inventory),people_images=sum(r[field] for r in inventory),
                    ge8=sum(r[field]>=8 for r in inventory),ge15=sum(r[field]>=15 for r in inventory))
    stats = dict(history=stock('history_n'),actual=stock('actual_n'),planning=stock('planning_n'),
                 after_september=stock('expected_n'),required_submitted=len(required_done),required_planned=len(required),
                 new_images=len(pending),new_tasks=len(assigned),newcomer_tasks=sum(a['worker_id'] is None for a in assigned),
                 existing_tasks=sum(a['worker_id'] is not None for a in assigned),october_images=len(october),
                 october_tasks=sum(r['need'] for r in october),approved_extra_ids=sorted(approved_found))
    OUT.mkdir(exist_ok=True)
    result=dict(schema='collection_plan_20260921_v1',sources=paths,stats=stats,people=people,images=inventory,
                assignments=assigned,october=october,room_pairs=room_pairs,issues=issues,duplicates=duplicates,
                observations=observations,checks='去重、暴露排除、人员上限、逐图缺口、10月目标均通过',
                interpretation='历史为既有可用Manual口径；新增为非空提交覆盖候选，非独立性/几何合格证明。原480份只在planning口径按补齐。',
                user_decisions=['新增16人；旧中文9人继续','缺5份规划视为将补齐','5份额外获准分析','低难度8至12人规划图10月全部补至少15人'],
                defaults=['新人上限50/旧人20；只补有依据的缺口，不凑满','10月最低目标15，人数未知，暂列图片缺口不虚构人员','现有中文沿用9人，W022额外提交不自动确认长期参与'])
    (OUT/'统计与安排.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    title='中文新增16人＋现有9人：候选安排与10月补齐'
    rows=['# '+title,'',f'本轮建议新增{stats["new_tasks"]}份、{len(pending)}图；新人{stats["newcomer_tasks"]}份，旧中文{stats["existing_tasks"]}份。10月对{october.__len__()}张既定简单8—12人图补{stats["october_tasks"]}份，最低到15人。','',
          '## 口径与选择依据','', '原480份在规划中视为将补齐，实际提交仍单列；5份额外已获准分析。新增覆盖含选做非空记录且同人同图只计一次。奇数点、父记录关联及重复作答取舍仍待核实，不能称为已新增独立可计算样本。',
          '仅在既有明确采用池内补稀疏视角，不恢复22张高人数历史统一追加，不将11图旧勾选作为新增授权。G184五图保持19人规划，不为凑20追加。OOS不自动排除。',
          '本候选沿用既有每图预算目标，未宣称统计充分；人员分配在满足缺口下压低新人最大负载。共同人员见逐对表，不保证每个房间全视角全员共同或每种AABC可组合。',
          '现有中文沿用9人；W022只批准本次额外记录，未自动加入后续人手。新人50张、旧人20张作为沿用上限，实际不凑满。所有新分配均为候选，需绑定新人身份并复查接触后才能派发。',
          '## 覆盖统计','', '| 口径 | 图片 | 人图 | ≥8人图片 | ≥15人图片 |','|---|---:|---:|---:|---:|']
    for k,label in [('history','历史基线'),('actual','历史＋当前非空提交'),('planning','加上5份预计补齐'),('after_september','本轮候选全完成后')]:
        s=stats[k];rows.append(f'| {label} | {s["images"]} | {s["people_images"]} | {s["ge8"]} | {s["ge15"]} |')
    rows+=['','## 逐人候选量','','| 人员/位置 | 张数 | 房间数 | 场景数 |','|---|---:|---:|---:|']
    for p in people:rows.append(f'| {p["slot"]} | {p["tasks"]} | {p["rooms"]} | {p["scenes"]} |')
    rows+=['','## 10月安排','', '名单由当前低难度和8—12人目标预先确定，包含届时已共识的图，不按9月是否分歧临时剔除。每图补到最低15人，按届时实际可用不同人员重新扣缺口；新旧队列分开报告。若9月未完成或质量核验减少可用人数，10月数量相应上调。未预设10月招募人数。',
           '## 验收与边界','', '候选未派发，新人ID空白；原9人本人既往提交、草稿、Semi接触及既有计划图均不重复安排。原始导出和历史分簇不变。详细统计、逐图与逐人列表在同目录HTML与JSON。',
           '35张简单低样本图来自既有明确采用池，不含“中等、12人”图；如需扩展低难度定义须另作决定。未用剩余工时自动扩大到未经用户采用的房间。']
    (OUT/'说明.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')
    def table(headers, values):
        return '<table><thead><tr>'+''.join('<th>'+escape(str(h))+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in row)+'</tr>' for row in values)+'</tbody></table>'
    html=['<!doctype html><meta charset="utf-8"><title>'+title+'</title><style>body{font:16px system-ui;max-width:1200px;margin:32px auto;padding:16px}table{border-collapse:collapse;width:100%;margin:16px 0}td,th{border:1px solid #ccc;padding:8px;text-align:left}th{background:#eef3f9}summary{cursor:pointer;padding:12px;background:#eef3f9}p{line-height:1.7}</style><h1>'+title+'</h1>',
          '<p>候选未派发。规划按原480份补齐；实际回收与可计算/独立性核验分开。新人身份待绑定。10月名单预先固定，不只追加出现分歧的图。</p>',
          table(['口径','图片','人图','≥8人图','≥15人图'],[[k,*stats[k].values()] for k in ['history','actual','planning','after_september']]),'<h2>本轮逐图候选</h2>',
          table(['图片','房间','难度','历史','实际','规划基础','本轮新增','预计','人员'],[[r['code'],r['room'],r['difficulty'],r['history_n'],r['actual_n'],r['planning_n'],r['need_now'],r['expected_n'],', '.join(sorted(proposed[r['image_id']]))] for r in pending]),'<h2>逐人任务</h2>']
    for p in people:
        html+=['<details><summary>'+escape(p['slot'])+f'：{p["tasks"]}张</summary>',table(['顺序','图片','房间','场景'],[[a['order'],a['code'],a['room'],a['scene']] for a in sorted(byslot[p['slot']],key=lambda a:a['order'])]),'</details>']
    html+=['<h2>10月低难度小样本补齐</h2>',table(['图片','房间','9月规划人数','10月目标','新增人数'],[[r['code'],r['room'],r['expected_before'],r['target'],r['need']] for r in october]),'<h2>同房视角对共同人员</h2>',table(['房间','图片A','图片B','共同人员','其中新人'],[[r[k] for k in ['room','left','right','common_people','common_newcomers']] for r in room_pairs])]
    (OUT/'安排总览.html').write_text('\n'.join(html),encoding='utf-8')
    print(json.dumps(stats,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
