"""独立排序工作台：复用 Panorama Studio，只展示当前有效点和排列副本。"""
from __future__ import annotations

import json
import csv
import copy
import math
import shutil
from collections import Counter
from pathlib import Path

from tools.label_studio.panorama_studio.geometry import analyze
from tools.label_studio.panorama_studio.build import data_image

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'analysis_results/consensus_visual_review_20260923'
OUT = ROOT / 'analysis_results/order_studio_20260926'
STUDIO = ROOT / 'tools/label_studio/panorama_studio'
HERE = Path(__file__).parent
DEFAULT_ID = '158cdf9ee8269d7a'
FINAL = ROOT / 'analysis_results/review_final_20260928'
EXPLICIT_ORDER = {'d22e8df3dcff4100efb5','75507c55b020fe0f933f','fba833f7e946e03406f0','81cd8395dbe20dc23478','b593f337fea5cb8bf3f2','new_94_3645_7433_W028','846f35a4fc23776b55a2','026b9a1fe7ba6a07'}


def read_js(path, prefix):
    text = path.read_text(encoding='utf-8')
    if not text.startswith(prefix):
        raise ValueError(f'Unexpected script prefix: {path}')
    return json.loads(text[len(prefix):].rstrip(';\n'))


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).replace('</', '<\\/')


def validate_inventory(rows, expected_records=3019, expected_images=259):
    if (len(rows) != expected_records or len({r['id'] for r in rows}) != expected_records
            or len({r['image_id'] for r in rows}) != expected_images):
        raise ValueError('inventory_count_or_identity_drift')


def original_ids(raw, effective):
    if raw == effective:
        return list(range(1, len(raw) + 1))
    result = []
    for point in effective:
        matches = [i + 1 for i, candidate in enumerate(raw) if candidate == point]
        result.append(matches[0] if len(matches) == 1 and effective.count(point) == 1 else None)
    return result


def geometry_variant(name, source, points, links):
    if any(len(p) != 2 or any(not math.isfinite(v) for v in p) for p in points):
        raise ValueError('nonfinite_or_malformed_point_array')
    variant = {'name': name, 'source': source}
    if links is None:
        variant['error'] = '上下配对尚不可用；保留全部二维点，不推断新配对。'
        return variant
    flat = [i for pair in links for i in pair]
    if (any(len(pair) != 2 for pair in links) or any(type(i) is not int for i in flat)
            or sorted(flat) != list(range(len(points)))):
        raise ValueError('pair_identity_drift')
    pairs = []
    for a, b in links:
        ids = source['original_point_ids_1based']
        pair_id = f'raw:{ids[a]}/{ids[b]}' if ids[a] is not None and ids[b] is not None else f'effective:{a+1}/{b+1}'
        pairs.append({'source_pair_id': pair_id, 'top': dict(zip(('x', 'y'), points[a])),
                      'bottom': dict(zip(('x', 'y'), points[b]))})
    try:
        variant['geometry'] = analyze({'width': 1024, 'height': 512, 'coordinate_mode': 'pixels',
                                       'ordered_pairs': pairs}, compute_fit=False)
    except ValueError as error:
        variant['error'] = str(error)
    return variant


def annotation_variant(row):
    points, raw = row['effective_points_1024x512'], row['raw_points_1024x512']
    source = {k: row.get(k) for k in ('canonical_annotation_id', 'worker_id', 'raw_condition', 'stage',
              'raw_export_path', 'runtime_task_id', 'raw_annotation_id', 'processing_status',
              'imputation_provenance', 'pairing_review', 'pairing_status')}
    source.update(role='annotation', points=points, raw_points_1024x512=raw,
                  points_identity_basis='effective_point_array', links_zero_based=row['links_zero_based'],
                  original_point_ids_1based=original_ids(raw, points), ring_confirmed=False,
                  geometry_basis='保留有效点各自坐标及现有配对排列；不平均x，不重排，不重新推断配对')
    name = f"{row['worker_id']} · {row['raw_condition']} · {len(points)}点"
    return geometry_variant(name, source, points, row['links_zero_based'])


