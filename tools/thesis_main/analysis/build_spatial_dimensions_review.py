"""接续空间视觉记录与历轮人工源；新描述不覆盖人工字段或正式资格。"""
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT/'analysis_results/scene_image_exploration_20260910_v1'
OUT = ROOT/'analysis_results/spatial_dimensions_review_20260913_v2'
RELATIONS = {'无明显建筑分隔','局部分隔或宽开口','明确墙体与门洞分隔','其他明确分隔','无法判断'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def indexed(rows, key='image_id'):
    result = {r[key]:r for r in rows}
    if len(result)!=len(rows):
        raise ValueError('重复身份: '+key)
    return result


def merge_dimensions(images, proposals):
    old, new = indexed(images), indexed(proposals)
    if set(old)!=set(new):
        raise ValueError('空间续审覆盖不完整')
    required = {'functional_regions','main_space','relations','relation_scope_note','reason','review_basis',
                'evidence_refs','needs_original_followup','human_comparison','human_conflicts','uncertainties'}
    result=[]
    for iid, image in old.items():
        p=new[iid]
        if not required<=p.keys() or p['review_basis'] not in {'carried_visual_record','new_original'}:
            raise ValueError('续审字段缺失或查看方式未知: '+iid)
        if not isinstance(p['functional_regions'],list) or not isinstance(p['human_conflicts'],list):
            raise ValueError('续审字段类型错误: '+iid)
        for rel in p['relations']:
            if not {'region_a','region_b','relation','evidence'}<=rel.keys() or rel['relation'] not in RELATIONS:
                raise ValueError('关系字段错误: '+iid)
        result.append(dict(image,new_spatial_review=p,adopted_classification_changed=False))
    return result


def attach_oos(rows, events):
    ids={r['image_id'] for r in rows}
    for e in events:
        if not set(e['image_ids']+e['context_image_ids'])<=ids:
            raise ValueError('OOS图像身份不匹配')
    for row in rows:
        iid=row['image_id']
        applied=[e for e in events if iid in e['image_ids']]
        context=[e for e in events if e['state']=='局部待定位' and iid in e['context_image_ids'] and iid not in e['image_ids']]
        states={e['state'] for e in applied}
        if '明确OOS' in states and '明确非OOS' in states:
            status='历轮相反意见待核实'
        elif '明确OOS' in states:
            status='人工曾明确OOS'+('；另有疑似意见' if states & {'疑似','存在争议'} else '')
        elif states & {'疑似','存在争议'}:
            status='人工疑似或争议'
        elif '明确非OOS' in states:
            status='人工明确非OOS'
        elif context:
            status='组内局部OOS待定位'
        else:
            status='未见人工OOS记录'
        row['oos_review']=dict(status=status,image_event_ids=[e['event_id'] for e in applied],
            context_event_ids=[e['event_id'] for e in context],formal_eligibility_changed=False,
            note='记录人工主张及作用范围；无记录不等于in-scope，组级判断不冒充逐图独立确认。')


def apply_chat_review(rows, events, review):
    """对话确认作为新增层；保留旧分类、AI争议和OOS原文。"""
    by_id=indexed(rows)
    for decision in review['decisions']:
        row=by_id[decision['image_id']]
        row['current_coarse_review']=dict(value=decision['coarse_type'],source=review['source'],
            basis=decision['basis'],human_accepted=True)
        row['resolved_spatial_conflicts']=row['new_spatial_review']['human_conflicts']
        row['new_spatial_review']=dict(row['new_spatial_review'],human_conflicts=[])
    ids=review['oos_image_ids']
    if any(by_id[i]['building']!='wc2JMjhGNzB' for i in ids):
        raise ValueError('对话OOS范围不匹配')
    events.append(dict(event_id='chat:20260913:wc-suspected',text=review['oos_quote'],
        state='疑似',image_ids=ids,context_image_ids=ids,scope='本次讨论的09、35、64；非整楼',
        source=review['source'],interpretation='最新人工意见为疑似；历史明确OOS原文仍保留，未确认空间类别。'))
    for row in rows:
        row.setdefault('current_coarse_review',dict(value=row['spatial_classification']['coarse_type'],
            source='既有采用分类（历史开放复合值待按分维度表达）',human_accepted=None))
    attach_oos(rows,events)
    for iid in ids:
        by_id[iid]['oos_review']['latest_explicit_opinion']='疑似'
        by_id[iid]['oos_review']['latest_source']=review['source']


def oos_events(initial, later, pairs, groups, group_codes, batch, selection, images):
    """逐条人工读过的OOS解释；新增未知原文必须重新解释，不做关键词裁决。"""
    events=[]
    early={('UwV83HsGsw3',3):'明确OOS',('X7HyMhZNoso',1):'明确OOS',
           ('pRbA3pwrgk9',1):'明确OOS',('pRbA3pwrgk9',3):'疑似',
           ('pRbA3pwrgk9',16):'明确OOS',('pa4otMbVnkk',8):'疑似'}
    group_states={'G014':'明确OOS','G044':'明确OOS','G049':'疑似','G098':'存在争议',
        'G114':'局部待定位','G124':'疑似','G136':'疑似','G142':'疑似','G180':'疑似',
        'G187':'明确OOS','G196':'疑似','G211':'明确OOS','G212':'明确OOS','G246':'明确OOS'}
    has=lambda s: bool(re.search(r'oos|范围外|非曼哈顿|超出',s,re.I))
    def add(eid,text,state,ids,scope,source,context=None,note=''):
        events.append(dict(event_id=eid,text=text,state=state,image_ids=ids,
            context_image_ids=ids if context is None else context,scope=scope,source=source,interpretation=note))
    for r in initial['rows']:
        if has(r['user_note']):raise ValueError('新增初始OOS原文需解释')
    for r in later['source_user']['rows']:
        if not has(r['user_note']):continue
        im=images[r['image_id']]; key=(im['building'],im['number'])
        if key not in early:raise ValueError('新增早期OOS原文需解释')
        add('dispute:'+r['image_id'],r['user_note'],early[key],[r['image_id']],'image',
            'user_review_20260912_v3.json#/source_user/rows')
    for r in later['rows']:
        note=r['user_revision'].get('note','')
        if not has(note):continue
        im=images[r['image_id']]
        if not (im['building']=='q9vSo1VnCiC' and im['number']==18):raise ValueError('新增后续OOS原文需解释')
        add('later:'+r['image_id'],note,'疑似',[r['image_id']],'image','user_review_20260912_v3.json#/rows/user_revision')
    for p in pairs['pairs']:
        if has(p['user_revision'].get('note','')):raise ValueError('配对OOS原文需解释')
    for g in groups['group_reviews']:
        note=g['current'].get('note','');code=group_codes[g['group_id']]
        if not has(note):continue
        if code not in group_states:raise ValueError('新增整组OOS原文需解释')
        ids=g['image_ids'];state=group_states[code];scope='group';explanation='保留组级原文；不是每张图独立填写。'
        if code=='G114':
            ids=[];scope='unresolved_local_region';explanation='书桌处的具体图片未定位，不将本组4图直接判为OOS。'
        elif code=='G196':
            ids=[i for i in ids if images[i]['number']==42];scope='image_subset';explanation='仅42疑似OOS；61与82只是同房关系，不能传递OOS。'
        elif code=='G014':explanation='本组4图明确OOS；提及13组在二层不等于13组也被判OOS。'
        add('group:'+code,note,state,ids,scope,'user_group_review_20260912.json#/group_reviews',g['image_ids'],explanation)
    for b in batch['rows']:
        if not has(b['source_comment']):continue
        if b['case_id']!='B04':raise ValueError('新增讨论OOS原文需解释')
        add('discussion:B04',b['source_comment'],'明确OOS',[r['image_id'] for r in b['images']],
            'image','batch_user_decisions_20260911_v1.json#/rows')
    for r in selection['decisions']:
        if has(r.get('note','')):raise ValueError('新增逐图选用OOS原文需解释')
    for g in selection['groups']:
        if not has(g.get('note','')):continue
        state={'G014':'明确OOS','G015':'明确非OOS'}.get(g['group'])
        if state is None:raise ValueError('新增选用组OOS原文需解释')
        ids=[r['image_id'] for r in selection['decisions'] if r['group']==g['group']]
        add('selection:'+g['group'],g['note'],state,ids,'selection_group',
            'candidate_selection_review_20260913_v1/用户审查原始记录.json#/groups')
    return events


def build():
    registry=read(BASE/'same_room_selection_registry_v2_20260912.json')
    initial=read(BASE/'user_visual_audit.json')['source_user']
    later=read(BASE/'user_review_20260912_v3.json')
    pairs=read(BASE/'user_pair_review_resume_v1.json')
    groups=read(BASE/'user_group_review_20260912.json')
    batch=read(BASE/'batch_user_decisions_20260911_v1.json')
    doorway=read(BASE/'门洞人工与AI历轮核对_20260913.json')
    selection=read(ROOT/'analysis_results/candidate_selection_review_20260913_v1/用户审查原始记录.json')
    if not (later==pairs['source_user']==groups['source_user'] and pairs['pairs']==groups['pairs']):
        raise ValueError('人工导出嵌套链不一致，需核实，禁止静默选取新版')
    originals=indexed(initial['rows']);post=indexed(later['source_user']['rows']);latest=indexed(later['rows'])
    old=indexed(registry['images']);doors=indexed(doorway['rows'])
    if any(set(d)!=set(old) for d in (originals,post,latest,doors)):raise ValueError('历轮648图覆盖不一致')
    for iid,r in old.items():
        stages={e['stage']:e for e in r['review_history'] if e['stage'] in {'initial_648','user_dispute_review'}}
        if stages['initial_648']['values']!=originals[iid] or stages['user_dispute_review']['values']!=post[iid]:
            raise ValueError('旧机器表与人工原始记录不一致')
    proposals=[r for name in 'abc' for r in read(OUT/f'dimensions_{name}.json')['rows']]
    patches=indexed(read(OUT/'dimensions_c_patch_b.json')['rows'])
    if not set(patches)<=set(old):raise ValueError('补核图像身份未知')
    carried=indexed(proposals)
    proposals=[patches.get(r['image_id'],r) for r in proposals]
    rows=merge_dimensions(registry['images'],proposals)
    checks=indexed(read(OUT/'root_crosschecks.json')['rows'])
    group_codes={r['group_id']:r['review_code'] for r in registry['groups']}
    group_raw={group_codes[r['group_id']]:r for r in groups['group_reviews']}
    pair_raw={r['pair_id']:r for r in pairs['pairs'] if r['user_revision']}
    decisions=indexed(selection['decisions'])
    selection_groups=indexed(selection['groups'],'group')
    for r in rows:
        iid=r['image_id'];lr=latest[iid]
        r['before_targeted_followup']=carried[iid] if iid in patches else None
        r['root_crosscheck']=checks.get(iid)
        r['human_spatial_rounds']=dict(initial_648=originals[iid],early_dispute=post[iid],
            later_spatial={k:lr[k] for k in ('prefill','current_classification','user_revision','changed_fields')},
            later_personally_reviewed=r['in_previous_disagreement_filter'])
        r['pair_user_review_refs']=[pid for pid,p in pair_raw.items() if iid in p['image_ids']]
        r['group_user_review_refs']=[code for code,g in group_raw.items() if iid in g['image_ids']]
        r['latest_selection_record']=decisions.get(iid)
        r['latest_selection_group']=selection_groups[decisions[iid]['group']] if iid in decisions else None
        r['preserved_doorway_record']=doors[iid]
    events=oos_events(initial,later,pairs,groups,group_codes,batch,selection,old)
    chat_review=read(OUT/'对话确认_粗类与OOS.json')
    apply_chat_review(rows,events,chat_review)
    rounds=[dict(stage='首次648图分类',date=initial['saved_at'],records=len(originals),scope='用户声明全量亲审'),
        dict(stage='早期争议复核',date=later['source_user']['saved_at'],records=len(post),
             changed_records=sum(originals[i]!=post[i] for i in old),scope='完整导出；74行有变化不等于74张全部重新亲审'),
        dict(stage='后续空间复核',date=later['saved_at'],records=len(latest),
             personally_reviewed=sum(r['in_previous_disagreement_filter'] for r in rows),
             revised_records=sum(bool(r['user_revision']) for r in latest.values()),scope='仅该轮意见不一致筛选；预填与人工作答分别保留'),
        dict(stage='配对复核',date=pairs['saved_at'],records=len(pairs['pairs']),revised_records=len(pair_raw),scope='3条填写；其余配对不冒充人工确认'),
        dict(stage='整组复核',date=groups['saved_at'],records=len(group_raw),
             revised_records=sum(bool(g['user_revision']) for g in group_raw.values()),scope='用户声明260组全部看完；状态空白不倒推漏审'),
        dict(stage='最新选图复核',date=selection['created_at'],records=len(decisions),group_records=len(selection['groups']),scope='保留选用/人数/难度/备注，非空间类型自动改写')]
    summary=dict(images=len(rows),human_rounds=rounds,
        new_review_basis=dict(Counter(r['new_spatial_review']['review_basis'] for r in rows)),
        human_conflict_images=sum(bool(r['new_spatial_review']['human_conflicts']) for r in rows),
        uncertainty_images=sum(bool(r['new_spatial_review']['uncertainties']) for r in rows),
        original_followup_images=sum(r['new_spatial_review']['needs_original_followup'] for r in rows),
        oos_events=len(events),oos_status_counts=dict(Counter(r['oos_review']['status'] for r in rows)))
    data=dict(schema='spatial_dimensions_human_history_v2',summary=summary,
        source_files=[str(p.relative_to(ROOT)).replace('\\','/') for p in [
            BASE/'user_visual_audit.json',BASE/'user_review_20260912_v3.json',BASE/'user_pair_review_resume_v1.json',
            BASE/'user_group_review_20260912.json',BASE/'batch_user_decisions_20260911_v1.json',
            BASE/'same_room_selection_registry_v2_20260912.json',BASE/'门洞人工与AI历轮核对_20260913.json',
            ROOT/'analysis_results/candidate_selection_review_20260913_v1/用户审查原始记录.json']],
        human_pair_reviews=pair_raw,human_group_reviews=group_raw,latest_selection_groups=selection['groups'],
        batch_discussion=batch,latest_chat_review=chat_review,oos_events=events,images=rows,
        integrity=dict(raw_source_chain_equal=True,registry_early_records_equal=True,
            human_fields_overwritten=False,room_groups_changed=False,eligibility_changed=False,
            old_open_counts_are_legacy_only=True))
    return data


def main():
    data=build()
    (OUT/'空间描述与历轮人工记录.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    render(data)
    print(json.dumps(data['summary'],ensure_ascii=False))


def render(data):
    # 页面只携带阅读/填写所需字段；完整原始关联在机器表中保留。
    view=[]
    for r in data['images']:
        iid=r['image_id'];p=r['new_spatial_review']
        view.append(dict(image_id=iid,building=r['building'],number=r['number'],path=r['path'],groups=r['group_codes'],
            ai=p,adopted=r['spatial_classification'],field_sources=r['spatial_field_sources'],
            history=r['human_spatial_rounds'],discussions=r['prior_discussion'],comments=r['all_user_notes'],
            pair_reviews=[data['human_pair_reviews'][x] for x in r['pair_user_review_refs']],
            group_reviews=[dict(code=x,**data['human_group_reviews'][x]) for x in r['group_user_review_refs']],
            selection=dict(image=r['latest_selection_record'],group=r['latest_selection_group']),doorway=r['preserved_doorway_record'],
            root_crosscheck=r['root_crosscheck'],
            coarse=r['current_coarse_review'],resolved_conflicts=r.get('resolved_spatial_conflicts',[]),
            oos=r['oos_review'],oos_events=[e for e in data['oos_events'] if e['event_id'] in r['oos_review']['image_event_ids']+r['oos_review']['context_event_ids']]))
    template=Path(__file__).with_name('spatial_dimensions_review.html').read_text(encoding='utf-8')
    payload=json.dumps(view,ensure_ascii=False).replace('<','\\u003c')
    (OUT/'空间关系续审.html').write_text(template.replace('/*__DATA__*/',payload),encoding='utf-8')
    s=data['summary'];lines=['# 空间描述续审与历轮来源核对','',
        '本轮采用功能区域、主要呈现空间、逐对分隔关系；门洞/交界位置与OOS独立保存。不再以“开放复合空间”作为互斥粗类，旧47/14及57张队列只作历史记录，不是新版分类统计或真实人工冲突数。','',
        '[查看与填写](空间关系续审.html) · [完整机器表](空间描述与历轮人工记录.json) · [统一规则](复核规则.md)','',
        '| 人工记录阶段 | 导出记录数 | 范围说明 |','|---|---:|---|']
    for r in s['human_rounds']:lines.append(f'| {r["stage"]} | {r["records"]} | {r["scope"]} |')
    lines+=['',f'续审648图：{s["new_review_basis"]}。这是接续旧视觉记录的方式统计，不宣称重新全量看图。人工事实疑点{s["human_conflict_images"]}图；结构/用途不确定性{s["uncertainty_images"]}图；仍需补原图{s["original_followup_images"]}图。','',
        '初始与争议轮648条原文已逐条与旧机器表核对一致；后续空间导出与配对/整组导出的嵌套源完全相同，3条配对填写也在后续快照中完整存在。本表保留这些原始字段、各轮AI预填/人工作答/合成值、逐组讨论、260组原始填写及最新112图/22组选图记录。现有原始快照不修改。','',
        '填写：先筛“需核实”，查看原人工记录及新建议；直接修改功能、主空间或关系，写一条评论即可。蓝色为原AI建议，橙色为改值；状态独立手动选择，不会因编辑而自动变化。保存到浏览器，并用“导出本轮填写”保留JSON。未填写、AI预填、人工确认严格区分。','',
        '## OOS原文与作用范围','',
        '下列仅为人工研究判断台账，不作正式资格裁决；无记录不等于in-scope。组级原文保留组级来源；G114书桌局部待定位，不能把4个成员全部算OOS；G196只将42关联疑似OOS，不传给61/82；G015的明确非OOS也保留。','',
        '| 当前记录状态 | 图数 |','|---|---:|']
    for key,n in s['oos_status_counts'].items():lines.append(f'| {key} | {n} |')
    lines+=['','| 来源条目 | 原文 | 解释／范围 |','|---|---|---|']
    for e in data['oos_events']:lines.append(f'| {e["event_id"]} | {e["text"].replace("|","／")} | {e["state"]}；{e["scope"]}；{e["interpretation"]} |')
    (OUT/'续审说明.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
