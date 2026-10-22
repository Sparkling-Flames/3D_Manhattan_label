"""Hierarchical, denominator-explicit summaries of new Semi exchange outcomes."""
from __future__ import annotations

from register_semi_closure import *

PAIR_COMPONENTS = ["B8L2","D10","IoU3D100","iou_2d","S_bottom_deg","dir","Hmean","Hcenter",
                   "omission","extension","height_mean_ratio","nodes","ref_node_recall_9","ref_edge_recall_9",
                   "diag_wall_coverage_03","diag_wall_coverage_05","diag_corner_recall_05","geometry_area_h2",
                   "height_mean_h","top_y_mean_px","bottom_y_mean_px","fusion_turn_n","fusion_short_turn_edges","fusion_redundancy_n"]
METRICS = [f"{p}_{f}" for p in ["same","cross","net"] for f in PAIR_COMPONENTS]
METRICS += [f"{p}_{f}" for p in ["same","cross","net"] for f in ["recorded_time_logratio","recorded_time_pct","loss_gt5","loss_gt10","Q_up","time_down","QT_both_improve"]]
METRICS += ["common_quality_within_abs","common_quality_cross_abs","abs_Q_change_advantage",
            "within_joint_stable_main","cross_joint_stable_main","net_joint_stable_main",
            "A_failure","B_failure","C_failure","net_Q_not_down_more_than1","net_Q_not_down_more_than2",
            "net_Q_up_more_than1","net_time_down_Q_within1","net_time_down_Q_within2","C_minus_mean_source_B8L2",
            "C_minus_mean_source_D10","C_minus_mean_source_nodes","C_logtime_minus_mean_source_logtime",
            "within_abs_recorded_time_logratio","cross_abs_recorded_time_logratio","time_abs_variation_advantage"]
METRICS += [f"common_geometry_{p}_{f}" for p in ["within","cross","advantage"] for f in
            ["floor_jaccard_difference","mean_height_prism_pair_difference","structure_bound_cyclic_deg","centroid_distance_h","floor_area_abs_log_ratio","node_count_difference"]]
CELL_KEYS=["analysis_layer","building","image","difficulty","class_direction_semantics","source_class","target_class","n","m_AB","cell_id"]


def boolcol(s):
    return s.astype(str).str.lower().eq("true")


def prepare(e):
    e=e.copy()
    for f in ["all_scored","all_complete","recorded_time_single_source","A_failure","B_failure","C_failure"]:
        e[f]=boolcol(e[f])
    for f in ["n","m_AB"]:
        e[f]=pd.to_numeric(e[f]).astype(int)
    q=pd.to_numeric(e.net_B8L2,errors="coerce")
    dt=pd.to_numeric(e.net_recorded_time_logratio,errors="coerce")
    valid=e.all_scored
    for th in [1,2]:
        e[f"net_Q_not_down_more_than{th}"]=np.where(valid,(q>=-th).astype(float),np.nan)
        e[f"net_time_down_Q_within{th}"]=np.where(valid&e.recorded_time_single_source,((q>=-th)&(dt<0)).astype(float),np.nan)
    e["net_Q_up_more_than1"]=np.where(valid,(q>1).astype(float),np.nan)
    av=pd.to_numeric(e.A_source_time_total_seconds,errors="coerce")
    bv=pd.to_numeric(e.B_source_time_total_seconds,errors="coerce")
    cv=pd.to_numeric(e.C_source_time_total_seconds,errors="coerce")
    e["C_logtime_minus_mean_source_logtime"]=np.where(e.recorded_time_single_source,np.log(cv)-.5*(np.log(av)+np.log(bv)),np.nan)
    e["within_abs_recorded_time_logratio"]=pd.to_numeric(e.same_recorded_time_logratio,errors="coerce").abs()
    e["cross_abs_recorded_time_logratio"]=pd.to_numeric(e.cross_recorded_time_logratio,errors="coerce").abs()
    used=[f for f in METRICS if f in e]
    for f in used:
        if e[f].dtype==object and set(e[f].dropna().astype(str).str.lower().unique())<=set(["true","false"]):
            e[f]=boolcol(e[f]).astype(float)
        else:
            e[f]=pd.to_numeric(e[f],errors="coerce")
    # Primary quality contrasts use the common three-score denominator.  The
    # original complete-event file retains pair-specific values unchanged.
    quality=[f for f in used if (any(f.startswith(p+"_") for p in ["same","cross","net"]) and not any(x in f for x in ["recorded_time","time_down","failure","joint_stable"]))]
    for f in quality:
        e.loc[~valid,f]=np.nan
    for f in [f for f in used if "QT_both" in f or f.startswith("net_time_down_Q")]:
        e.loc[~valid|~e.recorded_time_single_source,f]=np.nan
    return e,used


