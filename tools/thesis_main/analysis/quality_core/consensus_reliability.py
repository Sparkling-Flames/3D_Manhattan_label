"""Legacy consensus and reliability-input helpers for analyze_quality.

This module does not freeze formal C1/C2 worker statistics.
"""

import itertools

import numpy as np
from shapely.geometry import Polygon

from tools.thesis_main.analysis.quality_core.choice_parser import extract_data, parse_quality_flags_v2
from tools.thesis_main.analysis.quality_core.geometry_metrics import compute_iou


def _bootstrap_ci(values, stat_fn, n_iters: int = 1000, ci: float = 0.95, seed: int = 0):
    """Percentile bootstrap CI for a statistic.

    Returns (stat, ci_low, ci_high). If values is empty or all-NaN, returns (None, None, None).
    """
    vals = np.asarray(values, dtype=np.float32)
    vals = vals[~np.isnan(vals)]  # 过滤 NaN，避免统计函数返回 nan
    if vals.size == 0:
        return None, None, None

    stat = float(stat_fn(vals))
    if vals.size == 1:
        return stat, stat, stat

    n_iters = int(max(1, n_iters))
    ci = float(ci)
    ci = min(max(ci, 0.0), 1.0)
    alpha = 0.5 * (1.0 - ci)
    lo_q = 100.0 * alpha
    hi_q = 100.0 * (1.0 - alpha)

    rng = np.random.default_rng(int(seed))
    n = int(vals.size)
    boot = np.empty((n_iters,), dtype=np.float32)
    for i in range(n_iters):
        sample = rng.choice(vals, size=n, replace=True)
        boot[i] = float(stat_fn(sample))

    ci_low, ci_high = np.percentile(boot, [lo_q, hi_q]).astype(np.float32).tolist()
    return stat, float(ci_low), float(ci_high)


def compute_consistency(annotations, width=1024, height=512):
    """
    Compute pairwise IoU between multiple annotators for the same task.
    Returns: average_consistency_iou, details_list
    """
    if len(annotations) < 2:
        return 0.0, []
    
    # Extract polygons for all annotators
    # NOTE: For reliability/IAA we exclude OOS/unknown-scope annotations by default
    # because their boundaries are often definition-ambiguous, inflating disagreement.
    user_polys = []
    for ann in annotations:
        u_id = 'unknown'
        if 'completed_by' in ann:
            if isinstance(ann['completed_by'], dict):
                u_id = str(ann['completed_by'].get('id', 'unknown'))
            else:
                u_id = str(ann['completed_by'])
        
        corners, poly, choice_map, quality_all = extract_data(ann.get('result', []), width, height)
        qflags = parse_quality_flags_v2(choice_map, quality_all=quality_all, mode='v2')
        # Keep only explicit In-scope.
        if qflags.get('scope_missing') or (qflags.get('is_oos') is not False):
            continue

        # NOTE: Current annotation plan primarily uses Corner keypoints (no wall polygon).
        # For consistency/consensus we therefore default to corner-derived polygons.
        # If you later run a legacy export that contains manual wall polygons, those
        # are still preserved in separate columns (iou_manual) and can be opted into
        # via --metric manual.
        final_poly = []
        if corners is not None and len(corners) > 2:
            try:
                final_poly = list(Polygon(corners).convex_hull.exterior.coords)
            except Exception:
                final_poly = []
        elif poly:
            # Fallback only if corners are missing
            final_poly = poly

        if final_poly:
            user_polys.append({'uid': u_id, 'poly': final_poly})
    
    if len(user_polys) < 2:
        return 0.0, []
        
    # Calculate pairwise IoU
    ious = []
    details = []
    for p1, p2 in itertools.combinations(user_polys, 2):
        iou = compute_iou(p1['poly'], p2['poly'])
        ious.append(iou)
        details.append(f"{p1['uid']} vs {p2['uid']}: {iou:.4f}")
        
    return np.mean(ious), details


