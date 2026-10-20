"""Reproduce small interpretation tables without refitting frozen labels."""
import pandas as pd

from run_classification import HERE, ROOT
from evaluate_classification import aggregate_profiles


def main():
    profiles = pd.read_csv(HERE / "person_class_explanations.csv")
    candidate = pd.read_csv(HERE / "semi_new_candidate/final_labels.csv")
    candidate = candidate[candidate.candidate.eq("semi_position_scale")]
    d = candidate[["worker_id", "class_id"]].merge(profiles[profiles.condition.eq("semi")], on="worker_id")
    summary = d.groupby(["class_id", "origin"]).agg(
        n=("worker_id", "nunique"), members=("worker_id", lambda s: "|".join(s)),
        q_mean=("q_mean", "mean"), q_adjusted=("q_peer_adjusted", "mean"),
        q_p10=("q_p10", "mean"), t_median=("t_median_seconds", "median"), n_q=("n_quality", "sum")).reset_index()
    summary.to_csv(HERE / "semi_new_candidate/position_qt_by_source.csv", index=False)
    adopted_path = HERE / "semi_adopted_labels.csv"
    if adopted_path.exists():
        adopted = pd.read_csv(adopted_path)
        original = profiles[profiles.condition.eq("semi")].copy()
        original = original.rename(columns={c: "structure_exploratory_" + c for c in
            ["coarse_class", "fine_class", "coarse_name_zh", "fine_name_zh", "fine_status"]})
        fields = ["worker_id", "coarse_class", "fine_class", "coarse_name_zh", "fine_name_zh",
                  "coarse_adoption_status", "fine_adoption_status", "label_status", "missing_reason"]
        updated = adopted[fields].merge(original, on="worker_id", how="left")
        updated.to_csv(HERE / "semi_adopted_person_explanations.csv", index=False, encoding="utf-8-sig")
        aggregate_profiles(updated).to_csv(HERE / "semi_adopted_qt_auxiliary_by_source.csv", index=False, encoding="utf-8-sig")
    fields = ["worker_id", "condition", "fine_class", "log_height_peer_delta_mean",
              "log_height_peer_delta_negative_buildings", "log_height_peer_delta_positive_buildings",
              "top_y_mean_peer_delta_mean", "bottom_y_mean_peer_delta_mean", "n_near_collinear_images", "n_near_collinear_buildings"]
    profiles[profiles.condition.eq("manual")][fields].to_csv(HERE / "manual_height_collinearity_auxiliary.csv", index=False)
    x = pd.read_csv(ROOT / "research/workers/personnel_marking_patterns_20261020/record_expression.csv")
    x = x[x.condition.eq("semi") & x.personal_comparison & x.peer_n.ge(3)]
    rows = []
    for worker, g in x.groupby("worker_id"):
        for deg in [3, 5, 10]:
            positive = g[g[f"near_straight_nodes_{deg}deg"].gt(0)]
            rows.append(dict(worker_id=worker, angle_threshold=deg, records=len(g),
                             collinear_images=positive.image_id.nunique(), collinear_buildings=positive.building_id.nunique(),
                             repeated=positive.image_id.nunique() >= 2 and positive.building_id.nunique() >= 2))
    pd.DataFrame(rows).to_csv(HERE / "semi_new_candidate/repeated_collinearity_sensitivity.csv", index=False)


if __name__ == "__main__":
    main()
