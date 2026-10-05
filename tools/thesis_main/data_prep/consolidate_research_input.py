"""将最终输入、研究解释和评论收拢为合同指向的本地分析包。"""
import json
import math
import shutil
from collections import Counter
from pathlib import Path

from .materialize_current_research_input import ROOT, OUT, CONTRACT, read, dump, indexed
from tools.thesis_main.analysis.receive_order_review_20260928 import validate_return


def validate_bundle(data, research, comments, final):
    if (data['schema'],research['schema'],comments['schema'])!=('final_review_research_input_v1','review_research_interpretation_v1','review_comments_v1'):
        raise ValueError('component_schema_mismatch')
    objects = indexed(data['objects'], 'object_id')
    annotations = {i:o for i,o in objects.items() if o['object_kind']=='annotation'}
    images = indexed(data['images'], 'image_id')
    research_rows = indexed(research['annotations'], 'object_id')
    if set(annotations) != set(research_rows):
        raise ValueError('research_annotation_population_mismatch')
    if {i['image_id'] for i in research['images']}!={i['image_id'] for i in images.values() if i['population']=='research_annotation_image'}:
        raise ValueError('research_image_population_mismatch')
    orders = {}
    ready = 0
    for oid,o in objects.items():
        if o['image_id'] not in images:
            raise ValueError('unknown_image:' + oid)
        if o['preprocessing_status']=='ready':
            ready += 1
            before=o['before_preprocessing_points']; points=o['preprocessed_points']; links=o['links_zero_based']
            if len(points)!=len(before) or sorted(i for pair in links for i in pair)!=list(range(len(points))):
                raise ValueError('incomplete_pairing:' + oid)
            for top,bottom in links:
                delta=(before[bottom][0]-before[top][0]+512)%1024-512
                mid=(before[top][0]+delta/2)%1024
                if abs(delta)>=512-1e-8:
                    raise ValueError('ambiguous_periodic_midpoint:' + oid)
                for i in (top,bottom):
                    if not all(math.isfinite(v) for v in points[i]) or abs(points[i][0]-mid)>1e-8 or points[i][1]!=before[i][1]:
                        raise ValueError('shared_x_or_y_mismatch:' + oid)
            indices=o['ordered_source_point_indices']
            if sorted(indices)!=list(range(len(points))) or o['points_1024x512']!=[points[i] for i in indices]:
                raise ValueError('matterport_point_identity_mismatch:' + oid)
            if o['matterport_links_zero_based']!=[[i,i+1] for i in range(0,len(points),2)]:
                raise ValueError('matterport_pairing_mismatch:' + oid)
        elif o['points_1024x512'] is not None or o['preprocessed_points'] is not None:
            raise ValueError('unavailable_coordinates_not_null:' + oid)
        if o['ring_confirmed']:
            orders[oid]=o['order_record']
            pair_order=o['order_record']['order']
            if o['ordered_source_pair_indices']!=pair_order:
                raise ValueError('confirmed_ring_mismatch:' + oid)
        if oid in annotations:
            r=research_rows[oid]
            for k in ('image_id','worker_id','condition','cleaning_disposition','worker_quality_gate','consensus_group','trap_status','model_edit_status','order_status'):
                if r[k]!=o[k]:raise ValueError('research_field_mismatch:'+oid+':'+k)
            if r['geometry_status']!=o['geometry']['status']:raise ValueError('geometry_summary_mismatch:'+oid)
    validate_return(dict(schema='order_review_20260928_v3',examples_only=False,records=orders),objects)
    if len(orders)!=final['confirmed_orders'] or len(annotations)!=final['annotations']:
        raise ValueError('final_count_mismatch')
    if dict(Counter(o['cleaning_disposition'] for o in annotations.values()))!=final['cleaning']:
        raise ValueError('cleaning_summary_mismatch')
    for im in images.values():
        for kind,oid in im['references'].items():
            if objects[oid]['image_id']!=im['image_id'] or objects[oid]['object_kind']!=kind:
                raise ValueError('gt_reference_mismatch')
    occurrences=indexed(comments['occurrences'],'occurrence_id')
    if comments['summary']['occurrences']!=len(occurrences) or research['summary']['annotations']!=len(annotations):
        raise ValueError('component_summary_count_mismatch')
    for r in occurrences.values():
        if r['object_id'] is not None and (r['object_id'] not in objects or objects[r['object_id']]['image_id']!=r['image_id']):
            raise ValueError('comment_object_binding_mismatch')
        if r['binding_status']=='image_bound' and r['image_id'] not in images:
            raise ValueError('comment_image_binding_mismatch')
    linked=[i for r in comments['comments'] for i in r['occurrence_ids']]
    if len(linked)!=len(set(linked)) or set(linked)!=set(occurrences):
        raise ValueError('comment_occurrence_coverage_mismatch')
    for name,table in research['cross_tables'].items():
        valid=images if name in {'gt_marks','scene_images'} else objects
        ids=[i for row in table for i in row['ids']]
        if len(ids)!=len(set(ids)) or not set(ids)<=set(valid) or any(row['n']!=len(row['ids']) for row in table):
            raise ValueError('cross_table_ids_mismatch:'+name)
    return dict(status='passed',objects=len(objects),annotations=len(annotations),ready_coordinate_objects=ready,
        confirmed_orders=len(orders),research_images=sum(i['population']=='research_annotation_image' for i in images.values()),
        reference_only_images=sum(i['population']=='manual_gt_reference_only' for i in images.values()),
        comment_occurrences=len(occurrences),unresolved_comment_occurrences=sum(r['binding_status']=='unresolved' for r in occurrences.values()),
        checks=['完整配对','周期平均x及y不变','Matterport数组源点身份','确认环绑定','人员/GT/图片引用',
                '清洗及研究表字段一致','交叉表ID及计数','评论来源覆盖'],
        limitation='机器一致性验证，不宣称所有标注人工确认或方法可计算；人工未决和未知来源继续保留。')


