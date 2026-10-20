"""Shared derived outcomes; no scoring, fusion, labels or reference changes."""
import numpy as np
from analyze_discovery import KEY_METRICS, SUPPORT_METRICS

NEEDED = set(KEY_METRICS) | set(SUPPORT_METRICS) | {
    "event_id", "phase", "method_id", "domain", "context_id", "pool_id", "building", "image", "difficulty", "condition", "layer", "n", "m", "outgoing_class", "incoming_class",
    "n_band", "replacement_fraction", "A_team_key", "B_team_key", "C_team_key", "A_B8L2", "B_B8L2", "C_B8L2", "within_B8L2_change", "cross_B8L2_change",
    "within_bad_Q_gt5", "cross_bad_Q_gt5", "within_source_block_seconds", "cross_source_block_seconds", "within_target_block_seconds", "cross_target_block_seconds",
    "cross_over_within_source_block_time", "net_geometry_noQ_main", "reference_id", "history_Q_column",
    "out_history_Q", "within_history_Q", "cross_history_Q", "out_block_new_n", "within_block_new_n", "cross_block_new_n",
    "A_score_status", "B_score_status", "C_score_status", "A_geometry_reason", "B_geometry_reason", "C_geometry_reason",
    "outside_background_n", "background_policy", "matching", "within_node_count_change", "cross_node_count_change"}

def augment(df):
    df = df.copy()
    for arm in "ABC":
        df[arm + "_score_missing"] = df[arm + "_B8L2"].isna()
    for kind in ("within", "cross"):
        q = df[kind + "_B8L2_change"]
        df[kind + "_Q_drop_gt5"] = (q < -5).astype(float).where(q.notna())
        df[kind + "_absQ_gt5"] = df[kind + "_bad_Q_gt5"]
    df["net_Q_worsen_gt5"] = (df.net_B8L2_change < -5).astype(float).where(df.net_B8L2_change.notna())
    for kind in ("source", "target"):
        x, y = df["within_" + kind + "_block_seconds"], df["cross_" + kind + "_block_seconds"]
        ok = (x > 0) & (y > 0) & x.notna() & y.notna()
        df[kind + "_time_comparable"] = ok
        df[kind + "_block_log_ratio"] = np.log((y / x).where(ok))
    df["within_source_seconds_per_replaced_person"] = df.within_source_block_seconds / df.m
    df["cross_source_seconds_per_replaced_person"] = df.cross_source_block_seconds / df.m
    df["source_seconds_change_per_replaced_person"] = df.net_source_block_seconds / df.m
    save = df.cross_over_within_source_block_time <= .8
    df["source_save20"] = save.astype(float).where(df.source_time_comparable)
    good = df.B_complete & df.C_complete & df.net_B8L2_change.notna() & (df.net_B8L2_change >= -2)
    df["source_save20_Q_not_worse2"] = (save & good).astype(float).where(df.source_time_comparable)
    df["source_save20_Q_not_worse2_same_noQ_geometry"] = (save & good & df.net_geometry_noQ_main).astype(float).where(df.source_time_comparable)
    return df
