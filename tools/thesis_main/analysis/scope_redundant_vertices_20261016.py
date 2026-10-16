"""多空间的旧点职责、精确冗余和精度内结构简化；只生成派生视图。"""
import copy
import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np
from shapely.geometry import Point, Polygon

from tools.label_studio.panorama_studio.geometry import project_pixel
from .scope_difficulty_review_20261011 import floor_features

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/data/scope_redundant_vertices_20261016'
EPS = 1e-8


def edge_sources(kept, n):
    result = []
    for i, start in enumerate(kept):
        end = kept[(i + 1) % len(kept)]
        result.append([j % n + 1 for j in range(start, end if end > start else end + n)])
    return result


def normalize_boundary(floor, heights=None):
    """保持环序和原编号，底面与完整点对分别简化；未知高度不推断。"""
    p = np.asarray(floor, float)
    if (p.ndim != 2 or p.shape[1] != 2 or len(p) < 3 or not np.isfinite(p).all()
            or np.any(np.linalg.norm(p - np.roll(p, 1, axis=0), axis=1) <= EPS)):
        raise ValueError('invalid floor coordinates or zero edge')
    poly = Polygon(p)
    if not poly.is_valid or poly.area <= EPS:
        raise ValueError('invalid floor polygon')
    h = None if heights is None else np.asarray(heights, float)
    if h is not None and (h.shape != (len(p),) or not np.isfinite(h).all() or np.any(h <= 0)):
        raise ValueError('invalid paired heights')
    straight = [i - 1 for i in floor_features(p)['straight_vertices_1based']]
    keep = [i for i in range(len(p)) if i not in straight]
    reduced = Polygon(p[keep])
    if poly.hausdorff_distance(reduced) > EPS or poly.symmetric_difference(reduced).area > EPS:
        raise ValueError('numerical collinearity changes represented boundary')
    pair_keep, breaks = list(range(len(p))), []
    if h is not None:
        while True:
            removed = False
            for j in floor_features(p[pair_keep])['straight_vertices_1based']:
                j -= 1
                a, i, b = pair_keep[j - 1], pair_keep[j], pair_keep[(j + 1) % len(pair_keep)]
                t = np.dot(p[i] - p[a], p[b] - p[a]) / np.dot(p[b] - p[a], p[b] - p[a])
                if abs(h[i] - ((1 - t) * h[a] + t * h[b])) <= EPS:
                    pair_keep.remove(i)
                    removed = True
                    break
            if not removed:
                break
        breaks = [i + 1 for i in straight if i in pair_keep]
    return dict(floor=p[keep].tolist(), floor_kept_1based=[i + 1 for i in keep],
        floor_removed_1based=[i + 1 for i in straight],
        floor_edge_source_indices_1based=edge_sources(keep, len(p)),
        pair_floor=p[pair_keep].tolist() if h is not None else None,
        pair_heights=h[pair_keep].tolist() if h is not None else None,
        pair_kept_1based=[i + 1 for i in pair_keep] if h is not None else None,
        pair_removed_1based=[i + 1 for i in range(len(p)) if i not in pair_keep] if h is not None else None,
        height_break_1based=breaks if h is not None else None)


def precision_floor_view(floor):
    """0.01像素是现有ERP存储精度的筛查尺度，不证明物理上严格共线。"""
    p = np.asarray(floor, float)
    keep, removed = list(range(len(p))), []
    while len(keep) > 3:
        found = False
        for j, i in enumerate(keep):
            a, b = p[keep[j - 1]], p[keep[(j + 1) % len(keep)]]
            u, v, chord = p[i] - a, b - p[i], b - a
            angle = abs(float(np.degrees(np.arctan2(u[0] * v[1] - u[1] * v[0], u @ v))))
            t = float((p[i] - a) @ chord / (chord @ chord))
            if angle > .05 or not 0 < t < 1:
                continue
            projected = a + t * chord
            def pixel(x):
                return np.asarray(project_pixel([x[0], -1, x[1]], 1024, 512))
            delta = pixel(p[i]) - pixel(projected)
            delta[0] = (delta[0] + 512) % 1024 - 512
            distance = float(np.linalg.norm(p[i] - projected))
            if np.linalg.norm(delta) > .01 or distance > .001:
                continue
            keep.remove(i)
            removed.append(dict(original_vertex_1based=i + 1, turn_deg=angle,
                displacement_px=float(np.linalg.norm(delta)), displacement_h=distance))
            found = True
            break
        if not found:
            break
    q = p[keep]
    return dict(floor=q.tolist(), kept_1based=[i + 1 for i in keep], removed=removed,
        edge_source_indices_1based=edge_sources(keep, len(p)),
        symmetric_difference_area_h2=float(Polygon(p).symmetric_difference(Polygon(q)).area),
        hausdorff_distance_h=float(Polygon(p).hausdorff_distance(Polygon(q))),
        use='structural display/diagnostic only; not a replacement scoring reference')


