"""接收本轮双人排序，保存独立确认层和补查研究输入；原始来源不变。"""
from __future__ import annotations

import copy
import csv
import json
import shutil
from collections import Counter
from pathlib import Path

from .finalize_review_20260928 import read, dump, write_csv
from .receive_order_review_20260928 import validate_return, make_variant
from .build_order_gt_screened_20260928 import ordered_layout
from .build_order_studio_20260926 import ROOT, encode, geometry_variant
from tools.label_studio.panorama_studio.build import data_image

OUT=ROOT/'analysis_results/order_pattern_recall_20260929'
PREVIOUS=ROOT/'analysis_results/order_gt_screened_20260928'
FILES={
    'user':Path('C:/Users/ASUS/Downloads/角点顺序审核(1).json'),
    'yizheng':Path('C:/Users/ASUS/Documents/xwechat_files/wxid_lvoh11i1addo22_a66c/msg/file/2026-09/角点顺序审核 (2)(1).json'),
}
GLASS_ID='8f2f8f8bfdaec3360646'
DOOR_ID='2t7WUuJeko7_53937db036374126830e0f1203b04ead'


def cycle_key(order):
    return min(tuple(v[i:]+v[:i]) for v in (order,order[::-1]) for i in range(len(v)))


def merge_returns(seed, returns):
    merged=copy.deepcopy(seed);origins={};conflicts=[]
    for oid in sorted(set().union(*(set(r) for r in returns.values()))):
        updates=[(who,r[oid]) for who,r in returns.items() if oid in r and r[oid]!=seed.get(oid)]
        if not updates:continue
        decisions=[{k:r[k] for k in ('binding','status','order','note','cause')} for _,r in updates]
        if any(d!=decisions[0] for d in decisions[1:]):conflicts.append(oid);continue
        merged[oid]=copy.deepcopy(max(updates,key=lambda e:e[1]['updated_at'])[1])
        origins[oid]=[who for who,_ in updates]
    return merged,origins,conflicts


def freeze_file(src,dst):
    if dst.exists() and src.read_bytes()!=dst.read_bytes():raise ValueError('evidence_changed:'+str(dst))
    if not dst.exists():shutil.copyfile(src,dst)


