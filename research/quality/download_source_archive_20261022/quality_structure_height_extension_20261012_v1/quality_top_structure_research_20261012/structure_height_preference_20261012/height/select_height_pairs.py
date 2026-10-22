#!/usr/bin/env python3
"""Reproduce descriptive within-image pair searches, never generate labels.

The fixed final questions are in prepare_review_inputs.py. This script retains
all search hits, including repeated or derived geometry, and makes no claim that
the returned number of pairs is an independent sample count.
"""
from pathlib import Path
import itertools
import json
from score_existing import csvread, dump

HERE = Path(__file__).resolve().parent
OUT = HERE / "results"


def main():
    metrics = json.loads((OUT / "development907_candidates.json").read_text())
    by = {r["record_id"]:r for r in metrics}
    profiles = csvread(OUT / "development907_height_profiles.csv")
    groups = {}
    for r in profiles:
        groups.setdefault(r["image_id"], []).append(r)
    matched = []
    traded = []
    for rows in groups.values():
        for a,b in itertools.combinations(rows,2):
            x,y=by[a["record_id"]],by[b["record_id"]]
            di=abs(x["iou_2d"]-y["iou_2d"])
            dd=abs(x["dir"]-y["dir"])
            dm=abs(x["Hmean"]-y["Hmean"])
            dc=abs(x["Hcenter"]-y["Hcenter"])
            if di<.07 and dd<1.5 and dm<.03 and dc>.035:
                matched.append({"a":a["record_id"],"b":b["record_id"],"image":a["image_code"],
                    "explicit":x["applicability_confirmed"] and y["applicability_confirmed"],
                    "dI":di,"dD":dd,"dHm":dm,"dHc":dc,
                    "conditions":[{k:z[k] for k in ["record_id","Hmean","Hcenter","dir","iou_2d","annotation_support_gtmean_10","annotation_max_abs_deviation_from_own_mean_over_gt_mean"]} for z in [a,b]]})
        for a,b in itertools.permutations(rows,2):
            x,y=by[a["record_id"]],by[b["record_id"]]
            if x["Hmean"]<=y["Hmean"]+.03 or y["Hcenter"]<=x["Hcenter"]+.02:
                continue
            di=abs(x["iou_2d"]-y["iou_2d"])
            dd=abs(x["dir"]-y["dir"])
            if di>.07 or dd>1.5:
                continue
            fields=["Hmean","Hcenter","dir","iou_2d","Q_v11","Q_hsplit_top0","Q_dbounded1_hsplit","Q_dbounded1_local05","Q_dbounded1_mean1"]
            traded.append({"image":x["image_code"],"a":x["record_id"],"b":y["record_id"],
                "explicit":x["applicability_confirmed"] and y["applicability_confirmed"],
                "dI":di,"dD":dd,"a_values":{k:x[k] for k in fields},"b_values":{k:y[k] for k in fields}})
    matched.sort(key=lambda r:(not r["explicit"],-r["dHc"]/(.02+r["dI"]+.02*r["dD"]+r["dHm"])))
    traded.sort(key=lambda x:(not x["explicit"],-((x["a_values"]["Hmean"]-x["b_values"]["Hmean"])+(x["b_values"]["Hcenter"]-x["a_values"]["Hcenter"]))/ (.05+x["dI"]+.02*x["dD"])))
    dump(OUT / "height_same_image_candidate_search.json", {"selection_only_no_new_human_labels":True,
        "filters":{"floor_iou_diff_max":.07,"D_diff_deg_max":1.5,"Hmean_diff_max":.03,"Hcenter_diff_min":.035},"pairs":matched})
    dump(OUT / "global_vs_local_same_image_candidates.json", {"filters":{"dHmean_min":.03,"dHcenter_min":.02,"iou_diff_max":.07,"D_diff_max_deg":1.5},
        "selection_only_no_new_labels":True,"pairs":traded})
    print(json.dumps({"local_difference_pairs":len(matched),"explicit_local_pairs":sum(r["explicit"] for r in matched),
        "global_local_tradeoff_pairs":len(traded),"explicit_tradeoff_pairs":sum(r["explicit"] for r in traded),"independence_not_asserted":True}))


if __name__=="__main__":
    main()
