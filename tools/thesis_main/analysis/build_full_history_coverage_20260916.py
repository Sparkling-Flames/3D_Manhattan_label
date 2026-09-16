"""全历史、匿名新人安排及覆盖审计；仅研究准备，不创建LS任务。"""
import gzip
import json
from itertools import combinations
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import maximum_flow

from tools.thesis_main.analysis.build_stage1_image_packages_20260913 import exposure, VIEW, chinese_names

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'analysis_results/full_history_coverage_20260916'
CN=[1,2,6,8,10,12,13,15,17]


def read(path):
    return json.loads((ROOT/path).read_text(encoding='utf-8-sig'))


def main():
    OUT.mkdir(exist_ok=True)
    selection=read('analysis_results/candidate_selection_review_20260913_v2/选用复核机器表.json')
    assert selection['source_user']==read('analysis_results/candidate_selection_review_20260913_v2/用户审查原始记录.json')
    package=read('analysis_results/stage1_person_image_packages_20260913_v2/分配建议与核验.json')
    registry=read('analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json')
    spatial={r['image_id']:r for r in read('analysis_results/spatial_dimensions_review_20260913_v2/空间描述与历轮人工记录.json')['images']}
    with gzip.open(VIEW,'rt',encoding='utf-8') as f:records=[json.loads(l) for l in f]
    seen,pairs,sources=exposure(records)
    manual=defaultdict(set);semi=defaultdict(set);planned=defaultdict(set)
    for r in records:
        w=int(r['worker_id']);iid=r['image_id']
        if w in {19,26}:continue
        if r['unassisted_manual_included']:manual[iid].add(w)
        if r['assistance_exposure']=='model_preannotation':semi[iid].add(w)
    for r in package['assignments']:planned[r['image_id']].add(r['worker_id'])
    adopted={r['image_id']:r for r in selection['images'] if r['status']=='确定采用'}
    selection_all={r['image_id']:r for r in selection['images']}
    groups={g['review_code']:g for g in registry['groups']}
    all_images=[]
    for im in registry['images']:
        iid=im['image_id'];s=spatial[iid];a=adopted.get(iid);original=selection_all.get(iid)
        h=len(manual[iid]);target=a['planned_manual'] if a else h
        all_images.append(dict(image_id=iid,code=f'{im["building"]}-{im["number"]:02d}',building=im['building'],
            room=a['group'] if a else '',supported_rooms=[g for g in im['group_codes'] if groups[g]['raw_current'].get('physical_same')=='支持'],
            scene=a['scene'] if a else (s['current_coarse_review']['value'] or '主空间待定'),
            original_decision=original['effective_user_record'] if original else None,
            adopted=bool(a),history_manual=h,history_semi=len(semi[iid]),planned=len(planned[iid]),
            target=target,gap=max(0,target-h-len(planned[iid])) if a else 0,
            oos=s['oos_review']['status'],difficulty=a['difficulty'] if a else '未定',
            image_path=im['path'],core=False,priority='',reason='',review='已采用' if a else '未作本次采用确认'))
    lookup={r['image_id']:r for r in all_images}; assert len(lookup)==648
    # 原决定排除的图不因高人数自动进入共同池；无OOS记录也不冒充新裁定。
    allowed={'未见人工OOS记录','人工明确非OOS'}
    eligible=[r for r in all_images if r['history_manual']>=19 and r['gap']==0 and r['oos'] in allowed
              and (r['original_decision'] is None or r['adopted'])]
    used_rooms=set();used_buildings=Counter();used_scenes=Counter();core=[]
    def rank(r):
        room=r['room'] or next(iter(r['supported_rooms']),r['image_id'])
        return (room in used_rooms, not r['adopted'], used_scenes[r['scene']],used_buildings[r['building']],
                not bool(r['supported_rooms']),-len(manual[r['image_id']]&set(CN)),r['code'])
    for _ in range(22):
        r=min([r for r in eligible if r not in core],key=rank);core.append(r)
        used_rooms.add(r['room'] or next(iter(r['supported_rooms']),r['image_id']))
        used_buildings[r['building']]+=1;used_scenes[r['scene']]+=1
        r.update(core=True,priority='共同历史',reason='高人数历史连接新旧人员；优先未覆盖房间、已采用组及场景覆盖',
                 review='已采用；本次增加新人历史连接' if r['adopted'] else '共同历史拟选，待逐图复核')
    pending=[r for r in all_images if r['gap']]
    room_need=Counter();room_views=Counter();room_high=Counter()
    for r in all_images:
        if r['adopted']:
            room_need[r['room']]+=r['gap'];room_views[r['room']]+=1;room_high[r['room']]+=r['history_manual']>=19
    pending.sort(key=lambda r:(room_need[r['room']],not room_high[r['room']],-room_views[r['room']],r['room'],r['code']))
    room_order=list(dict.fromkeys(r['room'] for r in pending))
    for r in pending:
        r['priority']=f'补缺{room_order.index(r["room"])+1:02d}'
        r['reason']=f'整房尚缺{room_need[r["room"]]}份；采用视角{room_views[r["room"]]}张；高人数历史{room_high[r["room"]]}张'
    # 15个位置只是工作表列，不使用虚构worker_id。
    slots=[dict(slot=f'新人安排{i:02d}',worker_id=None,name='',kind='new') for i in range(1,16)]
    names=chinese_names()
    slots += [dict(slot=f'W{w:03d}',worker_id=w,name=names.get(w,''),kind='existing') for w in CN]
    offset=1+len(pending);sink=offset+len(slots);rr=[];cc=[];vv=[]
    def edge(a,b,c):rr.append(a);cc.append(b);vv.append(c)
    for i,r in enumerate(pending,1):
        edge(0,i,r['gap'])
        for j,s in enumerate(slots):
            if s['kind']=='new' or s['worker_id'] not in seen[r['image_id']]|planned[r['image_id']]:edge(i,offset+j,1)
    # 旧中文先承担20张；new每人最多28张，另22张共同历史。
    for j in list(range(15,24))+list(range(15)):edge(offset+j,sink,20 if j>=15 else 28)
    graph=coo_matrix((np.array(vv,dtype=np.int64),(rr,cc)),shape=(sink+1,sink+1)).tocsr()
    flow=maximum_flow(graph,0,sink)
    assert flow.flow_value==sum(r['gap'] for r in pending)==592
    assignments=[]
    def add(s,r,purpose):
        assignments.append(dict(slot=s['slot'],worker_id=s['worker_id'],name=s['name'],kind=s['kind'],image_id=r['image_id'],
            code=r['code'],room=r['room'] or '/'.join(r['supported_rooms']),scene=r['scene'],purpose=purpose,
            priority=r['priority'],review=r['review'],condition='Manual',status='拟新增，未派发'))
    for s in slots[:15]:
        for r in core:add(s,r,'连接新旧人员；画像；按房间交叉检验')
    for i,r in enumerate(pending,1):
        for j,s in enumerate(slots):
            if flow.flow[i,offset+j]>0:add(s,r,'补缺；同房及跨房间检验；画像')
    counts=Counter(r['slot'] for r in assignments)
    assert len({(r['slot'],r['image_id']) for r in assignments})==len(assignments)
    assert all(r['worker_id'] is None for r in assignments if r['kind']=='new')
    for r in assignments:
        if r['kind']=='existing':assert r['worker_id'] not in seen[r['image_id']]|planned[r['image_id']]
    for s in slots:
        rows=sorted((r for r in assignments if r['slot']==s['slot']),key=lambda r:(r['room'],r['code']))
        buckets=defaultdict(list)
        for r in rows:buckets[r['room'] or lookup[r['image_id']]['building']].append(r)
        ordered=[]
        while any(buckets.values()):
            for group in buckets.values():
                if group:ordered.append(group.pop(0))
        for i,r in enumerate(ordered,1):r.update(order=i,phase='先做' if i<=30 or s['kind']=='existing' else '后续')
    assert all(counts[s['slot']]<=50 for s in slots[:15]) and all(counts[s['slot']]<=20 for s in slots[15:])
    proposed=defaultdict(set)
    for r in assignments:proposed[r['image_id']].add(r['slot'])
    people=[]
    time=read('analysis_results/worker_sample_budget_20260916/核算数据.json')
    for s in slots:
        rows=[r for r in assignments if r['slot']==s['slot']]
        b={lookup[r['image_id']]['building'] for r in rows};sc={r['scene'] for r in rows}
        per_min=time['timing_summary']['manual_excluding_W019_W026' if s['kind']=='new' else 'current_chinese_manual']['mean_minutes']
        people.append(dict(**s,images=len(rows),common_images=sum(lookup[r['image_id']]['core'] for r in rows),
            buildings=len(b),scenes=len(sc),history_manual_images=sum(s['worker_id'] in v for v in manual.values()) if s['kind']=='existing' else 0,
            estimated_hours=len(rows)*per_min/60))
    for r in all_images:
        iid=r['image_id'];r['new_proposed']=len(proposed[iid]);r['expected']=r['history_manual']+r['planned']+r['new_proposed']
        r['remaining_if_required_complete']=max(0,r['target']-r['expected'])
        r['remaining_without_crediting_required']=max(0,r['target']-r['history_manual']-r['new_proposed'])
    assert all(r['remaining_if_required_complete']==0 for r in all_images if r['adopted'])
    # 全历史完整宽表；保留排除人员原提交身份，不计入主计数。
    historical_workers=sorted({int(r['worker_id']) for r in records})
    matrix=[]
    for r in all_images:
        iid=r['image_id'];row={'图片':r['code'],'房间':r['room'] or '/'.join(r['supported_rooms']),'场景':r['scene']}
        for w in historical_workers:
            states=[]
            if w in manual[iid]:states.append('历史手工')
            if w in semi[iid]:states.append('历史Semi')
            if w in seen[iid] and not states:states.append('历史接触/未计入')
            if w in planned[iid]:states.append('原必做待核实')
            if f'W{w:03d}' in proposed[iid]:states.append('拟新增')
            row[f'W{w:03d}']=','.join(states)
        for s in slots[:15]:row[s['slot']]='拟新增' if s['slot'] in proposed[iid] else ''
        matrix.append(row)
    rooms=[];room_pairs=[]
    for g in sorted({r['room'] for r in all_images if r['adopted']}):
        rows=[r for r in all_images if r['room']==g];usable=[r for r in rows if r['expected']>0]
        members=[set(f'W{w:03d}' for w in manual[r['image_id']]|planned[r['image_id']])|proposed[r['image_id']] for r in usable]
        rooms.append(dict(room=g,images=len(rows),expected_manual_images=len(usable),history_high=sum(r['history_manual']>=19 for r in rows),
            new_proposed=sum(r['new_proposed'] for r in rows),common_people_all_views=len(set.intersection(*members)) if members else 0,
            codes=[r['code'] for r in usable],note='共同人数为全视角交集；0不表示任意两图均无共同人；未计算人员类型'))
        for (i,a),(j,b) in combinations(enumerate(usable),2):
            room_pairs.append(dict(room=g,left=a['code'],right=b['code'],common_people=len(members[i]&members[j]),
                common_newcomers=len({x for x in members[i]&members[j] if x.startswith('新人安排')}),
                note='非独立样本对；允许构成不同的预测，固定人员比较仅使用实际交集'))
    scenes=[]
    for scene in sorted({r['scene'] for r in all_images}):
        rows=[r for r in all_images if r['scene']==scene and r['expected']>0]
        scenes.append(dict(scene=scene,history_images=sum(r['history_manual']>0 for r in all_images if r['scene']==scene),
            expected_images=len(rows),expected_ge8=sum(r['expected']>=8 for r in rows),buildings=len({r['building'] for r in rows}),
            adopted_rooms=len({r['room'] for r in rows if r['adopted']}),note='全历史场景工作分类；待定不自动归类，房间关系不完备者未计独立房间'))
    full_rooms=[]
    for c in registry['candidates']:
        if not c['physical_same_supported']:continue
        rows=[lookup[i] for i in c['image_ids']]
        if sum(r['expected']>0 for r in rows)<2:continue
        full_rooms.append(dict(group=c['candidate_id'],codes=[r['code'] for r in rows],
            history_counts=[r['history_manual'] for r in rows],expected_counts=[r['expected'] for r in rows],
            history_views=sum(r['history_manual']>0 for r in rows),expected_views=sum(r['expected']>0 for r in rows),
            expected_ge8=sum(r['expected']>=8 for r in rows),comparable=c['comparable_for_prediction'],
            holds=c['selection_hold_reasons'],note='同房候选子集可能重叠；不直接计为独立房间或已验证预测样本'))
    reserves=read('analysis_results/unassigned_room_inventory_20260915/池外同房补标候选.json')
    scene_n={s['scene']:s['buildings'] for s in scenes}
    def reserve_rank(r):
        known=[s for s in r['scene_counts'] if s not in {'null','主空间待定','无法判断'}]
        return (not bool(known),min((scene_n.get(s,0) for s in known),default=999),not bool(r['one_two_targets']),-r['room_views'],r['candidate'])
    reserves.sort(key=reserve_rank)
    backup=[dict(rank=i+1,group=r['candidate'],codes=r['codes'],scene=r['scene_counts'],history=r['manual_counts'],
        reason='按全历史场景已有楼数优先补覆盖较少类型，再看1—2人历史和视角数；楼数不替代独立房间数',status='待复核，未分配') for i,r in enumerate(reserves)]
    high_backup=read('analysis_results/unassigned_room_inventory_20260915/高人数历史与池外视角待核对.json')
    stats=dict(total_registry=648,history_images=sum(r['history_manual']>0 for r in all_images),historical_workers=len(historical_workers),
        history_pairs=sum(len(v) for v in manual.values()),core_images=len(core),core_review_needed=sum(not r['adopted'] for r in core),
        proposed_pairs=len(assignments),proposed_images=sum(bool(v) for v in proposed.values()),new_pairs=sum(r['kind']=='new' for r in assignments),
        existing_pairs=sum(r['kind']=='existing' for r in assignments),expected_manual_images=sum(r['expected']>0 for r in all_images),
        expected_ge8=sum(r['expected']>=8 for r in all_images),expected_pairs=sum(r['expected'] for r in all_images),
        total_estimated_hours=sum(r['estimated_hours'] for r in people),new_worker_id_blank=True,
        limits='规划以480份原必做有效完成为条件；共同历史待复核项未派发，50为上限，剩余容量不强凑；无新增收敛判定')
    data=dict(status='具体研究准备方案_未导入未派发_新人ID空白',stats=stats,people=people,images=all_images,
        assignments=assignments,matrix=matrix,rooms=rooms,room_pairs=room_pairs,full_history_rooms=full_rooms,
        scenes=scenes,backup=backup,high_history_backup=high_backup,raw_sources=sources,
        inputs=dict(registry=str(registry.get('schema','')),calculation_view=str(VIEW),
            selection='candidate_selection_review_20260913_v2/选用复核机器表.json',required='stage1_person_image_packages_20260913_v2/分配建议与核验.json'),
        user_decisions=dict(new_worker_id=None,low_n='真实低人数观察结论＋15人以上待验证预测',priority='补齐预测、已有高人数历史、按研究用途安排'))
    (OUT/'全历史覆盖机器表.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    report=['# 全历史图片与人员覆盖准备方案','',
        '独立复核结论及使用限制见[审查记录](../../docs/thesis_main/全历史覆盖方案独立复核_20260916.md)；本生成说明不替代人工采用复核和派发前检查。',
        f'覆盖全部648张分类图片、{stats["history_images"]}张可纳入手工历史图、{stats["history_pairs"]}份手工历史；26人历史身份保留，W019/W026不计主数量。',
        f'具体拟安排{stats["proposed_pairs"]}份，涉及{stats["proposed_images"]}张图片：新人{stats["new_pairs"]}份、旧中文{stats["existing_pairs"]}份。新人实际ID全部为空，“新人安排01—15”仅为安排位置。',
        f'共同历史图22张，其中{stats["core_review_needed"]}张尚需本次复核。其余592份用于已采用图片补缺。共同历史选择优先不同房间及已采用组，再平衡场景/building及旧中文连接；未按收敛结果筛选。',
        '原480份必做未当成完成事实，本方案是它们全有效完成后的接续安排。表内另列不计原必做时的剩余缺口；W035完成H仅为用户陈述，未将未核验几何结果预扣。',
        f'方案全有效完成后，预计手工库存{stats["expected_manual_images"]}张，其中{stats["expected_ge8"]}张至少8人；共{stats["expected_pairs"]}人图。8仅为库存档位，非收敛门槛。未定场景和OOS记录保留，不将库存数当作可验证预测数。',
        f'历史均值估算总操作约{stats["total_estimated_hours"]:.1f}人时，不含培训、练习、休息和返工。',
        '', '## 四种用途如何落实','',
        '补缺：每张已采用图都核查原目标；保留仅历史的Semi图，不强行转成Manual。连接：22张共同历史图由15名新人独立完成，连接同图旧人员。画像：共同图与扩展图联合使用，并保留不同房间/场景覆盖。检验：按房间交叉划分，目标房间的作答不用于给人员分类；同房预测则用该房间其他视角作依据，另列人员熟悉效应。',
        '覆盖表按全视角共同人员交集报告；旧历史与不同新增视角并非人人都重叠。不能据19组/100图直接承诺每种AABC组合均可抽取。各类需要在同一目标图确有足够不同真人，类型确定后再核查。',
        '', '## 9月观察与10月验证','',
        '实际低人数有效共识可记录观察内收敛，另登记15人以上继续稳定的预测；人数不补造。尚未读取新结果，本轮不预填任何图已收敛。10月对已共识图也按场景/房间/实际人数分层抽查，同时覆盖出现分歧图；先冻结预测与抽查规则，再看新增结果。新人构成变化单列，稳定多簇与合理单人标法保留。',
        '', '## 复核与使用','',
        '工作簿“拟选图片”是本次具体名单；“全历史同房候选”覆盖采用组以外的有数据同房子集，可能重叠，不能直接相加为独立房间数。“备用候选”和“高人数补视角待核对”均未进入分配，后者保留OOS与可比性待核对记录。池外历史共同图保留待复核。全历史矩阵中的缺失不作零质量。真实人员ID未绑定前，不能直接导入或派发；无新项目编号、无ZIP。',
        '机器表保留原采用文字、图片路径、人员安排位置、历史来源及检查数字。通过人图唯一性、旧人员接触排除、新人ID空白、个人上限、补缺总量及全库存去重检查。']
    (OUT/'执行说明.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8')
    print(json.dumps(stats,ensure_ascii=False));print(json.dumps(people,ensure_ascii=False))


if __name__=='__main__':main()
