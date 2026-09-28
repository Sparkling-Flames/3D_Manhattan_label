"""原始GT主筛的顺序工作台；复用共享x源和双人确认，不修改采集真源。"""
from __future__ import annotations

import copy
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from .build_order_studio_20260926 import ROOT, OUT as OLD, encode
from .receive_order_review_20260928 import make_variant, validate_return
from .finalize_review_20260928 import read, dump, write_csv
from .audit_supervisor_gt_sensitivity_20260922 import is_substantive_revision
from .materialize_model_gt_threshold_screen import _read_test_gt
from .paired_split_research.study import infer_links
from .review_reconciliation_audit_20260925 import verify_raw, same
from .shared_x_reanalysis_20260922 import shared_x
from tools.label_studio.panorama_studio.build import data_image

OUT = ROOT/'analysis_results/order_gt_screened_20260928'
RECEIVED = ROOT/'analysis_results/order_same_room_review_20260928'
NO_RECALL = {'B6ByNegPMKs-40','X7HyMhZNoso-05'}


def screen_gt_ring(xs):
    x=np.asarray(xs,float)
    if x.ndim!=1 or len(x)<3 or not np.isfinite(x).all():
        raise ValueError('invalid_gt_ring')
    x=x%1024
    monotonic=any(np.all(np.diff(np.roll(v,-int(np.argmin(v))))>=-1e-6) for v in (x,x[::-1]))
    ties=bool(np.any(np.diff(np.sort(x))<=1e-6))
    reason='local_backtracking' if not monotonic else 'same_x_pairs' if ties else 'cyclic_monotonic'
    return dict(candidate=not monotonic or ties,reason=reason,same_x_pairs=ties,source_pair_x=x.tolist())


def queue_state(obj, prior, gt_risk, explicit):
    if obj['object_kind']=='gt_original':
        return 'reference_only'
    if obj.get('cleaning_disposition') in {'excluded_by_review','historical_not_accepted'}:
        return 'excluded'
    if obj['preprocessing_status']!='ready' or prior.get('status')=='pairing':
        return 'pairing_deferred'
    if prior.get('status')=='confirmed':
        return 'confirmed'
    if obj['object_kind']=='gt_manual_revision':
        return 'pending'
    if obj['image_code'] in NO_RECALL:
        return 'not_selected'
    return 'pending' if gt_risk or explicit else 'not_selected'


def ordered_layout(obj, order):
    links=obj['links_zero_based']; points=obj['preprocessed_points']
    if (points is None or links is None or any(type(i) is not int for i in order)
            or sorted(order)!=list(range(len(links)))):
        raise ValueError('invalid_confirmed_order')
    indices=[j for i in order for j in links[i]]
    if sorted(indices)!=list(range(len(points))):
        raise ValueError('invalid_pair_identity')
    return dict(object_id=obj['object_id'],object_kind=obj['object_kind'],image_id=obj['image_id'],source=obj['source'],
        preprocessing=obj['preprocessing'],coordinate_frame='1024x512',closed=True,
        ordered_source_pair_indices=list(order),ordered_source_point_indices=indices,
        ordered_source_point_labels=[obj['point_labels'][j] for j in indices],
        points_1024x512=[points[j] for j in indices],links_zero_based=[[i,i+1] for i in range(0,len(points),2)])


def gt_object(iid, code, source, points, kind, master):
    oid='gt:'+iid+':'+source
    if oid in master:
        obj=master[oid]
        if not same(points,obj['original_export_points']):
            raise ValueError('gt_source_changed:'+oid)
        return copy.deepcopy(obj)
    p=np.asarray(points,float)
    if kind=='gt_original':
        if len(p)%2 or not np.all(p[::2,1]<255.5) or not np.all(p[1::2,1]>255.5) or not np.allclose(p[::2,0],p[1::2,0],atol=1e-7,rtol=0):
            raise ValueError('source_gt_pair_contract:'+oid)
        links=np.arange(len(p)).reshape(-1,2);basis='source_alternating_pairs'
    else:
        up=np.flatnonzero(p[:,1]<255.5);dn=np.flatnonzero(p[:,1]>255.5)
        links,basis,_=infer_links(p,up,dn) if len(up)+len(dn)==len(p) else (None,'point_on_horizon',{})
    after=shared_x(p,links).tolist() if links is not None else None
    return dict(object_id=oid,object_kind=kind,image_id=iid,image_code=code,source=source,
        original_export_points=p.tolist(),before_preprocessing_points=p.tolist(),preprocessed_points=after,
        preprocessing_status='ready' if after is not None else 'unavailable',
        links_zero_based=links.tolist() if links is not None else None,pairing_basis=basis,
        point_labels=['GT p'+str(i+1) for i in range(len(p))],preprocessing='shared_x_periodic_shortest_arc_v1')