def hierarchy(e,metrics):
    bgkeys=CELL_KEYS+["reservoir_id","background_id"]
    bg=e.groupby(bgkeys,dropna=False)[metrics].mean().reset_index()
    exposure=e.groupby(bgkeys,dropna=False).agg(oriented_events=("event_id","size"),physical_ABC=("physical_triple_id","nunique"),
                                             source_Q_min=("B_B8L2","min"),source_Q_max=("B_B8L2","max"),
                                             net_Q_min=("net_B8L2","min"),net_Q_max=("net_B8L2","max"),
                                             source_blocks=("same_count_block_Y","nunique"),C_team=("team_C","first"),
                                             common_background=("common_background","first"),target_block=("changed_count_block_Z","first")).reset_index()
    bg=bg.merge(exposure,on=bgkeys,validate="one_to_one")
    r=bg.groupby(CELL_KEYS+["reservoir_id"],dropna=False)[metrics].mean().reset_index()
    cells=r.groupby(CELL_KEYS,dropna=False)[metrics].mean().reset_index()
    counts=e.groupby(CELL_KEYS,dropna=False).agg(oriented_events=("event_id","size"),physical_ABC=("physical_triple_id","nunique"),
                                               common_backgrounds=("background_id","nunique"),reservoirs=("reservoir_id","nunique"),
                                               scored_oriented_events=("all_scored","sum"),complete_oriented_events=("all_complete","sum"),
                                               time_comparable_oriented_events=("recorded_time_single_source","sum")).reset_index()
    cells=cells.merge(counts,on=CELL_KEYS,validate="one_to_one")
    return bg,r,cells


def image_building(cells,metrics,extra=()):
    keys=["analysis_layer","building","image",*extra]
    im=cells.groupby(keys,dropna=False)[metrics].mean().reset_index()
    bk=["analysis_layer","building",*extra]
    bl=im.groupby(bk,dropna=False)[metrics].mean().reset_index()
    return im,bl


def summarize_subset(label,e,cells,metrics):
    im,bl=image_building(cells,metrics)
    row=dict(condition_id=label,analysis_layer=e.analysis_layer.iloc[0],oriented_events=len(e),physical_ABC=e.physical_triple_id.nunique(),
             images=e.image.nunique(),buildings=e.building.nunique(),cells=e.cell_id.nunique(),backgrounds=e[["pool_id","common_background"]].drop_duplicates().shape[0],
             unique_endpoints=len(set(e.team_A)|set(e.team_B)|set(e.team_C)),three_scored_events=int(e.all_scored.sum()),
             three_complete_events=int(e.all_complete.sum()),time_comparable_events=int(e.recorded_time_single_source.sum()),
             n_values="|".join(map(str,sorted(e.n.unique()))),m_values="|".join(map(str,sorted(e.m_AB.unique()))))
    row.update({f:float(bl[f].mean()) if bl[f].notna().any() else np.nan for f in metrics})
    for f in ["same","cross","net"]:
        logmean=row.get(f+"_recorded_time_logratio",np.nan)
        row[f+"_recorded_time_pct"]=100*math.expm1(logmean) if np.isfinite(logmean) else np.nan
    for name,frame in [("images",im),("buildings",bl)]:
        valid=frame.net_B8L2.notna()
        timeok=frame.net_recorded_time_logratio.notna()
        row[name+"_Q_evaluable"]=int(valid.sum())
        row[name+"_Q_improved"]=int((valid&(frame.net_B8L2>0)).sum())
        row[name+"_Q_ge_minus1"]=int((valid&(frame.net_B8L2>=-1)).sum())
        row[name+"_time_evaluable"]=int(timeok.sum())
        row[name+"_time_reduced"]=int((timeok&(frame.net_recorded_time_logratio<0)).sum())
        row[name+"_both_improved"]=int((valid&timeok&(frame.net_B8L2>0)&(frame.net_recorded_time_logratio<0)).sum())
        row[name+"_abs_cross_gt_within"]=int((frame.abs_Q_change_advantage>0).sum())
    return row


