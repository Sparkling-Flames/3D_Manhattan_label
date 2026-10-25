"""既定GT环的循环x顺序与声明底面自遮挡审计；不读取人员表现或难度标签。"""
from __future__ import annotations

from collections import Counter
import json

import numpy as np
from shapely.geometry import Point, Polygon

from tools.thesis_main.analysis.research_artifact_io import ROOT, write_csv, write_json
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle

OUT = ROOT / 'analysis_results/gt_order_visibility_20261009'
EPS = 1e-8


def classify_ring_x(xs):
    x = np.asarray(xs, dtype=float) % 1024
    if x.ndim != 1 or len(x) < 3 or not np.isfinite(x).all():
        raise ValueError('invalid_ring_x')
    monotonic = lambda v: any(np.all(np.diff(np.roll(v, -j)) >= -1e-6) for j in range(len(v)))
    increasing, decreasing = monotonic(x), monotonic(x[::-1])
    kind = 'cyclic_increasing' if increasing else 'cyclic_decreasing' if decreasing else 'local_backtracking'
    delta = (np.roll(x, -1) - x + 512) % 1024 - 512
    direction = 1 if delta.sum() >= 0 else -1
    backward = direction * delta < -1e-6
    ties = [[i + 1, j + 1] for i in range(len(x)) for j in range(i + 1, len(x))
            if abs((x[i] - x[j] + 512) % 1024 - 512) <= 1e-6]
    return dict(x_order_class=kind, same_x_pairs=bool(ties), same_x_pair_indices_1based=ties,
                starts_at_min_x=bool(abs(x[0] - x.min()) <= 1e-6),
                x_sequence=x.tolist(), backward_edge_count=int(backward.sum()),
                backward_angular_degrees=float(-np.sum(direction * delta[backward]) * 360 / 1024),
                backward_edges_1based=[[i + 1, (i + 1) % len(x) + 1]
                                      for i in np.flatnonzero(backward).tolist()])


def cross(a, b):
    return float(a[0] * b[1] - a[1] * b[0])


def visibility_from_floor(floor):
    """相机原点→顶点：横穿非相邻边为遮挡；擦角／沿墙退化情况另列。"""
    xy = np.asarray(floor, dtype=float)
    if xy.ndim != 2 or xy.shape[1] != 2 or len(xy) < 3 or not np.isfinite(xy).all():
        raise ValueError('invalid_floor_array')
    poly = Polygon(xy)
    if not poly.is_valid or poly.area <= 0:
        return dict(status='invalid_polygon', hidden_vertices_1based=None, visibility=[])
    if not poly.contains(Point(0, 0)):
        return dict(status='camera_not_strictly_inside', hidden_vertices_1based=None, visibility=[])
    result = []
    for i, target in enumerate(xy):
        blockers, contacts = [], []
        for j, a in enumerate(xy):
            end = (j + 1) % len(xy)
            if i in (j, end):
                continue
            b = xy[end]
            edge = b - a
            denom = cross(target, edge)
            tolerance = EPS * np.linalg.norm(target) * np.linalg.norm(edge)
            if abs(denom) <= tolerance:
                if abs(cross(a, target)) <= EPS * np.linalg.norm(target) * max(np.linalg.norm(a), 1):
                    lo, hi = sorted([float(a @ target / (target @ target)), float(b @ target / (target @ target))])
                    if hi > EPS and lo < 1 - EPS:
                        contacts.append([j + 1, end + 1])
                continue
            t, s = cross(a, edge) / denom, cross(a, target) / denom
            if EPS < t < 1 - EPS and -EPS <= s <= 1 + EPS:
                if EPS < s < 1 - EPS:
                    blockers.append(dict(edge_1based=[j + 1, end + 1], ray_fraction=t, edge_fraction=s,
                                         intersection_xy=(t * target).tolist()))
                else:
                    contacts.append([j + 1, end + 1])
        blockers.sort(key=lambda z: z['ray_fraction'])
        status = 'occluded_by_boundary' if blockers else 'grazing_or_collinear' if contacts else 'visible_in_floor_model'
        result.append(dict(vertex_1based=i + 1, status=status, blockers=blockers, contacts=contacts))
    return dict(status='valid_camera_inside',
                hidden_vertices_1based=[v['vertex_1based'] for v in result if v['status'] == 'occluded_by_boundary'],
                grazing_vertices_1based=[v['vertex_1based'] for v in result if v['status'] == 'grazing_or_collinear'],
                visibility=result)


