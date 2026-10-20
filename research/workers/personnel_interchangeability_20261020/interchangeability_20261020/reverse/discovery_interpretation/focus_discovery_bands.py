#!/usr/bin/env python3
"""Discovery-only explicit m/n review, preserving exact A/B/C comparisons.

No new class fitting, scoring, native replay, or assessment outcome access.
The n=11..17,m=2 window was requested before this focused outcome read.
Other adjacent n bands are counterchecks, not an optimized cutoff search.
"""
from pathlib import Path
import importlib.util
import json
import sys

import pandas as pd

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import analyze_reverse_discovery as rev


def load():
    discovery=rev.ROOT/"interchangeability_20261020/discovery"
    receipt=json.load(open(HERE/"REVERSE_DISCOVERY_INTERPRETATION_RECEIPT.json"))
    spec=importlib.util.spec_from_file_location("shared_focused_summarizer",rev.ROOT/"interchangeability_20261020/forward/discovery_interpretation/analyze_discovery.py")
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    needed=set(helper.KEY_METRICS)|set(helper.SUPPORT_METRICS)|{
        "event_id","phase","method_id","domain","context_id","pool_id","building","image","difficulty","n","m",
        "n_band","replacement_fraction","outgoing_class","incoming_class","background_policy",
        "A_team_key","B_team_key","C_team_key","A_B8L2","B_B8L2","C_B8L2",
        "within_B8L2_change","cross_B8L2_change","within_bad_Q_gt5","cross_bad_Q_gt5",
        "within_source_block_seconds","cross_source_block_seconds","within_target_block_seconds","cross_target_block_seconds",
        "cross_over_within_source_block_time","net_geometry_noQ_main",
        "within_mean_height_prism_pair_iou","cross_mean_height_prism_pair_iou",
        "within_wall_coverage_symmetric_min_main","cross_wall_coverage_symmetric_min_main",
        "within_true_corner_F1_main","cross_true_corner_F1_main","within_true_corner_count_difference","cross_true_corner_count_difference",
        "within_different_original_nodes_shape_main_passes","cross_different_original_nodes_shape_main_passes",
    }
    member=pd.read_csv(HERE/"event_member_index.csv.gz")
    frame=pd.concat([pd.read_csv(discovery/"reverse_metrics/event_parts"/(pid+".csv.gz"),usecols=lambda c:c in needed)
        for pid in sorted(member.pool_id.unique())],ignore_index=True)
    assert frame.phase.eq("discovery").all() and set(frame.event_id)==set(member.event_id)
    frame=frame.merge(member[["event_id"]+[c for c in member if c.endswith("_mask")]],on="event_id",validate="one_to_one")
    split=json.load(open(rev.ROOT/"analysis/composition/SPLIT.json"))
    assert set(frame.building)<=set(split["discovery_buildings"])
    return rev.prepare(frame),helper,receipt


def main():
    frame,helper,receipt=load()
    metrics=helper.KEY_METRICS+[
        "within_prism_distance","cross_prism_distance","excess_prism_distance",
        "within_wall_coverage_symmetric_min_main","cross_wall_coverage_symmetric_min_main",
        "within_true_corner_F1_main","cross_true_corner_F1_main",
        "within_different_original_nodes_shape_main_passes","cross_different_original_nodes_shape_main_passes"]
    bands=[("m2_n11_17",(frame.m==2)&frame.n.between(11,17)),
           ("m2_n3_10",(frame.m==2)&frame.n.between(3,10)),
           ("m2_n18_33",(frame.m==2)&frame.n.between(18,33)),
           ("mge3_n11_17",(frame.m>=3)&frame.n.between(11,17))]
    outputs={level:[] for level in ["per_image","per_building","aggregate"]}
    for name,mask in bands:
        for subset,data in helper.eligible_views(frame[mask]):
            if subset=="single_person_supplement_nge3" or data.empty:continue
            data=data.copy();data["focused_band"]=name;data["subset"]=subset
            keys=["focused_band","subset","method_id","domain","context_id","outgoing_class","incoming_class"]
            tables=helper.summarize(data,keys,metrics=metrics)
            for level,table in zip(outputs,tables):outputs[level].append(table)
    for level,pieces in outputs.items():rev.write_csv(HERE/("focused_bands_"+level+".csv.gz"),pd.concat(pieces,ignore_index=True))
    rev.write_json(HERE/"FOCUSED_BANDS_RECEIPT.json",{
        "phase":"discovery","source_interpretation_receipt_sha256":rev.sha(HERE/"REVERSE_DISCOVERY_INTERPRETATION_RECEIPT.json"),
        "script_sha256":rev.sha(Path(__file__)),"bands":[x[0] for x in bands],
        "selection_note":"n11..17,m2 explicitly requested before focused read; adjacent fixed bands retained as counterchecks",
        "aggregation":"events equally within image; image equally within building; building equally across support",
        "assessment_outcomes_read":False})


if __name__=="__main__":main()
