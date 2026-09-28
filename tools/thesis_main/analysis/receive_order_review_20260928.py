"""接收双人排序证据，按已确认物理同房关系建立独立复审工作台。"""
from __future__ import annotations

import copy
import csv
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from .build_order_studio_20260926 import ROOT, OUT as OLD, HERE, encode, geometry_variant, original_ids
from .finalize_review_20260928 import read, dump, write_csv
from .shared_x_reanalysis_20260922 import shared_x
from tools.label_studio.panorama_studio.build import data_image

OUT = ROOT / 'analysis_results/order_same_room_review_20260928'
PAIR_NOTE_ID = 'a3975721377143bb'
TARGET = '917375ed9bf4c232'


def validate_return(doc, sources):
    if doc.get('schema') != 'order_review_20260928_v3' or doc.get('examples_only') is not False:
        raise ValueError('return_schema_or_scope')
    if not isinstance(doc.get('records'), dict):
        raise ValueError('return_records')
    for oid, record in doc['records'].items():
        source = sources[oid]
        expected = dict(id=oid, points=source['preprocessed_points'], labels=source['point_labels'],
                        links=source['links_zero_based'], preprocessing=source['preprocessing'])
        if json.loads(record['binding']) != expected:
            raise ValueError('return_binding:' + oid)
        order = record['order']
        if (record['status'] not in {'confirmed', 'draft', 'pending', 'pairing'}
                or not isinstance(order, list) or any(type(i) is not int for i in order)
                or sorted(order) != list(range(len(expected['links'])))):
            raise ValueError('return_order_or_status:' + oid)
        for key in ('note', 'cause', 'updated_at'):
            if not isinstance(record.get(key), str):
                raise ValueError('return_missing_field:' + oid + ':' + key)


def reconcile(returns):
    history = defaultdict(list)
    for reviewer, doc in returns.items():
        for oid, record in doc['records'].items():
            history[oid].append(dict(reviewer=reviewer, record=record))
    merged, conflicts = {}, []
    for oid, events in history.items():
        decisions = [{k: e['record'][k] for k in ('status', 'order', 'note', 'cause')} for e in events]
        if any(d != decisions[0] for d in decisions[1:]):
            conflicts.append(oid)
            continue
        merged[oid] = copy.deepcopy(max(events, key=lambda e: e['record']['updated_at'])['record'])
    return merged, dict(history), conflicts


def expand_rooms(seeds, candidates):
    selected = [r for r in candidates if r['physical_same_supported'] and seeds.intersection(r['image_ids'])]
    room_map = {}
    for room in selected:
        for iid in room['image_ids']:
            if iid in room_map:
                raise ValueError('overlapping_physical_rooms:' + iid)
            room_map[iid] = room
    return seeds | set(room_map), room_map


def make_variant(obj, ledger):
    oid = obj['object_id']; ann = obj['object_kind'] == 'annotation'
    ready = obj['preprocessing_status'] == 'ready'
    # 配对不可用时只显示平均前二维点；禁止用它构造几何或充当共享x输入。
    points = obj['preprocessed_points'] if ready else (obj['before_preprocessing_points'] or [])
    links = obj['links_zero_based'] if ready else None
    row = ledger[oid] if ann else {}
    name = f"{obj['worker_id']} · {obj['condition']} · {len(points)}点" if ann else (
        '原始Matterport GT' if obj['object_kind'] == 'gt_original' else '人工修订GT')
    if not ready:
        name += ' · 配对待审（仅二维）'
    source = dict(role='annotation' if ann else 'reference', object_id=oid, object_kind=obj['object_kind'],
        canonical_annotation_id=oid if ann else None, worker_id=obj.get('worker_id'), raw_condition=obj.get('condition'),
        reference_name=name if not ann else None, reference_source=obj['source'] if not ann else None,
        points=points, effective_points=points, before_preprocessing_points=obj['before_preprocessing_points'],
        preprocessed_points=obj['preprocessed_points'], effective_point_labels=obj['point_labels'],
        links_zero_based=links, preprocessing=obj['preprocessing'],
        original_point_ids_1based=original_ids(obj['original_export_points'], obj['before_preprocessing_points'] or []),
        raw_points_1024x512=obj['original_export_points'], ring_confirmed=False,
        processing_status='共享x预处理基线' if ready else '平均前点仅供配对复审；不可计算',
        review={k: row.get(k, '') for k in ('model_edit_status','trap_status','current_decision_comment',
                    'cleaning_disposition','worker_quality_gate','image_comment')})
    return geometry_variant(name, source, points, links)


