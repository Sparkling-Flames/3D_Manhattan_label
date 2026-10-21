#!/usr/bin/env python3
"""Render small scientific summaries from frozen aggregate tables; no fitting/fusion."""
from pathlib import Path
import hashlib
import json
import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/hohonet_continuation_matplotlib")
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

CONT = Path(__file__).resolve().parents[1]
REPO = CONT.parents[3]
OUT = Path(__file__).resolve().parent
FONT = REPO / "research/workers/personnel_composition_study_20261019/analysis/fonts/NotoSansSC-Regular.ttf"
font_manager.fontManager.addfont(str(FONT))
REPORT_FONT = CONT.parent / "report/assets/HOHONET_Report_Regular.ttf"
font_manager.fontManager.addfont(str(REPORT_FONT))
plt.rcParams.update({"font.family": [font_manager.FontProperties(fname=str(FONT)).get_name(),
                                     font_manager.FontProperties(fname=str(REPORT_FONT)).get_name()],
                     "font.size": 10, "axes.unicode_minus": False,
                     "axes.spines.top": False, "axes.spines.right": False})

def csv_atomic(df, path):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        df.to_csv(f, index=False)
        f.flush()
        os.fsync(f.fileno())
    assert len(pd.read_csv(tmp)) == len(df)
    tmp.replace(path)

