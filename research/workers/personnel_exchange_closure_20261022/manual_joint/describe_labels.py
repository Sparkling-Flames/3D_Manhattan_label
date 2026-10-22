"""Explain frozen fold classes using the actual available personnel pool."""
from __future__ import annotations
import pandas as pd
from register_design import HERE, ROOT, FEATURES, write, save, sha


def main():
    members = pd.read_csv(HERE / "ACTUAL_MEMBER_LABELS.csv.gz")
    centers = members.groupby(["pool_id", "image", "building", "fold_class"])[FEATURES].mean().reset_index()
    support = members.groupby(["pool_id", "fold_class"]).agg(
        actual_members=("worker_id", lambda values: "|".join(sorted(values))),
        available_n=("worker_id", "size")).reset_index()
    centers = centers.merge(support, on=["pool_id", "fold_class"])
    write(HERE / "AVAILABLE_CLASS_CENTERS_AND_MEMBERS.csv", centers)
    indexed = centers.set_index(["pool_id", "fold_class"])
    events = pd.read_csv(HERE / "EVENTS_REGISTERED.csv.gz", usecols=["pool_id", "source_class", "target_class", "training_QT_direction", "n", "m_AB"]).drop_duplicates()
    rows = []
    for event in events.itertuples():
        src = indexed.loc[(event.pool_id, event.source_class)]
        dst = indexed.loc[(event.pool_id, event.target_class)]
        rows.append(dict(pool_id=event.pool_id, source_class=event.source_class, target_class=event.target_class,
                         registered_direction=event.training_QT_direction, n=event.n, m=event.m_AB,
                         available_source_n=src.available_n, available_target_n=dst.available_n,
                         available_history_delta_Q=dst.q_history-src.q_history,
                         available_history_delta_logT=dst.t_history-src.t_history,
                         available_history_delta_complex_turn=dst.complex_turn_history-src.complex_turn_history,
                         available_source_members=src.actual_members, available_target_members=dst.actual_members))
    write(HERE / "ACTUAL_DIRECTION_HISTORY.csv", pd.DataFrame(rows))
    save(HERE / "HISTORY_STRATUM_DEFINITION.json", dict(
        name="available_pool_historically_faster",
        definition="target available class mean t_history < source available class mean t_history",
        purpose="Distinguish global fold-class center semantics from the actual available new-only personnel subset",
        target_endpoint_outcomes_used=False, primary_registered_directions_all_retained=True,
        changes_members_or_labels=False, history_table_sha256=sha(HERE / "ACTUAL_DIRECTION_HISTORY.csv")))
    # Preserve the prior ALL-data descriptive labels separately.  The m_*
    # archive columns are Manual histories, not a Manual+Semi joint classifier.
    archive = ROOT / "research/workers/personnel_effective_exchange_conditions_20261022/cross_condition_taxonomy"
    prior = pd.read_csv(archive / "OLD_METHOD_LABELS_ALL.csv")
    prior = prior[prior.method.eq("V3_JOINT_QT") & prior.condition.eq("manual") & prior.tier.eq("coarse")]
    history = pd.read_csv(archive / "CROSS_LABELS_ALL.csv").drop_duplicates("worker_id")
    cols = [c for c in history if c.startswith("m_")]
    history = history[["worker_id"] + cols].rename(columns={c: c[2:] for c in cols})
    all_labels = prior.merge(history, on="worker_id", how="left", validate="one_to_one")
    all_labels["used_for_new_target_evaluation"] = False
    write(HERE / "GLOBAL_DESCRIPTIVE_LABELS_AND_HISTORY.csv", all_labels)
    known = all_labels[all_labels.known]
    center = known.groupby("class_id")[FEATURES].mean().reset_index()
    members = known.groupby("class_id").agg(members=("worker_id", lambda s: "|".join(sorted(s))), n_members=("worker_id", "size"),
                                              n_new=("origin", lambda s: s.eq("new").sum())).reset_index()
    write(HERE / "GLOBAL_DESCRIPTIVE_CLASS_DEFINITIONS.csv", center.merge(members, on="class_id"))


if __name__ == "__main__":
    main()
