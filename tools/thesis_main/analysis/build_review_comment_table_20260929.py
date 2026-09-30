"""独立评论表：原话、历史版本、对象绑定与来源位置，不重新解释裁决。"""
from collections import Counter, defaultdict
import json

from tools.thesis_main.data_prep.materialize_current_research_input import load_current_input, rows
from .finalize_review_20260928 import ROOT, read, dump

OUT = ROOT / 'analysis_results/review_comments_20260929'
FIELDS = {'comment', 'raw_comment', 'note', 'cause', 'current_comment', 'current_decision_comment', 'image_comment', 'quote', 'instruction', 'gt_blank_policy'}


def extract(value, objects, images, path='', context=None):
    context = dict(context or {})
    if isinstance(value, dict):
        for k in ('canonical_annotation_id', 'annotation_id', 'object_id', 'image_id', 'reviewer', 'updated_at', 'status', 'verdict', 'source', 'binding', 'view_context', 'cluster_reference', 'event_id', 'category', 'tags'):
            if k in value:
                context[k] = value[k]
        for k, v in value.items():
            pointer = path + '/' + k.replace('~','~0').replace('/','~1')
            nested = dict(context)
            target = k.split(':', 1)[1] if k.startswith(('annotation:', 'image:')) else k
            if target.endswith(':continue'):
                target = target[:-len(':continue')]
            code_matches = [iid for iid, im in images.items() if im.get('image_code') == target] if '-' in target else []
            if len(code_matches) == 1:
                target = code_matches[0]
            if target in objects:
                nested.update(object_id=target, image_id=objects[target]['image_id'])
            elif target in images:
                nested.update(object_id=None, canonical_annotation_id=None, annotation_id=None, image_id=target)
            if k in FIELDS and isinstance(v, str) and v.strip():
                oid = next((context.get(f) for f in ('object_id','canonical_annotation_id','annotation_id') if context.get(f) in objects), None)
                iid = objects[oid]['image_id'] if oid else context.get('image_id')
                yield dict(text=v, field=k, json_pointer=pointer, object_id=oid, image_id=iid,
                    worker_id=objects[oid].get('worker_id') if oid else None,
                    image_code=objects[oid].get('image_code') if oid else images.get(iid,{}).get('image_code'),
                    reviewer=context.get('reviewer'), updated_at=context.get('updated_at'),
                    recorded_status=context.get('status'), recorded_verdict=context.get('verdict'),
                    embedded_source=context.get('source'),
                    original_record_metadata={f:context[f] for f in ('binding','view_context','cluster_reference','event_id','category','tags') if f in context},
                    condition=objects[oid].get('condition') if oid else None,
                    coordinate_source=objects[oid]['source'] if oid else None,
                    binding_status='object_bound' if oid else 'image_bound' if iid in images else 'unresolved',
                    text_role='interpretation_or_derived_context' if any(w in pointer for w in ('interpretation','semantic','clarification','summary')) else 'recorded_text')
            if isinstance(v, (dict,list)):
                yield from extract(v, objects, images, pointer, nested)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from extract(v, objects, images, path+'/'+str(i), context)


