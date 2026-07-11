"""M-Anchor.4.1.2 visible-range, audit-only footprint sensitivity review."""
from __future__ import annotations

import copy
import itertools
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from tools.paper_a_manhattan import run_m_anchor_4_1_1_staged_micro_compensation_probe as m
from tools.paper_a_manhattan.run_local_3d_projection_review import run_local_review
from tools.paper_a_manhattan.run_m_anchor_1_3741 import ANCHOR_SIDECAR_PATH, SAFETY, _anchor_constraints, _load_anchor_sidecar, _sha, _write_text_lf
from tools.paper_a_manhattan.run_m_anchor_3_footprint_solver import M1_AUDIT_PATH, M2_VERDICT_PATH

CONSTRAINTS_PATH = Path("analysis_results/paper_a_manhattan/m_anchor/task218_ann3741_m_anchor_4/m_anchor_4_1_2_visible_range_constraints.json")
OUT_DIR = Path("analysis_results/paper_a_manhattan/m_anchor/task218_ann3741_m_anchor_4_1_2")
REVIEW_OUT_DIR = Path("analysis_results/paper_a_manhattan/hypothesis_local_review/task218_ann3741_m_anchor_4_1_2")


def _validate(doc: Mapping[str, Any]) -> None:
    if doc.get("schema_version") != "m_anchor_4_1_2_visible_range_constraints_v1": raise ValueError("unsupported M4.1.2 sidecar")
    if doc.get("case_name") != "task218_ann3741" or doc.get("source_annotation_id") != 3741 or doc.get("coordinate_space") != "ls_percent": raise ValueError("sidecar identity mismatch")
    if doc.get("allowed_variables") != ["x", "bottom_y"] or set(doc.get("locked_source_pair_ids", [])) != {6, 11, 12}: raise ValueError("sidecar permissions mismatch")
    if set(doc.get("stage_candidate_deltas", {})) != {"A", "B", "C", "D"}: raise ValueError("missing stage")
    caps = {"A": .15, "B": .30, "C": .50, "D": 1.0}
    previous: set[float] = set()
    for stage, cap in caps.items():
        row = doc["stage_candidate_deltas"][stage]; values = {float(v) for v in row["candidate_deltas"]}
        if float(row["min_delta"]) > float(row["max_delta"]) or 0.0 not in values or not previous <= values or any(abs(v) > cap or not float(row["min_delta"]) <= v <= float(row["max_delta"]) for v in values): raise ValueError("invalid staged delta contract")
        if any(-v not in values for v in values): raise ValueError("delta symmetry mismatch")
        previous = values
    if doc.get("extended_sensitivity_cap") != 1.0 or doc.get("stage_d_role") != "extended_visual_sensitivity_only" or doc.get("stage_d_requires_prior_failure") is not True: raise ValueError("missing Stage D safety contract")
    budget = doc["search_config"]["stage_evaluation_budget"]
    if sum(int(v) for v in budget.values()) > int(doc["search_config"]["max_raw_evaluations"]) or min(int(doc["search_config"][k]) for k in ("core_beam", "one_action_beam")) < 3: raise ValueError("insufficient search budget")


def _range(doc: Mapping[str, Any], stage: str, sid: int, axis: str, baseline: Mapping[int, Mapping[str, Any]], anchors: Sequence[Mapping[str, Any]]) -> tuple[float, float, list[str]]:
    cap = float(doc["stage_candidate_deltas"][stage]["max_delta"]); lo, hi = -cap, cap
    direction = doc["pair_axis_ranges"].get(f"{sid}:{axis}", {}).get("direction")
    if direction == "left": hi = 0.0
    if direction == "right": lo = 0.0
    limits = []
    endpoints = {"top", "bottom"} if axis == "x" else {"bottom"}
    for a in anchors:
        if int(a["source_pair_id"]) != sid or a["endpoint"] not in endpoints or a["axis"] != ("x" if axis == "x" else "y") or not a.get("hard_fail_on_violation"): continue
        endpoint = a["endpoint"]; current = float(baseline[sid][endpoint]["x" if axis == "x" else "y"]); anchor = float(a["anchor_value"]); tol = float(a["tolerance"])
        lo, hi = max(lo, anchor - tol - current), min(hi, anchor + tol - current); limits.append(a["constraint_id"])
    if lo > hi: raise ValueError("empty hard-anchor feasible range")
    return lo, hi, limits


