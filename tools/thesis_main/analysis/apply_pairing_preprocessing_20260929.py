"""接收完整配对，原始坐标直接共享x，独立生成新基线及排序续审。"""
import copy
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from .finalize_review_20260928 import read, dump, write_csv
from .receive_order_results_20260929 import ROOT, freeze_file
from .shared_x_reanalysis_20260922 import shared_x
from .audit_x_pairing_20260929 import x_adjacent
from .receive_order_review_20260928 import make_variant, validate_return
from .build_order_gt_screened_20260928 import NO_RECALL
from .build_order_studio_20260926 import encode
from tools.label_studio.panorama_studio.build import data_image

OUT=ROOT/'analysis_results/pairing_applied_20260929'
QUEUE=ROOT/'analysis_results/order_after_pairing_20260929'
INPUT=Path('C:/Users/ASUS/Downloads/补齐配对复核.json')


def jsdata(path):
    return json.loads(path.read_text(encoding='utf-8').removeprefix('window.PAIRING_DATA=').removesuffix(';'))


def validate_received(doc, cases):
    if doc.get('schema')!='pairing_completion_review_20260929_v1' or doc.get('scope')!='pairing_only' or doc.get('order_confirmed') is not False or set(doc['records'])!=set(cases):
        raise ValueError('return_scope_or_coverage')
    for oid,r in doc['records'].items():
        c=cases[oid]
        expected={k:c[k] for k in ['object_id','points','labels','coordinate_source','proposals','explicit_pairs']}
        if json.loads(r['binding'])!=expected or r['status']!='checked' or r['review_mode']!='complete_pairing' or r['order_confirmed'] is not False:
            raise ValueError('return_binding:'+oid)
        option=next(p for p in c['proposals'] if p['id']==r['proposal_id'])
        if r['deleted_source_indices']!=option['deleted']: raise ValueError('return_deletions:'+oid)
        ids=[i for p in r['pairs'] for i in p]
        if any(type(i) is not int for i in ids) or sorted(ids)!=[i for i in range(len(c['points'])) if i not in option['deleted']]:
            raise ValueError('return_pair_coverage:'+oid)
        x_adjacent(c['points'],r['pairs'])


def raw_initial_points(o):
    """原P点回到原始导出坐标；补点保留单独已确认坐标。"""
    points=o['before_preprocessing_points'];labels=o['point_labels'];raw=o['original_export_points']
    if points==raw:return copy.deepcopy(raw),list(range(len(raw or []))),[]
    if not points:return None,[],[]
    if len(labels)!=len(points):return None,[],['missing_point_identity']
    result=[];indices=[];changes=[]
    for i,(label,p) in enumerate(zip(labels,points)):
        m=re.fullmatch(r'p(\d+)',label)
        if m:
            index=int(m[1])-1
            if not 0<=index<len(raw):raise ValueError('raw_identity:'+o['object_id'])
            result.append(raw[index]);indices.append(index)
            if raw[index]!=p:changes.append(label+':使用原始导出坐标替代历史坐标移动')
        elif '补点' in label and o['repair_evidence']:
            result.append(p);indices.append(None);changes.append(label+':保留已确认补点')
        else:raise ValueError('unmapped_point:'+o['object_id']+':'+label)
    return result,indices,changes


def pair_keys(o):
    return [tuple(o['point_labels'][i] for i in pair) for pair in o['links_zero_based'] or []]


