"""15名新人最低50图，W018单列，候选优先、按同房组扩展。"""
from collections import Counter, defaultdict
from html import escape
from itertools import combinations

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import maximum_flow

from tools.thesis_main.analysis.build_collection_plan_20260921 import ROOT, read, CN

OUT = ROOT / 'analysis_results/collection_plan_20260921_v4'


def supplement_semi(inventory, manual, october):
    """复用历史自然输出候选；研究者元数据不是worker导入包。"""
    source = 'import_json/stage1_prescreen_final_20260325/stage1_prescreen_semi_import_v5.json'
    excluded = {r['image_id'] for r in manual + october}
    # 排除通行图wc-20与重复卧室e9-39；不按人员修改结果挑图。
    omitted = {'wc2JMjhGNzB-20', 'e9zR4mvMWw7-39'}
    images = []
    for task in read(source):
        data = task['data']; iid = data['base_task_id']; item = inventory[iid]
        if data['source_type'] not in {'control_natural', 'trap_natural'} or item['code'] in omitted:
            continue
        if iid in excluded or not task.get('predictions'):
            raise ValueError(f'Semi同图冲突或缺少原始初始化: {iid}')
        images.append(dict(image_id=iid, code=item['code'], room=item['room'], scene=item['scene'],
                           source_type=data['source_type'], source_import=source,
                           source_task_id=data['task_id'], original_data=data,
                           original_predictions=task['predictions'], review_status='历史自然预标注复用候选，待采用复核'))
    assert len(images) == 10
    assignments = [dict(slot=f'新人{n:02d}', image_id=r['image_id'], code=r['code'], condition='Semi',
                        order=k+1) for n in range(1,16)
                   for k,r in enumerate(images[(n-1)%10:]+images[:(n-1)%10])]
    return dict(images=images, assignments=assignments, tasks=len(assignments), per_newcomer=10,
                user_confirmation='每人额外10张Semi，Manual不减',
                status='候选，不是正式导入或派发表；原始初始化随附供复核',
                sequence='完成本轮Manual后再做Semi；轮换顺序仅分散次序，不宣称严格平衡',
                limitations=['保留历史control/trap标签；不视为当前正确性或难度金标准',
                             '尚未逐份比对历史运行时初始化；正式复用前需核对版本与图片/3D路由',
                             '未保证同房视角完全无先前接触；需结合房间台账记录顺序影响',
                             '10张仅初步观察修改行为，不承诺单独稳定分型；Manual/Semi分别统计'])


def fit(rows, seen, w18_tasks=20, old_tasks=30):
    """固定总量下为所有人员兑现配额；不可行则返回空，不丢弃任务。"""
    slots = [f'W{w:03d}' for w in CN] + ['W018'] + [f'新人{i:02d}' for i in range(1,16)]
    total = sum(r['need'] for r in rows)
    remaining = total - len(CN)*old_tasks - w18_tasks
    if remaining < 750:
        return None
    q, rem = divmod(remaining, 15)
    quotas = {s:old_tasks for s in slots[:9]}
    quotas['W018'] = w18_tasks
    quotas.update({s:q+(i<rem) for i,s in enumerate(slots[10:])})
    offset = len(rows)+1; sink=offset+len(slots)
    rr,cc,vv=[],[],[]
    def edge(a,b,c):rr.append(a);cc.append(b);vv.append(c)
    for i,r in enumerate(rows,1):
        edge(0,i,r['need'])
        for j,s in enumerate(slots):
            if s.startswith('新人') or int(s[1:]) not in seen[r['image_id']]:
                edge(i,offset+j,1)
    for j,s in enumerate(slots):edge(offset+j,sink,quotas[s])
    graph=coo_matrix((np.array(vv,dtype=np.int64),(rr,cc)),shape=(sink+1,sink+1)).tocsr()
    flow=maximum_flow(graph,0,sink)
    if flow.flow_value != total:return None
    result=[dict(slot=s,worker_id=None if s.startswith('新人') else int(s[1:]),
                 image_id=r['image_id'],code=r['code'],room=r['room'],scene=r['scene'],
                 phase=r['phase'],review_status=r['review_status'],reason=r['reason'])
            for i,r in enumerate(rows,1) for j,s in enumerate(slots) if flow.flow[i,offset+j]>0]
    counts = Counter(a['slot'] for a in result)
    assert all(counts[s] == q for s, q in quotas.items())
    return result,quotas


