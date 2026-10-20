"""Adapt reviewed discovery illustrations to the parent's generic case schema."""
from pathlib import Path
import json,pandas as pd
import design_baseline as d
from select_case_candidates import clean


def main():
    folder=Path(__file__).parent;results=folder/"results";source=results/"DISCOVERY_CASE_CANDIDATES.json"
    selected=d.fr.read(source);spec=d.fr.read(folder/"BASELINE_SPEC.json")
    events=pd.read_csv(folder/"EVENT_DESIGN.csv.gz").set_index("event_id");cases=[]
    def adapt(eid):
        e=events.loc[eid].to_dict();e["event_id"]=eid;e["n"]=int(e["k"]);e["phase"]="discovery_reused_v2_known_baseline"
        assert e["historical_phase"]=="discovery"
        t=spec["targets"][e["target"]];e["direction"]=t["outgoing"]+"→"+t["incoming"];e["outgoing_class"]=t["outgoing"];e["incoming_class"]=t["incoming"]
        # The original labels CSV calls this domain global, while the prior
        # scientific helper aliases it to all. This is the same frozen map.
        e["baseline_request_domain"]=e["domain"];e["domain"]="global";e["domain_alias_note"]="Original frozen labels file names global; baseline request helper aliases global to all. Labels and membership unchanged."
        return clean(e)
    categories={
      ("both_draws_multi_person_geometric_contrast","G"):("BL_G_repeat","同一构成换人较近，改类后两次都改变结构"),
      ("both_draws_multi_person_geometric_contrast","R"):("BL_R_repeat","同类换人稳定，改类却连续两次改善"),
      ("class_geometric_contrast","G"):("BL_G_pure","两个纯类别的八人构成出现明显差异"),
      ("same_composition_similar_Q_different_geometry","G"):("BL_G_sameQ","同构成和近似分数仍可能产生不同形状"),
      ("within_different_nodes_shape_equivalent","R"):("BL_R_nodes","原始节点数不同，真实转角与边界仍接近")}
    for z in selected["candidates"]:
        e=z["event"];key=(z["category"],e["target"])
        if key not in categories:continue
        cid,title=categories[key];event=adapt(e["event_id"]);teamkeys=[event[a+"_team_key"] for a in "ABC"];labels={event[a+"_team_key"]:a for a in "ABC"}
        if z["category"].startswith("both_draws"):
            rep=e["other_registered_draw_same_pool_n_m"][0];other=adapt(rep["event_id"]);event["other_registered_draw"]=other
            for arm in "ABC":
                labels[event[arm+"_team_key"]]="第1套"+arm
                labels[other[arm+"_team_key"]]="第2套"+arm;teamkeys.append(other[arm+"_team_key"])
        cases.append(dict(case_id=cid,title=title,reason=z["definition"],event=event,team_keys=teamkeys,team_labels=labels,native_dir=str((folder/"native_runs").relative_to(d.ROOT)),baseline_candidate=e,subtitle=e["image"]+f" | {e['target']} | n={e['k']}, m={e['m']} | 结果选择的 discovery 展示"))
    for z in selected["mechanism_candidates"]:
        s=z["step"]
        if (s["target"],z["category"]) not in [("G","threshold_quality_improves"),("R","threshold_quality_worsens")]:continue
        before=adapt(s["event_before"]);after=adapt(s["event_after"]);before["nested_event_after"]=after;before["nested_vote_bookkeeping"]=s
        teamkeys=[e[arm+"_team_key"] for e in [before,after] for arm in "ABC"]
        labels={e[arm+"_team_key"]:f"n{e['n']} {arm}" for e in [before,after] for arm in "ABC"}
        isg=s["target"]=="G"
        cases.append(dict(case_id="BL_G_threshold" if isg else "BL_R_threshold",title="增加一人，票数门槛上升后分数改善" if isg else "增加一人，票数门槛上升后分数下降",reason="Metadata-registered native transition: unchanged old observation partition; selected groups lose selection with unchanged support as ceil(n/2) increases. This does not establish semantic necessity or a pure causal head-count effect.",event=before,team_keys=teamkeys,team_labels=labels,native_dir=str((folder/"native_runs").relative_to(d.ROOT)),subtitle=z["before"]["image"]+f" | {s['target']} | n{s['n_before']}→{s['n_after']}, m={s['m']} | 加入 {s['added_worker']} | 重点 {s['arm']} 臂",mechanism=s))
    d.save_json(results/"BASELINE_EXPORT_SELECTION.json",clean(dict(schema="interchangeability_case_selection_v1",phase="Original discovery only; outcome-selected visual illustrations",candidate_source_sha256=d.sha(source),baseline_request_sha256=d.sha(folder/"REQUESTS.json.gz"),labels_file="analysis/reverse/worker_labels.csv.gz",image_policy="Parent supplies selected Release images; numerical export/replay does not need originals.",cases=cases)))
    print(json.dumps(dict(cases=len(cases),teams=sum(len(z["team_keys"]) for z in cases),output=str(results/"BASELINE_EXPORT_SELECTION.json"))))


if __name__=="__main__":main()
