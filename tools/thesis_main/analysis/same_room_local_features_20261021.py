"""Small image-supported physical feature correspondences; reuse frozen replay states."""
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.optimize import linear_sum_assignment
from scipy.stats import rankdata

from .same_room_multiview_20261020 import ROOT, OUT as PARENT, read

OUT=PARENT/"local_features_20261021"
MAPS=[
    dict(room="G046",feature="G046_shower_step_outer",label="洗手台与淋浴区窄转折外端",
         views={"S9hNv5qa7GM-05":4,"S9hNv5qa7GM-12":4,"S9hNv5qa7GM-21":4}),
    dict(room="G046",feature="G046_shower_step_inner",label="洗手台与淋浴区窄转折内端",
         views={"S9hNv5qa7GM-05":5,"S9hNv5qa7GM-12":5,"S9hNv5qa7GM-21":5}),
    dict(room="G057",feature="G057_control_wall_door_end",label="门与墙控旁窄墙体门侧端",
         views={"VFuaQ6m2Qom-07":9,"VFuaQ6m2Qom-10":5}),
    dict(room="G057",feature="G057_control_wall_vanity_end",label="门与墙控旁窄墙体台柜侧端",
         views={"VFuaQ6m2Qom-07":10,"VFuaQ6m2Qom-10":6}),
]