def build():
    d = load_current_input(); objects = {o['object_id']:o for o in d['objects']}; images={i['image_id']:i for i in d['images']}
    paths = set()
    for pattern in ('review*/evidence/*.json','order*/evidence/*.json','pairing*/evidence/*.json','x_pairing*/evidence/*.json','final_review_summary_20260929/evidence/*.json'):
        paths.update((ROOT/'analysis_results').glob(pattern))
    for rel in ('analysis_results/review_reconciliation_20260925/commentary.json',
                'analysis_results/review_return_20260927/comments.json',
                'analysis_results/review_closeout_20260928/clarifications.json',
                'tools/thesis_main/analysis/review_return_notes_20260927.json',
                'analysis_results/final_review_summary_20260929/received_orders.json'):
        paths.add(ROOT/rel)
    occurrences=[]; manifest=[]
    for p in sorted(paths):
        rel=p.relative_to(ROOT).as_posix(); before=len(occurrences)
        phase='pairing' if 'pairing' in rel else 'order' if '/order' in rel or 'received_orders' in rel or 'order23' in rel else 'compliance'
        initial = dict(reviewer='user' if p.name in {'user.json','user_review.json'} else 'yizheng') if phase=='compliance' and p.name in {'user.json','user_review.json','yizheng.json','yizheng_review.json'} else {}
        for r in extract(read(p), objects, images, context=initial):
            r.update(source_file=rel, phase=phase, source_kind='frozen_feedback' if '/evidence/' in rel and 'interpretations' not in rel else 'consolidated_or_interpreted',
                source_owner_hint='yizheng' if 'yizheng' in p.name else 'user' if p.stem=='user' else None)
            occurrences.append(r)
        manifest.append(dict(path=rel, comment_occurrences=len(occurrences)-before))
    # 补充最终台账中的聊天更正、旧评论和修复来源；不将自动解释冒充人工原话。
    ledger=ROOT/'analysis_results/review_final_20260928/全量复核.csv'
    for row in rows(ledger):
        oid=row['canonical_annotation_id']
        selected={k:row[k] for k in ('current_comment','current_decision_comment','image_comment')}
        for k in ('review_history','image_review_history','annotation_traits','image_traits','historical_repair_evidence','scene_dimension_evidence','old_comment_interpretations','second_comment_interpretations','continuation_issue','coverage_review','trap_model_evidence'):
            selected[k]=json.loads(row[k])
        for r in extract(selected,objects,images,context=dict(object_id=oid,image_id=row['image_id'])):
            if '/image_' in r['json_pointer'] or r['field']=='image_comment':
                r.update(object_id=None,worker_id=None,binding_status='image_bound')
            r.update(source_file=ledger.relative_to(ROOT).as_posix(), source_row_object_id=oid, phase='compliance',source_kind='consolidated_or_interpreted',source_owner_hint=None)
            occurrences.append(r)
    grouped={}
    for n,r in enumerate(occurrences,1):
        r['occurrence_id']=f'occurrence_{n:06d}'
        # 跨作者同文不自动视为同一次审核；未知作者也不从导出者猜测。
        key=(r['object_id'],r['image_id'],r['reviewer'],r['text_role'],r['text'])
        if r['binding_status']=='unresolved':key+= (r['source_file'],r['json_pointer'])
        group=grouped.setdefault(key,dict(comment_id=f'comment_{len(grouped)+1:06d}',text=r['text'],object_id=r['object_id'],image_id=r['image_id'],
            image_code=r['image_code'],worker_id=r['worker_id'],reviewer=r['reviewer'],text_role=r['text_role'],occurrence_ids=[]))
        group['occurrence_ids'].append(r['occurrence_id'])
    manifest.append(dict(path=ledger.relative_to(ROOT).as_posix(), comment_occurrences=sum(r['source_file']==ledger.relative_to(ROOT).as_posix() for r in occurrences)))
    result=dict(schema='review_comments_v1', purpose='供AI整理合规、排序与配对审核原话；不新增裁决或推断作者。',
        compliance_thread_consulted='01a0c84e-942f-71a1-9ab0-a9f8bb84b70f',
        chat_clarifications=read(ROOT/'analysis_results/review_closeout_20260928/clarifications.json'),
        frozen_cluster_references=[dict(object_id=r['canonical_annotation_id'], references=json.loads(r['frozen_cluster_references'])) for r in rows(ledger) if json.loads(r['frozen_cluster_references'])],
        rules=['comments按对象/图片、明确作者、原文和文本角色聚合，仅供检索；不代表独立审核次数。',
            'occurrences保留每次来源位置、历史状态和时间；previous_round_records/reopened_history不覆盖。',
            'reviewer缺失为null；source_owner_hint只描述文件归属，不证明其中继承记录的作者。',
            '派生解释与记录文字分开，字段名称本身不证明作者；最终资格另读取当前入口。',
            '无法绑定保留unresolved，不猜人员或图片。空白评论不入表，不代表未审。'],
        summary=dict(occurrences=len(occurrences), grouped_comments=len(grouped), phases=dict(Counter(r['phase'] for r in occurrences)),
            binding=dict(Counter(r['binding_status'] for r in occurrences))),
        sources=manifest, comments=list(grouped.values()), occurrences=occurrences)
    OUT.mkdir(exist_ok=True);dump(OUT/'comments.json',result);dump(OUT/'summary.json',result['summary'])
    return result


if __name__=='__main__':
    print(build()['summary'])
