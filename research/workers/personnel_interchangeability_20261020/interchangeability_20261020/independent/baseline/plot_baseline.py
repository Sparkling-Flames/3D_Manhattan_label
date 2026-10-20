"""Rebuild compact baseline figures from the small balanced result tables only."""
import os
os.environ.setdefault("MPLBACKEND","Agg")
os.environ.setdefault("MPLCONFIGDIR","/tmp/personnel_baseline_mpl")
import argparse,hashlib,io,json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import colors,font_manager
from matplotlib.lines import Line2D
from PIL import Image

ROOT=Path(__file__).resolve().parents[3]
FONT=ROOT/"analysis/fonts/NotoSansSC-Regular.ttf"
if FONT.exists():
    font_manager.fontManager.addfont(str(FONT));plt.rcParams["font.family"]=font_manager.FontProperties(fname=str(FONT)).get_name()
plt.rcParams.update({"axes.spines.top":False,"axes.spines.right":False,"axes.unicode_minus":False,"font.size":10,"axes.titleweight":"bold","savefig.facecolor":"white"})
NAMES={"G":"G：C02 → C01（全局几何反向二类）","R":"R：C05 → C02（全局角色反向五类）"}


def save(fig,path):
    fig.canvas.draw()
    # Freeze the solved constrained layout before the export renderer's second
    # draw; otherwise short m axes can move after the tight bounding box pass.
    fig.set_layout_engine(None)
    b=io.BytesIO();fig.savefig(b,format="png",dpi=180,bbox_inches="tight",pad_inches=.08);raw=b.getvalue();Image.open(io.BytesIO(raw)).verify()
    temp=path.with_name(path.name+".tmp")
    with temp.open("wb") as f:f.write(raw);f.flush();os.fsync(f.fileno())
    temp.replace(path);Image.open(path).verify();plt.close(fig)


def support(g):return g.buildings.ge(3)&g.images.ge(6)


