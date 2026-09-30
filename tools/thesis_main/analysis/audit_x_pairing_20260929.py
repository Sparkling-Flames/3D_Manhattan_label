"""全量配对追溯与x配对候选审计；不覆写冻结源、不自动迁移已确认环序。"""
import csv
import json
from collections import Counter
from pathlib import Path
import numpy as np
from .finalize_review_20260928 import read,dump,write_csv
from .receive_order_results_20260929 import ROOT,freeze_file
from .paired_split_research.study import infer_links
from .review_reconciliation_audit_20260925 import verify_raw

OUT=ROOT/'analysis_results/x_pairing_audit_20260929'


def pairset(links):return {tuple(sorted(p)) for p in links or []}


def x_adjacent(points, locked=()):
    """周期x相邻配对候选，不用地平线猜角色；y较小者为上端点。非人工真值。"""
    p=np.asarray(points,float);used=[]
    if p.ndim!=2 or p.shape[1]!=2 or not len(p) or not np.isfinite(p).all():
        if locked:raise ValueError('locked_without_points')
        return dict(status='no_effective_points',pairs=None)
    for a,b in locked:
        if type(a) is not int or type(b) is not int or not (0<=a<len(p) and 0<=b<len(p)) or a==b or a in used or b in used or p[a,1]>=p[b,1]:raise ValueError('invalid_locked_pair')
        used.extend([a,b])
    ids=sorted(set(range(len(p)))-set(used),key=lambda i:(p[i,0]%1024,i))
    if len(ids)%2:return dict(status='odd_remaining_points',pairs=None)
    if not ids:return dict(status='explicit_complete',pairs=list(locked),max_dx=0,
        same_horizon_side_pairs=[q for q in locked if (p[q[0],1]-255.5)*(p[q[1],1]-255.5)>0])
    options=[]
    for shift in (0,1):
        order=ids[shift:]+ids[:shift]
        pairs=[sorted(order[i:i+2],key=lambda j:p[j,1]) for i in range(0,len(order),2)]
        if any(p[a,1]==p[b,1] for a,b in pairs):continue
        dx=[abs((p[a,0]-p[b,0]+512)%1024-512) for a,b in pairs]
        options.append((sum(dx),pairs,max(dx)))
    if not options:return dict(status='equal_y_unresolved',pairs=None)
    options.sort(key=lambda x:x[0]);best=options[0]
    if len(options)>1 and abs(best[0]-options[1][0])<1e-8 and pairset(best[1])!=pairset(options[1][1]):return dict(status='cyclic_x_tie',pairs=None)
    pairs=list(locked)+best[1]
    return dict(status='wide_x_candidate' if best[2]>=51.2 else 'x_candidate',pairs=pairs,max_dx=float(best[2]),cost=float(best[0]),
        same_horizon_side_pairs=[q for q in pairs if (p[q[0],1]-255.5)*(p[q[1],1]-255.5)>0])