def build():
    from .materialize_current_research_input import build as build_input
    from tools.thesis_main.analysis.build_review_research_tables_20260929 import build as build_research
    from tools.thesis_main.analysis.build_review_comment_table_20260929 import build as build_comments
    data=build_input(); research=build_research(); comments=build_comments()
    final_dir=ROOT/'analysis_results/final_review_summary_20260929'
    final=read(final_dir/'summary.json')
    validation=validate_bundle(data,research,comments,final)
    # 单目录快照；原目录保留作为历史证据，后续消费只从manifest取入口。
    dump(OUT/'research_tables.json',research)
    dump(OUT/'comments.json',comments)
    archive=OUT/'final_review';archive.mkdir(exist_ok=True)
    files=[]
    for p in sorted(final_dir.iterdir()):
        if p.suffix.lower() in {'.json','.csv'}:
            shutil.copyfile(p,archive/p.name)
            files.append(dict(path='final_review/'+p.name,source=p.relative_to(ROOT).as_posix()))
    for name,src in [('research_tables_field_contract.json','review_research_tables_20260929/field_contract.json')]:
        shutil.copyfile(ROOT/'analysis_results'/src,OUT/name)
    dump(OUT/'validation.json',validation)
    manifest=dict(schema='research_analysis_bundle_v1',contract_version=data['contract_version'],
        entrypoints=dict(data='preprocessed_source.json',research='research_tables.json',comments='comments.json',
            final_summary='final_review/summary.json',final_orders='final_review/received_orders.json',validation='validation.json',field_contract='field_contract.json',research_field_contract='research_tables_field_contract.json'),
        additional_tables=files,validation=validation,
        consumer_rule='从本manifest相对路径读取；preprocessed_source只负责坐标及最终状态，汇总和评论不覆盖裁决。历史源路径仅用于追溯。',
        privacy='含原始评论和内部编号；2026-10-01已授权公开映射与原评语。当前可见范围见README，独立面板仍按白名单投影。')
    dump(OUT/'manifest.json',manifest)
    return manifest


def load_current_bundle():
    """统一入口；跨表不一致即报错，不静默读取旧批次。"""
    path=ROOT/read(CONTRACT)['data']['analysis_bundle']
    manifest=read(path)
    if manifest['schema']!='research_analysis_bundle_v1':raise ValueError('bundle_schema_mismatch')
    loaded={}
    for k,rel in manifest['entrypoints'].items():
        target=(path.parent/rel).resolve()
        if not target.is_relative_to(path.parent.resolve()):raise ValueError('bundle_path_outside_directory')
        loaded[k]=read(target)
    if loaded['data']['contract_version']!=manifest['contract_version'] or manifest['contract_version']!=read(CONTRACT)['contract_version']:
        raise ValueError('bundle_contract_mismatch')
    loaded['validation']=validate_bundle(loaded['data'],loaded['research'],loaded['comments'],loaded['final_summary'])
    if {o['object_id']:o['order_record'] for o in loaded['data']['objects'] if o['ring_confirmed']}!=loaded['final_orders']['records']:
        raise ValueError('final_order_snapshot_mismatch')
    if (ROOT/read(CONTRACT)['data']['preprocessed_source']).resolve()!=(path.parent/manifest['entrypoints']['data']).resolve():
        raise ValueError('contract_coordinate_entry_mismatch')
    return dict(manifest=manifest,**loaded)


if __name__=='__main__':
    print(json.dumps(build()['validation'],ensure_ascii=False,indent=2))
