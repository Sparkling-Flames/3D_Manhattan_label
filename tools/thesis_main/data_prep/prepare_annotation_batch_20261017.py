"""按当前点对编号构建Project98正式增量；先写独立包，再显式切换当前入口。"""
import argparse
import copy
import json
from collections import Counter
from pathlib import Path

import numpy as np

from .consolidate_research_input import load_current_bundle,validate_bundle
from .admit_annotation_batch_20261017 import apply_bundle,REVISION
from ..analysis.annotation_gallery_new_batch_20261017 import ROOT,REVIEW,image_identity
from ..analysis.new_annotation_intake_audit_20261017 import verify_review_export
from ..analysis.paired_split_research.study import infer_links
from ..analysis.scope_reference_reconstruction_20261016 import geometry,floor

BASELINE=ROOT/'analysis_results/research_input_20260929/manifest.json'
OUT=ROOT/'analysis_results/research_input_20261017'
EVIDENCE=ROOT/'research/statistics/new_annotation_intake_20261017'
CONTRACT=ROOT/'docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json'


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def numbered_pairs(raw):
    points=np.asarray(raw,float)*[10.24,5.12]
    links,status,_=infer_links(points,np.flatnonzero(points[:,1]<256),np.flatnonzero(points[:,1]>256))
    if links is None:raise ValueError(status)
    # 固定编号沿原始top点索引；先按x重编号会改变人工order的含义。
    return links.tolist()


