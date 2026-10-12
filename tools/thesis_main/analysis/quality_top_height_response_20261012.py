"""固定响应形状机制研究；冻结开发输入，保留资格和域外状态，不拟合或发布总分。"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from zipfile import ZipFile

if __package__:
    from .quality_review_constraints_20261012 import METRICS, PANELS, components, read_json, save_json
else:
    from quality_review_constraints_20261012 import METRICS, PANELS, components, read_json, save_json


PARITY_NAMES = {
    "relative2": "Q_dbounded1_hsplit", "relative2_weakTop": "Q_dbounded1_hsplit_weakTop",
    "relative2_Fguard": "Q_dbounded1_Fguard", "relative2_mean1": "Q_dbounded1_mean1",
    "log2": "Q_dbounded1_hsplit_logMean",
}


def response_terms(m, c):
    config = dict(direction_mode="bounded_denominator", direction_cap=1, direction_scale_deg=5,
                  flat_mode="old_numerator" if c["flat"] else "none", height_mean_scale=c["global_scale"],
                  height_center_scale=.25, height_combine="sum", top_weight=c["top_weight"], top_combine="sum")
    if c["representation"] == "log":
        config["height_mean_representation"] = "absolute_log_ratio"
        error = abs(math.log(m["height_mean_ratio"]))
    elif c["representation"] == "relative":
        error = m["Hmean"]
    else:
        raise ValueError(c["representation"])
    out = components(m, config)
    out["global_height_loss"] = (error / c["global_scale"]) ** c["power"]
    loss = out["global_height_loss"] + out["local_height_loss"] + out["top_boundary_loss"]
    base = 1 + m["S_bottom_deg"] ** 2 / 32 + out["direction_denominator"]
    out["combined_top_height_loss"] = loss
    out["score"] = 100 * m["iou_2d"] * (1 - out["flat_numerator_fraction"]) / (base + loss)
    out["top_only_penalty"] = 1 - (1 - out["flat_numerator_fraction"]) / (1 + loss)
    out["actual_top_height_score_drop"] = out["score_without_top_height"] - out["score"]
    out["actual_top_height_relative_drop"] = 1 - out["score"] / out["score_without_top_height"] if out["score_without_top_height"] else None
    out["top_boundary_loss_share"] = out["top_boundary_loss"] / loss if loss else 0.0
    return out


def profile_moments(g):
    bottom, top = g["bottom3d"], g["top3d"]
    heights = [t[1] - b[1] for b, t in zip(bottom, top)]
    lengths = [math.hypot(b[0] - a[0], b[2] - a[2]) for a, b in zip(bottom, bottom[1:] + bottom[:1])]
    perimeter = math.fsum(lengths)
    mean = math.fsum(w * (a + b) / 2 for w, a, b in zip(lengths, heights, heights[1:] + heights[:1])) / perimeter
    d = [h - mean for h in heights]
    variance = math.fsum(w * (a*a + a*b + b*b) / 3 for w, a, b in zip(lengths, d, d[1:] + d[:1])) / perimeter
    return dict(mean=mean, std=math.sqrt(variance), perimeter=perimeter, heights=heights,
                lengths=lengths, min_height=min(heights), max_height=max(heights))


def analytic_case(ratio, local_rms):
    bottom = [[-1, -1, -1], [1, -1, -1], [1, -1, 1], [-1, -1, 1]]
    amplitude = math.sqrt(3) * 2.4 * local_rms
    top = [[b[0], 2.4 * ratio - 1 + amplitude * (-1)**i, b[2]] for i, b in enumerate(bottom)]
    return {
        "id": f"analytic_r{ratio:g}_local{local_rms:g}", "annotation": dict(bottom3d=bottom, top3d=top),
        "reference": dict(bottom3d=bottom, top3d=[[b[0], 1.4, b[2]] for b in bottom]),
        "camera_inside_height_assumption": min(t[1] for t in top) > 0,
        "human_grade": None, "angular_terms_evaluated": False,
        "metrics": dict(iou_2d=1., dir=0., flat=0., Hmean=abs(ratio-1), Hcenter=local_rms,
                        S_top_deg=0., S_bottom_deg=0., height_mean_ratio=ratio),
    }


def validate_development_gates(rows, gates):
    by_id = {g["record_id"]: g for g in gates}
    ids = [r["record_id"] for r in rows]
    if len(set(ids)) != len(ids) or set(ids) != set(by_id):
        raise ValueError("Development input and gate IDs must agree, without duplicates")
    if any(not by_id[i]["new_descriptive_development_allowed"] or by_id[i]["explicit_exposure_barriers"] for i in ids):
        raise ValueError("Exposure barrier or development exclusion cannot be discarded")


def distribution(values):
    ordered = sorted(values)
    def quantile(p):
        x = p * (len(ordered)-1)
        i = int(x)
        return ordered[i] + (ordered[min(i+1, len(ordered)-1)] - ordered[i]) * (x-i)
    return {"min": ordered[0], "median": quantile(.5), "p90": quantile(.9), "p95": quantile(.95), "max": ordered[-1]}


def summarize_changes(rows, before, after):
    delta = [r["scores"][after] - r["scores"][before] for r in rows]
    return dict(records=len(rows), images=len({r["image_id"] for r in rows}),
                buildings=len({r["building_id"] for r in rows}), delta=distribution(delta),
                **{f"{direction}_ge_{t}": sum(sign*d >= t for d in delta)
                   for direction, sign in (("increase", 1), ("decrease", -1)) for t in (2, 5, 10)},
                quality_improvement_claimed=False)


def import_inputs(extension, prior_zip, review_evidence):
    full = read_json(extension / "height/results/development907_candidates.json")
    gates = read_json(extension / "evidence/results/development_907_filter.json")
    validate_development_gates(full, gates)
    with (extension / "height/results/development907_height_profiles.csv").open(encoding="utf-8-sig", newline="") as f:
        profiles = {r["record_id"]: r for r in csv.DictReader(f)}
    fields = ("annotation_own_height_std_over_gt_mean", "reference_own_height_std_over_gt_mean",
              "annotation_support_gtmean_10", "annotation_support_gtmean_20",
              "annotation_max_abs_deviation_from_own_mean_over_gt_mean")
    rows = []
    gate_by_id = {g["record_id"]: g for g in gates}
    for r in full:
        for key in ("object_id", "image_id", "reference_object_id", "building_id"):
            if r[key] != gate_by_id[r["record_id"]][key] or r[key] != profiles[r["record_id"]][key]:
                raise ValueError(("Source identity mismatch", r["record_id"], key))
        rows.append({"id": r["record_id"], **{k: r[k] for k in (
            "image_id", "image_code", "worker_id", "building_id", "applicability_confirmed", "object_id", "reference_object_id",
            "height_center_AG_distinct_tied_height_fraction", "height_center_GA_distinct_tied_height_fraction")},
            "metrics": {k: r[k] for k in (*METRICS, "height_mean_ratio")},
            "profile": {k: float(profiles[r["record_id"]][k]) for k in fields},
            "expected_scores": {n: r[n] for n in PARITY_NAMES.values()}})
    with ZipFile(prior_zip) as z:
        member = next(n for n in z.namelist() if n.endswith("/inputs/current_geometry_compact.json"))
        geometries = json.loads(z.read(member))["geometries"]
    ids = {r[k] for r in rows for k in ("object_id", "reference_object_id")}
    geometries = {i: {k: geometries[i][k] for k in ("top3d", "bottom3d")} for i in sorted(ids)}
    old = read_json(review_evidence)
    return dict(schema="quality_top_height_response_inputs_v1", rows=rows, gates=gates, geometries=geometries,
                previous_review=old, provenance=dict(extension_root=str(extension), prior_zip=str(prior_zip),
                    geometry_member=member, review_evidence=str(review_evidence),
                    note="冻结外部研究快照，仅复算机制；不替代当前正式输入loader，不读取留出几何"))


def evaluate(inputs, protocol):
    configs = protocol["candidates"]
    rows = inputs["rows"]
    validate_development_gates([dict(record_id=r["id"]) for r in rows], inputs["gates"])
    expected_scales = dict(global_scale=.5, local_scale=.25)
    assert protocol["inherited_scales"]["global"] == expected_scales["global_scale"]
    assert protocol["inherited_scales"]["local"] == expected_scales["local_scale"]
    all_errors, geometry_errors = [], []
    scored = []
    for r in rows:
        terms = {c["name"]: response_terms(r["metrics"], c) for c in configs}
        for name, old_name in PARITY_NAMES.items():
            all_errors.append(abs(terms[name]["score"] - r["expected_scores"][old_name]))
        a, g = (profile_moments(inputs["geometries"][r[k]]) for k in ("object_id", "reference_object_id"))
        errors = {"height_ratio": abs(a["mean"]/g["mean"] - r["metrics"]["height_mean_ratio"]),
                  "Hmean": abs(abs(a["mean"]/g["mean"]-1) - r["metrics"]["Hmean"]),
                  "own_std": abs(a["std"]/g["mean"] - r["profile"]["annotation_own_height_std_over_gt_mean"]),
                  "reference_std": abs(g["std"]/g["mean"] - r["profile"]["reference_own_height_std_over_gt_mean"])}
        if max(errors.values()) > 1e-6:
            raise ValueError((r["id"], errors))
        geometry_errors.append(errors)
        scored.append({k: r[k] for k in ("id", "image_id", "image_code", "building_id", "applicability_confirmed")} | {
            "scores": {n: t["score"] for n,t in terms.items()},
            "top_only_penalties": {n: t["top_only_penalty"] for n,t in terms.items()},
            "weak_top_share_after_fourth_power": terms["relative4_weakTop"]["top_boundary_loss_share"]})
    if max(all_errors) > 1e-9:
        raise ValueError("Saved development scalar mismatch")
    scored_map = {r["id"]: r for r in scored}
    old = inputs["previous_review"]
    reviewed = {r["id"]: r for r in old["tables"]["real39"]}
    for r in old["tables"]["targeted8"]:
        reviewed.setdefault(r["id"], r)
    selected, summaries = {}, {}
    comparisons = (("relative2", "relative4"), ("log2", "log4"), ("relative4", "log4"),
                   ("relative4", "relative4_weakTop"), ("relative4", "relative4_Fguard"), ("relative2", "relative2_mean1"))
    for scope in ("all907", "confirmed", "unknown"):
        subset = [r for r in rows if scope == "all907" or r["applicability_confirmed"] == (scope == "confirmed")]
        sr = [scored_map[r["id"]] for r in subset]
        summaries[scope] = {
            "records": len(subset), "images": len({r["image_id"] for r in subset}), "buildings": len({r["building_id"] for r in subset}),
            "Hmean": distribution([r["metrics"]["Hmean"] for r in subset]),
            "height_mean_ratio": distribution([r["metrics"]["height_mean_ratio"] for r in subset]),
            "Hcenter": distribution([r["metrics"]["Hcenter"] for r in subset]),
            "reference_std": distribution([r["profile"]["reference_own_height_std_over_gt_mean"] for r in subset]),
            "local_representation_gap": distribution([abs(r["metrics"]["Hcenter"] - r["profile"]["annotation_own_height_std_over_gt_mean"]) for r in subset]),
            "relative_global_above_crossover": sum(r["metrics"]["Hmean"] > .5 for r in subset),
            "log_global_above_crossover": sum(abs(math.log(r["metrics"]["height_mean_ratio"])) > .5 for r in subset),
            "changes": {a+"_to_"+b: summarize_changes(sr,a,b) for a,b in comparisons},
            "weak_top_share_after_fourth_power": distribution([r["weak_top_share_after_fourth_power"] for r in sr]),
            "weak_top_loss_dominates_height_loss_after_fourth_power": sum(r["weak_top_share_after_fourth_power"] > .5 for r in sr),
        }
        if scope == "all907":
            continue
        selectors = {
            "Hmean": lambda r: r["metrics"]["Hmean"], "Hcenter": lambda r: r["metrics"]["Hcenter"],
            "weak_top_increment": lambda r: scored_map[r["id"]]["scores"]["relative4"] - scored_map[r["id"]]["scores"]["relative4_weakTop"],
            "F_increment": lambda r: scored_map[r["id"]]["scores"]["relative4"] - scored_map[r["id"]]["scores"]["relative4_Fguard"],
            "local_representation_gap": lambda r: abs(r["metrics"]["Hcenter"] - r["profile"]["annotation_own_height_std_over_gt_mean"]),
        }
        for name, key in selectors.items():
            for r in sorted((r for r in subset if r["id"] not in reviewed), key=lambda r: (-key(r), r["id"]))[:3]:
                selected.setdefault(r["id"], []).append(dict(stratum=scope, criterion=name, value=key(r)))
    cases = []
    for r in rows:
        if r["id"] in selected:
            cases.append(dict(id=r["id"], reasons=selected[r["id"]],
                              terms={c["name"]: response_terms(r["metrics"],c) for c in configs},
                              annotation_profile=profile_moments(inputs["geometries"][r["object_id"]]),
                              reference_profile=profile_moments(inputs["geometries"][r["reference_object_id"]]),
                              human_grade=None, semantic_acceptance_newly_confirmed=False))
    controls, skipped = [], []
    for table in ("prior_height71", "matched65", "structure43"):
        for r in old["tables"][table]:
            if r["status"] != "available":
                controls.append(dict(table=table, **r))
                continue
            terms = {}
            for c in configs:
                if c["representation"] == "log" and "height_mean_ratio" not in r["metrics"]:
                    skipped.append([table,r["id"],c["name"],"missing_actual_ratio"])
                    continue
                terms[c["name"]] = response_terms(r["metrics"],c)
            controls.append(dict(table=table, id=r["id"], status=r["status"], metadata=r["metadata"], terms=terms, human_grade=None))
    analytic = []
    for ratio in protocol["analytic_controls"]["global_ratios"]:
        for local in protocol["analytic_controls"]["local_rms"]:
            case = analytic_case(ratio, local)
            case["terms"] = {c["name"]: response_terms(case["metrics"],c) for c in configs if not c["top_weight"] and not c["flat"]}
            analytic.append(case)
    reviewed_terms = {}
    development_by_id = {r["id"]: r for r in rows}
    for rid, row in reviewed.items():
        metrics = dict(row["metrics"])
        if rid in development_by_id:
            dev = development_by_id[rid]["metrics"]
            if not all(math.isclose(metrics[k],dev[k],abs_tol=1e-9) for k in METRICS):
                raise ValueError(("Reviewed/development mismatch",rid))
            metrics["height_mean_ratio"] = dev["height_mean_ratio"]
        reviewed_terms[rid] = {}
        for c in configs:
            if c["representation"] == "log" and "height_mean_ratio" not in metrics:
                skipped.append(["reviewed",rid,c["name"],"missing_actual_ratio"])
            else:
                reviewed_terms[rid][c["name"]] = response_terms(metrics,c)
    pairs = []
    for panel, (a,b,interpretation) in PANELS.items():
        pairs.append(dict(panel=panel, interpretation=interpretation, numeric_tolerance=None,
                          scores={n: dict(a=t["score"],b=reviewed_terms[b][n]["score"],difference=t["score"]-reviewed_terms[b][n]["score"])
                                  for n,t in reviewed_terms[a].items() if n in reviewed_terms[b]}))
    overlap = sorted(set(reviewed) & set(scored_map))
    outside_review = [r for r in scored if r["id"] not in reviewed]
    return dict(schema="quality_top_height_response_results_v1", status="mechanism_probe_not_validated_score",
                development=scored, strata=summaries, selected_real_cases=cases, inherited_controls=controls,
                analytic_controls=analytic, reviewed_terms=reviewed_terms, overall_pairs=pairs, skipped=skipped,
                reviewed_development_overlap_ids=overlap,
                excluding_reviewed_records_changes={a+"_to_"+b: summarize_changes(outside_review,a,b) for a,b in comparisons},
                verification=dict(saved_development_scalar_cells=len(all_errors), max_scalar_delta=max(all_errors),
                    geometry_records=len(geometry_errors), geometry_max_deltas={k:max(e[k] for e in geometry_errors) for k in geometry_errors[0]}),
                scope=dict(fitted_parameters=False, model_shape_is_a_choice=True, new_human_labels=0,
                           formal_scores_changed=False, independent_human_validation=False, holdout_used=False))


def write_figures(inputs, protocol, result, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    configs = {c["name"]: c for c in protocol["candidates"]}
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 2, figsize=(12, 8.5), constrained_layout=True)
    ratios = [.42 + i * 2.08/400 for i in range(401)]
    for name in ("relative2", "relative4", "log4", "relative2_mean1"):
        axes[0,0].plot(ratios, [response_terms(analytic_case(r,0)["metrics"],configs[name])["score"] for r in ratios], label=name)
    actual_ratios = [r["metrics"]["height_mean_ratio"] for r in inputs["rows"]]
    axes[0,0].axvspan(min(actual_ratios), max(actual_ratios), color="#bbbbbb", alpha=.2, label="907 observed range")
    axes[0,0].set(title="A. Pure global height; identical floor", xlabel="Annotation / reference mean height", ylabel="Diagnostic score", ylim=(0,102))
    axes[0,0].legend(fontsize=8)
    local = [i/1000 for i in range(251)]
    for name,ratio in (("relative2",1), ("relative4",1), ("relative2",1.2), ("relative4",1.2)):
        axes[0,1].plot(local,[response_terms(analytic_case(ratio,h)["metrics"],configs[name])["score"] for h in local],
                       label=f"{name}; mean ratio {ratio}", linestyle="--" if name=="relative4" else "-")
    axes[0,1].set(title="B. Local penalty retained (pure-local curves overlap)", xlabel="Centered local RMS / reference height", ylabel="Diagnostic score", ylim=(35,102))
    axes[0,1].legend(fontsize=8)
    controls = {r["id"]:r for r in result["inherited_controls"]}
    scales = [.5, 2, 10]
    for ratio in (.8,1.2):
        for name in ("relative4", "relative4_weakTop"):
            values = [controls[f"uniform_scale{s:g}_ratio{ratio:g}"]["terms"][name]["score"] for s in scales]
            axes[1,0].plot(scales,values,marker="o",label=f"{name}; ratio {ratio}",linestyle="--" if ratio==1.2 else "-")
    axes[1,0].set(title="C. Same 20% height error, different horizontal scale", xlabel="Horizontal scale / fixed camera height", ylabel="Diagnostic score", ylim=(78,100), xscale="log")
    axes[1,0].legend(fontsize=8)
    by_id = {r["id"]:r for r in inputs["rows"]}
    for known,color in ((False,"#b4bac1"),(True,"#2465a2")):
        subset = [r for r in result["development"] if r["applicability_confirmed"] == known]
        axes[1,1].scatter([by_id[r["id"]]["metrics"]["Hmean"] for r in subset],
                        [r["scores"]["relative4"]-r["scores"]["relative2"] for r in subset],s=13,alpha=.7,
                        color=color,label=f"{'Confirmed applicability' if known else 'Unknown applicability'} (n={len(subset)})")
    axes[1,1].axvline(.5,color="#a23b3b",linestyle="--",label="Inherited crossover (not a pass threshold)")
    axes[1,1].set(title="D. Real development data never reach stronger branch", xlabel="Absolute relative mean-height error", ylabel="Score change: relative4 - relative2", xlim=(-.01,.52))
    axes[1,1].legend(fontsize=8)
    fig.suptitle("Top + height response mechanisms | Fixed probes, no fitted weights or new human grades",fontsize=13)
    fig.savefig(output / "response_mechanisms.png",dpi=160)
    plt.close(fig)

    # These four cases illustrate distinct predeclared selection reasons; the full 27-case set stays in JSON.
    display = ["R00935", "R02177", "R01540", "R02297"]
    selected = {r["id"]:r for r in result["selected_real_cases"]}
    fig, axes = plt.subplots(4,2,figsize=(11,13),constrained_layout=True)
    for axrow,rid in zip(axes,display):
        r = by_id[rid]
        case = selected[rid]
        for who,color,style in (("reference","#707070","--"),("annotation","#2465a2","-")):
            g = inputs["geometries"][r[who+"_object_id"] if who=="reference" else r["object_id"]]
            b = g["bottom3d"] + g["bottom3d"][:1]
            axrow[0].plot([p[0] for p in b],[p[2] for p in b],color=color,linestyle=style,marker=".",label=who)
            p = case[who+"_profile"]
            x = [0.]
            for length in p["lengths"]:
                x.append(x[-1]+length/p["perimeter"])
            axrow[1].plot(x,[(h/case["reference_profile"]["mean"]) for h in p["heights"]+p["heights"][:1]],color=color,linestyle=style,label=who)
        axrow[0].scatter([0],[0],marker="+",color="#a23b3b",label="camera")
        axrow[0].set_aspect("equal",adjustable="datalim")
        axrow[0].set(title=f"{rid} | {r['image_code']} | {'confirmed' if r['applicability_confirmed'] else 'unknown'} applicability",xlabel="Floor x / camera height",ylabel="Floor z / camera height")
        m = r["metrics"]
        axrow[1].set(title=f"Mean ratio {m['height_mean_ratio']:.3f}; Hcenter {m['Hcenter']:.3f}; St {m['S_top_deg']:.2f} deg",xlabel="Each ring's own perimeter fraction (starts NOT aligned)",ylabel="Wall height / reference mean")
        axrow[1].axhline(1,color="#aaaaaa",linewidth=.6)
        axrow[0].legend(fontsize=8); axrow[1].legend(fontsize=8)
    fig.suptitle("Existing processed geometry diagnostics | No new semantic or image quality judgment",fontsize=13)
    fig.savefig(output / "real_case_geometry.png",dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--extension-root", type=Path)
    parser.add_argument("--prior-zip", type=Path)
    parser.add_argument("--review-evidence", type=Path, default=Path("research/quality_review_constraints_20261012/evidence.json"))
    parser.add_argument("--figures", action="store_true")
    args = parser.parse_args()
    protocol = read_json(args.output / "protocol.json")
    if args.extension_root:
        if not args.prior_zip:
            parser.error("import requires prior-zip")
        inputs = import_inputs(args.extension_root,args.prior_zip,args.review_evidence)
        save_json(args.output / "inputs.json",inputs)
    else:
        inputs = read_json(args.output / "inputs.json")
    result = evaluate(inputs,protocol)
    save_json(args.output / "results.json",result)
    if args.figures:
        write_figures(inputs,protocol,result,args.output)
    print(json.dumps(dict(verification=result["verification"], selected_real_cases=len(result["selected_real_cases"]),
                         analytic_controls=len(result["analytic_controls"]), skipped=len(result["skipped"])),ensure_ascii=False))


if __name__ == "__main__":
    main()
