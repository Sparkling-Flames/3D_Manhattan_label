"""当前裁决上的排序初筛；异常只召回，不改变清洗裁决。"""
import math
import numpy as np
from shapely.geometry import LineString


def resolve_links(original, points, labels):
    old = original['effective_points_1024x512']
    links = original.get('links_zero_based')
    if old == points:
        return links, 'existing_verified' if links else 'pairing_unavailable'
    if links and len(old) == len(points):
        return links, 'existing_identity_after_coordinate_repair'
    from .paired_split_research.study import infer_links
    p = np.asarray(points, float)
    up, dn = np.flatnonzero(p[:, 1] < 255.5), np.flatnonzero(p[:, 1] > 255.5)
    if len(up)+len(dn) != len(p):
        return None, 'point_on_horizon'
    links, reason, _ = infer_links(p, up, dn)
    return (links.tolist(), 'unique_pairing_after_repair') if links is not None else (None, reason)


def screen_order(pairs, floor):
    result = dict(crossings=[], acute_vertices=[], acute_angles_degrees={}, consecutive_acute=False, dense_pair_groups=[])
    if floor and all(p is not None for p in floor):
        p = np.asarray(floor)[:, [0, 2]]
        n = len(p)
        for i in range(n):
            a, b = p[i-1]-p[i], p[(i+1)%n]-p[i]
            norm = np.linalg.norm(a)*np.linalg.norm(b)
            if norm > 1e-12:
                angle=math.degrees(math.acos(float(np.clip(a.dot(b)/norm, -1, 1))))
                if angle<45:
                    result['acute_vertices'].append(i+1)
                    result['acute_angles_degrees'][str(i+1)]=round(angle,2)
            for j in range(i+1, n):
                if j-i in (1, n-1): continue
                if LineString([p[i],p[(i+1)%n]]).intersects(LineString([p[j],p[(j+1)%n]])):
                    result['crossings'].append([i+1,j+1])
        acute = set(result['acute_vertices'])
        result['consecutive_acute'] = any((i%n)+1 in acute for i in acute)
    xs = [p[0][0]%1024 for p in pairs]
    groups = {tuple(sorted(j+1 for j,y in enumerate(xs) if (y-x)%1024 <= 24)) for x in xs}
    result['dense_pair_groups'] = [list(g) for g in sorted(groups) if len(g)>=3 and not any(set(g)<set(h) for h in groups)]
    return result


def select_queue(row, metrics, count, explicit, paired):
    if row.get('cleaning_disposition') in {'excluded_by_review','historical_not_accepted'}: return 'excluded'
    if row.get('worker_quality_gate') in {'hold_all_analysis','hold_main_analysis'}: return 'hold'
    if row.get('scene_category') in {'oos','doorway_difficult','oos_stable_nonorthogonal'} or row.get('scene_oos_status')=='confirmed': return 'later'
    if not paired: return 'pairing'
    if explicit: return 'priority'
    if metrics['crossings']: return 'priority' if count>4 else 'geometry'
    if count>4 and (metrics['consecutive_acute'] or metrics['dense_pair_groups']): return 'weak'
    return 'normal'


def diagnose_points(points, links):
    """仅对有效完整点对作相机高度=1的地面投影；不是几何真值。"""
    from .shared_x_reanalysis_20260922 import shared_x
    empty=screen_order([],None)
    if points is None or links is None:
        return empty,'pairing_unavailable'
    p=np.asarray(points,float)
    if p.ndim!=2 or p.shape[1]!=2 or not np.isfinite(p).all():
        return empty,'invalid_points'
    if any(len(pair)!=2 for pair in links) or sorted(i for pair in links for i in pair)!=list(range(len(p))):
        return empty,'invalid_pair_identity'
    processed=shared_x(points,links).tolist()
    pairs=[[processed[a],processed[b]] for a,b in links]
    if any(not (a[1]<255.5 and b[1]>255.5) for a,b in pairs):
        return screen_order(pairs,None),'invalid_top_bottom_roles'
    floor=[]
    for _,b in pairs:
        x,y=b;u=2*math.pi*(x/1024-.5);v=math.pi*(.5-y/512)
        if v>=-math.radians(.5):
            return screen_order(pairs,None),'floor_near_horizon'
        radius=-math.cos(v)/math.sin(v)
        floor.append([radius*math.sin(u),-1,-radius*math.cos(u)])
    return screen_order(pairs,floor),'ok'