def build_viewer(objects,records,inventory,candidate_ids):
    """复用现有几何展示，比较页不接入保存或裁决。"""
    csv.field_size_limit(32*1024*1024)
    with (ROOT/'analysis_results/review_final_20260928/全量复核.csv').open(encoding='utf-8-sig') as f:
        ledger={r['canonical_annotation_id']:r for r in csv.DictReader(f)}
    changed={r['object_id']:r for r in inventory if r['status']=='confirmed' and r['cumulative_change']=='adjacency_changed'}
    examples=['new_95_3649_7457_W030','new_95_3649_7231_W036',GLASS_ID]
    ids=list(dict.fromkeys(list(candidate_ids)+examples+list(changed)))
    registry=read(ROOT/'analysis_results/consensus_research_20260923/inputs/room_registry.json.gz')
    meta={r['image_id']:r for r in registry['images']};images={};cases=[]
    for oid in ids:
        o=objects[oid];iid=o['image_id'];r=records.get(oid);row=next((x for x in inventory if x['object_id']==oid),None)
        initial=row['initial_order'] if row else list(range(len(o['links_zero_based'])))
        pairs=[('本轮审核前',initial)]
        if r and r['status']=='confirmed':pairs.append(('已确认排列',r['order']))
        if row and row['initial_order']==row['confirmed_order'] and row['cumulative_change']=='adjacency_changed':
            pairs.insert(0,('历史源排列',list(range(len(initial)))))
        variants=[]
        for name,order in pairs:
            source=make_variant(o,ledger)['source'];source.update(comparison_order=order,object_id=oid,
                scene_doorway_status=o.get('scene_doorway_status','not_recorded'),scene_oos_status=o.get('scene_oos_status','not_recorded'))
            variants.append(geometry_variant(name,source,o['preprocessed_points'],[o['links_zero_based'][i] for i in order]))
        category='遗漏候选：尚未判错' if oid in candidate_ids else '正确顺序反例／玻璃细节保留' if oid in examples else '真实改序对照'
        cases.append(dict(image_id=iid,title=f"{o['image_code']} · {o.get('worker_id') or o['object_kind']}",category=category,
            annotation_ids=[oid],variants=variants))
        if iid not in images:images[iid]=data_image(ROOT/meta[iid]['path'],texture=True)
    dataset=dict(cases=cases,counts=dict(cases=len(cases),variants=sum(len(c['variants']) for c in cases)),manifest=dict(contract_version='consensus_research_20260923_v1',formal_data_connected=False))
    (OUT/'comparison_data.js').write_text('window.STUDIO_DATA='+encode(dataset)+';const imagePool='+encode(images)+';window.STUDIO_IMAGES=Object.fromEntries(window.STUDIO_DATA.cases.map((c,i)=>[i,{original:imagePool[c.image_id],texture:imagePool[c.image_id]}]));',encoding='utf-8')
    page=(ROOT/'analysis_results/order_studio_20260926/index.html').read_text(encoding='utf-8')
    page=page.replace('<link rel="stylesheet" href="order_studio.css">','').replace('<script defer src="order_studio.js"></script>','')
    for name in ('studio.js','studio.css','three.min.js','OrbitControls.js'):
        page=page.replace('"'+name+'"','"../order_studio_20260926/'+name+'"')
    page=page.replace('"data.js"','"comparison_data.js"').replace('<title>点对拖拽排序</title>','<title>改序规律与遗漏候选对照</title>')
    page=page.replace('</head>','''<style>.order-editor,#card-fit,.order-actions{display:none!important}#compare-grid{display:block}.viewport{height:480px}</style>
<script>document.addEventListener('DOMContentLoaded',()=>{document.querySelector('h1').textContent='改序规律与遗漏候选对照';document.getElementById('panorama-panel').open=true;
const p=document.createElement('p');p.textContent='只读研究对照：来源切换审核前／确认后；曲线异常不等于顺序错误。4对点默认不自动召回。门洞/OOS属性见来源详情。';document.querySelector('.study-heading').after(p);
const id=new URL(location.href).searchParams.get('annotation');if(id){const i=dataset.cases.findIndex(c=>c.annotation_ids.includes(id));if(i>=0)chooseCase(i);}
requestAnimationFrame(()=>{views.forEach(resize);drawPanorama();});});</script></head>''')
    (OUT/'index.html').write_text(page,encoding='utf-8')
    return len(cases)


