"""Export the four registered B6 n20/m5 backgrounds, without cherry-picking them."""
from __future__ import annotations
import numpy as np
import pandas as pd
from register_design import HERE, write


def main():
    d = pd.read_csv(HERE / "EVENTS_COMPLETE.csv.gz", low_memory=False)
    d = d[d.pool_id.str.startswith("B6ByNegPMKs-47") & d.n.eq(20) & d.m_AB.eq(5) & d.training_QT_direction.eq("q_up__faster")]
    rows = []
    for team, g in d.groupby("team_C", sort=True):
        source = pd.concat([g[["team_A", "A_B8L2"]].rename(columns={"team_A": "team_key", "A_B8L2": "Q"}),
                            g[["team_B", "B_B8L2"]].rename(columns={"team_B": "team_key", "B_B8L2": "Q"})]).drop_duplicates("team_key")
        mean_source = source.Q.mean()
        distance = abs((g.A_B8L2 + g.B_B8L2) / 2 - mean_source)
        chosen = g.loc[distance.idxmin()].to_dict()
        row = {k: chosen[k] for k in ["pool_id", "image", "building", "event_id", "panel_id", "n", "m_AB", "source_class", "target_class",
            "team_A", "team_B", "team_C", "A_member_workers", "B_member_workers", "C_member_workers", "common_background",
            "outgoing_block_X", "same_count_block_Y", "changed_count_block_Z", "A_counts", "B_counts", "C_counts",
            "A_B8L2", "B_B8L2", "C_B8L2", "A_D10", "B_D10", "C_D10", "A_nodes", "B_nodes", "C_nodes",
            "A_source_time_total_seconds", "B_source_time_total_seconds", "C_source_time_total_seconds",
            "A_failure", "B_failure", "C_failure", "A_score_status", "B_score_status", "C_score_status",
            "same_B8L2", "cross_B8L2", "net_B8L2", "sym_B8L2", "sym_recorded_time_logratio"]}
        row.update(source_teams=len(source), source_Q_mean=mean_source, source_Q_min=source.Q.min(), source_Q_max=source.Q.max(),
                   all_source_partitions=len(g), source_pair_chosen_by="closest source-pair mean Q to full finite source endpoint mean; not maximum target gain")
        rows.append(row)
    result = pd.DataFrame(rows)
    assert len(result) == 4 and result.C_counts.nunique() == 1 and result.changed_count_block_Z.nunique() == 1
    write(HERE / "B6_FIXED_TARGET_FIVE_DIFFERENT_BACKGROUNDS.csv", result)


if __name__ == "__main__":
    main()