def save(name,x):
    OUT.mkdir(exist_ok=True)
    if isinstance(x,pd.DataFrame):x.to_csv(OUT/name,index=False,encoding="utf-8-sig")
    else:(OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8")


def local_assign(points,ref,tolerance):
    """Within-image azimuth observation matching, not automatic physical correspondence."""
    a=np.asarray(points,float)[::2,0]
    b=np.asarray(ref,float)[::2,0]
    dx=(a[None,:]-b[:,None]+512)%1024-512
    cost=np.abs(dx)*360/1024
    # Dummies permit missing reference corners; one observation cannot fill two ends.
    matrix=np.concatenate([np.where(cost<=tolerance,cost,1e6),np.full((len(b),len(b)),1000.)],axis=1)
    ii,jj=linear_sum_assignment(matrix)
    return {int(i):dict(pair_index=int(j),dx=float(dx[i,j]),distance_deg=float(cost[i,j]))
            for i,j in zip(ii,jj) if j<len(a) and cost[i,j]<=tolerance}


def history_prediction(frame,worker,image):
    own=frame[frame.worker_id.eq(worker)&~frame.image_code.eq(image)]
    source_images=set(own.image_code)
    assert image not in source_images
    other=frame[frame.image_code.isin(source_images)&~frame.worker_id.eq(worker)]
    perimage=other.groupby("image_code").hit.mean()
    if not len(own) or len(perimage)!=len(source_images):return None
    return float(own.hit.mean()),float(perimage.mean()),len(source_images)


def auc(y,p):
    y=np.asarray(y,bool);p=np.asarray(p,float)
    if not y.any() or y.all():return np.nan
    ranks=rankdata(p);n=y.sum()
    return float((ranks[y].sum()-n*(n+1)/2)/(n*(len(y)-n)))


def prediction_tables(pred):
    """Add fixed baselines on exactly the existing target rows; safe to rerun."""
    pred=pred[~pred.method.isin(["constant_half","others_half_shrunk"])].copy()
    other=pred[pred.method.eq("others_same_source_views")]
    additions=[]
    for method,probability in [("constant_half",.5),
                               ("others_half_shrunk",.5*other.probability+.25)]:
        part=other.copy()
        part["method"]=method
        part["probability"]=probability
        part["brier"]=(part.y-part.probability)**2
        part["absolute_error"]=abs(part.y-part.probability)
        additions.append(part)
    pred=pd.concat([pred,*additions],ignore_index=True)
    summary=[]
    for (room,tol,method),part in pred.groupby(["room","tolerance_deg","method"]):
        per=part.groupby(["feature","image"])[["brier","absolute_error"]].mean()
        perauc=[auc(p.y,p.probability) for _,p in part.groupby(["feature","image"])]
        summary.append(dict(room=room,tolerance_deg=tol,method=method,targets=len(part),
            brier=per.brier.mean(),absolute_error=per.absolute_error.mean(),
            within_target_auc=np.nanmean(perauc)))
    return pred,pd.DataFrame(summary)


def atlas(records):
    by={r["image_code"]:r for r in records if r["quality_usable"]}
    fig,axs=plt.subplots(2,3,figsize=(15,9))
    for j,code in enumerate(MAPS[0]["views"]):
        r=by[code];p=np.array(r["reference_evidence"]["points_1024x512"])
        img=plt.imread(ROOT/r["image_evidence"]["difficulty_record"]["photo"].replace("\\","/"))
        center=float(np.angle(np.exp(p[[6,8],0]*2j*np.pi/1024).mean())%(2*np.pi)*1024/(2*np.pi))
        # Wrap the source panorama for the feature crossing the left/right seam.
        triple=np.concatenate([img,img,img],axis=1)
        for row in range(2):
            ax=axs[row,j];ax.imshow(triple,extent=[-1024,2048,512,0])
            for ix,label,color in [(3,"A","#00ffff"),(4,"B","#ff40ff")]:
                points=p[ix*2:ix*2+2].copy()
                points[:,0]=center+(points[:,0]-center+512)%1024-512
                ax.plot(*points.T,color=color,lw=2);ax.text(points[1,0],points[1,1]+12,label,color=color,fontsize=14,
                    bbox=dict(facecolor="black",alpha=.6,pad=1))
            if row==0:ax.set_xlim(center-512,center+512);ax.set_ylim(512,0)
            else:ax.set_xlim(center-100,center+100);ax.set_ylim(490,140)
            ax.set_title(code+(" 全景环绕显示" if row==0 else "同一实体两端局部"))
    fig.suptitle("G046人工确认：-05的A/B分别与-12/-21的A/B对应，均为同一墙角的两个转折")
    fig.tight_layout();fig.savefig(OUT/"G046_local_correspondence.png",dpi=150);plt.close(fig)


def main():
    plt.rcParams["font.sans-serif"]=["Microsoft YaHei","DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"]=False
    records=read(ROOT/"research/statistics/v2_evidence_audit_20261019/records.json.gz")["records"]
    by={r["image_code"]:r for r in records if r["quality_usable"]}
    relations=pd.read_csv(ROOT/"research/statistics/v2_integrated_analysis_20261019/direct_relation_registry.csv")
    declared={tuple(sorted([r.image_a,r.image_b])):r for r in relations.itertuples()
              if r.physical_adopted and r.scope_comparable and not r.substantive_conflict}
    maps=[]
    for m in MAPS:
        views=list(m["views"])
        for i,a in enumerate(views):
            for b in views[i+1:]:
                assert tuple(sorted([by[a]["image_id"],by[b]["image_id"]])) in declared
        maps.append(dict(**m,correspondence_status="user_confirmed_cross_view_same_corner_20261021" if m["room"]=="G046" else "image_and_reference_supported_by_codex_not_human_confirmed",
            physical_evidence="same vanity/shower/step and L-shaped boundary" if m["room"]=="G046" else "same door, wall control, marble counter and narrow projecting wall",
            necessity="user_confirmed_existing_reference" if m["room"]=="G046" else "existing_reference_no_new_human_necessity_adjudication",
            visibility="vertical wall edge visible; bottom partly cabinet/fixture/stitched-region obscured; visibility is not scored numerically",
            reference_unchanged=True,direct_relations=[dict(image_a=by[a]["image_id"],image_b=by[b]["image_id"],
                adoption_version=declared[tuple(sorted([by[a]["image_id"],by[b]["image_id"]]))].adoption_version)
                for i,a in enumerate(views) for b in views[i+1:]]))
    save("FEATURE_MAP.json",dict(features=maps,unknowns=[
        "G057 other repeated vanity details not mapped; no transitive or full-ring extension",
        "G178 rectangular reference alone cannot disambiguate physical corners; localization work retained separately",
        "No supported doorway or Semi cross-view feature case adopted in this packet",
        "No camera extrinsics found in the inspected local data; reference alignment alone not accepted as identity"]))
    allcodes={c for m in MAPS for c in m["views"]}
    rows=[];coverage=[]
    for code in sorted(allcodes):
        candidates=[r for r in records if r["image_code"]==code and not r["is_oos"]]
        for condition in sorted({r["condition"] for r in candidates}):
            subset=[r for r in candidates if r["condition"]==condition]
            coverage.append(dict(image=code,condition=condition,records=len(subset),
                independent=sum(bool(r["independent_vote_eligible"]) for r in subset),
                geometry=sum(r["geometry_status"]=="surface_valid" for r in subset)))
        for r in candidates:
            if r["condition"]!="manual" or not r["independent_vote_eligible"] or r["geometry_status"]!="surface_valid":
                continue
            ref=by[code]["reference_evidence"]["points_1024x512"]
            assert r["reference_id"]==by[code]["reference_id"]
            for tol in [3,6,9]:
                matched=local_assign(r["points_1024x512"],ref,tol)
                for m in MAPS:
                    if code not in m["views"]:continue
                    ix=m["views"][code]-1;match=matched.get(ix)
                    rows.append(dict(room=m["room"],feature=m["feature"],image_code=code,image_id=r["image_id"],
                        worker_id=r["worker_id"],object_id=r["object_id"],condition=r["condition"],origin=r["origin"],
                        reference_id=r["reference_id"],reference_corner=ix+1,tolerance_deg=tol,hit=int(match is not None),
                        source_pair_index=match["pair_index"] if match else None,
                        dx=match["dx"] if match else None,
                        bottom_dy=r["points_1024x512"][2*match["pair_index"]+1][1]-ref[2*ix+1][1] if match else None,
                        quality_usable=r["quality_usable"]))
    data=pd.DataFrame(rows)
    assert not data.duplicated(["feature","image_code","worker_id","tolerance_deg"]).any()
    save("LOCAL_BEHAVIOR.csv",data);save("CONDITION_COVERAGE.csv",pd.DataFrame(coverage))
    save("VIEW_RATES.csv",data.groupby(["room","feature","image_code","tolerance_deg"]).agg(
        workers=("worker_id","size"),hits=("hit","sum"),rate=("hit","mean")).reset_index())
    predictions=[]
    for (_,_,_),part in data.groupby(["room","feature","tolerance_deg"]):
        for r in part.itertuples():
            h=history_prediction(part,r.worker_id,r.image_code)
            if h is None:continue
            own,other,n=h
            for method,p in [("own_other_views",own),("others_same_source_views",other),("equal_blend",.5*(own+other))]:
                predictions.append(dict(room=r.room,feature=r.feature,image=r.image_code,worker=r.worker_id,
                    object_id=r.object_id,tolerance_deg=r.tolerance_deg,method=method,history_images=n,
                    y=r.hit,probability=p,brier=(r.hit-p)**2,absolute_error=abs(r.hit-p)))
    pred,summary=prediction_tables(pd.DataFrame(predictions))
    save("LOCAL_PREDICTIONS.csv",pred)
    save("PREDICTION_SUMMARY.csv",summary)
    # Fusion states already saved: only read each full common-worker endpoint once.
    cases=read(PARENT/"structure_transfer/case_states.json")
    fusion=[]
    for c in cases:
        code=c["image"]
        if code not in allcodes:continue
        state=c["after"];ref=c["reference"]["points_1024x512"]
        workers={a["worker"] for a in state["assignments"]}
        for tol in [3,6,9]:
            matched=local_assign(state["candidate"]["points"],ref,tol)
            for m in MAPS:
                if code not in m["views"]:continue
                ix=m["views"][code]-1
                raw=data[data.feature.eq(m["feature"])&data.image_code.eq(code)&data.tolerance_deg.eq(tol)&data.worker_id.isin(workers)]
                assert len(raw)==len(workers)
                close=[]
                for g in state["identity_groups"]:
                    dx=(g["center"][0][0]-ref[2*ix][0]+512)%1024-512
                    if abs(dx)*360/1024<=tol:close.append(g)
                fusion.append(dict(room=m["room"],feature=m["feature"],image=code,tolerance_deg=tol,
                    common_workers=len(workers),raw_azimuth_hits=int(raw.hit.sum()),minimum_support=state["minimum_support"],
                    selected_endpoint_hit=int(ix in matched),
                    nearby_groups=len(close),nearby_max_group_support=max([g["support"] for g in close],default=0),
                    nearby_selected_groups=sum(g["selected"] for g in close),
                    endpoint_Q=c["quality_after"],
                    geometry_pointer="structure_transfer/case_states.json#"+code))
    save("FUSION_FEATURE_LINK.csv",pd.DataFrame(fusion))
    atlas(records)
    # One row per actual person; unknown source views remain empty.
    primary=data[data.tolerance_deg.eq(3)]
    fig,axs=plt.subplots(1,2,figsize=(14,12))
    for ax,room in zip(axs,["G046","G057"]):
        p=primary[primary.room.eq(room)].copy()
        p["column"]=p.image_code.str.rsplit("-",n=1).str[-1]+" / "+p.feature.str.replace(room+"_", "", regex=False)
        matrix=p.pivot(index="worker_id",columns="column",values="hit")
        image=ax.imshow(np.ma.masked_invalid(matrix.values),vmin=0,vmax=1,cmap="RdYlGn",aspect="auto")
        ax.set_xticks(range(len(matrix.columns)),matrix.columns,rotation=65,ha="right",fontsize=8)
        ax.set_yticks(range(len(matrix)),matrix.index,fontsize=8);ax.set_title(room+" 局部位置观测（灰白为缺答）")
    fig.suptitle("局部对应观测（G046两端同角已确认）：绿=3°内有角点；红=未命中，不自动等于语义漏标")
    fig.tight_layout();fig.savefig(OUT/"LOCAL_WORKER_BEHAVIOR.png",dpi=150);plt.close(fig)
    save("FIELD_CONTRACT.json",dict(identity="room + feature + image_id + worker_id + object_id + condition",
        map="G046 A/A and B/B across the three named views user-confirmed on 2026-10-21 as two turns of one corner; G057 photo-supported by Codex, not human-confirmed; explicit binding, no propagation",
        hit="unique within-image azimuth match within 3/6/9 degrees; primary 3 preselected; not semantic correctness or bottom accuracy",
        visibility="recorded separately, not inferred from GT hiddenness",
        prediction="target view excluded; other people baseline uses same available source images and excludes target worker; equal blend, constant 0.5 and 0.5*other+0.25 are fixed, not fitted",
        aggregation="feature x target image equal within each room; two rooms reported separately, not inferential population evidence",
        source_pair_index="index in points_1024x512 ordered pair sequence, not raw export order; object_id links coordinate_evidence",
        tables={p.name:list(pd.read_csv(p,nrows=0).columns) for p in OUT.glob("*.csv")}))
    print(pd.DataFrame(summary).to_string(index=False))


if __name__=="__main__":main()