def build():
    csv.field_size_limit(32*1024*1024);OUT.mkdir(exist_ok=True);(OUT/'evidence').mkdir(exist_ok=True)
    allobjects=read(ROOT/'analysis_results/shared_x_baseline_20260928/preprocessed_source.json')['objects']
    objects={o['object_id']:o for o in allobjects if o['object_kind']=='annotation'}
    base={r['canonical_annotation_id']:r for r in read(ROOT/'analysis_results/consensus_research_20260923/inputs/annotations.jsonl.gz')}
    pairing=read(Path('C:/Users/ASUS/Downloads/上下点配对审核.json'))
    expected={o['object_id']:o for o in read(ROOT/'analysis_results/pairing_review_20260929/source_objects.json')['objects']}
    if pairing.get('schema')!='pairing_only_review_20260929_v1' or pairing.get('scope')!='pairing_only' or pairing.get('order_confirmed') is not False or set(pairing['records'])!=set(expected):raise ValueError('pairing_return_scope')
    for oid,r in pairing['records'].items():
        o=expected[oid]
        if json.loads(r['binding'])!=dict(object_id=oid,points=o['before_preprocessing_points'],labels=o['point_labels'],coordinate_source='before_preprocessing_points'):raise ValueError('pairing_binding:'+oid)
        if r['status'] not in {'checked','paired','draft','deferred'} or r['order_confirmed'] is not False:raise ValueError('pairing_status:'+oid)
        x_adjacent(o['before_preprocessing_points'],r['pairs'])
    freeze_file(Path('C:/Users/ASUS/Downloads/上下点配对审核.json'),OUT/'evidence/pairing_return.json')
    orders=read(ROOT/'analysis_results/order_completion_audit_20260929/received_orders.json')['records']
    cache={};rows=[];received=[]
    for oid,o in objects.items():
        src=o['source'];path=src['path']
        if path not in cache:cache[path]={t['id']:t for t in read(ROOT/path)}
        task=cache[path][src['task']];ann=next(a for a in task['annotations'] if a['id']==src['annotation'])
        verify_raw(src,o['original_export_points'],task,ann)
        p=np.asarray(o['before_preprocessing_points'],float);old=o['links_zero_based'];original=base[oid]
        adjacent=x_adjacent(p)
        if adjacent['status']=='no_effective_points':links,reason,meta=None,'no_effective_points',{}
        else:
            up=np.flatnonzero(p[:,1]<255.5);dn=np.flatnonzero(p[:,1]>255.5)
            links,reason,meta=infer_links(p,up,dn) if len(up)+len(dn)==len(p) else (None,'on_horizon',{})
        horizon=links.tolist() if links is not None else None
        difference=('unavailable_both' if old is None and adjacent['pairs'] is None else 'previously_unavailable_x_candidate' if old is None else
            'x_unresolved' if adjacent['pairs'] is None else 'same_pairs' if pairset(old)==pairset(adjacent['pairs']) else 'different_pairs')
        identical=old==original['links_zero_based'] and o['before_preprocessing_points']==original['effective_points_1024x512']
        r=dict(object_id=oid,image_code=o['image_code'],worker_id=o['worker_id'],cleaning_disposition=o['cleaning_disposition'],
            raw_verified=True,old_pairing_basis=o['pairing_basis'],same_as_20260923_source=identical,
            old_pairing_status=original['pairing_status'],old_links=old,x_candidate=adjacent['pairs'],x_status=adjacent['status'],
            x_max_dx=adjacent.get('max_dx'),same_horizon_side_pairs=adjacent.get('same_horizon_side_pairs',[]),
            horizon_x_status=reason,horizon_x_pairs=horizon,comparison=difference,
            horizon_vs_adjacent='same' if horizon is not None and pairset(horizon)==pairset(adjacent['pairs']) else 'different_or_unavailable',
            order_status=orders.get(oid,{}).get('status','unreviewed'),
            order_binding_affected=orders.get(oid,{}).get('status')=='confirmed' and difference=='different_pairs',
            scene_doorway_status=o['scene_doorway_status'],scene_oos_status=o['scene_oos_status'])
        rows.append(r)
        if oid in pairing['records']:
            review=pairing['records'][oid];proposal=x_adjacent(p,review['pairs'])
            received.append(dict(object_id=oid,image_code=o['image_code'],worker_id=o['worker_id'],status=review['status'],
                review_mode=review.get('review_mode','legacy_full_pairing'),explicit_pairs=review['pairs'],note=review['note'],
                implicit_rule='未修改部分按x重新配对（用户本轮澄清）',candidate=proposal,
                case_recheck_requested=o['image_code']=='uNb9QFRL6hY-36',applied=False,order_confirmed=False))
    write_csv(OUT/'全3152份_配对来源及x对照.csv',rows)
    write_csv(OUT/'差异与不可配对明细.csv',[r for r in rows if r['comparison']!='same_pairs'])
    write_csv(OUT/'uNb36_逐人员追溯.csv',[r for r in rows if r['image_code']=='uNb9QFRL6hY-36'])
    dump(OUT/'接收34份_明确配对及剩余x候选.json',dict(schema='pairing_return_x_interpretation_v1',records=received,applied=False))
    detail=[]
    for item in received:
        oid=item['object_id'];o=objects[oid];p=np.asarray(o['before_preprocessing_points'],float)
        note=item['note'];candidate=item['candidate'];base_candidate=x_adjacent(p)
        explicit_oos_uncalculable=note=='这属于oos,这无法配对就认为是无法计算'
        explicit_oos_pairing_ok=note=='配对没问题,这是这图是oos导致很奇怪'
        extra=pairset(candidate['pairs'])-pairset(item['explicit_pairs'])
        differing=pairset(item['explicit_pairs'])-pairset(base_candidate['pairs'])
        status=('user_oos_uncalculable' if explicit_oos_uncalculable else 'user_oos_pairing_ok' if explicit_oos_pairing_ok
            else 'point_edit_pending' if item['status']=='deferred' else 'pairing_candidate_unresolved' if candidate['pairs'] is None
            else 'manual_vs_x_difference' if differing else 'horizon_role_limit' if candidate.get('same_horizon_side_pairs')
            else 'x_completion_required' if extra else 'explicit_complete')
        detail.append(dict(object_id=oid,image_code=o['image_code'],worker_id=o['worker_id'],review_result=status,note=note,
            explicit_pairs_1based=[[a+1,b+1] for a,b in item['explicit_pairs']],
            remaining_x_pairs_1based=[[a+1,b+1] for a,b in candidate['pairs'] or [] if tuple(sorted((a,b))) in extra],
            same_horizon_side_pairs_1based=[[a+1,b+1] for a,b in candidate.get('same_horizon_side_pairs',[])],
            manual_vs_x_pairs_1based=[[a+1,b+1] for a,b in sorted(differing)],
            all_pair_max_dx=max((abs((p[a,0]-p[b,0]+512)%1024-512) for a,b in candidate['pairs'] or []),default=None),
            old_has_pairs=bool(o['links_zero_based']),candidate_applied=False))
    write_csv(OUT/'34份逐项复核_只按明确OOS备注豁免.csv',detail)
    summary=dict(annotations=len(rows),images=len({o['image_id'] for o in objects.values()}),raw_verified=sum(r['raw_verified'] for r in rows),
        comparisons=dict(Counter(r['comparison'] for r in rows)),retained_comparisons=dict(Counter(r['comparison'] for r in rows if r['cleaning_disposition']=='retained')),
        old_identical_count=sum(r['same_as_20260923_source'] for r in rows),affected_confirmed_orders=sum(r['order_binding_affected'] for r in rows),
        affected_confirmed_ids=[r['object_id'] for r in rows if r['order_binding_affected']],
        accepted_return_status=dict(Counter(r['status'] for r in received)),return_candidate_status=dict(Counter(r['candidate']['status'] for r in received)),
        nonexcluded_comparisons=dict(Counter(r['comparison'] for r in rows if r['cleaning_disposition'] not in {'excluded_by_review','historical_not_accepted'})),
        returned_detail_states=dict(Counter(r['review_result'] for r in detail)),
        raw_mutation=False,automatic_pairing_applied=False,
        completion_caveat='之前零待审仅在旧配对基线上成立；x重配发生身份变化时必须重新核查共享x与排序绑定')
    dump(OUT/'summary.json',summary)
    dump(OUT/'field_contract.json',dict(primary_key='object_id',x_candidate='按周期x排序，比较两种相邻配对起点，最小总周期dx；y小者为上点；仅诊断候选，不证明语义正确',
        horizon_reference='旧规则：255.5中线上下分类，周期x匈牙利唯一匹配，51.2px边界及平局拒绝',
        known_limitations='相邻x候选可能配到同侧语义点；极密集/同x/遮挡仍需语义检查；候选差异不是错误数量',
        pairing_return='局部明确配对优先，剩余x候选独立保存；deferred不应用；uNb36用户明确要求重核',
        old_completion='1272确认保留原绑定证据；换配对不静默复用旧固定点对ID或确认环序'))
    return summary


if __name__=='__main__':print(json.dumps(build(),ensure_ascii=False,indent=2))
