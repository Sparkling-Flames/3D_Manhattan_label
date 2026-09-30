"""接收77份补查，汇总预标注证据，按历史同图改序继续筛查。"""
import csv
import json
from collections import Counter
from pathlib import Path

from .receive_order_results_20260929 import ROOT, OUT as PREVIOUS, freeze_file, build_continuation
from .receive_order_review_20260928 import validate_return
from .order_pattern_recall_20260929 import ring_relation, _read_context
from .build_order_gt_screened_20260928 import NO_RECALL
from .finalize_review_20260928 import read, dump, write_csv
from .build_order_studio_20260926 import encode

OUT=ROOT/'analysis_results/order_model_same_image_20260929'
INPUT=Path('C:/Users/ASUS/Downloads/角点顺序审核(2).json')
# 已逐条阅读原comment；不把检索命中自动升级为“被误导”。
REVIEWED_INFLUENCE_COMMENTS={
    '726df974bcd4c84b':'模型错误的预标注的影响',
    'b62a4df9e1645fe7':'模型的错误预标注的影响',
    '717840fe8221eba6':'模型的错误预标注的影响',
    '28935ccbb578589d':'被模型误导了标注的空间',
}


def validate_followup(doc, sources):
    if doc.get('schema') not in {'order_review_20260928_v2','order_review_20260928_v3'}:
        raise ValueError('unexpected_schema')
    if doc.get('previous_round_records')!={} or doc.get('reopened_history')!=[]:
        raise ValueError('unexpected_followup_history')
    if set(doc['records'])!=set(sources):raise ValueError('followup_coverage_mismatch')
    # 本入口遗漏export_schema而使用v2标签；逐字段绑定仍为完整共享x格式。
    validate_return({**doc,'schema':'order_review_20260928_v3'},sources)


def mentions(value, path=''):
    """仅索引人工评语，不从关键词推出因果结论。"""
    result=[]
    if isinstance(value,dict):
        for key,item in value.items():result.extend(mentions(item,path+'.'+key))
    elif isinstance(value,list):
        for i,item in enumerate(value):result.extend(mentions(item,path+f'[{i}]'))
    elif isinstance(value,str) and ('模型' in value or '预标注' in value) and any(w in value for w in ('误导','影响','带偏','没改','未改','不改','仍错','还是错')):
        result.append(dict(field=path,text=value))
    return result