def dump(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def prepare():
    baseline=load_current_bundle(BASELINE)
    mapping=read(EVIDENCE/'IDENTITY_MAPPING.json');review=read(REVIEW);audit=read(EVIDENCE/'audit.json')
    timing={r['source_id']:r for r in audit['records']}
    decisions=read(ROOT/'research/data/image_review_decisions_20261017/decisions.json')
    grades={r['image_id']:r for r in decisions['new_batch_difficulty_decisions']}
    gallery=read(ROOT/'research/statistics/annotation_gallery_20261017/gallery.json')
    codes={r['image_id']:r['image_code'] for r in gallery['images']}
    existing={r['image_id'] for r in baseline['data']['images']}
    records=[];pairs={};images=[];new_ids=set()
    for source in sorted((ROOT/'export_label/新增中文标注').glob('*.json')):
        if not verify_review_export(source.read_bytes(),review):raise ValueError('review_export_content_drift')
        for task in read(source):
            iid=image_identity(task['data'])
            if iid not in existing and iid not in new_ids:
                gt=ROOT/f'data/mp3d_layout/valid/label_cor/{iid}.txt'
                images.append(dict(image_id=iid,image_code=codes[iid],building_id=iid.split('_')[0],
                    gt_original=dict(source=gt.relative_to(ROOT).as_posix(),points_1024x512=np.loadtxt(gt).tolist())))
                new_ids.add(iid)
            for ann in task['annotations']:
                sid=f'ls98:{task["id"]}:{ann["id"]}'
                raw=[[r['value']['x'],r['value']['y']] for r in ann['result'] if r.get('type')=='keypointlabels']
                choices=[c for r in ann['result'] if r.get('from_name')=='worker_scope_response' for c in r.get('value',{}).get('choices',[])]
                receipt=dict(review['records'][sid],raw_keypoints=copy.deepcopy(raw),
                    numbering_basis='current_minimum_wrapped_x_assignment_then_source_top_index_order',
                    historical_task8_pair_basis_recovered=False,numbering_authorization='用户：你看有序号就行了')
                records.append(dict(source_id=sid,project_id=task['project'],task_id=task['id'],annotation_id=ann['id'],
                    source_file=source.relative_to(ROOT).as_posix(),completed_by=ann['completed_by'],image_id=iid,
                    image_code=codes[iid],raw_keypoints=raw,review=receipt,scope_response=choices,
                    was_cancelled=ann['was_cancelled'],ground_truth=ann['ground_truth'],parent_annotation=ann['parent_annotation']))
                pairs[sid]=numbered_pairs(raw)
    if set(timing)!={r['source_id'] for r in records}:raise ValueError('timing_batch_population_mismatch')
    bundle=apply_bundle(baseline,dict(records=records,images=images),pairs,mapping)
    objects={o['object_id']:o for o in bundle['data']['objects']}
    new_objects=[o for o in objects.values() if o.get('batch_revision')==REVISION]
    context=dict(version=REVISION,analysis_input_admitted=True,source_project=98,
        numbering_basis='current_minimum_wrapped_x_assignment_then_source_top_index_order',
        numbering_authorization='用户：你看有序号就行了。按当前明确编号采用回执；不再以前工具恢复为前置。',
        historical_task8_pair_basis_recovered=False,records=[],difficulty_records=[],reference_catalog=[])
    for obj in new_objects:
        source=obj['source'];sid=source['source_id'];t=timing[sid]
        if not t['task_worker_time_available'] or not t['worker_mapping_confirmed']:raise ValueError('unverified_new_record_time_or_worker')
        obj['collection_active_time']=dict(seconds=t['task_worker_active_seconds'],source_id=sid,
            identity_key=t['time_identity_key'],rule='session_max_then_sum_v10_task_worker',
            source_audit='research/statistics/new_annotation_intake_20261017/audit.json',
            source_log_pointers=t['log_source_pointers'],adopted=True,annotation_lifecycle_attribution=False,
            target_scope_attribution=False)
        context['records'].append(dict(object_id=obj['object_id'],image_id=obj['image_id'],worker_id=obj['worker_id'],
            condition=obj['condition'],source_id=sid,task_worker_active_seconds=t['task_worker_active_seconds'],
            worker_scope_response=obj['worker_scope_response']))
    for meta in images:
        iid=meta['image_id'];grade=grades[iid]
        gt_id=next(im for im in bundle['data']['images'] if im['image_id']==iid)['references']['gt_original']
        obj=objects[gt_id];points=obj['points_1024x512'];fp=floor(points).tolist()
        photo=ROOT/f'data/mp3d_layout/valid/img/{iid}.png'
        selected=dict(target_id=gt_id,role='selected_gt',floor=fp)
        context['difficulty_records'].append(dict(image_id=iid,image=meta['image_code'],
            current_class=grade['difficulty'],conditional_difficulty=grade['difficulty'],qualifier=grade['qualifier'],
            target_version=gt_id,selected=selected,candidates=[selected],scene='not_recorded',
            doorway_status='not_recorded',oos_subtype='not_recorded',photo=str(photo),
            gt_error_excluded=False,difficulty_analysis_exclusion='',difficulty_analysis_eligible=True,
            question='',evidence='用户直接裁定中等；偏简单仅备注。',classification_basis='user_direct_20261017'))
        context['reference_catalog'].append(dict(target_id=gt_id,image_id=iid,image_code=meta['image_code'],
            reference_version='gt_original',current_target=True,role='selected_gt',version_alias=False,
            is_admitted_space_candidate=True,full_reference_available=True,points_1024x512=points,
            floor_xz_h=fp,geometry=geometry(points),status='existing_full_geometry',method='existing_explicit_reference',
            source_reference_ids=[gt_id],sources=[meta['gt_original']['source']],evidence={},minimal_gap='',
            image_analysis_blocked=False,image_analysis_hold_reasons=[]))
    bundle['batch_admission']=context
    bundle['validation']=validate_bundle(bundle['data'],bundle['research'],bundle['comments'],bundle['final_summary'])
    assert len(new_objects)==70 and bundle['validation']['annotations']==3222
    assert bundle['data']['objects'][:len(baseline['data']['objects'])]==baseline['data']['objects']
    OUT.mkdir(parents=True,exist_ok=True)
    manifest=copy.deepcopy(baseline['manifest'])
    manifest['entrypoints']={k:f'{k}.json' for k in ['data','research','comments','final_summary','final_orders','validation','batch_admission']}
    for name in ['field_contract','research_field_contract']:
        bundle[name]=copy.deepcopy(baseline[name]);bundle[name]['current_population_note']='正式增量：3222人员作答、261研究图；旧基线字段含义不变。'
        manifest['entrypoints'][name]=f'{name}.json'
    bundle['quality_review_metadata']=baseline['quality_update']
    manifest['entrypoints']['quality_review_metadata']='quality_review_metadata.json'
    manifest.update(effective_input_revision=REVISION,validation=bundle['validation'],
        validation_scope='完整有效快照含Project98；旧quality_update已应用，不重复回放。',
        consumer_rule='load_current_bundle默认当前合同入口；旧manifest可显式载入复现。',
        source_baseline=BASELINE.relative_to(ROOT).as_posix())
    for name,filename in manifest['entrypoints'].items():dump(OUT/filename,bundle[name])
    dump(OUT/'manifest.json',manifest)
    dump(OUT/'pair_maps.json',dict(version=REVISION,basis=context['numbering_basis'],
        historical_basis_recovered=False,authorization=context['numbering_authorization'],
        pair_maps=pairs,original_review_source=str(REVIEW)))
    dump(OUT/'CHECKS.json',dict(validation=bundle['validation'],old_objects_unchanged=True,
        new_records=len(new_objects),new_images=len(images),geometry=dict(Counter(o['geometry']['status'] for o in new_objects)),
        time_seconds=sum(r['task_worker_active_seconds'] for r in context['records']),
        numbering_basis=context['numbering_basis'],historical_basis_recovered=False))
    load_current_bundle(OUT/'manifest.json')
    return bundle


def activate():
    loaded=load_current_bundle(OUT/'manifest.json')
    if loaded['manifest']['effective_input_revision']!=REVISION:raise ValueError('wrong_prepared_revision')
    contract=read(CONTRACT)
    contract['data'].update(analysis_bundle=(OUT/'manifest.json').relative_to(ROOT).as_posix(),
        preprocessed_source=(OUT/'data.json').relative_to(ROOT).as_posix(),
        preprocessed_source_scope='当前为旧有效基线加已核Project98的70份增量；原始导出与旧快照保持。',
        analysis_bundle_rule='正式当前输入从load_current_bundle/load_current_input读取；Project98完整快照与编号映射见manifest。')
    dump(CONTRACT,contract)
    load_current_bundle()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--activate',action='store_true');args=parser.parse_args()
    if args.activate:activate()
    else:print(json.dumps(prepare()['validation'],ensure_ascii=False,indent=2))
