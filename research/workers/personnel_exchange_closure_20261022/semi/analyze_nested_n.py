"""Describe existing nested-n paths with fixed exchange blocks; no new endpoints."""
from register_semi_closure import *


def main():
    e=pd.read_csv(HERE/"EVENTS_COMPLETE.csv.gz",low_memory=False)
    e=e[e.analysis_layer.eq("source_partition_expansion")].copy()
    # Canonical source orientation keeps A/B identity consistent along n.
    e=e[e.outgoing_block_X<e.same_count_block_Y]
    keys=["pool_id","image","building","source_class","target_class","m_AB","outgoing_block_X","same_count_block_Y","changed_count_block_Z"]
    rows=[]
    for _,group in e.groupby(keys,dropna=False):
        ns=sorted(group.n.unique())
        for low_n,high_n in zip(ns,ns[1:]):
            if high_n-low_n>2:continue
            lo=group[group.n.eq(low_n)]
            hi=group[group.n.eq(high_n)]
            for a in lo.itertuples():
                D=set(a.common_background.split("|"))
                for b in hi.itertuples():
                    H=set(b.common_background.split("|"))
                    if not D<=H:continue
                    row={k:getattr(a,k) for k in keys}
                    row.update(low_n=int(low_n),high_n=int(high_n),low_event_id=a.event_id,high_event_id=b.event_id,
                               low_background=a.common_background,high_background=b.common_background,added_background_members=join(H-D),
                               low_minimum_support=a.C_minimum_support,high_minimum_support=b.C_minimum_support,
                               low_C_nodes=a.C_nodes,high_C_nodes=b.C_nodes,low_B_nodes=a.B_nodes,high_B_nodes=b.B_nodes,
                               low_C_failure=bool(a.C_failure),high_C_failure=bool(b.C_failure),
                               low_A_Q=a.A_B8L2,low_B_Q=a.B_B8L2,low_C_Q=a.C_B8L2,
                               high_A_Q=b.A_B8L2,high_B_Q=b.B_B8L2,high_C_Q=b.C_B8L2,
                               low_net_Q=a.C_minus_mean_source_B8L2,high_net_Q=b.C_minus_mean_source_B8L2,
                               low_C_supports=a.C_node_supports,high_C_supports=b.C_node_supports)
                    row["net_Q_change_along_n"]=row["high_net_Q"]-row["low_net_Q"]
                    row["direction_reversal_over1"]=row["low_net_Q"]*row["high_net_Q"]<0 and min(abs(row["low_net_Q"]),abs(row["high_net_Q"]))>=1
                    row["threshold_raised_with_changed_nodes"]=(row["high_minimum_support"]>row["low_minimum_support"] and
                                                               (row["high_C_nodes"]!=row["low_C_nodes"] or row["high_B_nodes"]!=row["low_B_nodes"]))
                    row["mechanism_status"]="nested fixed blocks; changed background and threshold jointly observed, attribution requires retained vote correspondence"
                    rows.append(row)
    pairs=pd.DataFrame(rows).drop_duplicates(["low_event_id","high_event_id"])
    write(HERE/"NESTED_N_RESPONSES.csv.gz",pairs)
    candidates=pairs[pairs.direction_reversal_over1 & pairs.threshold_raised_with_changed_nodes].copy()
    candidates["absolute_effect_change"]=candidates.net_Q_change_along_n.abs()
    write(HERE/"NESTED_N_MECHANISM_CANDIDATES.csv",candidates.sort_values("absolute_effect_change",ascending=False).head(20))
    summary=pairs.groupby(["image","building","m_AB","low_n","high_n"]).agg(
        nested_paths=("low_event_id","size"),low_mean_net_Q=("low_net_Q","mean"),high_mean_net_Q=("high_net_Q","mean"),
        mean_net_Q_change=("net_Q_change_along_n","mean"),reversals_over1=("direction_reversal_over1","sum"),
        threshold_raised_node_changes=("threshold_raised_with_changed_nodes","sum")).reset_index()
    write(HERE/"NESTED_N_RESPONSE_SUMMARY.csv",summary)
    print(json.dumps(dict(nested_paths=len(pairs),threshold_change_reversal_candidates=len(candidates))))
    print(candidates.sort_values("absolute_effect_change",ascending=False)[["image","m_AB","low_n","high_n","low_event_id","high_event_id","low_net_Q","high_net_Q","low_C_nodes","high_C_nodes","low_minimum_support","high_minimum_support"]].head(5).to_string(index=False))


if __name__=="__main__":
    main()