def old_vertex_roles(old, new):
    """按新目标逐点记录旧坐标的位置关系，不把位置近似冒充点对应。"""
    p, q, poly = np.asarray(old), np.asarray(new), Polygon(new)
    result = []
    for i, x in enumerate(p):
        matched = np.flatnonzero(np.linalg.norm(q - x, axis=1) <= EPS)
        point = Point(x)
        status = ('same_coordinate_vertex' if len(matched) else 'on_new_edge_not_vertex'
                  if poly.boundary.distance(point) <= EPS else 'inside_new_scope_not_vertex'
                  if poly.contains(point) else 'outside_new_scope')
        result.append(dict(old_vertex_1based=i + 1, relation=status,
            matched_new_vertices_1based=(matched + 1).tolist()))
    return result


def compact_geometry(geometry, kept):
    result = copy.deepcopy(geometry)
    for key in ['bottom3d', 'top3d']:
        result[key] = [geometry[key][i - 1] for i in kept]
    if 'points_1024x512' in result:
        result['points_1024x512'] = [x for i in kept for x in geometry['points_1024x512'][2*i-2:2*i]]
    return result


def run():
    from ..data_prep.consolidate_research_input import load_current_bundle
    from .scope_reference_reconstruction_20261016 import build_reference_catalog
    from .scope_quality_binding_20261016 import build_affected_records
    from .scope_quality_scoring_20261016 import scoring_engine

    pointer_path = ROOT / 'analysis_results/image_difficulty_full_review_20261010/CURRENT.json'
    pointer_bytes = pointer_path.read_bytes()
    ptr = json.loads(pointer_bytes)
    details = (pointer_path.parent / ptr['details']).resolve()
    difficulty = json.loads(details.read_text(encoding='utf-8'))
    bundle = load_current_bundle()
    refs = build_reference_catalog(bundle, difficulty['records'])
    selected = [r for r in refs if r['current_target'] or r['is_admitted_space_candidate']]
    diff_by_image = {r['image_id']: r for r in difficulty['records']}
    audit, views, scope_rows, changed_full = [], [], [], {}
    for r in selected:
        p = r['floor_xz_h']
        exact = normalize_boundary(p)
        precision = precision_floor_view(p)
        row = {key:r[key] for key in ['target_id','image_id','image_code','current_target','role','full_reference_available']}
        row.update(raw_vertices=len(p), exact_turns=len(exact['floor']),
            precision_turns=len(precision['floor']), exact_removed=exact['floor_removed_1based'],
            precision_removed=[x['original_vertex_1based'] for x in precision['removed']])
        audit.append(row)
        is_scope = r['role'] in ['confirmed_scope','confirmed_space_candidate']
        if not is_scope and not precision['removed']:
            continue
        old = diff_by_image[r['image_id']]['candidates'][0]
        roles = old_vertex_roles(old['floor'], p)
        view = dict(**row, original_floor=p, exact_floor_view=exact,
            precision_floor_view=precision, original_comparison_target_id=old['target_id'],
            old_floor=old['floor'], old_vertex_roles=roles,
            reference_method=r['method'], introduced_scope_edges=r.get('introduced_scope_edges'),
            physical_wall_asserted=r.get('physical_wall_asserted'), paired_view=None)
        if r['full_reference_available']:
            g = r['geometry'];bottom=np.asarray(g['bottom3d']);top=np.asarray(g['top3d'])
            pair = normalize_boundary(bottom[:,[0,2]], top[:,1]-bottom[:,1])
            view['paired_view'] = dict(mapping=pair,
                geometry=compact_geometry(g,pair['pair_kept_1based']),
                points_1024x512=[x for i in pair['pair_kept_1based'] for x in r['points_1024x512'][2*i-2:2*i]])
            if pair['pair_removed_1based']:
                changed_full[r['target_id']] = view
        views.append(view)
        scope_rows.append(dict(**row, old_vertices=len(old['floor']),
            old_coordinate_relations=dict(Counter(x['relation'] for x in roles)),
            original_scope_symmetric_difference_h2=float(Polygon(old['floor']).symmetric_difference(Polygon(p)).area),
            pair_removed=(view['paired_view']['mapping']['pair_removed_1based'] if view['paired_view'] else None),
            precision_area_change_h2=precision['symmetric_difference_area_h2'],
            precision_max_distance_h=precision['hausdorff_distance_h']))

    binding = build_affected_records(bundle,difficulty['records'],refs)
    objects = {r['object_id']:r for r in bundle['data']['objects']}
    comparisons = []
    with scoring_engine() as (engine,models):
        def measure(a, ref):
            result = engine.measure(a,ref)
            if result['status'] != 'complete':
                raise ValueError(result)
            m = result['metrics']
            return dict(**m,B8L2=float(models.score(*[m[k] for k in ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']],models.B)))
        for tid, view in changed_full.items():
            r = next(r for r in selected if r['target_id']==tid)
            original = engine.geometry(r['points_1024x512'])
            reduced = compact_geometry(original,view['paired_view']['mapping']['pair_kept_1based'])
            answers = [('reference_self',original,False)]
            for b in binding['affected_records']:
                if b.get('chosen_target_id')==tid and b['score_input_eligible']:
                    answers.append((b['object_id'],engine.geometry(objects[b['object_id']]['points_1024x512']),
                        bool(b['person_quality_restriction_clear'] and b['pool_analysis_eligible'])))
            for oid, a, admitted in answers:
                before, after = measure(a,original), measure(a,reduced)
                ab, at = np.asarray(a['bottom3d']), np.asarray(a['top3d'])
                av = normalize_boundary(ab[:,[0,2]],at[:,1]-ab[:,1])
                both = measure(compact_geometry(a,av['pair_kept_1based']),reduced)
                comparisons.append(dict(target_id=tid,image_code=r['image_code'],object_id=oid,
                    current_analysis_eligible=admitted,before=before,after_reference_compaction=after,
                    delta={k:after[k]-before[k] for k in before},
                    answer_removed_1based=av['pair_removed_1based'],after_both_compaction=both,
                    both_delta={k:both[k]-before[k] for k in before}))
    assert pointer_path.read_bytes()==pointer_bytes, 'difficulty changed during audit'
    checks = dict(version='scope_redundant_vertices_20261016_v1',difficulty_version=difficulty['version'],
        admitted_or_current_references=len(selected),scope_views=len(scope_rows),
        scope_images=len({r['image_id'] for r in scope_rows}),
        exact_redundant_targets=sum(bool(r['exact_removed']) for r in audit),
        precision_redundant_targets=sum(bool(r['precision_removed']) for r in audit),
        current_exact_targets=sum(r['current_target'] and bool(r['exact_removed']) for r in audit),
        current_precision_targets=sum(r['current_target'] and bool(r['precision_removed']) for r in audit),
        full_pair_compaction_targets=len(changed_full),score_comparisons=len(comparisons),
        bound_answer_comparisons=sum(r['object_id']!='reference_self' for r in comparisons),
        max_abs_B8L2_delta=max((abs(r['delta']['B8L2']) for r in comparisons),default=0),
        max_abs_B8L2_both_delta=max((abs(r['both_delta']['B8L2']) for r in comparisons),default=0),
        raw_data_changed=False,reference_eligibility_changed=False,production_scores_changed=False,
        input_sources=[details.relative_to(ROOT).as_posix(),'analysis_results/research_input_20260929/manifest.json'],
        precision_screen=dict(max_turn_deg=.05,max_ERP_displacement_px=.01,max_displacement_h=.001),
        index_convention='All output vertex and edge indices are 1-based; introduced_scope_edges copied from source remain 0-based.')
    OUT.mkdir(exist_ok=True,parents=True)
    for name,data in [('inventory',audit),('scope_views',views),('scope_summary',scope_rows),('score_comparison',comparisons),('CHECKS',checks)]:
        (OUT/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    for name,rows in [('inventory',audit),('scope_summary',scope_rows)]:
        with (OUT/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader()
            writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rows)
    print(json.dumps(checks,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    run()
