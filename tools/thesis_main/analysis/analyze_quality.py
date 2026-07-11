import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon

# Legacy-compatible CLI entrypoint; implementation helpers live in quality_core.
_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from tools.thesis_main.analysis.quality_core.active_time import load_active_logs, lookup_active_log_entry
from tools.thesis_main.analysis.quality_core.choice_parser import (
    _normalize_choice_values,
    _normalize_model_issue_values,
    _pick_primary_model_issue,
    _scope_is_oos,
    _split_choice_values,
    extract_data,
    parse_quality_flags_v2,
)
from tools.thesis_main.analysis.quality_core.consensus_reliability import _bootstrap_ci, compute_consistency
from tools.thesis_main.analysis.quality_core.geometry_metrics import (
    _pair_keypoints_to_layout,
    _poly_is_valid,
    compute_boundary_mse_rmse,
    compute_iou,
    compute_layout_standard_metrics,
    compute_pointwise_rmse_cyclic,
    compute_rmse,
)
from tools.thesis_main.analysis.quality_core.report_writer import _safe_float, _summarize_by_tag, write_quality_report


def _annotation_worker_id(annotation):
    completed_by = annotation.get('completed_by')
    if isinstance(completed_by, dict):
        return str(completed_by.get('id', 'unknown'))
    return str(completed_by) if completed_by is not None else 'unknown'


def _build_annotation_owner_map(tasks):
    owner_map = {}
    for task in tasks:
        project_id = str(task.get('project', ''))
        task_id = str(task.get('id'))
        for index, annotation in enumerate(task.get('annotations', []) or [], start=1):
            annotation_id = str(annotation.get('id') or f"annotation_index_{index}")
            owner = _annotation_worker_id(annotation)
            owner_map[(project_id, task_id, annotation_id)] = owner
            owner_map[(task_id, annotation_id)] = owner
            owner_map[annotation_id] = owner
    return owner_map


