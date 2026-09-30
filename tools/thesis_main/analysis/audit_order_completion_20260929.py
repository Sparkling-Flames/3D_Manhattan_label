"""核对全批次接收及3152份排序筛选闭合性；不把未召回当作人工确认。"""
import csv
import json
from collections import Counter
from pathlib import Path

from .receive_order_results_20260929 import ROOT, freeze_file, merge_returns, build_continuation
from .receive_followup_model_audit_20260929 import validate_followup
from .receive_order_review_20260928 import validate_return
from .order_pattern_recall_20260929 import _read_context, initial_order, prechange_features, candidate_reason, ring_relation
from .build_order_gt_screened_20260928 import NO_RECALL
from .shared_x_reanalysis_20260922 import shared_x
from .finalize_review_20260928 import read, dump, write_csv
from .build_order_studio_20260926 import encode

OUT=ROOT/'analysis_results/order_completion_audit_20260929'


def build():
    csv.field_size_limit(32*1024*1024);OUT.mkdir(exist_ok=True);(OUT/'evidence').mkdir(exist_ok=True)
    objects={o['object_id']:o for o in read(ROOT/'analysis_results/shared_x_baseline_20260928/preprocessed_source.json')['objects']}
    objects.update({o['object_id']:o for o in read(ROOT/'analysis_results/order_gt_screened_20260928/source_objects.json')['objects']})
    first=ROOT/'analysis_results/order_pattern_recall_20260929'
    seed=read(ROOT/'analysis_results/order_gt_screened_20260928/received_orders.json')['records']
    returns={who:read(first/'evidence'/f'{who}.json') for who in ('user','yizheng')}
    for who,doc in returns.items():
        validate_return(doc,objects)
        if doc['previous_round_records']!=seed:raise ValueError('first_seed_changed:'+who)
    records,origins,conflicts=merge_returns(seed,{who:d['records'] for who,d in returns.items()})
    if conflicts or records!=read(first/'received_orders.json')['records']:raise ValueError('first_merge_drift')
    previous,explicit,history=_read_context()
    for oid,events in history.items():
        for event in events:validate_return(dict(schema='order_review_20260928_v3',examples_only=False,records={oid:event['record']}),objects)
    batches=[]
    for label,queue,path in [('followup77','order_followup_20260929',ROOT/'analysis_results/order_model_same_image_20260929/evidence/user_followup.json'),
                             ('same_image35','order_same_image_followup_20260929',Path('C:/Users/ASUS/Downloads/角点顺序审核(3).json'))]:
        sources={o['object_id']:o for o in read(ROOT/'analysis_results'/queue/'source_objects.json')['objects']}
        doc=read(path);validate_followup(doc,sources)
        if set(doc['records']) & set(records):raise ValueError('unexpected_cross_batch_overlap:'+label)
        for oid,o in sources.items():
            if o!=objects[oid]:raise ValueError('followup_source_drift:'+oid)
        if label=='followup77':
            if {**records,**doc['records']}!=read(ROOT/'analysis_results/order_model_same_image_20260929/received_orders.json')['records']:raise ValueError('second_merge_drift')
        freeze_file(path,OUT/'evidence'/f'{label}.json')
        records.update(doc['records']);origins.update({oid:['user_'+label] for oid in doc['records']})
        batches.append(dict(batch=label,expected=len(sources),received=len(doc['records']),
            statuses=dict(Counter(r['status'] for r in doc['records'].values())),
            changes=dict(Counter(ring_relation(list(range(len(r['order']))),r['order']) for r in doc['records'].values()))))
    validate_return(dict(schema='order_review_20260928_v3',examples_only=False,records=records),objects)
    changed_images=set()
    for oid,o in objects.items():
        if o['object_kind']!='annotation' or o['preprocessing_status']!='ready':continue
        events=([records[oid]] if oid in records else [])+[e['record'] for e in history.get(oid,[])]
        if any(r['status']=='confirmed' and ring_relation(list(range(len(o['links_zero_based']))),r['order'])=='adjacency_changed' for r in events):changed_images.add(o['image_id'])
    audit=[];candidates=[];geometry_blocked=[]
    for oid,o in objects.items():
        if o['object_kind']!='annotation':continue
        if o['preprocessing_status']=='ready' and shared_x(o['before_preprocessing_points'],o['links_zero_based']).tolist()!=o['preprocessed_points']:
            raise ValueError('shared_x_drift:'+oid)
        order=initial_order(o,seed) if o['preprocessing_status']=='ready' else []
        f=prechange_features(o,order);status=records.get(oid,{}).get('status','unreviewed')
        row=dict(object_id=oid,image_id=o['image_id'],image_code=o['image_code'],worker_id=o['worker_id'],
            object_kind='annotation',cleaning_disposition=o['cleaning_disposition'],current_status=status,
            explicit_order_evidence=oid in explicit,**f)
        geom_reason=candidate_reason(row)
        triggers=[]
        if previous[oid] in {'pending','confirmed'}:triggers.append('original_gt_or_explicit_queue')
        if geom_reason=='candidate':triggers.append('geometry_or_explicit')
        if o['image_id'] in changed_images:triggers.append('same_image_order_change')
        state=('excluded' if o['cleaning_disposition'] in {'excluded_by_review','historical_not_accepted'} else
            'confirmed' if status=='confirmed' else 'pairing_deferred' if status=='pairing' or o['preprocessing_status']!='ready' else
            'user_no_recall' if o['image_code'] in NO_RECALL else 'geometry_blocked' if f['feature_status']!='ok' else
            'four_pairs_default_skip' if f['pair_count']<=4 and not row['explicit_order_evidence'] and previous[oid] not in {'pending','confirmed'} else
            'pending_order' if triggers else 'not_triggered')
        row.update(final_state=state,trigger_reasons=triggers,geometry_rule_state=geom_reason,
            scene_doorway_status=o.get('scene_doorway_status'),scene_oos_status=o.get('scene_oos_status'))
        audit.append(row)
        if state=='pending_order':candidates.append(oid)
        if state=='geometry_blocked':geometry_blocked.append(oid)
    if len(audit)!=3152 or len({r['image_id'] for r in audit})!=259:raise ValueError('population_drift')
    write_csv(OUT/'全量3152份排序闭合审计.csv',audit)
    dump(OUT/'received_orders.json',dict(schema='all_order_batches_received_v1',records=records,origins=origins,previous_round_records=seed,batches=batches))
    continuation=build_continuation(objects,records,origins,candidates,out=OUT,queue_name='order_completion_remaining_20260929')
    with (OUT/'配对问题_汇总待后处理.csv').open(encoding='utf-8-sig') as f:pair_rows=list(csv.DictReader(f))
    for oid in geometry_blocked:
        o=objects[oid];pair_rows.append(dict(object_id=oid,image_code=o['image_code'],worker_id=o['worker_id'],
            sources=['completion_geometry_role_check'],note='上下端点角色不符合几何约束，待配对阶段核查；不自动判为配对错误'))
    write_csv(OUT/'下一阶段_配对及表示核查.csv',pair_rows)
    package=read(OUT/'同房汇集_Matterport_当前确认快照.json');package['representation_deferred']=geometry_blocked
    dump(OUT/'同房汇集_Matterport_当前确认快照.json',package)
    summary=dict(schema='order_completion_audit_v1',research_images=259,annotations=3152,batches=batches,
        annotation_states=dict(Counter(r['final_state'] for r in audit)),manual_gt_confirmed=sum(o['object_kind']=='gt_manual_revision' and records.get(i,{}).get('status')=='confirmed' for i,o in objects.items()),
        current_confirmation_total=sum(o['object_kind']!='gt_original' and records.get(i,{}).get('status')=='confirmed' for i,o in objects.items()),
        pending_order_ids=candidates,geometry_blocked_ids=geometry_blocked,pairing_deferred=continuation['pairing_deferred'],
        next_stage_total=len(pair_rows),queue_missing=continuation['missing'],
        order_queue_complete=not candidates and not continuation['missing'] and all(r['status']=='confirmed' for r in doc['records'].values()),
        all_annotations_individually_confirmed=all(r['final_state'] in {'confirmed','excluded'} for r in audit),
        full_pairing_and_order_complete=False,formal_analysis_connected=False)
    dump(OUT/'summary.json',summary)
    dump(OUT/'field_contract.json',dict(primary_key='object_id',order_queue_complete='既定GT/明确证据、几何和同图规则闭合且批次无缺漏；不是每份人工确认',
        full_pairing_and_order_complete='配对与表示核查未完，不宣称全部完成',unreviewed='4对默认跳过、用户不召回、未触发均保留未人工确认身份',
        feature_source='冻结共享x改前坐标和初始排列；不拿确认后的改善反推召回阈值',history='前轮双方原件重新归并、77和35逐批完整绑定校验；旧GT记录仅历史'))
    script='window.ORDER_ACCEPTED_REVIEW='+encode(dict(records=doc['records'],snapshots=[{},doc['records']]))+';'
    (OUT/'accepted_35.js').write_text(script,encoding='utf-8')
    page=ROOT/'analysis_results/order_same_image_followup_20260929/index.html';html=page.read_text(encoding='utf-8')
    tag='<script defer src="../order_completion_audit_20260929/accepted_35.js"></script>'
    if tag not in html:page.write_text(html.replace('<script defer src="data.js"></script>','<script defer src="data.js"></script>'+tag),encoding='utf-8')
    return summary


if __name__=='__main__':print(json.dumps(build(),ensure_ascii=False,indent=2))
