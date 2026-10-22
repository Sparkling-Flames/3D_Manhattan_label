"""Export practical conditions, component tables, selected cases and static plot."""
from register_semi_closure import *


def main():
    summaries=pd.read_csv(HERE/"CONDITION_RESPONSES.csv")
    main=summaries[summaries.analysis_layer.eq("source_partition_expansion")]
    counts=pd.read_csv(HERE/"FAILURE_AND_QUALITY_TAIL_COUNTS.csv")
    choices={
        "n12_m4":("优先采用：质量与效率兼顾","源类至少8人、目标类至少4人；多数图和楼升质，5图均节时"),
        "n14_m3":("优先采用：覆盖较广的定向换类","7图5楼支持，5图4楼升质，全部图楼节时"),
        "n14_m4":("采用：效率和较低质量损失风险","全部4图平均Q损失均不到1分；不写成多数图片必然升质"),
        "n16_m3":("采用：较大团队的效率方案","3/5图升质，全部5图节时；较大质量损失较少"),
        "n10_m3":("补充：较小团队规模响应","平均升质节时，源队存在失败和较高低尾"),
        "n12_m3":("补充：三人块的规模响应","平均升质节时，但质量低尾高于n14/m3、n16/m3"),
        "n10_m4":("风险对照，不作升质优先方案","时间节省较大，只有2/5图平均升质，较大质量损失较多"),
        "n13_m4":("单图完整枚举机制证据","仅7y-13；70有向ABC全部穷举，不能泛化成普遍13人队建议"),
        "n15_m3":("补充：容量边界与成员机制","仅2图2楼，节时较小且源成员波动较大")}
    rows=[]
    for key,(decision,reason) in choices.items():
        z=main[main.condition_id.eq(key)]
        if not len(z):continue
        row=z.iloc[0].to_dict()
        n,m=[int(x[1:]) for x in key.split("_")]
        row.update(classification_method="V3_JOINT_QT",input_condition="Semi自身历史",evaluation_condition="Semi",
                   class_level="楼外粗类，逐折按历史中心解释，K编号不跨折硬拼",personnel_domain="new_only_labelled",
                   source_semantics="相对于目标类，楼外历史Q较低且相对记录时间较长的源类",
                   target_semantics="楼外历史Q较高且更快；多数方向的转折/短边历史也较多",
                   n=n,m=m,replacement_fraction=m/n,class_seat_change=f"源类−{m}，目标类+{m}",
                   common_background_rule=f"三队共用完全相同的{n-m}人D，X/Y/Z各{m}人且四块不交",
                   adoption=decision,adoption_reason=reason,
                   direction_guard="另查实际可用人员楼外历史均值；7y两图K1→K2存在Q方向反号，原结果保留并单列解释",
                   interpretation="效率及定向质量用途成立；该源类内部的绝对Q变化通常比跨到目标类更大",
                   exact_members_file="EVENTS_REGISTERED_ALL.csv.gz",
                   quality_weighting="源划分→背景→成员储备→方向/n/m格→图片→建筑等权",
                   time_provenance="source record seconds, user_processed_reported_not_raw_log_replayed; sum then log ratio",
                   validation_status="v2内部冻结楼外类别与新成员/背景检查；未称外部盲测")
        risk=counts[(counts.analysis_layer.eq("source_partition_expansion"))&counts.condition_id.eq(key)]
        if len(risk):row.update({"raw_"+k:v for k,v in risk.iloc[0].to_dict().items() if k not in ["analysis_layer","condition_id"]})
        guarded=main[main.condition_id.eq("available_history_"+key)]
        if len(guarded):
            row.update({"available_history_check_"+k:guarded.iloc[0][k] for k in ["physical_ABC","images","buildings","net_B8L2","net_D10","net_recorded_time_pct","images_Q_improved","buildings_Q_improved","images_time_reduced","buildings_time_reduced"]})
            row["available_history_check_status"]="后验解释性条件检查，仅使用楼外历史与可用成员；另报而不替换冻结主结果"
        rows.append(row)
    write(HERE/"EFFECTIVE_SEMI_CONDITIONS.csv",pd.DataFrame(rows))
    components=["condition_id","physical_ABC","images","buildings","net_B8L2","net_D10","net_IoU3D100","net_iou_2d",
                "net_S_bottom_deg","net_dir","net_Hmean","net_Hcenter","net_omission","net_extension","net_height_mean_ratio",
                "net_top_y_mean_px","net_bottom_y_mean_px","net_nodes","net_fusion_short_turn_edges","net_fusion_redundancy_n",
                "net_ref_node_recall_9","net_ref_edge_recall_9","net_recorded_time_pct","net_loss_gt5","net_loss_gt10"]
    write(HERE/"KEY_COMPONENT_RESPONSES.csv",main[main.condition_id.isin(["all_registered_n_m",*choices,"difficulty_中等","difficulty_简单"])][components])
    e=pd.read_csv(HERE/"EVENTS_COMPLETE.csv.gz",low_memory=False)
    ids=[("efficiency_same_output","b3ea1be32dde2004e09bb43f"),
         ("position_improvement_same_nodes","b811ba12eb7033aa4cf18f8a"),
         ("position_loss_same_nodes","6b08426576f01bdfebc4009c"),
         ("background_failure_all_classes","06148ea45fcbd70a29cd2ada"),
         ("source_failure_target_recovers","547ad721db2e1775090aa907")]
    cases=[]
    for role,eid in ids:
        row=e[e.event_id.eq(eid)].iloc[0].to_dict()
        row["case_role"]=role
        cases.append(row)
    write(HERE/"SELECTED_CASES.csv",pd.DataFrame(cases))
    plot(main)


