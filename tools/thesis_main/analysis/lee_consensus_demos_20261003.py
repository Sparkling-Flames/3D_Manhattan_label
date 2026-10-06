"""真实 BEV 共识教学演示：确定性成员链、当前前缀重切 tile、保留失败与平票。"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import warnings

import numpy as np
from shapely.geometry import Polygon, mapping
from shapely.ops import unary_union

from .layout_display_projection import (
    projected_edge, region_projection, annotation_projection, compact_paths, project_display_record,
)
from .lee_tile_stage1_20261002 import ROOT, METHODS, tile_consensus, region_iou, write_json, write_csv
from .lee_tile_precision_20261003 import integration_basis, measure_masks, subset_mask

SOURCE = ROOT / 'analysis_results/lee_expanded_20261003'
OUT = ROOT / 'analysis_results/lee_consensus_demos_20261003'


def add_projection(demos, images):
    for demo in demos:
        image=images[demo['image']]; records={r['id']:r for r in image['annotations']}
        for worker in demo['workers']:
            record=records[worker['id']]
            if record['worker']!=worker['worker']: raise ValueError('display_worker_binding_mismatch')
            worker['erp']=project_display_record(record)
        demo['erp_references']={r['version']:project_display_record(r) for r in image['references'] if r['footprint'] is not None}
        for step in demo['steps']:
            step['erp_regions']={method:region_projection(step['regions'][method]) for method in METHODS}
            for regions in step['erp_regions'].values():
                for ring in regions: ring['paths']=compact_paths(ring['paths'])
    return dict(status='passed', workers=sum(len(d['workers']) for d in demos),
        max_floor_roundtrip_error_px=max(w['erp']['floor_roundtrip_max_px'] for d in demos for w in d['workers']),
        max_frozen_footprint_error_h=max(w['erp']['footprint_max_error_h'] for d in demos for w in d['workers']),
        coordinates='continuous 1024x512, +Y up, floor Y=-1, unchanged preprocessed points and stored ring order',
        top_boundary='Only individual and GT existing paired-top proxy curves; no fused top boundary is generated',
        visibility='All exterior/interior/component boundary segments projected; not claimed to be visible wall edges',
        sampling='65 samples per 3D edge piece; exact ERP seam crossing endpoints inserted. SVG display samples rounded to 0.001px; original points unchanged. Not metric computation.')


def add_pattern_views(demos, images, out):
    from .point_pattern_demo_20261003 import build_patterns
    from .erp_region_demo_20261003 import aggregate_records
    raw_regions={}; failures=[]; total_clusters=0
    for demo in demos:
        by_id={r['id']:r for r in images[demo['image']]['annotations']}
        demo['erp_region_cache']={}
        demo['point_projection_cache']={}
        def region_key(ids):
            key='|'.join(sorted(ids))
            if key not in demo['erp_region_cache']:
                raw=aggregate_records([by_id[i] for i in sorted(ids)],samples=512)
                raw_regions[demo['image']+':'+key]={k:v for k,v in raw.items() if k!='methods'}
                raw_regions[demo['image']+':'+key]['methods']={method:dict(threshold=value['threshold'],
                    top_support_min=min(value['top_support']),top_support_max=max(value['top_support']),
                    bottom_support_min=min(value['bottom_support']),bottom_support_max=max(value['bottom_support']))
                    for method,value in raw['methods'].items()}
                display={k:v for k,v in raw.items() if k!='methods'}
                display['methods']={method:dict(threshold=value['threshold'],
                    top_path=compact_paths([value['top_points']])[0],bottom_path=compact_paths([value['bottom_points']])[0])
                    for method,value in raw['methods'].items()}
                demo['erp_region_cache'][key]=display
            return key
        for step in demo['steps']:
            records=[by_id[i] for i in step['members']]
            views=build_patterns(records,thresholds=(5.,))
            step['all_erp_region_key']=region_key(step['members'])
            for view in views:
                view['threshold']=view['threshold_deg']
                view['label']=f"{view['threshold_deg']:g}°（演示阈值）"
                view['description']='同点数、整环对应后的上下端点最大球面角距；complete-link粗分，5°未校准。不同点数先分开，也可能拆开共线冗余点；不是自然标法数量。'
                view['clusters'].sort(key=lambda c:c['id'])
                for cluster in view['clusters']:
                    total_clusters+=1
                    cluster['erp_region_key']=region_key(cluster['members'])
                    candidate=cluster['candidate']
                    candidate['erp_key']=cluster['erp_region_key']
                    if candidate['points'] is not None and candidate['footprint'] is not None:
                        try:
                            if candidate['erp_key'] not in demo['point_projection_cache']:
                                demo['point_projection_cache'][candidate['erp_key']]=project_display_record(candidate)
                        except ValueError as exc:
                            failures.append(dict(image=demo['image'],k=step['k'],threshold=view['threshold_deg'],cluster=cluster['id'],reason=str(exc)))
                            candidate['display_reason']=str(exc)
                    cluster['description']=f"支持 {cluster['support']}/{step['k']} 人；{cluster['pair_count']} 点对；簇内最大角距 {cluster['diameter_deg']:.3f}°。先整环对齐，再对周期x、top_y、bottom_y分别取中位数；每个中心由对应观测估计，不代表原始坐标相同。"
                    candidate['note']='点中心候选状态：'+candidate['status']+('；原因：'+str(candidate['reason']) if candidate.get('reason') else '')+'。不是Lee完整输出。新候选环尚未经人工确认；显示曲线沿用墙顶代理。'
            step['pattern_views']=views
    write_json(out/'erp_region_results.json',raw_regions)
    summary=dict(schema='demo_pattern_views_v1',status='completed',thresholds_deg=[5.],
        cluster_instances=total_clusters,erp_region_groups=len(raw_regions),
        erp_unsupported=sum(v['status']!='ok' for v in raw_regions.values()),projection_failures=failures,
        semantics='Whole-annotation pattern clusters; preserve all clusters. Not worker classes or cross-count corner identity clustering. Cluster IDs are local to each current k, not longitudinal mode identities.',
        points='Aligned cyclic x/top_y/bottom_y medians per cluster; full independent pair points, not Lee.',
        erp='Direct ERP dense wall-band majority only on declared applicable rings; any unsupported member blocks that group.',
        gt_used_in_clustering_or_fusion=False)
    write_json(out/'pattern_checks.json',summary)
    return summary


def save_display(demos, images, checks, out):
    projection_checks=add_projection(demos,images)
    add_pattern_views(demos,images,out)
    write_json(out/'projection_checks.json',projection_checks)
    write_json(out/'demos.json',demos)
    contract=json.loads((out/'field_contract.json').read_text(encoding='utf-8'))
    contract['erp_display']='Existing preprocessed 1024x512 continuous points and stored ring order unchanged; raw source point/pair indices preserved. Fusion projects all ground polygon rings/components; no fused ceiling. SVG curve samples alone rounded to 0.001px, original corners and metric geometries remain full precision.'
    contract['pattern_views']='Separate teaching branch: whole-annotation complete-link by spherical ring distance, uncalibrated 5 degree split; different pair counts separated, possibly including collinear redundancy. Every cluster preserved, not natural mode counting. Cluster IDs local to current k only. Viewing a cluster does not change current k or saved Lee curves. Within-cluster circular-x/top_y/bottom_y medians are full-precision point candidates, not Lee output. No new GT quality validation.'
    contract['erp_region_views']='Direct ERP majority on eligible whole rings, 512 column samples. erp_region_results.json stores state and support summaries; demo stores display-only SVG paths rounded to 0.001px. Core aggregate_records returns full-precision dense curves for reproduction. Unsupported current members block the whole selected group. No sparse corner recovery or new quality validation.'
    write_json(out/'field_contract.json',contract)
    embedded=json.dumps(demos,ensure_ascii=False,allow_nan=False).replace('</','<\\/')
    (out/'index.html').write_text(HTML.replace('__DATA__',embedded),encoding='utf-8',newline='\n')
    report(demos,checks,out)


def build_case(records, references):
    """展示计算全由当前成员重新切片；全池基底仅用于事后交叉核验。"""
    if records != sorted(records, key=lambda r: r['id']):
        raise ValueError('demo_requires_record_id_order')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always', RuntimeWarning)
        basis = integration_basis(records, references)
    notices = [dict(stage='offline_basis', message=s) for s in basis['warnings']]
    notices.extend(dict(stage='offline_basis_evaluation', message=str(w.message)) for w in caught)
    steps = []; max_geometry = 0.; max_iou = 0.
    for k in range(1, len(records) + 1):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always', RuntimeWarning)
            current = tile_consensus(records[:k])
            notices.extend(dict(stage='current_tiling', k=k, message=s) for s in current['warnings'])
            counts = current['mesh']['votes'].sum(axis=0)
            tie = unary_union([tile for tile, s in zip(current['mesh']['tiles'], counts) if 2*s == k])
            step = dict(k=k, members=[r['id'] for r in records[:k]],
                        tiles=[dict(geometry=mapping(t), support=int(s)) for t, s in zip(current['mesh']['tiles'], counts)],
                        tile_count=len(counts), tie_geometry=mapping(tie), tie_area_h2=float(tie.area),
                        regions={}, metrics={})
            for method in METHODS:
                region = current['regions'][method]
                offline_counts = basis['mesh']['votes'][:k].sum(axis=0)
                selected = 2*offline_counts >= k if method == 'mv50' else 2*offline_counts > k
                offline = unary_union([t for t, keep in zip(basis['mesh']['tiles'], selected) if keep])
                geometry_error = float(region.symmetric_difference(offline).area)
                if geometry_error > 1e-9 * max(1., float(basis['area'].sum())):
                    raise ValueError('current_prefix_geometry_mismatch')
                max_geometry = max(max_geometry, geometry_error)
                measured = measure_masks(basis, np.array([subset_mask(range(k))], dtype=np.uint32), k, method)
                step['regions'][method] = mapping(region)
                step['metrics'][method] = {}
                for version, gt in basis['references'].items():
                    iou = region_iou(region, gt)
                    error = abs(iou - float(measured[version][0]))
                    if error > 1e-10:
                        raise ValueError('current_prefix_iou_mismatch')
                    max_iou = max(max_iou, error)
                    step['metrics'][method][version] = dict(iou=iou, area_h2=float(region.area),
                        omission_h2=float(gt.difference(region).area), extension_h2=float(region.difference(gt).area),
                        empty=region.is_empty)
            notices.extend(dict(stage='evaluation', k=k, message=str(w.message)) for w in caught)
            steps.append(step)
    return dict(steps=steps, warnings=notices, checks=dict(prefixes_rebuilt=len(records),
        region_comparisons=2*len(records), max_geometry_difference_h2=max_geometry, max_iou_difference=max_iou))


def choose_examples(curves):
    rows = [r for r in curves if r['version'] == 'original' and r['method'] == 'mv50'
            and int(r['k']) == int(r['n']) and int(r['n']) >= 8]
    rows.sort(key=lambda r: (float(r['gain_from_one']), r['image']))
    strict = {r['image']: r for r in curves if r['version'] == 'original' and r['method'] == 'mv_strict'
              and int(r['k']) == int(r['n'])}
    even = [r for r in rows if int(r['n']) % 2 == 0]
    tie = max(even, key=lambda r: (abs(float(r['iou_mean'])-float(strict[r['image']]['iou_mean'])), r['image']))
    return [(rows[-1], '较大改善', 'N≥8图中全员MV50减全池单人均值最大'),
            (rows[len(rows)//2], '增益中位附近', 'N≥8图按同一增益排序取上中位；不代表所有属性典型'),
            (rows[0], '接近参考变差', 'N≥8图中全员MV50减全池单人均值最小'),
            (tie, '平票规则敏感', 'N≥8且N为偶数，取全员两规则原参考IoU绝对差最大')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--refresh-display', action='store_true', help='仅补充ERP展示，不重算tile或指标')
    args = parser.parse_args(); out = args.out
    if args.refresh_display:
        data=json.loads((SOURCE/'input.json').read_text(encoding='utf-8'))
        images={r['code']:r for r in data['images']}
        demos=json.loads((out/'demos.json').read_text(encoding='utf-8'))
        checks=json.loads((out/'checks.json').read_text(encoding='utf-8'))
        before=(out/'metrics.csv').read_bytes()
        save_display(demos,images,checks,out)
        if (out/'metrics.csv').read_bytes()!=before: raise ValueError('display_refresh_modified_metrics')
        print('ERP display refreshed; metrics.csv unchanged',flush=True)
        return
    if out.exists():
        raise ValueError('use_new_output_directory')
    out.mkdir(parents=True)
    data = json.loads((SOURCE/'input.json').read_text(encoding='utf-8'))
    rosters = {r['image']: r for r in json.loads((SOURCE/'rosters.json').read_text(encoding='utf-8'))}
    images = {r['code']: r for r in data['images']}
    with (SOURCE/'image_curves.csv').open(encoding='utf-8-sig', newline='') as stream:
        curves = list(csv.DictReader(stream))
    selection = choose_examples(curves)
    write_json(out/'design.json', dict(schema='lee_consensus_demos_v1', status='started',
        input='analysis_results/lee_expanded_20261003/input.json',
        source_binding='analysis_results/lee_expanded_20261003/source_binding.json',
        selection=[dict(image=r['image'], purpose=title, reason=reason) for r,title,reason in selection],
        member_chain='Ascending fixed record ID; never searched for best chain. User-confirmed independent repeated geometry retains separate votes.',
        interpretation='Post-outcome teaching examples, not an unbiased estimate of fusion benefit.',
        no_new_preprocessing=True, gt_used_in_votes=False))
    demos = []; rows = []; notices = []; failures = []
    for chosen, title, reason in selection:
        code = chosen['image']; image = images[code]; roster = rosters[code]
        by_id = {r['id']: r for r in image['annotations']}
        records = [by_id[i] for i in roster['record_ids']]
        if [r['worker'] for r in records] != roster['workers']:
            raise ValueError('roster_worker_binding_mismatch:'+code)
        references = {r['version']: r['footprint'] for r in image['references']}
        try:
            case = build_case(records, references)
        except Exception as exc:
            failures.append(dict(image=code, error=type(exc).__name__+': '+str(exc), roster_n=len(records)))
            write_json(out/'failures.json', failures)
            raise
        notices.extend(dict(image=code, **w) for w in case.pop('warnings'))
        gts = {v: Polygon(p) for v,p in references.items() if p is not None}
        full = case['steps'][-1]
        full_difference = abs(full['metrics']['mv50']['original']['iou']-float(chosen['iou_mean']))
        singles = [region_iou(Polygon(r['footprint']), gts['original']) for r in records]
        original_rows = [r for r in curves if r['image'] == code and r['version'] == 'original']
        baseline = next(float(r['iou_mean']) for r in original_rows if r['method']=='mv50' and int(r['k'])==1)
        if full_difference > 1e-10 or abs(float(np.mean(singles))-baseline) > 1e-10:
            raise ValueError('saved_A_line_endpoint_mismatch:'+code)
        photo = ROOT/'data/mp3d_layout/test/img'/(image['image_id']+'.png')
        photo_rel = os.path.relpath(photo, out).replace('\\', '/') if photo.exists() else None
        demo = dict(image=code, title=title, selection_reason=reason, n=len(records), difficulty=image['difficulty'],
            building=image['building'], scene=image['scene'], photo=photo_rel,
            photo_source=photo.relative_to(ROOT).as_posix() if photo.exists() else None,
            references={v:mapping(g) for v,g in gts.items()},
            workers=[dict(id=r['id'], worker=r['worker'], geometry=mapping(Polygon(r['footprint'])),
                original_iou=score, order_status=r['order_status'], ring_confirmed=r['ring_confirmed']) for r,score in zip(records,singles)],
            single_mean=baseline, single_best=max(singles), full_gain=float(chosen['gain_from_one']),
            mean_curve=[dict(k=int(r['k']), method=r['method'], iou=float(r['iou_mean']),
                mc_error=float(r['mc_error_bound']), estimator=r['estimator']) for r in original_rows], **case)
        for step in case['steps']:
            for method in METHODS:
                for version, metrics in step['metrics'][method].items():
                    rows.append(dict(image=code, k=step['k'], method=method, version=version,
                        members='|'.join(step['members']), tile_count=step['tile_count'], tie_area_h2=step['tie_area_h2'], **metrics))
        demos.append(demo)
        print(code, 'prefixes', len(case['steps']), 'full gain', chosen['gain_from_one'], flush=True)
    write_json(out/'demos.json', demos); write_csv(out/'metrics.csv', rows)
    write_json(out/'warnings.json', notices); write_json(out/'failures.json', failures)
    checks = dict(status='passed', examples=len(demos), prefixes=sum(d['n'] for d in demos),
        region_comparisons=sum(d['checks']['region_comparisons'] for d in demos),
        max_geometry_difference_h2=max(d['checks']['max_geometry_difference_h2'] for d in demos),
        max_iou_difference=max(d['checks']['max_iou_difference'] for d in demos),
        warnings=len(notices), failures=len(failures), source_status='Reused frozen source binding and roster; no raw resubmission audit',
        visual_status='Panoramas provided for inspection; no new visual GT adjudication')
    write_json(out/'checks.json', checks)
    write_json(out/'field_contract.json', dict(schema='lee_consensus_demos_v1',
        metrics_fields=list(rows[0]), coordinates='Common camera BEV X,Z in h units; area h². Equal aspect and per-image fixed extent.',
        chain='Nested prefixes of ascending record IDs; deterministic teaching replay, not average/optimal chain.',
        mean_curve='Unchanged A-line uniform-member-set mean; exact or 16384-draw MC marked individually. Not this chain.',
        tie='Area supported by exactly k/2 current members; MV50 retains it and strict majority omits it.',
        photos='Local original PNGs referenced by repository-relative paths; copied demo folder alone is insufficient for photographs.',
        failures='No failed member is dropped; error stops calculation and writes failures.json.',
        selection='Post-outcome selection from N>=8 A-line images for illustration; no inference across these four examples.'))
    (out/'index.html').write_text(HTML.replace('__DATA__', json.dumps(demos, ensure_ascii=False, allow_nan=False).replace('</', '<\\/')), encoding='utf-8', newline='\n')
    save_display(demos, images, checks, out)
    design = json.loads((out/'design.json').read_text(encoding='utf-8')); design['status']='completed'; write_json(out/'design.json', design)


def report(demos, checks, out):
    lines = ['# 标法分组与融合候选：四个真实数据演示', '',
        '主展示已调整为：先看同图的整份标法簇，再看选中簇的完整上下点中心候选或直接ERP区域多数轮廓。原有Lee-BEV等权区域投票保留为折叠对照；其历史数值与成员资格没有改变。GT不参与任何一条分组／候选／投票构造。', '',
        '## 演示内容与选例', '',
        '打开[index.html](index.html)，首先显示当前k人全部标法簇的代表缩略图和支持人数；选簇后左侧为代表与同簇成员，右侧可切完整上下点中心／ERP上下稠密轮廓。逐人检查放在展开项。原角点、确认环／默认环与源索引保持冻结输入原值。', '',
        '整份标法分组：同点对数、允许周期起点／反向对应的上下端点最大球面角距离，complete-link，固定5°未校准阈值。不同点数先分开，可能把共线冗余点也分成不同组；分组数量不是自然标法数量。簇号仅对当前k有效；查看簇不改变k、全体投票或原人数曲线。',
        '点中心候选：在各簇内部保持整环对应，周期x、top_y、bottom_y分别取中位数，直接产生完整点对；保留所有簇，不选最大簇或用GT选优。点中心观测数是参与估计的人数，不是恰好落在新中心坐标的票数。全员存在多个标法时并列保留多个候选，不强行合成唯一layout。新候选未经GT质量验证。',
        '直接ERP区域多数：在原环能表示为每列单段、绕一周且上下跨共同地平线的适用域中，512列采样投票，输出上下稠密轮廓。保留原环与曲线；任何当前成员不适用则整组unsupported，不删人、重排或取可见包络。该输出不是稀疏角点恢复，也不是已经验证质量提升。',
        '**Lee-BEV对照仍仅输出融合底边。** 它不输出上角点或天花板；不以平均高度编造完整标注。所有外环、孔洞和断片都保留，不只取最大分量，也不把几何边断言为可见墙边。',
        '显示曲线复用`panorama_studio.geometry.pixel_ray/project_pixel`的continuous 1024×512约定，+Y向上、地面Y=-1。沿既定环将三维直边投回ERP，跨接缝分段；单体顶部沿用已配对底点的水平距离重建墙顶代理，不假设所有顶点平顶。角点仍直接使用输入原值。65点采样只服务显示，不改BEV或IoU。', '',
        '**按既有结果选例用于解释，不能当作四图总体效果估计。** 最大／中位／最小增益均在已有A线N≥8图片中，以全员MV50减全池单人均值选出；平票例取偶数N中两规则全员IoU差最大。成员按固定R编号升序进入，未搜索有利链。图中的细虚线是这条链，粗实线是已有成员集合均值，二者不可混用。', '',
        '| 目的 | 图片 | N | 全池单人均值 | 全员MV50 | 全员严格多数 | MV50增益 | 最好单人 |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for d in demos:
        m=d['steps'][-1]['metrics']
        lines.append(f"| {d['title']} | {d['image']} | {d['n']} | {d['single_mean']:.6f} | {m['mv50']['original']['iou']:.6f} | {m['mv_strict']['original']['iou']:.6f} | {d['full_gain']:+.6f} | {d['single_best']:.6f} |")
    lines += ['', '## 实测结果能说明什么', '',
        '- 当前真实输入的每个前缀都重新切tile，并与全池细分积分在形状和IoU上对照。计算正确性与质量提升是两件事；上表同时保留改善、下降和平票敏感例。',
        '- 不要求超过最好单人；最好单人需事后GT才能识别。若声称融合比随机单人好，应使用全池单人均值及完整图片面板，不能只拿链的第一个人作基线。',
        '- MV50奇→偶只能扩张、偶→奇只能收缩，严格多数相反；IoU如何变化仍取决于扩张／收缩位置。原始曲线不平滑。',
        '- 重复几何按用户确认的独立作答保留，不合并票、不更改人员资格。确认环保留，其余沿用已有共享x默认环，不重新预处理。',
        '- 融合算法已足以开展当前区域共识实验；当前结果没有证明它是最优融合、完整3D重建或自动标注替代，也没有证明加人必然更好。', '',
        '## 验证与追溯', '',
        f"本轮重新切片 {checks['prefixes']} 个前缀、核对 {checks['region_comparisons']} 个规则输出；最大形状对称差 {checks['max_geometry_difference_h2']:.3g} h²，最大IoU差 {checks['max_iou_difference']:.3g}。警告 {checks['warnings']} 条，失败 {checks['failures']} 条，均独立保存。四图k=1均值及全员MV50与既有A线结果一致。",
        '输入复用[冻结面板](../lee_expanded_20261003/input.json)、[来源绑定](../lee_expanded_20261003/source_binding.json)、[成员表](../lee_expanded_20261003/rosters.json)。本轮未重新审计原始提交链。',
        '来源、选例及固定链见design.json、demos.json；逐前缀机器指标见metrics.csv，核验见checks.json，字段见field_contract.json。每份作答的确认状态、人员ID和记录ID随演示保留。',
        '复现：`python -B -m tools.thesis_main.analysis.lee_consensus_demos_20261003 --out analysis_results/<新的目录>`。已有目录拒绝覆盖。',
        '仅刷新ERP展示：`python -B -m tools.thesis_main.analysis.lee_consensus_demos_20261003 --refresh-display`。保留既有metrics.csv字节；新增投影核验见projection_checks.json。单人身份、原点回环、接缝和孔洞投影有定向测试。',
        '新增分组状态见pattern_checks.json；直接ERP各独立成员组的支持摘要／不适用状态见erp_region_results.json。稀疏候选点以全精度保存，稠密曲线仅保留0.001px显示SVG及支持摘要；核心aggregate_records可返回全精度采样结果。',
        '相关测试：`python -B -m pytest tests/test_lee_consensus_demos_20261003.py tests/test_point_pattern_demo_20261003.py tests/test_erp_region_demo_20261003.py tests/test_lee_tile_stage1_20261002.py tests/test_lee_tile_precision_20261003.py -q -p no:cacheprovider`。', '',
        '| 图片 | 当前全员整份标法组数（5°演示） | 各组人数 | 全员直接ERP状态 |', '|---|---:|---|---|']
    for d in demos:
        end=d['steps'][-1]; groups=end['pattern_views'][0]['clusters']; state=d['erp_region_cache'][end['all_erp_region_key']]['status']
        lines.append(f"| {d['image']} | {len(groups)} | {'、'.join(str(c['support']) for c in groups)} | {state} |")
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n', encoding='utf-8', newline='\n')


HTML = r'''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>标法分组与融合候选 · 四例实测</title>
<style>
:root{font-family:system-ui,"Microsoft YaHei",sans-serif;color:#17293d;background:#f3f6fa}body{max-width:1320px;margin:24px auto;padding:0 20px}h1{font-size:26px;margin:0 0 6px}h2{font-size:18px;margin:0 0 12px}p{line-height:1.65}small,.muted{color:#53667b}button,select,input{font:inherit}button,select{border:1px solid #b9c6d4;background:white;border-radius:7px;padding:8px 11px}button{cursor:pointer}button[aria-pressed=true]{background:#173f68;color:white}nav{display:flex;gap:9px;flex-wrap:wrap;margin:18px 0}.box{background:white;border:1px solid #dee5ee;border-radius:12px;padding:18px;margin:14px 0}.controls{display:flex;gap:18px;align-items:center;flex-wrap:wrap}.controls label{white-space:nowrap}input[type=range]{width:230px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.stat{background:#f3f6fa;border-radius:8px;padding:12px}.stat b{display:block;font-size:24px;margin:5px 0}.warning{border-left:4px solid #bb7833;padding:9px 14px;background:#fff8ed}svg{width:100%;height:auto;display:block}#bev{background:#fafbfd;border:1px solid #e8edf3;border-radius:8px}#photo{width:100%;display:block;border-radius:8px}a{color:#175f9a}details{line-height:1.7}#members{font-family:ui-monospace,monospace;font-size:12px;overflow-wrap:anywhere}#curve text{font:12px system-ui}.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:13px;margin:10px 0}.key:before{content:"";display:inline-block;width:20px;height:3px;background:var(--c);vertical-align:middle;margin-right:5px}@media(max-width:850px){.grid{grid-template-columns:1fr}.stats{grid-template-columns:1fr 1fr}}
</style>
<style>.pattern-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(235px,1fr));gap:12px}.pattern-card{padding:10px;text-align:left;min-width:0}.pattern-card svg{border-radius:5px;margin:8px 0}.pattern-card b,.pattern-card small{display:block}.pattern-card[aria-pressed=true]{background:#eef7fa;color:#173f68;border:2px solid #287590}.pattern-card[aria-pressed=true] small{color:#395d76}#patternmeta{overflow-wrap:anywhere}</style>
<header><h1>标法分组与融合候选 · 四例实测</h1><p class="muted">先看同一图片有哪些整份标法，再分别检查簇内完整上下角点候选。全员 Lee 底面投票保留为次级对照。</p></header>
<div class="warning">这四例按既有结果选出，用于解释改善、下降和平票。它们不是整体效果估计；固定进入顺序也不是最优成员链。</div>
<nav id="cases" aria-label="选择真实案例"></nav>
<section class="box"><h2 id="title"></h2><p id="context" class="muted"></p>
<div class="controls"><label for="k">当前人数 <b id="klabel"></b></label><input id="k" type="range" min="1" value="1" step="1" aria-label="当前人数"><button id="full">全员</button><label>整份标法分簇阈值 <select id="threshold" disabled></select></label></div>
<div class="controls" style="margin-top:12px"><label><input id="showgt" type="checkbox" checked>叠加GT</label><label><input id="showpoints" type="checkbox" checked>显示上下角点</label><label><input id="showall" type="checkbox" checked>叠加当前簇成员</label></div>
</section>
<section class="box"><h2>1 · 当前图片的整份标法簇</h2><p id="patternmeta" class="muted"></p><div id="patterns" class="pattern-grid"></div><p class="muted">每张卡片是一簇整份作答，不是人员类型或角点身份簇。全部簇保留；默认展开第一簇便于查看，不表示算法选优。簇号仅在当前人数内有效，改变k会重新分组；查看某簇不改变全员人数或既有Lee曲线。</p></section>
<section class="box"><h2 id="patterntitle">2 · 查看当前簇的完整上下候选</h2><p id="candidateinfo" class="muted"></p><div class="controls"><label>右图方法 <select id="candidateMethod"><option value="point">点中心候选 · 上下角点</option><option value="erp">ERP区域多数 · 上下稠密轮廓</option></select></label><label>右图范围 <select id="candidateScope"><option value="cluster">当前选簇</option><option value="all">全部当前人员</option></select></label><label>ERP规则 <select id="erpRule"><option value="mv50">≥50%</option><option value="mv_strict">严格 &gt;50%</option></select></label></div><details><summary>展开：逐人检查当前簇</summary><label>单体 <select id="person"></select></label> <span id="personscore"></span></details></section>
<div class="grid"><section class="box"><h2 id="originaltitle">簇代表与同簇成员</h2><svg id="annotationpano" viewBox="0 0 1024 512" role="img" aria-label="标法簇代表及同簇成员原上下角点与连线"></svg><div class="legend"><span class="key" style="--c:#f6d25b">上角点与顶边</span><span class="key" style="--c:#71f0c1">下角点与底边</span><span class="key" style="--c:#fb8ef0">GT虚线</span></div><small>人员点直接来自冻结的已预处理坐标，保留既定环；顶部显示沿用配对底点水平距离的墙顶代理，不声明平顶。</small></section><section class="box"><h2 id="righttitle">簇内完整上下中心候选</h2><svg id="fusionpano" viewBox="0 0 1024 512" role="img" aria-label="标法簇的完整上下候选或直接ERP融合轮廓"></svg><div class="legend"><span class="key" style="--c:#f6d25b">候选上边</span><span class="key" style="--c:#00ffe5">候选下边</span><span class="key" style="--c:#fb8ef0">GT虚线</span></div><small id="fusionnote"></small></section></div>
<div class="warning">点中心是簇内对应后的上下角点估计；直接 ERP 区域多数给出上下稠密轮廓，两者都不等于已确认的完整 layout。多簇全员点模式展示全部簇候选；不硬合成单一标法。GT仅作叠加参照。</div>
<details class="box"><summary>3 · 次级对照：当前k人 Lee-BEV底面对照</summary><div class="controls"><label>Lee规则 <select id="method"><option value="mv50">MV50 · ≥50%</option><option value="mv_strict">严格多数 · &gt;50%</option></select></label></div><p class="muted">这里仍对当前k人的全部区域等权投票，与上方选中簇及完整中心候选分开。GT不参与两种输出的构造。</p>
<div class="stats" style="margin-top:16px"><div class="stat">当前链：Lee共识 IoU<b id="iou"></b><small id="delta"></small></div><div class="stat">另一规则 IoU<b id="other"></b><small id="gap"></small></div><div class="stat">遗漏 / GT面积<b id="omit"></b><small>GT内未覆盖</small></div><div class="stat">外扩 / GT面积<b id="extra"></b><small>GT外增加范围</small></div></div><svg id="leepano" viewBox="0 0 1024 512" role="img" aria-label="全员Lee底边对照"></svg><small id="leenote"></small>
<div class="grid"><section class="box"><h2>BEV：当前共识与成员</h2><div class="controls"><label><input id="showtiles" type="checkbox">支持率 tile</label><label><input id="showtie" type="checkbox">平票区域</label></div><svg id="bev" viewBox="0 0 580 500" role="img" aria-label="同坐标比例BEV叠加"></svg><div class="legend"><span class="key" style="--c:#192f47">GT虚线</span><span class="key" style="--c:#087e8b">融合</span><span class="key" style="--c:#8298af">当前成员</span><span class="key" style="--c:#d6533d">选中单体</span><span class="key" style="--c:#dd950a">平票</span></div><small id="geometrynote"></small></section>
<section class="box"><h2>人数曲线：均值与一条成员链</h2><svg id="curve" viewBox="0 0 580 350" role="img" aria-label="均值与固定成员链的IoU人数曲线"></svg><div class="legend"><span class="key" style="--c:#087e8b">MV50</span><span class="key" style="--c:#bd5f25">严格多数</span></div><p class="muted">粗实线：已有均匀成员集合均值；细虚线：本演示固定链。淡带仅为均值的计算误差界。固定链每一步是精确计算；不是均值，更不表示一般加入顺序。</p><p id="meanvalue"></p><details><summary>成员与计算追溯</summary><p id="members"></p><p id="verification"></p></details></section></div>
</details>
<details class="box"><summary>查看没有叠加的原全景图</summary><img id="photo" alt="当前案例原始全景图"><p class="muted">本地原图按 image_id 对应。本页未重新裁决 GT 的视觉正确性。图片需保留仓库 data 目录。</p></details>
<section class="box"><h2>如何判断“有效”</h2><p>计算层面：每个当前前缀重新切 tile，对照全池积分的形状和 IoU。研究层面：看相对全池单人均值的收益，并保留下降与平票敏感结果。融合不保证超过最好单人、不保证人数增加时单调改善，也不等于完整 layout 或三维质量。</p><p><a href="REPORT.md">中文报告</a> · <a href="metrics.csv">逐步指标 CSV</a> · <a href="checks.json">实测核验</a> · <a href="demos.json">完整几何与来源</a> · <a href="warnings.json">警告</a></p></section>
<script>
const DATA=__DATA__;
for(const d of DATA)for(const s of d.steps)for(const v of s.pattern_views)for(const c of v.clusters)c.candidate.erp=d.point_projection_cache[c.candidate.erp_key]||null;
const $=id=>document.getElementById(id), NS='http://www.w3.org/2000/svg';let selected=0,activePattern='';
function elt(tag,attrs,text){const e=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs))e.setAttribute(k,v);if(text!=null)e.textContent=text;return e}
function rings(g){if(g.type==='Polygon')return g.coordinates;if(g.type==='MultiPolygon')return g.coordinates.flat();if(g.type==='GeometryCollection')return g.geometries.flatMap(rings);return[]}
function area(g){const absRing=r=>Math.abs(r.reduce((s,p,i)=>s+p[0]*r[(i+1)%r.length][1]-r[(i+1)%r.length][0]*p[1],0))/2;const poly=r=>r.length?absRing(r[0])-r.slice(1).reduce((s,x)=>s+absRing(x),0):0;return g.type==='Polygon'?poly(g.coordinates):g.type==='MultiPolygon'?g.coordinates.reduce((s,p)=>s+poly(p),0):0}
function path(g,project){return rings(g).map(r=>r.map((p,i)=>(i?'L':'M')+project(p).join(',')).join(' ')+'Z').join(' ')}
function polygon(svg,g,project,attrs){svg.append(elt('path',{d:path(g,project),'fill-rule':'evenodd',...attrs}))}
function erpLines(svg,paths,color,dash=false){for(const d of paths){svg.append(elt('path',{d,fill:'none',stroke:'#101a27','stroke-width':5,opacity:.65}));svg.append(elt('path',{d,fill:'none',stroke:color,'stroke-width':2.5,'stroke-dasharray':dash?'9 7':''}))}}
function erpDot(svg,p,color,label){svg.append(elt('circle',{cx:p[0],cy:p[1],r:4,fill:color,stroke:'#102032','stroke-width':1.3}));if(label)svg.append(elt('text',{x:p[0]+6,y:p[1]-6,fill:color,stroke:'#102032','stroke-width':2,'paint-order':'stroke','font-size':15},label))}
function panoBase(svg,d){svg.replaceChildren();svg.append(elt('image',{href:d.photo,x:0,y:0,width:1024,height:512,preserveAspectRatio:'none'}))}
function layoutLines(svg,a,bottom='#71f0c1',labels=true){erpLines(svg,a.vertical_paths,'#f0f7ff');erpLines(svg,a.top_paths,'#f6d25b');erpLines(svg,a.bottom_paths,bottom);if($('showpoints').checked)a.points.forEach((p,i)=>erpDot(svg,p,i%2?bottom:'#f6d25b',labels?String(Math.floor(i/2)+1):''))}
function patternView(d,s){const view=s.pattern_views.find(v=>String(v.threshold)===$('threshold').value)||s.pattern_views[0];if(!view.clusters.some(c=>c.id===activePattern))activePattern=view.clusters[0].id;const cluster=view.clusters.find(c=>c.id===activePattern);$('patternmeta').textContent=`当前 ${s.k} 人 → ${view.clusters.length} 个整份标法簇。${view.description}`;$('patterns').replaceChildren();for(const c of view.clusters){const b=document.createElement('button');b.className='pattern-card';b.setAttribute('aria-pressed',String(c.id===activePattern));const title=document.createElement('b');title.textContent=`${c.id} · ${c.members.length}/${s.k} 人（${(100*c.members.length/s.k).toFixed(1)}%）`;b.append(title);const thumb=elt('svg',{viewBox:'0 0 1024 512','aria-label':c.id+'代表标注'});panoBase(thumb,d);const rep=d.workers.find(w=>w.id===c.representative);layoutLines(thumb,rep.erp,'#71f0c1',false);b.append(thumb);const sub=document.createElement('small');sub.textContent=`代表 ${rep.worker} / ${rep.id} · ${rep.erp.points.length/2} 点对`;b.append(sub);b.onclick=()=>{activePattern=c.id;$('person').value='';render()};$('patterns').append(b)}return cluster}
function drawCandidatePanel(d,s,cluster,right){
const all=$('candidateScope').value==='all',point=$('candidateMethod').value==='point';$('erpRule').disabled=point;
if(point){const view=s.pattern_views.find(v=>String(v.threshold)===$('threshold').value)||s.pattern_views[0],cs=all?view.clusters:[cluster];$('righttitle').textContent=all?`全部 ${cs.length} 个簇的上下候选（并列叠加）`:'当前簇的完整上下中心候选';const palette=['#00ffe5','#77d9ff','#ffa98b','#cff285','#d7b5ff','#ffffff'];cs.forEach((c,i)=>{if(c.candidate.erp)layoutLines(right,c.candidate.erp,palette[i%palette.length],cs.length===1);else if(c.candidate.points&&$('showpoints').checked)c.candidate.points.forEach((p,j)=>erpDot(right,p,j%2?palette[i%palette.length]:'#f6d25b',''))});$('fusionnote').textContent=all?((cs.length>1?`保留 ${cs.length} 个整份标法候选，没有产生跨簇唯一结果。`:'当前只有一簇，显示该簇候选。')+`各簇人数：${cs.map(c=>c.support).join('、')}。中心由对应观测取中位数，不表示原始点恰好重合。`):(cluster.candidate.note+(cluster.candidate.status==='unavailable'?' 未生成中心。':` 每个中心的观测人数：${cluster.candidate.point_support_counts.join('、')}。`));}
else{const result=d.erp_region_cache[all?s.all_erp_region_key:cluster.erp_region_key];$('righttitle').textContent=(all?'全部当前人员':'当前簇')+' · ERP区域多数';if(result.status==='ok'){const m=result.methods[$('erpRule').value];erpLines(right,[m.top_path],'#f6d25b');erpLines(right,[m.bottom_path],'#00ffe5');$('fusionnote').textContent=`直接在ERP墙带投票；${result.n}人、支持阈值${m.threshold}人、${result.samples}列。上下稠密轮廓，不是恢复稀疏角点，不补造点对。`;}
else{right.append(elt('text',{x:25,y:50,fill:'#fff',stroke:'#101a27','stroke-width':3,'paint-order':'stroke','font-size':25},'该组不满足直接ERP区域方法的适用条件'));const names={original_ring_not_single_valued_one_turn:'原环不是单值绕行，不能表示为每列一段墙带',zero_or_half_circle_edge_longitude_span:'原边有零跨度或半周歧义',boundaries_must_strictly_straddle_horizon_away_from_poles:'上下边界未严格跨越地平线或接近极点',top_bottom_not_shared_longitude:'上下点对经度不同',missing_or_multiple_column_branches:'部分列缺失或存在多支边界'};$('fusionnote').textContent='整组不可用，未删除人员后继续：'+result.unsupported.map(r=>r.id+'：'+(names[r.reason]||'原环不满足该墙带表示条件')).join('；')+'。原始状态码见erp_region_results.json。';}}
}
function panoramas(d,s,method,chosen,cluster){
const left=$('annotationpano'),right=$('fusionpano'),lee=$('leepano');for(const svg of[left,right,lee])panoBase(svg,d);
if($('showall').checked){const group=elt('g',{opacity:.28});for(const w of d.workers.filter(w=>cluster.members.includes(w.id))){if(w===chosen)continue;for(const path of[...w.erp.top_paths,...w.erp.bottom_paths,...w.erp.vertical_paths])group.append(elt('path',{d:path,fill:'none',stroke:'#e4ecff','stroke-width':1.5}));if($('showpoints').checked)w.erp.points.forEach(p=>group.append(elt('circle',{cx:p[0],cy:p[1],r:2,fill:'#e4ecff'})))}left.append(group)}
const gt=d.erp_references.original;if($('showgt').checked){for(const svg of[left,right])erpLines(svg,[...gt.top_paths,...gt.bottom_paths,...gt.vertical_paths],'#fb8ef0',true);erpLines(lee,gt.bottom_paths,'#fb8ef0',true)}layoutLines(left,chosen.erp);drawCandidatePanel(d,s,cluster,right);
$('originaltitle').textContent=(chosen.id===cluster.representative?'簇代表':'单体检查')+' · '+chosen.worker+' / '+chosen.id;$('patterntitle').textContent=`2 · ${cluster.id}：${cluster.members.length}/${s.k} 人支持的整份标法`;$('candidateinfo').textContent=cluster.description;
const projected=s.erp_regions[method];for(const ring of projected){erpLines(lee,ring.paths,'#00ffe5',ring.hole);if($('showpoints').checked)ring.vertices.slice(0,-1).forEach(p=>erpDot(lee,p,'#00ffe5',''))}$('leenote').textContent=`全体 ${s.k} 人参与Lee投票：${projected.filter(r=>!r.hole).length}个区域分量、${projected.filter(r=>r.hole).length}个孔洞。仅地面边界，没有融合top_y。`;}
function changeCase(i){selected=i;activePattern='';const d=DATA[i];$('k').max=d.n;$('k').value=d.n;$('person').value='';$('threshold').replaceChildren();d.steps[d.n-1].pattern_views.forEach(v=>$('threshold').add(new Option(v.label,String(v.threshold))));document.querySelectorAll('nav button').forEach((b,j)=>b.setAttribute('aria-pressed',String(j===i)));$('title').textContent=d.title+' · '+d.image;$('context').textContent=`${d.n}位独立人员 · 粗难度：${d.difficulty} · 原选例依据：${d.selection_reason}。选例不是簇效果估计。`;$('photo').src=d.photo||'';$('photo').hidden=!d.photo;render()}
function render(){const d=DATA[selected],k=+$('k').value,s=d.steps[k-1],method=$('method').value,other=method==='mv50'?'mv_strict':'mv50',m=s.metrics[method].original,o=s.metrics[other].original,ga=area(d.references.original);$('klabel').textContent=`${k} / ${d.n}`;$('iou').textContent=m.iou.toFixed(4);$('delta').textContent=`全池单人均值 ${d.single_mean.toFixed(4)} · 最好单人 ${d.single_best.toFixed(4)}`;$('other').textContent=o.iou.toFixed(4);$('gap').textContent=`当前规则 − 另一规则 ${(m.iou-o.iou).toFixed(4)}`;$('omit').textContent=(100*m.omission_h2/ga).toFixed(1)+'%';$('extra').textContent=(100*m.extension_h2/ga).toFixed(1)+'%';
const cluster=patternView(d,s),p=$('person'),previous=p.value;p.replaceChildren(new Option('当前簇代表',''));d.workers.filter(w=>cluster.members.includes(w.id)).forEach(w=>p.add(new Option(`${w.worker} / ${w.id}`,w.id)));p.value=previous;if(p.selectedIndex<0)p.selectedIndex=0;const chosen=d.workers.find(w=>w.id===(p.value||cluster.representative));$('personscore').textContent=`单体IoU ${chosen.original_iou.toFixed(4)} · ${chosen.ring_confirmed?'人工确认环':'默认环'}`;panoramas(d,s,method,chosen,cluster);
const points=[...d.workers.flatMap(w=>rings(w.geometry).flat()),...rings(d.references.original).flat(),[0,0]];const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]),xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys),scale=Math.min(500/(xmax-xmin||1),400/(ymax-ymin||1)),project=p=>[290+(p[0]-(xmin+xmax)/2)*scale,240-(p[1]-(ymin+ymax)/2)*scale];const svg=$('bev');svg.replaceChildren();if($('showtiles').checked)s.tiles.forEach(t=>polygon(svg,t.geometry,project,{fill:`rgba(8,126,139,${.05+.55*t.support/k})`,stroke:'#7c8b9b','stroke-width':.25}));else polygon(svg,s.regions[method],project,{fill:'#52bbba',opacity:.3,stroke:'none'});
if($('showall').checked)d.workers.slice(0,k).forEach(w=>polygon(svg,w.geometry,project,{fill:'none',stroke:'#8298af','stroke-width':1,opacity:.6}));if($('showtie').checked)polygon(svg,s.tie_geometry,project,{fill:'#efae24',opacity:.55,stroke:'#c67c00','stroke-width':1});polygon(svg,s.regions[method],project,{fill:'none',stroke:'#087e8b','stroke-width':2.7});if($('showgt').checked)polygon(svg,d.references.original,project,{fill:'none',stroke:'#192f47','stroke-width':2.1,'stroke-dasharray':'7 5'});if(chosen)polygon(svg,chosen.geometry,project,{fill:'none',stroke:'#d6533d','stroke-width':2.5});const camera=project([0,0]);svg.append(elt('circle',{cx:camera[0],cy:camera[1],r:3,fill:'#17293d'}));svg.append(elt('text',{x:camera[0]+6,y:camera[1]-6,fill:'#17293d','font-size':11},'相机 (0,0)'));svg.append(elt('line',{x1:40,y1:465,x2:40+scale,y2:465,stroke:'#17293d','stroke-width':2}));svg.append(elt('text',{x:40,y:484,fill:'#17293d','font-size':12},'1 h · X 向右，Z 向上 · 全人数固定范围 / 等比例'));$('geometrynote').textContent=`${s.tile_count}个当前tile；恰好半数支持面积 ${s.tie_area_h2.toFixed(4)} h²。${m.empty?'当前融合为空。':''}非连通和孔洞按原样保留。`;
const chart=$('curve');chart.replaceChildren();const cx=j=>48+(j-1)*510/(d.n-1),cy=v=>292-v*250;for(let j=0;j<=5;j++){const y=cy(j/5);chart.append(elt('line',{x1:48,y1:y,x2:558,y2:y,stroke:'#e0e7ef'}));chart.append(elt('text',{x:16,y:y+4,fill:'#53667b'},(j/5).toFixed(1)))}for(const j of [...new Set([1,k,d.n,...Array.from({length:Math.floor(d.n/4)},(_,i)=>(i+1)*4)])].sort((a,b)=>a-b))chart.append(elt('text',{x:cx(j)-4,y:317,fill:'#53667b'},j));for(const [method,color]of[['mv50','#087e8b'],['mv_strict','#bd5f25']]){const r=d.mean_curve.filter(r=>r.method===method).sort((a,b)=>a.k-b.k);const band=r.map(q=>[cx(q.k),cy(Math.min(1,q.iou+q.mc_error))]).concat([...r].reverse().map(q=>[cx(q.k),cy(Math.max(0,q.iou-q.mc_error))]));chart.append(elt('polygon',{points:band.map(p=>p.join(',')).join(' '),fill:color,opacity:.09}));chart.append(elt('polyline',{points:r.map(q=>`${cx(q.k)},${cy(q.iou)}`).join(' '),fill:'none',stroke:color,'stroke-width':2.6}));chart.append(elt('polyline',{points:d.steps.map(q=>`${cx(q.k)},${cy(q.metrics[method].original.iou)}`).join(' '),fill:'none',stroke:color,'stroke-width':1.2,'stroke-dasharray':'4 4',opacity:.7}));chart.append(elt('circle',{cx:cx(k),cy:cy(s.metrics[method].original.iou),r:4,fill:color}))}chart.append(elt('line',{x1:cx(k),y1:38,x2:cx(k),y2:292,stroke:'#768b9f','stroke-dasharray':'2 3'}));chart.append(elt('text',{x:7,y:20,fill:'#53667b'},'BEV IoU'));chart.append(elt('text',{x:518,y:341,fill:'#53667b'},'人数 k'));const mu=d.mean_curve.find(q=>q.k===k&&q.method===method);$('meanvalue').textContent=`当前k的集合均值：${mu.iou.toFixed(4)}；${mu.estimator==='exact'?'精确枚举':`MC计算误差界 ±${mu.mc_error.toFixed(4)}`}。这与当前链IoU ${m.iou.toFixed(4)} 是不同量。`;$('members').textContent=d.workers.slice(0,k).map(w=>`${w.worker}(${w.id})`).join(' → ');$('verification').textContent=`每一步已重切tile；本例 ${d.checks.region_comparisons} 个区域核对。最大形状差 ${d.checks.max_geometry_difference_h2.toExponential(2)} h²，最大IoU差 ${d.checks.max_iou_difference.toExponential(2)}。`;}
DATA.forEach((d,i)=>{const b=document.createElement('button');b.textContent=d.title;b.onclick=()=>changeCase(i);$('cases').append(b)});['k','method','person','showgt','showpoints','showall','showtiles','showtie','candidateMethod','candidateScope','erpRule'].forEach(id=>$(id).addEventListener('input',render));$('threshold').onchange=()=>{activePattern='';$('person').value='';render()};$('full').onclick=()=>{$('k').value=DATA[selected].n;render()};changeCase(0);
</script></html>'''


if __name__ == '__main__':
    main()