def build():
    csv.field_size_limit(32*1024*1024)
    with (ROOT/'analysis_results/review_final_20260928/全量复核.csv').open(encoding='utf-8-sig') as f:
        ledger={r['canonical_annotation_id']:r for r in csv.DictReader(f)}
    master={o['object_id']:o for o in read(ROOT/'analysis_results/shared_x_baseline_20260928/preprocessed_source.json')['objects']}
    received=read(RECEIVED/'received_orders.json'); prior=received['records']
    validate_return(dict(schema='order_review_20260928_v3',examples_only=False,records=prior),master)
    registry=read(ROOT/'analysis_results/consensus_research_20260923/inputs/room_registry.json.gz')
    meta={r['image_id']:r for r in registry['images']}
    room={iid:r['candidate_id'] for r in registry['candidates'] if r['physical_same_supported'] for iid in r['image_ids']}
    codes={iid:f"{m['building']}-{m['number']:02d}" for iid,m in meta.items()}
    study={r['image_id'] for r in ledger.values()}
    if len(study)!=259 or len(ledger)!=3152:
        raise ValueError('research_population_changed')
    manual=_read_test_gt(ROOT/'export_label/groudTruth.json')
    originals={}; risks={}; gt_audit=[]; revised=[]
    for split in ('test','valid'):
        for path in sorted((ROOT/f'data/mp3d_layout/{split}/label_cor').glob('*.txt')):
            iid=path.stem;raw=np.loadtxt(path);code=codes[iid];source=path.relative_to(ROOT).as_posix()
            originals[iid]=gt_object(iid,code,source,raw,'gt_original',master)
            risks[iid]=screen_gt_ring(raw[::2,0])
            change='no_manual_copy'
            if iid in manual:
                b=manual[iid]
                if is_substantive_revision(raw,b):
                    change='point_count_changed' if raw.shape!=b.shape else 'coordinates_changed'
                    revised.append(gt_object(iid,code,'export_label/groudTruth.json',b,'gt_manual_revision',master))
                else:
                    change='roundtrip_only' if np.allclose(raw,b,atol=1e-3,rtol=0) else 'order_only'
            gt_audit.append(dict(image_id=iid,image_code=code,in_research=iid in study,original_source=source,
                **risks[iid],manual_change=change,original_pair_count=len(raw)//2,
                manual_pair_count=len(manual[iid])//2 if iid in manual else None))
    if len(revised)!=30 or Counter(r['manual_change'] for r in gt_audit)['order_only']!=1:
        raise ValueError('manual_gt_revision_inventory_changed')
    with (ROOT/'analysis_results/order_candidates_20260928/全量排序初筛.csv').open(encoding='utf-8-sig') as f:
        explicit={r['object_id'] for r in csv.DictReader(f) if r['object_kind']=='annotation' and json.loads(r['explicit_order_evidence'])}
    explicit.update(oid for oid,r in prior.items() if master[oid]['object_kind']=='annotation'
                    and r['status']=='confirmed' and r['order']!=list(range(len(r['order']))))
    objects=[copy.deepcopy(o) for o in master.values() if o['object_kind']=='annotation']+revised
    inventory=[]; display=defaultdict(list); deferred=[]; exports={}
    for o in objects:
        oid=o['object_id'];iid=o['image_id'];o['image_code']=codes[iid]
        prev=prior.get(oid,{})
        state=queue_state(o,prev,risks[iid]['candidate'],oid in explicit)
        reasons=[]
        if risks[iid]['candidate']:reasons.append('original_gt:'+risks[iid]['reason'])
        if oid in explicit:reasons.append('explicit_person_order_evidence')
        if o['object_kind']=='gt_manual_revision':reasons.append('manual_gt_substantive_revision')
        if prev:reasons.append('received:'+prev['status'])
        if o.get('cleaning_disposition') in {'excluded_by_review','historical_not_accepted'}:reasons.append(o['cleaning_disposition'])
        if o['preprocessing_status']!='ready':reasons.append(o['pairing_basis'])
        if codes[iid] in NO_RECALL and o['object_kind']=='annotation':reasons.append('user_no_recall_image')
        if not reasons:reasons.append('original_gt_cyclic_monotonic_no_explicit_order_issue')
        item=dict(object_id=oid,image_id=iid,image_code=codes[iid],object_kind=o['object_kind'],
            worker_id=o.get('worker_id',''),state=state,reasons=reasons,prior_status=prev.get('status','unreviewed'),
            cleaning_disposition=o.get('cleaning_disposition','reference'),worker_quality_gate=o.get('worker_quality_gate',''),
            preprocessing_status=o['preprocessing_status'],note=prev.get('note',''))
        inventory.append(item)
        if state=='pairing_deferred':deferred.append(item)
        if state not in {'pending','confirmed'}:continue
        # 显示和保存始终绑定当前有效点及已冻结的共享x计算结果。
        if not np.array_equal(shared_x(o['before_preprocessing_points'],o['links_zero_based']),o['preprocessed_points']):
            raise ValueError('shared_x_drift:'+oid)
        if o['object_kind']=='annotation':
            row=ledger[oid]
            if o['before_preprocessing_points']!=json.loads(row['effective_points_1024x512'] or 'null'):
                raise ValueError('current_effective_points_changed:'+oid)
            src=o['source'];path=src['path']
            if path not in exports:exports[path]={t['id']:t for t in read(ROOT/path)}
            task=exports[path][src['task']];anns=[a for a in task['annotations'] if a['id']==src['annotation']]
            if len(anns)!=1:raise ValueError('raw_annotation_identity:'+oid)
            verify_raw(src,o['original_export_points'],task,anns[0])
        variant=make_variant(o,ledger)
        if 'geometry' not in variant:raise ValueError('order_geometry_unavailable:'+oid)
        source=variant['source'];source.update(image_id=iid,provenance=o['source'],selection_reasons=reasons,queue_state=state)
        source['default_preview_order']=sorted(range(len(o['links_zero_based'])),key=lambda i:(o['preprocessed_points'][o['links_zero_based'][i][0]][0],i)) if o['object_kind']=='gt_manual_revision' else list(range(len(o['links_zero_based'])))
        display[iid].append(variant)
    old_source=read(OLD/'preprocessed_source.json')['objects']
    old_slots={iid:i+1 for i,iid in enumerate(dict.fromkeys(o['image_id'] for o in old_source))}
    cases=[];images={}
    # 沿用原图号作为提示，不用压缩后队列号冒充原41–44号。
    for iid in sorted(display,key=lambda i:(old_slots.get(i,9999),codes[i])):
        variants=sorted(display[iid],key=lambda v:(v['source']['object_kind']!='annotation',v['source'].get('worker_id') or '',v['source']['object_id']))
        ref=make_variant(originals[iid],ledger);ref['source'].update(image_id=iid,provenance=originals[iid]['source'],review_read_only=True)
        variants.append(ref)
        cases.append(dict(image_id=iid,title=codes[iid],room_id=room.get(iid,''),original_slot=old_slots.get(iid),
            category='GT筛选 · 已确认直接沿用',variants=variants,annotation_ids=[v['source']['object_id'] for v in variants]))
        images[len(cases)-1]=dict(original=data_image(ROOT/meta[iid]['path'],texture=True))
    catalog=[]
    for oid in prior:
        o=master[oid]
        catalog.append(dict(object_id=oid,points=o['preprocessed_points'],effective_points=o['preprocessed_points'],
            effective_point_labels=o['point_labels'],links_zero_based=o['links_zero_based'],
            before_preprocessing_points=o['before_preprocessing_points'],preprocessing=o['preprocessing']))
    summary=dict(schema='gt_screened_order_review_v1',research_images=259,screened_annotations=3152,
        gt_risk_research_images=sum(risks[i]['candidate'] for i in study),
        annotation_states=dict(Counter(r['state'] for r in inventory if r['object_kind']=='annotation')),
        manual_gt_states=dict(Counter(r['state'] for r in inventory if r['object_kind']=='gt_manual_revision')),
        manual_gt_substantive_changes=30,manual_gt_order_only=1,original_gt_review_tasks=0,
        pending=sum(r['state']=='pending' for r in inventory),confirmed=sum(r['state']=='confirmed' for r in inventory),
        pending_images=len({r['image_id'] for r in inventory if r['state']=='pending'}),display_images=len(cases),
        pairing_deferred=len(deferred),formal_analysis_connected=False)
    dataset=dict(cases=cases,counts=dict(cases=len(cases),variants=sum(len(c['variants']) for c in cases)),
        manifest=dict(contract_version='consensus_research_20260923_v1',export_schema='order_review_20260928_v3',
            formal_data_connected=False,examples_only=False,review_round='gt_screened_20260928'),summary=summary)
    OUT.mkdir(exist_ok=True)
    (OUT/'data.js').write_text('window.STUDIO_IMAGES='+encode(images)+';Object.values(window.STUDIO_IMAGES).forEach(i=>i.texture=i.original);window.STUDIO_DATA='+encode(dataset)+';window.ORDER_REVIEW_SEED='+encode(prior)+';window.ORDER_HISTORY_SOURCES='+encode(catalog)+';',encoding='utf-8')
    page=(OLD/'index.html').read_text(encoding='utf-8')
    for name in ('studio.js','studio.css','three.min.js','OrbitControls.js'):
        page=page.replace('"'+name+'"','"../order_studio_20260926/'+name+'"')
    for suffix in ('js','css'):
        page=page.replace('"order_studio.'+suffix+'"','"../../tools/thesis_main/analysis/order_studio_20260926.'+suffix+'"')
    page=page.replace('</head>','<script defer src="../../tools/thesis_main/analysis/order_gt_screened_20260928.js"></script>\n</head>')
    (OUT/'index.html').write_text(page,encoding='utf-8')
    lookup={o['object_id']:o for o in objects}
    confirmed=[ordered_layout(lookup[r['object_id']],prior[r['object_id']]['order']) for r in inventory if r['state']=='confirmed']
    dump(OUT/'confirmed_layouts.json',dict(schema='matterport_connection_order_v1',objects=confirmed,formal_analysis_connected=False))
    dump(OUT/'summary.json',summary)
    dump(OUT/'received_orders.json',received)
    dump(OUT/'source_objects.json',dict(schema='order_gt_screened_sources_v1',objects=[lookup[r['object_id']] for r in inventory if r['state'] in {'pending','confirmed'}],
         supplemental_gt_scope='30份人工修订中不在原共享x研究范围者仅在本复核层补充，不扩展正式研究样本'))
    write_csv(OUT/'逐对象筛选.csv',inventory);write_csv(OUT/'原始与人工GT审计.csv',gt_audit);write_csv(OUT/'配对问题_后续统一处理.csv',deferred)
    dump(OUT/'field_contract.json',dict(schema=summary['schema'],primary_key='object_id',
        screening='全259图；GT循环起点/反向不敏感；局部回退或同x候选，加明确人员顺序例外；不采用稠密/锐角单项召回',
        queue_states=['excluded','pairing_deferred','not_selected','pending','confirmed'],
        default_preview_order='固定点对索引的零基排列；仅人工修订GT初始按共享x升序；不属于源绑定，已有确认优先',
        history='双人原件和派生配对解释保留；确认默认锁定，可逐对象撤销后编辑，保留排列和撤销前记录；原始GT始终只读且不计任务',
        review_rounds='previous：当前确认与ORDER_REVIEW_SEED原记录各绑定/状态/排列/备注/原因/时间字段一致；current：新增或更新的确认，不自动推断误点',
        review_export_extensions='previous_round_records为原审核快照；reopened_history为本页撤销前记录；v3 records继续表示当前状态',
        binding='order_review_20260928_v3沿用object_id/points/labels/links/preprocessing；未知身份或冲突拒绝覆盖',
        connection_export='matterport_connection_order_v1：依确认环序逐对上/下交替点数组，末对连首对；保存原点和点对索引',
        eligibility='队列选择不更改清洗和分析资格；未筛入不等于人工验收',raw_mutation=False))
    return summary


if __name__=='__main__':
    print(json.dumps(build(),ensure_ascii=False,indent=2))