def heatmap(ax,g,field,title,low,high,cmap="viridis",center=None):
    x=np.arange(3,34);y=np.arange(1,int(g.m.max())+1)
    matrix=g.pivot(index="m",columns="k",values=field).reindex(index=y,columns=x).to_numpy(float)
    cm=plt.get_cmap(cmap).copy();cm.set_bad("#edf0f3")
    norm=colors.TwoSlopeNorm(vmin=low,vcenter=center,vmax=high) if center is not None else colors.Normalize(low,high)
    im=ax.imshow(matrix,origin="lower",aspect="auto",extent=[2.5,33.5,.5,len(y)+.5],cmap=cm,norm=norm,interpolation="none")
    bad=g[~support(g)];ax.scatter(bad.k,bad.m,s=4,c="#29333b",marker=".",alpha=.65)
    ax.set(title=title,xlabel="总人数 n",ylabel="替换人数 m",xticks=[3,5,9,13,17,21,25,29,33],yticks=y if len(y)<=5 else [1,3,5,7,9,11]);return im


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--results",type=Path,default=Path(__file__).parent/"results");ap.add_argument("--out",type=Path,default=Path(__file__).parent/"figures");a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    M=pd.read_csv(a.results/"N_M.csv");files=[]
    for target in ("G","R"):
        g=M[M.target.eq(target)]
        fig,axs=plt.subplots(2,2,figsize=(12.6,6.8),layout="constrained")
        panels=[("within_joint_stable_main","同类换人 A→B：主稳定率",0,1,"viridis",None),("cross_joint_stable_main","改类换人 A→C：主稳定率",0,1,"viridis",None),("within_minus_cross_joint_main","同类−改类：主稳定率差",-.55,.55,"RdBu_r",0),("within_minus_cross_geometry_noQ_main","同类−改类：去 Q 几何稳定率差",-.55,.55,"RdBu_r",0)]
        for ax,args in zip(axs.flat,panels):im=heatmap(ax,g,*args);fig.colorbar(im,ax=ax,shrink=.83,pad=.015)
        fig.suptitle(NAMES[target]+"｜所有可行整数人数与替换规模",fontsize=15)
        fig.supxlabel("每图内先平均同 n,m 的抽样，再按图／建筑等权；灰色为不可行；小黑点：不足 6 图或 3 楼。n=2 为原生 deferred，另表保留。",fontsize=9)
        path=a.out/f"{target}_all_integer_stability.png";save(fig,path);files.append(path)
    fig,axs=plt.subplots(2,2,figsize=(12.6,7),layout="constrained")
    for row,target in enumerate(("G","R")):
        g=M[M.target.eq(target)]
        for ax,field,title in zip(axs[row],["net_Q","net_Q_event_p10"],["C−B：建筑等权平均 B8L2 变化","C−B：事件质量变化低 10% 分位"]):
            im=heatmap(ax,g,field,title,-20,20,"RdBu",0);fig.colorbar(im,ax=ax,shrink=.78,pad=.015)
        axs[row,0].set_ylabel(NAMES[target]+"\n替换人数 m")
    fig.suptitle("改类是变好还是变坏：方向与低尾分开看",fontsize=15)
    fig.supxlabel("正值表示改类 C 比同类重抽 B 得分更高。低尾为可评分事件分位，非独立图片分位；失败不补零，分母见小表。",fontsize=9)
    path=a.out/"quality_direction_and_low_tail.png";save(fig,path);files.append(path)
    fig,axs=plt.subplots(2,2,figsize=(12.6,7.6),sharex=True,sharey=True,layout="constrained")
    palette={1:"#087f8c",2:"#d26923",3:"#8052b8",4:"#547c20",8:"#b53755",11:"#545e75"}
    for row,target in enumerate(("G","R")):
        ms=[1,2,4,8,11] if target=="G" else [1,2,3]
        for col,metric in enumerate(("joint_stable_main","geometry_noQ_main")):
            ax=axs[row,col]
            for m in ms:
                g=M[M.target.eq(target)&M.m.eq(m)].sort_values("k")
                for relation,style in (("within","-"),("cross","--")):
                    ax.plot(g.k,g[relation+"_"+metric],style,color=palette[m],lw=1.7,label=f"m={m}" if relation=="within" else None)
                    bad=g[~support(g)];ax.scatter(bad.k,bad[relation+"_"+metric],s=9,color=palette[m],alpha=.4)
            ax.set(ylim=(-.025,1.025),xlim=(3,33),xticks=[3,5,9,13,17,21,25,29,33],title=("主稳定率：含 Q" if col==0 else "去 Q 几何稳定率"),ylabel=NAMES[target] if col==0 else "",xlabel="总人数 n");ax.grid(alpha=.18)
            if col==1:ax.legend(loc="lower right",ncol=2,fontsize=8,title="替换规模（预先选定）",title_fontsize=8)
    fig.suptitle("相同替换规模下增加共同背景：人数与比例曲线",fontsize=15)
    fig.legend(handles=[Line2D([0],[0],color="#31363b",ls="-",label="同类 A→B"),Line2D([0],[0],color="#31363b",ls="--",label="改类 A→C")],loc="outside lower center",ncol=2)
    path=a.out/"nested_background_count_curves.png";save(fig,path);files.append(path)
    S=pd.read_csv(a.results/"SHAPE_N_M.csv")
    fig,axs=plt.subplots(2,2,figsize=(12.6,7.1),layout="constrained")
    for row,target in enumerate(("G","R")):
        g=S[S.target.eq(target)].copy()
        g["shape_gap"]=g.within_geometry_shape_main-g.cross_geometry_shape_main
        g["bottom_gap"]=g.cross_bottom_y_absdiff_deg_p95-g.within_bottom_y_absdiff_deg_p95
        for ax,field,title,v in zip(axs[row],["shape_gap","bottom_gap"],["去冗余真实角／边界：同类−改类稳定率","bottom-y 变化 p95：改类−同类（度）"],[.55,3.]):
            im=heatmap(ax,g,field,title,-v,v,"RdBu_r",0);fig.colorbar(im,ax=ax,shrink=.8,pad=.015)
        axs[row,0].set_ylabel(NAMES[target]+"\n替换人数 m")
    fig.suptitle("并列几何诊断：只看事先登记的元数据子集",fontsize=15)
    fig.supxlabel("此子集按端点、n≈2m 与固定哈希选择，未按效果挑选；新形状阈值未经人工校准，不替换原主判据。",fontsize=9)
    path=a.out/"registered_shape_and_bottom_y.png";save(fig,path);files.append(path)
    receipt=dict(schema="baseline_small_table_figure_rebuild_v1",input_tables={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [a.results/"N_M.csv",a.results/"SHAPE_N_M.csv"]},code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),figures=[dict(file=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files],all_png_verified=True)
    (a.out/"FIGURE_RECEIPT.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")


if __name__=="__main__":main()