def member_associations(e):
    rows=[]
    main=e[e.analysis_layer.eq("source_partition_expansion")]
    for keys,g in main.groupby(["cell_id","reservoir_id","background_id"]):
        good=g[g.all_scored]
        if not len(good):continue
        first=good.iloc[0]
        workers=sorted(set("|".join(good.same_count_block_Y).split("|")))
        for worker in workers:
            present=good.same_count_block_Y.str.split("|").map(lambda x:worker in x)
            if not present.any() or present.all():continue
            row={k:first[k] for k in ["pool_id","building","image","difficulty","source_class","target_class","n","m_AB"]}
            row.update(cell_id=keys[0],reservoir_id=keys[1],background_id=keys[2],worker_id=worker,
                       blocks_present=int(present.sum()),blocks_absent=int((~present).sum()),
                       net_Q_worker_present=float(good.loc[present,"net_B8L2"].mean()),
                       net_Q_worker_absent=float(good.loc[~present,"net_B8L2"].mean()),
                       source_Q_worker_present=float(good.loc[present,"B_B8L2"].mean()),
                       source_Q_worker_absent=float(good.loc[~present,"B_B8L2"].mean()))
            row["source_member_inclusion_Q_contrast"]=row["source_Q_worker_present"]-row["source_Q_worker_absent"]
            rows.append(row)
    details=pd.DataFrame(rows)
    if len(details):
        write(HERE/"SOURCE_MEMBER_ASSOCIATIONS_BY_BACKGROUND.csv.gz",details)
        keys=["pool_id","building","image","source_class","target_class","n","m_AB","worker_id"]
        summary=details.groupby(keys).agg(background_comparisons=("background_id","size"),
                                        mean_source_Q_inclusion_contrast=("source_member_inclusion_Q_contrast","mean"),
                                        min_source_Q_inclusion_contrast=("source_member_inclusion_Q_contrast","min"),
                                        max_source_Q_inclusion_contrast=("source_member_inclusion_Q_contrast","max")).reset_index()
        summary["interpretation"]="Within frozen source union and same D, m-member block inclusion contrast; conditional group contribution, not an intrinsic personal causal effect"
        write(HERE/"SOURCE_MEMBER_BLOCK_ASSOCIATIONS.csv",summary)


def qt_summary():
    path=HERE/"CONTINUOUS_QT_COMPLETE.csv.gz"
    if not path.exists():return
    q=pd.read_csv(path)
    for f in ["all_scored","all_complete","recorded_time_single_source","C_failure","QT_failure"]:
        q[f]=boolcol(q[f])
    metrics=[f for f in q if f.startswith("class_minus_qt_")]+["class_vs_qt_log_time_ratio","C_failure","QT_failure"]
    for f in metrics:q[f]=pd.to_numeric(q[f],errors="coerce")
    rows=[]
    for layer,g in q.groupby("analysis_layer"):
        for name,z in [("all_same_candidates",g),("alternative_choice_exists",g[g.feasible_candidate_blocks.gt(1)]),
                       ("different_actual_QT_team",g[g.C_QT_actual_m.gt(0)])]:
            if not len(z):continue
            cells=z.groupby(["building","image","cell_id"])[metrics].mean().reset_index()
            ims=cells.groupby(["building","image"])[metrics].mean().reset_index()
            bs=ims.groupby("building")[metrics].mean()
            row=dict(analysis_layer=layer,scope=name,control_records=len(z),images=z.image.nunique(),buildings=z.building.nunique(),
                     cells=z.cell_id.nunique(),unique_class_teams=z.team_C.nunique(),unique_QT_teams=z.team_QT.nunique(),
                     scored_controls=int(z.all_scored.sum()),complete_controls=int(z.all_complete.sum()),
                     time_controls=int(z.recorded_time_single_source.sum()),same_C_QT_teams=int((z.C_QT_actual_m==0).sum()))
            row.update(bs.mean().to_dict())
            row["class_vs_qt_time_pct"]=100*math.expm1(row["class_vs_qt_log_time_ratio"]) if np.isfinite(row["class_vs_qt_log_time_ratio"]) else np.nan
            rows.append(row)
    write(HERE/"CONTINUOUS_QT_SAME_SUPPORT_SUMMARY.csv",pd.DataFrame(rows))


