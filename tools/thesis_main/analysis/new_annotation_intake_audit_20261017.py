"""新70份作答身份/时间/排序与正式库存接入审计；质量用途单独保留。"""
import copy
import csv
import hashlib
import json
import math
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path

from .annotation_gallery_new_batch_20261017 import ROOT,REVIEW,image_identity,person_id

OUT=ROOT/'research/statistics/new_annotation_intake_20261017'
EXPORT_DIR=ROOT/'export_label/新增中文标注'
LOG_DIR=ROOT/'active_logs/new_server'
BATCH=ROOT/'research/statistics/annotation_gallery_20261017/new_batch.json'
CATALOG=ROOT/'research/statistics/b8l2_shared_v6_20261016/inputs/reference_catalog.json'
ADMITTED_MANIFEST='analysis_results/research_input_20261017/manifest.json'
PAIR_MAPS=ROOT/'analysis_results/research_input_20261017/pair_maps.json'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def utc_epoch(value):
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None:raise ValueError('timestamp timezone unspecified')
    return dt.astimezone(timezone.utc).timestamp()*1000


def audit_time(annotation,reports,*,same_key_annotations=1):
    """v10来源累计重放：session内峰值，再跨session求和；不截annotation。"""
    key='|'.join(str(annotation[k]) for k in ['project','task','completed_by'])
    result=dict(time_identity_key=key,time_unit='seconds',time_identity_level='project_runtime_task_worker',
        time_status='missing_task_worker_logs',annotation_active_seconds=None,
        task_worker_active_seconds=None,task_worker_time_available=False,task_worker_time_adopted=False,session_peaks=[],pre_annotation_cumulative_seconds=None,
        n_raw_reports=len(reports),n_unique_reports=0,n_duplicate_reports=0,n_conflicting_events=0,
        n_identity_conflict_reports=0,n_invalid_reports=0,n_reports_before_annotation=0,n_reports_after_annotation=0,
        n_sessions=0,log_source_pointers=[],annotation_timestamp_status='not_checked',
        invalid_reports=[],first_client_event_utc=None,last_client_event_utc=None,server_received_at_values=[],
        annotation_attribution_status='not_collected_by_schema' if same_key_annotations==1 else 'multiple_annotations_share_task_time',
        time_restriction='Replayed task-worker source duration; not adopted for current analysis, not annotation lifecycle or selected/cropped-scope duration')
    events={};conflicts=set();invalid=[]
    for report in reports:
        actual='|'.join(str(report.get(k)) for k in ['project_id','task_id','annotator_id'])
        if report.get('active_time_key')!=key or actual!=key:
            result['n_identity_conflict_reports']+=1;continue
        reasons=[]
        if report.get('active_time_schema_version')!='c2plus_task_worker_v1':reasons.append('unsupported_time_schema')
        if report.get('script_version')!='manual_scope_only_20260913_v10':reasons.append('unverified_script_semantics')
        if report.get('page_type')!='annotation' or report.get('page_gate_eligible') is not True or report.get('store_mismatch_present'):
            reasons.append('page_identity_gate_not_clear')
        if not isinstance(report.get('active_seconds'),(float,int)) or not math.isfinite(report['active_seconds']) or report['active_seconds']<0:
            reasons.append('invalid_active_seconds')
        if not isinstance(report.get('timestamp'),(float,int)) or not math.isfinite(report['timestamp']):reasons.append('invalid_client_epoch_ms')
        if not report.get('session_id'):reasons.append('session_missing')
        if reasons:
            invalid.append(dict(source=report.get('_source_pointer'),reasons=reasons));continue
        eid=(report['session_id'],report['timestamp'])
        payload={k:v for k,v in report.items() if not k.startswith('_') and k!='server_received_at'}
        signature=json.dumps(payload,sort_keys=True,ensure_ascii=False)
        if eid in events:
            result['n_duplicate_reports']+=1
            if events[eid][0]!=signature:conflicts.add(eid)
            events[eid][1]['_sources'].append(report.get('_source_pointer'))
        else:events[eid]=(signature,dict(report,_sources=[report.get('_source_pointer')]))
    rows=sorted((x[1] for x in events.values()),key=lambda r:r['timestamp'])
    result.update(n_unique_reports=len(rows),n_invalid_reports=len(invalid),invalid_reports=invalid,
        n_conflicting_events=len(conflicts),n_sessions=len({r['session_id'] for r in rows}),
        log_source_pointers=[s for r in rows for s in r['_sources'] if s])
    if not rows:
        if result['n_identity_conflict_reports'] or invalid:result['time_status']='identity_or_schema_conflict'
        return result
    sessions=defaultdict(list)
    for row in rows:sessions[row['session_id']].append(row)
    reset=any(any(b['active_seconds']<a['active_seconds'] for a,b in zip(rr,rr[1:])) for rr in sessions.values())
    status=('ambiguous_log_conflict' if conflicts or invalid or result['n_identity_conflict_reports'] else
            'ambiguous_cumulative_reset' if reset else 'replay_available_task_worker_unadopted')
    peaks=[dict(session_id=session,peak_active_seconds=max(r['active_seconds'] for r in rr),
                n_reports=len(rr),first_client_timestamp_ms=rr[0]['timestamp'],last_client_timestamp_ms=rr[-1]['timestamp'])
           for session,rr in sessions.items()]
    result['session_peaks']=peaks
    result['time_status']=status
    result['first_client_event_utc']=datetime.fromtimestamp(rows[0]['timestamp']/1000,timezone.utc).isoformat()
    result['last_client_event_utc']=datetime.fromtimestamp(rows[-1]['timestamp']/1000,timezone.utc).isoformat()
    result['server_received_at_values']=sorted({r.get('server_received_at') for r in rows if r.get('server_received_at')})
    if status=='replay_available_task_worker_unadopted':
        result['task_worker_active_seconds']=sum(r['peak_active_seconds'] for r in peaks)
        result['task_worker_time_available']=True
    try:cutoff=utc_epoch(annotation['updated_at'])
    except ValueError:
        result['annotation_timestamp_status']='timezone_unknown';return result
    before=[r for r in rows if r['timestamp']<=cutoff];after=[r for r in rows if r['timestamp']>cutoff]
    result.update(n_reports_before_annotation=len(before),n_reports_after_annotation=len(after),annotation_timestamp_status='explicit_timezone_UTC_compared')
    if before and status=='replay_available_task_worker_unadopted':
        result['pre_annotation_cumulative_seconds']=sum(max(r['active_seconds'] for r in before if r['session_id']==session)
                                                       for session in {r['session_id'] for r in before})
    return result