def main():
    parser = argparse.ArgumentParser(description="Analyze annotation quality and efficiency")
    parser.add_argument('export_json', help="Path to Label Studio export JSON file")
    parser.add_argument('--active-logs', help="Path to active_logs directory", default="active_logs")
    parser.add_argument(
        '--active-log-start',
        help="Inclusive server_received_at lower bound for active logs, e.g. 2026-05-06 or 2026-05-06T09:00:00",
    )
    parser.add_argument(
        '--active-log-end',
        help="Inclusive server_received_at upper bound for active logs, e.g. 2026-05-06 or 2026-05-06T18:00:00",
    )
    parser.add_argument('--output_dir', help="Directory to save output files", default="analysis_results")
    parser.add_argument('--metric', choices=['auto', 'manual', 'corner'], default='corner', 
                        help="Primary metric for 'iou' column (recommended: corner; auto: prefer manual if exists)")
    parser.add_argument('--no_smooth', action='store_true', help='Disable boundary curve smoothing for boundary RMSE')
    parser.add_argument('--pair_warn_min_coverage', type=float, default=0.8, help='Min pairing coverage before warning (0-1)')
    parser.add_argument('--boundary_method', choices=['auto', 'heuristic', 'connect'], default='auto',
                        help='Boundary curve generation method: connect uses HoHoNet-style pano_connect_points when possible')
    parser.add_argument('--no_pointwise', action='store_true', help='Disable pointwise RMSE (cyclic shift aligned)')
    parser.add_argument('--pointwise_min_coverage', type=float, default=0.9, help='Min pairing coverage to enable pointwise RMSE (0-1)')
    parser.add_argument('--ru_min_tasks', type=int, default=5, help='Min multi-annotator tasks required to report r_u for a user')
    parser.add_argument('--ru_bootstrap_iters', type=int, default=1000, help='Bootstrap iterations for r_u confidence interval')
    parser.add_argument('--ru_ci', type=float, default=0.95, help='CI level for r_u bootstrap (e.g., 0.95)')
    parser.add_argument('--ru_seed', type=int, default=0, help='Random seed for r_u bootstrap')
    parser.add_argument('--dataset_group', type=str, default="Unknown", 
                        help="Dataset role: Manual_Test, SemiAuto_Test, Calibration_manual, etc.")
    parser.add_argument('--project_version', type=str, default="v1.0", 
                        help="Version tag for the analysis run.")
    parser.add_argument('--analysis_role', type=str, default="performance",
                        help="Analysis role: performance or reliability (used for manifest categorization)")
    parser.add_argument('--output', type=str, help="Path to save the output CSV (overrides default naming)")
    parser.add_argument('--append', action='store_true', help="Append to the output file if it exists")
    parser.add_argument(
        '--quality_mode',
        choices=['v2'],
        default='v2',
        help='How to parse Label Studio choice fields (v2 only).',
    )
    args = parser.parse_args()

    # Create output directory if not exists
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
        print(f"Created directory: {args.output_dir}")

    date_str = datetime.now().strftime("%Y%m%d")
    output_csv = args.output if args.output else os.path.join(args.output_dir, f"quality_report_{date_str}.csv")

    try:
        with open(args.export_json, 'r', encoding='utf-8') as f:
            tasks = json.load(f)
        if isinstance(tasks, dict):
            tasks = [tasks]
    except Exception as e:
        print(f"Error processing JSON: {e}")
        return

    # 1. Load Active Logs
    print("Loading active logs...")
    active_times = load_active_logs(
        args.active_logs,
        start_time=args.active_log_start,
        end_time=args.active_log_end,
        annotation_owner_map=_build_annotation_owner_map(tasks),
    )
    if args.active_log_start or args.active_log_end:
        print(f"Active log time window: start={args.active_log_start or '(none)'} end={args.active_log_end or '(none)'}")
    
    # 2. Process Tasks
    rows = []
    consistency_stats = [] # Store consistency data
    # For reliability / consensus
    task_user_poly = defaultdict(dict)  # task_id -> user_id -> poly_points(list)
    # Task-level scope vote stats (handle mixed in-scope vs OOS)
    task_scope_counts = defaultdict(lambda: {"n_total": 0, "n_in_scope": 0, "n_oos": 0, "n_unknown": 0})
    
    print(f"Processing {args.export_json}...")
    
    try:
        for task in tasks:
            t_id = str(task.get('id'))
            # NEW: Extract title and image metadata for cross-project pairing
            t_data = task.get('data', {})
            t_title = str(t_data.get('title', ''))
            t_image = str(t_data.get('image', ''))
            
            # Get Prediction (Model)
            # Label Studio JSON can have 'predictions' (list of objects or IDs) 
            # or 'prediction' (single object)
            preds_list = task.get('predictions', [])
            pred_obj = None
            
            # 1. Try 'prediction' key first (often contains the full object)
            if task.get('prediction') and isinstance(task.get('prediction'), dict):
                pred_obj = task.get('prediction')
            # 2. If not, check the first element of 'predictions' list
            elif preds_list and isinstance(preds_list[0], dict):
                pred_obj = preds_list[0]
            # 3. If 'predictions' is a list of IDs, we might not have the full object 
            # unless it's also in the annotation (Label Studio sometimes does this)
            
            # Get Annotations (User)
            anns = task.get('annotations', [])
            if not anns:
                continue

            export_source_path = os.path.abspath(args.export_json)
            export_source_file = os.path.basename(export_source_path)
            export_project_id = str(task.get('project', ''))
            export_dataset_group = str(t_data.get('dataset_group', '')).strip()
            export_init_type = str(t_data.get('init_type', '')).strip()
            export_is_anchor = t_data.get('is_anchor', '')
            export_has_expert_ref = t_data.get('has_expert_ref', '')

            # Infer condition (manual vs semi) from presence of predictions
            task_has_prediction = False
            if task.get('prediction') and isinstance(task.get('prediction'), dict):
                task_has_prediction = True
            elif preds_list:
                task_has_prediction = True
            if not task_has_prediction:
                for ann in anns:
                    if ann.get('prediction') and isinstance(ann.get('prediction'), dict):
                        task_has_prediction = True
                        break
                    for r in ann.get('result', []) or []:
                        if str(r.get('origin', '')).lower() == 'prediction':
                            task_has_prediction = True
                            break
                    if task_has_prediction:
                        break
            condition = 'semi' if task_has_prediction else 'manual'
            runtime_condition_source = 'derived_from_prediction_presence'

            # --- Consistency Check (Inter-Annotator Agreement) ---
            if len(anns) > 1:
                avg_consistency, cons_details = compute_consistency(anns)
                consistency_stats.append({
                    'task_id': t_id,
                    'n_annotators': len(anns),
                    'iaa_t': avg_consistency,
                    'details': cons_details
                })

            for ann_index, ann in enumerate(anns, start=1):
                # If we still don't have a prediction object, check if it's inside the annotation
                current_pred_obj = pred_obj
                if not current_pred_obj and ann.get('prediction') and isinstance(ann.get('prediction'), dict):
                    current_pred_obj = ann.get('prediction')
                
                # Extract prediction data
                if current_pred_obj:
                    pred_corners, pred_poly, _pred_choice_map, _pred_quality = extract_data(current_pred_obj.get('result', []))
                else:
                    pred_corners, pred_poly, _pred_choice_map, _pred_quality = (np.array([]), [], {}, "")
                
                # Prepare prediction polygons
                # - manual: directly from prediction polygon region if present
                # - corner: convex-hull polygon derived from predicted corners
                pred_manual_poly = pred_poly or []
                pred_corner_poly = []
                if pred_corners is not None and len(pred_corners) > 2:
                    try:
                        pred_corner_poly = list(Polygon(pred_corners).convex_hull.exterior.coords)
                    except Exception:
                        pred_corner_poly = []

                # Try to get user info
                u_id = 'unknown'
                if 'completed_by' in ann:
                    if isinstance(ann['completed_by'], dict):
                        u_id = str(ann['completed_by'].get('id', 'unknown'))
                    else:
                        u_id = str(ann['completed_by'])
                annotation_id = str(ann.get('id') or f"annotation_index_{ann_index}")

                # Get active time from logs, fallback to lead_time
                active_log_entry, active_time_match_status = lookup_active_log_entry(
                    active_times,
                    export_project_id,
                    t_id,
                    u_id,
                    annotation_id=annotation_id,
                )
                active_time = 0
                active_time_source = 'missing'
                active_time_source_file = ''
                active_time_project_ids = ''
                active_time_session_count = 0
                active_time_event_count = 0
                active_time_page_gate_reasons = ''
                active_time_page_gate_sources = ''
                active_time_script_versions = ''
                active_time_page_gate_ineligible_event_count = 0
                lead_time_seconds = float(ann.get('lead_time', 0) or 0)
                if active_log_entry:
                    active_time = float(active_log_entry.get('active_time_value', 0.0))
                    active_time_source = 'log'
                    active_time_source_file = str(active_log_entry.get('active_time_source_file', ''))
                    active_time_project_ids = str(active_log_entry.get('active_time_project_ids', ''))
                    active_time_session_count = int(active_log_entry.get('active_time_session_count', 0))
                    active_time_event_count = int(active_log_entry.get('active_time_event_count', 0))
                    active_time_page_gate_reasons = str(active_log_entry.get('active_time_page_gate_reasons', ''))
                    active_time_page_gate_sources = str(active_log_entry.get('active_time_page_gate_sources', ''))
                    active_time_script_versions = str(active_log_entry.get('active_time_script_versions', ''))
                    active_time_page_gate_ineligible_event_count = int(active_log_entry.get('active_time_page_gate_ineligible_event_count', 0))
                elif lead_time_seconds > 0:
                    active_time = lead_time_seconds
                    active_time_source = 'lead_time_fallback'
                    if active_time_match_status == 'missing':
                        active_time_match_status = 'fallback_no_direct_log'
                    else:
                        active_time_match_status = f'fallback_{active_time_match_status}'
                
                ann_corners, ann_poly, ann_choice_map, quality = extract_data(ann.get('result', []))
                # Prefer deterministic v2 parsing from structured fields (scope/difficulty/model_issue).
                qflags = parse_quality_flags_v2(ann_choice_map, quality_all=quality, mode=str(args.quality_mode))

                # Track task-level scope votes.
                # NOTE: missing/unknown scope should not be silently counted as in-scope.
                task_scope_counts[t_id]["n_total"] += 1
                if bool(qflags.get('scope_missing')) or (qflags.get('is_oos') is None):
                    task_scope_counts[t_id]["n_unknown"] += 1
                elif qflags.get('is_oos') is True:
                    task_scope_counts[t_id]["n_oos"] += 1
                else:
                    task_scope_counts[t_id]["n_in_scope"] += 1

                # Prepare final_ann_poly (candidate geometry to be used for consensus/reliability)
                final_ann_poly = []
                if len(ann_corners) > 2:
                    try:
                        final_ann_poly = list(Polygon(ann_corners).convex_hull.exterior.coords)
                    except Exception:
                        final_ann_poly = []
                elif ann_poly:
                    final_ann_poly = ann_poly
                
                # --- Dual IoU Calculation ---
                # IMPORTANT: if IoU is not computable (missing pred/ann geometry), keep it as None.
                # Do not use 0.0 as a placeholder; that would be interpreted as "very low quality".
                
                # 1) Manual Polygon IoU (only meaningful if manual wall polygons are present)
                iou_manual = None
                if ann_poly and pred_manual_poly:
                    iou_manual = compute_iou(pred_manual_poly, ann_poly)
                
                # 2) Corner Polygon IoU (corner-derived layout polygon)
                iou_corner = None
                ann_corner_poly = []
                if len(ann_corners) > 2:
                    # Use Convex Hull for corners to ensure valid polygon
                    # [V2.0 Fix]: Initialize to 0.0 so that invalid predictions get penalized 
                    # instead of being excluded (Selection Bias).
                    iou_corner = 0.0 
                    try:
                        ann_corner_poly = list(Polygon(ann_corners).convex_hull.exterior.coords)
                        if pred_corner_poly:
                            iou_corner = compute_iou(pred_corner_poly, ann_corner_poly)
                    except:
                        # Fallback to 0.0 if calculation crashes
                        iou_corner = 0.0

                # Primary IoU based on selected metric mode
                if args.metric == 'manual':
                    iou_primary = iou_manual
                elif args.metric == 'corner':
                    iou_primary = iou_corner
                else:  # auto
                    iou_primary = iou_manual if (iou_manual is not None) else iou_corner
                
                rmse = compute_rmse(pred_corners, ann_corners)

                layout_iou2d = None
                layout_iou3d = None
                layout_depth_rmse = None
                layout_delta1 = None
                layout_used = False
                layout_gate_reason = "disabled"
                if bool(qflags.get('scope_missing')) or (qflags.get('is_oos') is None):
                    # Unknown scope: treat as not eligible for standard layout metrics.
                    layout_used = False
                    layout_gate_reason = "scope_missing"
                elif qflags.get('is_oos') is True:
                    # Out-of-scope cases violate the Manhattan/single-ceiling assumption;
                    # standard layout metrics are not meaningful as a quality signal.
                    layout_used = False
                    layout_gate_reason = "out_of_scope"
                else:
                    try:
                        layout_iou2d, layout_iou3d, layout_depth_rmse, layout_delta1, layout_used, layout_meta = compute_layout_standard_metrics(
                            pred_corners,
                            ann_corners,
                            width=1024,
                            height=512,
                            min_coverage=float(args.pointwise_min_coverage),
                        )
                        layout_gate_reason = str(layout_meta.get('gate_reason', ''))
                    except Exception:
                        layout_used = False
                        layout_gate_reason = "exception"

                pointwise_rmse = None
                pointwise_used = False
                pointwise_meta = {"best_shift": None, "gate_reason": "disabled"}
                if not args.no_pointwise:
                    pointwise_rmse, pointwise_used, pointwise_meta = compute_pointwise_rmse_cyclic(
                        pred_corners,
                        ann_corners,
                        width=1024,
                        min_coverage=float(args.pointwise_min_coverage),
                    )

                boundary_mse, boundary_rmse, boundary_meta = compute_boundary_mse_rmse(
                    pred_corners,
                    ann_corners,
                    width=1024,
                    height=512,
                    smooth=(not args.no_smooth),
                    min_coverage=float(args.pair_warn_min_coverage),
                    method=str(args.boundary_method),
                )

                # Limited warnings to keep console readable
                if boundary_meta.get('pairing_warning'):
                    # Print only for a few early cases
                    if len([r for r in rows if r.get('pairing_warning')]) < 10:
                        print(
                            f"[WARN][Pairing] task={t_id} user={u_id} "
                            f"pred_pts={boundary_meta.get('pred_n_points')} pred_pairs={boundary_meta.get('pred_n_pairs')} cov={boundary_meta.get('pred_pair_coverage'):.2f} "
                            f"ann_pts={boundary_meta.get('ann_n_points')} ann_pairs={boundary_meta.get('ann_n_pairs')} cov={boundary_meta.get('ann_pair_coverage'):.2f} "
                            f"reason={boundary_meta.get('pairing_failure_reason') or 'ok'}"
                        )
                
                # Store user geometry for consensus/reliability **after** computing layout gate.
                # Store user geometry for consensus/reliability.
                # Paper-facing consensus/reliability gate is intentionally separated from `layout_used`:
                # - `layout_used` is an engineering gate for HoHoNet-style layout metrics.
                # - reliability gate focuses on whether the annotation is in-scope and yields a valid polygon.
                # This avoids selection bias from prediction/depth/pairing failures while keeping the
                # consensus set geometrically valid.
                reliability_used = False
                reliability_gate_reason = ""
                try:
                    if bool(qflags.get('scope_missing')):
                        reliability_gate_reason = "scope_missing"
                    elif qflags.get('is_oos') is not False:
                        reliability_gate_reason = "oos_or_unknown"
                    elif not final_ann_poly:
                        reliability_gate_reason = "empty_poly"
                    elif not _poly_is_valid(final_ann_poly):
                        reliability_gate_reason = "invalid_poly"
                    else:
                        reliability_used = True
                        task_user_poly[t_id][u_id] = final_ann_poly
                except Exception:
                    pass
                scope_norm = _normalize_choice_values('scope', ann_choice_map.get('scope', [])) if isinstance(ann_choice_map, dict) else []
                diff_norm = _normalize_choice_values('difficulty', ann_choice_map.get('difficulty', [])) if isinstance(ann_choice_map, dict) else []
                model_norm = _normalize_model_issue_values(_normalize_choice_values('model_issue', ann_choice_map.get('model_issue', []))) if isinstance(ann_choice_map, dict) else []

                diff_norm_l = [str(x).strip().lower() for x in diff_norm if str(x).strip()]
                model_norm_l = [str(x).strip().lower() for x in model_norm if str(x).strip()]
                has_trivial = ('trivial' in set(diff_norm_l))
                has_acceptable = ('acceptable' in set(model_norm_l))

                difficulty_filled = bool(diff_norm_l)
                model_issue_filled = bool(model_norm_l)
                scope_filled = bool([str(x).strip() for x in scope_norm if str(x).strip()])

                difficulty_conflict = bool(has_trivial and len(diff_norm_l) > 1)
                model_issue_conflict = bool(has_acceptable and len(model_norm_l) > 1)

                # model_issue is only required for semi-auto conditions.
                condition_norm = str(condition or '').strip().lower()
                model_issue_required = ('semi' in condition_norm)
                model_issue_missing_required = bool(model_issue_required and (not model_issue_filled))

                rows.append({
                    'dataset_group': args.dataset_group,
                    'dataset_group_source': 'cli_argument',
                    'export_dataset_group': export_dataset_group,
                    'project_version': args.project_version,
                    'task_id': t_id,
                    'title': t_title,
                    'image_url': t_image,
                    'export_project_id': export_project_id,
                    'export_source_file': export_source_file,
                    'export_source_path': export_source_path,
                    'export_init_type': export_init_type,
                    'export_is_anchor': export_is_anchor,
                    'export_has_expert_ref': export_has_expert_ref,
                    'condition': condition,
                    'runtime_condition_source': runtime_condition_source,
                    'annotator_id': u_id,
                    'active_time': active_time,
                    'active_time_source': active_time_source,
                    'active_time_source_file': active_time_source_file,
                    'active_time_project_ids': active_time_project_ids,
                    'active_time_match_status': active_time_match_status,
                    'active_time_session_count': active_time_session_count,
                    'active_time_event_count': active_time_event_count,
                    'active_time_page_gate_reasons': active_time_page_gate_reasons,
                    'active_time_page_gate_sources': active_time_page_gate_sources,
                    'active_time_script_versions': active_time_script_versions,
                    'active_time_page_gate_ineligible_event_count': active_time_page_gate_ineligible_event_count,
                    'lead_time_seconds': lead_time_seconds,
                    'iou': iou_primary,          # For compatibility
                    'iou_manual': iou_manual,    # Explicit Manual IoU
                    'iou_corner': iou_corner,    # Explicit Corner IoU
                    'rmse_px': rmse,
                    # Standard layout metrics (HoHoNet/HorizonNet style)
                    'layout_2d_iou': layout_iou2d,
                    'layout_3d_iou': layout_iou3d,
                    'layout_depth_rmse': layout_depth_rmse,
                    'layout_delta1': layout_delta1,
                    'layout_used': bool(layout_used),
                    'layout_gate_reason': layout_gate_reason,
                    'reliability_used': bool(reliability_used),
                    'reliability_gate_reason': reliability_gate_reason,
                    'pointwise_rmse_px': pointwise_rmse,
                    'pointwise_rmse_used': bool(pointwise_used),
                    'pointwise_best_shift': pointwise_meta.get('best_shift', None),
                    'pointwise_gate_reason': pointwise_meta.get('gate_reason', ''),
                    'boundary_mse': boundary_mse,
                    'boundary_rmse_px': boundary_rmse,
                    'pred_n_points': boundary_meta.get('pred_n_points', 0),
                    'pred_n_pairs': boundary_meta.get('pred_n_pairs', 0),
                    'pred_pair_coverage': boundary_meta.get('pred_pair_coverage', 0.0),
                    'pred_odd_points': boundary_meta.get('pred_odd_points', False),
                    'ann_n_points': boundary_meta.get('ann_n_points', 0),
                    'ann_n_pairs': boundary_meta.get('ann_n_pairs', 0),
                    'ann_pair_coverage': boundary_meta.get('ann_pair_coverage', 0.0),
                    'ann_odd_points': boundary_meta.get('ann_odd_points', False),
                    'pairing_warning': boundary_meta.get('pairing_warning', False),
                    'pairing_failure_reason': boundary_meta.get('pairing_failure_reason', ''),
                    'boundary_method_used': boundary_meta.get('boundary_method_used', 'heuristic'),
                    # Filled later if task has multiple annotators
                    'consensus_uid': '',
                    'iou_to_consensus': None,
                    # Leave-one-out (exclude self from consensus)
                    'consensus_uid_loo': '',
                    'iou_to_consensus_loo': None,
                    # Direct agreement summary without choosing a representative
                    'iou_to_others_median': None,
                    'quality': quality,
                    'scope': ";".join(scope_norm),
                    'difficulty': ";".join(diff_norm),
                    # Store raw (possibly including 'acceptable') for auditing UI usage.
                    'model_issue': ";".join(model_norm),
                    'tool_issue': ";".join(_normalize_choice_values('tool_issue', ann_choice_map.get('tool_issue', []))) if isinstance(ann_choice_map, dict) else "",
                    # Meta-label hygiene for auditing (do NOT silently filter).
                    'scope_filled': bool(scope_filled),
                    'difficulty_filled': bool(difficulty_filled),
                    'difficulty_has_trivial': bool(has_trivial),
                    'difficulty_conflict': bool(difficulty_conflict),
                    'model_issue_required': bool(model_issue_required),
                    'model_issue_filled': bool(model_issue_filled),
                    'model_issue_has_acceptable': bool(has_acceptable),
                    'model_issue_conflict': bool(model_issue_conflict),
                    'model_issue_missing_required': bool(model_issue_missing_required),
                    # Derived, deterministic fields for multi-select model_issue.
                    'has_model_issue': bool([t for t in model_norm_l if t != 'acceptable']),
                    'model_issue_types': ";".join([t for t in model_norm_l if t != 'acceptable']),
                    'model_issue_primary': _pick_primary_model_issue([t for t in model_norm_l if t != 'acceptable']),
                    # Keep tri-state for scope-derived fields: True / False / empty (unknown).
                    'scope_missing': bool(qflags.get('scope_missing')),
                    'difficulty_missing': bool(qflags.get('difficulty_missing')),
                    'model_issue_missing': bool(qflags.get('model_issue_missing')),
                    'difficulty_conflict_v2': bool(qflags.get('difficulty_conflict')),
                    'model_issue_conflict_v2': bool(qflags.get('model_issue_conflict')),
                    'is_oos': qflags.get('is_oos'),
                    'is_occlusion': bool(qflags.get('is_occlusion')),
                    'is_fail': bool(qflags.get('is_fail')),
                    'is_residual': bool(qflags.get('is_residual')),
                    'is_normal': qflags.get('is_normal'),
                    'n_corners': len(ann_corners),
                    'has_manual_poly': bool(ann_poly)
                })
                
    except Exception as e:
        print(f"Error processing JSON: {e}")

    # 3. Write CSV
    write_quality_report(
        rows=rows,
        args=args,
        output_csv=output_csv,
        date_str=date_str,
        consistency_stats=consistency_stats,
        task_scope_counts=task_scope_counts,
        task_user_poly=task_user_poly,
    )

if __name__ == "__main__":
    main()