def vertical_wall_occlusion(visibility, top_heights):
    """相机z=0、底面z=-1；按GT顶边插值的实心竖直墙，解析整个角线高度区间。"""
    heights = np.asarray(top_heights, dtype=float)
    if not np.isfinite(heights).all() or np.any(heights <= 0):
        raise ValueError('ceiling_not_above_camera')
    result = []
    for vertex in visibility:
        if vertex['status'] != 'occluded_by_boundary':
            continue
        height = heights[vertex['vertex_1based'] - 1]
        upper_limits = []
        for hit in vertex['blockers']:
            a, b = [n - 1 for n in hit['edge_1based']]
            wall_top = (1 - hit['edge_fraction']) * heights[a] + hit['edge_fraction'] * heights[b]
            # At fraction t, target z maps to t*z; blocker spans [-1, wall_top].
            upper_limits.append(wall_top / hit['ray_fraction'])
        limit = max(upper_limits)
        result.append(dict(vertex_1based=vertex['vertex_1based'], target_top_z=float(height),
                           occluded_target_z_upper=float(min(height, limit)),
                           hidden_height_fraction=float((min(height, limit) + 1) / (height + 1)),
                           fully_occluded=bool(limit >= height - EPS)))
    return dict(fully_occluded_vertical_pairs_1based=[r['vertex_1based'] for r in result if r['fully_occluded']],
                partial_wall_occlusion_pairs_1based=[r['vertex_1based'] for r in result if not r['fully_occluded']],
                vertical_occlusion=result)


def audit_object(obj, population):
    p = np.asarray(obj['points_1024x512'], dtype=float)
    if p.ndim != 2 or p.shape[1] != 2 or len(p) % 2 or not np.isfinite(p).all():
        raise ValueError('invalid_gt_pairs:' + obj['object_id'])
    if not np.allclose(p[::2, 0], p[1::2, 0], rtol=0, atol=1e-6):
        raise ValueError('unshared_gt_x:' + obj['object_id'])
    row = dict(image=obj['image_code'], image_id=obj['image_id'], object_id=obj['object_id'],
               kind=obj['object_kind'], population=population, source=obj['source'],
               ring_confirmed=obj['ring_confirmed'], order_status=obj['order_status'], pair_count=len(p)//2,
               ordered_source_pair_indices=obj['ordered_source_pair_indices'],
               **classify_ring_x(p[::2, 0]))
    order = np.asarray(obj['ordered_source_pair_indices'])
    row['source_adjacency_changed'] = not any(np.array_equal(order, np.roll(v, j))
        for v in (np.arange(len(order)), np.arange(len(order))[::-1]) for j in range(len(order)))
    floor = p[1::2]
    v = (floor[:, 1] / 512 - .5) * np.pi
    if np.any(v <= 0) or np.any(v >= np.pi / 2):
        row.update(geometry_status='floor_not_below_horizon', hidden_count=None,
                   hidden_vertices_1based=None, grazing_vertices_1based=None, floor_xy=None, visibility=[])
        return row
    u = (floor[:, 0] / 1024 - .5) * 2 * np.pi
    r = 1 / np.tan(v)
    xy = np.stack([r * np.sin(u), -r * np.cos(u)], axis=1)
    vis = visibility_from_floor(xy)
    row.update(geometry_status=vis.pop('status'), floor_xy=xy.tolist(), **vis)
    row['hidden_count'] = None if row['hidden_vertices_1based'] is None else len(row['hidden_vertices_1based'])
    ceiling_v = (p[::2, 1] / 512 - .5) * np.pi
    if row['geometry_status']=='valid_camera_inside' and np.all(ceiling_v < 0) and np.all(ceiling_v > -np.pi/2):
        row.update(vertical_wall_occlusion(row['visibility'], -r * np.tan(ceiling_v)))
        row['vertical_wall_test_status']='computed_from_gt_top_and_bottom'
    else:
        row.update(fully_occluded_vertical_pairs_1based=None, partial_wall_occlusion_pairs_1based=None,
                   vertical_occlusion=[], vertical_wall_test_status='geometry_or_ceiling_unavailable')
    return row


def summarize(rows):
    return dict(n=len(rows), x_order=dict(Counter(r['x_order_class'] for r in rows)),
                same_x=sum(r['same_x_pairs'] for r in rows),
                valid_camera_inside=sum(r['geometry_status']=='valid_camera_inside' for r in rows),
                any_transverse_occlusion=sum((r['hidden_count'] or 0)>0 for r in rows),
                any_full_height_wall_occlusion=sum(bool(r.get('fully_occluded_vertical_pairs_1based')) for r in rows),
                any_partial_height_only_pair=sum(bool(r.get('partial_wall_occlusion_pairs_1based')) for r in rows),
                non_min_start_monotonic=sum(r['x_order_class']!='local_backtracking' and not r['starts_at_min_x'] for r in rows))


