"""独立探索：固定真人区域，分开审计GT修订与环序表示；不写回原始数据。"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy import sparse
from scipy.sparse.linalg import lsqr
from shapely import contains_xy
from shapely.geometry import Polygon, Point
from shapely.ops import polygonize, unary_union

from . import reviewed_manual_20260921 as reviewed
from .shared_x_reanalysis_20260922 import shared_x, verify_raw, save
from .materialize_model_gt_threshold_screen import _read_test_gt
from .geometry_consensus.representation import normalize_geometry
from .quality_core.geometry_metrics import _interp_periodic

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/supervisor_independent_20260922'
MANUAL_GT = ROOT / 'export_label/groudTruth.json'


def is_substantive_revision(a, b):
    """沿用既有GT审计的1px实质修订门；一对一匹配只识别点集变化，不改环序。"""
    if a.shape != b.shape:
        return True
    dx = (a[:, None, 0] - b[None, :, 0] + 512) % 1024 - 512
    d = np.hypot(dx, a[:, None, 1] - b[None, :, 1])
    i, j = linear_sum_assignment(d)
    return bool(d[i, j].max() > 1.)


def footprint(pairs):
    p = np.asarray(pairs, float)
    if p.ndim != 3 or p.shape[1:] != (2, 2) or len(p) < 3 or not np.isfinite(p).all():
        return None, 'invalid_pairs'
    if np.any((p[:, :, 1] < 0) | (p[:, :, 1] >= 512)):
        return None, 'vertical_out_of_bounds'
    if np.any(p[:, 1, 1] <= 255.5):
        return None, 'floor_not_below_horizon'
    u = ((p[:, 1, 0] + .5) / 1024 - .5) * 2 * np.pi
    v = ((p[:, 1, 1] + .5) / 512 - .5) * np.pi
    r = 1 / np.tan(v)  # 相机离地高度单位化；不对齐、不旋转、不逐份缩放。
    poly = Polygon(np.column_stack([r * np.sin(u), -r * np.cos(u)]))
    if not poly.is_valid or poly.area < 1e-10:
        return None, 'invalid_source_ring'
    if not poly.covers(Point(0, 0)):
        return None, 'camera_outside'
    return poly, ''


def consecutive_pairs(points, average_x=False):
    p = np.asarray(points, float).copy()
    if len(p) % 2:
        raise ValueError('odd GT point count')
    pairs = p.reshape(-1, 2, 2)
    swaps = pairs[:, 0, 1] > pairs[:, 1, 1]
    pairs[swaps] = pairs[swaps, ::-1, :]
    if average_x:
        p = shared_x(pairs.reshape(-1, 2), np.arange(len(p)).reshape(-1, 2))
        pairs = p.reshape(-1, 2, 2)
    return pairs


def load_references():
    manual = _read_test_gt(MANUAL_GT)
    refs, audit = {}, []
    for split in ['test', 'valid']:
        for path in sorted((ROOT / f'data/mp3d_layout/{split}/label_cor').glob('*.txt')):
            iid = path.stem
            raw = np.loadtxt(path)
            changed = iid in manual and is_substantive_revision(raw, manual[iid])
            current = manual[iid] if changed else raw
            versions = {}
            row = dict(image_id=iid, split=split, changed=changed,
                       original_pairs=len(raw)//2, revised_pairs=len(current)//2,
                       original_source=str(path.relative_to(ROOT)),
                       revised_source='export_label/groudTruth.json' if changed else str(path.relative_to(ROOT)))
            for name, points in [('original', raw), ('revised', current)]:
                # 源序投影是可计算性审计，不断言LS存储顺序等于人工预期连接。
                raw_pairs = consecutive_pairs(points)
                gap = float(np.abs((raw_pairs[:, 0, 0]-raw_pairs[:, 1, 0]+512)%1024-512).max())
                pairs = consecutive_pairs(points, average_x=changed and name == 'revised')
                poly, reason = footprint(pairs)
                if gap >= 51.2:
                    poly, reason = None, 'consecutive_pairing_unresolved'
                versions[name + '_ring'] = poly
                row[name + '_ring_reason'] = reason
                row[name + '_max_pair_dx'] = gap
                normalized = normalize_geometry(points)
                if normalized['valid']:
                    q = np.array([[[x['x'] % 1024, x['y_ceiling']],
                                   [x['x'] % 1024, x['y_floor']]] for x in normalized['pairs']])
                    angular, why = footprint(q)
                else:
                    angular, why = None, normalized['reason']
                versions[name + '_angular'] = angular
                row[name + '_angular_reason'] = why
                row[name + '_ring_angular_iou'] = (poly.intersection(angular).area / poly.union(angular).area
                                                  if poly is not None and angular is not None else None)
            refs[iid] = versions
            audit.append(row)
    return refs, pd.DataFrame(audit)


def region_mesh(polygons):
    tiles = list(polygonize(unary_union([p.boundary for p in polygons])))
    xy = np.array([[p.representative_point().x, p.representative_point().y] for p in tiles])
    votes = np.array([contains_xy(p, xy[:, 0], xy[:, 1]) for p in polygons])
    keep = votes.any(axis=0)
    tiles = [p for p, use in zip(tiles, keep) if use]
    a = np.array([p.area for p in tiles])
    c = np.array([[p.centroid.x, p.centroid.y] for p in tiles])
    return dict(tiles=tiles, votes=votes[:, keep], area=a, moment=a[:, None]*c)


def region_score(mesh, selected, gt, intersections=None):
    if intersections is None:
        intersections = np.array([p.intersection(gt).area for p in mesh['tiles']])
    area = mesh['area'][selected].sum()
    inter = intersections[selected].sum()
    distance = (np.linalg.norm(mesh['moment'][selected].sum(axis=0)/area -
                              [gt.centroid.x, gt.centroid.y]) / np.sqrt(gt.area)) if area else np.nan
    return dict(iou=float(inter / (gt.area+area-inter)), centroid_norm=float(distance))


def error_components(mesh, gt):
    """精确有限人群恒等式：平均区域平方误差=共用偏差+分歧；不作人/图方差分量解释。"""
    p = mesh['votes'].mean(axis=0)
    overlap = np.array([t.intersection(gt).area for t in mesh['tiles']])
    bias = (np.dot(mesh['area'], p*p)-2*np.dot(p, overlap)+gt.area)/gt.area
    variance = np.dot(mesh['area'], p*(1-p))/gt.area
    return dict(shared_bias=float(bias), disagreement=float(variance))


def worker_effects(frame):
    wi, workers = pd.factorize(frame.worker, sort=True)
    ii, images = pd.factorize(frame.image_id, sort=True)
    n = len(frame)
    x = sparse.csr_matrix((np.ones(2*n), (np.tile(np.arange(n), 2),
                          np.r_[ii, len(images)+wi])), shape=(n, len(images)+len(workers)))
    beta = lsqr(x, 1-frame.iou.to_numpy(), atol=1e-12, btol=1e-12)[0][len(images):]
    beta -= beta.mean()
    return pd.DataFrame(dict(worker=workers, adjusted_loss=beta)).merge(
        frame.groupby('worker').agg(n=('iou', 'size'), buildings=('building', 'nunique'),
                                   raw_mean_iou=('iou', 'mean')).reset_index())


def load_annotation_inputs():
    history = reviewed.old.pipeline.rows_at(reviewed.old.HIST / 'responses.jsonl.gz')
    registry = reviewed.old.read(reviewed.REGISTRY)
    new, _ = reviewed.old.intake(history, registry, reviewed.SOURCES)
    rows, _, records, _ = reviewed.prepare(history, new, registry)
    base = [r for r in rows if r['calculation_included'] and r['worker_id'] not in {'W019', 'W026'}
            and r['raw_condition'] in {'manual', 'oos'}]
    usable = [r for r in base if not r['imputed_point'] and r['canonical_annotation_id'] in records
              and records[r['canonical_annotation_id']]['links'] is not None]
    return rows, base, usable, records, registry


def main(repeats):
    OUT.mkdir(parents=True, exist_ok=True)
    rows, base, usable, records, registry = load_annotation_inputs()
    verified = verify_raw(rows, {r['canonical_annotation_id'] for r in usable})
    save(OUT/'source_verification.json', verified)
    review = reviewed.old.read('analysis_results/cluster_screen_reviewed_20260922/逐项接收.json')
    known_wrong = {cid for r in review if r['case'] == 14 for cid in r['ids']}
    refs, gt_audit = load_references()
    image_ids = {r['image_id'] for r in base}
    gt_audit['in_descriptive_pool'] = gt_audit.image_id.isin(image_ids)
    save(OUT/'gt_source_audit.csv', gt_audit)
    changed = set(gt_audit.loc[gt_audit.changed, 'image_id'])
    meta = {i['image_id']: i for i in registry['images']}
    groups, screening = defaultdict(list), []
    for row in usable:
        cid = row['canonical_annotation_id']
        rec = records[cid]
        pairs = shared_x(rec['p'], rec['links'])[rec['links']]
        polygon, reason = footprint(pairs)
        why = 'existing_explicit_wrong' if cid in known_wrong else reason
        screening.append(dict(id=cid, image_id=row['image_id'], worker=row['worker_id'], reason=why,
                              pairing_source=rec['audit'].get('pairing_source')))
        if not why:
            groups[row['image_id']].append((row, polygon))
    save(OUT/'response_screen.csv', pd.DataFrame(screening))
    individual, curves, decomposition = [], [], []
    rng = np.random.default_rng(20260922)
    for number, (iid, pairs) in enumerate(sorted(groups.items())):
        pairs.sort(key=lambda item: item[0]['canonical_annotation_id'])
        rr, polygons = zip(*pairs)
        n = len(rr)
        assert n == len({r['worker_id'] for r in rr})
        mesh = region_mesh(polygons)
        a, v = mesh['area'], mesh['votes']
        np.testing.assert_allclose(v@a, [p.area for p in polygons], atol=1e-8)
        context = dict(image_id=iid, code=f"{meta[iid]['building']}-{meta[iid]['number']:02d}",
                       building=rr[0]['building_id'], changed=iid in changed, N=n)
        intersect = (v*a)@v.T
        areas = v@a
        affinity = intersect/(areas[:, None]+areas[None, :]-intersect)
        available = {name: gt for name, gt in refs[iid].items() if gt is not None}
        overlaps = {name: np.array([t.intersection(gt).area for t in mesh['tiles']])
                    for name, gt in available.items()}
        for version, gt in available.items():
            for j, row in enumerate(rr):
                q = region_score(mesh, v[j], gt, overlaps[version])
                individual.append(dict(**context, version=version, worker=row['worker_id'],
                                       id=row['canonical_annotation_id'], **q))
            terms = error_components(mesh, gt)
            direct = np.mean([p.symmetric_difference(gt).area/gt.area for p in polygons])
            assert abs(terms['shared_bias']+terms['disagreement']-direct) < 1e-8
            decomposition.append(dict(**context, version=version, **terms))
        if n < 3:
            continue
        orders = [rng.permutation(n) for _ in range(repeats)]
        for k in sorted(set([1, 3, 5, 7, 9, 11, 12, 16, n])):
            if k > n:
                continue
            subsets = [np.array([j]) for j in range(n)] if k == 1 else ([np.arange(n)] if k == n else [o[:k] for o in orders])
            values = defaultdict(list)
            for ss in subsets:
                # 两种平票规则显式并列；不根据GT选择规则。
                votes = v[ss].sum(axis=0)
                selections = {'vote_ge_half': 2*votes >= k, 'vote_gt_half': 2*votes > k,
                              'medoid': v[ss[np.argmax(affinity[np.ix_(ss, ss)].sum(axis=1))]]}
                for method, selected in selections.items():
                    for version, gt in available.items():
                        values[method, version].append(region_score(mesh, selected, gt, overlaps[version])['iou'])
            for (method, version), q in values.items():
                curves.append(dict(**context, k=k, method=method, version=version, draws=len(q),
                                   mean_iou=float(np.mean(q)), q10=float(np.quantile(q, .1)),
                                   q90=float(np.quantile(q, .9))))
        if number % 40 == 0:
            print(f'computed {number+1}/{len(groups)} images', flush=True)
    quality = pd.DataFrame(individual)
    curve = pd.DataFrame(curves)
    save(OUT/'individual_quality.csv', quality)
    save(OUT/'consensus_curves.csv', curve)
    save(OUT/'error_decomposition.csv', pd.DataFrame(decomposition))
    panels, effects = [], []
    for representation in ['ring', 'angular']:
        old, current = 'original_'+representation, 'revised_'+representation
        common = set(quality[quality.version == old].id) & set(quality[quality.version == current].id)
        fixed = quality[quality.id.isin(common)]
        for version in [old, current]:
            fx = worker_effects(fixed[fixed.version == version])
            fx['version'] = version
            effects.append(fx)
        for label, images in [('all', image_ids), ('changed_only', changed)]:
            for kmax in [12, 16]:
                z = curve[(curve.N >= kmax) & (curve.k <= kmax) & curve.image_id.isin(images)]
                panel = set(z[z.version == old].image_id) & set(z[z.version == current].image_id)
                z = z[z.image_id.isin(panel) & z.version.isin([old, current])]
                g = z.groupby(['version', 'method', 'k']).agg(
                    mean_iou=('mean_iou', 'mean'), images=('image_id', 'nunique'),
                    buildings=('building', 'nunique')).reset_index()
                g['panel'], g['kmax'] = label, kmax
                panels.append(g)
    save(OUT/'fixed_panel_summary.csv', pd.concat(panels, ignore_index=True))
    save(OUT/'worker_effects.csv', pd.concat(effects, ignore_index=True))
    save(OUT/'SUMMARY.json', dict(descriptive_responses=len(base), descriptive_images=len(image_ids),
        source_verified=len(verified), bound_independent=len(usable), floor_screened=sum(map(len, groups.values())),
        floor_images=len(groups), screen_reasons=Counter(x['reason'] for x in screening if x['reason']),
        changed_gt_images=int(gt_audit.changed.sum()), changed_in_descriptive=len(changed & image_ids),
        revised_ring_invalid_in_descriptive=int((gt_audit.changed & gt_audit.in_descriptive_pool &
                                                (gt_audit.revised_ring_reason != '')).sum()),
        repeats=repeats, references='MP3D label_cor test/valid; manual revisions only in groudTruth.json; no no_occ/HoHoNet/P1 override',
        output_contract='README.md', status='exploratory_reference_and_representation_sensitivity'))


def wall_mask(pairs, width=256, height=128):
    """二维墙带操作定义：周期线性上下包络，不使用地面环序；不是完整遮挡拓扑。"""
    p = np.asarray(pairs, float)
    if p.ndim != 3 or p.shape[1:] != (2, 2) or len(p) < 3:
        raise ValueError('insufficient_pairs')
    x = p[:, 0, 0] % 1024
    if len(np.unique(np.round(x, 6))) != len(x):
        raise ValueError('duplicate_longitude_envelope_unresolved')
    top = np.rint(_interp_periodic(x*width/1024, p[:, 0, 1]*height/512, width))
    bottom = np.rint(_interp_periodic(x*width/1024, p[:, 1, 1]*height/512, width))
    if np.any(top >= bottom):
        raise ValueError('inverted_envelope')
    y = np.arange(height)[:, None]
    return (y >= top) & (y <= bottom)


def mask_iou(a, b):
    return float(np.count_nonzero(a & b)/np.count_nonzero(a | b))


def mask_centroid(mask):
    """水平周期质心和集中程度。集中程度趋近0时角度无稳定解释。"""
    height, width = mask.shape
    area = mask.sum()
    z = np.dot(mask.sum(axis=0), np.exp(2j*np.pi*np.arange(width)/width))/area
    y = float(np.dot(mask.sum(axis=1), np.arange(height)/height)/area)
    return dict(angle=float(np.angle(z)), concentration=float(abs(z)), y=y)


def wall_analysis(repeats):
    OUT.mkdir(parents=True, exist_ok=True)
    rows, base, usable, records, registry = load_annotation_inputs()
    verify_raw(rows, {r['canonical_annotation_id'] for r in usable})
    gt_audit = pd.read_csv(OUT/'gt_source_audit.csv')
    changed = set(gt_audit.loc[gt_audit.changed, 'image_id'])
    manual = _read_test_gt(MANUAL_GT)
    review = reviewed.old.read('analysis_results/cluster_screen_reviewed_20260922/逐项接收.json')
    wrong = {cid for r in review if r['case'] == 14 for cid in r['ids']}
    groups = defaultdict(list)
    excluded, quality, curves, resolution = [], [], [], []
    for row in usable:
        cid = row['canonical_annotation_id']
        if cid in wrong:
            continue
        rec = records[cid]
        p = shared_x(rec['p'], rec['links'])[rec['links']]
        try:
            groups[row['image_id']].append((row, p, wall_mask(p, 512, 256)))
        except ValueError as exc:
            excluded.append(dict(id=cid, reason=str(exc)))
    rng = np.random.default_rng(20260922)
    for number, (iid, values) in enumerate(sorted(groups.items())):
        values.sort(key=lambda z:z[0]['canonical_annotation_id'])
        rr, pp, masks = zip(*values)
        masks = np.array(masks)
        context = dict(image_id=iid, building=rr[0]['building_id'], N=len(rr), changed=iid in changed)
        src = gt_audit[gt_audit.image_id == iid].iloc[0].original_source
        raw = np.loadtxt(ROOT/src)
        gm = {}
        for version, points in [('original', raw), ('revised', manual[iid] if iid in changed else raw)]:
            if version == 'revised' and iid in changed:
                normalized = normalize_geometry(points)
                if not normalized['valid']:
                    excluded.append(dict(id=iid, version=version, reason=normalized['reason']))
                    continue
                p = np.array([[[z['x'] % 1024, z['y_ceiling']], [z['x'] % 1024, z['y_floor']]]
                              for z in normalized['pairs']])
            else:
                p = consecutive_pairs(points, average_x=True)
            try:
                gm[version] = wall_mask(p, 512, 256)
                gt_hi = wall_mask(p, 1024, 512)
            except ValueError as exc:
                excluded.append(dict(id=iid, version=version, reason=str(exc)))
                continue
            gc = mask_centroid(gm[version])
            for row, p, m in values:
                centroid = mask_centroid(m)
                dx = abs((centroid['angle']-gc['angle']+np.pi)%(2*np.pi)-np.pi)/(2*np.pi)
                quality.append(dict(**context, version=version, id=row['canonical_annotation_id'],
                    worker=row['worker_id'], iou=mask_iou(m, gm[version]),
                    centroid_dx_cycles=dx if min(centroid['concentration'], gc['concentration']) > 1e-8 else None,
                    centroid_dy=centroid['y']-gc['y'], concentration=centroid['concentration'],
                    gt_concentration=gc['concentration']))
                resolution.append(dict(id=row['canonical_annotation_id'], version=version,
                    iou_512=mask_iou(m, gm[version]), iou_1024=mask_iou(wall_mask(p, 1024, 512), gt_hi)))
        n = len(rr)
        orders = [rng.permutation(n) for _ in range(repeats)]
        # 只比较等权区域投票；不先分类、调权或取最大簇。
        for k in [1, 3, 5, 7, 9, 11, 12, 16]:
            if k > n:
                continue
            subsets = [np.array([j]) for j in range(n)] if k == 1 else [o[:k] for o in orders]
            scores = defaultdict(list)
            for ss in subsets:
                aggregate = 2*masks[ss].sum(axis=0) >= k
                for version, reference in gm.items():
                    scores[version].append(mask_iou(aggregate, reference))
            for version, q in scores.items():
                curves.append(dict(**context, version=version, k=k, mean_iou=float(np.mean(q)),
                                   q10=float(np.quantile(q, .1)), q90=float(np.quantile(q, .9))))
        if number % 60 == 0:
            print(f'2D wall mask {number+1}/{len(groups)}', flush=True)
    save(OUT/'wall_individual.csv', pd.DataFrame(quality))
    save(OUT/'wall_curves.csv', pd.DataFrame(curves))
    save(OUT/'wall_resolution.csv', pd.DataFrame(resolution))
    save(OUT/'wall_unresolved.json', excluded)


def summarize():
    """从本轮结果生成汇总；模型诊断仍直接读取已冻结的本地预测TXT。"""
    w = pd.read_csv(OUT/'wall_individual.csv')
    c = pd.read_csv(OUT/'wall_curves.csv')
    audit = pd.read_csv(OUT/'gt_source_audit.csv')
    resolution = pd.read_csv(OUT/'wall_resolution.csv')
    effects = []
    for version, group in w.groupby('version'):
        z = worker_effects(group)
        z['version'] = version
        effects.append(z)
    e = pd.concat(effects)
    save(OUT/'wall_worker_effects.csv', e)
    z = e.pivot(index='worker', columns='version', values='adjusted_loss')
    ranks = z.rank()
    wide = w.pivot(index=['id', 'image_id', 'changed'], columns='version', values='iou').dropna().reset_index()
    wide['delta'] = wide.revised-wide.original
    panel = c.query('N>=12 and k in [1,12]').pivot(index=['image_id', 'building', 'version', 'changed'],
                                                 columns='k', values='mean_iou').dropna().reset_index()
    panel['gain'] = panel[12]-panel[1]
    summary = dict(wall_rows=int((w.version == 'original').sum()), wall_images=int(w.image_id.nunique()),
        wall_gt_delta_all=wide.delta.mean(), wall_gt_delta_changed=wide[wide.changed].delta.mean(),
        wall_changed_rows=int(wide.changed.sum()), wall_changed_images=int(wide[wide.changed].image_id.nunique()),
        worker_rank_spearman=float(z.corr(method='spearman').iloc[0, 1]),
        worker_max_rank_move=float(abs(ranks.original-ranks.revised).max()),
        resolution_mean_abs_delta=float(abs(resolution.iou_512-resolution.iou_1024).mean()),
        resolution_max_abs_delta=float(abs(resolution.iou_512-resolution.iou_1024).max()))
    for name, frame in [('wall_panel', panel), ('changed_panel', panel[panel.changed])]:
        summary[name] = frame.groupby('version').agg(images=('image_id', 'nunique'),
            buildings=('building', 'nunique'), one=(1, 'mean'), twelve=(12, 'mean'), gain=('gain', 'mean'),
            improved=('gain', lambda x: sum(x > 0))).reset_index().to_dict('records')
    manual = _read_test_gt(MANUAL_GT)
    models, failures = [], []
    for iid in sorted(set(w.image_id)):
        row = audit[audit.image_id == iid].iloc[0]
        directory = ('output/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34' if row.split == 'test'
                     else 'analysis_results/c2b_validation_static_20260802_v16/validation_prediction_txt')
        source = ROOT/directory/(iid+'.txt')
        model = np.loadtxt(source)
        try:
            mm = wall_mask(consecutive_pairs(model, True), 512, 256)
        except ValueError as exc:
            failures.append(dict(image_id=iid, source=str(source.relative_to(ROOT)), reason=str(exc)))
            continue
        raw = np.loadtxt(ROOT/row.original_source)
        for version, points in [('original', raw), ('revised', manual[iid] if row.changed else raw)]:
            if row.changed and version == 'revised':
                norm = normalize_geometry(points)
                if not norm['valid']:
                    raise ValueError(f'GT schema changed: {iid}: {norm["reason"]}')
                pairs = np.array([[[a['x'] % 1024, a['y_ceiling']], [a['x'] % 1024, a['y_floor']]] for a in norm['pairs']])
            else:
                pairs = consecutive_pairs(points, True)
            models.append(dict(image_id=iid, version=version, model_source=str(source.relative_to(ROOT)),
                model_corners=len(model)//2, model_wall_iou=mask_iou(mm, wall_mask(pairs, 512, 256))))
    m = pd.DataFrame(models)
    save(OUT/'model_difficulty_diagnostic.csv', m)
    save(OUT/'model_unresolved.json', failures)
    joint = c.query('N>=12 and k==12').merge(m, on=['image_id', 'version'])
    joint['corner_group'] = np.where(joint.model_corners <= 4, 'four_or_less', 'more_than_four')
    summary['model_corner_groups'] = joint.groupby(['version', 'corner_group']).agg(
        images=('image_id', 'nunique'), human_q12=('mean_iou', 'mean'), model_iou=('model_wall_iou', 'mean')).reset_index().to_dict('records')
    summary['model_human_spearman'] = {v: group.mean_iou.corr(group.model_wall_iou, method='spearman')
                                     for v, group in joint.groupby('version')}
    save(OUT/'readouts.json', summary)
    for filename, fields in [('individual_quality.csv', ['iou', 'centroid_norm']),
                             ('consensus_curves.csv', ['mean_iou']), ('wall_individual.csv', ['iou']),
                             ('wall_curves.csv', ['mean_iou'])]:
        frame = pd.read_csv(OUT/filename)
        assert np.isfinite(frame[fields]).all().all(), filename
        assert frame[fields[0]].between(-1e-10, 1+1e-10).all(), filename
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repeats', type=int, default=64)
    parser.add_argument('--wall-only', action='store_true')
    parser.add_argument('--summarize', action='store_true')
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('--repeats must be positive')
    if args.summarize:
        summarize()
    elif args.wall_only:
        wall_analysis(args.repeats)
    else:
        main(args.repeats)
