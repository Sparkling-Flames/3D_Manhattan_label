"""Incrementally evaluate registered Semi events from completed cached endpoints.

No fusion/scoring calls.  Reuses the frozen event/geometry/corner kernel; atomic
per-pool checkpoints make partial progress independently recoverable.
"""
from __future__ import annotations

import argparse
import sys
import time

from register_semi_closure import *

sys.path.insert(0, str(OLD))
import evaluate_joint as inherited

STUDY = HERE.parent
OLD_GLOBAL = ROOT / "research/workers/personnel_global_composition_20261021"


def endpoint_sources():
    sources = [(OLD/"ALL_USED_ENDPOINT_SCALARS.csv.gz", OLD/"ALL_USED_ENDPOINT_GEOMETRY.csv.gz")]
    for path in sorted((STUDY/"native/batches").glob("*/ENDPOINT_SCALARS.csv.gz")):
        geometry = path.with_name("ENDPOINT_GEOMETRY.csv.gz")
        if geometry.exists() and (path.parent/"COMPLETION.json").exists():
            sources.append((path,geometry))
    return [(s,g) for s,g in sources if s.exists() and g.exists()]


def load_teams(keys):
    teams, refs = {}, []
    for scalar, geometry in endpoint_sources():
        added=set()
        for chunk in pd.read_csv(scalar,dtype=str,keep_default_na=False,chunksize=20000):
            for row in chunk[chunk.team_key.isin(keys)].to_dict("records"):
                key=row["team_key"]
                item=inherited.typed(row)
                if key in teams:
                    assert [teams[key].get(k) for k in ["B8L2","D10","nodes"]]==[item.get(k) for k in ["B8L2","D10","nodes"]]
                    continue
                teams[key]=item
                added.add(key)
        if not added:
            continue
        for chunk in pd.read_csv(geometry,dtype=str,keep_default_na=False,chunksize=20000):
            for row in chunk[chunk.team_key.isin(added)].to_dict("records"):
                teams[row["team_key"]]["geometry"]=json.loads(row["geometry_json"]) if row["geometry_json"] else None
        refs.append(dict(scalar_file=str(scalar.relative_to(ROOT)),geometry_file=str(geometry.relative_to(ROOT)),
                         scalar_sha256=sha(scalar),geometry_sha256=sha(geometry),loaded_keys=len(added)))
    for key,item in teams.items():
        assert "geometry" in item,(key,"missing_geometry")
        item.update(dict(zip(inherited.EXTRA,inherited.expression(item["geometry"]))))
    return teams,refs


def annotate_event(event, teams):
    # Actual support fields permit threshold/mechanism tracing without rerunning
    # fusion.  They are diagnostics and never used to choose this experiment.
    for arm in "ABC":
        endpoint=teams[event["team_"+arm]]
        for field in ["minimum_support","identity_groups_n","unselected_groups_n","selected_support_min",
                      "half_vote_nodes","below_four","location_unresolved","connection_available",
                      "geometry_area_h2","height_mean_h","top_y_mean_px","bottom_y_mean_px"]:
            event[arm+"_"+field]=endpoint.get(field)
        supports=endpoint.get("node_supports")
        event[arm+"_node_supports"]="|".join(map(str,supports)) if isinstance(supports,list) else supports
    event["analysis_layer"]=("configuration_completion" if event["stage"]=="semi_closure_configuration_completion" else "source_partition_expansion")
    event["class_direction_semantics"]=("higher_historical_Q_faster_more_turns" if event["class_center_delta_turn_history"]>=.25
                                         else "higher_historical_Q_faster_ordinary_expression")
    # Every source partition and its A/B mirror are kept in the source census.
    # C minus the mean of both source teams is invariant to arbitrary orientation.
    for field in ["B8L2","D10","nodes","source_time_total_seconds"]:
        a,b,c=[event.get(arm+"_"+field) for arm in "ABC"]
        event["C_minus_mean_source_"+field]=c-(a+b)/2 if all(inherited.finite(x) for x in [a,b,c]) else None
    return event


def evaluate_controls(requests, teams):
    result=[]
    for row in requests.to_dict("records"):
        e=dict(row)
        a,b=teams[row["team_C"]],teams[row["team_QT"]]
        e["C_failure"]=not bool(a.get("complete_evaluable"))
        e["QT_failure"]=not bool(b.get("complete_evaluable"))
        e["all_scored"]=all(inherited.finite(x.get("B8L2")) for x in [a,b])
        e["all_complete"]=not(e["C_failure"] or e["QT_failure"])
        for arm,t in [("C",a),("QT",b)]:
            for f in ["B8L2","D10","source_time_total_seconds","time_source_kinds","source_time_known_n","score_status"]:
                e[arm+"_"+f]=t.get(f)
        for f in inherited.COMPONENTS+inherited.EXTRA:
            x,y=a.get(f),b.get(f)
            e["class_minus_qt_"+f]=x-y if inherited.finite(x) and inherited.finite(y) else None
        n=int(row["n"])
        comparable=(a.get("time_source_kinds")==b.get("time_source_kinds") and a.get("time_source_kinds")
                    and "|" not in a["time_source_kinds"]
                    and a.get("source_time_known_n")==n and b.get("source_time_known_n")==n
                    and all(inherited.finite(x.get("source_time_total_seconds")) and x["source_time_total_seconds"]>0 for x in [a,b]))
        e["recorded_time_single_source"]=bool(comparable)
        e["class_vs_qt_log_time_ratio"]=math.log(a["source_time_total_seconds"]/b["source_time_total_seconds"]) if comparable else None
        e["class_vs_qt_time_pct"]=100*math.expm1(e["class_vs_qt_log_time_ratio"]) if comparable else None
        result.append(e)
    return pd.DataFrame(result)