def plot_revised(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    chosen = [r for r in rows if r['kind']=='gt_manual_revision' and r['x_order_class']=='local_backtracking']
    fig, axes = plt.subplots((len(chosen)+2)//3, 3, figsize=(12, 12), squeeze=False)
    for ax, row in zip(axes.flat, chosen):
        xy = np.asarray(row['floor_xy']); closed = np.vstack([xy, xy[0]])
        ax.fill(closed[:,0], closed[:,1], color='#e8eef3')
        ax.plot(closed[:,0], closed[:,1], color='#34495e', lw=1.6)
        hidden = row['hidden_vertices_1based']
        for i, pt in enumerate(xy):
            color = '#cf382f' if i+1 in hidden else '#176d99'
            ax.scatter(*pt, color=color, s=20, zorder=3)
            if i+1 in hidden:
                offset=(-12, 8) if i % 2 == 0 else (8, 8)
                ax.annotate(str(i+1), pt, xytext=offset, textcoords='offset points', fontsize=9, color=color)
                ax.plot([0,pt[0]], [0,pt[1]], '--', color=color, lw=.8)
        ax.scatter(0,0,marker='*',s=90,color='#e5a000',edgecolor='#6b5000',zorder=5)
        ax.set_title(f"{row['image']} | hidden {row['hidden_count']}/{row['pair_count']}",fontsize=10)
        ax.set_aspect('equal',adjustable='datalim');ax.grid(alpha=.15);ax.margins(.15)
    for ax in list(axes.flat)[len(chosen):]:ax.axis('off')
    fig.suptitle('Confirmed revised GT rings: floor-model visibility\nRed = ray crosses another boundary; star = camera; red numbers = final pair positions',fontsize=13)
    fig.tight_layout(rect=(0,0,1,.95));fig.savefig(OUT/'revised_backtracking.png',dpi=170);plt.close(fig)


def main():
    bundle=load_current_bundle(); images={r['image_id']:r for r in bundle['data']['images']}
    rows=[audit_object(o,images[o['image_id']]['population']) for o in bundle['data']['objects']
          if o['object_kind'] in ('gt_original','gt_manual_revision')]
    rows.sort(key=lambda r:(r['image'],r['kind']))
    by_id={r['object_id']:r for r in rows}
    preferred=[by_id[im['references'].get('gt_manual_revision',im['references'].get('gt_original'))]
               for im in images.values() if im['population']=='research_annotation_image']
    for row in rows:row['selected_in_revised_preferred_research_view']=row in preferred
    manual=[r for r in rows if r['kind']=='gt_manual_revision']
    summary=dict(original=summarize([r for r in rows if r['kind']=='gt_original']),
                 manual_revision=summarize(manual), revised_preferred_research=summarize(preferred),
                 reference_only=summarize([r for r in rows if r['population']=='manual_gt_reference_only']))
    OUT.mkdir(parents=True,exist_ok=True)
    write_json(OUT/'summary.json',summary);write_json(OUT/'audit.json',rows)
    flat=[{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v
           for k,v in row.items() if k not in ('floor_xy','visibility','vertical_occlusion')} for row in rows]
    write_csv(OUT/'all_gt.csv',flat)
    write_csv(OUT/'revised_gt.csv',[r for r in flat if r['kind']=='gt_manual_revision'])
    write_csv(OUT/'research_revised_preferred.csv',[r for r in flat if r['selected_in_revised_preferred_research_view']])
    write_json(OUT/'field_contract.json',dict(schema='gt_order_visibility_audit_v1',
        input='analysis_results/research_input_20260929/manifest.json via load_current_bundle()',
        coordinates='continuous 1024x512; h=1, camera=(0,0); declared final ring, no sorting or geometry repair',
        x_order='cyclic start allowed; complete reversal separate but equivalent adjacency; same-x separate, tolerance 1e-6 pixel',
        ray_test='camera-to-vertex intersects nonincident boundary edge interior strictly before vertex; endpoint/collinear contact separate',
        index='all vertex/edge numbers one-based final pair positions; ordered_source_pair_indices remains original zero-based mapping',
        preferred='manual revision if present, else original, restricted to 259 research images; does not alter official reference policy',
        hidden_count='number of transverse-occluded floor vertices, not number of backward edges, not physical 3D full-height visibility',
        vertical_wall_test='floor z=-1, camera z=0; GT top z=-radius*tan(top_v). At each blocking wall interpolate its top by edge_fraction, then target z<=wall_top/ray_fraction is occluded. Union intervals to test the entire vertical pair; opaque solid walls without holes assumed.',
        limitations=['reference-dependent structural self-occlusion under opaque vertical wall assumptions',
                     'no furniture/material/opening or RGB visibility audit; full-height conclusion conditional on solid GT wall surfaces',
                     'not human difficulty or identified intrinsic uncertainty; GT may include scope or detail revisions',
                     'no worker responses, subjective difficulty labels or consensus outcomes used in feature calculation']))
    plot_revised(rows)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