def main():
    import json
    import re
    import gzip
    base=read('analysis_results/collection_plan_20260921/统计与安排.json')
    registry=read('analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json')
    selection=read('analysis_results/candidate_selection_review_20260913_v2/选用复核机器表.json')
    decisions={r['image_id']:r for r in selection['images']}
    doorway={r['image_id']:r for r in read('analysis_results/scene_image_exploration_20260910_v1/门洞人工与AI历轮核对_20260913.json')['rows']}
    def boundary(i):
        d=doorway[i]
        note=decisions.get(i,{}).get('effective_user_record',{}).get('note','')
        general=d.get('general_boundary') or ''
        return d['doorway']['current_working_label']!='否' or ('交界' in general and '暂不归入' not in general) or '交界' in note
    inventory={r['image_id']:dict(r) for r in base['images']}
    groups={g['review_code']:g for g in registry['groups']}
    seen=defaultdict(set)
    for r in read('import_json/scene_stability_stage1_20260913_v2/historical_exposure.json'):seen[r['image_id']].add(r['worker_id'])
    with gzip.open(ROOT/'analysis_results/clustering_release_local_20260920/current/inputs/responses.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            r=json.loads(line);seen[r['image_id']].add(int(r['worker_id'][1:]))
    for r in read('import_json/scene_stability_stage1_20260913_v2/required_assignments.json'):seen[r['image_id']].add(r['worker_id'])
    for path in base['sources']:
        for t in read(path):
            iid=t['data']['base_task_id']
            for a in t['annotations']:seen[iid].add(a['completed_by'])
            for d in t['drafts']:
                m=re.search(r',\s*(\d+)\s*$',d.get('created_username',''))
                if not m:raise ValueError('未知草稿人员')
                seen[iid].add(int(m[1]))
    adopted={i for i,r in inventory.items() if r['adopted']}
    rows=[];chosen=set()
    def add(i,room,phase,review,reason,target=None):
        if i in chosen:return
        r=inventory[i]
        target=r['target_now'] if target is None else target
        need=max(0,target-r['planning_n'])
        if not need:return
        rows.append(dict(image_id=i,code=r['code'],room=room,scene=r['scene'],difficulty=r['difficulty'],
                         base_n=r['planning_n'],target=target,need=need,phase=phase,review_status=review,
                         original_user=decisions.get(i,{}).get('effective_user_record'),oos=r['oos'],reason=reason))
        chosen.add(i)
    for r in inventory.values():
        if r['need_now']:add(r['image_id'],r['room'],1,'既有明确采用','先完成既有44图缺口')
    assert sum(r['need'] for r in rows)==524
    candidates=[c for c in registry['candidates'] if c['physical_same_supported']]
    # 优先补已有采用房间；按图保留备用/条件意见，规划不修改采用真源。
    for c in candidates:
        if set(c['image_ids']) & adopted:
            for i in c['image_ids']:
                if i not in adopted and not boundary(i):
                    add(i,c['candidate_id'],2,'同房备用，待采用复核','已有采用房间的其他视角；保留原文边界疑虑',15)
    existing_scenes=Counter(r['scene'] for r in inventory.values() if r['planning_n']>=8)
    candidates.sort(key=lambda c:(
        -sum(not boundary(i) for i in c['image_ids']),
        not any(inventory[i]['planning_n'] for i in c['image_ids']),
        min(existing_scenes[inventory[i]['scene']] for i in c['image_ids']),
        -len(c['image_ids']), c['candidate_id']))
    queue=[]
    for c in candidates:
        ids=[i for i in c['image_ids'] if i not in chosen and i not in adopted and not boundary(i)
             and inventory[i]['planning_n']<15]
        if not ids:continue
        # 明确反对采用者不被大范围覆盖要求静默翻转；其余未决保留为复核条件。
        blocked=[i for i in ids if decisions.get(i,{}).get('effective_user_record',{}).get('selection')=='不采用']
        ids=[i for i in ids if i not in blocked]
        queue.append(dict(candidate=c['candidate_id'],image_ids=ids,blocked=blocked,
                          review_state=c['review_state'],holds=c['selection_hold_reasons']))
    fit_result=fit(rows,seen)
    used_groups=[]
    for c in queue:
        if fit_result:break
        if not c['image_ids']:continue
        used_groups.append(c['candidate'])
        for i in c['image_ids']:
            add(i,c['candidate'],3,'同房关系有依据；新增采用待复核',
                '沿用整房优先：普通可用视角多的组优先，再考虑已有数据与场景覆盖；交界留储备，普通视角补至15',15)
        fit_result=fit(rows,seen)
    if not fit_result:raise ValueError('全部候选仍无法满足每名新人最低50图及W018配额')
    allocated,quotas=fit_result
    candidate_map = {c['candidate_id']:c for c in candidates}
    for r in rows:
        c = candidate_map.get(r['room'])
        r['selection_holds'] = c['selection_hold_reasons'] if c else []
        if r['phase'] == 3 and r['selection_holds']:
            r['review_status'] = '范围/OOS等用途待定；保留差异研究价值，采用待复核'
    row_by_id = {r['image_id']:r for r in rows}
    for a in allocated:
        a['review_status'] = row_by_id[a['image_id']]['review_status']
    byslot=defaultdict(list);members=defaultdict(set)
    for a in allocated:byslot[a['slot']].append(a);members[a['image_id']].add(a['slot'])
    for slot,items in byslot.items():
        ordered=[]
        for phase in [1,2,3]:
            buckets=defaultdict(list)
            for a in sorted(items,key=lambda a:(a['room'],a['code'])):
                if a['phase']==phase:buckets[a['room']].append(a)
            while any(buckets.values()):
                for bucket in buckets.values():
                    if bucket:ordered.append(bucket.pop(0))
        for k,a in enumerate(ordered,1):a['order']=k
    october=[]
    for original in base['october']:
        r=dict(original); iid=r['image_id']
        r['avoid_september_slots']=sorted(members[iid])
        r['avoid_workers']=sorted(set(inventory[iid]['planning_workers']) |
                                 {int(s[1:]) for s in members[iid] if s.startswith('W')})
        assert r['expected_before']==len(inventory[iid]['planning_workers'])+len(members[iid])
        october.append(r)
    semi=supplement_semi(inventory,rows,october)
    assert not any(r['october_low_sample'] and r['image_id'] in chosen and
                   next(x['target'] for x in rows if x['image_id']==r['image_id'])!=r['target_now']
                   for r in inventory.values())
    assert len({(a['slot'],a['image_id']) for a in allocated})==len(allocated)
    assert all(a['worker_id'] is None or a['worker_id'] not in seen[a['image_id']] for a in allocated)
    assert all(len(members[r['image_id']])==r['need'] for r in rows)
    assert all(quotas[f'新人{i:02d}']>=50 for i in range(1,16))
    byroom=defaultdict(set)
    for r in rows:byroom[r['room']].add(r['image_id'])
    room_summary=[]
    for room,ids in byroom.items():
        sets=[members[i]|{f'W{w:03d}' for w in inventory[i]['planning_workers']} for i in ids]
        room_summary.append(dict(room=room,planned_views=len(ids),common_all_planned_views=len(set.intersection(*sets)),
             pair_min_common=min((len(a&b) for a,b in combinations(sets,2)),default=None),
             note='仅本轮计划视角；同房候选子集可重叠，不等同独立房间数'))
        all_ids = [i for i in candidate_map.get(room,{}).get('image_ids',list(ids))
                   if inventory[i]['planning_workers'] or members[i]]
        all_sets = [members[i]|{f'W{w:03d}' for w in inventory[i]['planning_workers']} for i in all_ids]
        room_summary[-1].update(covered_views=len(all_ids),
            common_all_covered_views=len(set.intersection(*all_sets)),
            covered_members={inventory[i]['code']:sorted(s) for i,s in zip(all_ids,all_sets)},
            selection_holds=candidate_map.get(room,{}).get('selection_hold_reasons',[]))
    remaining=[]
    for c in queue:
        ids=[i for i in c['image_ids'] if i not in chosen]
        if ids:remaining.append(dict(candidate=c['candidate'],codes=[inventory[i]['code'] for i in ids],
                                    image_ids=ids,holds=c['holds'],status='后续同房扩展储备，未派发'))
    stats=dict(images=len(rows),tasks=len(allocated),newcomer_tasks=sum(v for k,v in quotas.items() if k.startswith('新人')),
               w18_tasks=quotas['W018'],old9_tasks=sum(quotas[f'W{w:03d}'] for w in CN),
               phases={str(p):dict(images=sum(r['phase']==p for r in rows),tasks=sum(r['need'] for r in rows if r['phase']==p)) for p in [1,2,3]},
               october_images=len(october),october_tasks=sum(r['need'] for r in october),
               reserve_unique_images=len({i for r in remaining for i in r['image_ids']}))
    boundary_reserve=[dict(image_id=i,code=r['code'],label=doorway[i]['doorway']['current_working_label'],
                          general_boundary=doorway[i].get('general_boundary'),original_user=decisions.get(i,{}).get('effective_user_record'))
                      for i,r in inventory.items() if boundary(i)]
    stats['selected_boundary_images']=sum(boundary(r['image_id']) for r in rows)
    counts=[len(r['planning_workers'])+len(members[i]) for i,r in inventory.items()]
    baseline_stats={k:base['stats'][k] for k in ['history','actual','planning','required_submitted','required_planned','approved_extra_ids']}
    baseline_stats['after_september']=dict(images=sum(n>0 for n in counts),people_images=sum(counts),
                                          ge8=sum(n>=8 for n in counts),ge15=sum(n>=15 for n in counts))
    stats.update(semi_images=len(semi['images']),semi_tasks=semi['tasks'],combined_tasks=len(allocated)+semi['tasks'])
    result=dict(schema='collection_plan_20260921_v4',stats=stats,quotas=quotas,images=rows,assignments=allocated,semi=semi,
                boundary_reserve=boundary_reserve,
                room_coverage=room_summary,october=october,reserve=remaining,baseline_stats=baseline_stats,
                prior_plan='analysis_results/collection_plan_20260921/统计与安排.json',
                defaults=['15名新人每人至少50张新任务','W018已有66份历史可用Manual，另新增20张','旧中文9人各30张',
                          '新扩展图暂按15人预算，不把未知难度归为简单；既有简单8—12人数留待10月补齐',
                          '新增采用待复核，身份待绑定；暂未形成正式派发表'],
                caveats=['50张是采集要求，不是人员分类可靠性证明','未按本轮目标图结果选择人员类型','全量同房储备仍有未覆盖，不称全部完成'])
    OUT.mkdir(exist_ok=True)
    (OUT/'统计与安排.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 新人15人＋W018：Manual与Semi候选','',
           f'替代v3。本轮Manual候选{stats["images"]}图、{stats["tasks"]}份：15名新人{stats["newcomer_tasks"]}份，W018 {stats["w18_tasks"]}份，旧9人270份。另加10张Semi、15人各10份，共150份；本轮合计1202份，十月206份另计。',
           '', '## Semi补充（用户已确认工作量，逐图采用仍待复核）','',
           '用户原话：“每人额外10张Semi，Manual不减”。15名新人共用10张历史自然模型预标注，5张旧control、5张旧trap_natural；不复用他人修改后的答案，不纳入人工构造错误。排除通行图wc-20及重复卧室e9-39，不根据人员作答结果选图。',
           '与本轮Manual及十月队列无同图重叠；建议完成Manual后再做Semi。循环轮换顺序仅分散次序，不保证严格平衡或消除同房接触影响。原始data与predictions在JSON的semi字段中；它是研究候选资料，不可直接作为worker导入包。历史运行时初始化一致性及路由尚需验收。',
           '| Semi图片 | 场景 | 历史预标注条件 |','|---|---|---|',
           *[f'| {r["code"]} | {r["scene"]} | {r["source_type"]} |' for r in semi['images']],
           '', '## 独立核对外部建议','',
           'Manual预计297图、3529人图成立（包含未收齐5份的规划假设），不等于可计算性验收。修复了生成器沿用旧版272图/3001人图以及16张十月排除名单不一致的问题；不覆盖外部审计历史文件。',
           '四个扩展组G051/G124/G155/G180的范围或OOS用途待定，共20图261份。JSON和逐图页保留其selection_holds，不把未确认门洞当作已确认普通可比空间，也不删除其研究价值。',
           '共同人员建议方向合理，但不能承诺只在原1052份内换名单即可解决。G078的Z6-08及G090的e9-15、e9-26已有8人全为英文人员，本轮没有给这些视角分配中文新任务；无论怎样交换其他图，都不能得到全组共同中文人员。房间摘要现同时列出本轮视角与全部已覆盖视角。',
           '下一步如研究同一人跨视角，需增加这些固定视角上的共同人员，或重新授权英文人手/调整每图配额；本版未替用户改变负载与采用。当前仍可比较不同人员构成下的分布，但须报告构成差异。外部52组和398图对口径本轮未全量独立复算，不把图对当独立房间。',
           '', '## 优先顺序','',
           '1. 先完成既有44图524份缺口；不恢复高人数22图统一追加，不为G184五图凑20。',
           '2. 回查旧批次：按采用后视角数优先整房，门洞专项主要在英文选做H。uNb-71/uNb-10本轮移回交界储备。',
           '3. 同房扩展按非交界可用视角数优先，再考虑已有数据、场景覆盖；普通视角按15人预算。确认/疑似门洞、一般交界及用户明确交界文字均下调，不把OOS自动当作门洞。',
           '', '## 人员','', '| 人员 | 本轮新增图数 |','|---|---:|']
    for s,q in quotas.items():lines.append(f'| {s} | {q} |')
    lines+=['','W018是旧身份，89图历史接触/66份历史可用Manual不作为新人空白记录；本轮候选不重复任何已知本人提交或草稿图。W022不自动加入长期中文人手。',
            '', '## 10月与仍未覆盖','',
            f'既有35张简单8—12人图仍预计补206份到至少15人；排除名单已按本版Manual分配重建，仅有15名新人位置。新增扩展图难度未定，暂按15人，不加入简单小样本队列。',
            f'同房储备去重后还有{stats["reserve_unique_images"]}张未进入本轮，完整储备见JSON；不把候选子集数当作独立房间数。',
            '', '## 审核与统计边界','',
            '候选先做的含义是先完成其规划重复人数，而不是每人都重复全部44图；后者会破坏简单图8—12人阶段。15名新人最低50张通过扩展不同图片实现。',
            '本轮新增备用与其他同房图的人工采用未自动确认，原文字保留；清单为可审核候选，不是已派发任务。50张不能自动证明可稳定划分人员类别，应在其他房间验证。',
            '规划继续按原480份将补齐、5份额外获准纳入；实际数据的奇数点、父记录和重复来源问题单列，未改原始数据或几何结果。',
            '用户最新授权W018另外新增20张，原9人各30张；本人历史提交与草稿均不重复。人数满足不等于分类已经验证。',
            '生成时验证：逐人配额、每图缺口、同人同图唯一性、历史暴露排除、15新人最低50及10月队列保持检查均通过。',
            '回归命令：python -m pytest tests/test_collection_plan_20260921.py tests/test_audit_collection_plan_20260921.py -q。覆盖Semi原始初始化完整保留、无同图重叠、当前十月排除名单、旧Manual分配保持及覆盖总量。',
            '交付检查：相关6项测试通过，JSON/HTML内容核对及git diff --check通过；未做浏览器视觉验收或历史运行时初始化逐份验收。未运行无关全库测试。项目地图与README已更新v4入口；原始导出、正式protocol/schema/routing/SOP与worker派发未改。']
    (OUT/'说明.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    def table(headers,values):
        return '<table><tr>'+''.join('<th>'+escape(str(h))+'</th>' for h in headers)+'</tr>'+''.join('<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in row)+'</tr>' for row in values)+'</table>'
    html=['<!doctype html><meta charset="utf-8"><title>中文后续安排v4</title><style>body{font:16px system-ui;max-width:1200px;margin:32px auto;padding:16px}table{border-collapse:collapse;width:100%;margin:18px 0}td,th{border:1px solid #ccc;padding:8px;text-align:left}th,summary{background:#edf3fa;padding:12px}summary{cursor:pointer}</style>',
          '<h1>15名新人＋W018：普通同房视角优先</h1><p>新人至少50图；W018新增20图，旧9人各30图。先原候选，再按普通可用视角数优先同房组；交界视角留储备，未派发。</p>',
          '<p>另加新人每人10张Semi，共150份；Manual1052份不减，合计1202份。所有新增采用仍为候选。</p>',
          '<h2>Semi共用候选（每人10张）</h2>',table(['图片','场景','历史初始化类型'],[[r['code'],r['scene'],r['source_type']] for r in semi['images']]),
          table(['阶段','图数','份数'],[[p,v['images'],v['tasks']] for p,v in stats['phases'].items()]),
          '<h2>逐图候选</h2>',table(['阶段','图片','房间','原人数','目标','新增','采用状态','用户原文'],
          [[r['phase'],r['code'],r['room'],r['base_n'],r['target'],r['need'],r['review_status']+'；'+'；'.join(r['selection_holds']),(r['original_user'] or {}).get('note','')] for r in rows]),'<h2>逐人Manual安排</h2>']
    for s,q in quotas.items():
        html+=['<details><summary>'+escape(s)+f'：{q}张</summary>',table(['顺序','阶段','图片','房间','采用状态'],
               [[a['order'],a['phase'],a['code'],a['room'],a['review_status']] for a in sorted(byslot[s],key=lambda a:a['order'])]),'</details>']
    html+=['<h2>10月固定低难度队列</h2>',table(['图片','当前阶段预计人数','10月目标','补量'],[[r['code'],r['expected_before'],r['target'],r['need']] for r in october]),
           '<h2>同房共同人员</h2>',table(['组','本轮视角数','本轮共同人数','本轮逐对最少共同人数','全部已覆盖视角','全部已覆盖视角共同人数'],[[r['room'],r['planned_views'],r['common_all_planned_views'],r['pair_min_common'],r['covered_views'],r['common_all_covered_views']] for r in room_summary])]
    (OUT/'安排总览.html').write_text('\n'.join(html),encoding='utf-8')
    print(json.dumps(stats,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