def verify_review_export(source_bytes,review):
    return review.get('source_sha256')==hashlib.sha256(source_bytes).hexdigest()


def audit_review_scope(annotation,review,candidates,*,review_geometry_verified=False):
    points=[r for r in annotation['result'] if r.get('type')=='keypointlabels']
    choices=[c for r in annotation['result'] if r.get('from_name')=='worker_scope_response' for c in r.get('value',{}).get('choices',[])]
    order=review.get('order') if review else None
    compatible=(isinstance(order,list) and len(points)%2==0 and len(order)==len(points)//2 and
                sorted(order)==list(range(len(points)//2)))
    return dict(review_status=review.get('filter') if review else None,
        review_order_confirmed=bool(review and review.get('order_confirmed')),
        review_order_index_compatible=compatible,review_order=order,
        review_geometry_version_status='verified_full_export_identity' if review_geometry_verified else 'not_proven_source_snapshot_unavailable',
        order_adoption_status='pending_pair_index_basis' if review_geometry_verified and compatible and review.get('order_confirmed') else 'unverified_review_binding',
        order_applied=False,
        worker_scope_choices=choices,bound_target_id=None,
        scope_status='unbound_existing_image_candidates' if candidates else 'unbound_no_existing_image_catalog',
        candidate_target_ids=[r['target_id'] for r in candidates],
        scope_restriction='Worker in/out scope response is not a declared reference ID/version; no geometry or score based routing')


def scan_logs(directory,projects):
    indexed=defaultdict(list);files=[];schemas=Counter()
    for path in sorted(directory.rglob('*.jsonl')):
        n=selected=0
        for line_no,line in enumerate(path.open(encoding='utf-8-sig'),1):
            if not line.strip():continue
            row=json.loads(line);n+=1;schemas[tuple(sorted(row))]+=1
            if str(row.get('project_id')) not in projects:continue
            selected+=1;row['_source_pointer']=path.relative_to(ROOT).as_posix()+f'#line={line_no}'
            indexed[(str(row.get('project_id')),str(row.get('task_id')),str(row.get('annotator_id')))].append(row)
        files.append(dict(source_file=path.relative_to(ROOT).as_posix(),raw_rows=n,selected_project_rows=selected))
    return indexed,files,[dict(fields=list(k),rows=v) for k,v in schemas.items()]


def old_account_candidates(account_ids):
    """只列旧原件completed_by同号证据；不据数字认定采集实例或人员相同。"""
    from ..data_prep.consolidate_research_input import load_current_bundle
    examples={};exports={};evidence=defaultdict(list)
    for obj in load_current_bundle()['data']['objects']:
        if obj['object_kind']=='annotation':examples.setdefault((obj['source']['project'],obj['worker_id']),obj)
    for obj in examples.values():
        src=obj['source'];path=ROOT/src['path']
        if path not in exports:
            exports[path]={(str(t['id']),str(a['id'])):a for t in read(path) for a in t['annotations']}
        ann=exports[path][str(src['task']),str(src['annotation'])]
        account=str(person_id(ann['completed_by']))
        if account in account_ids:
            evidence[account].append(dict(candidate_worker_id=obj['worker_id'],old_project_id=src['project'],
                old_task_id=src['task'],old_annotation_id=src['annotation'],old_completed_by=account,
                old_export=src['path'],old_object_id=obj['object_id'],same_collection_instance_proven=False))
    return [dict(source_account_id=account,candidate_existing_worker_ids=sorted({e['candidate_worker_id'] for e in evidence[account]}),
                 mapping_status='same_number_old_export_evidence_instance_unconfirmed' if evidence[account] else 'no_same_number_old_export_evidence',
                 evidence=evidence[account],automatic_person_mapping=False,
                 exclusion_identity_risk=bool({'W019','W026'} & {e['candidate_worker_id'] for e in evidence[account]}))
            for account in sorted(account_ids,key=int)]


def confirmed_identity_mapping(document,candidates):
    if (document.get('schema')!='annotation_source_identity_mapping_v1' or document.get('source_project')!=98 or
        document.get('target_namespace')!='existing_W' or document.get('identity_confirmed') is not True):
        raise ValueError('identity_mapping_unconfirmed')
    rows=document['mappings'];mapping={str(r['source_account_id']):r['worker_id'] for r in rows}
    expected={r['source_account_id']:r['candidate_existing_worker_ids'] for r in candidates}
    if any(r.get('identity_confirmed') is not True for r in rows):raise ValueError('identity_mapping_unconfirmed')
    if (len(mapping)!=len(rows) or set(mapping)!=set(expected) or len(set(mapping.values()))!=len(mapping) or
        any(worker not in expected[account] for account,worker in mapping.items())):
        raise ValueError('identity_mapping_source_conflict')
    return mapping


def apply_admission_status(rows,bundle,contract_manifest_path,pair_document=None):
    """以当前合同指向及完整source登记识别采用，不以准备目录存在授予资格。"""
    active=(ROOT/contract_manifest_path).resolve()==(ROOT/ADMITTED_MANIFEST).resolve()
    output=copy.deepcopy(rows)
    for row in output:
        row.update(formal_input_admitted=False,inventory_included=False,analysis_included=False,
            quality_analysis_included=False,time_adopted=False,historical_basis_recovered=False,
            source_pair_indices=None,pair_map_origin=None,source_pair_order_basis=None,geometry_status=None)
    if not active:return output,False
    records=bundle.get('batch_admission',{}).get('records',[])
    indexed={r['source_id']:r for r in records}
    if len(indexed)!=len(records) or set(indexed)!={r['source_id'] for r in rows}:
        raise ValueError('admitted_source_population_mismatch')
    if pair_document is None or set(pair_document['pair_maps'])!=set(indexed):
        raise ValueError('admitted_pair_map_population_mismatch')
    objects={o['object_id']:o for o in bundle['data']['objects']}
    for row in output:
        sid=row['source_id'];registered=indexed[sid];obj=objects[registered['object_id']]
        if any(row[k]!=registered[k] for k in ('image_id','worker_id')):
            raise ValueError('admitted_source_identity_mismatch:'+sid)
        pairs=pair_document['pair_maps'][sid]
        if (obj['links_zero_based']!=pairs or obj['ordered_source_pair_indices']!=row['review_order'] or
            obj['ring_confirmed'] is not True):
            raise ValueError('admitted_order_pair_binding_mismatch:'+sid)
        if [p[0] for p in pairs]!=sorted(p[0] for p in pairs):
            raise ValueError('admitted_source_top_index_order_mismatch:'+sid)
        if not row['task_worker_time_available'] or row['task_worker_active_seconds']!=registered['task_worker_active_seconds']:
            raise ValueError('admitted_time_binding_mismatch:'+sid)
        row.update(formal_input_admitted=True,inventory_included=True,analysis_included=True,
            quality_analysis_included=False,time_adopted=True,task_worker_time_adopted=True,
            time_status='adopted_task_worker_source_duration',
            time_restriction='Adopted task-worker source duration; not annotation lifecycle or selected/cropped-scope duration',
            order_applied=True,order_adoption_status='adopted_explicit_current_numbering',
            source_pair_indices=copy.deepcopy(pairs),pair_map_origin=PAIR_MAPS.relative_to(ROOT).as_posix()+'#/pair_maps/'+sid,
            numbering_basis=pair_document['basis'],source_pair_order_basis='source_top_index_order',
            geometry_status=obj.get('geometry',{}).get('status'),historical_basis_recovered=pair_document['historical_basis_recovered'])
    return output,True


def audit_readme(audit):
    adopted=audit['formal_input_admitted'];checks=audit['checks']
    status='已进入当前合同指向的正式研究输入；新增质量仍待目标绑定' if adopted else '尚未进入当前合同指向的正式研究输入'
    return f'''# 新增中文70份作答：身份、时间、排序与接入审计

本包记录正式接入时刻（评分前）的证据，下面quality_analysis_included=false及70份待绑定是该时刻状态。后续当前评分与局部归属请读 research/quality/quality_b8l2_d10_20261017/CROSS_MODULE_INPUTS.json，不用本审计的历史质量标志覆盖当前评分。

接入时状态：**{status}**。`analysis_included`在本包只表示正式研究输入采用，不代表所有质量用途合格。70份新增的`quality_analysis_included=false`，质量值保持空，不能补0。旧3152份快照及旧评分不追改。

- [完整审计](audit.json)与[逐条台账](records.csv)：项目、任务、作答、既有W身份、时间和排序来源。
- [字段合同](FIELD_CONTRACT.json)、[身份登记](IDENTITY_MAPPING.json)及[身份直接证据](IDENTITY_EVIDENCE.md)。
- [历史时间方法证据](HISTORICAL_TIME_METHOD.md)：最近93/94项目未冻结时间的历史事实与本次采用分开。

## 采用判据与结果

采用只在当前合同manifest为`{ADMITTED_MANIFEST}`且`batch_admission.records`的source_id与70条原作答完整匹配时成立；准备目录存在不算采用。当前合同指向：`{audit['current_contract_manifest']}`。

|项目|结果|
|---|---:|
|图片／作答／源账号|{checks['images']}／{checks['annotations']}／{checks['accounts']}|
|确认既有W身份|{checks['records_with_confirmed_worker_mapping']}份／7人|
|任务账号时间可用／正式采用|{checks['task_worker_active_values']}／{sum(r['time_adopted'] for r in audit['records'])}|
|排序已应用|{checks['orders_applied']}|
|完整导出同版验证|{checks['review_geometry_verified']}|
|当前surface_valid|{checks['surface_valid']}|
|接入当时新增质量可用|0，70份待目标绑定|

7个源账号1、6、8、10、12、15、17已确认映射既有W001、W006、W008、W010、W012、W015、W017。证据为93→98共同页面session的项目实例桥，加各账号旧93原始作答completed_by与bundle W身份精确锚；不是仅凭数字，也不是7名全新人员。既有人员排除、作答清洗与独立票门继续有效。

## 排序与参考

原审核的完整导出内容绑定已核实一致；此前“旧几何未证实”的缺口已解决。用户明确“你看有序号就行了”，本次按当前明确编号规则采用审核order，逐source保存原keypoint上下点对索引，台账`pair_map_origin`指向`analysis_results/research_input_20261017/pair_maps.json`。`historical_basis_recovered=false`：没有声称恢复旧task8工具的历史编号算法。

19图中17图已有库存，2t7-02/03为两张新增图，原GT来自valid/label_cor，人工难度为中等（偏简单）。GT完整不等于70份作答已绑定目标；新增质量用途仍待显式目标版本绑定。原图与新作答均保留全部点，不以最高质量或几何近似挑目标，不裁剪原作答。

scope仅指原导出in_scope/out_of_scope，69／1；out_of_scope为`ls98:3686:7549`。此choice不等于GT问题、人员排除或target_id，不存在另需补交的scope文件。

## 时间单位与边界

日志为v10／c2plus_task_worker_v1，身份是project|runtime_task|source_account，单位秒。每session取累计active_seconds峰值，再跨session求和；fragment不是网络增量，不能逐上报相加。70键合计5205秒；279原始日志、277去重事件，2重复，无冲突。采用状态以台账`time_adopted/task_worker_time_adopted`为准。

client epoch与有时区annotation时间统一UTC；naive服务器接收墙钟仅诊断，重传、manual flush和updated_at后的活动不自动使任务总时间无效。`annotation_active_seconds`保持空，因为采集合同未分解annotation生命周期；整份任务累计也不是裁切scope专属时间。未用lead_time替代或缺失填0。

最近93/94实际消费者历史上是unfrozen/null，本次Project98采用不追改它们的历史资格。原export_label和active_logs只读，未重算旧质量或改旧冻结包，未生成截图。目录和共享入口由主线程统一维护。
'''


def main():
    from ..data_prep.consolidate_research_input import load_current_bundle
    from ..data_prep.materialize_current_research_input import CONTRACT
    contract_manifest=read(CONTRACT)['data']['analysis_bundle']
    bundle=load_current_bundle()
    batch=read(BATCH);review_by_id={r['source_id']:r['review'] for r in batch['records']}
    review_source=read(REVIEW)
    if review_by_id!=review_source['records']:raise ValueError('review_index_snapshot_mismatch')
    review_binding={path:verify_review_export(path.read_bytes(),review_source) for path in sorted(EXPORT_DIR.glob('*.json'))}
    from .current_annotation_context_20261017 import load_current_context
    context=load_current_context(bundle)
    refs=defaultdict(list)
    for r in context['reference_catalog']:
        if r['current_target'] or r['is_admitted_space_candidate']:refs[r['image_id']].append(r)
    raw=[]
    for path in sorted(EXPORT_DIR.glob('*.json')):
        for task in read(path):
            image=image_identity(task['data'])
            for ann in task['annotations']:
                if ann['project']!=task['project'] or ann['task']!=task['id']:
                    raise ValueError('annotation/export project-task identity conflict')
                a=dict(ann,project=task['project'],task=task['id'],completed_by=person_id(ann['completed_by']))
                key=f'ls{a["project"]}:{a["task"]}:{a["id"]}'
                raw.append((path,image,task,a,key))
    counts=Counter((str(a['project']),str(a['task']),str(a['completed_by'])) for _,_,_,a,_ in raw)
    identities=old_account_candidates({str(a['completed_by']) for _,_,_,a,_ in raw})
    identity_map={r['source_account_id']:r for r in identities}
    identity_path=OUT/'IDENTITY_MAPPING.json'
    identity_document=read(identity_path)
    confirmed_workers=confirmed_identity_mapping(identity_document,identities)
    for candidate in identities:
        candidate.update(mapping_status='confirmed_shared_project_instance_and_old_source_anchor',
            confirmed_worker_id=confirmed_workers[candidate['source_account_id']],
            instance_confirmation_source=identity_path.relative_to(ROOT).as_posix()+'#/project_instance_bridge')
        for evidence in candidate['evidence']:
            evidence['same_collection_instance_proven']=evidence['candidate_worker_id']==candidate['confirmed_worker_id']
    decision_path=ROOT/'research/data/image_review_decisions_20261017/decisions.json'
    planning={r['image_id']:r for r in read(decision_path)['new_batch_difficulty_decisions']}
    logs,files,schemas=scan_logs(LOG_DIR,{str(a['project']) for _,_,_,a,_ in raw})
    rows=[]
    for path,image,task,a,key in raw:
        identity=(str(a['project']),str(a['task']),str(a['completed_by']))
        rows.append(dict(source_id=key,source_file=path.relative_to(ROOT).as_posix(),image_id=image,
            project_id=a['project'],task_id=a['task'],annotation_id=a['id'],completed_by=a['completed_by'],
            account_identity_status='confirmed_shared_project_instance_and_old_source_anchor',
            candidate_existing_worker_ids=identity_map[str(a['completed_by'])]['candidate_existing_worker_ids'],
            worker_id=confirmed_workers[str(a['completed_by'])],worker_mapping_confirmed=True,
            planning_difficulty=planning.get(image),
            same_task_worker_annotations=counts[identity],annotation_created_at=a['created_at'],
            annotation_updated_at=a['updated_at'],raw_keypoints=[r['value'] for r in a['result'] if r.get('type')=='keypointlabels'],
            analysis_included=False,**audit_time(a,logs.get(identity,[]),same_key_annotations=counts[identity]),
            **audit_review_scope(a,review_by_id.get(key),refs.get(image,[]),review_geometry_verified=review_binding[path])))
    active_path=(ROOT/contract_manifest).resolve()==(ROOT/ADMITTED_MANIFEST).resolve()
    rows,adopted=apply_admission_status(rows,bundle,contract_manifest,read(PAIR_MAPS) if active_path else None)
    identity_document['analysis_adopted']=adopted
    for entry in identity_document['mappings']:entry['analysis_adopted']=adopted
    adoption=dict(formal_input_admitted=adopted,inventory_included=adopted,analysis_included=adopted,
        quality_analysis_included=False,time_adopted=adopted,order_applied=adopted,historical_basis_recovered=False)
    audit=dict(version='new_annotation_intake_audit_20261017_v4',**adoption,
        current_contract_manifest=contract_manifest,
        admission_status='adopted_inventory_quality_target_pending' if adopted else 'pending_formal_contract_activation',
        checks=dict(annotations=len(rows),images=len({r['image_id'] for r in rows}),accounts=len({r['completed_by'] for r in rows}),
            unique_source_ids=len({r['source_id'] for r in rows}),log_files=len(files),raw_log_rows=sum(f['raw_rows'] for f in files),
            project_log_rows=sum(f['selected_project_rows'] for f in files),time_status=dict(Counter(r['time_status'] for r in rows)),
            annotation_active_values=sum(r['annotation_active_seconds'] is not None for r in rows),
            task_worker_active_values=sum(r['task_worker_time_available'] for r in rows),
            records_with_post_annotation_reports=sum(r['n_reports_after_annotation']>0 for r in rows),
            records_with_pre_annotation_reports=sum(r['n_reports_before_annotation']>0 for r in rows),
            worker_scope_choices=dict(Counter(v for r in rows for v in r['worker_scope_choices'])),
            scope_status=dict(Counter(r['scope_status'] for r in rows)),
            review_index_compatible=sum(r['review_order_index_compatible'] for r in rows),
            review_geometry_verified=sum(r['review_geometry_version_status']=='verified_full_export_identity' for r in rows),
            orders_applied=sum(r['order_applied'] for r in rows),
            formal_input_admitted=sum(r['formal_input_admitted'] for r in rows),
            time_adopted=sum(r['time_adopted'] for r in rows),
            surface_valid=sum(r['geometry_status']=='surface_valid' for r in rows),
            records_with_confirmed_worker_mapping=sum(r['worker_mapping_confirmed'] for r in rows)),
        source_files=dict(export_files=sorted({r['source_file'] for r in rows}),review_identity_index=BATCH.relative_to(ROOT).as_posix(),
            active_log_root=LOG_DIR.relative_to(ROOT).as_posix(),scope_catalog=CATALOG.relative_to(ROOT).as_posix(),
            admitted_scope_catalog=ADMITTED_MANIFEST.replace('manifest.json','batch_admission.json#/reference_catalog') if adopted else None,
            pair_maps=PAIR_MAPS.relative_to(ROOT).as_posix() if adopted else None,
            time_script_semantics='tools/label_studio/official/ls_userscript_annotator.js:2731-2784',
            planning_decisions=decision_path.relative_to(ROOT).as_posix(),identity_mapping=identity_path.relative_to(ROOT).as_posix()),
        review_source_binding=dict(review_source=str(REVIEW),review_source_name=review_source['source_name'],
            current_exports=[dict(source_file=p.relative_to(ROOT).as_posix(),exact_export_match=ok) for p,ok in review_binding.items()]),
        gaps=['原task8工具的历史点对编号源码未恢复；当前按用户明确编号规则采用，逐source配对索引已保存。' if adopted else '准备包尚未由当前合同采用。',
              '七账号已按共同项目实例桥及旧原件锚映射既有W身份，不是7名全新人员；仍按既有人员/作答排除门接入。',
              'scope就是导出中的in_scope/out_of_scope，不存在另需补交的scope文件；此choice不声明GT/目标版本。',
              'task-worker累计已采用；annotation生命周期及裁切scope专属耗时未被该合同采集。' if adopted else 'task-worker累计可重放，本批尚未正式采用。',
              '70份新作答目标版本尚待绑定，质量指标保持空值；正式库存采用不代表全用途质量资格。'],
        recent_actual_adoption=dict(projects=[93,94],status='unfrozen_no_adopted_seconds',
            consumer='tools/thesis_main/analysis/analyze_new_manual_20260921.py:71',
            continuation='tools/thesis_main/analysis/reviewed_manual_20260921.py:141',
            note='最近项目实际消费者未采用有效秒公式；本次重放不宣称延用它们已冻结的数值。'),
        confirmed_identity_mapping=identity_document,account_identity_candidates=identities,records=rows,log_file_inventory=files,log_schema_inventory=schemas)
    audit['checks'].update(duplicate_log_reports=sum(r['n_duplicate_reports'] for r in rows),
        conflicting_log_events=sum(r['n_conflicting_events'] for r in rows),
        invalid_log_reports=sum(r['n_invalid_reports'] for r in rows),
        identity_conflict_reports=sum(r['n_identity_conflict_reports'] for r in rows),
        missing_task_worker_logs=sum(r['time_status']=='missing_task_worker_logs' for r in rows))
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    (identity_path).write_text(json.dumps(identity_document,ensure_ascii=False,indent=2),encoding='utf-8')
    with (OUT/'records.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader()
        writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in row.items()} for row in rows)
    contract=dict(version=audit['version'],**adoption,records_columns=list(rows[0]),
        analysis_included_definition='正式研究输入采用；quality_analysis_included仅为接入时评分前历史状态，当前质量读quality_b8l2_d10_20261017共同评分，不代表当前仍70份待绑定。',
        adoption_gate='当前合同manifest必须指向research_input_20261017，且batch_admission source_id与70原作答完整匹配；准备目录存在不代表采用。',
        identity='Exact project/task/annotation source ID. Seven source accounts mapped to existing W identities through the documented shared-project instance bridge and original Project93 annotation anchors. worker_mapping_confirmed=true does not grant analysis admission.',
        units='active_seconds and fragment are seconds, timestamp is client epoch milliseconds. Annotation ISO time requires timezone and is converted to UTC. Naive server_received_at is evidence text only.',
        cumulative='Per session maximum active_seconds, then sum across sessions under verified cumulative contract. Not summing network reports/fragments or choosing a preferred annotation. Missing sessions/conflicts or within-session decreases remain unresolved.',
        task_worker_active_seconds='Project/runtime-task/account duration, session max then cross-session sum. Adoption follows current contract and batch admission; recent Project93/94 actual consumers historically kept time unfrozen. Multiple sessions or post-updated_at activity alone do not invalidate task duration.',
        annotation_active_seconds='Null because schema deliberately does not collect annotation lifecycle identity. This does not invalidate task-worker duration; no lead_time fallback or selected-scope attribution.',
        pre_annotation_cumulative_seconds='Per-session peaks at/before annotation.updated_at in UTC, summed only as diagnostic partial cumulative; not a cutoff for replayed task duration.',
        review='审核绑定的完整导出内容一致。当前按用户明确编号规则采用已保存pair_maps与review.order；historical_basis_recovered=false，不声称恢复旧工具编号源码。是否实际应用以order_applied为准。',
        scope='in_scope/out_of_scope is worker response, not target ID/version. Existing catalog candidates are context only. No score or geometric-proximity selection.',
        missing='JSON null / CSV blank; never imputed zero',
        logs='Recursive source inventory includes nested legacy files; dates are event/log dates, not pull dates. Only project98 events enter row matching.')
    (OUT/'FIELD_CONTRACT.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'README.md').write_text(audit_readme(audit),encoding='utf-8')
    print(json.dumps(audit['checks'],ensure_ascii=False,indent=2))
    return audit


if __name__=='__main__':main()