def unique_gt_references(references):
    """只保留GT；同一源文件的两个界面别名只算一份。"""
    result={}
    for ref in references:
        if ref['name'] not in {'gt_original','gt_revised'}:
            continue
        key=ref.get('source') or 'missing_gt'
        if key in result:
            if result[key].get('raw_points')!=ref.get('raw_points'):
                raise ValueError('same_gt_source_different_points:'+key)
            result[key]['aliases'].append(ref['name'])
        else:
            result[key]={**ref,'aliases':[ref['name']]}
    return list(result.values())


def materialize_shared_x_baseline():
    """全研究共享输入：全量预处理与分析资格独立，不只保存排序候选。"""
    import csv,json
    from pathlib import Path
    from .finalize_review_20260928 import read,dump,write_csv
    from .shared_x_reanalysis_20260922 import shared_x
    from .materialize_model_gt_threshold_screen import _read_test_gt
    root=Path(__file__).resolve().parents[3];out=root/'analysis_results/shared_x_baseline_20260928';out.mkdir(exist_ok=True)
    csv.field_size_limit(32*1024*1024)
    with (root/'analysis_results/review_final_20260928/全量复核.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    base={r['canonical_annotation_id']:r for r in read(root/'analysis_results/consensus_research_20260923/inputs/annotations.jsonl.gz')}
    records=[]
    for r in rows:
        cid=r['canonical_annotation_id'];before=json.loads(r['effective_points_1024x512'] or 'null');labels=json.loads(r['effective_point_labels'])
        links=None;reason='no_effective_points';after=None
        if before:
            links,reason=resolve_links(base[cid],before,labels)
            if links is not None:
                try:after=shared_x(before,links).tolist()
                except ValueError as exc:reason=str(exc)
        records.append(dict(object_id=cid,object_kind='annotation',image_id=r['image_id'],image_code=r['image_code'],worker_id=r['worker_id'],condition=r['condition'],
            source=json.loads(r['raw_source']),original_export_points=base[cid]['raw_points_1024x512'],before_preprocessing_points=before,
            preprocessed_points=after,point_labels=labels,links_zero_based=links,pairing_basis=reason,
            preprocessing_status='ready' if after is not None else 'unavailable',preprocessing='shared_x_periodic_shortest_arc_v1',
            repair_evidence=json.loads(r['repair_evidence']),cleaning_disposition=r['cleaning_disposition'],worker_quality_gate=r['worker_quality_gate'],
            consensus_group=r['consensus_group'],scene_category=r['scene_category'],scene_oos_status=r['scene_oos_status'],scene_doorway_status=r['scene_doorway_status'],
            trap_status=r['trap_status'],model_edit_status=r['model_edit_status'],ring_confirmed=False))
    manual=_read_test_gt(root/'export_label/groudTruth.json')
    with (root/'analysis_results/order_candidates_20260928/全量排序初筛.csv').open(encoding='utf-8-sig') as f:gt_rows=[r for r in csv.DictReader(f) if r['object_kind']!='annotation']
    for r in gt_rows:
        source=r['source'];before=(manual[r['image_id']] if source=='export_label/groudTruth.json' else np.loadtxt(root/source)).tolist()
        links=json.loads(r['links_zero_based']);after=None;reason=r['pairing_basis']
        if links is not None:
            try:after=shared_x(before,links).tolist()
            except ValueError as exc:reason=str(exc)
        records.append(dict(object_id=r['object_id'],object_kind=r['object_kind'],image_id=r['image_id'],image_code=r['image_code'],source=source,
            original_export_points=before,before_preprocessing_points=before,preprocessed_points=after,point_labels=['GT p'+str(i+1) for i in range(len(before))],
            links_zero_based=links,pairing_basis=reason,preprocessing_status='ready' if after is not None else 'unavailable',
            preprocessing='shared_x_periodic_shortest_arc_v1',repair_evidence=[],worker_quality_gate=r['worker_quality_gate'],ring_confirmed=False))
    assert len(records)==3439 and len({r['object_id'] for r in records})==3439
    payload=dict(schema='research_preprocessed_source_v1',method='shared_x_periodic_shortest_arc_v1',coordinate_frame='1024x512',objects=records)
    dump(out/'preprocessed_source.json',payload)
    from collections import Counter
    summary=dict(annotations=3152,gt_sources=287,annotation_status=dict(Counter(r['preprocessing_status'] for r in records if r['object_kind']=='annotation')),
                 gt_status=dict(Counter(r['preprocessing_status'] for r in records if r['object_kind']!='annotation')),
                 scope='后续分簇、区域质量、人员/图片差异、共识、排序共用；预处理完成不代表分析资格或顺序正确')
    dump(out/'summary.json',summary)
    dump(out/'field_contract.json',dict(schema=payload['schema'],primary_key='object_id',ready='完整配对共享x，y保持',unavailable='preprocessed_points=null；原因见pairing_basis，不回退到未处理点',
        consumers=['clustering','quality','consensus','order_review'],eligibility='按cleaning_disposition、worker_quality_gate及用途单独筛选',raw_mutation=False))
    write_csv(out/'预处理覆盖.csv',[dict(object_id=r['object_id'],image_code=r['image_code'],object_kind=r['object_kind'],status=r['preprocessing_status'],reason=r['pairing_basis']) for r in records])
    (out/'README.md').write_text('# 全研究共享x预处理源数据\n\n覆盖全部3152份人员标注及287份去重GT来源，不限排序候选。依据当前有效点（含已确认修复）与完整上下配对，周期最短弧平均x，y保持；原始与预处理前点分开保留。\n\n预处理状态与资格分离：ready不恢复已排除或暂停对象；unavailable的预处理点为null，后续计算必须报告失败，不能退回未平均坐标。排序确认将作为另一个独立排列层，不覆盖本点集。\n\n未来分簇、质量、共识、排序统一读取preprocessed_source.json，再按用途读取最新资格和确认排列。历史已完成结果不追改，历史脚本不冒充已切换。\n\n'+json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return payload


def build_candidates():
    import csv,json,html
    from pathlib import Path
    from collections import Counter,defaultdict
    from .build_order_studio_20260926 import EXPLICIT_ORDER
    from .finalize_review_20260928 import read,write_csv,dump
    from .materialize_model_gt_threshold_screen import _read_test_gt
    from .paired_split_research.study import infer_links
    from .audit_supervisor_gt_sensitivity_20260922 import is_substantive_revision
    root=Path(__file__).resolve().parents[3]
    final=root/'analysis_results/review_final_20260928'
    out=root/'analysis_results/order_candidates_20260928';out.mkdir(exist_ok=True)
    csv.field_size_limit(32*1024*1024)
    with (final/'全量复核.csv').open(encoding='utf-8-sig',newline='') as f: ledger=list(csv.DictReader(f))
    base={r['canonical_annotation_id']:r for r in read(root/'analysis_results/consensus_research_20260923/inputs/annotations.jsonl.gz')}
    references=read(root/'analysis_results/consensus_research_20260923/inputs/references.json.gz')
    manual=_read_test_gt(root/'export_label/groudTruth.json')
    examples={r['annotation_id'] for r in read(root/'analysis_results/order_acute_examples_20260928/MANIFEST.json')['examples']}
    by_image=defaultdict(list);records=[]
    def append_record(row,object_id,kind,source,points,links,pairing_basis,explicit,source_verified=True,aliases=None):
        metrics,geometry_status=diagnose_points(points,links)
        queue=select_queue(row,metrics,len(links or []),bool(explicit),links is not None)
        if queue=='excluded':geometry_status='not_screened_excluded'
        if queue not in {'excluded','hold','later','pairing'} and geometry_status!='ok':queue='geometry'
        if not source_verified:queue='source_check'
        triggers=[]
        if explicit:triggers.append('explicit_order_review')
        if metrics['crossings']:triggers.append('floor_edge_intersection')
        if metrics['consecutive_acute']:triggers.append('consecutive_angles_under_45deg')
        if metrics['dense_pair_groups']:triggers.append('three_pairs_within_24px_periodic')
        records.append(dict(object_id=object_id,object_kind=kind,image_id=row['image_id'],image_code=row['image_code'],
            worker_id=row['worker_id'] if kind=='annotation' else '',condition=row['condition'] if kind=='annotation' else '',
            source=source,reference_aliases=aliases or [],source_verified=source_verified,queue=queue,triggers=triggers,
            point_count=len(points or []),pair_count=len(links or []),links_zero_based=links,point_version='current_effective' if kind=='annotation' else 'source_gt_coordinates',
            pairing_basis=pairing_basis,geometry_status=geometry_status,metrics=metrics,explicit_order_evidence=explicit,
            scene_category=row['scene_category'],scene_oos_status=row['scene_oos_status'],scene_doorway_status=row['scene_doorway_status'],
            cleaning_disposition=row['cleaning_disposition'],worker_quality_gate=row['worker_quality_gate'],
            individual_review_covered=row['individual_review_covered'] if kind=='annotation' else '',
            image_comment=row['image_comment'],order_confirmed=False))
    for row in ledger:
        iid=row['image_id'];cid=row['canonical_annotation_id'];by_image[iid].append(row)
        # CSV合同规定历史无有效点用空单元格表示null，不是空点集。
        points=json.loads(row['effective_points_1024x512'] or 'null');labels=json.loads(row['effective_point_labels'])
        links=None;basis='not_screened_excluded'
        if row['cleaning_disposition'] not in {'excluded_by_review','historical_not_accepted'}:
            if points is not None and len(points)>0:links,basis=resolve_links(base[cid],points,labels)
            else:basis='no_effective_points'
        explicit=[]
        if cid in EXPLICIT_ORDER:explicit.append(dict(source='latest_review',comment=row['current_decision_comment'],scope='current_annotation'))
        if cid in examples:explicit.append(dict(source='用户对10例的明确回复',comment='这些图都要重新排序',scope='ten_example_annotation'))
        append_record(row,cid,'annotation',json.loads(row['raw_source']),points,links,basis,explicit,row['raw_verified']=='true')
    for iid,group in by_image.items():
        first=group[0]
        # GT只继承图片级暂停/OOS，不继承恰好排在首行的某个人的排除。
        context={**first,'cleaning_disposition':'reference','worker_quality_gate':'candidate_pending_geometry'}
        gates={r['worker_quality_gate'] for r in group}
        if 'hold_all_analysis' in gates:context['worker_quality_gate']='hold_all_analysis'
        elif 'hold_main_analysis' in gates:context['worker_quality_gate']='hold_main_analysis'
        explicit=[dict(source=r['canonical_annotation_id'],comment=r['current_decision_comment'],scope='GT_version_unspecified') for r in group
                  if 'gt' in r['current_decision_comment'].lower() and '顺序' in r['current_decision_comment']]
        refs=unique_gt_references(references[iid]['references'])
        original=next((ref for ref in refs if 'gt_original' in ref['aliases'] and ref.get('source')),None)
        if original:
            has_current_revision=iid in manual and is_substantive_revision(np.loadtxt(root/original['source']),manual[iid])
            if has_current_revision!=any(ref.get('source')=='export_label/groudTruth.json' for ref in refs):
                raise ValueError('GT_revision_inventory_changed:'+iid)
        for ref in refs:
            source=ref.get('source');points=ref.get('raw_points');links=None;basis=ref.get('pairing_basis','missing');verified=False
            if source:
                current=manual.get(iid) if source=='export_label/groudTruth.json' else np.loadtxt(root/source)
                verified=current is not None and points is not None and np.asarray(points).shape==np.asarray(current).shape and np.allclose(points,current,atol=1e-5,rtol=0)
                if verified and basis=='source_alternating_pairs' and len(points)%2==0:
                    links=[[i,i+1] for i in range(0,len(points),2)]
                elif verified and points:
                    p=np.asarray(points,float);up=np.flatnonzero(p[:,1]<255.5);dn=np.flatnonzero(p[:,1]>255.5)
                    if len(up)+len(dn)==len(points):
                        found,basis,_=infer_links(p,up,dn);links=found.tolist() if found is not None else None
                        if links is not None:basis='diagnostic_unique_pairing_source_top_point_order_unconfirmed'
            kind='gt_manual_revision' if source=='export_label/groudTruth.json' else 'gt_original'
            append_record(context,'gt:'+iid+':'+str(source),kind,source,points,links,basis,explicit,verified,ref['aliases'])
    assert len([r for r in records if r['object_kind']=='annotation'])==3152
    assert len({r['object_id'] for r in records})==len(records)
    write_csv(out/'全量排序初筛.csv',records)
    candidates=[r for r in records if r['queue'] in {'priority','weak'}]
    write_csv(out/'待排序候选.csv',candidates)
    summary=dict(schema='order_candidate_inventory_v1',formal_data_connected=False,
        annotation_count=3152,images=len(by_image),gt_sources=len(records)-3152,
        annotation_queues=dict(Counter(r['queue'] for r in records if r['object_kind']=='annotation')),
        gt_queues=dict(Counter(r['queue'] for r in records if r['object_kind']!='annotation')),
        candidate_objects=len(candidates),candidate_images=len({r['image_id'] for r in candidates}),
        accepted_individually_reviewed=sum(r['accepted_before_review']=='true' and r['individual_review_covered']=='true' for r in ledger),
        accepted_without_individual_record=sum(r['accepted_before_review']=='true' and r['individual_review_covered']=='false' for r in ledger),
        completion='既有清洗问题已处理，不等于所有作答逐份人工审查；本次只整理候选，不接入全量排序。')
    dump(out/'summary.json',summary)
    dump(out/'field_contract.json',dict(schema=summary['schema'],primary_key='object_id',fields=list(records[0]),
        queues={'priority':'明确排序意见或>4对自交','weak':'>4对连续锐角或周期密集','geometry':'四对异常或投影失败，不能认定换序可修复','pairing':'先核验配对','later':'OOS/难标门洞后续队列','hold':'图片明确暂缓','excluded':'当前明确排除或历史未纳入','source_check':'GT源或绑定需核对','normal':'本轮初筛未命中，不证明顺序正确'},
        limits=['固定现有完整点对，仅对显示副本shared-x','GT原始源环序保留；人工修订GT唯一水平配对仅作诊断，连接顺序仍未知','自交/锐角不是排序错误真值','GT版本未指明的评论不擅自指定一版','不含HoHoNet模型GT']))
    labels={'priority':'优先排序候选','weak':'几何弱线索候选','pairing':'先核验配对','geometry':'先核验几何／点位','source_check':'先核验来源'}
    trigger_labels={'explicit_order_review':'明确排序意见','floor_edge_intersection':'地面投影非邻边相交','consecutive_angles_under_45deg':'连续锐角<45°','three_pairs_within_24px_periodic':'24px内至少三对'}
    tr=[]
    for r in sorted(candidates,key=lambda r:(r['queue']!='priority',r['image_code'],r['object_kind'],r['worker_id'])):
        tr.append('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in [r['image_code'],r['worker_id'] or ('人工修订GT' if r['object_kind']=='gt_manual_revision' else '原始GT'),labels[r['queue']],r['pair_count'],'；'.join(trigger_labels[t] for t in r['triggers']),r['scene_category']])+'</tr>')
    blocked=[r for r in records if r['queue'] in {'pairing','geometry','source_check'}]
    write_csv(out/'配对与表示待核.csv',blocked)
    blocked_html='<details><summary>另列：配对与表示待核（'+str(len(blocked))+'个，不假定重排可修复）</summary><p><a href="配对与表示待核.csv">下载完整证据</a></p><ul>'+''.join('<li>'+html.escape(r['image_code']+' · '+(r['worker_id'] or r['object_kind'])+'：'+labels[r['queue']]+'；'+r['pairing_basis']+'；'+r['geometry_status'])+'</li>' for r in blocked)+'</ul></details>'
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>排序候选清单</title><style>body{font:16px system-ui;margin:30px;background:#f5f7f4}table{border-collapse:collapse;background:white;width:100%}th,td{padding:9px;border-bottom:1px solid #ddd;text-align:left}th{position:sticky;top:0;background:#e8efe8}p{line-height:1.7}</style><h1>人员与GT排序候选</h1><p>仅初筛，尚未接入全量工作台。自交、连续锐角和密集点对均不是已确认顺序错误；四对异常、配对失败、OOS/难标门洞及暂停图片另列。</p><p><a href="待排序候选.csv">下载候选</a> · <a href="全量排序初筛.csv">下载含全部状态的初筛</a> · <a href="README.md">口径与数量</a></p><table><thead><tr><th>图片</th><th>人员／GT</th><th>优先级</th><th>点对数</th><th>线索</th><th>场景</th></tr></thead><tbody>'+''.join(tr)+'</tbody></table>',encoding='utf-8')
    page=out/'index.html';page.write_text(page.read_text(encoding='utf-8')+blocked_html,encoding='utf-8')
    (out/'README.md').write_text('# 排序候选整理\n\n'+summary['completion']+'\n\n人员使用最新有效点与清洗裁决；明确排除85份和历史未纳入133份不召回。GT原始/人工修订按源文件区分、相同源文件别名去重，并回读源坐标核验。没有将模型预测作为GT。\n\n复用现有几何初筛：相机高度1的地面投影非邻边相交、相邻角度均小于45度、周期24像素内至少三对。四对不因弱线索进入排序；失败另外记录。不按IoU筛选，不修改点对或顺序。人工修订GT的唯一水平匹配仅为诊断，未确认连接次序。\n\nGT原始环保留文件原始点对顺序，不自动按x排序；GT评论未指明版本时并列核验两版，不冒称两版都错。GT不继承某个人的排除，但服从图片暂停与OOS/门洞分层。\n\n待排序候选.csv只列priority/weak；配对与表示待核.csv单列配对、四对异常、投影/来源问题；全量排序初筛.csv保留全部状态和证据。63份人员候选与27份GT候选涉及45张图片。10例已确认需要排序，其他仍是初筛提示，不能当已确认错误。\n\n```json\n'+json.dumps(summary,ensure_ascii=False,indent=2)+'\n```\n',encoding='utf-8')
    return summary


if __name__=='__main__':
    import json
    print(json.dumps(build_candidates(),ensure_ascii=False,indent=2))