def build_continuation(objects, records, origins, candidate_ids, out=OUT, queue_name='order_followup_20260929'):
    """独立续审入口；同房导出是当前确认快照，最终全量归档等待续审/配对完成。"""
    def rows(path):
        with path.open(encoding='utf-8-sig') as f:
            return list(csv.DictReader(f))
    old=rows(PREVIOUS/'逐对象筛选.csv')
    prior_queue=[r for r in old if r['state'] in {'pending','confirmed'}]
    coverage=[dict(object_id=r['object_id'],image_code=r['image_code'],previous_state=r['state'],
        current_status=records.get(r['object_id'],{}).get('status','missing'),
        current_reviewers=origins.get(r['object_id'],[])) for r in prior_queue]
    write_csv(out/'上一轮覆盖核对.csv',coverage)
    coverage_counts={state:dict(Counter(r['current_status'] for r in coverage if r['previous_state']==state)) for state in ('pending','confirmed')}
    deferred={r['object_id']:dict(object_id=r['object_id'],image_code=r['image_code'],worker_id=r['worker_id'],
        sources=['previous_pairing_queue'],note=r['note']) for r in rows(PREVIOUS/'配对问题_后续统一处理.csv')}
    for oid,r in records.items():
        if r['status']!='pairing':continue
        o=objects[oid]
        entry=deferred.setdefault(oid,dict(object_id=oid,image_code=o['image_code'],worker_id=o.get('worker_id',''),sources=[],note=''))
        entry['sources'].append('received_pairing_report');entry['note']=r['note'] or entry['note']
    write_csv(out/'配对问题_汇总待后处理.csv',list(deferred.values()))
    registry=read(ROOT/'analysis_results/consensus_research_20260923/inputs/room_registry.json.gz')
    meta={r['image_id']:r for r in registry['images']};room={}
    for group in registry['candidates']:
        if not group['physical_same_supported']:continue
        for iid in group['image_ids']:
            if iid in room and room[iid]!=group['candidate_id']:raise ValueError('ambiguous_room:'+iid)
            room[iid]=group['candidate_id']
    grouped={}
    for oid,record in records.items():
        if record['status']!='confirmed' or objects[oid]['object_kind']=='gt_original':continue
        o=objects[oid];iid=o['image_id'];rid=room.get(iid)
        key=rid or 'unresolved:'+iid
        group=grouped.setdefault(key,dict(room_id=rid,room_status='confirmed_same_room' if rid else 'unresolved',images={}))
        image=group['images'].setdefault(iid,dict(image_id=iid,image_code=o['image_code'],annotations=[]))
        layout=ordered_layout(o,records[oid]['order']);layout.update(worker_id=o.get('worker_id'),reviewers=origins.get(oid,[]))
        image['annotations'].append(layout)
    dump(out/'同房汇集_Matterport_当前确认快照.json',dict(schema='room_grouped_matterport_order_v1',
        complete=False,room_source='analysis_results/consensus_research_20260923/inputs/room_registry.json.gz',
        rooms=list(grouped.values()),remaining_order_candidates=candidate_ids,pairing_deferred=list(deferred),formal_analysis_connected=False))
    if not candidate_ids:
        result=dict(previous_queue_states=coverage_counts,missing=[r['object_id'] for r in coverage if r['current_status']=='missing'],
            previous_pending_without_current_reviewer=[r['object_id'] for r in coverage if r['previous_state']=='pending' and not r['current_reviewers']],
            pairing_deferred=len(deferred),next_round_objects=0,next_round_images=0)
        dump(out/'覆盖与续审汇总.json',result)
        return result
    ledger={r['canonical_annotation_id']:r for r in rows(ROOT/'analysis_results/review_final_20260928/全量复核.csv')}
    selected={};next_out=ROOT/'analysis_results'/queue_name;next_out.mkdir(exist_ok=True)
    for oid in candidate_ids:
        if oid in deferred or records.get(oid,{}).get('status')=='confirmed':raise ValueError('invalid_followup:'+oid)
        o=objects[oid];v=make_variant(o,ledger)
        v['source'].update(image_id=o['image_id'],provenance=o['source'],queue_state='pending',
            default_preview_order=list(range(len(o['links_zero_based']))))
        selected.setdefault(o['image_id'],[]).append(v)
    cases=[];images={}
    for iid,variants in sorted(selected.items(),key=lambda item:(room.get(item[0],''),item[0])):
        images[len(cases)]=dict(original=data_image(ROOT/meta[iid]['path'],texture=True))
        cases.append(dict(image_id=iid,title=objects[variants[0]['source']['object_id']]['image_code'],room_id=room.get(iid,''),
            category='顺序补查候选',variants=variants,annotation_ids=[v['source']['object_id'] for v in variants]))
    dataset=dict(cases=cases,counts=dict(cases=len(cases),variants=len(candidate_ids)),
        manifest=dict(contract_version='consensus_research_20260923_v1',review_round='followup_20260929',export_schema='order_review_20260928_v3',examples_only=False,formal_data_connected=False))
    (next_out/'data.js').write_text('window.STUDIO_IMAGES='+encode(images)+';Object.values(window.STUDIO_IMAGES).forEach(i=>i.texture=i.original);window.STUDIO_DATA='+encode(dataset)+';window.ORDER_REVIEW_SEED={};window.ORDER_HISTORY_SOURCES=[];',encoding='utf-8')
    page=(PREVIOUS/'index.html').read_text(encoding='utf-8').replace('<script defer src="../order_pattern_recall_20260929/accepted_review.js"></script>','')
    (next_out/'index.html').write_text(page,encoding='utf-8')
    dump(next_out/'source_objects.json',dict(objects=[objects[i] for i in candidate_ids]))
    result=dict(previous_queue_states=coverage_counts,missing=[r['object_id'] for r in coverage if r['current_status']=='missing'],
        previous_pending_without_current_reviewer=[r['object_id'] for r in coverage if r['previous_state']=='pending' and not r['current_reviewers']],
        pairing_deferred=len(deferred),next_round_objects=len(candidate_ids),next_round_images=len(cases))
    dump(out/'覆盖与续审汇总.json',result)
    return result