def build():
    csv.field_size_limit(32*1024*1024)
    OUT.mkdir(exist_ok=True);(OUT/'evidence').mkdir(exist_ok=True)
    source=read(ROOT/'analysis_results/order_followup_20260929/source_objects.json')
    sources={o['object_id']:o for o in source['objects']}
    doc=read(INPUT);validate_followup(doc,sources);freeze_file(INPUT,OUT/'evidence/user_followup.json')
    old=read(PREVIOUS/'received_orders.json');records={**old['records'],**doc['records']}
    origins={**old['origins'],**{i:['user_followup'] for i in doc['records']}}
    objects={o['object_id']:o for o in read(ROOT/'analysis_results/shared_x_baseline_20260928/preprocessed_source.json')['objects']}
    objects.update({o['object_id']:o for o in read(ROOT/'analysis_results/order_gt_screened_20260928/source_objects.json')['objects']})
    validate_return(dict(schema='order_review_20260928_v3',examples_only=False,records=records),objects)
    dump(OUT/'received_orders.json',dict(schema='received_followup_model_audit_v1',records=records,origins=origins,
        input_schema=doc['schema'],schema_adapter='v2_label_only_exact_shared_x_binding_validated',previous_received_path=str(PREVIOUS/'received_orders.json')))
    changes=[]
    for oid,r in doc['records'].items():
        o=objects[oid]
        changes.append(dict(object_id=oid,image_id=o['image_id'],image_code=o['image_code'],worker_id=o['worker_id'],
            status=r['status'],change=ring_relation(list(range(len(o['links_zero_based']))),r['order']),order=r['order']))
    write_csv(OUT/'77份补查接收.csv',changes)
    # 原77份入口显示已接收结果，仍保留未知的新本地修改。
    script='window.ORDER_ACCEPTED_REVIEW='+encode(dict(records=doc['records'],snapshots=[{},doc['records']]))+';'
    (OUT/'accepted_followup.js').write_text(script,encoding='utf-8')
    page=ROOT/'analysis_results/order_followup_20260929/index.html'
    html=page.read_text(encoding='utf-8');tag='<script defer src="../order_model_same_image_20260929/accepted_followup.js"></script>'
    if tag not in html:page.write_text(html.replace('<script defer src="data.js"></script>','<script defer src="data.js"></script>'+tag),encoding='utf-8')
    with (ROOT/'analysis_results/review_final_20260928/全量复核.csv').open(encoding='utf-8-sig') as f:ledger=list(csv.DictReader(f))
    evidence=[]
    for row in ledger:
        oid=row['canonical_annotation_id']
        fields={k:json.loads(row[k] or '{}') for k in ('annotation_traits','trap_model_evidence','review_history','old_comment_interpretations')}
        fields.update({k:row[k] for k in ('current_comment','current_decision_comment','image_comment')})
        refs=mentions(fields)
        explicit_comment=REVIEWED_INFLUENCE_COMMENTS.get(oid,'')
        if explicit_comment and fields['annotation_traits'].get('comment')!=explicit_comment:
            raise ValueError('reviewed_comment_changed:'+oid)
        tags=fields['annotation_traits'].get('tags',[])
        if row['model_edit_status']!='unchanged_coordinates' and not refs and not any('model' in t for t in tags):continue
        evidence.append(dict(object_id=oid,image_id=row['image_id'],image_code=row['image_code'],worker_id=row['worker_id'],
            condition=row['condition'],cleaning_disposition=row['cleaning_disposition'],worker_quality_gate=row['worker_quality_gate'],
            model_edit_status=row['model_edit_status'],trap_status=row['trap_status'],trap_origin=row['trap_origin'],
            annotation_tags=tags,comment_evidence=refs,model_evidence=fields['trap_model_evidence'],
            user_reported_model_influence=bool(explicit_comment),influence_comment=explicit_comment,
            influence_comment_field='annotation_traits.comment' if explicit_comment else '',
            evidence_interpretation='人工评语检索线索，非自动因果裁决',order_review_status=records.get(oid,{}).get('status','unreviewed'),
            scene_doorway_status=row['scene_doorway_status'],scene_oos_status=row['scene_oos_status']))
    write_csv(OUT/'预标注未改动与影响评语汇总.csv',evidence)
    write_csv(OUT/'用户comment明确记录_模型误导影响.csv',[r for r in evidence if r['user_reported_model_influence']])
    _,_,history=_read_context();changed_by_image={};prior_changed_images=set()
    for oid,o in objects.items():
        if o['object_kind']!='annotation' or o['preprocessing_status']!='ready':continue
        seq=list(range(len(o['links_zero_based'])))
        events=[('current',records[oid])] if oid in records else []
        events.extend(('historical:'+e['reviewer'],e['record']) for e in history.get(oid,[]))
        changed=[dict(object_id=oid,source=name) for name,r in events if r['status']=='confirmed' and ring_relation(seq,r['order'])=='adjacency_changed']
        if changed:changed_by_image.setdefault(o['image_id'],[]).extend(changed)
        prior_events=([old['records'][oid]] if oid in old['records'] else [])+[e['record'] for e in history.get(oid,[])]
        if any(r['status']=='confirmed' and ring_relation(seq,r['order'])=='adjacency_changed' for r in prior_events):prior_changed_images.add(o['image_id'])
    audits=[]
    for o in objects.values():
        if o['object_kind']!='annotation':continue
        oid=o['object_id'];events=[e for e in changed_by_image.get(o['image_id'],[]) if e['object_id']!=oid]
        state=records.get(oid,{}).get('status','unreviewed')
        reason=('no_other_same_image_change' if not events else 'excluded' if o.get('cleaning_disposition') in {'excluded_by_review','historical_not_accepted'}
            else 'already_confirmed' if state=='confirmed' else 'pairing_deferred' if state=='pairing' or o['preprocessing_status']!='ready'
            else 'user_no_recall_image' if o['image_code'] in NO_RECALL else 'four_pairs_default_skip' if len(o['links_zero_based'])<=4 else 'candidate')
        audits.append(dict(object_id=oid,image_id=o['image_id'],image_code=o['image_code'],worker_id=o['worker_id'],
            current_status=state,reason=reason,other_changed_evidence=events,
            scene_doorway_status=o.get('scene_doorway_status'),scene_oos_status=o.get('scene_oos_status')))
    candidates=[r['object_id'] for r in audits if r['reason']=='candidate']
    write_csv(OUT/'同图历史改序_全量筛查.csv',audits)
    if candidates:write_csv(OUT/'同图历史改序_新增候选.csv',[r for r in audits if r['reason']=='candidate'])
    continuation=build_continuation(objects,records,origins,candidates,out=OUT,queue_name='order_same_image_followup_20260929')
    summary=dict(input_records=len(doc['records']),input_statuses=dict(Counter(r['status'] for r in doc['records'].values())),
        followup_changes=dict(Counter(r['change'] for r in changes)),model_status_full_population=dict(Counter(r['model_edit_status'] for r in ledger)),
        model_evidence_rows=len(evidence),unchanged_rows=sum(r['model_edit_status']=='unchanged_coordinates' for r in evidence),
        comment_mention_rows=sum(bool(r['comment_evidence']) for r in evidence),same_image_changed_images=len(changed_by_image),
        user_comment_explicit_influence_rows=sum(r['user_reported_model_influence'] for r in evidence),
        same_image_screen_counts=dict(Counter(r['reason'] for r in audits)),continuation=continuation,
        prospective_77_by_prior_same_image={label:dict(reviewed=sum((r['image_id'] in prior_changed_images)==flag for r in changes),
            changed=sum((r['image_id'] in prior_changed_images)==flag and r['change']=='adjacency_changed' for r in changes))
            for label,flag in [('previously_changed_image',True),('no_previous_change_image',False)]},
        hypothesis='同图历史改序为补查线索，尚无独立样本证实提高概率；排除本对象自身作为同图证据',formal_analysis_connected=False)
    dump(OUT/'summary.json',summary)
    dump(OUT/'field_contract.json',dict(primary_key='object_id',comments='仅逐条读过且明确写模型误导/影响的用户comment计入user_reported_model_influence；保留原文和路径。其他关键词只检索，不自动标为误导',
        unchanged='原台账比较初始预标注与原始提交坐标；不等于没有检查、顺序未改或被模型误导',
        same_image='其他标注存在历史真实环邻接改动；固定点对identity为比较基线，起点/反向等价不算',
        grouping='既有physical_same_supported分组；未知逐图保留；当前确认快照complete=false'))
    return summary


if __name__=='__main__':print(json.dumps(build(),ensure_ascii=False,indent=2))
