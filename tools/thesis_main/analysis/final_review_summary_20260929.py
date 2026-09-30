"""最终审核描述统计、历史评语索引及同房Matterport数据包。"""
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path
from .finalize_review_20260928 import ROOT, read, dump, write_csv
from .receive_order_results_20260929 import freeze_file
from .receive_order_review_20260928 import validate_return
from .build_order_gt_screened_20260928 import ordered_layout
from .order_pattern_recall_20260929 import ring_relation, prechange_features, RULES
from .build_order_studio_20260926 import encode
from tools.label_studio.panorama_studio.geometry import analyze

OUT=ROOT/'analysis_results/final_review_summary_20260929'
INPUT=Path('C:/Users/ASUS/Downloads/角点顺序审核(4).json')


def rows(path):
    with (ROOT/path).open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))


def comment_leaves(value,path=''):
    """只取原评语，不把自动解释或同图复制内容当成新意见。"""
    if isinstance(value,dict):
        for key,v in value.items():
            p=path+'.'+key
            if key in {'comment','raw_comment','note'} and isinstance(v,str) and v.strip():yield p,v
            elif key not in {'interpretation','summary','view_context'}:yield from comment_leaves(v,p)
    elif isinstance(value,list):
        for i,v in enumerate(value):yield from comment_leaves(v,path+f'[{i}]')


def comment_topics(text):
    # 仅检索线索，否定、疑问、历史意见均不自动升格为当前分类。
    topics=[]
    if any(w in text for w in ('范围','停止','截止','空间不同','不同空间','空间差','空间区域','最小空间','标注区域','标注空间','小空间','大空间','玻璃')):topics.append('scope')
    if any(w in text for w in ('细节','壁炉','凸起','凹凸','墙面变化','简化','省略','拐角')):topics.append('detail')
    return topics


def collect_comments(ledger):
    records={}
    for r in ledger:
        oid=r['canonical_annotation_id'];iid=r['image_id']
        sources=[('annotation',oid,k,r[k]) for k in ('current_comment','current_decision_comment')]
        sources.append(('image',iid,'image_comment',r['image_comment']))
        for k,scope in [('review_history','annotation'),('image_review_history','image'),('annotation_traits','annotation'),('image_traits','image')]:
            for path,text in comment_leaves(json.loads(r[k] or '{}'),k):sources.append((scope,oid if scope=='annotation' else iid,path,text))
        for scope,target,path,text in sources:
            if not text.strip():continue
            key=(scope,target,text)
            e=records.setdefault(key,dict(image_id=iid,image_code=r['image_code'],object_kind=scope,object_id=target,
                worker_id=r['worker_id'] if scope=='annotation' else '',comment=text,source_fields=[],
                current_cleaning_disposition=r['cleaning_disposition'] if scope=='annotation' else 'image_context_not_personal_exclusion',
                topics=comment_topics(text),evidence_level='comment_candidate_not_new_verdict'))
            if path not in e['source_fields']:e['source_fields'].append(path)
    return list(records.values())


def geometry_status(o,order):
    if o['preprocessing_status']!='ready':return dict(status='pairing_unavailable',issues=[],unusable_pair_ids=[])
    p=o['preprocessed_points'];links=o['links_zero_based']
    if any(not (0<=x<=1024 and 0<=y<=512) for x,y in p):
        return dict(status='representation_limited',issues=['coordinates_outside_image'],unusable_pair_ids=[])
    if len(links)<3:return dict(status='representation_limited',issues=['too_few_pairs'],unusable_pair_ids=[])
    pairs=[dict(top=dict(zip(('x','y'),p[links[i][0]])),bottom=dict(zip(('x','y'),p[links[i][1]]))) for i in order]
    g=analyze(dict(width=1024,height=512,coordinate_mode='pixels',ordered_pairs=pairs),compute_fit=False)['raw']
    missing=[order[i]+1 for i,(a,b) in enumerate(zip(g['floor'],g['ceiling'])) if a is None or b is None]
    return dict(status='surface_valid' if g['surface_valid'] else 'representation_limited',issues=g['issues'],unusable_pair_ids=missing)