def _candidate(index: int, stage: str, doc: Mapping[str, Any], core: Mapping[int, Mapping[str, float]], actions: Sequence[tuple[int, str, float]], before: Sequence[Mapping[str, Any]], anchors: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    cap = float(doc["stage_candidate_deltas"][stage]["max_delta"])
    # Reuse the established geometry implementation; D only lifts its old 0.5 audit cap.
    row = m._candidate(index, "C", cap, core, actions, before, anchors)
    row["candidate_id"] = f"m_anchor_4_1_2_{stage.lower()}_{index:04d}"; row["search_stage"] = stage
    ranges = {f"{sid}:{axis}": _range(doc, stage, sid, axis, m._by_source(before), anchors) for sid, axis in [(4,"x"),(9,"x"),(10,"x")]+[(sid,a) for sid in (1,2,3,5,7,8) for a in ("x","bottom_y")]}
    values = {float(v) for v in doc["stage_candidate_deltas"][stage]["candidate_deltas"]}
    pair_ok = all(key in ranges and ranges[key][0]-1e-12 <= value <= ranges[key][1]+1e-12 and value in values for sid, vals in m._add_actions(core, actions).items() for axis, value in vals.items() if abs(value)>1e-12 for key in [f"{sid}:{axis}"])
    row.update(sensitivity_only=stage == "D", final_refinement_eligible=stage != "D", requires_explicit_human_visual_verdict=stage == "D", direct_ls_trial_allowed=False, m_anchor_4_2_input_eligible=False)
    row["hard_gate"].update({"pair_axis_range_satisfied": pair_ok, "hard_anchor_satisfied": not row["anchor_audit"]["hard_violations"], "candidate_delta_belongs_to_sidecar_values": pair_ok, "changed_pair_axis_is_authorized": pair_ok, "maximum_absolute_delta_le_stage_cap": row["maximum_absolute_delta"] <= cap+1e-12, "stage_d_sensitivity_flag_present": stage != "D" or row["sensitivity_only"], "stage_d_not_final_refinement": stage != "D" or not row["final_refinement_eligible"], "stage_d_does_not_override_hard_anchor": stage != "D" or not row["anchor_audit"]["hard_violations"]})
    if stage == "D": row["hard_gate"]["maximum_absolute_delta_le_0_5"] = True
    row["hard_gate_passed"] = all(row["hard_gate"].values()); row["hard_gate_failure_reasons"] = [k for k,v in row["hard_gate"].items() if not v]
    improved = row["hard_gate_passed"] and row["local_floor_heading_residual_max_deg"] <= row["local_floor_heading_residual_max_before_deg"]+.05 and (row["local_floor_heading_residual_sum_before_deg"]-row["local_floor_heading_residual_sum_deg"] >= .05 or row["floor_heading_residual_sum_before_deg"]-row["floor_heading_residual_sum_deg"] >= .05)
    local_gain = row["local_floor_heading_residual_sum_before_deg"]-row["local_floor_heading_residual_sum_deg"]
    global_gain = row["floor_heading_residual_sum_before_deg"]-row["floor_heading_residual_sum_deg"]
    row["candidate_class"] = "review_available_geometry_improved" if improved else ("rejected_hard_gate" if not row["hard_gate_passed"] else ("neutral_geometry_tradeoff" if max(local_gain, global_gain) >= .05 else "diagnostic_human_direction_only"))
    return row


def _stage(doc, stage, before, anchors, start):
    vals = [abs(float(v)) for v in doc["stage_candidate_deltas"][stage]["candidate_deltas"] if float(v)>0]
    ranges = {sid:_range(doc,stage,sid,"x",m._by_source(before),anchors) for sid in (4,9,10)}
    cores=[{4:{"x":-a,"bottom_y":0},9:{"x":-b,"bottom_y":0},10:{"x":c,"bottom_y":0}} for a,b,c in itertools.product(vals,repeat=3) if ranges[4][0]<=-a<=ranges[4][1] and ranges[9][0]<=-b<=ranges[9][1] and ranges[10][0]<=c<=ranges[10][1]]
    actions=[(sid,axis,float(v)) for sid in (1,2,3,5,7,8) for axis in ("x","bottom_y") for v in doc["stage_candidate_deltas"][stage]["candidate_deltas"] if v]
    cfg=doc["search_config"]; budget=int(cfg["stage_evaluation_budget"][stage]); out=[_candidate(start+i,stage,doc,c,(),before,anchors) for i,c in enumerate(cores)]
    beam=sorted((r for r in out if r["hard_gate_passed"]),key=m._beam_key)[:int(cfg["core_beam"])]
    for r in beam:
        core={int(k):v for k,v in r["directional_core"].items()}
        out.extend(_candidate(start+len(out),stage,doc,core,(a,),before,anchors) for a in actions)
    one=sorted((r for r in out if r["hard_gate_passed"] and len(r["micro_actions"])==1),key=m._beam_key)[:int(cfg["one_action_beam"])]
    for r in one:
        core={int(k):v for k,v in r["directional_core"].items()}; first=r["micro_actions"][0]
        pool=sorted((q for q in out if q["directional_core"]==r["directional_core"] and len(q["micro_actions"])==1 and (q["micro_actions"][0]["source_pair_id"],q["micro_actions"][0]["axis"]) != (first["source_pair_id"],first["axis"])),key=m._beam_key)
        for q in pool[:10]: out.append(_candidate(start+len(out),stage,doc,core,((first["source_pair_id"],first["axis"],first["delta"]),(q["micro_actions"][0]["source_pair_id"],q["micro_actions"][0]["axis"],q["micro_actions"][0]["delta"])),before,anchors))
    if len(out)>budget: raise ValueError("stage budget exceeded")
    return out,{"core_count":len(cores),"action_count":len(actions),"configured_core_beam":int(cfg["core_beam"]),"effective_core_beam":len(beam),"configured_one_action_beam":int(cfg["one_action_beam"]),"effective_one_action_beam":len(one),"raw_count":len(out),"pruning_count":len(cores)-len(beam),"budget_remaining":budget-len(out),"beam_reduction_reason":None if len(beam)>=3 and len(one)>=3 else "fail_closed"}


def run(out_dir: Path=OUT_DIR, review_out_dir: Path=REVIEW_OUT_DIR, constraints_path: Path=CONSTRAINTS_PATH):
    doc=m._load(constraints_path); _validate(doc); m1,m2=m._load(M1_AUDIT_PATH),m._load(M2_VERDICT_PATH); before=next(r for r in m1["solver_prototypes"] if r["candidate_id"]==m2["reviewed_candidate"])["corrected_coordinates"]; anchors=_anchor_constraints(_load_anchor_sidecar()); cards=[]; stats={};
    for stage in "ABCD":
        stage_cards,stats[stage]=_stage(doc,stage,before,anchors,len(cards)+1); cards+=stage_cards
        if any(r["candidate_class"]=="review_available_geometry_improved" for r in stage_cards): break
    if len(cards)>int(doc["search_config"]["max_raw_evaluations"]): raise ValueError("raw cap exceeded")
    chosen=[]
    for stage in "ABCD":
        candidates=sorted((r for r in cards if r["search_stage"]==stage and r["hard_gate_passed"]),key=m._beam_key); chosen += candidates[:(2 if stage=="A" else 1)]
    improved=next((r for r in sorted(cards,key=m._beam_key) if r["candidate_class"]=="review_available_geometry_improved" and r["candidate_id"] not in {x["candidate_id"] for x in chosen}),None); chosen.append(improved or next(r for r in sorted(cards,key=m._beam_key) if r["candidate_id"] not in {x["candidate_id"] for x in chosen})); chosen=chosen[:6]
    failures={s:Counter(v["constraint_id"] for r in cards if r["search_stage"]==s for v in r["anchor_audit"]["hard_violations"]) for s in stats}
    payload={"schema_version":"m_anchor_4_1_2_visible_range_audit_v1","case_name":"task218_ann3741","baseline_candidate":m2["reviewed_candidate"],"input_provenance":{"constraints":{"path":constraints_path.as_posix(),"sha256":_sha(constraints_path)},"anchor_sidecar":{"path":ANCHOR_SIDECAR_PATH.as_posix(),"sha256":_sha(ANCHOR_SIDECAR_PATH)}},"stages_executed":list(stats),"stage_stats":stats,"hard_anchor_failure_count_by_stage":{s:dict(x) for s,x in failures.items()},"hard_gate_fail_count_by_stage":{s:sum(not r["hard_gate_passed"] for r in cards if r["search_stage"]==s) for s in stats},"review_candidates":chosen,"m_anchor_4_2_height_completion_authorized":False,**SAFETY}
    out_dir.mkdir(parents=True,exist_ok=True); paths={"audit":out_dir/"m_anchor_4_1_2_visible_range_audit.json","cards":out_dir/"m_anchor_4_1_2_candidate_cards.jsonl","summary":out_dir/"m_anchor_4_1_2_summary.md","ledger":out_dir/"m_anchor_4_1_2_feedback_ledger_stub.jsonl","ablation":out_dir/"m_anchor_4_1_2_component_ablation.json"}; _write_text_lf(paths["audit"],json.dumps(payload,ensure_ascii=False,indent=2)+"\n"); _write_text_lf(paths["cards"],"".join(json.dumps(r,ensure_ascii=False)+"\n" for r in chosen)); _write_text_lf(paths["summary"],"# M-Anchor.4.1.2\n\nStage D is sensitivity-only, not a final refinement.\n"); _write_text_lf(paths["ledger"],json.dumps({"expert_selected_candidate":None,"expert_verdict":None,"accepted_as_final_fix":False,"m_anchor_4_2_height_completion_authorized":False,"stage_d_reviewed":False,"stage_d_is_sensitivity_only":True,**SAFETY})+"\n"); _write_text_lf(paths["ablation"],json.dumps({"audit_only":True,"component_ablation":[]})+"\n")
    review_out_dir.mkdir(parents=True,exist_ok=True); paths["manifest"]=review_out_dir/"hypothesis_review_bridge_manifest.json"; manifest={"schema_version":"m_anchor_4_1_2_review_bridge_v1","case_name":"task218_ann3741_m_anchor_4_1_2","source_image":m1.get("source_image"),"ordered_pairs":before,"candidates":[{"candidate_id":r["candidate_id"],"family":"m_anchor_4_1_2_visible_range","decision_class":r["candidate_class"],"coordinate_changes":r["coordinate_changes"],"sensitivity_only":r["sensitivity_only"],"final_refinement_eligible":r["final_refinement_eligible"],"requires_explicit_human_visual_verdict":r["requires_explicit_human_visual_verdict"],"direct_ls_trial_allowed":False,"m_anchor_4_2_input_eligible":False,"accepted":False,"annotation_writeback":False} for r in chosen],"safety_boundary":{**SAFETY,"preview_only":True}}; _write_text_lf(paths["manifest"],json.dumps(manifest,ensure_ascii=False,indent=2)+"\n"); paths.update({f"review_{k}":v for k,v in run_local_review(input_path=paths["manifest"],candidate_json=paths["manifest"],candidate_limit=len(chosen),out_dir=review_out_dir,image_root=Path("data/mp3d_layout/img_v"),case_name="task218_ann3741_m_anchor_4_1_2",width=1024,height=512,coordinate_mode="ls_percent",local_server_root=m._local_server_root(review_out_dir)).items()}); return paths

if __name__ == "__main__": print(run()["audit"])
