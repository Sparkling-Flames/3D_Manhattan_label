"""Development-only preflight for annotation uncertainty trajectories."""
from __future__ import annotations

import argparse, csv, json, math, random, statistics, sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.thesis_main.analysis import run_topology_sequential_preflight as v3
from tools.thesis_main.analysis.geometry_cluster_v2 import cluster_geometry_records

SEED = 20260820
KS = (3, 5, 8, 12, 16, 20, 22)
FLAGS = {"development_only": True, "scientific_conclusion_prohibited": True,
         "formal_uncertainty_model_frozen": False, "main_launch_authorized": False}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = []
    for row in rows:
        for key in row:
            if key not in fields: fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for row in rows:
            w.writerow({k: json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v,(dict,list))
                        else "true" if v is True else "false" if v is False else "" if v is None else v
                        for k,v in row.items()})


def mean(values):
    values = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return statistics.mean(values) if values else None


def cluster(records, task_id, q=.95):
    return cluster_geometry_records(records, min_q_boundary=q, min_q_wallwall=q,
        base_task_id=task_id, condition="manual", minimum_valid_k=3,
        pairwise_fn=v3._pairwise_metric)


def groups(result):
    raw = result.get("cluster_membership_json")
    return json.loads(raw) if raw else []


def entropy(memberships, k):
    if not memberships or k < 2: return None
    p = [len(g)/k for g in memberships]
    return -sum(x*math.log(x) for x in p if x>0)/math.log(k)


def pair_agreement(prefix_groups, terminal_label):
    ids = [x for g in prefix_groups for x in g]
    if len(ids)<2 or any(x not in terminal_label for x in ids): return None
    prefix = {x:i for i,g in enumerate(prefix_groups) for x in g}
    agree=total=0
    for i in range(len(ids)):
        for j in range(i+1,len(ids)):
            agree += int((prefix[ids[i]]==prefix[ids[j]]) ==
                         (terminal_label[ids[i]]==terminal_label[ids[j]]))
            total += 1
    return agree/total if total else None


def n_pairs(row):
    text=str(row.get("topology_signature") or "")
    try: return float(text.split(":",1)[1]) if text.startswith("n_pairs:") else None
    except ValueError: return None


def variance(values):
    return statistics.pvariance(values) if len(values)>1 else 0.0


