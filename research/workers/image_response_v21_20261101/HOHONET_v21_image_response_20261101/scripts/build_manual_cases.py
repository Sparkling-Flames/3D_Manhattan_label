#!/usr/bin/env python3
"""Build traceable per-image cases using existing v2.1 paths and cached endpoints only."""
from __future__ import annotations
from pathlib import Path
import base64,gzip,hashlib,json,math,shutil,os
os.environ.setdefault("MPLCONFIGDIR","/tmp/hohonet_response_matplotlib")
import numpy as np,pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
from normalize_manual import save_csv

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/"source/repo/research/data/releases/v2.1"
OUT=ROOT/"stage05_cases/manual"
SNAP={p["pool_id"]:p for p in json.loads((REL/"pools/INPUT_SNAPSHOT.json").read_text())["images"]}
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,"axes.spines.top":False,
 "axes.spines.right":False,"svg.fonttype":"none","pdf.fonttype":42})
COLORS={"W103":"#246A9F","W113":"#CA553D","W134":"#9564A0","FULL35":"#666666"}

def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,float) and not math.isfinite(x):return None
    if x is pd.NA:return None
    return x

def jsave(obj,path):
    b=json.dumps(clean(obj),ensure_ascii=False,allow_nan=False,indent=2).encode()
    path.write_bytes(gzip.compress(b,compresslevel=6,mtime=0) if path.suffix==".gz" else b)
    check=json.loads(gzip.decompress(path.read_bytes()) if path.suffix==".gz" else path.read_text())
    return check

def source_path(name):
    return ROOT/"source/repo"/name

def figsave(fig,path):
    for ext in ["png","pdf","svg"]:
        final=path.with_suffix("."+ext)
        temporary=final.with_name(final.name+f".{os.getpid()}.writing")
        fig.savefig(temporary,format=ext,dpi=180,bbox_inches="tight")
        if ext=="png":
            with Image.open(temporary) as im:im.load()
        os.replace(temporary,final)
    plt.close(fig)
    with Image.open(path.with_suffix(".png")) as im:im.load()
    
def curve(d):
    out=[]
    for k,g in d.groupby("k"):
        q=g.B8L2.dropna();valid=g.quality_valid.astype(bool)
        rec=dict(k=int(k),N=int(g.N.iloc[0]),k_fraction=k/g.N.iloc[0],paths=len(g),
                 unique_teams=g.team_key.nunique(),Q_valid=len(q),
                 Q_mean=q.mean(),Q_p10=q.quantile(.1),Q_p90=q.quantile(.9),
                 Q_sd=q.std(ddof=1),D10_mean=g.D10.mean(),IoU3D100_mean=g.IoU3D100.mean(),
                 complete_evaluable_rate=pd.to_numeric(g.complete_evaluable,errors="coerce").mean(),
                 consensus_not_formed_rate=g.status_class.eq("consensus_not_formed").mean(),
                 output_unscoreable_rate=g.status_class.eq("output_unscoreable").mean(),
                 nodes_mean=g.nodes.mean(),turns_mean=g.turns.mean(),
                 floor_area_h2_mean=g.floor_area_h2.mean(),height_mean_h_mean=g.height_mean_h.mean(),
                 S_bottom_deg_mean=g.S_bottom_deg.mean(),omission_mean=g.omission.mean(),
                 extension_mean=g.extension.mean())
        out.append(rec)
    return pd.DataFrame(out)

def rawpoints(pool):
    rows=[]
    for r in pool["records"]:
        for i,(x,y) in enumerate(r["points"]):
            rows.append(dict(worker=r["worker"],object_id=r["object_id"],point_index=i,
                pair_index=i//2,endpoint="top" if i%2==0 else "bottom",x_1024=x,y_512=y,
                individual_B8L2=r.get("B8L2"),individual_D10=r.get("D10"),
                source_time_seconds=r.get("source_time_seconds"),order_status=r.get("order_status"),
                ring_confirmed=r.get("ring_confirmed")))
    return pd.DataFrame(rows)