def risk_counts(e):
    rows=[]
    for layer,frame in e.groupby("analysis_layer"):
        slices=[("all_registered_n_m",frame)]
        slices.extend((f"n{n}_m{m}",g) for (n,m),g in frame.groupby(["n","m_AB"]))
        for scope,g in slices:
            good=g[g.all_scored]
            pairs=good.drop_duplicates(["team_B","team_C"])
            fail_keys={arm:set(g.loc[g[arm+"_failure"].astype(bool),"team_"+arm]) for arm in "ABC"}
            row=dict(analysis_layer=layer,condition_id=scope,oriented_events=len(g),physical_ABC=g.physical_triple_id.nunique(),
                     failed_physical_ABC=g[g.A_failure.astype(bool)|g.B_failure.astype(bool)|g.C_failure.astype(bool)].physical_triple_id.nunique(),
                     common_three_scored_source_comparisons=len(good),distinct_scored_B_C_pairs=len(pairs),
                     A_failure_unique_teams=len(fail_keys["A"]),B_failure_unique_teams=len(fail_keys["B"]),C_failure_unique_teams=len(fail_keys["C"]),
                     total_failure_unique_teams=len(set.union(*fail_keys.values())))
            row["unique_source_A_B_teams"]=len(set(g.team_A)|set(g.team_B))
            row["unique_target_C_teams"]=g.team_C.nunique()
            row["unique_ABC_teams"]=len(set(g.team_A)|set(g.team_B)|set(g.team_C))
            for threshold in [5,10]:
                row[f"net_loss_gt{threshold}_source_comparisons"]=int((good.net_B8L2 < -threshold).sum())
                row[f"net_loss_gt{threshold}_distinct_B_C_pairs"]=int((pairs.net_B8L2 < -threshold).sum())
                row[f"net_loss_gt{threshold}_raw_pair_fraction"]=float((pairs.net_B8L2 < -threshold).mean())
            rows.append(row)
    write(HERE/"FAILURE_AND_QUALITY_TAIL_COUNTS.csv",pd.DataFrame(rows))