def build():
    OUT.mkdir(exist_ok=True);(OUT/'evidence').mkdir(exist_ok=True)
    seed=read(PREVIOUS/'received_orders.json')['records']
    objects={o['object_id']:o for o in read(ROOT/'analysis_results/shared_x_baseline_20260928/preprocessed_source.json')['objects']}
    display={o['object_id']:o for o in read(PREVIOUS/'source_objects.json')['objects']};objects.update(display)
    docs={who:read(path) for who,path in FILES.items()}
    for who,doc in docs.items():
        validate_return(doc,objects)
        if doc['previous_round_records']!=seed:raise ValueError('previous_round_drift:'+who)
        for event in doc['reopened_history']:
            validate_return(dict(schema=doc['schema'],examples_only=False,records={event['object_id']:event['record']}),objects)
        freeze_file(FILES[who],OUT/'evidence'/f'{who}.json')
    records,origins,conflicts=merge_returns(seed,{who:d['records'] for who,d in docs.items()})
    if conflicts:raise ValueError('review_conflict:'+','.join(conflicts))
    dataset=json.loads((PREVIOUS/'data.js').read_text(encoding='utf-8').split('window.STUDIO_DATA=',1)[1].split(';window.ORDER_REVIEW_SEED=',1)[0])
    variants={v['source']['object_id']:v['source'] for c in dataset['cases'] for v in c['variants']}
    inventory=[]
    for oid,o in display.items():
        r=records.get(oid)
        if r is None:raise ValueError('missing_review:'+oid)
        initial=seed[oid]['order'] if oid in seed else variants[oid]['default_preview_order']
        default=variants[oid]['default_preview_order'];source_order=list(range(len(o['links_zero_based'])))
        change=lambda old:'unchanged' if old==r['order'] else 'cycle_equivalent' if cycle_key(old)==cycle_key(r['order']) else 'adjacency_changed'
        inventory.append(dict(object_id=oid,image_id=o['image_id'],image_code=o['image_code'],worker_id=o.get('worker_id',''),
            object_kind=o['object_kind'],status=r['status'],reviewers=origins.get(oid,[]),initial_order=initial,default_order=default,
            confirmed_order=r['order'],round_change=change(initial),cumulative_change=change(source_order),
            pair_count=len(source_order),updated_at=r['updated_at'],note=r['note']))
    dump(OUT/'received_orders.json',dict(schema='received_order_results_20260929_v1',records=records,previous_round_records=seed,
        origins=origins,history={who:d['records'] for who,d in docs.items()},
        reopened_history={who:d['reopened_history'] for who,d in docs.items()},formal_analysis_connected=False))
    dump(OUT/'importable_orders.json',dict(schema='order_review_20260928_v3',examples_only=False,records=records,
        previous_round_records=seed,reopened_history=[e for d in docs.values() for e in d['reopened_history']]))
    scene_labels={i:{k:o.get(k,'not_recorded') for k in ('scene_doorway_status','scene_oos_status')} for i,o in display.items()}
    (OUT/'accepted_review.js').write_text('window.ORDER_ACCEPTED_REVIEW='+encode(dict(records=records,
        previous_round_records=seed,snapshots=[seed]+[d['records'] for d in docs.values()]))+';window.ORDER_SCENE_LABELS='+encode(scene_labels)+';',encoding='utf-8')
    dump(OUT/'confirmed_layouts.json',dict(schema='matterport_connection_order_v1',objects=[ordered_layout(display[i],r['order'])
        for i,r in records.items() if i in display and r['status']=='confirmed'],formal_analysis_connected=False))
    write_csv(OUT/'审核归并与改序清单.csv',inventory)
    write_csv(OUT/'待后续处理的配对问题.csv',[dict(object_id=i,image_code=objects[i]['image_code'],worker_id=objects[i].get('worker_id',''),note=r['note']) for i,r in records.items() if r['status']=='pairing'])
    clarifications=dict(schema='order_review_clarifications_20260929_v1',source='用户本轮明确意见',
        annotations={GLASS_ID:dict(image_code='uNb9QFRL6hY-60',worker_id='W028',cleaning_disposition='retained',
            comment='用户明确认可：正确标注玻璃内墙角，不能因少数标法排除。',unique_glass_corner_basis='用户说明，非算法独立认定')},
        images={DOOR_ID:dict(image_code='2t7WUuJeko7-07',doorway_status='difficult',oos_status='not_recorded',
            comment='原台账已有难标门洞记录，补充展示；曲线异常而点序正确。')},
        counterexamples=[dict(file=f'screenshot_{i}.png',order_correct=True,geometry_curve_odd=True,
            object_id=oid) for i,oid in enumerate(['new_95_3649_7457_W030','new_95_3649_7231_W036',None],1)],
        third_screenshot_identity='未显示图片编号，不推断归属',four_pair_policy='4对点默认不自动召回；明确人工顺序证据单列例外',
        scene_policy='门洞/OOS独立字段，可重叠；几何显示异常不判顺序错误',raw_mutation=False)
    for i,name in enumerate(['97b3cf8a-5ce4-45aa-960a-f1c6c8a941e3','215d996d-0518-45c7-a31c-d62971f78ee9','71fee458-a504-4298-95ee-dca07fb157c6'],1):
        freeze_file(Path('C:/Users/ASUS/AppData/Local/Temp')/f'codex-clipboard-{name}.png',OUT/'evidence'/f'screenshot_{i}.png')
    dump(OUT/'review_clarifications.json',clarifications)
    assert objects[GLASS_ID]['cleaning_disposition']=='retained'
    from .order_pattern_recall_20260929 import analyze_patterns
    patterns=analyze_patterns(objects,records,seed,origins,OUT)
    with (OUT/'遗漏候选.csv').open(encoding='utf-8-sig') as f:
        candidate_ids=[r['object_id'] for r in csv.DictReader(f)]
    comparison_cases=build_viewer(objects,records,inventory,candidate_ids)
    continuation=build_continuation(objects,records,origins,candidate_ids)
    summary=dict(schema='order_results_and_recall_v1',received_records=len(records),
        statuses=dict(Counter(r['status'] for r in records.values())),
        current_objects=len(display),current_states=dict(Counter(records[i]['status'] for i in display)),
        current_kind_status={f'{kind}:{status}':n for (kind,status),n in Counter((o['object_kind'],records[i]['status']) for i,o in display.items()).items()},
        patterns=patterns,comparison_cases=comparison_cases,continuation=continuation,formal_analysis_connected=False)
    dump(OUT/'summary.json',summary)
    dump(OUT/'field_contract.json',dict(schema=summary['schema'],primary_key='object_id',
        merge='各文件仅相对原89份基线的实际改动参与合并；相同决定保留双方归属；不同决定停止，不按时间静默覆盖',
        round_change='最终排列对本轮初始排列；既有确认优先，否则页面default；循环起点/反向等价单列',
        cumulative_change='最终排列对固定源点对identity；人工GT单列，不把初始x升序当作人工修改',
        confirmations='本次1160份有效确认，原始GT20份仅历史；其余配对/草稿不纳入确认数组',
        coverage='上一轮coverage逐对象保留previous_state/current_status/current_reviewers；待审有结果但无本轮审核人必须单列',
        continuation='独立order_followup_20260929入口仅含候选；配对汇总按object_id合并历史队列与本轮报告',
        room_export='room_grouped_matterport_order_v1：既有physical_same_supported房间→image_id→annotations；未知逐图单列；complete=false直到续审和配对完成',
        scope='候选不是错误裁决；4对点默认跳过自动召回；门洞与OOS分别统计，原始和清洗裁决不覆写'))
    return summary


if __name__=='__main__':
    print(json.dumps(build(),ensure_ascii=False,indent=2))
