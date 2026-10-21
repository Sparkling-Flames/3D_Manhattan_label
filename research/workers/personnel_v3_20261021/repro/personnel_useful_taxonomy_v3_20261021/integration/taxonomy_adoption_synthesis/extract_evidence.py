#!/usr/bin/env python3
"""Collect small, source-identifiable rows; never fuse, score, or re-fit a model.

Run from any cwd. Reads only finished summary CSV files. A separate receipt makes
the completion state explicit; missing later stages are not replaced with zero.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
V3 = HERE.parents[1]


def atomic(path: Path, data: bytes):
    tmp = path.with_name(path.name + '.partial')
    with tmp.open('wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


def write_csv(path, records):
    if not records:
        return
    columns = list(dict.fromkeys(k for r in records for k in r))
    f = io.StringIO(newline='')
    w = csv.DictWriter(f, fieldnames=columns)
    w.writeheader()
    w.writerows(records)
    atomic(path, ('\ufeff' + f.getvalue()).encode('utf-8'))


def clean(x):
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, list):
        return [clean(v) for v in x]
    if pd.isna(x):
        return None
    if hasattr(x, 'item'):
        return x.item()
    return x


rows, sources, unavailable = [], [], []


def take(rel, topic, selector, required=False):
    p = V3 / rel
    if not p.exists():
        unavailable.append({'path': rel, 'required_now': required})
        if required:
            raise FileNotFoundError(p)
        return
    raw = p.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    d = pd.read_csv(p, low_memory=False)
    selected = selector(d)
    sources.append(dict(path=rel, sha256=sha, source_rows=len(d), extracted_rows=len(selected), topic=topic))
    for i, r in selected.iterrows():
        obj = clean(r.to_dict())
        eid = hashlib.sha256((rel + '|' + str(i) + '|' + sha).encode()).hexdigest()[:16]
        rows.append(dict(evidence_id=eid, topic=topic, source_path=rel,
                         source_sha256=sha, source_row_index=int(i),
                         row_json=json.dumps(obj, ensure_ascii=False, separators=(',', ':'), allow_nan=False)))


take('taxonomy/OUTER_CLASS_ROLE_SUMMARY.csv', 'raw_role', lambda d:
     d[d['layer'].eq('ordinary') & d['tier'].eq('fine_label') & d['source'].isin(['all', 'old', 'new'])], True)
take('taxonomy/RAW_GEOMETRIC_SIMILARITY_SUMMARY.csv', 'raw_shape', lambda d:
     d[d.metric.eq('bound_deg')], True)
take('taxonomy/RAW_PREDICTION_INCREMENT.csv', 'raw_increment', lambda d:
     d[d.outcome.isin(['B8L2_peer_delta', 'log_time_peer_delta', 'near_straight_nodes_5deg_peer_delta'])], True)
take('taxonomy/OUTER_STABILITY_SUMMARY.csv', 'partition_stability', lambda d: d, True)
take('taxonomy/CLASS_DEFINITIONS.csv', 'full_data_class_meanings', lambda d: d, True)
take('taxonomy/SEMI_REDUNDANCY_SUPPORT.csv', 'semi_redundancy_member_opportunities', lambda d: d, True)

policies = ['QT_interaction__balanced', 'class_coarse_interaction__balanced',
            'class_fine_interaction__balanced', 'class_fine_interaction__quality',
            'exact_continuous_interaction__balanced',
            'exact_continuous_interaction_class_fine__balanced',
            'history_Q', 'history_T', 'source__balanced']
outcomes = ['delta_B8L2', 'delta_D10', 'failure_delta_pp', 'time_percent_vs_uniform',
            'time_seconds_delta', 'failure_or_loss_gt5_delta_pp']
for condition in ['SEMI', 'MANUAL']:
    take(f'utility/{condition}_UTILITY_CHECKPOINT.csv', 'actual_selection', lambda d:
         d[d.regime.eq('cross_panel_LOBO') & d.policy.isin(policies) &
           d.slice_kind.isin(['all', 'joint_time_support']) & d.outcome.isin(outcomes)])
    take(f'utility/{condition}_UTILITY_CHECKPOINT_PAIRED.csv', 'paired_actual_selection', lambda d:
         d[d.regime.eq('cross_panel_LOBO') &
           d.new_policy.isin(['class_fine_interaction__balanced',
                             'exact_continuous_interaction_class_fine__balanced']) &
           d.slice_kind.isin(['all', 'joint_time_support'])])

response_models = ['source', 'new_coarse', 'new_fine', 'new_coarse_quadratic', 'new_fine_quadratic',
                   'old_coarse', 'old_fine', 'joint_coarse', 'joint_fine',
                   'joint_coarse_quadratic', 'joint_fine_quadratic',
                   'QT', 'QT_quadratic', 'QT_new_fine', 'QT_structure',
                   'behavior_same_fields_moments', 'behavior_same_fields_quadratic',
                   'joint_same_fields_moments', 'joint_same_fields_quadratic']
response_outcomes = ['B8L2', 'D10', 'log_source_time', 'failure', 'fusion_turn_n',
                     'fusion_redundancy_n', 'ref_node_recall_9', 'ref_edge_recall_9']
for condition in ['semi', 'manual']:
    for domain in ['geometry_common', 'qt_common']:
        take(f'response/{condition}/{domain}/PREDICTION_SUMMARY.csv', 'heldout_response', lambda d:
             d[d.stratum.eq('all') & d.model.isin(response_models) & d.outcome.isin(response_outcomes)])
        take(f'response/{condition}/{domain}/DECOMPOSITION_SUMMARY.csv', 'finite_configuration_variance', lambda d:
             d[d.outcome.isin(response_outcomes)])

direction_metrics = ['cross_B8L2', 'cross_D10', 'cross_IoU3D100', 'cross_ref_node_recall_5',
                     'cross_ref_edge_recall_5', 'cross_fusion_turn_n',
                     'cross_fusion_redundancy_n', 'cross_failure_difference',
                     'cross_loss_gt10', 'abs_Q_change_advantage', 'stable_advantage']
def direction(d):
    return d[d.view.eq('overall') & d.method_id.isin(['V3_BEHAVIOR', 'V3_JOINT_QT']) &
             d.source_domain.eq('all_formal') & d.history_direction.eq('increase') &
             d.history_axis.isin(['turn_history', 'redundancy_history']) & d.metric.isin(direction_metrics)]
main_direction = 'composition/direction/PANEL_DIRECTED_CORE_SUMMARY.csv'
take(main_direction if (V3/main_direction).exists() else
     'composition/direction/PANEL_SEMI_CHECKPOINT_DIRECTED_CORE_SUMMARY.csv',
     'directed_class_changes_A_to_C', direction)

take('utility/F01_EXTREME_CONFIGURATION_SUMMARY.csv', 'F01_complete_configurations', lambda d:
     d[d.outcome.isin(['high_fast_minus_low_fast_B8L2', 'high_fast_minus_low_fast_D10',
                       'relative_time_percent_high_vs_low', 'failure_delta_pp',
                       'high_fast_minus_low_fast_ref_node_recall_9',
                       'high_fast_minus_low_fast_ref_edge_recall_9'])])

# Final stage additions: exact registered actual-event domains are not pooled.
strict_metrics=['common_quality_within_abs','common_quality_cross_abs','abs_Q_change_advantage',
                'stable_advantage','same_loss_gt10','cross_loss_gt10','B_failure','C_failure',
                'within_floor_jaccard_difference','cross_floor_jaccard_difference']
take('composition/matched/PANEL_OVERALL_CHECKPOINT.csv','main_strict_matched',lambda d:
     d[d.summary_view.eq('overall') & d.sensitivity.eq('unmatched_total_effect') & d.metric.isin(strict_metrics)],True)
take('composition/matched/STRICT_MATCHED_OVERVIEW.csv','large_and_pure_strict_matched',lambda d:
     d[d.summary_view.eq('overall') & d.sensitivity.eq('unmatched_total_effect') & d.metric.isin(strict_metrics)],True)
take('composition/direction/PURE_DIRECTED_CORE_SUMMARY.csv','pure_directed_structure',lambda d:
     d[d.method_id.isin(['V3_BEHAVIOR','M_structure','SP_scale','A2_relation']) &
       d.history_axis.eq('turn_history') & d.view.isin(['overall','target_difficulty','m_band_and_seats']) &
       d.metric.isin(direction_metrics+['cross_extension','cross_fusion_short_turn_edges','cross_recorded_time_pct'])],True)
take('utility/F01_POLICY_CHECKPOINT.csv','F01_actual_selection',lambda d:
     d[d.slice_kind.isin(['all','difficulty']) & d.outcome.isin(outcomes)],True)

write_csv(HERE/'EVIDENCE_ROWS.csv', rows)
write_csv(HERE/'SOURCE_SUMMARIES.csv', sources)
receipt = dict(version='final_completed_raw_manual_semi_selection_response_main_large_pure_F01',
               created_utc=datetime.now(timezone.utc).isoformat(),
               sources=len(sources), extracted_rows=len(rows),
               missing_later_stage_files=unavailable,
               native_calls=0, scoring_calls=0, models_refit=0,
               purpose='Adoption synthesis of separately preserved experiments; not an extra experiment.')
atomic(HERE/'EVIDENCE_RECEIPT.json', (json.dumps(receipt, ensure_ascii=False, indent=2)+'\n').encode())
print(json.dumps({k: v for k, v in receipt.items() if k != 'missing_later_stage_files'}, ensure_ascii=False))