def build():
    csv.field_size_limit(32 * 1024 * 1024)
    OUT.mkdir(exist_ok=True); (OUT / 'evidence').mkdir(exist_ok=True)
    files = {
        'user': Path('C:/Users/ASUS/Downloads/角点顺序审核.json'),
        'yizheng': Path('C:/Users/ASUS/Documents/xwechat_files/wxid_lvoh11i1addo22_a66c/msg/file/2026-09/角点顺序审核.json'),
    }
    returns = {}
    for reviewer, src in files.items():
        dst = OUT / 'evidence' / f'{reviewer}.json'
        if dst.exists() and dst.read_bytes() != src.read_bytes():
            raise ValueError('evidence_changed:' + reviewer)
        shutil.copyfile(src, dst); returns[reviewer] = read(dst)
    old = json.loads((OLD / 'data.js').read_text(encoding='utf-8').split('window.STUDIO_DATA=', 1)[1].rstrip(';\n'))
    slots = {c['image_id']: i+1 for i, c in enumerate(old['cases'])}
    original = {o['object_id']: o for o in read(OLD / 'preprocessed_source.json')['objects']}
    master = {o['object_id']: o for o in read(ROOT / 'analysis_results/shared_x_baseline_20260928/preprocessed_source.json')['objects']}
    for oid, obj in original.items():
        for key in ('preprocessed_points','before_preprocessing_points','point_labels','links_zero_based','source'):
            if obj[key] != master[oid][key]:
                raise ValueError('shared_source_binding:' + oid)
    for doc in returns.values():
        validate_return(doc, original)
    from .review_reconciliation_audit_20260925 import verify_raw, same
    from .materialize_model_gt_threshold_screen import _read_test_gt
    manual_gt = _read_test_gt(ROOT/'export_label/groudTruth.json')
    exports = {}
    for oid in set().union(*(set(doc['records']) for doc in returns.values())):
        obj=original[oid]
        if obj['object_kind']=='annotation':
            src=obj['source']; path=src['path']
            if path not in exports:
                exports[path]={t['id']:t for t in read(ROOT/path)}
            task=exports[path][src['task']]
            annotations=[a for a in task['annotations'] if a['id']==src['annotation']]
            if len(annotations)!=1:
                raise ValueError('raw_annotation_binding:'+oid)
            verify_raw(src,obj['original_export_points'],task,annotations[0])
        else:
            points=manual_gt[obj['image_id']] if obj['source']=='export_label/groudTruth.json' else np.loadtxt(ROOT/obj['source'])
            if not same(points,obj['original_export_points']):
                raise ValueError('current_gt_version_changed:'+oid)
    merged, history, conflicts = reconcile(returns)
    if conflicts:
        dump(OUT / 'conflicts.json', dict(object_ids=conflicts, history=history))
        raise ValueError('reviewer_conflict:' + ','.join(conflicts))
    if merged[PAIR_NOTE_ID]['note'] != '第3 第4对点匹配错误':
        raise ValueError('explicit_pairing_note_changed')
    effective = copy.deepcopy(merged)
    effective[PAIR_NOTE_ID]['status'] = 'pairing'
    dump(OUT / 'received_orders.json', dict(schema='received_order_layer_v1', history=history,
        records=effective, source_coordinates_mutated=False, formal_analysis_connected=False,
        interpretation={PAIR_NOTE_ID: '确认按钮与明确配对错误评论并存；保留原记录，顺序不可视为已解决'},
        reviewer_identity_basis='Downloads覆盖28起，微信文件覆盖1–29；结合用户说明归属，文件本身没有审核人字段'))
    dump(OUT / 'importable_orders.json', dict(schema='order_review_20260928_v3', examples_only=False, records=effective))
    with (ROOT / 'analysis_results/review_final_20260928/全量复核.csv').open(encoding='utf-8-sig') as f:
        ledger = {r['canonical_annotation_id']: r for r in csv.DictReader(f)}
    registry = read(ROOT / 'analysis_results/consensus_research_20260923/inputs/room_registry.json.gz')
    expanded, room_map = expand_rooms(set(slots), registry['candidates'])
    meta = {r['image_id']: r for r in registry['images']}
    by_image = defaultdict(list)
    for row in ledger.values():
        by_image[row['image_id']].append(row)
    objects = defaultdict(list); omitted = []
    for obj in master.values():
        if obj['image_id'] not in expanded:
            continue
        if obj['object_kind'] == 'annotation' and ledger[obj['object_id']]['cleaning_disposition'] in {'excluded_by_review','historical_not_accepted'}:
            omitted.append(dict(object_id=obj['object_id'], image_id=obj['image_id'], reason=ledger[obj['object_id']]['cleaning_disposition']))
            continue
        objects[obj['image_id']].append(obj)
    for iid in expanded:
        if not any(o['object_kind']=='gt_original' for o in objects[iid]):
            image = meta[iid]; path = Path(image['path']).parent.parent / 'label_cor' / f'{iid}.txt'
            points = np.loadtxt(ROOT/path).tolist()
            if (len(points) < 6 or len(points)%2 or any(points[i][0]!=points[i+1][0]
                    or not points[i][1]<255.5<points[i+1][1] for i in range(0,len(points),2))):
                raise ValueError('new_gt_pair_contract:' + iid)
            links = [[i,i+1] for i in range(0,len(points),2)]
            objects[iid].append(dict(object_id='gt:'+iid+':'+path.as_posix(), object_kind='gt_original', image_id=iid,
                source=path.as_posix(), original_export_points=points, before_preprocessing_points=points,
                preprocessed_points=shared_x(points,links).tolist(), preprocessing_status='ready',
                point_labels=['GT p'+str(i+1) for i in range(len(points))], links_zero_based=links,
                preprocessing='shared_x_periodic_shortest_arc_v1', pairing_basis='source_alternating_pairs',
                scope='新增同房无人员标注视角；本工作台GT补充层，不扩展正式研究样本'))
        from .audit_supervisor_gt_sensitivity_20260922 import is_substantive_revision
        from .paired_split_research.study import infer_links
        original_gt=next(o for o in objects[iid] if o['object_kind']=='gt_original')
        if (iid in manual_gt and not any(o['object_kind']=='gt_manual_revision' for o in objects[iid])
                and is_substantive_revision(np.asarray(original_gt['original_export_points']),manual_gt[iid])):
            points=manual_gt[iid]; up=np.flatnonzero(points[:,1]<255.5);dn=np.flatnonzero(points[:,1]>255.5)
            links,basis,_=infer_links(points,up,dn) if len(up)+len(dn)==len(points) else (None,'point_on_horizon',{})
            processed=shared_x(points,links).tolist() if links is not None else None
            objects[iid].append(dict(object_id='gt:'+iid+':export_label/groudTruth.json',object_kind='gt_manual_revision',image_id=iid,
                source='export_label/groudTruth.json',original_export_points=points.tolist(),before_preprocessing_points=points.tolist(),
                preprocessed_points=processed,preprocessing_status='ready' if processed is not None else 'unavailable',
                point_labels=['GT p'+str(i+1) for i in range(len(points))],links_zero_based=links.tolist() if links is not None else None,
                preprocessing='shared_x_periodic_shortest_arc_v1',pairing_basis=basis,
                scope='新增同房视角现存人工修订GT；唯一水平配对仅作诊断，环序未确认'))
    cases=[]; images={}; scope=[]; seed={}; object_rows=[]
    # 原45图保持原编号，新增视角排后；每图展示全部尚保留的人员及全部已登记GT版本。
    image_order = list(slots) + sorted(expanded-set(slots), key=lambda iid:(meta[iid]['building'],meta[iid]['number']))
    for iid in image_order:
        m=meta[iid]; code=f"{m['building']}-{m['number']:02d}"; room=room_map.get(iid)
        group=sorted(objects[iid],key=lambda o:(o['object_kind']!='annotation',o.get('worker_id',''),o['object_id']))
        variants=[make_variant(o,ledger) for o in group]
        pos=len(cases); image_path=ROOT/m['path']
        if not image_path.is_file():
            raise ValueError('missing_room_image:'+iid)
        images[pos]=dict(original=data_image(image_path,texture=True))
        category=(room['candidate_id'] if room else '同房关系未确认')+' · 全来源复核'
        cases.append(dict(image_id=iid,title=code,room_id=room['candidate_id'] if room else '',category=category,variants=variants,
                          annotation_ids=[o['object_id'] for o in group]))
        scope.append(dict(image_id=iid,image_code=code,original_slot=slots.get(iid),review_slot=pos+1,
            room_id=room['candidate_id'] if room else '',physical_same_supported=bool(room),
            room_members=room['image_ids'] if room else [],room_evidence=room or {},
            raw_image_path=m['path'],annotation_count=len(by_image[iid]),
            review_annotations=sum(o['object_kind']=='annotation' for o in group),
            review_gt=sum(o['object_kind']!='annotation' for o in group),
            priority=slots.get(iid) in {41,42,43,44} or bool(room and room['candidate_id'] in {'G184','G243','G245'}),
            review_status='pending_user_review'))
        for o,v in zip(group,variants):
            oid=o['object_id']; prior=effective.get(oid)
            if prior:
                seed[oid]={**prior,'status':'pairing' if prior['status']=='pairing' else 'draft'}
            object_rows.append(dict(object_id=oid,image_code=code,object_kind=o['object_kind'],
                worker_id=o.get('worker_id',''),preprocessing_status=o['preprocessing_status'],
                previous_status=prior['status'] if prior else 'unreviewed',
                new_round_status=seed[oid]['status'] if oid in seed else 'unreviewed',
                worker_quality_gate=o.get('worker_quality_gate',''),
                geometry_available='geometry' in v,geometry_issue=v.get('error',''),
                note=prior['note'] if prior else ''))
    dataset=dict(cases=cases,counts=dict(cases=len(cases),variants=len(object_rows)),
        manifest=dict(contract_version='consensus_research_20260923_v1',export_schema='order_review_20260928_v3',
            formal_data_connected=False,examples_only=False,review_round='same_room_expansion_20260928'))
    (OUT/'data.js').write_text('window.STUDIO_IMAGES='+encode(images)+';Object.values(window.STUDIO_IMAGES).forEach(i=>i.texture=i.original);window.STUDIO_DATA='+encode(dataset)+';window.ORDER_REVIEW_SEED='+encode(seed)+';',encoding='utf-8')
    page=(OLD/'index.html').read_text(encoding='utf-8')
    for name in ('studio.js','studio.css','three.min.js','OrbitControls.js'):
        page=page.replace('"'+name+'"','"../order_studio_20260926/'+name+'"')
    page=page.replace('"order_studio.js"','"../../tools/thesis_main/analysis/order_studio_20260926.js"')
    page=page.replace('"order_studio.css"','"../../tools/thesis_main/analysis/order_studio_20260926.css"')
    (OUT/'index.html').write_text(page,encoding='utf-8')
    dump(OUT/'source_objects.json',dict(schema='same_room_review_sources_v1',objects=[o for iid in image_order for o in objects[iid]],
        primary_source='analysis_results/shared_x_baseline_20260928/preprocessed_source.json',formal_population_changed=False))
    write_csv(OUT/'同房复核范围.csv',scope);write_csv(OUT/'逐对象复核.csv',object_rows);write_csv(OUT/'未召回排除对象.csv',omitted)
    # 同一截图对象逐点回查运行时导出和正式导入，不依赖页面摘要。
    target=ledger[TARGET]; evidence=json.loads(target['trap_model_evidence']); binding=json.loads(target['raw_source'])
    runtime=next(t for t in read(ROOT/binding['path']) if t['id']==binding['task'])
    ann=next(a for a in runtime['annotations'] if a['id']==binding['annotation'])
    raw=[[p['value']['x']*1024/100,p['value']['y']*512/100] for p in ann['result'] if p['type']=='keypointlabels']
    initial=evidence['model_check']['initial_points_1024x512']
    if not np.allclose(raw,initial,atol=1e-6,rtol=0):
        raise ValueError('model_unchanged_evidence_drift')
    imported=[t for t in read(ROOT/evidence['evidence']['formal_import']) if t['data'].get('base_task_id')==target['image_id']]
    if len(imported)!=1 or imported[0]['data']['semi_role']!='trap':
        raise ValueError('formal_trap_binding')
    predictions=imported[0]['predictions']
    if len(predictions)!=1:
        raise ValueError('ambiguous_initial_prediction')
    init_raw=[[p['value']['x']*1024/100,p['value']['y']*512/100] for p in predictions[0]['result'] if p['type']=='keypointlabels']
    if not np.allclose(raw,init_raw,atol=1e-6,rtol=0):
        raise ValueError('formal_initialization_mismatch')
    dump(OUT/'model_unchanged_check.json',dict(object_id=TARGET,image_code=target['image_code'],worker_id='W011',
        status=target['model_edit_status'],trap_status=target['trap_status'],raw_source=binding,
        formal_import=evidence['evidence']['formal_import'],point_count=len(raw),
        maximum_coordinate_difference=float(np.max(np.abs(np.asarray(raw)-init_raw))),
        annotation_traits=json.loads(target['annotation_traits']),
        finding='台账已有记录；旧排序工作台source.review漏带模型与Trap字段，导致显示未记录。'))
    summary=dict(schema='same_room_order_review_summary_v1',reviewer_records={k:dict(Counter(r['status'] for r in v['records'].values())) for k,v in returns.items()},
        original_objects=90,received_unique=len(merged),raw_source_verified=len(merged),overlap=len(history)-sum(len(v)==1 for v in history.values()),
        raw_status=dict(Counter(r['status'] for r in merged.values())),effective_status=dict(Counter(r['status'] for r in effective.values())),
        missing_objects=sorted(set(original)-set(merged)),conflicts=conflicts,
        original_gt_received=sum(original[k]['object_kind']=='gt_original' for k in merged),
        original_gt_changed=sum(original[k]['object_kind']=='gt_original' and r['order']!=list(range(len(original[k]['links_zero_based']))) for k,r in merged.items()),
        rooms=len({r['candidate_id'] for r in room_map.values()}),images=len(cases),
        images_with_annotations=sum(bool(by_image[iid]) for iid in image_order),
        images_without_annotations=sum(not by_image[iid] for iid in image_order),
        unbound_seed_images=[r['image_code'] for r in scope if not r['room_id']],
        review_objects=len(object_rows),review_annotations=sum(o['object_kind']=='annotation' for o in object_rows),
        review_gt=sum(o['object_kind']!='annotation' for o in object_rows),
        omitted_objects=len(omitted),preprocessing=dict(Counter(o['preprocessing_status'] for o in object_rows)),
        geometry_unavailable=sum(not o['geometry_available'] for o in object_rows),new_round_confirmed=0,
        formal_analysis_connected=False)
    dump(OUT/'summary.json',summary)
    dump(OUT/'field_contract.json',dict(schema=summary['schema'],
        received_layer='保留两个来源的原始记录；仅相同status/order/note/cause允许合并，时间戳取较新；冲突拒绝自动选择',
        pairing_note='a3975721377143bb明确评论优先；派生状态pairing，原confirmed保留在history',
        order='完整固定点对索引的零基排列；绑定共享x坐标、标签、配对、方法和object_id',
        new_round='全部114图待人工复审；上轮排列用于预览，状态重置draft或保留pairing，不算本轮确认',
        unpaired='preprocessed_points=null；平均前点仅二维展示，无几何，无顺序确认',
        scope='全部有证据同房视角+无已确认同房关系的原候选；所有尚保留人员及现存GT；排除和历史未纳入对象仅列表',
        qualification='原清洗、图片与分析资格保留；此层不接入正式分析，不扩展正式研究样本',
        csv_keys={'同房复核范围.csv':'image_id','逐对象复核.csv':'object_id','未召回排除对象.csv':'object_id'},
        raw_mutation=False))
    return summary


if __name__=='__main__':
    print(json.dumps(build(),ensure_ascii=False,indent=2))