def build():
    csv.field_size_limit(32*1024*1024)
    cases={r['object_id']:r for r in jsdata(ROOT/'analysis_results/pairing_completion_review_20260929/data.js')['cases']}
    doc=read(INPUT);validate_received(doc,cases)
    audit=ROOT/'analysis_results/x_pairing_audit_20260929'
    with (audit/'34份逐项复核_只按明确OOS备注豁免.csv').open(encoding='utf-8-sig') as f:classifications={r['object_id']:r for r in csv.DictReader(f)}
    previous=read(audit/'evidence/pairing_return.json')['records']
    master={o['object_id']:o for o in read(ROOT/'analysis_results/shared_x_baseline_20260928/preprocessed_source.json')['objects']}
    # 两份人工GT补充版本也保留在新基线中。
    for o in read(ROOT/'analysis_results/order_gt_screened_20260928/source_objects.json')['objects']:
        if o['object_id'] not in master:master[o['object_id']]=o
    orders=read(ROOT/'analysis_results/order_completion_audit_20260929/received_orders.json')['records']
    validate_return(dict(schema='order_review_20260928_v3',examples_only=False,records=orders),master)
    result={};rows=[];kept={};pending=[]
    for oid,old in master.items():
        o=copy.deepcopy(old);links=o['links_zero_based'];deleted=[];changes=[]
        if o['object_kind']=='annotation':
            points,raw_indices,changes=raw_initial_points(o)
        else:points=copy.deepcopy(o['before_preprocessing_points']);raw_indices=list(range(len(points)))
        basis=o['pairing_basis']
        if oid in classifications:
            if classifications[oid]['review_result']=='user_oos_uncalculable':links=None;basis='user_explicit_oos_uncalculable'
            elif oid in doc['records']:
                r=doc['records'][oid];deleted=r['deleted_source_indices'];links=r['pairs'];basis='complete_pairing_review_20260929'
            else:
                r=previous[oid]
                if r['status'] not in {'checked','paired'}:raise ValueError('prior_not_checked:'+oid)
                links=x_adjacent(points,r['pairs'])['pairs'];basis='previous_explicit_pairs_plus_x_completion'
                if links is None:raise ValueError('unresolved_previous:'+oid)
        labels=o['point_labels']
        if deleted:
            keep=[i for i in range(len(points)) if i not in deleted];mapping={i:j for j,i in enumerate(keep)}
            links=[[mapping[a],mapping[b]] for a,b in links]
            points=[points[i] for i in keep];labels=[labels[i] for i in keep];raw_indices=[raw_indices[i] for i in keep]
        processed=shared_x(points,links).tolist() if points and links is not None else None
        if processed is None:links=None
        o.update(before_preprocessing_points=points,point_labels=labels,links_zero_based=links,preprocessed_points=processed,
            preprocessing_status='ready' if processed is not None else 'unavailable',pairing_basis=basis,
            initialization='raw_export_coordinates_then_confirmed_point_edits_then_pair_mean_x',
            original_export_indices=raw_indices,deleted_previous_point_indices=deleted,initialization_notes=changes,
            previous_baseline='shared_x_baseline_20260928',ring_confirmed=False)
        result[oid]=o
        oldkeys=pair_keys(old);newkeys=pair_keys(o);same_identity=bool(newkeys) and set(oldkeys)==set(newkeys)
        prior=orders.get(oid,{})
        if o['object_kind']=='gt_original':reason='original_gt_reference'
        elif o.get('cleaning_disposition') in {'excluded_by_review','historical_not_accepted'}:reason='excluded'
        elif processed is None:reason='pairing_unavailable'
        elif prior.get('status')=='confirmed' and same_identity:
            sequence=[newkeys.index(oldkeys[i]) for i in prior['order']]
            kept[oid]=dict(prior,order=sequence,binding=json.dumps(dict(id=oid,points=processed,labels=labels,links=links,preprocessing=o['preprocessing']),ensure_ascii=False,separators=(',',':')),
                previous_record=prior,identity_mapping='point_label_pair_identity',coordinates_reinitialized=processed!=old['preprocessed_points'])
            reason='confirmed_ring_preserved'
        elif o.get('image_code') in NO_RECALL:reason='user_no_recall'
        elif oid in classifications or (prior.get('status')=='confirmed' and not same_identity):
            if len(links)<=4:reason='four_pairs_default_skip'
            else:reason='pairing_resolved_order_pending';pending.append(oid)
        else:reason='outside_changed_pairing_scope'
        rows.append(dict(object_id=oid,image_code=o['image_code'],worker_id=o.get('worker_id',''),reason=reason,
            pair_count=len(links or []),pair_identity_same=same_identity,preprocessing_changed=processed!=old['preprocessed_points'],
            deleted_previous_point_indices=deleted,initialization_notes=changes,scene_doorway_status=o.get('scene_doorway_status'),scene_oos_status=o.get('scene_oos_status')))
    OUT.mkdir(exist_ok=True);(OUT/'evidence').mkdir(exist_ok=True)
    freeze_file(INPUT,OUT/'evidence/completed_pairing.json')
    dump(OUT/'preprocessed_source.json',dict(schema='research_preprocessed_source_v2',method='shared_x_periodic_shortest_arc_v1',coordinate_frame='1024x512',objects=list(result.values())))
    validate_return(dict(schema='order_review_20260928_v3',examples_only=False,records=kept),result)
    dump(OUT/'preserved_orders.json',dict(schema='order_review_20260928_v3',examples_only=False,records=kept))
    write_csv(OUT/'全量初始化及排序去向.csv',rows)
    write_csv(OUT/'本轮34份去向.csv',[r for r in rows if r['object_id'] in classifications])
    write_csv(OUT/'需要排序.csv',[r for r in rows if r['object_id'] in pending])
    summary=dict(received_confirmed=len(doc['records']),objects=len(result),annotations=sum(o['object_kind']=='annotation' for o in result.values()),
        preprocessing_changed=sum(r['preprocessing_changed'] for r in rows),preserved_orders=len(kept),
        next_order_objects=len(pending),next_order_images=len({result[i]['image_id'] for i in pending}),
        reviewed_34_destinations=dict(Counter(r['reason'] for r in rows if r['object_id'] in classifications)),
        formal_analysis_connected=False)
    dump(OUT/'summary.json',summary)
    dump(OUT/'field_contract.json',dict(schema='research_preprocessed_source_v2',coordinate_frame='1024x512',
        initialization='原P点读原始导出坐标；保留已确认删点/补点；上下配对共享周期最短弧x中点，y不变；结果持久写入preprocessed_points，非仅显示变换。',
        original_export_indices='有效点到原导出的零基映射；补点为null，保留repair_evidence',
        order='点对身份按上下点label映射；相同身份沿用历史确认环，四对默认不召回；新完整配对>4对且无可沿用环进入续审。',
        separation='门洞/OOS独立保留；明确无法计算的5份不自动复活；资格及原始文件不改；历史计算不自动冒充使用本版本。'))
    build_queue(result,pending)
    return summary


