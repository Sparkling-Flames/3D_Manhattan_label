"""固定解析房间的局部算法探针；不排序真人数据，不修改质量/排除规则。

python -m tools.thesis_main.analysis.layout_metric_probe_20260926 --out PATH
所有三维长度采用同一相机离地高度 1；ERP 采用像素中心约定。
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from shapely.geometry import Point, Polygon
from shapely.validation import explain_validity

from tools.thesis_main.analysis.consensus_region_20260923 import compare_masks, wall_mask
from tools.label_studio.panorama_studio.geometry import heading_frame

LAMBDAS = [0, .25, .5, 1, 2]


def _polygon(points):
    p = np.asarray(points, float)
    if p.ndim != 2 or p.shape[1:] != (2,) or len(p) < 3 or not np.isfinite(p).all():
        raise ValueError('invalid_coordinate_array')
    result = Polygon(p)
    if not result.is_valid or result.area < 1e-12:
        raise ValueError(explain_validity(result) if not result.is_valid else 'zero_area')
    return result


def _scores(iou, distance, length):
    if iou is None or distance is None:
        return None
    return [float(1-iou + weight*distance/length) for weight in LAMBDAS]


def bev_range_metrics(a, b):
    """声明环 BEV 范围；共同相机高度单位，不附带高度代理或总分。"""
    try:
        p,q=_polygon(a),_polygon(b)
    except ValueError as exc:
        return dict(status='unavailable',reason=str(exc),bev_range_iou=None)
    inter=p.intersection(q).area
    return dict(status='ok',reason=None,bev_range_iou=float(inter/(p.area+q.area-inter)),
                area_a_h2=float(p.area),area_b_h2=float(q.area),
                coverage_of_a=float(inter/p.area),coverage_of_b=float(inter/q.area),
                symmetric_difference_h2=float(p.area+q.area-2*inter),
                centroid_distance_h=float(p.centroid.distance(q.centroid)))


def polygon_metrics(a, b, height_a=2.7, height_b=2.7, *, boundary_samples=512):
    """a 相对 b；保留顶点邻接，失败显式返回，禁止修复无效多边形。"""
    polygons = []
    for name, points in [('a', a), ('b', b)]:
        try:
            polygons.append(_polygon(points))
        except ValueError as exc:
            return dict(status='invalid_'+name, reason=str(exc), iou=None,
                        volume_iou=None, centroid_distance=None, scores=None)
    if not all(math.isfinite(h) and h > 0 for h in [height_a, height_b]):
        raise ValueError('invalid_prism_height')
    if type(boundary_samples) is not int or boundary_samples < 2:
        raise ValueError('invalid_boundary_samples')
    p, q = polygons
    inter = p.intersection(q).area
    iou = inter/(p.area+q.area-inter)
    volume_inter = inter*min(height_a, height_b)
    viou = volume_inter/(p.area*height_a+q.area*height_b-volume_inter)
    dc = p.centroid.distance(q.centroid)
    # ponytail: fixed arclength quadrature for diagnostic distances; increase samples for convergence studies.
    distances = np.array([source.boundary.interpolate(t, normalized=True).distance(target.boundary)
                          for source, target in [(p, q), (q, p)]
                          for t in np.arange(boundary_samples)/boundary_samples])
    normalizer = math.sqrt(q.area)
    return dict(status='ok', iou=float(iou), volume_iou=float(viou),
                area_a=float(p.area), area_b=float(q.area), intersection_area=float(inter),
                centroid_a=list(p.centroid.coords[0]), centroid_b=list(q.centroid.coords[0]),
                centroid_distance=float(dc), normalizer_sqrt_reference_area=normalizer,
                camera_inside_a=bool(p.contains(Point(0, 0))), camera_inside_b=bool(q.contains(Point(0, 0))),
                boundary_mean_distance=float(distances.mean()),
                boundary_p95_distance=float(np.quantile(distances, .95)),
                boundary_sampled_max=float(distances.max()), boundary_samples_per_side=boundary_samples,
                boundary_mean_a_to_b=float(distances[:boundary_samples].mean()),
                boundary_mean_b_to_a=float(distances[boundary_samples:].mean()),
                boundary_step_a=float(p.length/boundary_samples), boundary_step_b=float(q.length/boundary_samples),
                scores=_scores(iou, dc, normalizer))


def pairs_from_floor(xz, room_height=2.7):
    """固定有序 footprint -> 精确上下角射线，输出 1024×512 像素中心坐标。"""
    p = np.asarray(xz, float)
    if room_height <= 1:
        raise ValueError('ceiling_not_above_camera')
    radius = np.linalg.norm(p, axis=1)
    if (radius <= 0).any():
        raise ValueError('corner_at_camera')
    u = np.arctan2(p[:, 0], -p[:, 1])
    x = ((u/(2*np.pi)+.5)*1024-.5) % 1024
    top = (.5-np.arctan2(room_height-1, radius)/np.pi)*512-.5
    bottom = (.5+np.arctan2(1., radius)/np.pi)*512-.5
    return np.stack([np.c_[x, top], np.c_[x, bottom]], axis=1)


def nearest_wall_mask(xz, room_height=2.7, width=512, height=256):
    """按显式墙环逐射线求最近正交点；不假设相机处于多边形可见核。"""
    poly = _polygon(xz)
    if not poly.contains(Point(0, 0)):
        raise ValueError('camera_not_strictly_inside')
    if room_height <= 1:
        raise ValueError('ceiling_not_above_camera')
    p = np.asarray(xz, float)
    angles = ((np.arange(width)+.5)/width-.5)*2*np.pi
    rays = np.c_[np.sin(angles), -np.cos(angles)]
    distance = np.full(width, np.inf)
    cross = lambda a, b: a[..., 0]*b[..., 1]-a[..., 1]*b[..., 0]
    for a, b in zip(p, np.roll(p, -1, axis=0)):
        edge = b-a
        denom = cross(rays, edge)
        good = np.abs(denom) > 1e-12
        radius = np.full(width, np.inf)
        fraction = np.full(width, np.inf)
        radius[good] = cross(a, edge)/denom[good]
        fraction[good] = cross(a, rays[good])/denom[good]
        hit = good & (radius > 0) & (fraction >= -1e-10) & (fraction <= 1+1e-10)
        distance[hit] = np.minimum(distance[hit], radius[hit])
    if not np.isfinite(distance).all():
        raise ValueError('uncovered_ray')
    latitude = np.pi*(.5-(np.arange(height)+.5)/height)
    top, bottom = np.arctan2(room_height-1, distance), -np.arctan2(1., distance)
    return (latitude[:, None] <= top) & (latitude[:, None] >= bottom)


def _sphere(mask):
    h, w = mask.shape
    latitude = np.pi*(.5-(np.arange(h)+.5)/h)
    longitude = 2*np.pi*((np.arange(w)+.5)/w-.5)
    weights = np.cos(latitude)[:, None]*mask
    total = weights.sum()
    if total == 0:
        return dict(resultant=None, direction=None), weights
    moment = np.array([(weights*np.cos(latitude)[:, None]*np.sin(longitude)).sum(),
                       (weights*np.sin(latitude)[:, None]).sum(),
                       -(weights*np.cos(latitude)[:, None]*np.cos(longitude)).sum()])/total
    resultant = float(np.linalg.norm(moment))
    return dict(resultant=resultant, direction=(moment/resultant).tolist() if resultant > 1e-12 else None), weights


def compare_regions(a, b):
    """固定 ERP 域面积及球面立体角权重；两种质量定义分别报告。"""
    out = compare_masks(a, b)
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    from tools.thesis_main.analysis.consensus_region_20260923 import centroid
    ca, cb = centroid(a), centroid(b)
    sa, _ = _sphere(a)
    sb, _ = _sphere(b)
    weights = np.cos(np.pi*(.5-(np.arange(a.shape[0])+.5)/a.shape[0]))[:, None]
    union = float((weights*(a | b)).sum())
    siou = float((weights*(a & b)).sum()/union) if union else None
    angle = (float(np.arccos(np.clip(np.dot(sa['direction'], sb['direction']), -1, 1)))
             if sa['direction'] is not None and sb['direction'] is not None else None)
    circular_distance = (math.hypot(out['circular_dx_px'], out['dy_px'])
                         if out['circular_dx_px'] is not None else None)
    out.update(circular_R_a=ca['circular_R'], circular_R_b=cb['circular_R'],
               area_pixels_a=int(a.sum()), area_pixels_b=int(b.sum()),
               spherical_iou=siou, spherical_angle_rad=angle,
               spherical_resultant_a=sa['resultant'], spherical_resultant_b=sb['resultant'],
               spherical_direction_a=sa['direction'], spherical_direction_b=sb['direction'],
               scores_erp=_scores(out['iou'], out['erp_distance_px'], math.hypot(1024, 512)),
               scores_circular=_scores(out['iou'], circular_distance, math.hypot(1024, 512)),
               scores_spherical=_scores(siou, angle, math.pi))
    return out


def _scenarios():
    square = np.array([[-2, -2], [2, -2], [2, 2], [-2, 2]], float)
    lshape = np.array([[-2, -2], [2, -2], [2, 0], [0, 0], [0, 2], [-2, 2]], float)-[-1, 1.3]
    longitude = lshape[np.argsort(np.arctan2(lshape[:, 0], -lshape[:, 1]))]
    bump = np.array([[-2, -2], [2, -2], [2, -.1], [2.05, -.1], [2.05, .1], [2, .1], [2, 2], [-2, 2]])
    return {
        'l_order': (longitude, lshape, 2.7, 2.7),
        'same_centroid_different_shape': (np.array([[-4, -1], [4, -1], [4, 1], [-4, 1]]), square, 2.7, 2.7),
        'symmetric_expansion': (square*1.5, square, 2.7, 2.7),
        'same_summary_horizontal': (np.array([[-3, -1], [3, -1], [3, 1], [-3, 1]]), square, 2.7, 2.7),
        'same_summary_vertical': (np.array([[-1, -3], [1, -3], [1, 3], [-1, 3]]), square, 2.7, 2.7),
        'insert_collinear': (np.insert(square, 1, [0, -2], axis=0), square, 2.7, 2.7),
        'cyclic_shift': (np.roll(square, 2, axis=0), square, 2.7, 2.7),
        'reverse_ring': (square[::-1], square, 2.7, 2.7),
        'small_bump': (bump, square, 2.7, 2.7),
        'omit_block': (np.array([[-2, -2], [.5, -2], [.5, 2], [-2, 2]]), square, 2.7, 2.7),
        'top_only': (square, square, 3.4, 2.7),
        'known_corner_deformation': (square+np.array([[.02, .02], [.03, -.01], [-.04, .02], [0, .03]]), square, 2.7, 2.7),
        'invalid': (square[[0, 2, 1, 3]], square, 2.7, 2.7),
    }


def _source_labels():
    """身份来自合成生成过程的显式定义，绝不根据点数或最近距离推断。"""
    quad = ['SW', 'SE', 'NE', 'NW']
    return {
        'l_order': (['L5', 'L0', 'L3', 'L1', 'L2', 'L4'], ['L0', 'L1', 'L2', 'L3', 'L4', 'L5']),
        'same_centroid_different_shape': (quad, quad),
        'symmetric_expansion': (quad, quad),
        'same_summary_horizontal': (quad, quad),
        'same_summary_vertical': (quad, quad),
        'insert_collinear': (['SW', 'south_midpoint', 'SE', 'NE', 'NW'], quad),
        'cyclic_shift': (['NE', 'NW', 'SW', 'SE'], quad),
        'reverse_ring': (['NW', 'NE', 'SE', 'SW'], quad),
        'small_bump': (['SW', 'SE', 'bump0', 'bump1', 'bump2', 'bump3', 'NE', 'NW'], quad),
        'omit_block': (quad, quad),
        'top_only': (quad, quad),
        'known_corner_deformation': (quad, quad),
        'invalid': (['SW', 'NE', 'SE', 'NW'], quad),
    }


def _point_correspondence(a, b, ha, hb, labels_a, labels_b):
    for points, labels in [(a, labels_a), (b, labels_b)]:
        if len(points) != len(labels) or len(set(labels)) != len(labels):
            raise ValueError('invalid_explicit_source_identity')
    common = [label for label in labels_a if label in labels_b]
    ai = [labels_a.index(label) for label in common]
    bi = [labels_b.index(label) for label in common]
    horizontal_squared = np.sum((np.asarray(a)[ai]-np.asarray(b)[bi])**2, axis=1)
    top_squared = horizontal_squared+(ha-hb)**2
    return dict(status='explicit_synthetic_correspondence', source_labels_a=labels_a, source_labels_b=labels_b,
                matched_labels=common, matched_corners=len(common),
                unmatched_a=len(labels_a)-len(common), unmatched_b=len(labels_b)-len(common),
                floor_rmse=float(np.sqrt(horizontal_squared.mean())) if common else None,
                top_rmse=float(np.sqrt(top_squared.mean())) if common else None,
                combined_rmse=float(np.sqrt(np.r_[horizontal_squared, top_squared].mean())) if common else None,
                definition='sqrt(mean(squared Euclidean distance per matched 3D endpoint)); unmatched corners retained separately')


def _manhattan(points):
    try:
        _polygon(points)
    except ValueError as exc:
        return dict(status='invalid_polygon', reason=str(exc), frame_deg=None, mean_deg=None, max_deg=None)
    p = np.asarray(points, float)
    edge = np.roll(p, -1, axis=0)-p
    lengths = np.linalg.norm(edge, axis=1)
    if (lengths <= 1e-12).any():
        return dict(status='zero_length_edge', frame_deg=None, mean_deg=None, max_deg=None)
    frame = heading_frame(p)
    angle = np.arctan2(edge[:, 1], edge[:, 0])
    residual = np.degrees(np.abs((angle-frame+np.pi/4) % (np.pi/2)-np.pi/4))
    return dict(status='ok', frame_deg=float(np.degrees(frame)), mean_deg=float(residual.mean()),
                length_weighted_mean_deg=float(np.average(residual, weights=lengths)),
                max_deg=float(residual.max()), per_edge_deg=residual.tolist(),
                definition='one common Manhattan frame independently fitted per layout using existing heading_frame; self-consistency only')


def _explicit_curves(xz, room_height):
    """每条空间直线独立投影；保留遮挡的边，不把它们强制写成单值包络。"""
    p = np.asarray(xz)
    curves = []
    for side_height in [room_height-1, -1]:
        for a, b in zip(p, np.roll(p, -1, axis=0)):
            xy = a+(b-a)*np.linspace(0, 1, 129)[:, None]
            x = (np.arctan2(xy[:, 0], -xy[:, 1])/(2*np.pi)+.5)*1024-.5
            y = (.5-np.arctan2(side_height, np.linalg.norm(xy, axis=1))/np.pi)*512-.5
            cuts = np.r_[0, np.flatnonzero(np.abs(np.diff(x)) > 512)+1, len(x)]
            curves.extend(np.c_[x[lo:hi], y[lo:hi]] for lo, hi in zip(cuts[:-1], cuts[1:]))
    return curves


def _figures(out, scenarios, results, masks):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors = ['#c55220', '#146c94']
    fig, axes = plt.subplots(2, 3, figsize=(14, 8), constrained_layout=True)
    a, b, ha, hb = scenarios['l_order']
    for points, label, color in [(a, 'longitude order', colors[0]), (b, 'physical order', colors[1])]:
        p = np.vstack([points, points[0]])
        axes[0, 0].plot(p[:, 0], p[:, 1], '-o', color=color, label=label)
    axes[0, 0].scatter([0], [0], marker='*', s=100, c='black', label='camera')
    axes[0, 0].set_aspect('equal'); axes[0, 0].legend(fontsize=8)
    axes[0, 0].set_title('Same points, different adjacency\nBEV IoU = 4/7')
    for points, height, color in [(a, ha, colors[0]), (b, hb, colors[1])]:
        for curve in _explicit_curves(points, height):
            axes[0, 1].plot(curve[:, 0], curve[:, 1], color=color, alpha=.8)
    axes[0, 1].set(xlim=(0, 1024), ylim=(512, 0), title='Explicit 3D straight-edge projection\nIncludes occluded edges')
    for ax, key, title in [(axes[0, 2], 'erp_sorted_curve', 'Sorted ERP curves'),
                           (axes[1, 0], 'erp_sorted_linear', 'Sorted ERP straight segments'),
                           (axes[1, 1], 'erp_visible', 'First-hit visibility from explicit ring')]:
        ma, mb = masks['l_order'][key]
        rgb = np.ones((*ma.shape, 3))
        rgb[ma & mb] = [.5, .64, .66]; rgb[ma & ~mb] = [1, .54, .3]; rgb[mb & ~ma] = [.24, .65, .95]
        ax.imshow(rgb, extent=(0, 1024, 512, 0), aspect='auto')
        ax.set_title(title+'\nIoU = '+format(results['l_order'][key]['iou'], '.4f'))
    axes[1, 2].axis('off')
    axes[1, 2].text(0, .95, 'Orange: longitude order\nBlue: physical order\nGray: intersection\n\nFull footprint and visible wall band\nare different measurement targets.\n\nNo vertex coordinates were changed.\nNo order was inferred or optimized.\nEqual-height 3D IoU = BEV IoU.', va='top', fontsize=11)
    name = 'order_representation.png'; fig.savefig(out/name, dpi=160); plt.close(fig)
    figures = [name]
    chosen = ['same_centroid_different_shape', 'symmetric_expansion', 'same_summary_horizontal',
              'same_summary_vertical', 'small_bump', 'omit_block']
    fig, axes = plt.subplots(2, 3, figsize=(13, 8), constrained_layout=True)
    for ax, key in zip(axes.flat, chosen):
        a, b, *_ = scenarios[key]
        for points, color in [(b, colors[1]), (a, colors[0])]:
            p = np.vstack([points, points[0]]); ax.plot(p[:, 0], p[:, 1], color=color)
        m = results[key]['bev']
        ax.set_aspect('equal'); ax.set_title(key.replace('_', ' ')+'\nIoU={:.4f}; centroid distance={:.4f}'.format(m['iou'], m['centroid_distance']))
    name = 'centroid_counterexamples.png'; fig.savefig(out/name, dpi=160); plt.close(fig); figures.append(name)
    return figures


def run(out: Path):
    """唯一报告入口；返回有限 JSON 数据，图和 JSON 仅写入指定输出目录。"""
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    scenarios, results, masks = _scenarios(), {}, {}
    identities = _source_labels()
    if set(identities) != set(scenarios):
        raise ValueError('synthetic_source_identity_missing')
    for name, (a, b, ha, hb) in scenarios.items():
        result = dict(points_a=a.tolist(), points_b=b.tolist(), height_a=ha, height_b=hb,
                      bev=polygon_metrics(a, b, ha, hb),
                      point_correspondence=_point_correspondence(a, b, ha, hb, *identities[name]),
                      manhattan=dict(a=_manhattan(a), b=_manhattan(b)))
        masks[name] = {}
        for mode, key in [('curve', 'erp_sorted_curve'), ('linear', 'erp_sorted_linear'), ('visible', 'erp_visible')]:
            try:
                if mode == 'visible':
                    pair = [nearest_wall_mask(p, h) for p, h in [(a, ha), (b, hb)]]
                else:
                    pair = [wall_mask(pairs_from_floor(p, h), mode=mode) for p, h in [(a, ha), (b, hb)]]
                masks[name][key] = pair
                result[key] = dict(status='ok', **compare_regions(*pair))
            except ValueError as exc:
                result[key] = dict(status='not_computable', reason=str(exc), iou=None)
        results[name] = result
    seam_a = np.zeros((128, 256), bool); seam_b = seam_a.copy()
    seam_a[35:90, :32] = True; seam_b[35:90, 16:48] = True
    seam = [dict(roll_columns=k, **compare_regions(np.roll(seam_a, k, 1), np.roll(seam_b, k, 1))) for k in [0, 240]]
    latitudes = [.5, 1, 5, 15, 45]
    horizon = []
    for degrees in latitudes:
        phi, delta = np.radians(degrees), np.pi/512
        radius, shifted = 1/np.tan(phi), 1/np.tan(phi+delta)
        horizon.append(dict(floor_depression_deg=degrees, radius=float(radius),
                            depth_change_one_px=float(radius-shifted),
                            relative_depth_change_one_px=float((radius-shifted)/radius)))
    short = [dict(edge_length=length, perpendicular_endpoint_error=.01,
                  angle_error_deg=math.degrees(math.atan2(.01, length))) for length in [.02, .1, 1, 5]]
    heights = dict(status='controlled_height_only', bev_iou=1., height_a=3.4, height_b=2.7,
                   volume_iou=2.7/3.4)
    result = dict(schema_version='layout_metric_probe_20260926_v1', scope='synthetic_diagnostic_only',
                  lambda_grid=LAMBDAS, cases=results,
                  sensitivities=dict(seam=seam, near_horizon=horizon, short_edge=short, height_only=heights),
                  definitions=dict(camera_height=1, camera_origin=[0, 0, 0], floor_y=-1,
                                   scale='shared_camera_height_not_individual_normalization',
                                   erp_shape=[256, 512], reported_erp_pixels=[1024, 512],
                                   boundary_distance='symmetric_uniform_arclength_512_samples_each_direction',
                                   bev_scores='(1-BEV_IoU)+lambda*centroid_distance/sqrt(reference_area)',
                                   erp_scores='(1-ERP_IoU)+lambda*ERP_centroid_distance/hypot(1024,512)',
                                   circular_scores='(1-ERP_IoU)+lambda*hypot(circular_dx,dy)/hypot(1024,512)',
                                   spherical_scores='(1-solid_angle_IoU)+lambda*direction_angle/pi',
                                   spherical_degenerate='resultant<=1e-12 returns no direction or direction score',
                                   adjacency='fixed_explicit_synthetic_rings_no_search',
                                   invalid_policy='explicit_state_no_repair_no_zero_substitution'),
                  limitations=['Synthetic known geometry does not validate human annotation quality.',
                               'ERP x-sorted curves and straight segments intentionally ignore source adjacency.',
                               'Nearest-ray mask measures visible wall rays, not complete footprint.',
                               'Spherical moments can cancel; a direction is not a room centroid.',
                               'Heights are controlled constants; no general nonplanar volume is claimed.',
                               'Point RMSE uses declared synthetic identities; missing/extra points remain unmatched, never silently matched by array position.',
                               'Manhattan residual is internal geometric conformity; zero residual or zero point RMSE does not establish correct scope or topology.',
                               'Boundary summaries are numerical quadrature, not exact continuous Hausdorff.',
                               'Weights are a sensitivity grid; none is selected or calibrated.'])
    result['summary'] = dict(
        order_information_loss=dict(analytic_bev_iou=4/7,
                                    measured_bev_iou=results['l_order']['bev']['iou'],
                                    sorted_erp_iou=results['l_order']['erp_sorted_curve']['iou'],
                                    visible_erp_iou=results['l_order']['erp_visible']['iou']),
        nonidentifiability=dict(reference_square=[[-2, -2], [2, -2], [2, 2], [-2, 2]],
                                candidate_areas=[12, 12], intersection_areas=[8, 8],
                                union_areas=[20, 20], ious=[.4, .4], centroids=[[0, 0], [0, 0]],
                                all_lambda_scores_equal=True,
                                meaning='Different horizontal/vertical local errors have identical IoU and centroid summaries.'),
        same_center_expansion_iou=results['symmetric_expansion']['bev']['iou'],
        small_bump=dict(iou=results['small_bump']['bev']['iou'],
                        centroid_distance=results['small_bump']['bev']['centroid_distance']),
        scope='Mathematical counterexamples and implementation checks; not human-quality validation.',
        sensitivity_only='Short-edge and horizon probes quantify propagation; no rejection or relaxation threshold is set.')
    result['figures'] = _figures(out, scenarios, results, masks)
    (out/'geometry_results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report = run(args.out)
    print(json.dumps(dict(cases=len(report['cases']), figures=report['figures'], output=str(args.out))))