def main():
    inputs = [CONT/"n20_abc/checkpointed_manual/summary/N20_MATCHED_PRIMARY_SUMMARY.csv",
              CONT/"n20_abc/results_semi/N20_ABC_PRIMARY_SUMMARY.csv"]
    d = pd.concat([pd.read_csv(p) for p in inputs], ignore_index=True)
    keys = ["condition", "method_id", "tier", "scope"]
    primary = d[d.scope.isin(["all_composition_changes", "within_parent_fine_change"])].copy()
    assert not primary.duplicated(keys + ["metric"]).any()
    metadata = ["events", "images", "buildings", "m_min", "m_max", "all_scored_events", "all_complete_events"]
    wide = primary.groupby(keys, sort=True)[metadata].first()
    for field in ["mean", "valid_events", "valid_buildings", "lo95", "hi95"]:
        piv = primary.pivot(index=keys, columns="metric", values=field)
        piv.columns = [str(c) + "__" + field for c in piv.columns]
        wide = wide.join(piv)
    csv_atomic(wide.reset_index(), OUT/"N20_MATCHED_INTEGRATED_KEY_RESULTS.csv")

    specs = [("manual", "M_structure", "coarse", "Manual · M 粗类"),
             ("manual", "M_structure", "fine", "Manual · M 细类"),
             ("manual", "MV_QTD_manual_new", "coarse", "Manual · QTD 粗类"),
             ("manual", "MV_QTD_manual_new", "fine", "Manual · QTD 细类"),
             ("manual", "A2_relation", "single", "Manual · A2"),
             ("semi", "SP_scale", "coarse", "Semi · SP 粗类"),
             ("semi", "A2_relation", "single", "Semi · A2")]
    fig, axes = plt.subplots(1, 2, figsize=(14, 7.8), gridspec_kw={"width_ratios": [1, 1.1]})
    fig.subplots_adjust(left=.235, right=.965, top=.77, bottom=.18, wspace=.24)
    ys = np.arange(len(specs))[::-1]
    labels = []
    for y, (condition, method, tier, label) in zip(ys, specs):
        r = wide.loc[(condition, method, tier, "all_composition_changes")]
        labels.append(f"{label}\n{int(r.events):,} 对照 / {int(r.buildings)} 栋")
        a, b = r["common_quality_within_abs__mean"], r["common_quality_cross_abs__mean"]
        axes[0].plot([a, b], [y, y], color="#b7c4d0", lw=2.5)
        axes[0].scatter(a, y, color="#167d9a", s=52, label="同构成换人" if y==ys[0] else None, zorder=3)
        axes[0].scatter(b, y, color="#c87722", marker="D", s=40, label="改构成换人" if y==ys[0] else None, zorder=3)
        for off, metric, color, marker, name in [(.12, "stable_advantage", "#167d9a", "o", "B8L2"),
                                                (-.12, "stable_D10_advantage", "#c87722", "s", "D10")]:
            mean = 100*r[metric+"__mean"]
            lo, hi = 100*r[metric+"__lo95"], 100*r[metric+"__hi95"]
            axes[1].scatter(mean, y+off, color=color, marker=marker, s=35, zorder=3,
                            label=name if y==ys[0] else None)
            if np.isfinite(lo) and np.isfinite(hi):
                axes[1].plot([lo,hi],[y+off,y+off], color=color, lw=1.8)
    axes[0].set_yticks(ys, labels)
    axes[1].set_yticks(ys, [""]*len(ys))
    for ax in axes:
        ax.set_ylim(-.65, len(specs)-.35)
        ax.grid(axis="x", alpha=.16)
        ax.set_axisbelow(True)
        ax.legend(loc="upper left", bbox_to_anchor=(0,1.17), frameon=False, ncol=2)
    axes[0].set_xlabel("平均绝对 B8L2 变化（分）")
    axes[0].set_xlim(left=0)
    axes[1].axvline(0,color="#687786",lw=.8)
    axes[1].set_xlabel("联合稳定率：同构成 − 改构成（百分点）")
    fig.suptitle("20人匹配对照：质量变幅与联合形状稳定是不同用途", x=.04, ha="left", y=.975, fontsize=17)
    fig.text(.04,.915,"各事件对齐共同背景、总人数20与实际换人数m≥4；事件→池→图→建筑等权。",color="#536476",fontsize=11)
    fig.text(.04,.86,"比较来自各方法自己的冻结成员面板，不能据此给不同方法作统一排序。",color="#536476",fontsize=11)
    fig.text(.04,.08,"左图只使用三队均可评分的共同分母；右图保留失败，线段为建筑层描述性95%区间，SP仅2栋故不画区间。",fontsize=10,color="#536476")
    fig.text(.04,.038,"M细层全部对照含跨父类变化；保持父构成不变的679个对照另列。细类的质量波动信号不等于普遍几何可互换。",fontsize=10,color="#536476")
    fig.savefig(OUT/"N20_同构成与改构成_质量和形状.png",dpi=170,facecolor="white")
    plt.close(fig)

    time_rows=[]
    models=["coarse_source","fine_source","QT_source","QT_moments_source"]
    names=["多变量粗类","多变量细类","连续 Q/T","连续 Q/T\n＋个人二阶矩"]
    fig,axes=plt.subplots(1,2,figsize=(13,6.4),sharey=True)
    fig.subplots_adjust(left=.07,right=.97,top=.74,bottom=.22,wspace=.15)
    for ax, condition, label in zip(axes,["manual","semi"],["Manual：125图 / 22栋 / 46,436队", "Semi：12图 / 9栋 / 233队"]):
        path=CONT/"n20_analysis"/condition/"N20_PREDICTION_SUMMARY.csv"
        inputs.append(path)
        q=pd.read_csv(path)
        q=q[(q.support_scope=="common_new_anchor")&(q.target_panel=="all")&
            (q.outcome=="log_source_time_total")&(q.method_id.str.startswith("MV_"))&q.model.isin(models)]
        assert len(q)==8
        time_rows.append(q)
        for offset, weighting, color, legend in [(-.18,"configuration_uniform","#167d9a","配置等权"),
                                                  (.18,"member_universe_estimate","#8db9bc","成员宇宙抽样估计")]:
            vals=[q[(q.weighting==weighting)&(q.model==m)].iloc[0].R2_relative_to_pool_mean for m in models]
            bars=ax.bar(np.arange(4)+offset,vals,width=.34,color=color,label=legend)
            for bar,val in zip(bars,vals):
                ax.text(bar.get_x()+bar.get_width()/2,val+.015,f"{val:.3f}",ha="center",fontsize=9)
        ax.set_xticks(np.arange(4),names)
        ax.set_title(label,fontsize=12,pad=14)
        ax.axhline(0,color="#687786",lw=.8)
        ax.set_ylim(-.045,.75)
        ax.grid(axis="y",alpha=.15)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("楼外相对时间响应 R²")
    axes[0].legend(loc="upper left",frameon=False)
    fig.suptitle("效率细类有增量，连续历史特征提供更充分的成本解释",x=.04,ha="left",y=.97,fontsize=17)
    fig.text(.04,.885,"同一条件内使用相同团队；目标建筑外标签与特征，固定模型，不按目标结果挑选配比。",color="#536476",fontsize=10.5)
    fig.text(.04,.09,"时间 = 20人兼容来源记录秒数之和的自然对数；不是并行等待时间。响应减去目标池实际均值，不能当新图绝对时间预测。",fontsize=10,color="#536476")
    fig.text(.04,.04,"成员宇宙值来自每配置至多3队的加权估计，未穷举全体成员组合。Semi可比人数21–22，近满员条件保留。",fontsize=10,color="#536476")
    fig.savefig(OUT/"N20_效率细类与连续特征.png",dpi=170,facecolor="white")
    plt.close(fig)
    csv_atomic(pd.concat(time_rows,ignore_index=True),OUT/"N20_TIME_RESPONSE_KEY_RESULTS.csv")
    receipt={"new_fusion_calls":0,"new_model_fits":0,"inputs":{str(p.relative_to(CONT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
             "outputs":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob("N20_*") if p.suffix in {".csv",".png"}}}
    (OUT/"SUMMARY_FIGURES_RECEIPT.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"tables":len(wide),"time_rows":sum(map(len,time_rows)),"figures":2},ensure_ascii=False))

if __name__ == "__main__":
    main()