def analyse(root: Path, replicates: int, permutations: int):
    data=v3.load_frozen_inputs(root)
    full={}
    full_rows=[]
    for task_id,records in sorted(data["candidates"].items()):
        result=cluster(records,task_id)
        full[task_id]=result
        full_rows.append({"base_task_id":task_id,"building_id":data["tasks"][task_id].get("building_id",""),
            "candidate_n":len(records),"support_band":"k22" if len(records)==22 else "exact_k5",
            "partition_status":result.get("partition_status"),
            "crowd_status":result.get("task_crowd_structure_status"),
            "cluster_count":result.get("cluster_count"),
            "largest_support":result.get("largest_cluster_support"),
            "second_support":result.get("second_cluster_support"),
            "largest_share":result.get("largest_cluster_share"),
            "second_share":result.get("second_cluster_share"),
            "partition_entropy":entropy(groups(result),len(records)),**FLAGS})
    k22=[t for t,r in data["candidates"].items() if len(r)==22]
    if len(k22)!=12: raise AssertionError(f"k22 denominator {len(k22)}")

    acc={(t,k):{"status":Counter(),"largest":[],"entropy":[],"agreement":[]} for t in k22 for k in KS}
    for task_id in k22:
        records=data["candidates"][task_id]
        terminal_groups=groups(full[task_id])
        terminal={x:i for i,g in enumerate(terminal_groups) for x in g}
        for rep in range(replicates):
            order=v3._stable_order(records,task_id,rep,SEED)
            for k in KS:
                result=cluster(order[:k],task_id)
                key=acc[task_id,k]
                status=str(result.get("task_crowd_structure_status") or "not_evaluable")
                key["status"][status]+=1
                if result.get("largest_cluster_share") not in (None,""):
                    key["largest"].append(float(result["largest_cluster_share"]))
                e=entropy(groups(result),k)
                if e is not None: key["entropy"].append(e)
                a=pair_agreement(groups(result),terminal)
                if a is not None: key["agreement"].append(a)
    trajectory=[]
    for (task_id,k),state in sorted(acc.items()):
        total=sum(state["status"].values())
        trajectory.append({"base_task_id":task_id,"building_id":data["tasks"][task_id].get("building_id",""),
            "prefix_k":k,"replicates":total,
            "p_unimodal":state["status"]["unimodal"]/total,
            "p_dominant_with_dissent":state["status"]["dominant_with_dissent"]/total,
            "p_supported_multimodal":state["status"]["supported_multimodal"]/total,
            "p_not_evaluable":state["status"]["not_evaluable"]/total,
            "mean_largest_share":mean(state["largest"]),
            "mean_uncertainty_mass":1-mean(state["largest"]) if state["largest"] else None,
            "mean_partition_entropy":mean(state["entropy"]),
            "mean_agreement_with_k22_partition":mean(state["agreement"]),**FLAGS})

    # Test whether the same workers repeatedly occupy dominant/minority modes.
    labels_by_task={}; topology_by_task={}
    for task_id in k22:
        result=full[task_id]; membership=groups(result)
        if result.get("partition_status")!="unique" or not membership: continue
        by_id={v3._key(r):r for r in data["candidates"][task_id]}
        labels={}; values={}
        for gi,g in enumerate(membership):
            role="dominant" if gi==0 else "supported_minority" if len(g)>=2 else "singleton"
            for aid in g:
                row=by_id[aid]; wid=int(row["worker_id"]); labels[wid]=role
                value=n_pairs(row)
                if value is not None: values[wid]=value
        labels_by_task[task_id]=labels; topology_by_task[task_id]=values
    workers=sorted({w for x in labels_by_task.values() for w in x})

    def dominant_variance(labels):
        counts={w:[0,0] for w in workers}
        for task in labels.values():
            for w,role in task.items(): counts[w][0]+=int(role=="dominant"); counts[w][1]+=1
        return variance([a/b for a,b in counts.values() if b])
    def corner_variance(values):
        by_worker=defaultdict(list)
        for task in values.values():
            m=mean(task.values())
            if m is not None:
                for w,v in task.items(): by_worker[w].append(v-m)
        return variance([mean(v) for v in by_worker.values() if v])
    obs_dom=dominant_variance(labels_by_task); obs_corner=corner_variance(topology_by_task)
    rng=random.Random(SEED+17); null_dom=[]; null_corner=[]
    for _ in range(permutations):
        pl={}; pc={}
        for t,task in labels_by_task.items():
            ws=list(task); roles=list(task.values()); rng.shuffle(roles); pl[t]=dict(zip(ws,roles))
            vals=topology_by_task.get(t,{}); ws2=list(vals); vv=list(vals.values()); rng.shuffle(vv); pc[t]=dict(zip(ws2,vv))
        null_dom.append(dominant_variance(pl)); null_corner.append(corner_variance(pc))
    tests={"evaluable_k22_tasks":len(labels_by_task),"workers":len(workers),"permutations":permutations,
        "dominant_membership":{"observed_variance":obs_dom,"null_mean":mean(null_dom),
            "p_value":(1+sum(x>=obs_dom for x in null_dom))/(permutations+1)},
        "task_centered_corner_count":{"observed_variance":obs_corner,"null_mean":mean(null_corner),
            "p_value":(1+sum(x>=obs_corner for x in null_corner))/(permutations+1)},**FLAGS}

    worker_rows=[]
    for w in workers:
        roles=[task[w] for task in labels_by_task.values() if w in task]
        residuals=[]
        for task in topology_by_task.values():
            if w in task: residuals.append(task[w]-mean(task.values()))
        worker_rows.append({"worker_id":w,"k22_tasks":len(roles),
            "dominant_rate":roles.count("dominant")/len(roles) if roles else None,
            "supported_minority_rate":roles.count("supported_minority")/len(roles) if roles else None,
            "singleton_rate":roles.count("singleton")/len(roles) if roles else None,
            "mean_task_centered_corner_pair_residual":mean(residuals),**FLAGS})

    q95=Counter(r["crowd_status"] for r in full_rows)
    exact5=Counter(r["crowd_status"] for r in full_rows if r["support_band"]=="exact_k5")
    high=Counter(r["crowd_status"] for r in full_rows if r["support_band"]=="k22")
    summary={"status":"complete","denominators":{"tasks_k_ge_5":78,"exact_k5":66,"k22":12,"submissions":594},
        "full_support_q095":{"all":dict(q95),"exact_k5":dict(exact5),"k22":dict(high)},
        "worker_tendency_tests":tests,"replicates_per_k22_task":replicates,
        "limitations":["12 k22 tasks are 12 independent tasks; replays are sensitivity analyses, not new samples.",
          "Complete-link clusters are operational measurements, not validated latent truths.",
          "Different corner counts are incompatible under the current contract and may inflate topology uncertainty.",
          "Persistent means disagreement remains at finite observed support, not proof of non-convergence at infinity."],**FLAGS}
    return full_rows,trajectory,worker_rows,tests,summary


def main():
    p=argparse.ArgumentParser(); p.add_argument("--root",type=Path,default=ROOT)
    p.add_argument("--output-dir",type=Path,default=ROOT/"analysis_results"/"annotation_uncertainty_preflight_20260820_v1")
    p.add_argument("--replicates",type=int,default=200); p.add_argument("--permutations",type=int,default=5000)
    a=p.parse_args(); a.output_dir.mkdir(parents=True,exist_ok=True)
    full,traj,workers,tests,summary=analyse(a.root,a.replicates,a.permutations)
    write_csv(a.output_dir/"FULL_SUPPORT_STATES.csv",full); write_csv(a.output_dir/"K22_PREFIX_TRAJECTORIES.csv",traj)
    write_csv(a.output_dir/"K22_WORKER_TENDENCIES.csv",workers)
    (a.output_dir/"WORKER_TENDENCY_TESTS.json").write_text(json.dumps(tests,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    (a.output_dir/"ANNOTATION_UNCERTAINTY_SUMMARY.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    report="# Annotation uncertainty trajectory preflight\n\n"+\
      "Development-only; no paper direction or policy is frozen.\n\n"+\
      f"Full-support q=.95 states: `{json.dumps(summary['full_support_q095']['all'],sort_keys=True)}`.\n\n"+\
      f"k22 states: `{json.dumps(summary['full_support_q095']['k22'],sort_keys=True)}`.\n\n"+\
      f"Worker dominant-mode tendency permutation p={tests['dominant_membership']['p_value']:.6f}; "+\
      f"task-centred corner-count tendency p={tests['task_centered_corner_count']['p_value']:.6f}.\n\n"+\
      "See `K22_PREFIX_TRAJECTORIES.csv` for how each task changes as k increases.\n"
    (a.output_dir/"ANNOTATION_UNCERTAINTY_REPORT.md").write_text(report,encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
