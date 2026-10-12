"""高度归一化、相同坐标分母和底点微扰诊断；不修改或重新拟合质量分。"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

if __package__:
    from .quality_top_height_response_20261012 import distribution, profile_moments, read_json, save_json, validate_development_gates
else:
    from quality_top_height_response_20261012 import distribution, profile_moments, read_json, save_json, validate_development_gates


def clearance_diagnostics(annotation_mean, reference_mean):
    delta = annotation_mean-reference_mean
    available = reference_mean > 1
    return dict(annotation_mean=annotation_mean, reference_mean=reference_mean,
                wall_ratio=annotation_mean/reference_mean, signed_wall_error=delta/reference_mean,
                annotation_clearance=annotation_mean-1, reference_clearance=reference_mean-1,
                clearance_ratio=(annotation_mean-1)/(reference_mean-1) if available else None,
                signed_clearance_error=delta/(reference_mean-1) if available else None,
                normalization_multiplier=reference_mean/(reference_mean-1) if available else None,
                clearance_status="available" if available else "nonpositive_reference_clearance")


def coordinate_key(row, geometry):
    return (row["image_id"], row["reference_object_id"],
            tuple(map(tuple,geometry["bottom3d"])), tuple(map(tuple,geometry["top3d"])))


def bottom_margins(g, height):
    return [math.atan2(1,math.hypot(p[0],p[2]))*height/math.pi for p in g["bottom3d"]]


def perturb_bottom(g, indices, delta_y_px, height):
    changed = {k:[list(p) for p in g[k]] for k in ("bottom3d","top3d")}
    for i in indices:
        b, t = g["bottom3d"][i], g["top3d"][i]
        radius = math.hypot(b[0],b[2])
        angle = math.atan2(1,radius) + delta_y_px*math.pi/height
        if not 0 < angle < math.pi/2:
            return dict(status="out_of_projection_domain", failed_corner_index=i)
        scale = (1/math.tan(angle))/radius
        changed["bottom3d"][i] = [b[0]*scale,-1.,b[2]*scale]
        changed["top3d"][i] = [v*scale for v in t]
    return dict(status="available",geometry=changed)


def scenario(g, indices, delta, height, baseline, ref_mean):
    indices = list(indices)
    moved = perturb_bottom(g,indices,delta,height)
    result = dict(changed_corner_indices=indices,delta_y_px=delta,status=moved["status"])
    if moved["status"] != "available":
        return result | dict(failed_corner_index=moved["failed_corner_index"])
    after = profile_moments(moved["geometry"])
    # A positive scaling of each top endpoint also preserves every declared spherical top arc.
    ray_errors = []
    for a,b in zip(g["top3d"],moved["geometry"]["top3d"]):
        an,bn = math.sqrt(sum(v*v for v in a)),math.sqrt(sum(v*v for v in b))
        ray_errors.append(math.sqrt(sum((u/an-v/bn)**2 for u,v in zip(a,b))))
    return result | dict(mean_after=after["mean"],std_after=after["std"],
                         delta_mean_over_reference_height=(after["mean"]-baseline["mean"])/ref_mean,
                         delta_std_over_reference_height=(after["std"]-baseline["std"])/ref_mean,
                         maximum_top_unit_ray_change=max(ray_errors))


def row_diagnostics(row, geometries, design):
    a,g = (geometries[row[k]] for k in ("object_id","reference_object_id"))
    # This diagnostic is valid for the frozen shared-x reconstruction convention, not arbitrary 3-D input.
    for b,t in zip(a["bottom3d"],a["top3d"]):
        if not (b[1] == -1 and all(math.isclose(b[k],t[k],rel_tol=0,abs_tol=1e-12) for k in (0,2))):
            raise ValueError(("Fixed-camera vertical-pair convention mismatch",row["id"]))
    ap,gp = profile_moments(a),profile_moments(g)
    pixels = design["erp_height_px"]
    single = [scenario(a,[i],d,pixels,ap,gp["mean"]) for d in design["bottom_pixel_deltas"] for i in range(len(a["bottom3d"]))]
    valid = [s for s in single if s["status"] == "available"]
    all_points = [scenario(a,range(len(a["bottom3d"])),d,pixels,ap,gp["mean"]) for d in design["bottom_pixel_deltas"]]
    return {k:row[k] for k in ("id","image_id","image_code","building_id","applicability_confirmed")} | dict(
        height=clearance_diagnostics(ap["mean"],gp["mean"]),
        own_std_over_reference_height=ap["std"]/gp["mean"],Hcenter_frozen=row["metrics"]["Hcenter"],
        min_bottom_margin_px=min(bottom_margins(a,pixels)),
        single_evaluated_count=len(single),single_unavailable=[s for s in single if s["status"] != "available"],
        single_max_mean_change=max(valid,key=lambda s:abs(s["delta_mean_over_reference_height"])) if valid else None,
        single_max_std_change=max(valid,key=lambda s:abs(s["delta_std_over_reference_height"])) if valid else None,
        all_bottom_changes=all_points,
        max_top_ray_change=max([s["maximum_top_unit_ray_change"] for s in valid+all_points if s["status"] == "available"],default=0))


def statistics(rows, scores):
    def dist(values):
        return distribution(values) if values else None
    return dict(
        St_dominant_count=sum(scores[r["id"]]["weak_top_share_after_fourth_power"]>.5 for r in rows),
        relative4_increase_ge2=sum(scores[r["id"]]["scores"]["relative4"]-scores[r["id"]]["scores"]["relative2"]>=2 for r in rows),
        min_bottom_margin_px=dist([r["min_bottom_margin_px"] for r in rows]),
        signed_wall_error=dist([r["height"]["signed_wall_error"] for r in rows]),
        clearance_ratio=dist([r["height"]["clearance_ratio"] for r in rows if r["height"]["clearance_status"]=="available"]),
        normalization_multiplier=dist([r["height"]["normalization_multiplier"] for r in rows if r["height"]["clearance_status"]=="available"]),
        single_max_abs_mean_change=dist([abs(r["single_max_mean_change"]["delta_mean_over_reference_height"]) for r in rows if r["single_max_mean_change"]]),
        single_max_abs_std_change=dist([abs(r["single_max_std_change"]["delta_std_over_reference_height"]) for r in rows if r["single_max_std_change"]]),
        coherent_max_abs_mean_change=dist([max(abs(s["delta_mean_over_reference_height"]) for s in r["all_bottom_changes"] if s["status"]=="available") for r in rows if any(s["status"]=="available" for s in r["all_bottom_changes"])]))


def run(inputs, previous, design):
    rows,geometries = inputs["rows"],inputs["geometries"]
    validate_development_gates([dict(record_id=r["id"]) for r in rows],inputs["gates"])
    scores = {r["id"]:r for r in previous["development"]}
    if {r["id"] for r in rows} != set(scores):
        raise ValueError("Previous results and frozen development IDs differ")
    grouped = {}
    for r in sorted(rows,key=lambda r:r["id"]):
        grouped.setdefault(coordinate_key(r,geometries[r["object_id"]]),[]).append(r["id"])
    by_id = {r["id"]:r for r in rows}
    for members in grouped.values():
        first = by_id[members[0]]
        for rid in members[1:]:
            r = by_id[rid]
            if r["applicability_confirmed"] != first["applicability_confirmed"] or any(
                    not math.isclose(r["metrics"][k],v,rel_tol=0,abs_tol=1e-10) for k,v in first["metrics"].items()):
                raise ValueError(("Same-coordinate qualification or metric mismatch",members))
    # Evaluate identical coordinates once, then retain every source record in the statistical output.
    diagnostics = {}
    for members in grouped.values():
        base = row_diagnostics(by_id[members[0]],geometries,design)
        for rid in members:
            diagnostics[rid] = dict(base,id=rid)
    representatives = [diagnostics[m[0]] for m in grouped.values()]
    strata,selected = {},{}
    for name,known in (("all",None),("confirmed",True),("unknown",False)):
        subset = [r for r in diagnostics.values() if known is None or r["applicability_confirmed"]==known]
        unique = [r for r in representatives if known is None or r["applicability_confirmed"]==known]
        strata[name] = dict(records=len(subset),coordinate_groups=len(unique),
            images=len({r["image_id"] for r in subset}),buildings=len({r["building_id"] for r in subset}),
            record_statistics=statistics(subset,scores),coordinate_group_statistics=statistics(unique,scores))
        if known is None:
            continue
        criteria = dict(
            small_horizon_margin=lambda r:-r["min_bottom_margin_px"],
            single_mean_sensitivity=lambda r:abs(r["single_max_mean_change"]["delta_mean_over_reference_height"]),
            single_std_sensitivity=lambda r:abs(r["single_max_std_change"]["delta_std_over_reference_height"]),
            relative_ceiling_lowering=lambda r:-r["height"]["signed_clearance_error"])
        for criterion,key in criteria.items():
            available = [r for r in unique if r["single_max_mean_change"] and r["single_max_std_change"] and r["height"]["clearance_status"]=="available"]
            for r in sorted(available,key=lambda r:(-key(r),r["id"]))[:3]:
                selected.setdefault(r["id"],[]).append(dict(stratum=name,criterion=criterion,value=key(r)))
    review = {r["id"]:r for r in inputs["previous_review"]["tables"]["real39"]}
    review_diag = []
    for r in design["review_means"]:
        old = review[r["id"]]
        d = clearance_diagnostics(r["annotation_mean"],r["reference_mean"])
        if r["reference_object_id"] != old["metadata"]["reference_object_id"] or not math.isclose(abs(d["signed_wall_error"]),old["metrics"]["Hmean"],abs_tol=1e-12):
            raise ValueError(("Reviewed mean binding mismatch",r["id"]))
        review_diag.append(dict(id=r["id"],**d,in_development907=r["id"] in diagnostics))
    original_selected = [r["id"] for r in previous["selected_real_cases"]]
    old_selection_keys = {coordinate_key(by_id[rid],geometries[by_id[rid]["object_id"]]) for rid in original_selected}
    return dict(schema="quality_height_conditioning_results_v1",strata=strata,
        records=list(diagnostics.values()),coordinate_groups=[dict(representative=m[0],members=m) for m in grouped.values()],
        selected_cases=[dict(id=rid,reasons=reasons,human_grade=None) for rid,reasons in sorted(selected.items())],
        previous_selected_case_counts=dict(records=len(original_selected),coordinate_groups=len(old_selection_keys)),
        review_mean_diagnostics=review_diag,
        verification=dict(unique_coordinate_scenarios=sum(r["single_evaluated_count"]+len(r["all_bottom_changes"]) for r in representatives),
            unavailable_unique_scenarios=sum(len(r["single_unavailable"])+sum(s["status"]!="available" for s in r["all_bottom_changes"]) for r in representatives),
            maximum_top_unit_ray_change=max(r["max_top_ray_change"] for r in representatives)),
        scope=dict(new_human_labels=0,formal_scores_changed=False,perturbed_scores_computed=False,
                   perturbed_Hcenter_computed=False,perturbed_full_layout_validity_evaluated=False,
                   raw_pairing_changed=False,noise_distribution_estimated=False,holdout_used=False))


def figures(result,output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),constrained_layout=True)
    ids={g["representative"] for g in result["coordinate_groups"]}
    for known,color in ((False,"#aeb8c2"),(True,"#2267a3")):
        rows=[r for r in result["records"] if r["id"] in ids and r["applicability_confirmed"]==known]
        label=f"{'Confirmed' if known else 'Unknown'} applicability (coordinate groups)"
        axes[0].scatter([r["height"]["signed_wall_error"]*100 for r in rows],
                        [r["height"]["signed_clearance_error"]*100 for r in rows],s=14,alpha=.7,color=color,label=label)
        axes[1].scatter([r["min_bottom_margin_px"] for r in rows],
                        [100*abs(r["single_max_mean_change"]["delta_mean_over_reference_height"]) for r in rows],s=14,alpha=.7,color=color,label=label)
    axes[0].plot([-30,30],[-30,30],color="#999999",linestyle="--",linewidth=1)
    t20=next(r for r in result["records"] if r["id"]=="R00397")
    axes[0].annotate("T20",(100*t20["height"]["signed_wall_error"],100*t20["height"]["signed_clearance_error"]),xytext=(6,-12),textcoords="offset points")
    axes[0].set(title="Same mean-height error, different denominators",xlabel="Signed whole-wall error (%)",ylabel="Signed above-camera clearance error (%)")
    axes[1].set(title="Top pixels fixed; one bottom endpoint moved by 1 px",xlabel="Closest bottom endpoint to horizon (px in 512-high ERP)",ylabel="Max absolute mean-height change / reference height (%)")
    for ax in axes:
        ax.legend(fontsize=8);ax.spines["top"].set_visible(False);ax.spines["right"].set_visible(False)
    fig.suptitle("Height interpretation and conditioning | Diagnostics, not calibrated penalties",fontsize=13)
    fig.savefig(output/"conditioning.png",dpi=160)
    plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--study",required=True,type=Path)
    p.add_argument("--figures",action="store_true")
    args=p.parse_args()
    result=run(read_json(args.study/"inputs.json"),read_json(args.study/"results.json"),read_json(args.study/"conditioning_design.json"))
    save_json(args.study/"conditioning.json",result)
    if args.figures:figures(result,args.study)
    print(result["verification"])


if __name__=="__main__":
    main()
