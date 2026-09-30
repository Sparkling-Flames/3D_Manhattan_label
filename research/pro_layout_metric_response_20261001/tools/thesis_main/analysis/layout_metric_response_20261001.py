"""小型指标响应实验；原因由生成器给定，真人面板仅描述，不作评分或聚合。

python -B -m tools.thesis_main.analysis.layout_metric_response_20261001 --out analysis_results/layout_metric_response_20261001
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path

import numpy as np
from shapely.geometry import box
from shapely.ops import unary_union

from tools.thesis_main.analysis.layout_foundation_20260930 import synthetic_record
from tools.thesis_main.analysis.layout_metric_probe_20260926 import bev_range_metrics, polygon_metrics
from tools.thesis_main.analysis.research_round_20260929 import (
    reconstruct, declared_column_wall_mask, iou, validate_panel, write_json, write_csv,
)

SCHEMA = 'layout_metric_response_v1'
QUAD = ['SW', 'SE', 'NE', 'NW']
SQUARE = np.array([[-2, -2], [2, -2], [2, 2], [-2, 2]], float)
PLAN = dict(
    schema=SCHEMA, purpose='controlled_metric_response_and_descriptive_real_panel',
    synthetic_parameters_fixed_before_first_run=True, camera_height=1, length_unit='common_camera_height_h',
    real_selection_review='first draft included comment candidates; corrected before accepted rerun: exclude comment-only candidates and prioritize explicit annotation marks; no metric/GT criteria',
    source_coordinate='C: continuous 1024x512; explicit P equivalent is C-0.5',
    raster_sampling='output pixel centres, independent of input coordinate phase',
    raster_sizes=[[512, 256], [1024, 512]], boundary_samples_per_side=512,
    boundary_dense_check=dict(case='near_three_pairs', gap_h=.002, samples_per_side=8192),
    extent_amplitudes_h=[0, .05, .25, 1, 2],
    detail_depths_h=[0, .002, .01, .05, .2], detail_half_width_h=.1,
    zero_depth_detail='limit geometry with two distinct collinear inserted nodes; positive depth has four detail nodes; unmatched identities reported, no coincident zero edges',
    near_pair_half_gaps_h=[.002, .01, .05, .1], near_three_pair_depth_h=.05,
    localization_amplitudes_native_px=[0, .1, .5, 1, 2, 4],
    localization_corner='SE: shared x, bottom y toward horizon, top y toward horizon, separately',
    ordinary_half_extent_h=2, near_horizon_half_extent_h=32,
    hidden_extension_lengths_h=[4, 8, 12, 20],
    fixed_manhattan_axis_deg=0,
    real_selection=dict(per_category=2, minimum_images=8, maximum_images=12,
        priority=['detail', 'scope', 'oos', 'doorway', 'near_horizon', 'ordinary'],
        order='scope/detail: annotation mark, image explicit tag, existing ledger, then image code and record alias; other categories: image code then record alias',
        near_horizon_bottom_margin_deg=5,
        population='confirmed rings AND retained; gates copied, never changed',
        evidence='explicit annotation marks, image explicit tags/existing ledger or explicit scene states; comment-only candidates excluded; missing is unknown',
        forbidden='no GT distance, difficulty outcome or metric-based semantic labels'),
    limitations=['no real RMSE without source identity correspondence',
        'column band is a declared bottom-first-hit and linearly interpolated wall-top proxy',
        'non-flat top does not define a measured roof or volume',
        'finite boundary quadrature may miss detail; max is sampled, never Hausdorff',
        'no weights, clustering, consensus, personnel totals or training'],
)


def _record(floor, labels, heights=2.7):
    if len(labels) != len(floor) or len(set(labels)) != len(labels):
        raise ValueError('invalid_synthetic_identity')
    return dict(synthetic_record(floor, heights), source_pair_indices=list(labels),
                coordinate_convention='continuous')


def synthetic_experiments():
    """参数固定；不因指标排序改变几何，环的身份与邻接显式保存。"""
    base = _record(SQUARE, QUAD)
    cases = []
    def add(family, name, amplitude, unit, a, b=base):
        cases.append(dict(family=family, case=name, amplitude=amplitude, amplitude_unit=unit, a=a, b=b))
    add('equivalence', 'cyclic_shift', 0, 'equivalent', _record(np.roll(SQUARE, 2, axis=0), QUAD[2:]+QUAD[:2]))
    add('equivalence', 'reverse_ring', 0, 'equivalent', _record(SQUARE[::-1], QUAD[::-1]))
    add('equivalence', 'collinear_subdivision', 0, 'equivalent',
        _record(np.insert(SQUARE, 1, [0, -2], axis=0), ['SW', 'south_midpoint', 'SE', 'NE', 'NW']))
    pixel = deepcopy(base)
    pixel.update(points=(np.asarray(base['points'])-.5).tolist(), coordinate_convention='pixel_center')
    add('equivalence', 'converted_C_P', 0, 'equivalent', pixel)
    for d in PLAN['extent_amplitudes_h']:
        right = SQUARE.copy(); right[[1, 2], 0] += d
        add('extent', 'single_side_extension', d, 'h', _record(right, QUAD))
        add('extent', 'symmetric_extension', d, 'h', _record(SQUARE*(1+d/2), QUAD))
        cut = SQUARE.copy(); cut[[1, 2], 0] -= d
        add('extent', 'single_side_truncation', d, 'h', _record(cut, QUAD))
    for d in PLAN['detail_depths_h']:
        if d == 0:
            # 零深度仅保留两个不同的共线插点，避免构造重合零长边。
            points = [[-2,-2],[2,-2],[2,-.1],[2,.1],[2,2],[-2,2]]
            labels = ['SW','SE','detail_start','detail_end','NE','NW']
            for name in ('convex_detail', 'concave_detail'):
                add('detail', name, d, 'h', _record(points, labels))
            continue
        for name, sign in [('convex_detail', 1), ('concave_detail', -1)]:
            points = [[-2,-2],[2,-2],[2,-.1],[2+sign*d,-.1],[2+sign*d,.1],[2,.1],[2,2],[-2,2]]
            labels = ['SW','SE','detail_start','detail_outer_start','detail_outer_end','detail_end','NE','NW']
            add('detail', name, d, 'h', _record(points, labels))
    for gap in PLAN['near_pair_half_gaps_h']:
        two = _record([[-2,-2],[2,-2],[2,-gap],[2,gap],[2,2],[-2,2]],
                      ['SW','SE','near_start','near_end','NE','NW'])
        three = _record([[-2,-2],[2,-2],[2,-gap],[2.05,0],[2,gap],[2,2],[-2,2]],
                        ['SW','SE','near_start','near_middle','near_end','NE','NW'])
        add('detail', 'near_three_pairs', gap, 'half_gap_h', three, two)
    for extent, name in [(2, 'ordinary'), (32, 'near_horizon')]:
        reference = _record(SQUARE*(extent/2), QUAD)
        for d in PLAN['localization_amplitudes_native_px']:
            for part in ('shared_x', 'bottom_y', 'top_y'):
                a = deepcopy(reference); pairs = np.asarray(a['points']).reshape(-1,2,2)
                if part == 'shared_x': pairs[1,:,0] = (pairs[1,:,0]+d) % 1024
                elif part == 'bottom_y': pairs[1,1,1] -= d
                else: pairs[1,0,1] += d
                a['points'] = pairs.reshape(-1,2).tolist()
                add('localization', name+'_'+part, d, 'native_px', a, reference)
    hidden_base = None
    for length in PLAN['hidden_extension_lengths_h']:
        poly = unary_union([box(-2,-2,2,2), box(2,.5,4,1.5), box(3,1.5,4,length)])
        floor = np.asarray(poly.exterior.coords)[:-1]
        # 身份来自生成参数：仅最远的两个点随length移动，其余生成节点不动。
        labels = [f'far_{x:g}' if z == length else f'fixed_{x:g}_{z:g}' for x,z in floor]
        a = _record(floor, labels)
        if hidden_base is None: hidden_base = a
        add('extent', 'hidden_extension', length, 'total_length_h', a, hidden_base)
    # 保留非水平墙顶，但仅用列式代理；不构造屋顶/棱柱指标。
    nonflat = _record(SQUARE, QUAD, [1.5,3.5,3.5,1.5])
    split = _record([[-2,-2],[2,-2],[2,0],[2,2],[-2,2]],
                    ['SW','SE','east_midpoint','NE','NW'], [1.5,3.5,3.5,3.5,1.5])
    add('equivalence', 'nonflat_collinear_subdivision', 0, 'equivalent', split, nonflat)
    return cases


def _fixed_axis(g):
    if g['representations']['declared_footprint']['status'] != 'ok':
        return dict(status='unavailable', reason=g['representations']['declared_footprint']['reason'])
    edge = np.roll(g['floor'], -1, axis=0)-g['floor']; lengths = np.linalg.norm(edge, axis=1)
    if (lengths <= 1e-12).any(): return dict(status='unavailable', reason='zero_length_edge')
    angle = np.arctan2(edge[:,1], edge[:,0])
    residual = np.degrees(abs((angle+np.pi/4) % (np.pi/2)-np.pi/4))
    return dict(status='ok', reason=None, axis_deg=0, per_edge_deg=residual.tolist(),
                mean_deg=float(residual.mean()), length_weighted_mean_deg=float(np.average(residual, weights=lengths)),
                max_deg=float(residual.max()), definition='single-layout residual to known synthetic axes; not distance between layouts')


def _correspondence(a, b, ga, gb):
    la, lb = a['source_pair_indices'], b['source_pair_indices']
    if len(set(la)) != len(la) or len(set(lb)) != len(lb): raise ValueError('duplicate_synthetic_identity')
    common = [label for label in la if label in lb]
    result = dict(status='unavailable', matched_labels=common, matched_pairs=len(common),
        unmatched_a=len(la)-len(common), unmatched_b=len(lb)-len(common),
        floor_rmse_h=None, top_rmse_h=None, combined_rmse_h=None,
        definition='sqrt(mean(squared Euclidean distance per matched 3D endpoint)); all unmatched pairs retained')
    if not common or any(g['floor'] is None or g['heights'] is None for g in (ga,gb)):
        return dict(result, reason='no_valid_reconstructed_correspondence')
    ai, bi = [la.index(k) for k in common], [lb.index(k) for k in common]
    floor2 = np.sum((ga['floor'][ai]-gb['floor'][bi])**2, axis=1)
    top2 = floor2+(ga['heights'][ai]-gb['heights'][bi])**2
    result.update(status='explicit_synthetic_identity', reason=None,
        floor_rmse_h=float(np.sqrt(floor2.mean())), top_rmse_h=float(np.sqrt(top2.mean())),
        combined_rmse_h=float(np.sqrt(np.r_[floor2,top2].mean())))
    return result


def measure(a, b, *, synthetic=False, boundary_samples=512):
    gs = [reconstruct(r, coordinate_convention=r.get('coordinate_convention', 'continuous')) for r in (a,b)]
    states = [g['representations']['declared_footprint'] for g in gs]
    reasons = ';'.join(f'{name}:{s["reason"]}' for name,s in zip(('a','b'), states) if s['status'] != 'ok')
    bev = bev_range_metrics(*(g['floor'] for g in gs)) if not reasons else dict(status='unavailable', reason=reasons, bev_range_iou=None)
    boundary = dict(status='unavailable', reason=bev['reason'], boundary_mean_distance=None,
                    boundary_p95_distance=None, boundary_sampled_max=None)
    if bev['status'] == 'ok':
        # 复用原边界核，仅取二维边界字段；不使用其历史棱柱、总分结果。
        raw = polygon_metrics(*(g['floor'] for g in gs), boundary_samples=boundary_samples)
        boundary = dict(status='ok', reason=None, **{k:v for k,v in raw.items() if k.startswith('boundary_')})
        boundary['sampled_max_upper_error_bound_h'] = max(boundary['boundary_step_a'], boundary['boundary_step_b'])/2
        boundary['definition'] = 'pooled two-way equal-arclength quadrature; distances in h; sampled max <= continuous boundary sup <= sampled max+half max step'
    column = {}
    for width,height in PLAN['raster_sizes']:
        try:
            masks = [declared_column_wall_mask(g,width,height) for g in gs]
            value = iou(*masks)
            column[f'{width}x{height}'] = dict(status='ok' if value is not None else 'unavailable',
                reason=None if value is not None else 'empty_union', iou=value,
                area_pixels_a=int(masks[0].sum()), area_pixels_b=int(masks[1].sum()),
                differing_pixels=int(np.count_nonzero(masks[0] ^ masks[1])))
        except ValueError as exc:
            column[f'{width}x{height}'] = dict(status='unavailable', reason=str(exc), iou=None)
    out = dict(bev=bev, boundary=boundary, column=column,
        geometry=[dict(status=g['status'], reason=g['reason'],
            floor=g['floor'].tolist() if g['floor'] is not None else None,
            heights=g['heights'].tolist() if g['heights'] is not None else None,
            bottom_horizon_margin_deg=g.get('bottom_horizon_margin_deg'),
            top_horizon_margin_deg=g.get('top_horizon_margin_deg'),
            camera_relation=g['camera_relation'], camera_in_visible_kernel=g['camera_in_visible_kernel'],
            ring_confirmed=g['ring_confirmed'], coordinate_convention=g['coordinate_convention']) for g in gs])
    if synthetic:
        out.update(correspondence=_correspondence(a,b,*gs), manhattan=[_fixed_axis(g) for g in gs])
    else:
        out.update(correspondence=dict(status='unavailable', reason='real_source_correspondence_not_established'),
                   manhattan=dict(status='unavailable', reason='real_common_axis_not_established'))
    return out


def select_real_panel(panel):
    """固定证据选样；原GT环未审也不被升级。重复图片优先占较稀缺类别。"""
    population = [(im,r) for im in sorted(panel['images'], key=lambda im:im['code'])
                  for r in sorted(im['annotations'], key=lambda r:r['id'])
                  if r['ring_confirmed'] is True and r['cleaning'] == 'retained']
    selected = []; used = set(); coverage = {}
    for category in PLAN['real_selection']['priority']:
        candidates = []
        for im,r in population:
            review = im.get('review') or {}; own = r.get('review') or {}; scene = im['scene']
            if category in ('scope', 'detail'):
                marked = own.get(category+'_annotation') is True or any(review.get(category+'_'+k) is True for k in ('explicit_tag','existing_ledger'))
            elif category == 'oos': marked = scene['oos_status'] == 'confirmed'
            elif category == 'doorway': marked = scene['doorway_status'] in ('difficult','annotatable')
            elif category == 'ordinary': marked = scene['oos_status'] == 'not_oos' and scene['doorway_status'] == 'none'
            else:
                margin = reconstruct(r).get('bottom_horizon_margin_deg')
                marked = margin is not None and 0 < margin <= PLAN['real_selection']['near_horizon_bottom_margin_deg']
            if marked: candidates.append((im,r))
        def tier(im,r):
            if category not in ('scope','detail'): return 'explicit_scene_or_geometry'
            if (r.get('review') or {}).get(category+'_annotation') is True: return 'annotation_mark'
            if (im.get('review') or {}).get(category+'_explicit_tag') is True: return 'image_explicit_tag'
            return 'image_existing_ledger'
        tiers={'annotation_mark':0,'image_explicit_tag':1,'image_existing_ledger':2,'explicit_scene_or_geometry':0}
        candidates.sort(key=lambda pair:(tiers[tier(*pair)], pair[0]['code'], pair[1]['id']))
        chosen = []
        for im,r in candidates:
            if im['code'] in used: continue
            selected.append((im,r)); used.add(im['code']); chosen.append(dict(image=im['code'],id=r['id'],evidence_tier=tier(im,r)))
            if len(chosen) == PLAN['real_selection']['per_category']: break
        coverage[category] = dict(available_images=len({im['code'] for im,_ in candidates}),
            selected=chosen, requested=PLAN['real_selection']['per_category'], missing_slots=PLAN['real_selection']['per_category']-len(chosen))
    for im,r in population:
        if len(selected) >= PLAN['real_selection']['minimum_images']: break
        if im['code'] not in used:
            selected.append((im,r)); used.add(im['code'])
            coverage.setdefault('additional_confirmed', dict(selected=[]))['selected'].append(dict(image=im['code'],id=r['id']))
    return selected, coverage


def _flat(row):
    m = row['metrics']; bev = m['bev']; boundary = m['boundary']
    result = {k:v for k,v in row.items() if k not in ('metrics','a','b')}
    result.update(bev)
    result.update({'boundary_'+k:v for k,v in boundary.items() if k in ('status','reason')})
    result.update({k:v for k,v in boundary.items() if k.startswith('boundary_') or k == 'sampled_max_upper_error_bound_h'})
    for key,value in m['column'].items(): result.update({f'column_{key}_{k}':v for k,v in value.items()})
    result.update({'correspondence_'+k:v for k,v in m['correspondence'].items() if k != 'definition'})
    if isinstance(m['manhattan'], list):
        for name,value in zip(('a','b'),m['manhattan']):
            result.update({f'manhattan_{name}_{k}':v for k,v in value.items() if k != 'definition'})
    else: result.update({'manhattan_'+k:v for k,v in m['manhattan'].items()})
    return result


def _plots(rows, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for family in ('extent','detail','localization'):
        fig, axes = plt.subplots(2,2,figsize=(12,8))
        fields = [('bev','bev_range_iou','BEV IoU'), ('bev','centroid_distance_h','Area-centroid distance / h'),
                  ('boundary','boundary_sampled_max','Boundary sampled max / h'), ('column','1024x512','Declared column-band IoU')]
        subset = [r for r in rows if r['family'] == family]
        for ax,(domain,field,label) in zip(axes.flat, fields):
            for name in dict.fromkeys(r['case'] for r in subset):
                group = [r for r in subset if r['case'] == name]
                # hidden length及近邻gap的轴独立标明，避免混合不同幅度定义。
                if family == 'extent' and name == 'hidden_extension': continue
                if family == 'detail' and name == 'near_three_pairs': continue
                values = [r['metrics'][domain].get(field) if domain != 'column' else r['metrics'][domain][field]['iou'] for r in group]
                ax.plot([r['amplitude'] for r in group], [np.nan if v is None else v for v in values], '.-', label=name)
            ax.set_ylabel(label); ax.set_xlabel('Native 1024x512 pixel perturbation' if family == 'localization' else 'Geometric amplitude / h')
            ax.grid(alpha=.25); ax.legend(fontsize=7)
        if family == 'localization':
            fig.suptitle('Near-horizon bottom y at 4 px: unavailable (wrong hemisphere); missing values are gaps', fontsize=10)
        fig.tight_layout(rect=(0,0,1,.95) if family == 'localization' else (0,0,1,1))
        fig.savefig(out/(family+'_response.png'), dpi=160); plt.close(fig)
    # 小细节和隐藏范围单列，避免在全局图的坐标范围中消失。
    fig,axes = plt.subplots(1,2,figsize=(11,4))
    for ax,name in zip(axes, ('near_three_pairs','hidden_extension')):
        group = [r for r in rows if r['case'] == name]
        ax.plot([r['amplitude'] for r in group], [r['metrics']['bev']['bev_range_iou'] for r in group], '.-',label='BEV IoU')
        for size in ('512x256','1024x512'):
            ax.plot([r['amplitude'] for r in group], [r['metrics']['column'][size]['iou'] for r in group], '.-',label='Column '+size)
        ax.set_title(name); ax.set_xlabel('Half gap / h' if name == 'near_three_pairs' else 'Total extension length / h'); ax.set_ylabel('IoU'); ax.legend(); ax.grid(alpha=.25)
    fig.tight_layout(); fig.savefig(out/'detail_hidden_resolution.png',dpi=160); plt.close(fig)


def run(panel, out):
    validate_panel(panel); out = Path(out); out.mkdir(parents=True,exist_ok=True)
    write_json(out/'experiment_plan.json', PLAN)  # 在指标计算前落盘固定参数与选样规则。
    synthetic = [dict(c,metrics=measure(c['a'],c['b'],synthetic=True)) for c in synthetic_experiments()]
    dense_case = next(c for c in synthetic if c['case'] == PLAN['boundary_dense_check']['case'] and c['amplitude'] == PLAN['boundary_dense_check']['gap_h'])
    dense = dict(case=dense_case['case'],amplitude=dense_case['amplitude'],
                 boundary=measure(dense_case['a'],dense_case['b'],synthetic=True,boundary_samples=8192)['boundary'])
    selected, coverage = select_real_panel(panel); real = []
    selection={entry['id']:dict(category=category,**entry) for category,c in coverage.items() for entry in c['selected']}
    for im,r in selected:
        versions = {ref['version']:ref for ref in im['references']}
        for version in ('original','manual_revision'):
            ref = versions.get(version)
            meta = dict(image=im['code'],id=r['id'],selection=selection[r['id']],worker=r['worker'],condition=r['condition'],
                scene=im['scene'],image_review=im['review'],annotation_review=r['review'],
                cleaning=r['cleaning'],independent=r['independent'],quality_candidate=r['quality_candidate'],
                consensus_eligible=r['consensus_eligible'],quality_gate=r['main_quality_gate'],consensus_gate=r['main_consensus_gate'],
                reference_version=version,reference_id=ref['id'] if ref else None,
                source_point_indices_a=r['source_point_indices'],source_point_indices_b=ref['source_point_indices'] if ref else None,
                source_pair_indices_a=r['source_pair_indices'],source_pair_indices_b=ref['source_pair_indices'] if ref else None,
                ring_confirmed_a=r['ring_confirmed'],ring_confirmed_b=ref['ring_confirmed'] if ref else None)
            if ref is None:
                missing = dict(status='unavailable',reason='reference_version_absent')
                metrics = dict(bev=dict(missing,bev_range_iou=None),boundary=dict(missing,boundary_sampled_max=None),
                    column={f'{w}x{h}':dict(missing,iou=None) for w,h in PLAN['raster_sizes']},
                    correspondence=dict(status='unavailable',reason='real_source_correspondence_not_established'),
                    manhattan=dict(status='unavailable',reason='real_common_axis_not_established'))
            else: metrics = measure(r,ref)
            real.append(dict(meta,a=r,b=ref,metrics=metrics))
    result = dict(schema=SCHEMA,source_manifest=panel['source_manifest'],plan=PLAN,
        selection_coverage=coverage,real_images=len(selected),synthetic=synthetic,real=real,boundary_dense_check=dense)
    write_json(out/'results.json', result)
    flat_synthetic,flat_real=[_flat(r) for r in synthetic],[_flat(r) for r in real]
    write_csv(out/'synthetic_metrics.csv', flat_synthetic)
    write_csv(out/'real_metrics.csv', flat_real)
    write_json(out/'field_contract.json', dict(schema=SCHEMA,
        orientation='a: perturbed/selected personnel; b: baseline/reference version',
        geometry='inputs retain ordered top/bottom endpoints and source identities; all lengths h, areas h^2',
        bev='exact declared polygon intersection/union; coverage_of_a=intersection/area_a and coverage_of_b=intersection/area_b; symmetric_difference_h2=area_a+area_b-2*intersection',
        boundary='mean, p95 and sampled max of pooled two-way equal-arclength distances, plus per-direction means/steps; not exact Hausdorff',
        column='declared column band IoU, output pixel-centre quadrature at both ERP sizes; no true roof/volume claims',
        manhattan='synthetic only, residual to fixed known axis 0deg; separate from two-layout difference',
        correspondence='synthetic explicit identity only; floor/top/combined RMSE and unmatched pair counts; real unavailable',
        missing='null metric with explicit status/reason, never 0; missing GT version gets a row',
        review='marks copied from final bundle; false/no mark means unknown, not negative; gates never inferred from metrics',
        csv='flattened metric domains; nested review/gates/identities serialized as JSON; results.json is complete record',
        csv_fields=dict(synthetic=list(dict.fromkeys(k for r in flat_synthetic for k in r)),
                        real=list(dict.fromkeys(k for r in flat_real for k in r))),
        boundary_kernel_extension='existing polygon_metrics adds optional sample count and directional means/steps; historical callers keep default512; old artifacts untouched'))
    _plots(synthetic,out)
    _report(result,out)
    return result


def _report(result,out):
    family_counts={name:sum(r['family']==name for r in result['synthetic']) for name in ('equivalence','extent','detail','localization')}
    present=sum(r['b'] is not None for r in result['real']); absent=len(result['real'])-present
    def case(name,amp): return next(r for r in result['synthetic'] if r['case']==name and r['amplitude']==amp)['metrics']
    symmetric=case('symmetric_extension',1); hidden=case('hidden_extension',20); small=case('convex_detail',.002)
    regular=case('ordinary_bottom_y',.5); far=case('near_horizon_bottom_y',.5); near=case('near_three_pairs',.002)
    lines=['# 坐标来源收尾与指标响应小实验（2026-10-01）','',
        f"输入：最终manifest完整bundle；{result['real_images']}张固定证据图片、{len(result['real'])}条人员/参考版本记录（{present}条有参考比较，{absent}条人工参考缺失记录）；{len(result['synthetic'])}个参数化合成对照，由{family_counts['equivalence']}个等价、{family_counts['extent']}个范围、{family_counts['detail']}个细节和{family_counts['localization']}个定位对照构成，**不是{len(result['synthetic'])}个独立样本**。合成参数在首次运行前固定。选样审查纠正了评论候选混入的问题，最终证据层级与规则在接收复算前写入experiment_plan.json；未按指标结果改参数或选样。",'',
        '当前合同已纠正：原始GT生产C；最终LS百分比用C画布解释；原生HoHoNet为P。C/P正确转换是等价性检查。同值套两公式是错配/未知来源敏感性，不能再把原始GT的P解释当等可能来源。输入phase与输出中心采样分开。','',
        '## 受控结果','',
        '| 对照 | BEV IoU | 面积质心差/h | 边界采样最大/h | 列式IoU 512 / 1024 |','|---|---:|---:|---:|---|']
    for name,m in [('对称扩展1h',symmetric),('隐藏范围延至20h',hidden),('小凸起0.002h',small),('近邻两对/三对 gap0.002h',near)]:
        lines.append(f"|{name}|{m['bev']['bev_range_iou']:.9f}|{m['bev']['centroid_distance_h']:.9f}|{m['boundary']['boundary_sampled_max']:.9f}|{m['column']['512x256']['iou']:.9f} / {m['column']['1024x512']['iou']:.9f}|")
    eq=[r['metrics'] for r in result['synthetic'] if r['family']=='equivalence']
    lines += ['', f"循环、反向、平顶/非平顶同边共线插点、正确C/P转换：BEV IoU最小{min(m['bev']['bev_range_iou'] for m in eq):.12f}；边界采样最大差至多{max(m['boundary']['boundary_sampled_max'] for m in eq):.3g}h。身份匹配RMSE近零，但新增中间对仍记未匹配；不靠删点获得等价。",'',
        f"同一SE底点向地平线移动0.5原域像素：普通房间floor RMSE={regular['correspondence']['floor_rmse_h']:.6f}h；近地平线房间={far['correspondence']['floor_rmse_h']:.6f}h。该RMSE汇总4个对应底点，只有SE被扰动，因此单个SE位移分别为其2倍（{2*regular['correspondence']['floor_rmse_h']:.6f}h和{2*far['correspondence']['floor_rmse_h']:.6f}h）。near_horizon是半宽32h的更大合成房间，ordinary半宽2h；这是投影/深度传播对照，不是同一房间的人员能力比较。4px近地平线底点越界保留unavailable及原因，不当零或剔除。",'',
        'BEV使用精确多边形面积，能看到隐藏声明范围；列式墙带只看每列最近底墙和线性墙顶，隐藏范围可投影相同。对称扩展质心可保持不动；凸/凹小细节IoU受全局面积稀释，边界尾部受采样限制。固定Manhattan轴残差独立报告，正交范围变化残差仍可为零，不替代空间差异。', '',
        'near_three_pairs比较的是原墙上的两个共线端点与两端之间新增三角形尖凸中点的路径；同时改变点数、几何和局部角度。它不是对真实正交两对/三对表达的完整规律检验，也没有验证局部整体投票。保留身份与未匹配项，只说明这一固定尖凸案例的响应。', '',
        f"最小近邻细节边界复核：512样本max={near['boundary']['boundary_sampled_max']:.9f}h，8192样本max={result['boundary_dense_check']['boundary']['boundary_sampled_max']:.9f}h。有限采样的max不称Hausdorff；每侧步长与保守最大值误差上界保留。p95可能为0是细节所占边长不足5%，不能解释为无差异。",'',
        '两个栅格分别保留IoU和差异像素；亚像素量化可产生平台及小幅非单调，分辨率对照不作为方法真实精度证明。相同最终几何无论来自范围选择还是定位偏移，所有这些指标都相同；语义原因不能单靠指标识别。', '',
        '## 真实面板与缺失','', '| 类别 | 可用图片 | 本类别新选 | 缺额 |','|---|---:|---:|---:|']
    for name,c in result['selection_coverage'].items():
        lines.append(f"|{name}|{c.get('available_images','—')}|{len(c['selected'])}|{c.get('missing_slots','—')}|")
    lines += ['', '范围/细节优先明确个人标记，其次图级明确标签、既有台账；评论候选只保留背景，不作为选样证据。OOS/门洞需明确场景状态，近地平线用底点角距≤5°；ordinary只认明确not_oos+none。缺失标记不是阴性，类别可重叠，缺额可能来自重复图片已先选。同证据层按图片编号与记录别名固定选择，不按GT距离、人员质量或难度挑选。','',
        '| 图片 | 人员记录 | 原始GT BEV / 列式1024 IoU | 人工GT BEV / 列式1024 IoU |','|---|---|---|---|']
    def show(r):
        m=r['metrics']; a=m['bev'].get('bev_range_iou'); b=m['column']['1024x512']['iou']
        return (f'{a:.6f}' if a is not None else 'NA:'+m['bev']['reason'])+' / '+(f'{b:.6f}' if b is not None else 'NA:'+m['column']['1024x512']['reason'])
    for image in dict.fromkeys(r['image'] for r in result['real']):
        rs=[r for r in result['real'] if r['image']==image]
        lines.append(f"|{image}|{rs[0]['id']}|{show(rs[0])}|{show(rs[1])}|")
    lines += ['', '这是固定小面板的参考一致性描述。原始GT环未经过人员环审核，状态仍为false；人工修订版本单列，缺版本明确NA。所有gate、来源索引和部分审核标记保留，不替换资格、裁定GT、传播同房标签或汇总人员分数。真实RMSE因未建立对应身份而不计算；真实Manhattan未计算是本轮未定义共同轴的实验边界。即使没有GT或共同轴，数学上仍可各自拟合每个layout的最佳轴并计算自洽残差，但各自拟合轴的残差不能替代跨layout结构距离；本轮没有实施该拟合。', '',
        '## 工件与复算','',
        '- [完整结果](results.json)、[固定计划](experiment_plan.json)、[字段合同](field_contract.json)、[合成CSV](synthetic_metrics.csv)、[真实CSV](real_metrics.csv)。',
        '- [范围幅度图](extent_response.png)、[细节幅度图](detail_response.png)、[定位幅度图](localization_response.png)、[近邻/隐藏范围及分辨率图](detail_hidden_resolution.png)。','',
        '本次验证命令、结果、地图同步及交付边界见[交付核验](VALIDATION.md)。','',
        '```powershell', 'python -B -m tools.thesis_main.analysis.layout_metric_response_20261001 --out analysis_results/layout_metric_response_20261001', '```','',
        '本轮不执行全量共识、分簇、训练或LS运营。未观测屋顶不封顶计分；未使用原生模型至LS转换或重复缩小的训练入口。这两个具体适配缺陷须在使用相应链路前修复；ERP实际采样/逐图调平记录仍缺，不据图像相同升级物理标定。结果只用于检查指标响应和盲点，尚不能冻结总分、阈值或方法优劣。']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle
    bundle=load_current_bundle(); panel,mapping=project_bundle(bundle)
    source={mapping['records'][o['object_id']]:o for o in bundle['data']['objects']}
    for im in panel['images']:
        for r in im['annotations']+im['references']:
            r['source_pair_indices']=source[r['id']]['ordered_source_pair_indices']
    result=run(panel,args.out)
    print(f"{result['schema']}: {len(result['synthetic'])} synthetic pairs, {result['real_images']} real images")
