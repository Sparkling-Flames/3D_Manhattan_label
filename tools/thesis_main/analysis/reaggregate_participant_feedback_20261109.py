"""Reaggregate final adopted feedback records; no fusion or quality rescoring.
Cluster summaries adapted from Stage03 analyze_feedback.py; estimands and seed unchanged.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "research/difficulty/participant_feedback_20261109"
OUT = BASE / "results"
SEED = 20261109
FACTORS = ["occlusion", "low_texture", "seam", "reflection", "low_quality", "trivial"]
METRICS = ["simplified", "turn_deficit", "matched_boundary_abs_deg", "omission", "B8L2"]
def save_csv(name, frame):
    frame.to_csv(OUT / name,index=False,encoding="utf-8-sig",lineterminator="\n")
def interval_from_clusters(frame, unit="image_id", cluster="building_id"):
    """Percentile resampling of clusters; point estimate remains unit-equal.

    This describes variation across the observed clusters. It is not a random
    population-sampling assertion and does not treat repeated human rows as IID.
    """
    x = frame[[unit, cluster, "difference"]].drop_duplicates(unit)
    if x[cluster].nunique() < 2:
        return np.nan, np.nan
    groups = x.groupby(cluster).difference.agg(["sum", "count"])
    rng = np.random.default_rng(SEED)
    ind = rng.integers(len(groups), size=(4000, len(groups)))
    vals = groups["sum"].to_numpy()[ind].sum(1) / groups["count"].to_numpy()[ind].sum(1)
    return tuple(np.quantile(vals, [.025, .975]))

def associations(d):
    select = d.formal_primary & d.difficulty_recorded
    # Predeclared summaries for all five concrete factors; no p-value screening.
    raw_contrasts = []
    person_contrasts = []
    summaries = []
    for (condition, route), z in d[select].groupby(["condition", "scene_route"]):
        for factor in FACTORS[:-1]:
            for metric in METRICS:
                zz = z.dropna(subset=[metric]).copy()
                for key, p in zz.groupby(["image_id", "reference_id"], dropna=False):
                    if p[factor].nunique() != 2:
                        continue
                    a, b = p.loc[p[factor].eq(1), metric], p.loc[p[factor].eq(0), metric]
                    raw_contrasts.append(dict(condition=condition, scene_route=route, factor=factor, metric=metric,
                        image_id=key[0], image_code=p.image_code.iloc[0], reference_id=key[1],
                        building_id=p.building_id.iloc[0], selected_n=len(a), not_selected_n=len(b),
                        selected_mean=a.mean(), not_selected_mean=b.mean(), difference=a.mean()-b.mean()))
                # Complementary within-person evidence: first remove the
                # image-target mean, then compare each person's reports within
                # a building, and finally average buildings equally per person.
                if not len(zz):
                    continue
                zz["residual"] = zz[metric] - zz.groupby(["image_id", "reference_id"], dropna=False)[metric].transform("mean")
                for (worker, building), p in zz.groupby(["worker_id", "building_id"]):
                    if p[factor].nunique() != 2:
                        continue
                    a, b = p[p[factor].eq(1)], p[p[factor].eq(0)]
                    person_contrasts.append(dict(condition=condition, scene_route=route, factor=factor, metric=metric,
                        worker_id=worker, building_id=building, selected_n=len(a), not_selected_n=len(b),
                        raw_difference=a[metric].mean()-b[metric].mean(),
                        difference=a.residual.mean()-b.residual.mean()))
    images = pd.DataFrame(raw_contrasts)
    persons = pd.DataFrame(person_contrasts)
    group = ["condition", "scene_route", "factor", "metric"]
    for key, p in images.groupby(group):
        lo, hi = interval_from_clusters(p)
        summaries.append(dict(zip(group, key), comparison="same_image_target", units=len(p),
            buildings=p.building_id.nunique(), selected_responses=int(p.selected_n.sum()),
            not_selected_responses=int(p.not_selected_n.sum()), mean_difference=p.difference.mean(),
            median_difference=p.difference.median(), lower_95=lo, upper_95=hi,
            positive_units=int((p.difference>1e-12).sum()), negative_units=int((p.difference < -1e-12).sum()),
            zero_units=int((p.difference.abs()<=1e-12).sum()), interval_unit="building_cluster_resample"))
    person_means = persons.groupby(group+["worker_id"]).agg(difference=("difference", "mean"),
        raw_difference=("raw_difference", "mean"), buildings=("building_id", "nunique"),
        selected_n=("selected_n", "sum"), not_selected_n=("not_selected_n", "sum")).reset_index()
    for key, p in person_means.groupby(group):
        pp = p.copy()
        pp["cluster"] = pp.worker_id
        lo, hi = interval_from_clusters(pp, unit="worker_id", cluster="cluster")
        summaries.append(dict(zip(group, key), comparison="same_person_same_building_image_centered", units=len(p),
            buildings=int(persons.loc[np.logical_and.reduce([persons[c].eq(v) for c,v in zip(group,key)]), "building_id"].nunique()),
            selected_responses=int(p.selected_n.sum()), not_selected_responses=int(p.not_selected_n.sum()),
            mean_difference=p.difference.mean(), median_difference=p.difference.median(), lower_95=lo, upper_95=hi,
            positive_units=int((p.difference>1e-12).sum()), negative_units=int((p.difference < -1e-12).sum()),
            zero_units=int((p.difference.abs()<=1e-12).sum()), interval_unit="person_cluster_resample"))
    save_csv("difficulty_same_image_target_contrasts.csv", images)
    save_csv("difficulty_same_person_building_contrasts.csv", persons)
    save_csv("difficulty_same_person_summary.csv", person_means)
    save_csv("difficulty_association_summary.csv", pd.DataFrame(summaries))
    cols = ["object_id", "worker_id", "image_code", "image_id", "building_id", "condition", "scene_route", "reference_id",
            "difficulty_choices", *FACTORS, *METRICS]
    save_csv("difficulty_geometry_analysis_records.csv", d.loc[select, cols])

def main():
    d=pd.read_csv(BASE / "inputs/formal_feedback_records.csv")
    assert d.object_id.is_unique
    assert d.groupby("condition").size().to_dict()=={"manual":1016,"semi":456}
    assert d.scene_route.eq("ordinary").all() and d.formal_primary.all()
    assert d.difficulty_recorded.all()
    OUT.mkdir(exist_ok=True)
    associations(d)
    support=[]
    for (condition,), p in d.groupby(["condition"]):
        for metric in METRICS:
            q=p.dropna(subset=[metric])
            support.append(dict(condition=condition,metric=metric,records=len(q),people=q.worker_id.nunique(),images=q.image_id.nunique(),buildings=q.building_id.nunique()))
    save_csv("metric_support.csv",pd.DataFrame(support))
    summary=pd.read_csv(OUT/"difficulty_association_summary.csv")
    old=pd.read_csv(BASE/"inputs/previous_association_summary.csv")
    keys=["condition","scene_route","factor","metric","comparison"]
    changes=summary.merge(old,on=keys,suffixes=("_final","_previous"),validate="one_to_one")
    changes["estimate_change"]=changes.mean_difference_final-changes.mean_difference_previous
    save_csv("aggregation_change_check.csv",changes)
    print(summary.query("factor=='occlusion' and metric in ['simplified','omission']")[["condition","metric","comparison","units","mean_difference","lower_95","upper_95"]].to_string(index=False))
if __name__=="__main__": main()
