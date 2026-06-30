"""Legacy report helper functions for analyze_quality."""

import csv
import os
from collections import defaultdict

import numpy as np

from tools.thesis_main.analysis.quality_core.choice_parser import _split_choice_values
from tools.thesis_main.analysis.quality_core.consensus_reliability import (
    _bootstrap_ci,
    apply_consensus_reliability_fields,
)


def _safe_float(x):
    try:
        if x is None:
            return None
        if isinstance(x, bool):
            return float(x)
        s = str(x).strip()
        if s == "" or s.lower() in {"none", "nan"}:
            return None
        return float(s)
    except Exception:
        return None


def _mean(values: list):
    vals = [v for v in values if v is not None]
    return float(np.mean(vals)) if vals else None


def _summarize_by_tag(rows: list, tag_field: str, multi: bool, metrics: list, title: str, top_k: int = 20):
    """Print per-tag summary so UI options become interpretable outputs.

    This is intentionally console-only to keep the pipeline lightweight.
    """
    tag_to_rows = defaultdict(list)
    for r in rows:
        raw = r.get(tag_field, "")
        if multi:
            tags = _split_choice_values(raw)
        else:
            tags = _split_choice_values(raw)[:1] if raw else []
        if not tags:
            tag_to_rows["(empty)"].append(r)
            continue
        for t in tags:
            tag_to_rows[t].append(r)

    # Build sortable items
    items = []
    for tag, rs in tag_to_rows.items():
        item = {"tag": tag, "n": len(rs)}
        for m in metrics:
            item[m] = _mean([_safe_float(x.get(m)) for x in rs])
        items.append(item)

    items.sort(key=lambda d: (d["n"], (d.get(metrics[0]) is not None), (d.get(metrics[0]) or -1e9)), reverse=True)

    print(f"\n--- {title} ---")
    header = ["tag", "n"] + [f"mean_{m}" for m in metrics]
    print(" | ".join([f"{h:<22}" for h in header]))
    for it in items[: int(max(1, top_k))]:
        parts = [f"{it['tag'][:22]:<22}", f"{it['n']:<22d}"]
        for m in metrics:
            v = it.get(m)
            parts.append(f"{('' if v is None else f'{v:.4f}'):<22}")
        print(" | ".join(parts))