def plot(main):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    order=["n10_m3","n12_m3","n14_m3","n16_m3","n10_m4","n12_m4","n14_m4"]
    d=main.set_index("condition_id").loc[order]
    x=np.arange(len(d));colors=["#277DA1"]*4+["#D68C22"]*3
    plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False,"figure.facecolor":"white"})
    fig,axs=plt.subplots(2,2,figsize=(12.6,8.0),constrained_layout=True)
    labels=[x.replace("_", " / ").replace("n", "n=").replace("m", "m=") for x in order]
    ax=axs[0,0]
    ax.bar(x,d.net_B8L2,color=colors)
    for i,(_,r) in enumerate(d.iterrows()):
        ax.text(i,r.net_B8L2+.08,f"{int(r.images_Q_improved)}/{int(r.images_Q_evaluable)} images",ha="center",fontsize=8)
    ax.set_ylabel("Mean change in B8L2 points")
    ax.set_title("A  Cross-class net quality: C minus source mean",loc="left")
    ax=axs[0,1]
    ax.bar(x,-d.net_recorded_time_pct,color=colors)
    for i,(_,r) in enumerate(d.iterrows()):
        ax.text(i,-r.net_recorded_time_pct+.2,f"{int(r.images_time_reduced)}/{int(r.images_time_evaluable)}",ha="center",fontsize=8)
    ax.set_ylabel("Reduction in summed record time (%)")
    ax.set_title("B  Recorded-time savings",loc="left")
    ax=axs[1,0]
    ax.bar(x,d.net_loss_gt5*100,color=colors)
    ax.set_ylabel("Weighted source comparisons with Q loss > 5 (%)")
    ax.set_title("C  Downside risk remains condition-dependent",loc="left")
    ax=axs[1,1]
    ax.bar(x-.18,d.common_quality_within_abs,width=.36,color="#696D7D",label="Same class |B-A|")
    ax.bar(x+.18,d.common_quality_cross_abs,width=.36,color="#66A182",label="Cross class |C-A|")
    ax.set_ylabel("Mean absolute B8L2 change")
    ax.set_title("D  Smaller cross-class variation in this direction",loc="left")
    ax.legend(fontsize=9,frameon=False)
    for ax in axs.flat:
        ax.set_xticks(x,labels,rotation=45,ha="right")
        ax.grid(axis="y",alpha=.18)
        ax.set_axisbelow(True)
    fig.suptitle("Semi own joint classes: useful quality-time conditions on real v2 data",fontsize=16)
    fig.supxlabel("Outside-building labels; source-partition layer; image then building equal weights. Supported image pools differ by n/m.",fontsize=9)
    dest=HERE/"figures";dest.mkdir(exist_ok=True)
    fig.savefig(dest/"semi_exchange_quality_time_risk.png",dpi=180)
    fig.savefig(dest/"semi_exchange_quality_time_risk.pdf")
    plt.close(fig)


if __name__=="__main__":
    main()
