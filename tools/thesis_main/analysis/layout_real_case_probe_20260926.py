"""少量有既有连接证据的真实标注诊断；不搜索顺序、不更新裁决。"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from shapely.geometry import Point, Polygon
from shapely.validation import explain_validity

from tools.label_studio.panorama_studio.geometry import analyze, geometry_issues, pixel_ray
from tools.thesis_main.analysis.build_consensus_handoff_20260923 import read_json, write_json
from tools.thesis_main.analysis.consensus_region_20260923 import wall_mask, centroid, compare_masks
from tools.thesis_main.analysis.shared_x_reanalysis_20260922 import shared_x

ROOT = Path(__file__).resolve().parents[3]
COMMENTS = 'analysis_results/标注区域差异评论清单_20260926.json'
ORDER = 'analysis_results/order_preliminary_review_20260923/建议清单.json'
INPUTS = 'analysis_results/consensus_research_20260923/inputs'
SCREENSHOT_IDS = ('fc8f6754ddce3edb', '053bc4b35d6a7e89')
USER_ORDER = [0, 1, 2, 4, 3, 5]


def source_points(root, row, cache):
    """读取指定原件；派生快照只提供索引和核对坐标，不能替代原件。"""
    prov = row.get('provenance')
    source = prov['source'] if prov else row['raw_export_path']
    task = str(prov['task'] if prov else row['runtime_task_id'])
    ann = str(prov['annotation'] if prov else row['raw_annotation_id'])
    if not source:
        raise ValueError('raw_source_path_missing')
    path = root / source
    if not path.is_file():
        raise ValueError('raw_source_file_missing:' + source)
    if source not in cache:
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(payload, list):
            raise ValueError('raw_export_not_task_array')
        entries = [(str(t['id']), str(a['id']), a) for t in payload for a in t.get('annotations', [])]
        if len({(t, a) for t, a, _ in entries}) != len(entries):
            raise ValueError('duplicate_task_annotation_identity')
        cache[source] = {(t, a): r for t, a, r in entries}
    raw = cache[source].get((task, ann))
    if raw is None:
        raise ValueError('raw_task_annotation_missing')
    points = np.array([[r['value']['x']*1024/100, r['value']['y']*512/100]
                       for r in raw['result'] if r['type'] == 'keypointlabels'], float)
    expected = np.asarray(row['raw_points_1024x512'], float)
    if points.shape != expected.shape or not np.allclose(points, expected, rtol=0, atol=1e-8):
        raise ValueError('raw_coordinate_mismatch:' + row['canonical_annotation_id'])
    return points, dict(status='verified_against_raw_export', source=source, task=task, annotation=ann,
                        source_tier='runtime_raw_export' if source.startswith('export_label/') else 'archived_raw_export',
                        coordinate_units='LS_percent_scaled_to_1024x512_continuous_coordinates')


def candidate_reason(evidence):
    if evidence is None:
        return 'no_existing_order_evidence'
    if evidence['verdict'] != '无需调整':
        return 'existing_order_review_unresolved'
    # 此记录明示整段墙后走廊不可见；不把“未见新换序”当作隐藏连接已知。
    if evidence['image_code'] == 'e9zR4mvMWw7-09':
        return 'existing_evidence_hidden_adjacency_unresolved'
    return 'preliminary_order_evidence'


def valid_polygon(points):
    p = np.asarray(points, float)
    if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3 or not np.isfinite(p).all():
        raise ValueError('invalid_floor_points')
    poly = Polygon(p)
    if not poly.is_valid or poly.area < 1e-10:
        raise ValueError('invalid_floor_polygon:' + explain_validity(poly))
    return poly


def compare_footprints(first, second):
    a, b = valid_polygon(first), valid_polygon(second)
    # 按弧长等距采样至另一条完整边界；不同点数无需虚构角点对应。
    distances = []
    for p, q in ((a, b), (b, a)):
        distances.extend(p.boundary.interpolate(t, normalized=True).distance(q.boundary)
                         for t in np.linspace(0, 1, 512, endpoint=False))
    delta = np.array(a.centroid.coords[0]) - b.centroid.coords[0]
    return dict(iou=a.intersection(b).area/a.union(b).area,
                centroid_delta_camera_height=delta.tolist(), centroid_distance_camera_height=float(np.linalg.norm(delta)),
                normalized_centroid_distance=float(np.linalg.norm(delta)/np.sqrt(b.area)),
                area_camera_height_squared=[a.area, b.area],
                boundary_rms_camera_height=float(np.sqrt(np.mean(np.square(distances)))),
                boundary_sampled_hausdorff_camera_height=float(max(distances)),
                boundary_samples_per_polygon=512)


def floor_points(pairs):
    rays = np.array([pixel_ray(*p[1], 1024, 512) for p in pairs])
    if np.any(rays[:, 1] >= -1e-5):
        raise ValueError('floor_not_below_or_too_near_horizon')
    return (-rays/rays[:, 1, None])[:, [0, 2]]


def inspect_pairs(pairs):
    payload = dict(width=1024, height=512, coordinate_mode='pixels', ordered_pairs=[
        dict(source_pair_id=str(i), top=dict(zip(('x', 'y'), t)), bottom=dict(zip(('x', 'y'), b)))
        for i, (t, b) in enumerate(pairs)])
    geometry = analyze(payload, compute_fit=False)['raw']
    result = dict(pairs=pairs.tolist(), geometry_metrics=geometry['metrics'], geometry_issues=geometry['issues'],
                  geometry_coordinate_convention='continuous_x/width_y/height_no_pixel_center_offset')
    try:
        xy = floor_points(pairs)
        poly = valid_polygon(xy)
        result['bev'] = dict(status='conditional_geometry', floor_points=xy.tolist(), area=poly.area,
                             centroid=list(poly.centroid.coords[0]), issues=geometry_issues(xy),
                             camera_inside=poly.contains(Point(0, 0)), unit='camera_height=1',
                             interpretation='按已有证据给定的连接计算，不证明真实墙环；可见性异常与无效多边形分开')
    except ValueError as exc:
        result['bev'] = dict(status='unavailable', reason=str(exc))
    try:
        mask = wall_mask(pairs)
        result['erp'] = dict(status='envelope_diagnostic', centroid=centroid(mask),
                             coordinate_convention='legacy_wall_mask_pixel_center_offset',
                             note='按方位排序的单值墙带，不验证物理连接')
    except ValueError as exc:
        result['erp'] = dict(status='unavailable', reason=str(exc))
    return result


def pair_metrics(first, second, bev_allowed=True):
    result = {}
    try:
        result['erp'] = dict(status='envelope_diagnostic', **compare_masks(wall_mask(first), wall_mask(second)))
    except ValueError as exc:
        result['erp'] = dict(status='unavailable', reason=str(exc))
    if not bev_allowed:
        result['bev'] = dict(status='unavailable', reason='reference_order_evidence_missing')
    else:
        try:
            result['bev'] = dict(status='conditional_geometry', **compare_footprints(floor_points(first), floor_points(second)))
        except ValueError as exc:
            result['bev'] = dict(status='unavailable', reason=str(exc))
    return result


def plot_panel(path, image_path, title, panels, reference_pairs=None):
    """每行单份标注，避免多层填色掩盖点位；图是研究工件而非检查截图。"""
    background = np.asarray(Image.open(image_path).convert('RGB').resize((1024, 512)))
    fig, axs = plt.subplots(len(panels), 2, figsize=(14, 4*len(panels)), squeeze=False,
                            gridspec_kw={'width_ratios': [2, 1]})
    for axes, (label, pairs, ids) in zip(axs, panels):
        axes[0].imshow(background)
        for side, color in ((0, '#00ffff'), (1, '#ffb000')):
            axes[0].scatter(pairs[:, side, 0], pairs[:, side, 1], c=color, s=18)
            for i, p in enumerate(pairs[:, side]):
                axes[0].annotate('P'+str(ids[i][side]), p, color='white', fontsize=9)
        axes[0].set_title(label + ' | point pairs only; ring on right')
        axes[0].axis('off')
        try:
            xy = floor_points(pairs)
            closed = np.vstack([xy, xy[0]])
            axes[1].plot(closed[:, 0], closed[:, 1], '-o', markersize=4)
            valid_polygon(xy)
            axes[1].fill(closed[:, 0], closed[:, 1], alpha=.12, color='tab:blue', label='Annotation')
            for i, p in enumerate(xy):
                axes[1].annotate('P'+str(ids[i][0]), p)
            if reference_pairs is not None:
                reference = floor_points(reference_pairs)
                valid_polygon(reference)
                closed_reference = np.vstack([reference, reference[0]])
                axes[1].plot(closed_reference[:, 0], closed_reference[:, 1], color='tab:orange', label='Original GT: source ring')
                axes[1].fill(closed_reference[:, 0], closed_reference[:, 1], alpha=.1, color='tab:orange')
            axes[1].scatter([0], [0], marker='x', c='black', label='Camera')
            axes[1].set_aspect('equal', adjustable='datalim')
            axes[1].set_title('BEV of paired floor points; labels = upper IDs')
            axes[1].set_xlabel('Camera-height units (height = 1)')
            axes[1].grid(alpha=.2)
            axes[1].legend(fontsize=8)
        except ValueError as exc:
            axes[1].text(.05, .5, str(exc), transform=axes[1].transAxes)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def load_reference(ref, root, revised_cache):
    if not ref.get('source'):
        raise ValueError('reference_source_missing')
    source = root / ref['source']
    if source.suffix == '.txt':
        points = np.loadtxt(source)
    elif ref['source'] == 'export_label/groudTruth.json':
        if not revised_cache:
            from tools.thesis_main.analysis.materialize_model_gt_threshold_screen import _read_test_gt
            revised_cache.update(_read_test_gt(source))
        points = np.asarray(revised_cache[ref['image_id']], float)
    else:
        raise ValueError('unsupported_reference_source:' + ref['source'])
    expected = np.asarray(ref['raw_points'], float)
    if points.shape != expected.shape or not np.allclose(points, expected, atol=1e-8, rtol=0):
        raise ValueError('reference_raw_coordinate_mismatch')
    return points


def run(out: Path):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    comments, order = read_json(ROOT/COMMENTS), read_json(ROOT/ORDER)
    rows = read_json(ROOT/INPUTS/'annotations.jsonl.gz', lines=True)
    accepted = {r['canonical_annotation_id']: r for r in rows if r['accepted_before_new_review']}
    if len(accepted) != 3019:
        raise ValueError('current_inventory_drift')
    refs = read_json(ROOT/INPUTS/'references.json.gz')
    orders = {r['object_id']: r for r in order['records'] if r['object_type'] == 'canonical_annotation'}
    gt_orders = {r['image_id']: r for r in order['records'] if r['object_type'] == 'mp3d_gt_original'}
    by_comment = {}
    for case in comments['images']:
        for category, values in case.items():
            if not category.endswith('_records'):
                continue
            for value in values:
                cid = value['canonical_annotation_id']
                record = by_comment.setdefault(cid, dict(image_id=case['image_id'], code=case['code'], comments=[]))
                record['comments'].append(dict(category=category, **value))
    if len(by_comment) != 240 or not set(by_comment) <= set(accepted):
        raise ValueError('comment_identity_drift')
    raw_cache, verified, inventory = {}, {}, []
    for cid in sorted(set(by_comment) | set(orders) | set(SCREENSHOT_IDS)):
        row = accepted[cid]
        try:
            points, evidence = source_points(ROOT, row, raw_cache)
            verified[cid] = points
        except ValueError as exc:
            evidence = dict(status='unavailable', reason=str(exc))
        reason = candidate_reason(orders.get(cid))
        inventory.append(dict(canonical_annotation_id=cid, image_id=row['image_id'], worker_id=row['worker_id'],
                              from_comment_lookup=cid in by_comment,
                              comments=by_comment.get(cid, {}).get('comments', []),
                              order_evidence=orders.get(cid), order_basis=reason, source=evidence,
                              candidate=reason == 'preliminary_order_evidence' and cid in verified,
                              eligibility_reason=reason if cid in verified else evidence['reason']))
    selected = sorted((r for r in inventory if r['candidate']), key=lambda r: refs[r['image_id']]['code'])
    # 只用这批现有初审候选；不把未审作答认作“简单”以凑满8图。
    if len(selected) > 8:
        raise ValueError('existing_evidence_pool_changed_requires_panel_decision')
    results, revised_cache = [], {}
    for item in selected:
        cid, iid = item['canonical_annotation_id'], item['image_id']
        row, meta = accepted[cid], refs[iid]
        raw = verified[cid]
        links = np.asarray(row['links_zero_based'], int)
        expected_links = np.array([g['original_point_ids_1based'] for g in orders[cid]['current_ring_groups']])-1
        if not np.array_equal(links, expected_links) or sorted(links.ravel()) != list(range(len(raw))):
            raise ValueError('preliminary_order_point_identity_drift:' + cid)
        if not np.allclose(raw, row['effective_points_1024x512'], rtol=0, atol=1e-8):
            raise ValueError('selected_candidate_has_unverified_effective_revision:' + cid)
        variants = dict(raw=raw[links], shared_x=shared_x(raw, links)[links])
        case_comments = next((c for c in comments['images'] if c['image_id'] == iid), None)
        rec = dict(canonical_annotation_id=cid, image_id=iid, code=meta['code'], worker_id=row['worker_id'],
                   evidence_status='preliminary_order_evidence_pending_user_confirmation', source=item['source'],
                   comments_for_this_annotation=item['comments'], comments_for_image_context=case_comments,
                   point_ids_1based=(links+1).tolist(), variants={k: inspect_pairs(p) for k, p in variants.items()},
                   references=[], comparisons=[])
        reference_plot = None
        for ref in meta['references']:
            if ref['name'] not in ('gt_original', 'gt_revised'):
                continue
            record = dict(name=ref['name'], source=ref.get('source'),
                          order_evidence=gt_orders.get(iid) if str(ref.get('source')).endswith('.txt') else None)
            try:
                points = load_reference(dict(ref, image_id=iid), ROOT, revised_cache)
                if ref['pairing_basis'] != 'source_alternating_pairs':
                    record.update(status='raw_verified_pairing_unresolved', reason='revised_GT_pair_identity_not_confirmed', raw_points=points.tolist())
                    rec['references'].append(record)
                    for variant in variants:
                        rec['comparisons'].append(dict(view=variant, reference=ref['name'], status='unavailable', reason=record['reason']))
                    continue
                reference_pairs = points.reshape(-1, 2, 2)
                record.update(status='raw_verified', raw_points=points.tolist(),
                              bev_order_available=record['order_evidence'] is not None)
                if ref['name'] == 'gt_original' and record['order_evidence'] is not None:
                    reference_plot = reference_pairs
                for variant, pairs in variants.items():
                    rec['comparisons'].append(dict(view=variant, reference=ref['name'],
                                                   **pair_metrics(pairs, reference_pairs, record['order_evidence'] is not None)))
            except (ValueError, FileNotFoundError, KeyError) as exc:
                record.update(status='unavailable', reason=str(exc))
            rec['references'].append(record)
        image_path = ROOT / meta['image_path']
        figure = f"{meta['code']}_{row['worker_id']}.png"
        plot_panel(out/figure, image_path, meta['code'] + ' / ' + row['worker_id'] + ' | preliminary evidence',
                   [('Raw endpoints', variants['raw'], links+1), ('Shared-x endpoints', variants['shared_x'], links+1)],
                   reference_plot)
        rec['figure'] = figure
        results.append(rec)
    screenshot, screenshot_pairs = [], {}
    for cid in SCREENSHOT_IDS:
        row, raw = accepted[cid], verified[cid]
        links = np.asarray(row['links_zero_based'], int)
        if links.tolist() != [[0, 1], [4, 9], [3, 2], [6, 5], [8, 7], [10, 11]]:
            raise ValueError('screenshot_pair_identity_drift')
        views = dict(raw=raw[links], shared_x=shared_x(raw, links)[links])
        screenshot_pairs[cid] = views
        record = dict(canonical_annotation_id=cid, worker_id=row['worker_id'], image_id=row['image_id'],
                      status='user_specified_representation_comparison_not_quality_GT',
                      upper_raw_point_ids_user_order=[1, 5, 4, 9, 7, 11], pair_order_zero_based=USER_ORDER,
                      source=next(r['source'] for r in inventory if r['canonical_annotation_id'] == cid), views={})
        for name, pairs in views.items():
            record['views'][name] = dict(azimuth_order=inspect_pairs(pairs),
                                        user_order=inspect_pairs(pairs[USER_ORDER]),
                                        comparison=pair_metrics(pairs, pairs[USER_ORDER]))
        fig = 'e9zR4mvMWw7-19_' + row['worker_id'] + '_two_given_rings.png'
        plot_panel(out/fig, ROOT/refs[row['image_id']]['image_path'], 'e9zR4mvMWw7-19 / '+row['worker_id'],
                   [('Azimuth ring: upper IDs 1,5,4,7,9,11', views['raw'], links+1),
                    ('User-given ring: upper IDs 1,5,4,9,7,11', views['raw'][USER_ORDER], (links+1)[USER_ORDER])])
        record['figure'] = fig
        screenshot.append(record)
    left, right = SCREENSHOT_IDS
    cross_worker = dict(status='coordinate_preprocessing_sensitivity_not_worker_quality',
                        ids=list(SCREENSHOT_IDS),
                        raw_differing_endpoint_ids_1based=(np.flatnonzero(np.any(np.abs(verified[left]-verified[right]) > 1e-8, axis=1))+1).tolist(),
                        comparisons={})
    for view in ('raw', 'shared_x'):
        a, b = screenshot_pairs[left][view], screenshot_pairs[right][view]
        cross_worker['comparisons'][view] = dict(azimuth_order=pair_metrics(a, b),
                                                user_order=pair_metrics(a[USER_ORDER], b[USER_ORDER]))
    strata = Counter()
    for rec in results:
        context = rec['comments_for_image_context'] or {}
        has_detail, has_scope = bool(context.get('detail_omission_records')), bool(context.get('scope_difference_records'))
        strata['dual_scope_detail' if has_detail and has_scope else 'detail_image_context' if has_detail else
               'scope_image_context' if has_scope else 'context_only'] += 1
    strata = {key: strata[key] for key in ('simple_control', 'detail_image_context', 'scope_image_context', 'dual_scope_detail', 'context_only')}
    summary = dict(schema='layout_real_case_probe_20260926_v1', input_comment_images=95, input_comment_canonicals=240,
                   source_snapshot_used_as_index_only=True, current_inventory=3019,
                   selected_images=len(results), selected_annotations=len(results), formally_confirmed_orders=0,
                   coverage_note=f'{len(results)}幅既有初审候选；没有补入新判定的简单图。评论类别保留到具体作答，不将别人的评论转给候选。',
                   selected_image_context_strata=strata,
                   shortage_reason='当前明确连接证据仅覆盖少数作答，等待二次复核；不开展新排序筛查。',
                   comment_eligibility_counts=dict(Counter(r['eligibility_reason'] for r in inventory if r['from_comment_lookup'])),
                   source_verification_counts=dict(Counter(r['source']['status'] for r in inventory)),
                   no_raw_writeback=True, no_worker_ranking=True, no_new_exclusion=True,
                   pixel_convention_limit='BEV用LS连续坐标；旧ERP沿用像素中心约定。两表示差异不能全部归因于邻接。',
                   panel_inventory=inventory, selected_cases=results, screenshot_representation_probe=screenshot,
                   screenshot_cross_worker_probe=cross_worker)
    write_json(out/'real_case_probe.json', summary)
    return summary


if __name__ == '__main__':
    result = run(ROOT/'analysis_results/layout_algorithm_exploration_20260926/real')
    print(json.dumps({k: v for k, v in result.items() if k not in ('panel_inventory', 'selected_cases', 'screenshot_representation_probe', 'screenshot_cross_worker_probe')}, ensure_ascii=False))
