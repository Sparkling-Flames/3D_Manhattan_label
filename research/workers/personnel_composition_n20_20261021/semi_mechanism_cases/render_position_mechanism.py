#!/usr/bin/env python3
"""Plot actual observations behind one selected position group in each arm."""
from __future__ import annotations
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "/tmp/hohonet_deps")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/hohonet_n20_matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent.parent
ROOT=STUDY.parents[2]
FONT=ROOT/"research/workers/personnel_composition_study_20261019/analysis/fonts/NotoSansSC-Regular.ttf"


def main():
    plt.rcParams["font.family"]=FontProperties(fname=str(FONT)).get_name()
    from matplotlib import font_manager
    font_manager.fontManager.addfont(str(FONT))
    plt.rcParams["font.size"]=10
    plt.rcParams["axes.unicode_minus"]=False
    files=[HERE/"cases/N20_SP_q9_positive_m15.json.gz",HERE/"cases/N20_SP_q9_counterexample_m13.json.gz"]
    cases=[json.loads(gzip.decompress(p.read_bytes())) for p in files]
    fig,axes=plt.subplots(2,3,figsize=(13,7),sharex=True,sharey=True)
    rows=[]
    colors={"SP_LOW":"#ae5c29","SP_OTHER":"#216f98"}
    for i,case in enumerate(cases):
        byclass={m["worker_id"]:m["class_id"] for m in case["members"]}
        for j,t in enumerate(case["teams"]):
            group=min((g for g in t["full_state"]["identity_groups"] if g["selected"]),
                      key=lambda g:abs(g["center"][1][0]-460))
            # The local group is selected by a disclosed x-coordinate query.
            # Its immutable observation keys, not the local node number, are
            # retained in the source table for verification across endpoints.
            members=sorted(group["members"],key=lambda m:(m["points"][1][1],m["worker"]))
            ys=np.array([m["points"][1][1] for m in members])
            median=float(np.median(ys))
            assert abs(median-group["center"][1][1])<1e-10
            ax=axes[i,j]
            for rank,m in enumerate(members,1):
                cl=byclass[m["worker"]]
                ax.scatter(rank,m["points"][1][1],color=colors[cl],s=38,zorder=3,
                           marker="D" if cl=="SP_LOW" else "o")
                rows.append(dict(case_id=case["case_id"],arm=t["label"],
                    local_feature_id=group["feature_id"],record_id=m["id"],pair_index=m["pair_index"],
                    worker_id=m["worker"],class_id=cl,bottom_y_px=m["points"][1][1],
                    rank=rank,median_bottom_y_px=median,support=group["support"],
                    minimum_support=t["minimum_support"]))
            ax.axhline(median,color="#b33342",linewidth=1.5,linestyle="--")
            ax.text(.03,.94,f"底点中位数 {median:.2f}px\n支持 {group['support']} / 门槛 {t['minimum_support']}",
                    transform=ax.transAxes,va="top",color="#343c47",fontsize=9,
                    bbox=dict(facecolor="white",edgecolor="none",alpha=.88))
            label={"A":"基准团队","B":"同构成换人","C":"改构成换人"}[t["label"]]
            ax.set_title(f"{t['label']} {label} | LOW {t['counts'].get('SP_LOW',0)}人\nB8L2 {t['B8L2']:.2f}",pad=9)
            ax.set_xlim(.4,20.6);ax.set_xticks([1,5,10,15,20])
            ax.grid(alpha=.18,zorder=0)
            if j==0:
                ax.set_ylabel(("支持型个例 m=15" if i==0 else "反例 m=13")+"\n原答底点 ERP y（像素）")
            if i==1:
                ax.set_xlabel("该位置组内观察，按底点 y 排序")
    ylo=min(r["bottom_y_px"] for r in rows)-3
    yhi=max(r["bottom_y_px"] for r in rows)+3
    for ax in axes.ravel():
        ax.set_ylim(ylo,yhi)
    assert all(ylo<r["bottom_y_px"]<yhi for r in rows)
    fig.suptitle("同一类别人数并不固定坐标中位数：q9-15 的两个20人匹配对照",x=.055,ha="left",fontsize=16,y=.98)
    fig.text(.055,.905,"只看约 x=460 的选中位置组；两例均输出4个角点，门槛均为10，所有共同观察的同组关系均未改变。",fontsize=10,color="#526477")
    handles=[plt.Line2D([0],[0],marker="D",color="none",markerfacecolor=colors["SP_LOW"],markeredgecolor=colors["SP_LOW"],label="SP_LOW 较低推导高度"),
             plt.Line2D([0],[0],marker="o",color="none",markerfacecolor=colors["SP_OTHER"],markeredgecolor=colors["SP_OTHER"],label="SP_OTHER 其余尺度表达"),
             plt.Line2D([0],[0],color="#b33342",linestyle="--",label="实际融合坐标中位数")]
    fig.legend(handles=handles,ncol=3,loc="lower left",bbox_to_anchor=(.05,.038),frameon=False)
    fig.text(.055,.012,"ERP坐标为1024×512；这里只解释局部位置，不把整队变化归因于单一类别。案例为结果后选，全部成员与票账另存。",fontsize=9,color="#526477")
    fig.subplots_adjust(left=.075,right=.985,top=.82,bottom=.16,wspace=.18,hspace=.42)
    out=HERE/"figures/N20_SP_q9_coordinate_medians.png"
    fig.savefig(out,dpi=170,facecolor="white")
    plt.close(fig)
    table=HERE/"POSITION_MEDIAN_OBSERVATIONS.csv"
    pd.DataFrame(rows).to_csv(table,index=False,encoding="utf-8-sig")
    assert len(pd.read_csv(table))==len(rows)
    receipt=dict(rows=len(rows),all_six_medians_equal_native=True,all_observations_in_axis_bounds=True,
        groups_selected="selected identity group closest to ERP x=460 per arm",
        group_ids_not_assumed_portable=True,no_fusion_or_scoring=True,
        image_sha256=hashlib.sha256(out.read_bytes()).hexdigest())
    (HERE/"POSITION_MEDIAN_RECEIPT.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=="__main__":
    main()
