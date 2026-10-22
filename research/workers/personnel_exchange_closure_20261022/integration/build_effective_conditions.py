"""Join finished analyses into a denominator-explicit adoption table.

No annotation, label, fusion, or score is changed by this script.  Each value is
copied from a named completed analysis table.  An absent metric stays missing.
"""
from pathlib import Path
import hashlib
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "integration"


def load(rel):
    return pd.read_csv(ROOT / rel, dtype={"possible_unordered_XY_ABC": str,
                                         "possible_concrete_backgrounds": str,
                                         "unregistered_unordered_XY_ABC": str,
                                         "unregistered_concrete_backgrounds": str})


def val(r, key, default=None):
    x = r.get(key, default)
    return default if pd.isna(x) else x


def base(method, condition, source, key):
    return dict(classification=method, evaluation_condition=condition,
                underlying_data="real_v2", labels="target_building_excluded",
                source_table=source, source_row_key=key,
                endpoint_file="delivery/endpoints/ALL_REQUIRED_ENDPOINT_SCALARS.csv.gz",
                geometry_file="delivery/endpoints/ALL_REQUIRED_ENDPOINT_GEOMETRY.csv.gz",
                whole_personnel_space_exhaustive=False,
                result_identity="v2 internal evaluation; no external blind-test claim")