def response_plot(c,title,dest,exact=None):
    c=c[c.k.ne(2)];cc=c[c.k.ge(3)]
    fig,ax=plt.subplots(3,1,figsize=(11,9),sharex=True,gridspec_kw={"height_ratios":[1.6,1,1]})
    ax[0].fill_between(cc.k,cc.Q_p10,cc.Q_p90,color="#397EA8",alpha=.15,label="Team P10-P90")
    ax[0].plot(cc.k,cc.Q_mean,"o-",ms=3,color="#235F89",label="Mean B8L2")
    ax[0].plot(cc.k,cc.Q_p10,"--",color="#C7732C",label="P10 B8L2")
    if exact is not None:
        ax[0].plot([34],[exact],"D",color="black",ms=7,label="Exact N-1 finite mean")
    ax[0].set_ylabel("B8L2 quality");ax[0].legend(ncol=2,loc="best",fontsize=9)
    ax[1].plot(cc.k,cc.Q_sd,"o-",ms=3,color="#528C6E");ax[1].set_ylabel("Between-team Q SD")
    ax[2].plot(cc.k,cc.complete_evaluable_rate,"o-",ms=3,color="#235F89",label="Complete & evaluable")
    ax[2].plot(cc.k,cc.consensus_not_formed_rate,"--",color="#B34D46",label="Consensus not formed")
    ax[2].set_ylim(-.03,1.05);ax[2].set_ylabel("Attempt proportion")
    ax[2].set_xlabel("Number of annotators k");ax[2].legend(ncol=2,loc="lower left",fontsize=9)
    for a in ax:a.grid(alpha=.18);a.set_xlim(3,int(c.N.iloc[0]))
    ax[0].set_title(title+" | 256 nested paths per k",loc="left",fontweight="bold")
    if c.loc[c.k.eq(c.N.iloc[0]),"Q_valid"].iloc[0]==0:
        ax[0].annotate("Full pool: no evaluable Q",(int(c.N.iloc[0]),cc.Q_mean.dropna().iloc[-1]),
            xytext=(-185,35),textcoords="offset points",arrowprops={"arrowstyle":"->","color":"#555"},
            color="#555",fontsize=9)
    fig.tight_layout();figsave(fig,dest)

def bev_plot(pool,geometries,endpoints,title,dest):
    ref=np.asarray(pool["reference"]["floor_xz_h"],float)
    fig,axes=plt.subplots(1,len(geometries),figsize=(4*len(geometries),4.7),squeeze=False)
    allpts=[ref]
    for g in geometries:
        if g["geometry"] and g["geometry"].get("footprint"):allpts.append(np.asarray(g["geometry"]["footprint"],float))
    pts=np.concatenate(allpts);lo=pts.min(axis=0)-.35;hi=pts.max(axis=0)+.35
    for ax,g in zip(axes[0],geometries):
        key=g["team_key"];e=next(x for x in endpoints if x["team_key"]==key);label=g.get("label",g.get("absent_worker",""))
        r=np.vstack([ref,ref[0]]);ax.plot(r[:,0],r[:,1],color="black",lw=1.4,label="Current reference")
        geo=g.get("geometry") or {};p=geo.get("footprint")
        if p:
            p=np.asarray(p,float);p=np.vstack([p,p[0]])
            ok=e.get("complete_evaluable",False);col=COLORS.get(g.get("absent_worker",label),"#246A9F")
            ax.plot(p[:,0],p[:,1],color=col,lw=2,ls="-" if ok else "--",marker="o",ms=3,label="Saved fusion")
        q=e.get("B8L2");qtxt="unscoreable" if q is None or not np.isfinite(q) else "B8L2 "+format(q,".2f")
        ax.set_title(label+"\n"+str(e["nodes"])+" nodes; "+qtxt,fontsize=10)
        ax.set(xlim=(lo[0],hi[0]),ylim=(lo[1],hi[1]),xlabel="x / camera height",ylabel="z / camera height")
        ax.set_aspect("equal");ax.grid(alpha=.15);ax.plot(0,0,"+",color="#333",ms=7)
    axes[0,0].legend(fontsize=8,loc="best")
    fig.suptitle(title,fontweight="bold");fig.tight_layout();figsave(fig,dest)