def build_queue(objects,ids):
    QUEUE.mkdir(exist_ok=True)
    with (ROOT/'analysis_results/review_final_20260928/全量复核.csv').open(encoding='utf-8-sig') as f:ledger={r['canonical_annotation_id']:r for r in csv.DictReader(f)}
    registry=read(ROOT/'analysis_results/consensus_research_20260923/inputs/room_registry.json.gz');meta={r['image_id']:r for r in registry['images']}
    room={iid:g['candidate_id'] for g in registry['candidates'] if g['physical_same_supported'] for iid in g['image_ids']}
    groups=defaultdict(list)
    for oid in ids:
        o=objects[oid];v=make_variant(o,ledger)
        v['source'].update(image_id=o['image_id'],provenance=o['source'],queue_state='pending',
            scene_doorway_status=o.get('scene_doorway_status'),scene_oos_status=o.get('scene_oos_status'),
            default_preview_order=sorted(range(len(o['links_zero_based'])),key=lambda i:o['preprocessed_points'][o['links_zero_based'][i][0]][0]))
        if 'geometry' not in v:raise ValueError('queue_geometry:'+oid+':'+v.get('error',''))
        groups[o['image_id']].append(v)
    cases=[];images={}
    for iid,variants in sorted(groups.items()):
        images[len(cases)]=dict(original=data_image(ROOT/meta[iid]['path'],texture=True))
        cases.append(dict(image_id=iid,title=objects[variants[0]['source']['object_id']]['image_code'],room_id=room.get(iid,''),category='配对完成后的排序',variants=variants))
    dataset=dict(cases=cases,counts=dict(cases=len(cases),variants=len(ids)),manifest=dict(contract_version='consensus_research_20260923_v1',review_round='after_pairing_20260929',export_schema='order_review_20260928_v3',examples_only=False,formal_data_connected=False))
    (QUEUE/'data.js').write_text('window.STUDIO_IMAGES='+encode(images)+';Object.values(window.STUDIO_IMAGES).forEach(i=>i.texture=i.original);window.STUDIO_DATA='+encode(dataset)+';window.ORDER_REVIEW_SEED={};window.ORDER_HISTORY_SOURCES=[];',encoding='utf-8')
    page=(ROOT/'analysis_results/order_followup_20260929/index.html').read_text(encoding='utf-8')
    page=re.sub(r'<script defer src="[^\"]*accepted[^\"]*"></script>','',page)
    page=page.replace('已确认结果直接沿用；人工修订GT未确认时默认按共享x升序，固定点对编号不变。','本轮使用原始导出坐标共享x后的预处理数据；默认按共享x升序预览，固定点对编号不变。')
    (QUEUE/'index.html').write_text(page,encoding='utf-8')
    dump(QUEUE/'source_objects.json',dict(objects=[objects[i] for i in ids]))


if __name__=='__main__':print(json.dumps(build(),ensure_ascii=False,indent=2))
