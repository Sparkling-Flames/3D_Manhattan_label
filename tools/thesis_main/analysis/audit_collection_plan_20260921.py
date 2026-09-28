"""只读核对 v3 采集草案；输出覆盖与负载审计，不派发、不改计划或原始数据。"""
import gzip
import json
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/collection_plan_20260921_audit'


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8-sig'))


def blocks(candidates):
    """重叠支持关系仅用于防泄漏分块，不传递生成已确认的同房配对。"""
    parent = {}
    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            x = parent[x]
        return x
    for c in candidates:
        ids = c['image_ids']
        for iid in ids:
            parent[find(iid)] = find(ids[0])
    return {i: find(i) for i in parent}


def main():
    base = read('analysis_results/collection_plan_20260921/统计与安排.json')
    plan = read('analysis_results/collection_plan_20260921_v3/统计与安排.json')
    registry = read('analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json')
    required = read('import_json/scene_stability_stage1_20260913_v2/required_assignments.json')
    images = {i['image_id']: i for i in base['images']}
    with gzip.open(ROOT / 'analysis_results/clustering_release_local_20260920/current/inputs/responses.jsonl.gz', 'rt', encoding='utf8') as f:
        history = [json.loads(l) for l in f]
    pools = {s: {i: set() for i in images} for s in ['history', 'actual', 'planning', 'after_v3', 'semi']}
    for row in history:
        w, iid = row['worker_id'], row['image_id']
        assert iid in images
        if w in {'W019', 'W026'}:
            continue
        if row['unassisted_manual_included']:
            assert row['calculation_included']
            pools['history'][iid].add(w)
        if row['calculation_included'] and row['assistance_exposure'] == 'model_preannotation':
            pools['semi'][iid].add(w)
    # 回查本轮覆盖清单的原始标注身份；不把点数/父记录告警当成已验收。
    raw = {}
    seen = defaultdict(set)
    for r in history:
        seen[r['image_id']].add(r['worker_id'])
    for r in read('import_json/scene_stability_stage1_20260913_v2/historical_exposure.json') + required:
        seen[r['image_id']].add(f"W{r['worker_id']:03d}")
    for source in base['sources']:
        for task in read(source):
            for ann in task['annotations']:
                raw[(int(task['project']), ann['id'])] = (task, ann)
                seen[task['data']['base_task_id']].add(f"W{int(ann['completed_by']):03d}")
            for draft in task['drafts']:
                match = re.search(r',\s*(\d+)\s*$', draft['created_username'])
                assert match, '草稿身份无法解析'
                seen[task['data']['base_task_id']].add(f'W{int(match[1]):03d}')
    for iid in images:
        assert pools['history'][iid] == {f'W{w:03d}' for w in images[iid]['history_workers']}
        pools['actual'][iid] = pools['history'][iid].copy()
    for o in base['observations']:
        task, ann = raw[o['project'], o['annotation_id']]
        assert task['id'] == o['task_id'] and int(ann['completed_by']) == o['worker_id']
        assert task['data']['base_task_id'] == o['image_id']
        if o['admitted'] and o['worker_id'] not in {19, 26}:
            pools['actual'][o['image_id']].add(f"W{o['worker_id']:03d}")
    for iid in images:
        assert pools['actual'][iid] == {f'W{w:03d}' for w in images[iid]['actual_workers']}
        pools['planning'][iid] = pools['actual'][iid].copy()
    for row in required:
        pools['planning'][row['image_id']].add(f"W{row['worker_id']:03d}")
    for iid in images:
        assert pools['planning'][iid] == {f'W{w:03d}' for w in images[iid]['planning_workers']}
        pools['after_v3'][iid] = pools['planning'][iid].copy()
    for row in plan['assignments']:
        assert row['slot'] not in seen[row['image_id']]
        assert row['slot'] not in pools['after_v3'][row['image_id']]
        pools['after_v3'][row['image_id']].add(row['slot'])
    assert len(plan['assignments']) == 1052
    assert Counter(r['slot'] for r in plan['assignments']) == plan['quotas']
    assert sum(map(len, pools['after_v3'].values())) - sum(map(len, pools['planning'].values())) == 1052
    supported = [c for c in registry['candidates'] if c['physical_same_supported']]
    family = blocks(supported)
    assert len(set(blocks([{'image_ids': ['a','b']}, {'image_ids': ['b','c']}]).values())) == 1
    all_room_rows, summaries = [], {}
    for stage, pool in pools.items():
        rows = []
        for c in supported:
            ids = [i for i in c['image_ids'] if pool[i]]
            if len(ids) < 2:
                continue
            pairs = [(a,b,len(pool[a] & pool[b])) for a,b in combinations(ids,2)]
            rows.append(dict(stage=stage, group=c['candidate_id'], family=family[ids[0]],
                codes=[images[i]['code'] for i in ids], counts=[len(pool[i]) for i in ids],
                total_candidate_views=len(c['image_ids']),
                unobserved_codes=[images[i]['code'] for i in c['image_ids'] if not pool[i]],
                comparable=c['comparable_for_prediction'], oos_pending=c['oos_pending'],
                holds=c['selection_hold_reasons'], common_all=len(set.intersection(*(pool[i] for i in ids))),
                minimum_pair_common=min(p[2] for p in pairs),
                pairs=[dict(left=images[a]['code'], right=images[b]['code'], common=n) for a,b,n in pairs]))
        all_room_rows += rows
        summary = dict(images=sum(bool(v) for v in pool.values()), person_images=sum(map(len,pool.values())),
            images_ge8=sum(len(v)>=8 for v in pool.values()), images_ge15=sum(len(v)>=15 for v in pool.values()), rooms={})
        for band in [1,8,15]:
            for subset in ['supported', 'comparable_non_oos_pending']:
                selected = [r for r in rows if sum(n>=band for n in r['counts'])>=2 and
                    (subset=='supported' or (r['comparable'] and not r['oos_pending']))]
                eligible = {c['candidate_id'] for c in supported if c['candidate_id'] in {r['group'] for r in selected}}
                pairs = set()
                for c in supported:
                    if c['candidate_id'] in eligible:
                        pairs.update(tuple(sorted((a,b))) for a,b in combinations(c['image_ids'],2) if len(pool[a])>=band and len(pool[b])>=band)
                summary['rooms'][f'{subset}_ge{band}'] = dict(candidate_subsets=len(selected),
                    leakage_blocks=len({r['family'] for r in selected}), unique_image_pairs=len(pairs),
                    fully_covered_subsets=sum(not r['unobserved_codes'] and min(r['counts'])>=band for r in selected),
                    pairs_with_shared_worker=sum(bool(pool[a]&pool[b]) for a,b in pairs),
                    pairs_common_ge8=sum(len(pool[a]&pool[b])>=8 for a,b in pairs))
        summaries[stage] = summary
    workers = sorted(set().union(*(set().union(*p.values()) for p in pools.values())))
    people = [dict(worker=w, **{s:sum(w in v for v in p.values()) for s,p in pools.items()},
                   new_round=plan['quotas'].get(w,0)) for w in workers]
    scenes = []
    for scene in sorted({i['scene'] for i in images.values()}):
        ids = [i for i in images if images[i]['scene']==scene]
        row = dict(scene=scene)
        for stage in ['history','actual','planning','after_v3','semi']:
            chosen = [i for i in ids if pools[stage][i]]
            row[stage] = dict(images=len(chosen), buildings=len({i.split('_')[0] for i in chosen}),
                supported_room_blocks=len({family[i] for i in chosen if i in family}),
                no_supported_room_images=sum(i not in family for i in chosen),
                images_ge8=sum(len(pools[stage][i])>=8 for i in chosen),
                images_ge15=sum(len(pools[stage][i])>=15 for i in chosen))
        scenes.append(row)
    october = []
    for row in plan['october']:
        now = sorted(a['slot'] for a in plan['assignments'] if a['image_id']==row['image_id'])
        assert max(0, 15-len(pools['after_v3'][row['image_id']])) == row['need']
        old = row['avoid_september_slots']
        october.append(dict(code=row['code'], need=row['need'], old_slots=old, v3_slots=now,
            obsolete_slots=sorted(set(old)-set(now)), missing_slots=sorted(set(now)-set(old))))
    selected_groups = []
    for c in supported:
        rows = [i for i in plan['images'] if i['phase']==3 and i['room']==c['candidate_id']]
        if rows:
            selected_groups.append(dict(group=c['candidate_id'], codes=[i['code'] for i in rows],
                tasks=sum(i['need'] for i in rows), comparable=c['comparable_for_prediction'],
                oos_pending=c['oos_pending'], holds=c['selection_hold_reasons'], review_state=c['review_state']))
    result = dict(schema='collection_plan_20260921_independent_audit_v1',
        scope='候选覆盖与负载核算；未完成新增几何、独立作答与时间验收；不派发。',
        denominator='Manual按人×图去重，排除W019/W026；Semi单列。原始奇数点以确认后的计算视图为准。',
        room_rule='至少两张有作答的视角；8/15仅覆盖展示档，不是收敛或预测资格门槛。防泄漏块不等于确认的独立房间。',
        summaries=summaries, workers=people, rooms=all_room_rows, scenes=scenes,
        selected_new_groups=selected_groups, october_assignment_drift=october,
        new_record_flags=base['issues'], duplicates=base['duplicates'])
    new_pairs = {(o['worker_id'],o['image_id']) for o in base['observations'] if o['admitted']}
    result['repeated_historical_person_images'] = [dict(worker=f'W{w:03d}', code=images[i]['code'])
        for w,i in sorted(new_pairs) if f'W{w:03d}' in pools['history'][i]]
    result['checks'] = dict(raw_observations=len(base['observations']), unique_new_person_images=len(new_pairs),
        old_person_image_overlap=len(result['repeated_historical_person_images']),
        new_unique_manual_coverage=summaries['actual']['person_images']-summaries['history']['person_images'],
        required_remaining=summaries['planning']['person_images']-summaries['actual']['person_images'],
        known_worker_exposure_check='pass; 新人占位符仍须绑定真实身份后检查',
        forecast_all_condition_images=len({i for i in images if pools['after_v3'][i] or pools['semi'][i]}))
    OUT.mkdir(exist_ok=True)
    (OUT/'核算明细.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    write_report(result)
    print(json.dumps(dict(output=str(OUT), summaries=summaries,
        october_drift_images=sum(bool(x['obsolete_slots'] or x['missing_slots']) for x in october)),ensure_ascii=False,indent=2))


def write_report(a):
    lines = ['# 9月21日 v3 采集方案独立审查', '',
        '结论：整房、多视角、优先补低覆盖的方向合适；当前应作为待复核草案，不能把1052份或八个新增组当成已经验收的预测样本。没有必要恢复给历史高人数图片普遍加人的做法。本轮83图补采前最多8人，没有历史19人及以上图片。', '',
        '本次只读回查2501份冻结记录、三份新导出、原480份安排及v3分配；未重新审图、未派发、未改变正式Paper A合同。原始奇数点已有人工补/删且计算视图纳入者仍计入；新导出异常尚未据此自动修正。', '',
        '## 一、全量覆盖与可开展的预测比较', '',
        'Manual按人×图去重，排除W019/W026；OOS仍保留研究价值。新导出及未来作答均只是覆盖核算，不冒充几何、独立作答与冻结时间已验收。预测数量不等于预测效果或收敛已获证明。', '',
        '| 阶段 | Manual图片 | Manual人图 | 同房候选组：至少两视角有作答 | 其中范围可比且非OOS待定 |',
        '|---|---:|---:|---:|---:|']
    for key,label in [('history','历史冻结'),('actual','含本次已提交导出'),('planning','再完成原必做剩余5份'),('after_v3','再完成本轮1052份')]:
        s=a['summaries'][key]
        lines.append(f"| {label} | {s['images']} | {s['person_images']} | {s['rooms']['supported_ge1']['candidate_subsets']} | {s['rooms']['comparable_non_oos_pending_ge1']['candidate_subsets']} |")
    lines += ['', '预计52组共398个不重复的无向图对，其中373对有共同人员；范围较可比子集24组、185图对，其中172对有共同人员。图对不是独立房间样本，也不是398次独立实验。只使用直接候选关系生成图对；重叠关系形成防泄漏块，不传递生成新的已确认配对。这里候选组数与相应防泄漏块数恰好一致，不能据此跳过物理房间验收。', '',
        '52组中37组全部候选视角至少有一份作答。若要求至少两视角各达到8人，为35组（较可比20组）；各达到15人，为24组（较可比11组）。若要求组内全部候选视角均达到15人，则为16组（较可比10组）。8/15只是展示覆盖的档位，不是预测或收敛成立的门槛。', '',
        '其余28组的范围/OOS等未决不能当作研究无价值；可用于差异、不确定性及适用边界分析。较可比子集是额外分析标签，不能因预测不好再删图。', '',
        f"另有历史Semi 43图、538人图，支持2个至少两视角的同条件候选组、4个图对；不能与Manual人数混成无辅助样本。完成本轮后，Manual与Semi的图片并集为{a['checks']['forecast_all_condition_images']}张；不是297+43直接相加。", '',
        '同场景按现有粗类可形成以下八类研究池，其中七类跨多个建筑；特殊用途目前只有一个建筑，只能支持楼内探索，不能单独证明跨建筑泛化。粗类不是一个独立房间，也不保证任意两图相似。工作与学习虽然有9图，但只涉及2个有支持关系的房间块，独立房间覆盖很薄。', '',
        '| 场景 | 预计Manual图片 | 建筑 | 有支持关系的房间块 | 无已支持房间关系的图片 | ≥15人图片 |',
        '|---|---:|---:|---:|---:|---:|']
    for r in a['scenes']:
        if r['scene'] in {'主空间待定','无法判断','开放复合空间'}:
            continue
        s=r['after_v3']; lines.append(f"| {r['scene']} | {s['images']} | {s['buildings']} | {s['supported_room_blocks']} | {s['no_supported_room_images']} | {s['images_ge15']} |")
    lines += ['', '另有主空间待定14图、无法判断1图、旧开放复合空间标签3图，保留，暂不强塞进明确同类型池。各类房间块可能重复，不相加当成总房间数。未归组图片可按建筑留出做保守分析，不能每图虚构成一个独立房间。', '',
        '## 二、逐人预计量', '',
        '以下累计为Manual覆盖人图，包含历史及本次已提交覆盖，不包含十月尚未分到个人的206份；新增提交尚待资格核验。Semi为另一个条件的历史量，不能直接加成同条件预测人数。执行新人数尚须确认并绑定真实身份；新人01—15只是占位符。', '',
        '| 人员 | 冻结历史Manual | 含当前提交 | 原必做尚缺 | 本轮新增 | 完成本轮累计Manual | 历史Semi另列 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for r in a['workers']:
        lines.append(f"| {r['worker']} | {r['history']} | {r['actual']} | {r['planning']-r['actual']} | {r['new_round']} | {r['after_v3']} | {r['semi']} |")
    lines += ['', '十月206份目标仍与v3几何覆盖数量一致，若全部完成Manual总量预计3735人图，但逐人负载尚不能承诺。15新人50—51张可形成初步人员画像，不代表分类已经稳定。必须按留建筑训练/评价，不能用目标图结果给人员定类后再评价目标图。', '',
        '## 三、方案需要修正或说明的地方', '',
        '1. 新增八组中四组有现存用途待定，共20图、261份：G051、G124、G155、G180。算法只检查支持同房，未把可比性/OOS未决作为优先级条件。这不是自动删除依据，但必须显示用途和你的原话，不能统称已可用普通预测组。',
        '2. 整房选图不等于共同人员覆盖。只看本轮安排，G090四图仅1人全组共同；接入历史后，G090六个有Manual视角、G078四个视角均无全组共同人员，且部分图对共同人数为0。若主要分析固定人员的跨视角迁移，需要先在同预算内调配共同人员；若比较不同人员抽样下的分布，仍可用，但须与人员构成差异分开解释。',
        '3. 十月排除表直接沿用v1：35图中16图的“本轮已接触人员”已变化，仍出现不存在于v3的新人16。人数缺口206没有变，但派发前必须按v3实际执行记录重新生成排除名单。详见核算明细中的october_assignment_drift。',
        '4. v3的baseline_stats.after_september仍是v1结果272图/3001人图，不能作为v3总量；v3应为297图/3529人图。当前审核报告独立纠正了口径，未覆盖原计划文件。',
        '5. 新导出640记录→639个不同人图；其中10个人图与历史重叠，净新增覆盖629，所以1843+629=2472。重做/修订不是新人票。尚有45条父记录关联、3条奇数点，以及W034的7271/7272同人同图两份记录需要本地选择版本和核对独立性；不等于自动判无效。旧人工已确认复原不重新判奇数不可用。',
        '6. 1052是兑现人员配额、整组加入时得到的可行预算，不是证明必要的最小采集量。排除本轮门洞优先仅是采集范围，不应删掉历史交界/OOS/错误表达，也不能把本批结果推广为全部场景的自然分布。', '',
        '## 四、用户审核顺序', '',
        '优先处理新增采用与用途：先G180、G124，再G155、G051、G201，最后G130、G234、G235的整组采用确认。没有新矛盾的既有物理同房事实不重问；原文与当前用途分别保留。', '',
        '| 组 | 本轮图片 | 新增作答 | 当前台账待定 |', '|---|---|---:|---|']
    group_index={r['group']:r for r in a['selected_new_groups']}
    for g in ['G180','G124','G155','G051','G201','G130','G234','G235']:
        r=group_index[g]; lines.append(f"| {g} | {'、'.join(r['codes'])} | {r['tasks']} | {'；'.join(r['holds']) or ('已有困难细节评论，采用待确认' if g=='G201' else '本轮采用待确认')} |")
    lines += ['', '需要你判断的是本轮是否采用、按哪种研究用途标记，而不是强迫把困难图变成正确/错误二分。G051原话“22,19,12有点难标”；G124“有可能算oos”；G180“疑似oos”；G155已明确六图同房，待的是跨子组比较范围。G201强调两个凸起墙难标/被忽略；G235强调墙体小拐角被忽略，二者正有局部表达差异的研究价值。', '',
        '数据人工处理其次：本地先排查来源/修订后，仅将仍未决的W006/uNb-87/7111（9点）、W031/uNb-59/6925（13点）、W034/e9-26/7273（7点）交你确认多点、漏点或保留。45条父记录和10条历史重叠先由本地查证，不要求你逐条机械审批。', '',
        '分簇审核另开优先队列：延续16图里尚暂缓的8项、uNb-21其他成员对应、近似却拆开及代表半径下较远却合并的案例；已确认W006/W013映射不重问。方法稳定后扩展到全部历史图片，当前不混入无告警对照来增加审核负担。', '',
        '## 验证与复算', '',
        '运行：`python -X utf8 -B tools/thesis_main/analysis/audit_collection_plan_20260921.py`。检查原始身份、覆盖集合、人数守恒、已知人员重复接触、1052配额及十月数量；失败即停止写出本审计。审计只解释候选计划，不生成正式资格或时间结论。', '',
        '相关pytest：`tests/test_audit_collection_plan_20260921.py`与`tests/test_collection_plan_20260921.py`，5项通过。原分配测试有一个同名函数重复定义，实际仍是4项唯一测试；这些测试不能代替视觉和研究有效性验收。', '',
        '输入：v1/v3计划快照、20260912同房关联表、current/inputs/responses.jsonl.gz、原480份required_assignments、historical_exposure以及v1记录的三份export_label原始导出。逐组/图对、逐人、十月名单差异及异常完整见同目录核算明细.json。', '',
        '本审计为支撑工件，未修改原始数据、旧计划或正式协议。地图与README已检查；沿用现有采集计划入口，不新增正式方法入口。']
    (OUT/'审查与待审核事项.md').write_text('\n'.join(lines)+'\n',encoding='utf8')


if __name__ == '__main__':
    main()