def pano_plot(pool,image_path,geometries,dest):
    im=np.asarray(Image.open(image_path));fig,axes=plt.subplots(2,1,figsize=(14,12))
    datasets=[("Current reference: all saved top-bottom pairs",pool["reference"]["points_1024x512"],"#F1C75B")]
    g=geometries[-1];datasets.append(("Saved fusion ("+g.get("label",g.get("absent_worker","selected team"))+"): all top-bottom pairs",(g["geometry"] or {}).get("points",[]),"#54CFED"))
    for ax,(title,pts,color) in zip(axes,datasets):
        ax.imshow(im,extent=[0,1024,512,0]);p=np.asarray(pts,float)
        for i in range(0,len(p),2):
            ax.plot(p[i:i+2,0],p[i:i+2,1],"-o",lw=1,ms=4,color=color)
            ax.annotate(str(i//2+1),(p[i+1,0],p[i+1,1]),xytext=(4,3),textcoords="offset points",
                color="black",weight="bold",bbox={"fc":"white","alpha":.85,"ec":"none","pad":1},fontsize=8)
        ax.set_title(title,loc="left");ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.set_xlabel("Equirectangular x (1024-pixel convention)");ax.set_ylabel("y (512-pixel convention)")
    fig.tight_layout();figsave(fig,dest)

HTML = r"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>__TITLE__：原图与完整标注</title>
<style>body{font:16px system-ui,sans-serif;margin:24px auto;max-width:1250px;color:#183046;background:#fafbfd}h1{font-size:25px}section{padding:18px;background:white;border:1px solid #dbe3eb;border-radius:9px;margin:15px 0}canvas{width:100%;height:auto;border:1px solid #adbccd}select{font-size:15px;padding:7px;margin:5px}table{border-collapse:collapse;font-size:13px;width:100%}td,th{padding:6px;border-bottom:1px solid #dce3ea;text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}.note{color:#526477;line-height:1.65}.legend span{margin-right:18px}label{margin-right:15px}</style>
<h1>__TITLE__：原图、完整原答与实际融合</h1><p class="note">本页保留冻结目标和实际原始上下点对。画布只画保存的点对，不在全景图上补造墙面连线。平面图与票账见同目录文件；缺失不填零。</p>
<section><label>个人原答<select id="worker"></select></label><label>融合团队<select id="team"></select></label>
<label><input id="gt" type="checkbox" checked>正式参考</label><label><input id="raw" type="checkbox" checked>个人完整点对</label><label><input id="fused" type="checkbox">团队点对</label>
<p class="legend"><span style="color:#BA941D">● 参考</span><span style="color:#DA453E">● 原答</span><span style="color:#008FAE">● 融合</span></p>
<canvas id="c" width="2048" height="1024"></canvas><p id="details" class="note"></p></section>
<section><h2>精确成员与原答身份</h2><pre id="identity"></pre></section><section><h2>已保存的局部支持票</h2><p id="voteNote" class="note"></p><table id="votes"></table></section>
<script>
const DATA=__PAYLOAD__;const IMG="data:image/png;base64,__IMAGE__";const selw=document.getElementById("worker"),selt=document.getElementById("team");
DATA.pool.records.forEach(r=>{const o=document.createElement("option");o.value=r.worker;o.textContent=r.worker+" | "+r.object_id;selw.appendChild(o)});
DATA.geometries.forEach(g=>{const o=document.createElement("option");o.value=g.team_key;o.textContent=g.label||g.absent_worker||g.team_key;selt.appendChild(o)});
if(DATA.pool.records.some(r=>r.worker==="W104"))selw.value="W104";
const im=new Image();im.onload=draw;im.src=IMG;
function points(ctx,p,col,prefix){ctx.lineWidth=2;ctx.strokeStyle=col;ctx.fillStyle=col;ctx.font="20px sans-serif";for(let i=0;i<p.length;i+=2){ctx.beginPath();ctx.moveTo(p[i][0]*2,p[i][1]*2);ctx.lineTo(p[i+1][0]*2,p[i+1][1]*2);ctx.stroke();for(let j=i;j<i+2;j++){ctx.beginPath();ctx.arc(p[j][0]*2,p[j][1]*2,5,0,Math.PI*2);ctx.fill()}ctx.fillText(prefix+String(i/2+1),p[i+1][0]*2+6,p[i+1][1]*2+18)}}
function draw(){const ctx=document.getElementById("c").getContext("2d");ctx.drawImage(im,0,0,2048,1024);
const r=DATA.pool.records.find(x=>x.worker===selw.value),g=DATA.geometries.find(x=>x.team_key===selt.value),e=DATA.endpoints.find(x=>x.team_key===selt.value);
if(document.getElementById("gt").checked)points(ctx,DATA.pool.reference.points_1024x512,"#E5BB3F","G");
if(document.getElementById("raw").checked)points(ctx,r.points,"#F0544D","P");
if(document.getElementById("fused").checked&&g.geometry)points(ctx,g.geometry.points||[],"#45D2EB","F");
document.getElementById("details").textContent="个人 "+r.worker+"：Q="+String(r.B8L2)+"；全部"+String(r.points.length/2)+"点对。当前目标："+DATA.pool.reference.target_id+"。团队 k="+e.k+"，Q="+String(e.B8L2)+"，状态="+String(e.score_status)+"。";
document.getElementById("identity").textContent="team_key: "+e.team_key+"\nworkers: "+(Array.isArray(e.member_workers)?e.member_workers.join(" | "):e.member_workers)+"\nobject_ids: "+(Array.isArray(e.member_object_ids)?e.member_object_ids.join(" | "):e.member_object_ids)+"\nreference: "+DATA.pool.reference.reference_version;
const vv=DATA.votes.filter(x=>x.team_key===selt.value);document.getElementById("voteNote").textContent=vv.some(x=>x.trace_origin==="parity_verified_diagnostic_replay")?"本端点完整候选票账由本轮冻结诊断回放恢复；47项原缓存一致性核对全部通过。正式结果和原缓存未被替换。":(vv.length?"这些票数来自实际保存状态；包括未入选组时明确列出。":"该端点未保存完整候选组票账。不得从所选节点或邻近团队反推未入选组。");
const t=document.getElementById("votes");t.innerHTML="<tr><th>feature</th><th>support</th><th>threshold</th><th>selected</th><th>bottom x</th><th>bottom y</th></tr>";vv.forEach(v=>{const tr=document.createElement("tr");["feature_id","support","minimum_support","selected","bottom_x","bottom_y"].forEach(k=>{const td=document.createElement("td");td.textContent=String(v[k]??"");tr.appendChild(td)});t.appendChild(tr)})}
["worker","team","gt","raw","fused"].forEach(id=>document.getElementById(id).addEventListener("change",draw));
</script></html>"""

def viewer(pool,geometries,endpoints,votes,image_path,out):
    data=clean(dict(pool=pool,geometries=geometries,endpoints=endpoints,votes=votes))
    html=HTML.replace("__TITLE__",pool["meta"]["image"]).replace("__PAYLOAD__",json.dumps(data,ensure_ascii=False,allow_nan=False)).replace("__IMAGE__",base64.b64encode(image_path.read_bytes()).decode())
    (out/"VIEWER.html").write_text(html,encoding="utf8")

def common(pid,folder,image_rel):
    p=SNAP[pid];out=OUT/folder;out.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(ROOT/f"stage02_normalized/manual/pools/{pid}.csv.gz",low_memory=False)
    c=curve(d);save_csv(c,out/"CURRENT_256_CURVE.csv")
    save_csv(d,out/"CURRENT_PATH_PREFIX_VALUES.csv.gz")
    jsave(p,out/"CURRENT_POOL_FULL_INPUT.json.gz");save_csv(rawpoints(p),out/"ALL_RAW_POINT_PAIRS.csv")
    image_path=source_path(image_rel);shutil.copy2(image_path,out/"PANORAMA_ORIGINAL.png")
    for rec in p["records"]:
        rawdir=out/"raw_answers";rawdir.mkdir(exist_ok=True)
        jsave(rec,rawdir/(rec["worker"]+".json"))
    return p,d,c,out,image_path

def vfua():
    pid="VFuaQ6m2Qom-04__manual__fbe40a551f"
    pool,d,c,out,image_path=common(pid,"VFuaQ6m2Qom-04","data/mp3d_layout/valid/img/VFuaQ6m2Qom_5fb269a812f349b4bc2ad5dfac000b85.png")
    src=source_path("research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025/analysis_geometry/case_VFua_04")
    legacy=out/"legacy_evidence";legacy.mkdir(exist_ok=True)
    for f in src.iterdir():
        if f.is_file():shutil.copy2(f,legacy/f.name)
    saved=json.loads(gzip.decompress((src/"VFUA_MECHANISM_GEOMETRY.json.gz").read_bytes()))
    assert saved["pool_id"]==pid
    assert saved["reference"]["target_id"]==pool["reference"]["target_id"]
    np.testing.assert_allclose(saved["reference"]["points_1024x512"],pool["reference"]["points_1024x512"],rtol=0,atol=1e-12)
    np.testing.assert_allclose(saved["reference"]["floor_xz_h"],pool["reference"]["floor_xz_h"],rtol=0,atol=1e-12)
    es=pd.read_csv(src/"VFUA_SELECTED_ENDPOINTS.csv")
    current=d.drop_duplicates("team_key").set_index("team_key")
    matches=[]
    for e in es.to_dict("records"):
        now=current.loc[e["team_key"]]
        for col in ["B8L2","D10","IoU3D100","nodes"]:
            np.testing.assert_allclose([now[col]],[e[col]],atol=1e-10,rtol=0,equal_nan=True)
        assert set(e["member_workers"].split("|"))==set(now.member_workers.split("|"))
        assert set(e["member_object_ids"].split("|"))==set(now.member_object_ids.split("|"))
        matches.append(dict(team_key=e["team_key"],absent_worker=e["absent_worker"],current_v21_match=True,
            paths_current=int(d.team_key.eq(e["team_key"]).sum()),k=int(e["k"])))
    save_csv(pd.DataFrame(matches),out/"CACHED_ENDPOINT_CURRENT_PARITY.csv")
    save_csv(es,out/"SELECTED_CACHED_ENDPOINTS.csv")
    occ=d[d.team_key.isin(es.team_key)].copy();save_csv(occ,out/"SELECTED_TEAM_PATH_OCCURRENCES.csv.gz")
    reps=[]
    for key in es.loc[es.k.eq(34),"team_key"]:
        r=occ[occ.team_key.eq(key)].sort_values(["origin_stratum","replicate_id"]).iloc[0]
        path=d[d.replicate_id.eq(r.replicate_id)].copy();path["selected_endpoint"]=key;reps.append(path)
    save_csv(pd.concat(reps,ignore_index=True),out/"REPRESENTATIVE_COMPLETE_NESTED_PATHS.csv.gz")
    exact=d[d.k.eq(34)].drop_duplicates("team_key").copy()
    assert len(exact)==35
    allworkers=set(pool["records"][i]["worker"] for i in range(35))
    exact["absent_worker"]=exact.member_workers.map(lambda s:next(iter(allworkers-set(s.split("|")))))
    assert exact.absent_worker.nunique()==35
    exact["finite_probability"]=1/35
    save_csv(exact,out/"EXACT_N34_CURRENT_TEAMS.csv")
    exactq=exact.B8L2.dropna()
    votes=pd.read_csv(src/"VFUA_SAVED_GROUP_VOTES.csv")
    diagpath=out/"FULL35_VERIFIED_DIAGNOSTIC_STATE.json.gz"
    diagnostic=json.loads(gzip.decompress(diagpath.read_bytes())) if diagpath.exists() else None
    if diagnostic:
        assert diagnostic["all_parity"]
        votes=pd.concat([votes,pd.read_csv(out/"FULL35_CANDIDATE_GROUP_VOTES.csv")],ignore_index=True)
    checks=[]
    for key,state in saved["selected_full_states"].items():
        sv=votes[votes.team_key.eq(key)].set_index("feature_id")
        selected={n["feature_id"] for n in state["node_consensus"]["nodes"]}
        for g in state["identity_groups"]:
            fid=g["feature_id"];support=len({a["worker"] for a in state["assignments"] if fid in a["feature_ids"]})
            assert support==g["support"]==int(sv.loc[fid,"support"])
            assert (fid in selected)==bool(sv.loc[fid,"selected"])
        checks.append(dict(team_key=key,candidate_groups=len(state["identity_groups"]),
            candidate_supports_verified_from_raw_assignments=True,selected_groups=len(selected)))
    save_csv(pd.DataFrame(checks),out/"VOTE_LEDGER_CHECKS.csv")
    order=["W103","W113","W134","FULL35"]
    geos=sorted(saved["geometries"],key=lambda g:order.index(g["absent_worker"]))
    for g in geos:g["label"]="Full pool (35)" if g["absent_worker"]=="FULL35" else "Without "+g["absent_worker"]+" (34)"
    endpoints=clean(es.to_dict("records"));jsave(dict(current_pool=pool,saved_cases=saved,
        separately_recovered_full35_diagnostic=diagnostic),out/"COMPLETE_CASE_EVIDENCE.json.gz")
    response_plot(c,"VFua-04: late instability and full-pool failure",out/"FIG_VFUA_RESPONSE",exactq.mean())
    bev_plot(pool,geos,endpoints,"VFua-04: near-full teams switch geometry or fail",out/"FIG_VFUA_GEOMETRY")
    pano_plot(pool,image_path,geos,out/"FIG_VFUA_PANORAMA")
    viewer(pool,geos,endpoints,votes.to_dict("records"),image_path,out)
    summary=dict(image="VFuaQ6m2Qom-04",N=35,all_main_paths=256,
        exact_n34_teams=35,exact_n34_scoreable=32,exact_n34_Q_mean=float(exactq.mean()),
        exact_n34_Q_p10=float(exactq.quantile(.1)),exact_n34_Q_sd_population=float(exactq.std(ddof=0)),
        full35_quality_missing=True,full35_complete_evaluable=False,
        full35_candidate_vote_ledger_available=bool(diagnostic),representative_n34_full_states=3,
        full35_ledger_origin="parity_verified_diagnostic_replay" if diagnostic else None,
        full35_parity_checks=len(diagnostic["checks"]) if diagnostic else 0,
        diagnostic_existing_team_replays=1 if diagnostic else 0,
        new_scientific_teams=0,new_natural_paths=0,new_fusions=0,new_scores=0)
    jsave(summary,out/"CASE_RECEIPT.json")
    return summary

def pa4():
    pid="pa4otMbVnkk-11__manual__v21_249"
    pool,d,c,out,image_path=common(pid,"pa4otMbVnkk-11","data/mp3d_layout/valid/img/pa4otMbVnkk_4fbdfc08c934474ea9a04977f9081d0e.png")
    src=REL/"new_space_natural256"/pid
    lookup=json.loads((ROOT/"stage00_manual_sources/PA4_SELECTED_TEAM_LOOKUP.json").read_text())
    endpoints=[];geos=[];votes=[];pointer=[]
    for item in lookup:
        path=src/f"part_{item['part']:05d}.jsonl.gz"
        rows=[json.loads(line) for line in gzip.open(path,"rt")]
        row=next(x for x in rows if x["team_key"]==item["team_key"])
        now=d[d.team_key.eq(row["team_key"])].iloc[0]
        for col in ["B8L2","D10","IoU3D100","nodes"]:
            np.testing.assert_allclose([now[col]],[row[col]],atol=1e-10,rtol=0,equal_nan=True)
        assert set(now.member_workers.split("|"))==set(row["member_workers"])
        endpoints.append(row);geos.append(dict(team_key=row["team_key"],label="k="+str(row["k"]),geometry=row["geometry"]))
        fids=row["geometry"].get("feature_ids",[])
        assert len(row["node_supports"])==row["nodes"]
        for i,n in enumerate(row["node_supports"]):
            p=row["geometry"]["points"][2*i+1]
            votes.append(dict(team_key=row["team_key"],feature_id=fids[i] if i<len(fids) else "selected_"+str(i),
                support=n,minimum_support=row["minimum_support"],selected=True,bottom_x=p[0],bottom_y=p[1],
                ledger_scope="saved selected-node supports; full identity state not saved",
                identity_groups_n=row["identity_groups_n"],unselected_groups_n=row["unselected_groups_n"]))
        pointer.append(dict(team_key=row["team_key"],source_file=str(path.relative_to(ROOT/"source/repo")),
                            line_1based=next(i+1 for i,x in enumerate(rows) if x["team_key"]==row["team_key"])))
    assert all(len(r["points"])//2==8 for r in pool["records"])
    assert all(e["nodes"]==8 and e["identity_groups_n"]==8 and e["unselected_groups_n"]==0 for e in endpoints)
    assert all(all(n==e["k"] for n in e["node_supports"]) for e in endpoints)
    save_csv(pd.DataFrame(pointer),out/"EXACT_ENDPOINT_POINTERS.csv")
    jsave(endpoints,out/"SELECTED_CACHED_ENDPOINTS.json.gz")
    save_csv(pd.DataFrame([{k:v for k,v in e.items() if not isinstance(v,(dict,list))} for e in endpoints]),out/"SELECTED_CACHED_ENDPOINTS_SCALARS.csv")
    save_csv(pd.DataFrame(votes),out/"SAVED_SELECTED_NODE_SUPPORTS.csv")
    rid="new_space256::"+pid+"__new256_0";save_csv(d[d.replicate_id.eq(rid)],out/"REPRESENTATIVE_COMPLETE_NESTED_PATH.csv.gz")
    response_plot(c,"pa4-11: early mean stability at low reference quality",out/"FIG_PA4_RESPONSE")
    bev_plot(pool,geos,endpoints,"pa4-11: stable eight-node expression versus the current reference",out/"FIG_PA4_GEOMETRY")
    pano_plot(pool,image_path,geos,out/"FIG_PA4_PANORAMA")
    viewer(pool,geos,endpoints,votes,image_path,out)
    post=c[c.k.ge(3)]
    summary=dict(image="pa4otMbVnkk-11",N=35,paths_per_k=256,difficulty="中等",
        k3_to_full_mean_Q_range=float(post.Q_mean.max()-post.Q_mean.min()),
        full_B8L2=float(c.loc[c.k.eq(35),"Q_mean"].iloc[0]),
        full_S_bottom_deg=float(c.loc[c.k.eq(35),"S_bottom_deg_mean"].iloc[0]),
        full_complete_evaluable=float(c.loc[c.k.eq(35),"complete_evaluable_rate"].iloc[0]),
        raw_answers=35,raw_answers_with_8_nodes=35,current_reference_nodes=4,
        selected_k=[3,10,20,35],each_selected_node_unanimous=True,full_identity_state_available=False,
        new_fusions=0,new_scores=0)
    jsave(summary,out/"CASE_RECEIPT.json")
    return summary

def polygon_area(poly):
    p=np.asarray(poly,float)
    if len(p)<3:return 0.0
    return float(abs(np.sum(p[:,0]*np.roll(p[:,1],-1)-p[:,1]*np.roll(p[:,0],-1)))/2)

def convex_intersection(subject,clip):
    """Sutherland-Hodgman, used only for validated convex four-corner case polygons."""
    clip=np.asarray(clip,float);out=np.asarray(subject,float)
    signed=np.sum(clip[:,0]*np.roll(clip[:,1],-1)-clip[:,1]*np.roll(clip[:,0],-1))
    orientation=np.sign(signed)
    cross=lambda a,b:float(a[0]*b[1]-a[1]*b[0])
    for poly in [clip,out]:
        e=np.roll(poly,-1,axis=0)-poly
        cc=np.array([cross(e[i],e[(i+1)%len(e)]) for i in range(len(e))])
        assert (cc>=-1e-10).all() or (cc<=1e-10).all(),"case polygon not convex"
    for a,b in zip(clip,np.roll(clip,-1,axis=0)):
        if not len(out):break
        pts=[];prior=out[-1];dp=orientation*cross(b-a,prior-a)
        for cur in out:
            dc=orientation*cross(b-a,cur-a)
            if dc>=-1e-12:
                if dp< -1e-12:pts.append(prior+(cur-prior)*(dp/(dp-dc)))
                pts.append(cur)
            elif dp>=-1e-12:pts.append(prior+(cur-prior)*(dp/(dp-dc)))
            prior=cur;dp=dc
        out=np.asarray(pts,float)
    return out

def case_iou(a,b):
    intersection=polygon_area(convex_intersection(a,b));union=polygon_area(a)+polygon_area(b)-intersection
    return intersection/union

def e9z():
    pid="e9zR4mvMWw7-17__manual__v21_3"
    pool,d,c,out,image_path=common(pid,"e9zR4mvMWw7-17","data/mp3d_layout/test/img/e9zR4mvMWw7_4273c4dd97974531b5256f96204fee47.png")
    src=REL/"new_space_natural256"/pid
    lookup=json.loads((ROOT/"stage00_manual_sources/E9Z_SELECTED_TEAM_LOOKUP.json").read_text())
    endpoints=[];geos=[];votes=[];pointers=[];ref_checks=[]
    ref=pool["reference"]["floor_xz_h"]
    for item in lookup:
        path=src/f"part_{item['part']:05d}.jsonl.gz"
        rows=[json.loads(line) for line in gzip.open(path,"rt")]
        row=next(x for x in rows if x["team_key"]==item["team_key"])
        now=d[d.team_key.eq(row["team_key"])].iloc[0]
        for col in ["B8L2","D10","IoU3D100","nodes"]:
            np.testing.assert_allclose([now[col]],[row[col]],atol=1e-10,rtol=0,equal_nan=True)
        assert set(now.member_workers.split("|"))==set(row["member_workers"])
        assert row["nodes"]==4 and now.turns==4
        assert row["identity_groups_n"]==4 and row["unselected_groups_n"]==0
        assert all(n==row["k"] for n in row["node_supports"])
        observed_iou=case_iou(row["geometry"]["footprint"],ref)
        np.testing.assert_allclose(observed_iou,row["iou_2d"],rtol=0,atol=1e-10)
        ref_checks.append(dict(team_key=row["team_key"],recomputed_reference_iou=observed_iou,
            cached_reference_iou=row["iou_2d"],absolute_difference=abs(observed_iou-row["iou_2d"])))
        endpoints.append(row);geos.append(dict(team_key=row["team_key"],label="k="+str(row["k"]),geometry=row["geometry"]))
        for i,n in enumerate(row["node_supports"]):
            p=row["geometry"]["points"][2*i+1]
            votes.append(dict(team_key=row["team_key"],feature_id=row["geometry"]["feature_ids"][i],
                support=n,minimum_support=row["minimum_support"],selected=True,bottom_x=p[0],bottom_y=p[1],
                ledger_scope="saved selected-node supports; full state not saved",identity_groups_n=4,unselected_groups_n=0))
        pointers.append(dict(team_key=row["team_key"],source_file=str(path.relative_to(ROOT/"source/repo")),
            line_1based=next(i+1 for i,x in enumerate(rows) if x["team_key"]==row["team_key"])))
    pair_rows=[];vertex_rows=[]
    for ai,bi in [(0,1),(1,2),(0,2)]:
        a,b=endpoints[ai],endpoints[bi];p=np.asarray(a["geometry"]["footprint"]);q=np.asarray(b["geometry"]["footprint"])
        # Check positional correspondence over the finite cyclic/reversed orderings.
        options=[(np.sqrt(np.mean(np.sum((p-np.roll(q[::-1] if rev else q,shift,axis=0))**2,axis=1))),rev,shift)
                 for rev in [False,True] for shift in range(4)]
        options.sort();rms,rev,shift=options[0];qq=np.roll(q[::-1] if rev else q,shift,axis=0)
        assert not rev and shift==0 and options[1][0]>rms+1,(a["k"],b["k"],options)
        displacement=np.sqrt(np.sum((p-qq)**2,axis=1))
        centroid=np.hypot(b["centroid_x_h"]-a["centroid_x_h"],b["centroid_z_h"]-a["centroid_z_h"])
        pair_rows.append(dict(k_from=a["k"],k_to=b["k"],team_key_from=a["team_key"],team_key_to=b["team_key"],
            entrants="|".join(sorted(set(b["member_workers"])-set(a["member_workers"]))),
            B8L2_delta=b["B8L2"]-a["B8L2"],D10_delta=b["D10"]-a["D10"],
            node_count_from=a["nodes"],node_count_to=b["nodes"],turn_count_from=4,turn_count_to=4,
            floor_1_minus_iou=1-case_iou(p,q),centroid_distance_h=centroid,
            area_from_h2=polygon_area(p),area_to_h2=polygon_area(q),area_percent_change=100*(polygon_area(q)/polygon_area(p)-1),
            cyclic_matched_corner_rms_h=rms,max_corner_displacement_h=float(displacement.max()),
            cyclic_match_reversed=rev,cyclic_match_shift=shift,next_best_alignment_rms_h=options[1][0],
            S_bottom_deg_delta=b["S_bottom_deg"]-a["S_bottom_deg"],
            Hmean_delta=b["Hmean"]-a["Hmean"],Hcenter_delta=b["Hcenter"]-a["Hcenter"]))
        for i in range(4):vertex_rows.append(dict(k_from=a["k"],k_to=b["k"],corner_index=i,
            x_from=p[i,0],z_from=p[i,1],x_to=qq[i,0],z_to=qq[i,1],displacement_h=displacement[i]))
    save_csv(pd.DataFrame(pair_rows),out/"SAME_COUNT_GEOMETRY_CHANGES.csv")
    save_csv(pd.DataFrame(vertex_rows),out/"CORRESPONDING_CORNER_DISPLACEMENTS.csv")
    save_csv(pd.DataFrame(ref_checks),out/"GEOMETRY_DISTANCE_REFERENCE_PARITY.csv")
    save_csv(pd.DataFrame(pointers),out/"EXACT_ENDPOINT_POINTERS.csv")
    save_csv(pd.DataFrame(votes),out/"SAVED_SELECTED_NODE_SUPPORTS.csv")
    jsave(endpoints,out/"SELECTED_CACHED_ENDPOINTS.json.gz")
    save_csv(pd.DataFrame([{k:v for k,v in e.items() if not isinstance(v,(dict,list))} for e in endpoints]),out/"SELECTED_CACHED_ENDPOINTS_SCALARS.csv")
    rid="new_space256::"+pid+"__new256_225";path=d[d.replicate_id.eq(rid)].copy();save_csv(path,out/"REPRESENTATIVE_COMPLETE_NESTED_PATH.csv.gz")
    response_plot(c,"e9z-17: mean quality and member variation differ",out/"FIG_E9Z_RESPONSE")
    fig,axs=plt.subplots(2,1,figsize=(10,7),sharex=True)
    cc=c[c.k.ge(3)];pp=path[path.k.ge(3)]
    axs[0].plot(cc.k,cc.Q_mean,color="#999999",lw=1.5,label="256-path image mean")
    axs[0].plot(pp.k,pp.B8L2,"o-",color="#276C9D",ms=3,label="One saved entering path")
    axs[0].scatter([11,12,13],[e["B8L2"] for e in endpoints],s=65,color="#D57935",zorder=4,label="Traced teams k=11,12,13")
    axs[0].set_ylabel("B8L2 quality");axs[0].legend(loc="best",fontsize=9)
    axs[1].plot(pp.k,pp.floor_area_h2,"o-",color="#648E58",ms=3,label="Saved floor area")
    axs[1].set_ylabel("Floor area / camera height squared");axs[1].set_xlabel("Number of annotators k")
    axs[1].legend(loc="best",fontsize=9)
    for ax in axs:ax.grid(alpha=.2);ax.set_xlim(3,31);ax.axvspan(10.6,13.4,color="#D57935",alpha=.10)
    axs[0].set_title("e9z-17: four-node outputs can move substantially",loc="left",fontweight="bold")
    fig.tight_layout();figsave(fig,out/"FIG_E9Z_NESTED_PATH")
    bev_plot(pool,geos,endpoints,"e9z-17: four corresponding corners, different positions and scale",out/"FIG_E9Z_GEOMETRY")
    # Shared frame magnifies actual coordinate displacement without changing polygon geometry.
    fig,ax=plt.subplots(figsize=(8,7));rr=np.asarray(ref);rr=np.vstack([rr,rr[0]])
    ax.plot(rr[:,0],rr[:,1],color="black",lw=1.4,label="Current reference")
    for e,col in zip(endpoints,["#276C9D","#D57935","#648E58"]):
        pp=np.asarray(e["geometry"]["footprint"]);pp=np.vstack([pp,pp[0]])
        ax.plot(pp[:,0],pp[:,1],"o-",color=col,label="k="+str(e["k"])+"; Q="+format(e["B8L2"],".2f"),ms=4)
    ax.set_aspect("equal");ax.set_xlabel("x / camera height");ax.set_ylabel("z / camera height");ax.grid(alpha=.2)
    ax.set_title("e9z-17: same four corners move along one entering path",fontweight="bold")
    ax.legend(loc="best");fig.tight_layout();figsave(fig,out/"FIG_E9Z_POSITION_OVERLAY")
    pano_plot(pool,image_path,geos,out/"FIG_E9Z_PANORAMA")
    viewer(pool,geos,endpoints,votes,image_path,out)
    summary=dict(image="e9zR4mvMWw7-17",N=31,paths_per_k=256,difficulty="简单",
        representative_path=rid,selected_k=[11,12,13],all_nodes_and_turns_four=True,
        all_selected_groups_unanimous=True,full_identity_state_available=False,
        new_fusions=0,new_scores=0,new_pair_geometry_measurements=3,pair_changes=pair_rows)
    jsave(summary,out/"CASE_RECEIPT.json");return summary

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    results=[vfua(),pa4(),e9z()]
    jsave(results,OUT/"CASE_BUILD_RECEIPT.json")
    print(json.dumps(results,ensure_ascii=False,indent=2))
if __name__=="__main__":main()