def run():
    began=time.monotonic()
    requests=pd.read_csv(HERE/"EVENTS_REGISTERED_ALL.csv.gz",dtype=str,keep_default_na=False)
    control_frames=[]
    for name,layer in [("CONTINUOUS_QT_CONTROLS.csv.gz","source_partition_expansion"),
                       ("CONFIGURATION_COMPLETION_QT_CONTROLS.csv.gz","configuration_completion")]:
        frame=pd.read_csv(HERE/name,dtype=str,keep_default_na=False)
        frame["analysis_layer"]=layer
        control_frames.append(frame)
    controls=pd.concat(control_frames,ignore_index=True)
    keys=set(requests.team_A)|set(requests.team_B)|set(requests.team_C)|set(controls.team_QT)
    teams,refs=load_teams(keys)
    write(HERE/"ENDPOINT_SOURCE_REFERENCES.csv",pd.DataFrame(refs))
    completed_frames,completed_controls,ledger=[],[],[]
    engine=None
    histories=None
    for pool,req in requests.groupby("pool_id",sort=True):
        cr=controls[controls.pool_id.eq(pool)]
        need=set(req.team_A)|set(req.team_B)|set(req.team_C)|set(cr.team_QT)
        name=h("completed_pool",pool)[:20]
        out=HERE/"completed_pools"/(name+".csv.gz")
        out_qt=HERE/"completed_pools"/(name+"_QT.csv.gz")
        receipt=HERE/"completed_pools"/(name+".json")
        row=dict(pool_id=pool,registered_events=len(req),registered_controls=len(cr),needed_teams=len(need),
                 available_teams=len(need&set(teams)),missing_teams=len(need-set(teams)))
        if not need<=teams.keys():
            row["status"]="waiting_for_endpoints"
            ledger.append(row)
            continue
        if out.exists() and out_qt.exists() and receipt.exists():
            prior=json.loads(receipt.read_text())
            assert prior["events"]==len(req) and prior["controls"]==len(cr)
            frame=pd.read_csv(out,low_memory=False)
            qc=pd.read_csv(out_qt,low_memory=False)
            row["status"]="reused_completed_pool_checkpoint"
        else:
            if engine is None:
                # Setup imports the frozen geometry modules, without invoking
                # fusion_runner; all endpoint generation is centrally owned.
                _,_,sg,corner=inherited.gs.setup_engine()
                engine=(sg,corner)
                histories=pd.read_csv(OLD_GLOBAL/"multivariate/continuous_features_lobo.csv.gz")
                hist={(r.condition,r.heldout_building,r.worker_id):r for r in histories.itertuples()}
            sg,corner=engine
            pairs,signatures={},{}
            results=[]
            for request in req.to_dict("records"):
                e=inherited.complete_event(request,teams,pairs,signatures,hist,sg,corner,"semi")
                # Extra hex identifiers remain opaque even in the rare case of
                # a digits-only digest.
                for f in ["cell_id","reservoir_id","background_id","qt_control_id","team_QT","config_id"]:
                    if f in request:e[f]=request[f]
                results.append(annotate_event(e,teams))
            frame=pd.DataFrame(results)
            qc=evaluate_controls(cr,teams)
            write(out,frame)
            write(out_qt,qc)
            save(receipt,dict(pool_id=pool,events=len(frame),controls=len(qc),unique_teams=len(need),
                              events_sha256=sha(out),controls_sha256=sha(out_qt),
                              fusion_calls=0,scoring_calls=0,used_frozen_kernel=True))
            row["status"]="new_pool_evaluation_saved"
        completed_frames.append(frame)
        completed_controls.append(qc)
        row.update(scored_events=int(frame.all_scored.sum()),complete_events=int(frame.all_complete.sum()),
                   time_comparable_events=int(frame.recorded_time_single_source.sum()))
        ledger.append(row)
        write(HERE/"POOL_COMPLETION_LEDGER.csv",pd.DataFrame(ledger))
        print(json.dumps(row,ensure_ascii=False),flush=True)
    if completed_frames:
        write(HERE/"EVENTS_COMPLETE.csv.gz",pd.concat(completed_frames,ignore_index=True))
        write(HERE/"CONTINUOUS_QT_COMPLETE.csv.gz",pd.concat(completed_controls,ignore_index=True))
    write(HERE/"POOL_COMPLETION_LEDGER.csv",pd.DataFrame(ledger))
    status=dict(registered_events=len(requests),registered_controls=len(controls),needed_teams=len(keys),available_teams=len(teams),
                completed_events=sum(len(f) for f in completed_frames),completed_pools=len(completed_frames),
                pending_pools=len(ledger)-len(completed_frames),elapsed_seconds=time.monotonic()-began,
                frozen_event_kernel=str((OLD_GLOBAL/"continuation_20261021/n20_abc/event_kernel.py").relative_to(ROOT)),
                fusion_calls=0,scoring_calls=0)
    save(HERE/"EVALUATION_PROGRESS.json",status)
    print(json.dumps(status,ensure_ascii=False),flush=True)


if __name__=="__main__":
    run()
