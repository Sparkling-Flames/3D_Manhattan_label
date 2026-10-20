"""Reuse v2 record evidence and saved actual-prefix geometry to explain room transfer."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from shapely.geometry import Polygon

from .same_room_multiview_20261020 import ROOT, OUT as REPLAY, read
from .personnel_vote_trace_20261020 import trace_groups

OUT = REPLAY / "structure_transfer"
FOCUS = ["MV0001", "MV0003", "MV0004", "MV0005", "MV0007"]


def write(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    if isinstance(value, pd.DataFrame):
        value.to_csv(OUT / name, index=False, encoding="utf-8-sig")
    else:
        (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def floor(points):
    p = np.asarray(points, float)[1::2]
    a = p[:, 0] * 2 * np.pi / 1024
    r = 1 / np.tan((p[:, 1] / 512 - .5) * np.pi)
    return np.column_stack([-np.sin(a) * r, np.cos(a) * r])


def geometry_features(points, reference):
    p = np.asarray(points, float)
    out = dict(corners=len(p) // 2, bottom_y=float(np.median(p[1::2, 1])))
    if reference is None or len(reference) < 6:
        return out
    q = np.asarray(reference, float)
    out["corner_delta"] = len(p) // 2 - len(q) // 2
    # A diagnostic angular correspondence, not a claim of shared physical wall identity.
    def unit(bottom):
        a = bottom[:, 0] * 2 * np.pi / 1024
        b = (bottom[:, 1] / 512 - .5) * np.pi
        return np.column_stack([-np.sin(a)*np.cos(b), -np.sin(b), np.cos(a)*np.cos(b)])
    cost = np.degrees(np.arccos(np.clip(unit(p[1::2]) @ unit(q[1::2]).T, -1, 1)))
    ii, jj = linear_sum_assignment(cost)
    for angle in (9, 12):
        valid = cost[ii, jj] <= angle
        out[f"unmatched_ref_{angle}"] = 1 - valid.sum() / (len(q) // 2)
        out[f"bottom_bias_{angle}"] = float(np.mean(p[1::2][ii[valid], 1] - q[1::2][jj[valid], 1])) if valid.any() else np.nan
    if (p[1::2, 1] > 256).all() and (q[1::2, 1] > 256).all():
        a, b = Polygon(floor(p)), Polygon(floor(q))
        if a.is_valid and b.is_valid and a.area > 0 and b.area > 0:
            out.update(omission=a.intersection(b).area / b.area,
                       extension=a.difference(b).area / a.area,
                       log_area_ratio=float(np.log(a.area / b.area)))
            out["omission"] = 1 - out["omission"]
    return out


def collect(records):
    inventory = pd.DataFrame([{k: r[k] for k in ["object_id", "image_id", "image_code", "worker_id", "condition",
        "is_doorway", "quality_usable", "geometry_status", "room_id"]} for r in records if not r["is_oos"]])
    write("non_oos_inventory.csv.gz", inventory)
    rows = []
    for r in records:
        if r["is_oos"]:
            continue
        p = r["points_1024x512"]
        if p is None or len(p) < 6 or len(p) % 2 or not np.isfinite(p).all():
            continue
        ref = (r.get("reference_evidence") or {}).get("points_1024x512")
        row = {k:r[k] for k in ["object_id", "worker_id", "image_id", "image_code", "building_id", "condition",
                                "origin", "is_doorway", "quality_usable", "reference_id", "geometry_status",
                                "independent_vote_eligible", "cleaning_disposition"]}
        row.update(geometry_features(p, ref))
        row["B8L2"] = r["B8L2"]
        rows.append(row)
    d = pd.DataFrame(rows)
    # GT-free expression: compare each person to the other actual respondents, separately by condition.
    d["peer_corner_delta"] = np.nan
    eligible=d[d.independent_vote_eligible & d.geometry_status.eq("surface_valid")]
    for _, ix in eligible.groupby(["image_id", "condition"]).groups.items():
        vals = d.loc[ix, "corners"]
        if len(vals) >= 3:
            for i in ix:
                d.loc[i, "peer_corner_delta"] = vals[i] - vals.drop(i).median()
    write("record_features.csv.gz", d)
    write("inventory_coverage.json", dict(non_oos_records=len(inventory), non_oos_images=inventory.image_id.nunique(),
        doorway_images=inventory[inventory.is_doorway].image_id.nunique(), geometry_records=len(d),
        non_quality_geometry_records=int((~d.quality_usable).sum()), source="research/statistics/v2_evidence_audit_20261019/records.json.gz"))
    return d


def prediction(d):
    groups=[g for g in read(REPLAY/"GROUPS.json") if g["metric"]=="B8L2" and g["origin"]=="all"]
    manual=d[d.condition.eq("manual") & ~d.is_doorway & d.independent_vote_eligible & d.geometry_status.eq("surface_valid")].copy()
    assert not manual.duplicated(["image_id","worker_id"]).any()
    metrics=["peer_corner_delta","corner_delta","unmatched_ref_9","unmatched_ref_12","bottom_bias_9","omission","extension","log_area_ratio"]
    rows=[]
    for g in groups:
        local=manual[manual.image_id.isin(g["images"])]
        for metric in metrics:
            use=local if metric=="peer_corner_delta" else local[local.quality_usable]
            outside=manual[~manual.building_id.eq(g["building"])]
            if metric!="peer_corner_delta":outside=outside[outside.quality_usable]
            base=outside.groupby("worker_id")[metric].mean()
            for r in use.itertuples():
                hist=use[use.worker_id.eq(r.worker_id)&~use.image_id.eq(r.image_id)][metric].dropna()
                observed=getattr(r,metric)
                if len(hist)<1 or not np.isfinite(observed) or r.worker_id not in base or not np.isfinite(base[r.worker_id]):
                    continue
                source_images=set(use[use.worker_id.eq(r.worker_id)&~use.image_id.eq(r.image_id)&use[metric].notna()].image_id)
                other=use[use.image_id.isin(source_images)&~use.worker_id.eq(r.worker_id)].groupby("image_id")[metric].mean()
                assert r.image_id not in source_images
                rows.append(dict(group_id=g["group_id"],building=g["building"],image=r.image_code,worker=r.worker_id,
                    metric=metric,history_n=len(hist),actual=observed,predicted=hist.mean(),baseline=base[r.worker_id],
                    other_source=other.mean(),other_source_error=abs(observed-other.mean()),
                    error=abs(observed-hist.mean()),baseline_error=abs(observed-base[r.worker_id])))
    r=pd.DataFrame(rows);write("transfer_predictions.csv.gz",r)
    assert r.other_source_error.notna().all()
    images=r.groupby(["metric","building","image"])[["error","baseline_error","other_source_error"]].mean().reset_index()
    buildings=images.groupby(["metric","building"])[["error","baseline_error","other_source_error"]].mean().reset_index()
    write("transfer_buildings.csv",buildings)
    summary=buildings.groupby("metric").agg(same_room_mae=("error","mean"),outside_worker_mae=("baseline_error","mean"),
        other_people_same_sources_mae=("other_source_error","mean"),buildings=("building","nunique")).reset_index()
    write("transfer_summary.csv",summary)
    # Direction consistency is a paired-person description, not a new frozen class.
    write("focus_worker_features.csv",manual[manual.image_id.isin({i for g in groups if g["group_id"] in FOCUS for i in g["images"]})])
    return summary


def normalized_groups(state):
    return [dict(g, members=[dict(worker=m["worker"],source_pair_index=m["source_pair_index"]) for m in g["members"]])
            for g in state["identity_groups"]]


def mechanisms(records):
    nodes=pd.read_csv(REPLAY/"replay_nodes.csv.gz",low_memory=False)
    nodes=nodes[nodes.group_id.isin(FOCUS)]
    write("focus_process.csv",nodes.groupby(["group_id","image","k"])[
        ["B8L2","nodes","omission","extension","S_bottom_deg","dir","height_mean_ratio","reference_pair_count"]].mean().reset_index())
    refs={r["image_id"]:r for r in records}
    transitions=[]; cases=[]; offsets=[]
    for pool_id,part in nodes.groupby("pool_id"):
        raw=read(REPLAY/"runtime/pools"/pool_id/"states.json.gz")["states"]
        states={s["team_id"]:s["automatic"] for s in raw}
        k=int(part.k.max())
        full=part[part.k.eq(k)].iloc[0]
        end=states[full.team_id]
        # All distinct last entrants: no choice of the largest drop.
        for _, prev in part[part.k.eq(k-1)].drop_duplicates("team_id").iterrows():
            after=part[part.replay.eq(prev.replay)&part.k.eq(k)].iloc[0]
            start=states[prev.team_id]
            retained=set(prev.ordered_workers.split("|"))
            traced=trace_groups(normalized_groups(start),normalized_groups(end),retained)
            for t in traced:
                t.update(image=prev.image,group_id=prev.group_id,replay=int(prev.replay),k_before=k-1,k_after=k,
                    threshold_before=start["minimum_support"],threshold_after=end["minimum_support"],
                    entrant=next(w for w in after.ordered_workers.split("|") if w not in retained),
                    quality_change=after.B8L2-prev.B8L2,nodes_change=after.nodes-prev.nodes)
                transitions.append(t)
        # Stable example rule for geometry panels: first saved order, penultimate versus full.
        prev=part[part.replay.eq(0)&part.k.eq(k-1)].iloc[0]
        example=dict(image=full.image,image_id=full.image_id,group_id=full.group_id,k=k,
            before=states[prev.team_id],after=end,quality_before=float(prev.B8L2),quality_after=float(full.B8L2),
            reference=refs[full.image_id]["reference_evidence"],record=refs[full.image_id])
        cases.append(example)
        ref=np.asarray(example["reference"]["points_1024x512"])[1::2]
        v=np.asarray(end["candidate"]["points"])[1::2]
        dx=(v[:,None,0]-ref[None,:,0]+512)%1024-512
        dy=v[:,None,1]-ref[None,:,1]
        ii,jj=linear_sum_assignment(np.hypot(dx,dy))
        for i,j in zip(ii,jj):
            offsets.append(dict(image=full.image,reference_corner=int(j+1),ref_x=ref[j,0],ref_y=ref[j,1],
                fused_x=v[i,0],fused_y=v[i,1],dx=dx[i,j],dy=dy[i,j]))
    t=pd.DataFrame(transitions);write("last_entrant_transitions.csv.gz",t)
    events=t.drop_duplicates(["image","entrant"])
    write("last_entrant_summary.csv",events.groupby(["group_id","image"]).agg(entrants=("entrant","size"),
        mean_quality_change=("quality_change","mean"),min_quality_change=("quality_change","min"),
        max_quality_change=("quality_change","max"),mean_node_change=("nodes_change","mean")).reset_index())
    # Save only the selected, already-existing states used in figures.
    write("case_states.json",[{k:v for k,v in c.items() if k!="record"} for c in cases])
    write("endpoint_corner_offsets.csv",pd.DataFrame(offsets))
    return cases


def plots(cases,d):
    plt.rcParams["font.sans-serif"]=["Microsoft YaHei","DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"]=False
    process=pd.read_csv(OUT/"focus_process.csv")
    for gid in FOCUS:
        cs=[c for c in cases if c["group_id"]==gid]
        fig,axes=plt.subplots(len(cs),3,figsize=(15,3.6*len(cs)),squeeze=False)
        for ax,c in zip(axes,cs):
            for key,label,color in [("before",f'首条顺序 k={c["k"]-1}',"#e69f00"),("after",f'全员 k={c["k"]}',"#0072b2")]:
                p=c[key]["candidate"].get("footprint")
                if p is not None:
                    p=np.array(p);p=np.vstack([p,p[0]]);ax[0].plot(*p.T,".-",color=color,label=label)
            ref=np.array(c["reference"]["floor_xz_h"]);ref=np.vstack([ref,ref[0]])
            ax[0].plot(*ref.T,"k--",label="当前参考");ax[0].scatter([0],[0],marker="x",color="black");ax[0].axis("equal")
            ax[0].set_title(c["image"]);ax[0].legend(fontsize=8)
            p=process[process.image.eq(c["image"])]
            ax[1].plot(p.k,p.B8L2,".-");ax[1].set_ylabel("路径平均 B8L2");ax[1].set_xlabel("真实加入人数")
            ax[2].plot(p.k,p.nodes,".-",label="融合节点");ax[2].axhline(len(ref)-1,color="black",ls="--",label="参考节点")
            ax[2].set_xlabel("真实加入人数");ax[2].legend()
        fig.suptitle(f"{gid}：同一已存人员顺序的末步几何；右侧为全部路径平均",fontsize=15)
        fig.tight_layout();fig.savefig(OUT/f"{gid}_geometry_process.png",dpi=140);plt.close(fig)
    # Photo overlays use actual points; no generated or edited scene content.
    for code in ["VFuaQ6m2Qom-07","S9hNv5qa7GM-12","uNb9QFRL6hY-79"]:
        c=next(c for c in cases if c["image"]==code)
        photo=c["record"]["image_evidence"]["difficulty_record"]["photo"]
        path=ROOT/Path(photo.replace("\\","/"))
        if not path.exists():
            raise FileNotFoundError(path)
        img=plt.imread(path)
        fig,axs=plt.subplots(2,1,figsize=(15,9))
        for ax in axs:
            ax.imshow(img,extent=[0,1024,512,0])
            for points,label,color in [(c["reference"]["points_1024x512"],"参考","#ffdc00"),
                (c["before"]["candidate"]["points"],"末步前","#00ffff"),(c["after"]["candidate"]["points"],"全员","#ff40ff")]:
                p=np.array(points)
                # Bottom corners show actual placement; segments follow declared ring.
                for i in range(0,len(p),2):
                    ax.plot(p[i:i+2,0],p[i:i+2,1],color=color,alpha=.7,lw=1)
                ax.scatter(p[1::2,0],p[1::2,1],s=22,label=label,color=color)
            ax.legend(loc="upper right")
        # Center crop on the largest bottom-point mismatch to reference, reproducibly.
        ref=np.array(c["reference"]["points_1024x512"])[1::2]
        cur=np.array(c["after"]["candidate"]["points"])[1::2]
        dx=np.abs(ref[:,None,0]-cur[None,:,0]);dx=np.minimum(dx,1024-dx)
        cost=np.hypot(dx,ref[:,None,1]-cur[None,:,1])
        x,y=ref[np.argmax(cost.min(axis=1))]
        axs[1].set_xlim(max(0,x-140),min(1024,x+140));axs[1].set_ylim(min(512,y+80),max(0,y-110))
        axs[0].set_title(f"{code} 同图叠加；下方放大参考底点与融合结果距离最大处")
        fig.tight_layout();fig.savefig(OUT/f"{code}_overlay.png",dpi=150);plt.close(fig)


def worker_patterns(records,d):
    plt.rcParams["font.sans-serif"]=["Microsoft YaHei","DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"]=False
    groups=[g for g in read(REPLAY/"REPLAY_GROUPS.json") if g["group_id"] in FOCUS]
    roles=pd.read_csv(ROOT/"research/workers/personnel_composition_study_20261019/analysis/reverse/historical_roles.csv.gz")
    rows=[]
    for g in groups:
        p=d[d.image_id.isin(g["images"]) & d.worker_id.isin(g["common_workers"]) & d.condition.eq("manual")
            & d.independent_vote_eligible]
        assert len(p)==len(g["images"])*len(g["common_workers"])
        p=p.copy();p["group_id"]=g["group_id"];rows.append(p)
    fixed=pd.concat(rows)
    write("common_worker_patterns.csv",fixed.merge(roles[roles.domain.eq("global")][
        ["worker_id","count_gap_mean","depression_gap_mean","count_below_rate","n_images"]],
        on="worker_id",how="left",validate="many_to_one"))
    g=fixed[fixed.group_id.eq("MV0003")]
    pivot=g.pivot(index="worker_id",columns="image_code",values="corners")
    fig,ax=plt.subplots(figsize=(9,6))
    im=ax.imshow(pivot.values,cmap="viridis",vmin=4,vmax=16)
    for i in range(len(pivot)):
        for j in range(len(pivot.columns)):
            ax.text(j,i,str(int(pivot.iloc[i,j])),ha="center",va="center",color="white" if pivot.iloc[i,j]<10 else "black")
    ax.set_xticks(range(len(pivot.columns)),[x.rsplit("-",1)[1] for x in pivot.columns]);ax.set_yticks(range(len(pivot)),pivot.index)
    ax.set_title("G057 同一9人各视角实际角点数（参考依次10、14、16、16）")
    fig.colorbar(im,ax=ax,label="实际角点数");fig.tight_layout();fig.savefig(OUT/"G057_worker_patterns.png",dpi=150);plt.close(fig)
    # Contrasting observed examples, not classes or estimates of prevalence.
    chosen={r["image_code"]:r for r in records if r["worker_id"]=="W112" and r["image_code"].startswith("VFua")
            and r["condition"]=="manual" and r["independent_vote_eligible"]}
    chosen2={r["image_code"]:r for r in records if r["worker_id"]=="W107" and r["condition"]=="manual" and r["independent_vote_eligible"]}
    fig,axs=plt.subplots(4,1,figsize=(15,13))
    for ax,code in zip(axs,pivot.columns):
        r=chosen[code];s=chosen2[code];photo=r["image_evidence"]["difficulty_record"]["photo"]
        ax.imshow(plt.imread(ROOT/Path(photo.replace("\\","/"))),extent=[0,1024,512,0])
        for points,label,color in [(r["reference_evidence"]["points_1024x512"],"参考","#ffdc00"),
                                  (r["points_1024x512"],"W112","#00ffff"),(s["points_1024x512"],"W107","#ff40ff")]:
            p=np.asarray(points)
            ax.scatter(p[1::2,0],p[1::2,1],color=color,s=17,label=label)
            for i in range(0,len(p),2):ax.plot(p[i:i+2,0],p[i:i+2,1],color=color,alpha=.6,lw=.8)
        ax.set_title(code);ax.legend(loc="upper right",fontsize=8)
    fig.suptitle("同一人员的保留与简化：原始处理点位叠加，未移动或补点")
    fig.tight_layout();fig.savefig(OUT/"G057_two_workers_overlay.png",dpi=140);plt.close(fig)


def gate_examples():
    plt.rcParams["font.sans-serif"]=["Microsoft YaHei","DejaVu Sans"]
    fig,axs=plt.subplots(1,2,figsize=(12,6))
    metadata=[]
    for ax,code in zip(axs,["VFuaQ6m2Qom-04","VFuaQ6m2Qom-07"]):
        folder=next((REPLAY/"runtime/pools").glob(code+"*"))
        nodes=pd.DataFrame(read(folder/"request_results.json.gz")["results"])
        prev=nodes[nodes.k.eq(8)].drop_duplicates("team_id").sort_values(["B8L2","team_id"]).iloc[4]
        final=nodes[nodes.k.eq(9)].iloc[0]
        states={x["team_id"]:x["automatic"] for x in read(folder/"states.json.gz")["states"]}
        a,b=states[prev.team_id],states[final.team_id]
        assert a["minimum_support"]==4 and b["minimum_support"]==5
        for state,label,color in [(a,"8人／4票门槛","#e69f00"),(b,"9人／5票门槛","#0072b2")]:
            p=np.array(state["candidate"]["footprint"]);p=np.vstack([p,p[0]])
            ax.plot(*p.T,".-",color=color,label=label)
        tr=trace_groups(normalized_groups(a),normalized_groups(b),set(prev.ordered_workers.split("|")))
        lost=[t for t in tr if t["kind"]=="one_to_one" and t["selected_before"]==1 and t["selected_after"]==0]
        assert all(t["support_before"]==t["support_after"]==4 for t in lost)
        for t in lost:
            g=next(g for g in b["identity_groups"] if g["feature_id"]==t["after_ids"])
            point=floor(g["center"])[0];ax.scatter(*point,color="red",marker="x",s=60)
        ax.set_title(f'{code}\nQ {prev.B8L2:.2f} → {final.B8L2:.2f}；丢失{len(lost)}个原有节点')
        ax.axis("equal");ax.legend()
        metadata.append(dict(image=code,selection="median eight-person Q among all nine distinct predecessor teams",
            before_team=prev.team_id,after_team=final.team_id,ordered_workers_before=prev.ordered_workers,
            lost_one_to_one_groups=lost))
    fig.suptitle("末步门槛效应实例：各图取九种末步变化中间的案例；红叉为原有4票节点")
    fig.tight_layout();fig.savefig(OUT/"G057_gate_examples.png",dpi=150);plt.close(fig)
    write("G057_gate_examples.json",metadata)


def main():
    records=read(ROOT/"research/statistics/v2_evidence_audit_20261019/records.json.gz")["records"]
    d=collect(records);summary=prediction(d);print(summary.to_string(index=False),flush=True)
    cases=mechanisms(records);plots(cases,d);worker_patterns(records,d);gate_examples()
    write("FIELD_CONTRACT.json",dict(source="v2_evidence_audit_20261019/records.json.gz",
        reference_metrics="diagnostic against unchanged reference; prediction restricted to quality_usable",
        expression_metric="peer_corner_delta: count minus other respondents median, image and condition specific; GT free",
        correspondence="9/12 degree one-to-one bottom-ray assignment within one image; NOT cross-view physical corner matching",
        prediction="all observed other views of same worker in declared room, target excluded; compare same-worker other-building mean; target image then building equal",
        scope="omission=1-intersection/reference area; extension=outside-reference/answer area; not semantic scope adjudication",
        last_step="all distinct penultimate teams; geometry examples use replay 0; existing states only",
        tables={p.name:list(pd.read_csv(p,nrows=0).columns) for p in OUT.glob("*.csv*")}))


if __name__=="__main__":
    main()