def build():
    csv.field_size_limit(32*1024*1024);OUT.mkdir(exist_ok=True);(OUT/'evidence').mkdir(exist_ok=True)
    ledger=rows('analysis_results/review_final_20260928/全量复核.csv');byid={r['canonical_annotation_id']:r for r in ledger}
    objects={o['object_id']:o for o in read(ROOT/'analysis_results/pairing_applied_20260929/preprocessed_source.json')['objects']}
    sources={o['object_id']:o for o in read(ROOT/'analysis_results/order_after_pairing_20260929/source_objects.json')['objects']}
    doc=read(INPUT);validate_return(doc,sources)
    if set(doc['records'])!=set(sources) or any(r['status']!='confirmed' for r in doc['records'].values()):raise ValueError('latest_batch_incomplete')
    if doc['previous_round_records']!={}:raise ValueError('unexpected_latest_seed')
    freeze_file(INPUT,OUT/'evidence/order23.json')
    old=read(ROOT/'analysis_results/order_completion_audit_20260929/received_orders.json')
    kept=read(ROOT/'analysis_results/pairing_applied_20260929/preserved_orders.json')['records']
    if set(kept)&set(doc['records']):raise ValueError('batch_overlap')
    final={**kept,**doc['records']};validate_return(dict(schema='order_review_20260928_v3',examples_only=False,records=final),objects)
    origins={**old['origins'],**{oid:['user_after_pairing23'] for oid in doc['records']}}
    dump(OUT/'received_orders.json',dict(schema='order_review_20260928_v3',examples_only=False,records=final,origins=origins))
    # 最新对象继承原始显示排列，不能拿点对数组存储顺序冒充本轮默认排列。
    batches=[];feature_rows=[];batch_counts=[]
    first={r['object_id']:r for r in rows('analysis_results/order_pattern_recall_20260929/审核归并与改序清单.csv')}
    frozen={o['object_id']:o for o in read(ROOT/'analysis_results/shared_x_baseline_20260928/preprocessed_source.json')['objects']}
    frozen.update({o['object_id']:o for o in read(ROOT/'analysis_results/order_gt_screened_20260928/source_objects.json')['objects']})
    for oid,r in final.items():
        o=objects[oid]
        if oid in doc['records']:
            batch='after_pairing23';before=sorted(range(len(o['links_zero_based'])),key=lambda i:o['preprocessed_points'][o['links_zero_based'][i][0]][0]);fsource=o
        elif oid in first:
            batch='first_merged';before=json.loads(first[oid]['initial_order']);fsource=frozen[oid]
        else:batch='followup77' if origins.get(oid)==['user_followup77'] or origins.get(oid)==['user_followup'] else 'same_image35';fsource=frozen[oid];before=list(range(len(fsource['links_zero_based'])))
        previous=r.get('previous_record',r)
        after=r['order'] if batch=='after_pairing23' else previous['order']
        change=ring_relation(before,after)
        entry=dict(object_id=oid,image_id=o['image_id'],image_code=o['image_code'],worker_id=o.get('worker_id',''),object_kind=o['object_kind'],
            batch=batch,reviewers=origins.get(oid,['historical_seed']),initial_order=before,final_order=after,change=change)
        batches.append(entry)
        if o['object_kind']=='annotation':feature_rows.append(dict(entry,**prechange_features(fsource,before)))
    for batch in sorted({r['batch'] for r in batches}):
        items=[r for r in batches if r['batch']==batch];batch_counts.append(dict(batch=batch,objects=len(items),images=len({r['image_id'] for r in items}),changes=dict(Counter(r['change'] for r in items))))
    write_csv(OUT/'逐对象改序及审核来源.csv',batches);write_csv(OUT/'改前特征与最终改序.csv',feature_rows)
    feature_stats=[]
    for batch in sorted({r['batch'] for r in feature_rows}):
        cohort=[r for r in feature_rows if r['batch']==batch]
        for rule in RULES:
            valid=[r for r in cohort if r['feature_status']=='ok'];hit=lambda r:any(r[k] for k in ('any_acute','dense_three_pairs_24px','near_bearing_depth_jump')) if rule=='recall_union' else r[rule]
            yes=[r for r in valid if hit(r)];no=[r for r in valid if not hit(r)]
            feature_stats.append(dict(batch=batch,rule=rule,eligible=len(valid),uncomputable=len(cohort)-len(valid),hit=len(yes),hit_changed=sum(r['change']=='adjacency_changed' for r in yes),nonhit=len(no),nonhit_changed=sum(r['change']=='adjacency_changed' for r in no)))
    write_csv(OUT/'改序共性_按批次描述.csv',feature_stats)
    # 完整保留同房分类，研究样本覆盖另算，不把全部同房库规模当259图分母。
    registry=read(ROOT/'analysis_results/consensus_research_20260923/inputs/room_registry.json.gz')
    registry_images={r['image_id']:r for r in registry['images']}
    original_groups=[dict(review_code=g['review_code'],building=g['building'],image_ids=g['image_ids'],numbers=g['numbers'],
        **g['raw_current'],review_state=g['review_state']) for g in registry['groups']]
    write_csv(OUT/'同房原分组_完整分类.csv',original_groups)
    dump(OUT/'同房分类_原始完整记录.json',dict(source='analysis_results/consensus_research_20260923/inputs/room_registry.json.gz',groups=registry['groups'],candidates=registry['candidates'],images=registry['images']))
    rooms={};room_rows=[];population={r['image_id'] for r in ledger}
    for g in registry['candidates']:
        if g['physical_same_supported']:
            for iid in g['image_ids']:
                if iid in rooms and rooms[iid]!=g['candidate_id']:raise ValueError('ambiguous_room:'+iid)
                rooms[iid]=g['candidate_id']
        room_rows.append(dict(candidate_id=g['candidate_id'],source_group_codes=g['source_group_codes'],raw_decision=g['raw_decision'],physical_same_supported=g['physical_same_supported'],
            difficulty_similarity=g['difficulty_similarity'],comparable_for_prediction=g['comparable_for_prediction'],review_state=g['review_state'],
            oos_status=g['oos_status'],issue_tags=g['issue_tags'],selection_hold_reasons=g['selection_hold_reasons'],image_ids=g['image_ids'],numbers=g['numbers'],
            research_images=sorted(set(g['image_ids'])&population),research_image_count=len(set(g['image_ids'])&population)))
    write_csv(OUT/'同房分类_全部候选组.csv',room_rows)
    oldstates={r['object_id']:r['final_state'] for r in rows('analysis_results/order_completion_audit_20260929/全量3152份排序闭合审计.csv')}
    paired={r['object_id']:r['reason'] for r in rows('analysis_results/pairing_applied_20260929/本轮34份去向.csv')}
    comment_records=collect_comments(ledger);write_csv(OUT/'历史评语_去重来源索引.csv',comment_records)
    evidence=[r for r in comment_records if r['topics']];write_csv(OUT/'空间与细节_评语候选明细.csv',evidence)
    comments_by_image=defaultdict(list)
    for r in evidence:comments_by_image[r['image_id']].append(r)
    inventory=[];layouts=defaultdict(list)
    for r in ledger:
        oid=r['canonical_annotation_id'];o=objects[oid]
        state='confirmed' if oid in final else 'four_pairs_default_skip' if paired.get(oid)=='four_pairs_default_skip' else 'pairing_deferred' if paired.get(oid)=='pairing_unavailable' else oldstates[oid]
        order=final[oid]['order'] if oid in final else list(range(len(o['links_zero_based'] or [])))
        g=geometry_status(o,order)
        inventory.append(dict(object_id=oid,image_id=o['image_id'],image_code=o['image_code'],worker_id=o['worker_id'],condition=o['condition'],
            room_id=rooms.get(o['image_id'],''),cleaning_disposition=r['cleaning_disposition'],worker_quality_gate=r['worker_quality_gate'],
            order_state=state,order_change=next((x['change'] for x in batches if x['object_id']==oid),'not_human_confirmed'),
            preprocessing_status=o['preprocessing_status'],geometry_status=g['status'],geometry_issues=g['issues'],unusable_pair_ids=g['unusable_pair_ids'],
            individually_reviewed=r['individual_review_covered'],scene_oos_status=r['scene_oos_status'],scene_doorway_status=r['scene_doorway_status'],
            scope_difference_image=r['scope_difference_image'],detail_difference_image=r['detail_difference_image'],
            scope_difference_annotation=r['scope_difference_annotation'],detail_difference_annotation=r['detail_difference_annotation'],
            model_edit_status=r['model_edit_status'],trap_status=r['trap_status'],repair_evidence=o['repair_evidence'],deleted_previous_point_indices=o.get('deleted_previous_point_indices',[])))
    write_csv(OUT/'全量3152份最终台账.csv',inventory)
    write_csv(OUT/'不可计算及表示限制.csv',[r for r in inventory if r['geometry_status']!='surface_valid'])
    images=[]
    for iid in sorted(population):
        group=[r for r in ledger if r['image_id']==iid];states=[r for r in inventory if r['image_id']==iid]
        for k in ('scene_oos_status','scene_doorway_status','scope_difference_image','detail_difference_image'):
            if len({r[k] for r in group})!=1:raise ValueError('image_field_conflict:'+iid+':'+k)
        scope_tag=any('scope' in json.loads(r['image_traits'] or '{}').get('tags',[]) or 'scope' in json.loads(r['annotation_traits'] or '{}').get('tags',[]) or 'scope' in json.loads(r['coverage_review'] or '{}').get('effective_tags',[]) for r in group)
        detail_tag=any('detail' in json.loads(r['image_traits'] or '{}').get('tags',[]) or 'detail' in json.loads(r['annotation_traits'] or '{}').get('tags',[]) or 'detail' in json.loads(r['coverage_review'] or '{}').get('effective_tags',[]) for r in group)
        ev=comments_by_image[iid];image=dict(image_id=iid,image_code=group[0]['image_code'],room_id=rooms.get(iid,''),annotations=len(group),
            room_spatial_classification=registry_images[iid]['spatial_classification'],room_classification_sources=registry_images[iid]['spatial_field_sources'],
            main_visual_space=registry_images[iid]['main_visual_space'],expected_annotation_extent=registry_images[iid]['expected_annotation_extent'],
            cleaning_counts=dict(Counter(r['cleaning_disposition'] for r in group)),order_counts=dict(Counter(r['order_state'] for r in states)),
            oos_status=group[0]['scene_oos_status'],doorway_status=group[0]['scene_doorway_status'],
            scope_explicit_tag=scope_tag,detail_explicit_tag=detail_tag,
            scope_existing_ledger=any(r['scope_difference_image']=='true' or r['scope_difference_annotation']=='true' for r in group),
            detail_existing_ledger=any(r['detail_difference_image']=='true' or r['detail_difference_annotation']=='true' for r in group),
            scope_comment_candidate=any('scope' in r['topics'] for r in ev),detail_comment_candidate=any('detail' in r['topics'] for r in ev),
            comments=ev,coverage='not_exhaustively_reviewed_for_scope_or_detail',image_comment=group[0]['image_comment'])
        images.append(image)
    write_csv(OUT/'逐图分类及覆盖.csv',images)
    write_csv(OUT/'空间不同_图片收集.csv',[r for r in images if r['scope_explicit_tag'] or r['scope_existing_ledger'] or r['scope_comment_candidate']])
    write_csv(OUT/'细节不同_图片收集.csv',[r for r in images if r['detail_explicit_tag'] or r['detail_existing_ledger'] or r['detail_comment_candidate']])
    write_csv(OUT/'OOS_图片清单.csv',[r for r in images if r['oos_status'] in {'confirmed','pending'}])
    write_csv(OUT/'门洞交界_图片清单.csv',[r for r in images if r['doorway_status'] not in {'none','not_recorded'}])
    workers=[]
    for worker in sorted({r['worker_id'] for r in inventory}):
        group=[r for r in inventory if r['worker_id']==worker]
        workers.append(dict(worker_id=worker,total=len(group),images=len({r['image_id'] for r in group}),cleaning=dict(Counter(r['cleaning_disposition'] for r in group)),
            order=dict(Counter(r['order_state'] for r in group)),changes=dict(Counter(r['order_change'] for r in group)),geometry=dict(Counter(r['geometry_status'] for r in group))))
    write_csv(OUT/'逐人统计.csv',workers)
    # 数据包覆盖全部对象；默认环仅作未审表示，不当作人工确认或合格几何。
    for oid,o in objects.items():
        confirmed=oid in final;order=final[oid]['order'] if confirmed else list(range(len(o['links_zero_based'] or [])))
        layout=ordered_layout(o,order) if o['preprocessing_status']=='ready' else dict(object_id=oid,points_1024x512=None,links_zero_based=None)
        layout.update(image_id=o['image_id'],image_code=o['image_code'],worker_id=o.get('worker_id'),object_kind=o['object_kind'],
            order_status='human_confirmed' if confirmed else 'original_gt_reference' if o['object_kind']=='gt_original' else 'default_unreviewed',
            preprocessing_status=o['preprocessing_status'],worker_quality_gate=o.get('worker_quality_gate'),cleaning_disposition=o.get('cleaning_disposition'),
            geometry=geometry_status(o,order),scene_oos_status=o.get('scene_oos_status'),scene_doorway_status=o.get('scene_doorway_status'),
            source=o['source'],point_labels=o['point_labels'],original_export_indices=o.get('original_export_indices'),repair_evidence=o['repair_evidence'] if o['object_kind']=='annotation' else [],reviewers=origins.get(oid,[]))
        layouts[rooms.get(o['image_id'],'unresolved:'+o['image_id'])].append(layout)
    dump(OUT/'同房汇集_Matterport.json',dict(schema='final_room_grouped_matterport_v1',order_queue_complete=True,all_objects_human_confirmed=False,
        coordinate_source='analysis_results/pairing_applied_20260929/preprocessed_source.json',rooms=[dict(room_id=key,objects=vals) for key,vals in layouts.items()]))
    for name in ('预标注未改动与影响评语汇总.csv','用户comment明确记录_模型误导影响.csv'):
        freeze_file(ROOT/'analysis_results/order_model_same_image_20260929'/name,OUT/name)
    freeze_file(ROOT/'analysis_results/order_gt_screened_20260928/原始与人工GT审计.csv',OUT/'原始与人工GT审计.csv')
    for source,name in [('order_pattern_recall_20260929/顺序规律_summary.json','首轮本人及一正_统计.json'),
        ('order_pattern_recall_20260929/顺序规律_历史本人改序补充.csv','历史本人改序补充.csv'),
        ('order_pattern_recall_20260929/顺序规律_规则评估.csv','首轮改序共性_规则评估.csv'),
        ('order_model_same_image_20260929/summary.json','同图历史改序_补查统计.json')]:
        freeze_file(ROOT/'analysis_results'/source,OUT/name)
    summary=dict(annotations=len(inventory),images=len(images),confirmed_orders=len(final),annotation_order_states=dict(Counter(r['order_state'] for r in inventory)),
        cleaning=dict(Counter(r['cleaning_disposition'] for r in inventory)),geometry=dict(Counter(r['geometry_status'] for r in inventory)),
        retained_geometry=dict(Counter(r['geometry_status'] for r in inventory if r['cleaning_disposition'] not in {'excluded_by_review','historical_not_accepted'})),
        manual_gt_confirmed=sum(objects[i]['object_kind']=='gt_manual_revision' for i in final),batches=batch_counts,
        scene_images=dict(oos=dict(Counter(r['oos_status'] for r in images)),doorway=dict(Counter(r['doorway_status'] for r in images)),
            both=sum(r['oos_status']=='confirmed' and r['doorway_status'] not in {'none','not_recorded'} for r in images)),
        scope_detail={k:sum(bool(r[k]) for r in images) for k in ('scope_explicit_tag','detail_explicit_tag','scope_existing_ledger','detail_existing_ledger','scope_comment_candidate','detail_comment_candidate')},
        scope_collected_images=sum(r['scope_explicit_tag'] or r['scope_existing_ledger'] or r['scope_comment_candidate'] for r in images),
        detail_collected_images=sum(r['detail_explicit_tag'] or r['detail_existing_ledger'] or r['detail_comment_candidate'] for r in images),
        room_registry_groups=len(registry['groups']),room_candidates=len(room_rows),supported_room_candidates=sum(r['physical_same_supported'] for r in room_rows),
        original_room_classification=dict(Counter(g['raw_current']['decision'] for g in registry['groups'])),
        research_supported_rooms=len({rooms[i] for i in population if i in rooms}),research_images_with_room=sum(i in rooms for i in population),
        unchanged_model_coordinates=sum(r['model_edit_status']=='unchanged_coordinates' for r in ledger),
        user_comment_model_influence=len(rows('analysis_results/order_model_same_image_20260929/用户comment明确记录_模型误导影响.csv')),
        order_queue_complete=True,all_annotations_individually_confirmed=False,formal_analysis_connected=False)
    if len(inventory)!=3152 or len(images)!=259 or len(final)!=1295 or any(r['order_state'] in {'pending_order','geometry_blocked'} for r in inventory):raise ValueError('final_coverage_drift')
    dump(OUT/'summary.json',summary)
    dump(OUT/'field_contract.json',dict(schema='final_review_summary_v1',primary_keys=['object_id','image_id','candidate_id'],
        population='3152份/259图；同房全库使用自己的组数分母；历史未纳入与本轮排除分开。',
        scope_detail='explicit_tag仅结构化标签；existing_ledger保留既有语义归纳；comment_candidate仅历史评语检索线索，不是新增人工裁决。无记录不等于无差异，图片线索不传播给同房其他图。',
        ring='各轮实际初始顺序对比最终环；起点/方向等价不算邻接改变；本轮配对改变与旧点对不直接比较。',
        geometry='表示限制独立于配对、排序、清洗资格；uNb19/W010第2/3对wrong_hemisphere，不自动判OOS。',
        export='默认未审环与人工确认环分开；不可配对无数组；完整JSON保留同房原分类、raw_current和证据。'))
    write_report(summary,images,room_rows,original_groups)
    script='window.ORDER_ACCEPTED_REVIEW='+encode(dict(records=doc['records'],snapshots=[{},doc['records']]))+';'
    (OUT/'accepted_23.js').write_text(script,encoding='utf-8')
    page=ROOT/'analysis_results/order_after_pairing_20260929/index.html';text=page.read_text(encoding='utf-8');tag='<script defer src="../final_review_summary_20260929/accepted_23.js"></script>'
    if tag not in text:page.write_text(text.replace('<script defer src="data.js"></script>','<script defer src="data.js"></script>'+tag),encoding='utf-8')
    return summary