def main():
    rows = []
    src = "manual_joint/EFFECTIVE_CONDITIONS.csv"
    common = load("manual_joint/COMMON_ABC_SIGNED_EFFECTS.csv").set_index(["stage", "view"])
    panels_a = load("manual_joint/BACKGROUND_PANELS.csv.gz")
    panels_b = load("manual_joint/phase_b_highq_slower/BACKGROUND_PANELS.csv.gz")
    capacities = load("manual_joint/CAPACITY_ALL_N_M.csv.gz")
    # Theoretical ABC capacities can exceed 2**53: retain integers from CSV text.
    cap_exact = pd.read_csv(ROOT / "manual_joint/CAPACITY_ALL_N_M.csv.gz", dtype=str).set_index("capacity_id")
    for _, r in load(src).iterrows():
        stage, view = r["stage"], r["view"]
        c = common.loc[(stage, view)]
        q = base("Manual 结构＋Q/T 联合分类", "Manual", src, f"{stage}:{view}")
        q.update(condition_id=f"MANUAL_{stage}_{view}", input_condition=r.input_condition,
                 class_level=r.class_level, personnel_domain=r.personnel_domain,
                 source_semantics=r.source_semantics, target_semantics=r.target_semantics,
                 n=int(r.n), m=int(r.actual_m), replacement_fraction=r.replacement_fraction,
                 class_seat_change=r.class_seat_change,
                 background_rule=f"same D of {int(r.common_background_n)}; frozen balanced member reservoirs",
                 selection_identity=("stage A outcome-selected direction; new stage B backgrounds" if stage == "B"
                                     else "post hoc semantic subset" if "exploratory" in view else "frozen stage A design"),
                 adoption=r.adoption, use=r.use, registered_event_rows=int(r.events),
                 physical_ABC=int(r.events), common_ABC_rows=int(c.common_scored_events),
                 images=int(r.images), buildings=int(r.buildings), backgrounds=int(r.unique_backgrounds),
                 all_time_rows=int(r.time_comparable_events), aggregation=r.estimate_order,
                 Q_B_minus_A=c.same_B8L2, Q_C_minus_A=c.cross_B8L2,
                 Q_C_minus_B=c.net_B8L2, Q_C_minus_mean_A_B=c.sym_B8L2,
                 signed_Q_denominator="same common ABC scored rows",
                 D10_B_minus_A=c.same_D10, D10_C_minus_A=c.cross_D10,
                 D10_C_minus_B=c.net_D10, D10_C_minus_mean_A_B=c.sym_D10,
                 pairwise_Q_B_minus_A=r.pairwise_same_B8L2,
                 pairwise_Q_C_minus_A=r.pairwise_cross_B8L2,
                 pairwise_Q_C_minus_B=r.pairwise_net_B8L2,
                 same_abs_Q=r.common_quality_within_abs,
                 cross_abs_Q=r.sym_cross_abs_B8L2,
                 abs_cross_definition="(|C-A|+|C-B|)/2; common ABC scores",
                 Q_net_positive_images=c.image_net_Q_positive, Q_net_known_images=c.image_net_Q_known,
                 Q_net_positive_buildings=c.building_net_Q_positive, Q_net_known_buildings=c.building_net_Q_known,
                 Q_sym_positive_images=c.image_sym_Q_positive, Q_sym_known_images=c.image_sym_Q_known,
                 Q_sym_positive_buildings=c.building_sym_Q_positive, Q_sym_known_buildings=c.building_sym_Q_known,
                 cross_abs_larger_images=r.image_sym_cross_abs_larger_improved,
                 cross_abs_larger_images_known=r.image_sym_cross_abs_larger_known,
                 cross_abs_larger_buildings=r.building_sym_cross_abs_larger_improved,
                 cross_abs_larger_buildings_known=r.building_sym_cross_abs_larger_known,
                 positive_backgrounds_sym=r.panel_sym_quality_improved,
                 scored_backgrounds_sym=r.panel_sym_quality_known,
                 time_pct=r.sym_recorded_time_logratio_geomean_pct,
                 time_contrast="C / arithmetic mean(T_A,T_B), geometric aggregation; all reliable-time rows",
                 time_C_minus_B_common_pct=c.net_recorded_time_geomean_pct,
                 time_source=r.time_source,
                 joint_quality_time_positive_images=r.image_sym_QT_both_improved,
                 joint_quality_time_known_images=r.image_sym_QT_known,
                 joint_quality_time_positive_buildings=r.building_sym_QT_both_improved,
                 joint_quality_time_known_buildings=r.building_sym_QT_known,
                 A_failed_unique_endpoints=r.A_failed_unique_endpoints,
                 B_failed_unique_endpoints=r.B_failed_unique_endpoints,
                 C_failed_unique_endpoints=r.C_failed_unique_endpoints,
                 A_unique_endpoints=r.A_unique_endpoints, B_unique_endpoints=r.B_unique_endpoints,
                 C_unique_endpoints=r.C_unique_endpoints,
                 loss_gt5_weighted=r.sym_loss_gt5, loss_gt10_weighted=r.sym_loss_gt10,
                 loss_contrast="C-(A+B)/2 on common scored ABC",
                 components_contrast="C-(A+B)/2; each component retains its own valid denominator",
                 finite_reservoir_member_enumeration_complete=True,
                 member_coverage_note="all disjoint source partitions and target subsets in frozen finite reservoirs; not full pool",
                 exact_events_file=("manual_joint/phase_b_highq_slower/EVENTS_COMPLETE.csv.gz" if stage == "B"
                                    else "manual_joint/EVENTS_COMPLETE.csv.gz"),
                 class_members_reference="manual_joint/AVAILABLE_CLASS_CENTERS_AND_MEMBERS.csv",
                 capacity_reference="manual_joint/CAPACITY_ALL_N_M.csv.gz")
        for field in ["IoU3D100", "iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter", "omission", "extension",
                      "nodes", "height_mean_h", "height_mean_ratio", "fusion_turn_n", "fusion_short_turn_edges",
                      "fusion_redundancy_n", "ref_node_recall_9", "ref_edge_recall_9", "top_y_mean_px",
                      "bottom_y_mean_px", "geometry_area_h2", "centroid_x_h", "centroid_z_h"]:
            q[f"component_{field}"] = val(r, "sym_" + field)
        ps = panels_b if stage == "B" else panels_a
        ps = ps[(ps.n == r.n) & (ps.m == r.actual_m) &
                (ps.training_QT_direction == view.split(";")[0])]
        if "exploratory" in view:
            # This row is an outcome-selected subset; do not substitute a wider capacity.
            q["capacity_note"] = "semantic subset; exact 20 selected folds in PHASE_A_B_HIGH_Q_SLOWER_COMPARISON.csv"
        else:
            ids = list(dict.fromkeys(ps.capacity_id))
            q["observed_background_class_vectors"] = len(ps[["capacity_id", "background_counts"]].drop_duplicates())
            q["feasible_background_class_vectors"] = sum(int(cap_exact.loc[x, "feasible_background_class_configurations"]) for x in ids)
            q["theoretical_unordered_XY_ABC_in_selected_cells"] = str(sum(int(cap_exact.loc[x, "theoretical_unordered_source_ABC"]) for x in ids))
            q["theoretical_concrete_backgrounds_in_selected_cells"] = str(sum(int(cap_exact.loc[x, "feasible_concrete_backgrounds"]) for x in ids))
        rows.append(q)

    src = "structure/RECOMMENDED_CONDITIONS.csv"
    for _, r in load(src).iterrows():
        q = base("Manual 结构三类", "Manual", src, r.condition_id)
        q.update(condition_id=r.condition_id, input_condition="Manual structure history",
                 class_level=r.tier, personnel_domain=r.source_domain,
                 source_semantics=r.source_semantics, target_semantics=r.target_semantics,
                 n=int(r.n), m=int(r.actual_m), replacement_fraction=r.replacement_fraction,
                 class_seat_change=r.class_seat_change, background_rule=r.common_background_rule,
                 selection_identity=r.selection_identity, adoption=r.adoption,
                 use="结构解释、定向质量、换类风险", registered_event_rows=r.registered_events,
                 physical_ABC=r.unique_physical_triples, common_ABC_rows=r.common_ABC_events,
                 images=r.images_total, buildings=r.buildings_total, backgrounds=r.backgrounds_total,
                 aggregation=r.aggregation, signed_Q_denominator="same common ABC scored rows",
                 Q_B_minus_A=r.ABC_common_same_B8L2_mean, Q_C_minus_A=r.ABC_common_cross_B8L2_mean,
                 Q_C_minus_B=r.ABC_common_net_B8L2_mean,
                 Q_C_minus_mean_A_B=(r.ABC_common_cross_B8L2_mean+r.ABC_common_net_B8L2_mean)/2,
                 D10_B_minus_A=r.ABC_common_same_D10_mean, D10_C_minus_A=r.ABC_common_cross_D10_mean,
                 D10_C_minus_B=r.ABC_common_net_D10_mean,
                 pairwise_Q_B_minus_A=r.same_B8L2_mean, pairwise_Q_C_minus_A=r.cross_B8L2_mean,
                 pairwise_Q_C_minus_B=r.net_B8L2_mean,
                 same_abs_Q=r.common_quality_within_abs_mean, cross_abs_Q=r.common_quality_cross_abs_mean,
                 abs_cross_definition="|C-A|; common ABC scored events; source orientations not mirrored",
                 Q_net_positive_images=r.ABC_common_net_B8L2_images_positive,
                 Q_net_known_images=r.ABC_common_net_B8L2_image_n,
                 Q_net_positive_buildings=r.ABC_common_net_B8L2_buildings_positive,
                 Q_net_known_buildings=r.ABC_common_net_B8L2_building_n,
                 cross_abs_larger_buildings=r.abs_Q_change_advantage_buildings_positive,
                 cross_abs_larger_buildings_known=r.abs_Q_change_advantage_building_n,
                 time_pct=r.net_recorded_time_pct_mean,
                 time_contrast="C/B - 1, hierarchical arithmetic average; reliable same-source subset",
                 time_source=r.time_provenance, all_time_rows=r.net_recorded_time_pct_event_n,
                 time_images=r.net_recorded_time_pct_image_n, time_buildings=r.net_recorded_time_pct_building_n,
                 A_failure_weighted=r.A_failure_mean, B_failure_weighted=r.B_failure_mean,
                 C_failure_weighted=r.C_failure_mean,
                 A_failed_unique_endpoints=r.A_unique_failed_endpoints,
                 B_failed_unique_endpoints=r.B_unique_failed_endpoints,
                 C_failed_unique_endpoints=r.C_unique_failed_endpoints,
                 loss_gt10_weighted=r.net_loss_gt10_mean,
                 loss_contrast="C-B; pair-specific valid score denominator",
                 components_contrast="C-B; pair-specific valid denominators",
                 observed_background_class_vectors=r.observed_ABC_background_count_vectors,
                 feasible_background_class_vectors=r.feasible_ABC_background_count_vectors,
                 theoretical_unordered_XY_ABC_in_selected_cells=r.possible_unordered_XY_ABC,
                 theoretical_concrete_backgrounds_in_selected_cells=r.possible_concrete_backgrounds,
                 unregistered_unordered_XY_ABC=r.unregistered_unordered_XY_ABC,
                 unregistered_concrete_backgrounds=r.unregistered_concrete_backgrounds,
                 member_coverage_note=r.coverage_interpretation,
                 exact_events_file="structure/EVENTS_COMPLETE.csv.gz",
                 class_members_reference="structure/CLASS_LABELS_REUSED.csv.gz",
                 capacity_reference="structure/CAPACITY_AND_COVERAGE.csv.gz")
        for field in ["IoU3D100", "iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter", "omission", "extension",
                      "nodes", "fusion_turn_n", "ref_node_recall_5", "ref_edge_recall_5"]:
            q["component_"+field] = val(r, "net_"+field+"_mean")
        rows.append(q)

    src = "semi/EFFECTIVE_SEMI_CONDITIONS.csv"
    for _, r in load(src).iterrows():
        q = base("Semi 自身结构＋Q/T 联合分类", "Semi", src, r.condition_id)
        q.update(condition_id="SEMI_"+r.condition_id, input_condition=r.input_condition,
                 class_level=r.class_level, personnel_domain=r.personnel_domain,
                 source_semantics=r.source_semantics, target_semantics=r.target_semantics,
                 n=int(r.n), m=int(r.m), replacement_fraction=r.replacement_fraction,
                 class_seat_change=r.class_seat_change, background_rule=r.common_background_rule,
                 selection_identity=r.validation_status, adoption=r.adoption, use="效率、定向质量取舍",
                 registered_event_rows=r.oriented_events, physical_ABC=r.physical_ABC,
                 common_ABC_rows=r.three_scored_events, images=r.images, buildings=r.buildings,
                 backgrounds=r.backgrounds, all_time_rows=r.time_comparable_events,
                 aggregation=r.quality_weighting, signed_Q_denominator="common ABC scored rows; both A/B orientations",
                 Q_B_minus_A=r.same_B8L2, Q_C_minus_A=r.cross_B8L2, Q_C_minus_B=r.net_B8L2,
                 Q_C_minus_mean_A_B=r.C_minus_mean_source_B8L2,
                 D10_B_minus_A=r.same_D10, D10_C_minus_A=r.cross_D10, D10_C_minus_B=r.net_D10,
                 D10_C_minus_mean_A_B=r.C_minus_mean_source_D10,
                 same_abs_Q=r.common_quality_within_abs, cross_abs_Q=r.common_quality_cross_abs,
                 abs_cross_definition="both source orientations retained; one physical ABC is not two independent trials",
                 Q_net_positive_images=r.images_Q_improved, Q_net_known_images=r.images_Q_evaluable,
                 Q_net_positive_buildings=r.buildings_Q_improved, Q_net_known_buildings=r.buildings_Q_evaluable,
                 cross_abs_larger_images=r.images_abs_cross_gt_within,
                 cross_abs_larger_images_known=r.images_Q_evaluable,
                 cross_abs_larger_buildings=r.buildings_abs_cross_gt_within,
                 cross_abs_larger_buildings_known=r.buildings_Q_evaluable,
                 time_pct=r.net_recorded_time_pct,
                 time_contrast="C/B log ratio, geometric aggregation; both source orientations; all reliable-time rows",
                 time_source=r.time_provenance, time_images=r.images_time_evaluable,
                 time_buildings=r.buildings_time_evaluable,
                 joint_quality_time_positive_images=r.images_both_improved,
                 joint_quality_time_known_images=r.images_Q_evaluable,
                 joint_quality_time_positive_buildings=r.buildings_both_improved,
                 joint_quality_time_known_buildings=r.buildings_Q_evaluable,
                 A_failure_weighted=r.A_failure, B_failure_weighted=r.B_failure, C_failure_weighted=r.C_failure,
                 A_failed_unique_endpoints=r.raw_A_failure_unique_teams,
                 B_failed_unique_endpoints=r.raw_B_failure_unique_teams,
                 C_failed_unique_endpoints=r.raw_C_failure_unique_teams,
                 C_unique_endpoints=r.raw_unique_target_C_teams,
                 source_A_B_unique_endpoints=r.raw_unique_source_A_B_teams,
                 failed_physical_ABC=r.raw_failed_physical_ABC,
                 loss_gt5_weighted=r.net_loss_gt5, loss_gt10_weighted=r.net_loss_gt10,
                 loss_gt5_raw_count=r.raw_net_loss_gt5_distinct_B_C_pairs,
                 loss_gt10_raw_count=r.raw_net_loss_gt10_distinct_B_C_pairs,
                 scored_distinct_B_C_pairs=r.raw_distinct_scored_B_C_pairs,
                 loss_contrast="C-B, common ABC scores",
                 components_contrast="C-B, common ABC scores; geometry-specific unknown retained",
                 finite_reservoir_member_enumeration_complete=True,
                 member_coverage_note="all source partitions in selected reservoirs; eight small cells fully enumerated; full capacity in referenced tables",
                 exact_events_file="semi/EVENTS_COMPLETE.csv.gz",
                 class_members_reference="semi/CLASS_ROLES_AND_MEMBERS.csv",
                 capacity_reference="semi/CAPACITY_ALL_ATTEMPTS.csv",
                 available_subset_history_guard=r.direction_guard)
        for field in ["IoU3D100", "iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter", "omission", "extension",
                      "nodes", "height_mean_h", "height_mean_ratio", "fusion_turn_n", "fusion_short_turn_edges",
                      "fusion_redundancy_n", "ref_node_recall_9", "ref_edge_recall_9", "top_y_mean_px",
                      "bottom_y_mean_px", "geometry_area_h2"]:
            q["component_"+field] = val(r, "net_"+field)
        rows.append(q)

    frame = pd.DataFrame(rows)
    for c in ["Q", "D10"]:
        err = frame[f"{c}_C_minus_A"] - frame[f"{c}_B_minus_A"] - frame[f"{c}_C_minus_B"]
        assert err.abs().max() < 1e-7, (c, err.abs().max())
    frame.to_csv(OUT/"有效换类条件表.csv", index=False, encoding="utf-8-sig", float_format="%.10g")
    # A genuinely compact view. The complete table above preserves all contrasts,
    # metric identities, failure denominators and coverage references.
    compact = frame[["condition_id", "classification", "evaluation_condition", "source_semantics", "target_semantics",
                     "n", "m", "replacement_fraction", "background_rule", "physical_ABC", "images", "buildings",
                     "Q_B_minus_A", "Q_C_minus_A", "Q_C_minus_B", "Q_C_minus_mean_A_B", "D10_C_minus_B",
                     "same_abs_Q", "cross_abs_Q", "Q_net_positive_images", "Q_net_known_images",
                     "Q_net_positive_buildings", "Q_net_known_buildings", "time_pct", "time_contrast",
                     "C_failed_unique_endpoints", "loss_gt10_weighted", "adoption", "source_table", "source_row_key"]]
    compact.to_csv(OUT/"有效换类条件表_精简.csv", index=False, encoding="utf-8-sig", float_format="%.6g")
    receipt = dict(status="complete", rows=len(frame), columns=len(frame.columns),
                   source_rows={"manual_joint":20,"structure":14,"semi":9},
                   common_ABC_signed_identities_checked=True, new_fusion_calls=0, new_scoring_calls=0,
                   sha256=hashlib.sha256((OUT/"有效换类条件表.csv").read_bytes()).hexdigest())
    (OUT/"CONDITIONS_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
