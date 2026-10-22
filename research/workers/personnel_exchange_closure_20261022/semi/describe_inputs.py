"""Describe inherited class roles and precise registered coverage, no outcomes."""
from register_semi_closure import *


def main():
    all_labels=pd.read_csv(V3/"taxonomy/ALL_METHOD_LABELS_LOBO.csv.gz")
    all_labels=all_labels[all_labels.method.eq("V3_JOINT_QT")&all_labels.condition.eq("semi")]
    write(HERE/"INHERITED_LABELS_LOBO_WITH_UNKNOWN.csv.gz",all_labels)
    labels=pd.read_csv(HERE/"INHERITED_LABELS_LOBO.csv.gz")
    events=pd.read_csv(HERE/"EVENTS_REGISTERED_ALL.csv.gz")
    domains=pd.read_csv(HERE/"DOMAIN_INVENTORY.csv")
    capacity=pd.read_csv(HERE/"CAPACITY_ALL_ATTEMPTS.csv")
    configs=pd.read_csv(HERE/"ALL_CLASS_CONFIGURATIONS.csv")
    roles=[]
    for building,group in events.groupby("building"):
        for lab in sorted(set(group.source_class)|set(group.target_class)):
            z=labels[(labels.heldout_building==building)&(labels.coarse_label==lab)]
            uses={side:set("|".join(group[group[col]==lab][block].astype(str)).split("|"))-{''}
                  for side,col,block in [("X","source_class","outgoing_block_X"),
                                         ("Y","source_class","same_count_block_Y"),
                                         ("Z","target_class","changed_count_block_Z")]}
            row=dict(condition="semi",method="V3_JOINT_QT",heldout_building=building,coarse_label=lab,
                     fine_labels="|".join(sorted(z.fine_label.unique())),coarse_k=int(z.coarse_k.iloc[0]),fine_k=int(z.fine_k.iloc[0]),
                     selected_family=z.selected_family.iloc[0],historical_members=join(z.worker_id),historical_member_n=len(z),
                     new_members=join(z.loc[z.origin.eq("new"),"worker_id"]),
                     used_X=join(uses["X"]),used_Y=join(uses["Y"]),used_Z=join(uses["Z"]),
                     actual_pools=group[(group.source_class==lab)|(group.target_class==lab)].pool_id.nunique(),
                     **{feature:float(z[feature].mean()) for feature in FEATURES})
            for feature in ["n_records","n_images","n_buildings","q_images","q_buildings","t_images","t_buildings"]:
                row[feature+"_minimum"]=int(z[feature].min())
                row[feature+"_median"]=float(z[feature].median())
            roles.append(row)
    write(HERE/"CLASS_ROLES_AND_MEMBERS.csv",pd.DataFrame(roles))
    subgroup=[]
    inventory_by_pool=domains.set_index("pool_id")
    for (pool,src,dst),group in events.groupby(["pool_id","source_class","target_class"]):
        first=group.iloc[0]
        fold=labels[labels.heldout_building.eq(first.building)].set_index("worker_id")
        available=fold.loc[inventory_by_pool.loc[pool,"workers"].split("|")]
        source=available[available.coarse_label.eq(src)]
        target=available[available.coarse_label.eq(dst)]
        dq=float(target.q_history.mean()-source.q_history.mean())
        dt=float(target.t_history.mean()-source.t_history.mean())
        subgroup.append(dict(pool_id=pool,image=first.image,building=first.building,source_class=src,target_class=dst,
                             center_dQ=first.class_center_delta_q_history,center_dT=first.class_center_delta_t_history,
                             available_dQ=dq,available_dT=dt,available_history_direction_conflict=dq<=0 or dt>=0,
                             source_workers=join(source.index),target_workers=join(target.index),
                             support="same inherited LOBO features restricted to actual eligible pool; no target Q/T outcomes"))
    write(HERE/"CLASS_CENTER_VS_AVAILABLE_SUBGROUP.csv",pd.DataFrame(subgroup))
    active=capacity[capacity.registered_oriented_ABC.gt(0)].copy()
    # A member reservoir includes both the source union and the target block.
    source_union=[]
    for row in events.itertuples():
        source_union.append(join(set(row.outgoing_block_X.split("|"))|set(row.same_count_block_Y.split("|"))))
    events["source_union"]=source_union
    coverage=events.groupby(["cell_id","stage"]).agg(
        oriented_ABC=("oriented_triple_id","nunique"),physical_ABC=("physical_triple_id","nunique"),
        source_unions=("source_union","nunique"),source_blocks=("outgoing_block_X","nunique"),
        target_blocks=("changed_count_block_Z","nunique"),backgrounds=("common_background","nunique"),
        member_reservoirs=("reservoir_id","nunique")).reset_index()
    coverage=coverage.merge(active,on="cell_id",suffixes=("","_main"))
    write(HERE/"COVERAGE_BY_CELL_AND_LAYER.csv",coverage)
    full=active[active.full_cell_enumeration.astype(str).str.lower().eq("true")]
    write(HERE/"FULLY_ENUMERATED_CELLS.csv",full)
    inventory=domains.copy()
    inventory["has_registered_condition"]=inventory.pool_id.isin(events.pool_id)
    inventory["reason_if_not_registered"]=np.where(inventory.has_registered_condition,"","no_q_up_faster_direction_with_2m_source_m_target_and_n_ge_10")
    write(HERE/"POOL_OPPORTUNITY_LEDGER.csv",inventory)
    receipt=dict(input_pools=len(domains),input_buildings=domains.building.nunique(),registered_pools=events.pool_id.nunique(),
                 registered_buildings=events.building.nunique(),registered_cells=events.cell_id.nunique(),
                 feasible_class_count_configurations=len(configs),registered_class_count_configurations=len(configs),
                 complete_ABC_cells=len(full),theoretical_ordered_ABC=sum(int(x) for x in active.theoretical_ordered_ABC),
                 registered_oriented_ABC=events.oriented_triple_id.nunique(),registered_physical_ABC=events.physical_triple_id.nunique(),
                 registered_ABC_unique_endpoints=len(set(events.team_A)|set(events.team_B)|set(events.team_C)),
                 registered_distinct_pool_backgrounds=events[["pool_id","common_background"]].drop_duplicates().shape[0],
                 all_member_sets_exhaustive=False,all_class_configurations_exhaustive=True,
                 time_source="user_processed_reported_not_raw_log_replayed",time_unit="seconds, sum of member record times",
                 original_study_identity="Semi own joint EQT, real_v2; all_data descriptions and LOBO labels remain separate")
    save(HERE/"COVERAGE_RECEIPT.json",receipt)
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