def write_report(s,images,rooms,original_groups):
    def table(title,items):
        keys=list(items[0]) if items else []
        return '<h2>'+html.escape(title)+'</h2><table><thead><tr>'+''.join('<th>'+html.escape(k)+'</th>' for k in keys)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(r[k]))+'</td>' for k in keys)+'</tr>' for r in items)+'</tbody></table>'
    intro=f'<h1>最终审核统计与分类索引</h1><p>{s["annotations"]}份人员标注 · {s["images"]}张图 · {s["confirmed_orders"]}份排序确认（含30份人工GT）。既定排序队列已闭合，不等于所有标注逐份人工确认或几何均可计算。</p>'
    intro+='<p>uNb9QFRL6hY-19/W010：第2、3对上端点在地平线下，当前模型无法构造这些顶点及相邻曲线。配对、预处理和排序记录有效；不自动判错标或OOS。</p><p>空间/细节：勾选标签、既有台账归纳、历史评语候选分别展示。评语可能是否定、疑问或旧意见，必须阅读原文；未出现线索不表示无差异。门洞与OOS可同时存在。</p>'
    files=['README.md','逐图分类及覆盖.csv','空间不同_图片收集.csv','细节不同_图片收集.csv','空间与细节_评语候选明细.csv','OOS_图片清单.csv','门洞交界_图片清单.csv','同房原分组_完整分类.csv','同房分类_全部候选组.csv','同房分类_原始完整记录.json','同房汇集_Matterport.json','全量3152份最终台账.csv','逐人统计.csv','逐对象改序及审核来源.csv','改序共性_按批次描述.csv','用户comment明确记录_模型误导影响.csv','预标注未改动与影响评语汇总.csv','不可计算及表示限制.csv']
    intro+='<details><summary>下载数据与证据</summary><ul>'+''.join(f'<li><a href="{html.escape(f)}">{html.escape(f)}</a></li>' for f in files)+'</ul></details><p><label>查找图片、房间、评语 <input id="search" type="search"></label></p>'
    cards=[]
    for r in images:
        ev=''.join('<li>'+html.escape(e['worker_id'] or '图片意见')+'：'+html.escape(e['comment'])+' <small>'+html.escape('；'.join(e['source_fields']))+'</small></li>' for e in r['comments'])
        labels=dict(scope_explicit_tag='空间差异勾选',detail_explicit_tag='细节差异勾选',scope_existing_ledger='空间差异既有台账',detail_existing_ledger='细节差异既有台账',scope_comment_candidate='空间评语线索',detail_comment_candidate='细节评语线索')
        flags={labels[k]:'有记录' if v else '未记录' for k,v in r.items() if k in labels}
        cards.append('<details class="image"><summary>'+html.escape(r['image_code']+' · '+(r['room_id'] or '同房未确认')+' · OOS:'+r['oos_status']+' · 门洞:'+r['doorway_status'])+'</summary><p>'+html.escape(str(flags))+'</p><p>'+html.escape(r['image_comment'])+'</p><ul>'+ev+'</ul></details>')
    room_cards=''.join('<details class="image"><summary>'+html.escape(g['review_code']+' · '+g['building']+' · '+g['decision'])+'</summary><pre style="white-space:pre-wrap">'+html.escape(json.dumps(g,ensure_ascii=False,indent=2))+'</pre></details>' for g in original_groups)
    headline=table('图片维度（可重叠；缺少记录不是否定）',[dict(类别='OOS明确',图片数=s['scene_images']['oos'].get('confirmed',0)),dict(类别='门洞交界',图片数=sum(v for k,v in s['scene_images']['doorway'].items() if k not in {'none','not_recorded'})),dict(类别='空间差异既有台账',图片数=s['scope_detail']['scope_existing_ledger']),dict(类别='细节差异既有台账',图片数=s['scope_detail']['detail_existing_ledger'])])
    batch_names=dict(first_merged='首轮双人归并（含历史沿用）',followup77='77份补查',same_image35='35份同图补查',after_pairing23='23份配对后排序')
    batch_table=[dict(批次=batch_names[r['batch']],标注份数=r['objects'],图片数=r['images'],邻接改变=r['changes'].get('adjacency_changed',0),未改=r['changes'].get('unchanged',0),环等价=r['changes'].get('equivalent',0)) for r in s['batches']]
    page='<!doctype html><meta charset="utf-8"><title>最终审核统计</title><style>body{font:16px system-ui;margin:28px;color:#163a32;background:#f5f8f6}p{line-height:1.7}table{border-collapse:collapse;width:100%;background:white}td,th{padding:10px;border:1px solid #ddd;text-align:left}details{background:white;padding:12px;margin:8px 0}summary{cursor:pointer}input{font:inherit;padding:8px;width:50%}small{color:#65726d}</style>'+intro+headline+table('批次改序（不同基线分开）',batch_table)+table('同房原分类（260组；拆分后的259候选组另表）',[dict(分类=k,组数=v) for k,v in s['original_room_classification'].items()])+'<h2>同房原分类与评语</h2>'+room_cards+'<h2>逐图分类与评语</h2>'+''.join(cards)+'<script>document.getElementById("search").oninput=e=>{const q=e.target.value.toLowerCase();document.querySelectorAll(".image").forEach(x=>x.hidden=!x.textContent.toLowerCase().includes(q));};</script>'
    (OUT/'index.html').write_text(page,encoding='utf-8')
    md='# 最终审核统计\n\n[浏览分类及评语](index.html)。当前全部指定排序队列闭合；未逐份人工确认对象、5份配对不可用及三维表示限制继续独立记录。\n\n'
    md+='## 统计汇总\n\n```json\n'+json.dumps(s,ensure_ascii=False,indent=2)+'\n```\n\n'
    md+='## 同房、场景与差异口径\n\n同房全库组、拆分候选组和259图覆盖使用不同分母。原始完整记录保留physical_same、主视觉空间一致性、标注范围一致性、难度相似性、决策、评论、候选拆分及暂缓原因。只在physical_same_supported的组内汇集，其他图片逐图单列。\n\nOOS与门洞相互独立，可重叠；not_recorded不是正常。空间/细节收集包括历史排除评语和保留评语，不因现已排除而丢掉场景线索。explicit_tag是用户结构化标签；existing_ledger含旧语义归纳；comment_candidate是宽检索，含疑问/否定/历史意见，不自动认定差异。没有记录为未知，不能算阴性；同房其他视角不自动继承分类。\n\n'
    md+='## 排序与共性\n\n13份本批真实邻接改动、10份未改；环起点/方向等价独立。首轮为归并后的对象统计，不能加总审核者事件充当独立样本。逐对象表保留审核者；原首轮按本人/一正的独立分析见order_pattern_recall_20260929/顺序规律_summary.json。新特征比较沿用45度锐角、24px密集及1.5深度比，基于每批改前排列；几何不可计算单列。批次筛选不同，比例仅描述；同图历史改序召回参考order_model_same_image_20260929/summary.json，35份补查仅1份实际改邻接，不宣称总体规律或因果。\n\n'
    md+='## 模型与GT\n\n模型影响仅按comment明确的4份；100份原提交坐标未改与模型影响不是同义，可能重叠。保留完整证据表，预处理不改写原提交对比结论。原始与人工GT差异按既有1px口径，30份实质修订已排序确认，纯次序差异另列，不把原始GT当待审任务。\n\n'
    md+='## 数据包与限制\n\n同房汇集_Matterport.json包含原始GT、人工GT和人员对象，按最终确认环输出上点/下点交替数组。默认未审环仅标default_unreviewed；不可配对points为null；每项保留清洗、资格、表示状态和原来源。不修改原始导出，不开展正式共识或IoU重算。初始几何的默认环可有自交，不等于人员错误。\n\nuNb9QFRL6hY-19/W010的第2、3对上端点y约261，下方端点约289，虽可配对但上点低于当前相机水平线，因此wrong_hemisphere，涉及它们的曲线缺失。现行模型下完整3D不可构造，不能靠排序修复，也不自动增加OOS裁决。\n'
    md+='\n## 复现与验证\n\n生成命令：`python -m tools.thesis_main.analysis.final_review_summary_20260929`。独立字段合同见field_contract.json。定向Python与浏览器验证包括3152份闭合、1295确认绑定、3441对象连接数组还原、分类不传播、评语去重、最新队列确认接收及地平线限制提示。截图检查后清理；未运行无关全仓测试或正式实验。首轮按审核者统计及历史补充已另存本目录，不能把审核事件数相加作为独立标注数。\n'
    (OUT/'README.md').write_text(md,encoding='utf-8')


if __name__=='__main__':print(json.dumps(build(),ensure_ascii=False,indent=2))