def reference_variant(row):
    points = row['raw_points'] or []
    # Only source-provided consecutive pairs establish identity; normalization alone does not.
    links = ([[i, i+1] for i in range(0, len(points), 2)]
             if row.get('pairing_basis') == 'source_alternating_pairs' and len(points) % 2 == 0 else None)
    source = dict(role='reference', reference_name=row['name'], reference_source=row['source'],
                  points=points, raw_points_1024x512=points, points_identity_basis='reference_source_point_array',
                  original_point_ids_1based=list(range(1, len(points)+1)), links_zero_based=links,
                  processing_status='reference_source_coordinates', ring_confirmed=False, source_unavailable_reason=row.get('reason'))
    return geometry_variant('参考 · ' + row['name'], source, points, links)


def candidate_workspace():
    """冻结共享x输入基线；仅接入本轮90个候选，不覆盖采集真源。"""
    import gzip
    import numpy as np
    from .shared_x_reanalysis_20260922 import shared_x
    from .materialize_model_gt_threshold_screen import _read_test_gt
    from .finalize_review_20260928 import read
    from .order_review_20260928 import materialize_shared_x_baseline
    global_baseline=materialize_shared_x_baseline()
    preprocessed={r['object_id']:r for r in global_baseline['objects']}
    csv.field_size_limit(32*1024*1024)
    with (ROOT/'analysis_results/order_candidates_20260928/待排序候选.csv').open(encoding='utf-8-sig') as f: candidates=list(csv.DictReader(f))
    with (FINAL/'全量复核.csv').open(encoding='utf-8-sig') as f: ledger={r['canonical_annotation_id']:r for r in csv.DictReader(f)}
    manual=_read_test_gt(ROOT/'export_label/groudTruth.json')
    base={r['canonical_annotation_id']:r for r in read(ROOT/'analysis_results/consensus_research_20260923/inputs/annotations.jsonl.gz')}
    records=[];cases=[];images={};by_image={}
    for r in sorted(candidates,key=lambda r:(r['image_code'],r['object_kind']!='annotation',r['worker_id'],r['object_id'])):
        iid=r['image_id'];oid=r['object_id'];links=json.loads(r['links_zero_based'])
        if r['queue'] not in {'priority','weak'} or r['source_verified']!='true':raise ValueError('candidate_not_ready:'+oid)
        is_ann=r['object_kind']=='annotation'
        if is_ann:
            row=ledger[oid];before=json.loads(row['effective_points_1024x512']);raw=base[oid]['raw_points_1024x512']
            labels=json.loads(row['effective_point_labels']);provenance=json.loads(row['raw_source']);repair=json.loads(row['repair_evidence'])
            name=f"{r['worker_id']} · {r['condition']} · {len(before)}点"
        else:
            provenance=r['source'];before=(manual[iid] if provenance=='export_label/groudTruth.json' else np.loadtxt(ROOT/provenance)).tolist()
            raw=before;labels=['GT p'+str(i+1) for i in range(len(before))];repair=[]
            name='人工修订GT' if r['object_kind']=='gt_manual_revision' else '原始Matterport GT'
        master=preprocessed[oid]
        if master['preprocessing_status']!='ready' or master['before_preprocessing_points']!=before or master['links_zero_based']!=links:
            raise ValueError('candidate_preprocessing_binding_mismatch:'+oid)
        processed=master['preprocessed_points']
        record=dict(object_id=oid,object_kind=r['object_kind'],image_id=iid,image_code=r['image_code'],source=provenance,
            before_preprocessing_points=before,preprocessed_points=processed,original_export_points=raw,
            point_labels=labels,links_zero_based=links,repair_evidence=repair,
            preprocessing='shared_x_periodic_shortest_arc_v1',coordinate_frame='1024x512',y_unchanged=True,
            pairing_basis=r['pairing_basis'],ring_confirmed=False)
        records.append(record)
        source=dict(role='annotation' if is_ann else 'reference',object_id=oid,object_kind=r['object_kind'],
            canonical_annotation_id=oid if is_ann else None,worker_id=r['worker_id'],raw_condition=r['condition'],
            reference_name=name if not is_ann else None,reference_source=provenance if not is_ann else None,
            points=processed,effective_points=processed,before_preprocessing_points=before,effective_point_labels=labels,
            original_point_ids_1based=original_ids(raw,before),links_zero_based=links,preprocessing=record['preprocessing'],
            processing_status='预处理基线：上下点共享x',screening=json.loads(r['metrics']),queue=r['queue'],
            review={**r, **({k: row[k] for k in ('model_edit_status','trap_status','current_decision_comment')} if is_ann else {})},
            ring_confirmed=False,raw_points_1024x512=raw)
        variant=geometry_variant(name,source,processed,links)
        if 'geometry' not in variant:raise ValueError('candidate_geometry_unavailable:'+oid+':'+variant.get('error',''))
        if iid not in by_image:
            original=read_js(SOURCE/'cases'/f'{iid}.js','window.REVIEW_CASE=')
            slot=len(cases);by_image[iid]=slot
            cases.append(dict(image_id=iid,title=r['image_code'],category='排序候选 · 共享x预处理基线',variants=[],annotation_ids=[]))
            url=data_image((OUT/original['image_src']).resolve(),texture=True);images[slot]=dict(original=url,texture=url)
        case=cases[by_image[iid]];case['variants'].append(variant);case['annotation_ids'].append(oid)
    if len(records)!=90 or len(cases)!=45 or len({r['object_id'] for r in records})!=90:raise ValueError('candidate_population_changed')
    baseline=dict(schema='order_preprocessed_source_v1',method='shared_x_periodic_shortest_arc_v1',objects=records)
    path=OUT/'preprocessed_source.json'
    if path.exists() and json.loads(path.read_text(encoding='utf-8'))!=baseline:raise ValueError('preprocessed_baseline_changed_requires_new_version')
    path.write_text(json.dumps(baseline,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'field_contract.json').write_text(json.dumps(dict(schema='order_review_20260928_v3',source_schema=baseline['schema'],
        primary_key='object_id',states=['draft','confirmed','pending','pairing'],
        pairing='点位匹配错误；独立后续审核，不作无效或已确认顺序',
        binding='object_id + preprocessed points + fixed point labels + complete links + preprocessing method',
        raw_mutation=False),ensure_ascii=False,indent=2),encoding='utf-8')
    return cases,images,records


def build_workspace(examples=False,candidates=False):
    """默认空台；十例作为独立验证样本，不接入正式排序队列。"""
    from .order_review_20260928 import resolve_links, screen_order
    from .shared_x_reanalysis_20260922 import shared_x
    out=ROOT/'analysis_results'/('order_acute_examples_20260928' if examples else 'order_studio_20260926')
    out.mkdir(exist_ok=True)
    cases=[]; images={}; selected=[]
    if candidates:
        cases,images,selected=candidate_workspace()
    elif examples:
        with (FINAL/'全量复核.csv').open(encoding='utf-8-sig') as f:ledger={r['canonical_annotation_id']:r for r in csv.DictReader(f)}
        index=read_js(SOURCE/'data.js','window.REVIEW_DATA=')
        for iid in sorted({r['image_id'] for r in index['rows']}):
            case=read_js(SOURCE/'cases'/f'{iid}.js','window.REVIEW_CASE=')
            candidates=[]
            for original in case['annotations']:
                cid=original['canonical_annotation_id'];r=ledger[cid]
                if r['cleaning_disposition']!='retained' or r['worker_quality_gate'] in {'hold_all_analysis','hold_main_analysis'}:continue
                if r['scene_category'] in {'oos','doorway_difficult','oos_stable_nonorthogonal'} or r['scene_oos_status']=='confirmed':continue
                points=json.loads(r['effective_points_1024x512']);labels=json.loads(r['effective_point_labels'])
                links,basis=resolve_links(original,points,labels)
                if not links or len(links)<=4:continue
                processed=shared_x(points,links).tolist(); floor=[]
                for a,b in links:
                    x,y=processed[b];u=2*math.pi*(x/1024-.5);v=math.pi*(.5-y/512)
                    if v>=-math.radians(.5):break
                    radius=-math.cos(v)/math.sin(v);floor.append([radius*math.sin(u),-1,-radius*math.cos(u)])
                if len(floor)!=len(links):continue
                pairs=[[processed[a],processed[b]] for a,b in links];metrics=screen_order(pairs,floor)
                if not metrics['consecutive_acute']:continue
                row=copy.deepcopy(original);row.update(effective_points_1024x512=points,links_zero_based=links)
                candidates.append((len(metrics['acute_vertices']),row,processed,labels,basis,metrics,r))
            if not candidates:continue
            _,row,processed,labels,basis,metrics,r=max(candidates,key=lambda x:x[0])
            variant=annotation_variant(row);source=variant['source']
            source.update(points=processed,effective_points=row['effective_points_1024x512'],effective_point_labels=labels,
                pairing_basis=basis,screening=metrics,queue='example',review={k:r[k] for k in ('current_decision_comment','image_comment','scene_category','trap_status','model_edit_status')})
            variant=geometry_variant(variant['name'],source,processed,row['links_zero_based'])
            slot=len(cases);cases.append(dict(image_id=iid,title=case['code'],category='连续锐角十例 · 原因待你判断',variants=[variant]))
            image_path=(out/case['image_src']).resolve();url=data_image(image_path,texture=True);images[slot]=dict(original=url,texture=url)
            selected.append(dict(image_id=iid,code=case['code'],annotation_id=row['canonical_annotation_id'],worker=row['worker_id'],metrics=metrics))
            if len(cases)==10:break
        if len(cases)!=10:raise ValueError('fewer_than_ten_acute_examples')
    else:
        cases=[dict(image_id='',title='尚未接入正式数据',category='点对拖拽工作台',variants=[dict(name='等待数据',error='正式数据未接入；可用下方演示试拖动。',source=dict(role='empty',points=[],original_point_ids_1based=[],links_zero_based=None))])]
    dataset=dict(cases=cases,counts=dict(cases=len(cases) if selected else 0,variants=len(selected)),manifest=dict(contract_version='consensus_research_20260923_v1',export_schema='order_review_20260928_v3' if candidates else 'order_review_20260928_v2',formal_data_connected=candidates,examples_only=examples))
    (out/'data.js').write_text('window.STUDIO_IMAGES='+encode(images)+';window.STUDIO_DATA='+encode(dataset)+';',encoding='utf-8')
    for name in ('studio.js','studio.css'):shutil.copy2(STUDIO/name,out/name)
    script=(out/'studio.js').read_text(encoding='utf-8')
    # 空台没有图像，跳过贴图加载；其余共享查看器保持原实现。
    script=script.replace('    const images=window.STUDIO_IMAGES[currentCase], img=new Image();', '    if(!window.STUDIO_IMAGES[currentCase]){ $("texture-state").textContent="未接入图片";return; }\n    const images=window.STUDIO_IMAGES[currentCase], img=new Image();')
    (out/'studio.js').write_text(script,encoding='utf-8')
    for name in ('three.min.js','OrbitControls.js'):shutil.copy2(STUDIO.parent/name,out/name)
    for suffix in ('js','css'):shutil.copy2(HERE/f'order_studio_20260926.{suffix}',out/f'order_studio.{suffix}')
    page=(STUDIO/'index.html').read_text(encoding='utf-8').replace('<title>空间标本 · 全景布局审查</title>','<title>点对拖拽排序</title>')
    page=page.replace('<link rel="stylesheet" href="studio.css">','<link rel="stylesheet" href="studio.css"><link rel="stylesheet" href="order_studio.css">')
    page=page.replace('<script defer src="studio.js"></script>','<script defer src="studio.js"></script><script defer src="order_studio.js"></script>')
    (out/'index.html').write_text(page,encoding='utf-8')
    (out/'MANIFEST.json').write_text(json.dumps(dict(dataset['manifest'],examples=selected),ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'README.md').write_text('# 点对拖拽排序\n\n正式数据未接入。十例页仅验证连续锐角是否有诊断价值，按图片ID顺序取前10张命中图，每图选尖角最多的一份；不是随机样本或已确认排序错误。\n\n移动完整点对，坐标不变；自动保存草稿，明确确认后单独导出JSON。模型行为、场景与清洗结论只读保留。\n',encoding='utf-8')
    if candidates:
        (out/'README.md').write_text('# 全部排序候选\n\n45图90对象：63份人员、21份原始GT、6份人工修订GT。只接入候选，未列入对象不是已确认顺序正确。\n\npreprocessed_source.json是本轮独立输入基线：最新有效点经周期共享x平均，y不变；平均前、原始导出、点标签、配对及修复证据分别保留。27份GT候选x本已相同。原始导出与GT文件不变。\n\n下一份遍历同图人员和GT；点位匹配错误单独记录后续审核，不自动重配、不作人员无效。v3记录绑定预处理点集；v2导入须匹配平均前点集、标签、配对与预处理后坐标，冲突拒绝覆盖。\n',encoding='utf-8')
    return dict(output=str(out),examples=len(selected))


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser();mode=parser.add_mutually_exclusive_group();mode.add_argument('--examples',action='store_true');mode.add_argument('--candidates',action='store_true');args=parser.parse_args()
    print(json.dumps(build_workspace(args.examples,args.candidates), ensure_ascii=False))
