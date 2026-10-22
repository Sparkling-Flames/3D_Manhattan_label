"""Exact inventory, class configurations, concrete blocks and background coverage."""
from __future__ import annotations
import math
import pandas as pd
from register_design import HERE, write, save


def main():
    events = pd.read_csv(HERE / "EVENTS_REGISTERED.csv.gz")
    capacity = pd.read_csv(HERE / "CAPACITY_ALL_N_M.csv.gz", dtype={"theoretical_ordered_ABC": str, "theoretical_unordered_source_ABC": str,
                                                                        "feasible_concrete_backgrounds": str, "uncovered_unordered_source_ABC": str})
    rows = []
    for cid, group in events.groupby("capacity_id"):
        cap = capacity[capacity.capacity_id.eq(cid)].iloc[0]
        source_blocks = set(group.outgoing_block_X) | set(group.same_count_block_Y)
        source_unions = {"|".join(sorted(set(a.split("|")) | set(b.split("|")))) for a, b in zip(group.outgoing_block_X, group.same_count_block_Y)}
        target_blocks = set(group.changed_count_block_Z)
        source_workers = set("|".join(source_blocks).split("|"))
        target_workers = set("|".join(target_blocks).split("|"))
        rows.append(dict(capacity_id=cid, pool_id=cap.pool_id, image=cap.image, building=cap.building,
                         source_class=cap.source_class, target_class=cap.target_class, direction=cap.training_QT_direction,
                         n=int(cap.n), m=int(cap.m), source_capacity=int(cap.source_capacity), target_capacity=int(cap.target_capacity),
                         feasible_source_blocks=str(math.comb(int(cap.source_capacity), int(cap.m))),
                         registered_source_blocks=len(source_blocks), feasible_source_unions=str(math.comb(int(cap.source_capacity), 2*int(cap.m))),
                         registered_source_unions=len(source_unions), feasible_target_blocks=str(math.comb(int(cap.target_capacity), int(cap.m))),
                         registered_target_blocks=len(target_blocks), registered_source_workers=len(source_workers),
                         registered_target_workers=len(target_workers), registered_backgrounds=group.background_id.nunique(),
                         registered_background_count_vectors=group.common_background.map(lambda s: s).nunique(),
                         feasible_concrete_backgrounds=cap.feasible_concrete_backgrounds,
                         registered_physical_ABC=len(group), theoretical_unordered_source_ABC=cap.theoretical_unordered_source_ABC,
                         full_source_block_coverage=len(source_blocks)==math.comb(int(cap.source_capacity), int(cap.m)),
                         full_target_block_coverage=len(target_blocks)==math.comb(int(cap.target_capacity), int(cap.m)),
                         source_workers="|".join(sorted(source_workers)), target_workers="|".join(sorted(target_workers))))
    table = pd.DataFrame(rows)
    # Replace concrete-background count above with the actual class-vector count.
    table = table.drop(columns="registered_background_count_vectors").merge(
        capacity[["capacity_id", "registered_background_class_configurations", "feasible_background_class_configurations"]],
        on="capacity_id", validate="one_to_one")
    write(HERE / "MEMBER_BLOCK_AND_BACKGROUND_COVERAGE.csv", table)
    save(HERE / "COVERAGE_SCOPE.json", dict(
        underlying_data_version="v2", candidate_n=[19,20,21], candidate_m_min=2,
        target_people="ordinary Manual; new-only formal personnel with known held-out-building V3 joint class and history",
        all_feasible_class_configurations_in_ledger=True,
        all_concrete_member_combinations_in_whole_pool=False,
        finite_source_reservoir_partitions_complete=True, finite_target_reservoir_subsets_complete=True,
        selected_backgrounds_outcome_free=True, selected_backgrounds_exhaustive=False,
        ordered_addition_process="only fixed-block nested n19/20/21 paths; identical member endpoints evaluated once",
        old_result_recomputation=False, new_registered_unique_ABC=events.event_id.nunique()))


if __name__ == "__main__":
    main()