def apply_consensus_reliability_fields(rows, args, task_scope_counts, task_user_poly):
    # --- Task-level scope conflict handling ---
    # If a task has mixed votes (some in-scope, some OOS), it indicates the task goal/boundary
    # definition is not stable/reproducible across annotators. By default we:
    #   - keep per-row metrics in the CSV
    #   - but EXCLUDE such tasks from consensus/LOO/ru computations to avoid contaminating reliability
    mixed_scope_tasks = set()
    scope_unknown_tasks = set()
    scope_majority_by_task = {}
    for t_id, c in task_scope_counts.items():
        n_in = int(c.get('n_in_scope', 0))
        n_oos = int(c.get('n_oos', 0))
        n_unk = int(c.get('n_unknown', 0))
        if n_in > 0 and n_oos > 0:
            mixed_scope_tasks.add(t_id)
        if n_unk > 0:
            scope_unknown_tasks.add(t_id)
        # majority label (ties are labeled as 'tie')
        if n_unk > 0 and n_in == 0 and n_oos == 0:
            scope_majority_by_task[t_id] = 'unknown'
        elif n_in > n_oos:
            scope_majority_by_task[t_id] = 'in_scope'
        elif n_oos > n_in:
            scope_majority_by_task[t_id] = 'oos'
        else:
            scope_majority_by_task[t_id] = 'tie'

    # Attach task-level scope stats to each row
    for r in rows:
        t_id = str(r.get('task_id'))
        c = task_scope_counts.get(t_id, {"n_total": 0, "n_in_scope": 0, "n_oos": 0, "n_unknown": 0})
        n_total = int(c.get('n_total', 0))
        n_in = int(c.get('n_in_scope', 0))
        n_oos = int(c.get('n_oos', 0))
        n_unk = int(c.get('n_unknown', 0))
        r['task_scope_n_total'] = n_total
        r['task_scope_n_in_scope'] = n_in
        r['task_scope_n_oos'] = n_oos
        r['task_scope_n_unknown'] = n_unk
        r['task_scope_oos_rate'] = (float(n_oos) / float(n_total)) if n_total > 0 else 0.0
        r['task_scope_unknown_rate'] = (float(n_unk) / float(n_total)) if n_total > 0 else 0.0
        r['task_scope_majority'] = scope_majority_by_task.get(t_id, '')
        r['task_scope_is_mixed'] = bool(t_id in mixed_scope_tasks)
        r['task_scope_has_unknown'] = bool(t_id in scope_unknown_tasks)

    # --- Consensus + reliability (r_u) ---
    # Consensus per task: medoid annotation that maximizes median IoU to others.
    consensus_uid_by_task = {}
    iou_to_consensus_map = {}  # (task_id, user_id) -> iou

    # Leave-one-out consensus per (task, user): consensus built from other annotators only.
    consensus_uid_loo_map = {}       # (task_id, user_id) -> consensus_uid (from others)
    iou_to_consensus_loo_map = {}    # (task_id, user_id) -> iou(user, consensus_from_others)
    iou_to_others_median_map = {}    # (task_id, user_id) -> median IoU to all others

    for t_id, user_polys in task_user_poly.items():
        # Exclude tasks with mixed scope votes from consensus/reliability.
        if str(t_id) in mixed_scope_tasks:
            continue
        # Also exclude tasks with any unknown-scope votes.
        if str(t_id) in scope_unknown_tasks:
            continue
        # Paper-facing consensus requires >=3 annotators per task.
        uids = sorted([str(x) for x in user_polys.keys()])
        if len(uids) < 3:
            continue
        # pairwise IoU matrix
        iou_mat = np.zeros((len(uids), len(uids)), dtype=np.float32)
        for i in range(len(uids)):
            for j in range(i + 1, len(uids)):
                iou = compute_iou(user_polys[uids[i]], user_polys[uids[j]])
                iou_mat[i, j] = iou
                iou_mat[j, i] = iou
        # medoid by median agreement
        scores = []  # (median, mean, uid, idx)
        for i, uid in enumerate(uids):
            others = np.delete(iou_mat[i], i)
            med = float(np.median(others)) if others.size > 0 else 0.0
            mean = float(np.mean(others)) if others.size > 0 else 0.0
            scores.append((med, mean, uid, i))
        # Deterministic tie-break: median desc, mean desc, uid asc (str for determinism)
        best_idx = sorted(scores, key=lambda x: (-x[0], -x[1], str(x[2])))[0][3]
        consensus_uid = uids[best_idx]
        consensus_uid_by_task[t_id] = consensus_uid
        for i, uid in enumerate(uids):
            # iou to consensus (self gets 1.0)
            if uid == consensus_uid:
                iou_to_consensus_map[(t_id, uid)] = 1.0
            else:
                iou_to_consensus_map[(t_id, uid)] = float(iou_mat[i, best_idx])

        # --- Leave-one-out consensus per user ---
        # For each user k, build consensus from others only, using medoid among others.
        for k, uid_k in enumerate(uids):
            other_idx = [i for i in range(len(uids)) if i != k]
            if len(other_idx) == 0:
                continue

            # Median IoU from uid_k to others (no representative needed)
            iou_to_others = iou_mat[k, other_idx]
            iou_to_others_median_map[(t_id, uid_k)] = float(np.median(iou_to_others)) if iou_to_others.size > 0 else 0.0

            # Choose medoid among others by median agreement within the others set.
            other_scores = []  # (median, mean, uid, idx)
            for cand in other_idx:
                cand_others = [j for j in other_idx if j != cand]
                vals = iou_mat[cand, cand_others]
                med = float(np.median(vals)) if vals.size > 0 else 0.0
                mean = float(np.mean(vals)) if vals.size > 0 else 0.0
                other_scores.append((med, mean, uids[cand], cand))
            # Deterministic tie-break: median desc, mean desc, uid asc (str for determinism)
            c_idx = sorted(other_scores, key=lambda x: (-x[0], -x[1], str(x[2])))[0][3]
            consensus_uid_loo_map[(t_id, uid_k)] = uids[c_idx]
            iou_to_consensus_loo_map[(t_id, uid_k)] = float(iou_mat[k, c_idx])

    # Fill per-row consensus fields
    for r in rows:
        t_id = r.get('task_id')
        u_id = r.get('annotator_id')
        r['analysis_role'] = args.analysis_role
        
        if t_id in consensus_uid_by_task:
            r['consensus_uid'] = consensus_uid_by_task[t_id]
            r['iou_to_consensus'] = iou_to_consensus_map.get((t_id, u_id), None)
            r['consensus_uid_loo'] = consensus_uid_loo_map.get((t_id, u_id), '')
        
        if r.get('iou_to_consensus') is None:
            r['iou_to_consensus'] = iou_to_consensus_map.get((t_id, u_id), None)
        
        if (t_id, u_id) in iou_to_consensus_loo_map:
            r['iou_to_consensus_loo'] = iou_to_consensus_loo_map.get((t_id, u_id), None)
            r['iou_to_others_median'] = iou_to_others_median_map.get((t_id, u_id), None)
        else:
            # BUG-C01 Fix: If task excluded from consensus (mixed scope/unknown/n<3),
            # update reliability_used to False to maintain consistency.
            if r.get('reliability_used') is True:
                r['reliability_used'] = False
                if not r.get('reliability_gate_reason'):
                    r['reliability_gate_reason'] = 'excluded_from_consensus'

    return mixed_scope_tasks