def write_quality_report(rows, args, output_csv, date_str, consistency_stats, task_scope_counts, task_user_poly):
    if rows:
        mixed_scope_tasks = apply_consensus_reliability_fields(
            rows=rows,
            args=args,
            task_scope_counts=task_scope_counts,
            task_user_poly=task_user_poly,
        )
        if not rows:
            print("No rows to save.")
            return

        file_exists = os.path.exists(output_csv)
        mode = 'a' if (args.append and file_exists) else 'w'
        
        # [Robust Append]: If appending, read existing header to ensure column alignment
        keys = list(rows[0].keys())
        if mode == 'a':
            try:
                with open(output_csv, 'r', encoding='utf-8') as f_read:
                    reader = csv.reader(f_read)
                    existing_header = next(reader, None)
                    if existing_header:
                        # Check compatibility
                        missing_curr = set(existing_header) - set(keys)
                        missing_prev = set(keys) - set(existing_header)
                        
                        if missing_prev:
                            print(f"⚠️ [Warning] New columns found in this run but missing in CSV: {missing_prev}")
                            print("   (These will be dropped to maintain schema consistency)")
                        
                        # Use existing header order
                        final_keys = existing_header
                    else:
                        print("⚠️ [Warning] CSV exists but empty/no-header. Switching to 'w' mode.")
                        mode = 'w'
                        final_keys = keys
            except Exception as e:
                print(f"⚠️ [Error] Failed to read existing CSV header: {e}. Aborting append.")
                return
        else:
            final_keys = keys
        
        with open(output_csv, mode, newline='', encoding='utf-8') as f:
            # extrasaction='ignore' ensures we don't crash if new script version has extra cols
            writer = csv.DictWriter(f, fieldnames=final_keys, extrasaction='ignore')
            if mode == 'w':
                writer.writeheader()
            writer.writerows(rows)
            
        print(f"Analysis saved to {output_csv} (Mode: {mode})")
        
        # Print Summary
        print(f"\n--- Summary (Mode: {args.metric}) ---")
        
        ious = [v for v in (_safe_float(r.get('iou')) for r in rows) if v is not None]
        ious_manual = [v for v in (_safe_float(r.get('iou_manual')) for r in rows) if v is not None]
        ious_corner = [v for v in (_safe_float(r.get('iou_corner')) for r in rows) if v is not None]
        
        if ious: print(f"Average Primary IoU:  {np.mean(ious):.4f}")
        if ious_manual: print(f"Average Manual IoU:   {np.mean(ious_manual):.4f} (Semantic)")
        if ious_corner: print(f"Average Corner IoU:   {np.mean(ious_corner):.4f} (Layout)")

        # Standard layout metrics summary
        layout_rows = [r for r in rows if r.get('layout_used')]
        if layout_rows:
            l2d = [float(r['layout_2d_iou']) for r in layout_rows if r.get('layout_2d_iou') is not None]
            l3d = [float(r['layout_3d_iou']) for r in layout_rows if r.get('layout_3d_iou') is not None]
            lrmse = [float(r['layout_depth_rmse']) for r in layout_rows if r.get('layout_depth_rmse') is not None]
            ld1 = [float(r['layout_delta1']) for r in layout_rows if r.get('layout_delta1') is not None]
            print(f"\n--- Standard Layout Metrics (HoHoNet-style, gated) ---")
            print(f"Layout usable rows: {len(layout_rows)}/{len(rows)}")
            if l2d: print(f"Layout 2D IoU:       {np.mean(l2d):.4f}")
            if l3d: print(f"Layout 3D IoU:       {np.mean(l3d):.4f}")
            if lrmse: print(f"Layout depth RMSE:   {np.mean(lrmse):.4f}")
            if ld1: print(f"Layout delta_1:      {np.mean(ld1):.4f}")

        # Quality tag stratification (minimal, reviewer-friendly)
        n_total = len(rows)
        n_scope_missing = len([r for r in rows if r.get('scope_missing')])
        n_diff_missing = len([r for r in rows if r.get('difficulty_missing')])
        n_diff_conflict = len([r for r in rows if r.get('difficulty_conflict')])
        n_model_missing_required = len([r for r in rows if r.get('model_issue_missing_required')])
        n_model_conflict = len([r for r in rows if r.get('model_issue_conflict')])
        n_oos = len([r for r in rows if r.get('is_oos') is True])
        n_normal = len([r for r in rows if r.get('is_normal') is True])
        n_fail = len([r for r in rows if r.get('is_fail')])
        n_occl = len([r for r in rows if r.get('is_occlusion')])
        n_resid = len([r for r in rows if r.get('is_residual')])
        print(f"\n--- Difficulty/Issue Tags (counts) ---")
        print(f"Total rows: {n_total}")
        print(
            f"ScopeMissing: {n_scope_missing} | DiffMissing: {n_diff_missing} | DiffConflict(trivial+others): {n_diff_conflict} | "
            f"ModelMissing(required, semi): {n_model_missing_required} | ModelConflict(acceptable+others): {n_model_conflict} | "
            f"Normal: {n_normal} | Out-of-scope: {n_oos} | PredFail: {n_fail} | Occlusion: {n_occl} | Residual: {n_resid}"
        )

        # Task-level scope disagreement (mixed in-scope vs OOS)
        # Useful to diagnose ambiguous task definitions or insufficient instruction.
        multi_annotator_task_ids = {str(c.get('task_id')) for c in consistency_stats} if consistency_stats else set()
        mixed_multi = [t for t in mixed_scope_tasks if t in multi_annotator_task_ids] if multi_annotator_task_ids else []
        if mixed_scope_tasks:
            print(f"\n--- Scope Disagreement (task-level) ---")
            print(f"Tasks with mixed scope votes: {len(mixed_scope_tasks)}")
            if multi_annotator_task_ids:
                print(f"Mixed among multi-annotator tasks: {len(mixed_multi)}/{len(multi_annotator_task_ids)}")
            # Show a few examples for quick triage
            show = list(sorted(mixed_scope_tasks))[:10]
            if show:
                print("Example mixed-scope task_ids:", ", ".join(show))

        # Data hygiene: OOS rows may still contain model_issue because the LS UI
        # requires the field for semi-auto tasks. Report it for transparency, but
        # do not treat model_issue as an OOS scoring/adjudication signal.
        oos_rows = [r for r in rows if r.get('is_oos') is True]
        if oos_rows:
            oos_with_model_issue = [r for r in oos_rows if str(r.get('model_issue') or '').strip()]
            rate = float(len(oos_with_model_issue)) / float(len(oos_rows))
            print(f"OOS rows: {len(oos_rows)} | OOS rows with model_issue filled: {len(oos_with_model_issue)} ({rate*100:.1f}%)")
            if rate > 0.3:
                print("[INFO] OOS rows include model_issue values. This is expected when the semi-auto UI requires model_issue; these values are not used for OOS scoring.")

        # If you want to 'exclude but report': show separate primary IoU means.
        non_oos_rows = [r for r in rows if (r.get('is_oos') is False) and (not r.get('scope_missing'))]
        if non_oos_rows and oos_rows:
            non_oos_iou = [v for v in (_safe_float(r.get('iou')) for r in non_oos_rows) if v is not None]
            oos_iou = [v for v in (_safe_float(r.get('iou')) for r in oos_rows) if v is not None]
            print(f"Primary IoU mean (non-OOS): {np.mean(non_oos_iou):.4f}")
            print(f"Primary IoU mean (OOS):     {np.mean(oos_iou):.4f}")

        # Make choice options actionable: print per-tag summaries.
        # Metrics chosen to match the study goals: efficiency + change magnitude + geometry robustness.
        tag_metrics = [
            'active_time',
            'iou',
            'boundary_rmse_px',
        ]
        _summarize_by_tag(rows, tag_field='scope', multi=False, metrics=tag_metrics, title='Scope Breakdown (UI choices used)')
        _summarize_by_tag(rows, tag_field='difficulty', multi=True, metrics=tag_metrics, title='Difficulty Breakdown (multi-select)')
        # Prefer issue-only tags (exclude 'acceptable') for readability.
        tag_field_issue = 'model_issue_types' if any(('model_issue_types' in r) for r in rows) else 'model_issue'
        _summarize_by_tag(rows, tag_field=tag_field_issue, multi=True, metrics=tag_metrics, title='Model Issue Breakdown (semi only)')
        
        # Annotator Stats
        by_user = defaultdict(list)
        for r in rows:
            by_user[r['annotator_id']].append(r)
            
        print("\n--- Per Annotator Stats ---")
        print(f"{'User':<10} | {'Tasks':<5} | {'Avg Time(s)':<12} | {'Avg IoU':<8} | {'Avg RMSE':<8}")
        for uid, u_rows in by_user.items():
            n_tasks = len(u_rows)
            avg_time = np.mean([float(x['active_time']) for x in u_rows])
            u_ious = [v for v in (_safe_float(x.get('iou')) for x in u_rows) if v is not None]
            avg_u_iou = float(np.mean(u_ious)) if u_ious else 0.0

            # Filter valid RMSEs
            u_rmses = [float(x['rmse_px']) for x in u_rows if x['rmse_px'] is not None]
            avg_u_rmse = np.mean(u_rmses) if u_rmses else 0

            print(f"{uid:<10} | {n_tasks:<5} | {avg_time:<12.2f} | {avg_u_iou:<8.4f} | {avg_u_rmse:<8.2f}")

        # --- Consistency Report ---
        if consistency_stats:
            print("\n--- Inter-Annotator Consistency (Expert Validation) ---")
            print(f"Found {len(consistency_stats)} tasks with multiple annotators.")
            print(f"{'Task ID':<10} | {'Annotators':<10} | {'IAA_t (median pairwise IoU)':<24}")
            for c in consistency_stats:
                v = c.get('iaa_t', None)
                if v is None:
                    v = c.get('avg_iou', None)
                v = float(v) if v is not None else float('nan')
                print(f"{c['task_id']:<10} | {c['n_annotators']:<10} | {v:.4f}")

        # --- Reliability (r_u) ---
        # r_u (leave-one-out) = median over tasks of IoU(annotator, consensus_from_others(task))
        ru_values = defaultdict(list)
        ru_values_3plus = defaultdict(list)  # n>=3 only (true consensus)
        ru_values_2 = defaultdict(list)      # n=2 only (pairwise)
        
        for r in rows:
            iou_c = r.get('iou_to_consensus_loo')
            if iou_c is None:
                continue
            try:
                n_annotators = int(r.get('task_scope_n_total', 0))
                ru_values[r['annotator_id']].append(float(iou_c))
                if n_annotators >= 3:
                    ru_values_3plus[r['annotator_id']].append(float(iou_c))
                elif n_annotators == 2:
                    ru_values_2[r['annotator_id']].append(float(iou_c))
            except Exception:
                continue

        if ru_values:
            min_tasks = int(max(1, args.ru_min_tasks))
            ci_level = float(args.ru_ci)
            iters = int(max(1, args.ru_bootstrap_iters))
            seed = int(args.ru_seed)

            # Count tasks by n_annotators for transparency
            n_tasks_total = len(set(r['task_id'] for r in rows if r.get('iou_to_consensus_loo') is not None))
            n_tasks_3plus = len(set(r['task_id'] for r in rows 
                                   if r.get('iou_to_consensus_loo') is not None 
                                   and int(r.get('task_scope_n_total', 0)) >= 3))
            n_tasks_2 = len(set(r['task_id'] for r in rows 
                               if r.get('iou_to_consensus_loo') is not None 
                               and int(r.get('task_scope_n_total', 0)) == 2))
            
            print("\n--- Annotator Reliability (r_u) from Multi-Annotator Tasks (Leave-One-Out) ---")
            print(f"Total tasks with LOO: {n_tasks_total} (n>=3: {n_tasks_3plus}, n=2: {n_tasks_2})")
            if n_tasks_2 > 0:
                pct_2 = 100.0 * n_tasks_2 / n_tasks_total if n_tasks_total > 0 else 0.0
                print(f"Warning: {n_tasks_2} tasks ({pct_2:.1f}%) have n=2 annotators.")
                print(f"   LOO reliability for n=2 degenerates to pairwise IoU (not true consensus).")
                print(f"   For paper-level rigor, consider reporting n>=3 subset separately.\n")
            
            print(
                f"{'User':<10} | {'n_tasks':<6} | {'r_u(median)':<11} | {'CI':<25} | {'mean IoU':<10}"
            )

            items = []
            for uid, vals in ru_values.items():
                if len(vals) < min_tasks:
                    continue
                if len(vals) < 5:
                    print(f"[WARN][r_u] user={uid} has only n_tasks={len(vals)}; CI may be unstable.")
                med, lo, hi = _bootstrap_ci(vals, stat_fn=lambda a: np.median(a), n_iters=iters, ci=ci_level, seed=seed)
                mean = float(np.mean(vals))
                items.append((uid, len(vals), float(med), float(lo), float(hi), mean))

            items.sort(key=lambda x: (x[2], x[1]), reverse=True)
            if not items:
                print(f"(No users meet ru_min_tasks={min_tasks}. Increase multi-annotator tasks or lower threshold.)")
            else:
                for uid, n, med, lo, hi, mean in items:
                    print(f"{uid:<10} | {n:<6d} | {med:<11.4f} | [{lo:.4f}, {hi:.4f}] (p{int(ci_level*100)}) | {mean:<10.4f}")

                # --- Stratified report: n>=3 vs n=2 ---
                if ru_values_3plus and ru_values_2:
                    print("\n--- Stratified LOO Reliability: n>=3 (true consensus) vs n=2 (pairwise) ---")
                    for uid in sorted(set(ru_values_3plus.keys()) | set(ru_values_2.keys())):
                        vals_3plus = ru_values_3plus.get(uid, [])
                        vals_2 = ru_values_2.get(uid, [])
                        r_3plus = f"{np.median(vals_3plus):.3f}" if vals_3plus else "N/A"
                        r_2 = f"{np.median(vals_2):.3f}" if vals_2 else "N/A"
                        print(f"{uid:<10} | n>=3: {len(vals_3plus):<3d} r_u={r_3plus:<6s} | n=2: {len(vals_2):<3d} r_u={r_2:<6s}")

                # Also save a per-user reliability report
                reliability_csv = os.path.join(args.output_dir, f"reliability_report_{date_str}.csv")
                with open(reliability_csv, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(
                        f,
                        fieldnames=[
                            'annotator_id',
                            'n_tasks',
                            'ru_median_iou',
                            'ru_ci_level',
                            'ru_ci_low',
                            'ru_ci_high',
                            'ru_mean_iou',
                            'bootstrap_iters',
                        ],
                    )
                    writer.writeheader()
                    for uid, n, med, lo, hi, mean in items:
                        writer.writerow(
                            {
                                'annotator_id': uid,
                                'n_tasks': int(n),
                                'ru_median_iou': float(med),
                                'ru_ci_level': float(ci_level),
                                'ru_ci_low': float(lo),
                                'ru_ci_high': float(hi),
                                'ru_mean_iou': float(mean),
                                'bootstrap_iters': int(iters),
                            }
                        )
                print(f"Reliability report saved to {reliability_csv}")

        # --- Outlier / Edge Case Report ---
        print("\n--- Edge Case Candidates (For Paper) ---")
        # 1. High Modification (Low IoU) - Potential "Hard Cases" or "Bad Predictions"
        # Only sort by IoU for rows where IoU is computable.
        rows_with_iou = [r for r in rows if _safe_float(r.get('iou')) is not None]
        sorted_by_iou = sorted(rows_with_iou, key=lambda x: float(_safe_float(x.get('iou'))))
        print("\n[Top 5 Most Modified Tasks (Lowest IoU)] -> Check for 'Major Corrections'")
        for r in sorted_by_iou[:5]:
            i = _safe_float(r.get('iou'))
            t = _safe_float(r.get('active_time'))
            i_str = "NA" if i is None else f"{float(i):.4f}"
            t_str = "NA" if t is None else f"{float(t):.1f}s"
            print(f"Task {r['task_id']} (User {r['annotator_id']}): IoU={i_str}, Time={t_str}")

        # 2. High RMSE (Geometric Deviation) - Potential "3D Deformity" candidates
        # Prefer boundary_rmse (robust to add/delete points); fallback to Hungarian rmse_px.
        valid_boundary = [r for r in rows if r.get('boundary_rmse_px') is not None]
        if valid_boundary:
            sorted_by_brmse = sorted(valid_boundary, key=lambda x: float(x['boundary_rmse_px']), reverse=True)
            print("\n[Top 5 High Geometric Error (Highest Boundary-RMSE)] -> Check for '3D Deformity'")
            for r in sorted_by_brmse[:5]:
                i = _safe_float(r.get('iou'))
                i_str = "NA" if i is None else f"{i:.4f}"
                print(
                    f"Task {r['task_id']} (User {r['annotator_id']}): BoundaryRMSE={float(r['boundary_rmse_px']):.2f}, IoU={i_str}"
                )
        else:
            valid_rmse = [r for r in rows if r['rmse_px'] is not None]
            sorted_by_rmse = sorted(valid_rmse, key=lambda x: float(x['rmse_px']), reverse=True)
            print("\n[Top 5 High Geometric Error (Highest RMSE)] -> Check for '3D Deformity'")
            for r in sorted_by_rmse[:5]:
                i = _safe_float(r.get('iou'))
                i_str = "NA" if i is None else f"{i:.4f}"
                print(f"Task {r['task_id']} (User {r['annotator_id']}): RMSE={r['rmse_px']:.2f}, IoU={i_str}")

        # 3. High Time but Low Change (Inefficient?)
        # Heuristic: Time > 75th percentile AND IoU > 0.9
        times = [float(r['active_time']) for r in rows if _safe_float(r.get('active_time')) is not None]
        if times:
            time_thresh = np.percentile(times, 75)
            inefficient = []
            for r in rows:
                t = _safe_float(r.get('active_time'))
                i = _safe_float(r.get('iou'))
                if t is None or i is None:
                    continue
                if t > time_thresh and i > 0.9:
                    inefficient.append(r)
            if inefficient:
                print("\n[High Effort, Low Change] -> Check for 'Hesitation' or 'Fine-tuning'")
                for r in inefficient[:5]:
                    t = _safe_float(r.get('active_time'))
                    i = _safe_float(r.get('iou'))
                    t_str = "NA" if t is None else f"{float(t):.1f}s"
                    i_str = "NA" if i is None else f"{float(i):.4f}"
                    print(f"Task {r['task_id']}: Time={t_str}, IoU={i_str}")
            
    else:
        print("No annotations found to process.")
