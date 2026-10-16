"""复用已审历史局部几何路由；先定参考，绝不读取质量分数或补造顶界。"""
from functools import lru_cache
import importlib.util
import json
from pathlib import Path

import numpy as np
from shapely.geometry import Point

from .difficulty_coarse_closeout_20261014 import floor

ROOT = Path(__file__).resolve().parents[3]
SOURCE = 'research/quality_pro_joint_archive_20261013/source/routing'
VERSION = 'current_reference_local_router_20261017_v1'


@lru_cache(maxsize=1)
def historical_router():
    path = ROOT/SOURCE
    spec = importlib.util.spec_from_file_location('audited_local_reference_router', path/'router.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, json.loads((path/'config.json').read_text(encoding='utf-8'))


def route_missing_space(points, spaces, allowed, prepared_cache):
    """只收原点和已准入底面；族约束先限定输入，精确双并列继续待定。"""
    evidence = dict(version=VERSION, source=SOURCE, quality_or_height_used_for_route=False,
                    route_is_quality_acceptance=False, true_intent_established=False)
    values = np.asarray(points, dtype=float)
    if (values.ndim != 2 or values.shape[1] != 2 or len(values) < 6 or len(values) % 2
            or not np.isfinite(values[1::2]).all()
            or not ((values[1::2, 1] > 256) & (values[1::2, 1] < 512)).all()):
        return '', dict(evidence, status='floor_unavailable', uncertainty='invalid_declared_bottom_points')
    router, config = historical_router()
    annotation = floor(values)
    try:
        polygon = router.strict_polygon(annotation)
    except ValueError as exc:
        return '', dict(evidence, status='floor_unavailable', uncertainty=str(exc))
    if not polygon.contains(Point(0, 0)):
        return '', dict(evidence, status='floor_unavailable', uncertainty='camera_not_inside_floor')
    candidates = [dict(candidate_id=s['target_id'], floor_xz_h=s['floor_xz_h'])
                  for s in spaces if s['target_id'] in allowed]
    if {c['candidate_id'] for c in candidates} != set(allowed) or len(candidates) < 2:
        raise ValueError('local_router_candidate_registry_mismatch')
    key = tuple((c['candidate_id'], tuple(tuple(p) for p in c['floor_xz_h'])) for c in candidates)
    if key not in prepared_cache:
        prepared_cache[key] = router.prepare_reference_set(candidates, config)
    route = router.route_floor(annotation, prepared_cache[key])
    chosen = route['candidate_id']
    metrics = route['candidate_floor_metrics']
    best = metrics[chosen]
    tied = [cid for cid in route['surviving_candidates'] if metrics[cid]['I'] == best['I']
            and metrics[cid]['boundary_mean_over_sqrt_ref_area'] == best['boundary_mean_over_sqrt_ref_area']]
    if len(tied) > 1:
        chosen = ''
        route.update(candidate_id=None, uncertainty='exact_iou_and_boundary_tie', tied_candidates=tied)
    return chosen, dict(evidence, **route, status='selected_provisional' if chosen else 'unresolved_exact_tie')
