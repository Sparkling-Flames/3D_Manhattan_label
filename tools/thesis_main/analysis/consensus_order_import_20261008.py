"""接收冻结工作台的人工排序；变化的节点单列，绝不把旧确认套到新坐标。"""
import json
from .consensus_delivery_20261008 import OUT, read
from .research_artifact_io import write_json
from .union_branch_consensus_20260926 import _ring_key


def source_binding(source):
    return dict(id=source['object_id'],points=source['effective_points'],
                labels=source['effective_point_labels'],links=source['links_zero_based'],
                preprocessing=source['preprocessing'])


def prepare_orders(document, sources, outputs):
    if document.get('schema')!='fusion_order_review_20261008_v1' or document.get('examples_only') is not False:
        raise ValueError('unexpected_order_review_schema')
    catalog={s['object_id']:s for s in sources};live={r['image']:r for r in outputs}
    accepted=[];pending=[]
    for oid,review in document['records'].items():
        source=catalog[oid];code=oid.removeprefix('fusion:');current=live[code]
        if json.loads(review['binding'])!=source_binding(source):raise ValueError('review_source_binding_mismatch:'+code)
        if review['status'] not in ('confirmed','pairing'):raise ValueError('unknown_review_status:'+code)
        order=review['order'];count=len(source['feature_ids'])
        if any(type(i) is not int for i in order) or sorted(order)!=list(range(count)):
            raise ValueError('order_not_a_permutation:'+code)
        if review['status']=='pairing':
            pending.append(dict(image=code,reason='needs_identity_review',note=review['note']));continue
        if current['n']==2:
            pending.append(dict(image=code,reason='two_person_sorting_deferred',note=review['note']));continue
        nodes=current['node_consensus']['nodes']
        if source['feature_ids']!=[n['feature_id'] for n in nodes] or source['points']!=[p for n in nodes for p in n['points']]:
            pending.append(dict(image=code,reason='needs_order_reconfirmation',note='审核快照之后节点身份或坐标变化',
                                submitted_order=order,old_feature_ids=source['feature_ids']));continue
        ids=[source['feature_ids'][i] for i in order]
        accepted.append(dict(image=code,manual_order=ids,
            order_binding=[dict(feature_id=n['feature_id'],points=n['points']) for n in nodes],
            order_changed=_ring_key(ids)!=_ring_key([source['feature_ids'][i] for i in source['default_preview_order']]),
            source='order_workbench/user_order_review_20261008.json',note=review['note']))
    return dict(accepted=accepted,pending=pending,
                unsubmitted=[s['object_id'] for s in sources if s['object_id'] not in document['records']])


def run():
    workbench=OUT/'order_workbench'
    result=prepare_orders(read(workbench/'user_order_review_20261008.json'),
        read(workbench/'sources.json')['objects'],read(OUT/'outputs.json'))
    feedback=read(OUT/'user_followup.json');bycode={r['image']:r for r in feedback['records']}
    for accepted in result['accepted']:
        item=bycode.setdefault(accepted['image'],dict(image=accepted['image']))
        item.update({k:accepted[k] for k in ('manual_order','order_binding','source')})
        item.pop('review_issue',None)
    unresolved=[];result['resolved_by_followup']=[]
    for pending in result['pending']:
        item=bycode.setdefault(pending['image'],dict(image=pending['image']))
        if pending['reason']=='needs_order_reconfirmation' and item.get('order_review_resolution'):
            result['resolved_by_followup'].append(dict(pending,resolution=item['order_review_resolution']))
            continue
        if pending['reason']=='needs_identity_review' and item.get('identity_review_resolution'):
            result['resolved_by_followup'].append(dict(pending,resolution=item['identity_review_resolution']))
            continue
        # A later explicit follow-up may refine the original uploaded issue.
        if item.get('review_issue',{}).get('status')=='incomplete_consensus_review':
            pending['followup']=item['review_issue']
        else:
            item['review_issue']=dict(status=pending['reason'],note=pending['note'])
        unresolved.append(pending)
    result['pending']=unresolved
    feedback['records']=list(bycode.values())
    write_json(OUT/'user_followup.json',feedback)
    write_json(OUT/'order_import.json',result)
    print('accepted',len(result['accepted']),'pending',result['pending'])


if __name__=='__main__':run()