def main():
    path=HERE/"EVENTS_COMPLETE.csv.gz"
    if not path.exists():
        print("No completed pool yet; registration and coverage are already saved.")
        return
    raw=pd.read_csv(path,low_memory=False)
    e,metrics=prepare(raw)
    bg,r,cells=hierarchy(e,metrics)
    write(HERE/"BLOCK_BACKGROUND_RESPONSES.csv.gz",bg)
    write(HERE/"MEMBER_RESERVOIR_RESPONSES.csv",r)
    write(HERE/"DIRECTION_CELL_RESPONSES.csv",cells)
    images,buildings=image_building(cells,metrics,extra=["n","m_AB"])
    write(HERE/"IMAGE_N_M_RESPONSES.csv",images)
    write(HERE/"BUILDING_N_M_RESPONSES.csv",buildings)
    whole_images,whole_buildings=image_building(cells,metrics)
    write(HERE/"IMAGE_OVERALL_RESPONSES.csv",whole_images)
    write(HERE/"BUILDING_OVERALL_RESPONSES.csv",whole_buildings)
    rows=[]
    for layer,g in e.groupby("analysis_layer"):
        c=cells[cells.analysis_layer.eq(layer)]
        rows.append(summarize_subset("all_registered_n_m",g,c,metrics))
        for m,gm in g.groupby("m_AB"):
            rows.append(summarize_subset(f"m{m}_all_n",gm,c[c.m_AB.eq(m)],metrics))
        for (n,m),gm in g.groupby(["n","m_AB"]):
            rows.append(summarize_subset(f"n{n}_m{m}",gm,c[c.n.eq(n)&c.m_AB.eq(m)],metrics))
        for role,gr in g.groupby("class_direction_semantics"):
            rows.append(summarize_subset(role,gr,c[c.class_direction_semantics.eq(role)],metrics))
        for difficulty,gr in g.groupby("difficulty"):
            rows.append(summarize_subset("difficulty_"+str(difficulty),gr,c[c.difficulty.eq(difficulty)],metrics))
        # Separately labeled interpretation check. The original frozen main
        # rows above retain all directions, including any available-subgroup
        # historical direction disagreement.
        available=pd.read_csv(HERE/"CLASS_CENTER_VS_AVAILABLE_SUBGROUP.csv")
        supported=available[~boolcol(available.available_history_direction_conflict)]
        ok=set(zip(supported.pool_id,supported.source_class,supported.target_class))
        keep=g.apply(lambda z:(z.pool_id,z.source_class,z.target_class) in ok,axis=1)
        gr=g[keep]
        cr=c[c.cell_id.isin(gr.cell_id)]
        if len(gr):
            rows.append(summarize_subset("available_subgroup_history_Q_up_faster_posthoc_interpretation",gr,cr,metrics))
            for (n,m),gm in gr.groupby(["n","m_AB"]):
                rows.append(summarize_subset(f"available_history_n{n}_m{m}",gm,cr[cr.n.eq(n)&cr.m_AB.eq(m)],metrics))
    summary=pd.DataFrame(rows)
    write(HERE/"CONDITION_RESPONSES.csv",summary)
    den=[]
    for (layer,n,m),g in e.groupby(["analysis_layer","n","m_AB"]):
        for f in metrics:
            good=g[g[f].notna()]
            den.append(dict(analysis_layer=layer,n=n,m=m,metric=f,nonmissing_oriented_events=len(good),
                            nonmissing_physical_ABC=good.physical_triple_id.nunique(),images=good.image.nunique(),
                            buildings=good.building.nunique(),backgrounds=good[["pool_id","common_background"]].drop_duplicates().shape[0]))
    write(HERE/"METRIC_DENOMINATORS.csv",pd.DataFrame(den))
    # Keep actual examples and all low-tail denominators in the complete file.
    cases=raw[raw.all_scored].copy()
    cases["orientation_free_net_Q"]=cases.C_B8L2-(cases.A_B8L2+cases.B_B8L2)/2
    physical=cases.sort_values("event_id").drop_duplicates("physical_triple_id")
    selected=pd.concat([physical.nlargest(12,"orientation_free_net_Q"),physical.nsmallest(12,"orientation_free_net_Q"),
                        physical[(physical.C_nodes==physical.B_nodes)&(physical.net_B8L2>3)].nlargest(6,"net_B8L2"),
                        raw[raw.A_failure|raw.B_failure|raw.C_failure].head(20)],ignore_index=True).drop_duplicates("event_id")
    write(HERE/"MECHANISM_CASE_CANDIDATES.csv",selected)
    member_associations(e)
    qt_summary()
    risk_counts(e)
    status=dict(events=len(e),physical_ABC=e.physical_triple_id.nunique(),images=e.image.nunique(),buildings=e.building.nunique(),
                main_weighting="source partitions -> same background -> member reservoir -> direction/n/m cell -> image -> building equal",
                completion_layer="kept separate; one physical ABC per newly covered class-count configuration",
                signed_same_change_warning="A/B mirrors cancel signed B-A by design; same-class stability is assessed using absolute changes",
                independent_unit="image/building; events, mirrored orientations, and reused endpoints are not independent samples",
                time_summary="geometric ratio of summed compatible source record seconds; not measured future elapsed production time")
    save(HERE/"SUMMARY_RECEIPT.json",status)
    print(summary[["analysis_layer","condition_id","physical_ABC","images","buildings","net_B8L2","net_D10","net_recorded_time_pct","images_Q_improved","images_time_reduced","common_quality_within_abs","common_quality_cross_abs","C_failure"]].to_string(index=False))


if __name__=="__main__":
    main()
