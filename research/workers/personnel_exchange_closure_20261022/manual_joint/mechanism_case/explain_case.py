"""Explain saved Manual-joint ABC and metadata. No fusion and no scoring."""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path
import uuid

import pandas as pd

HERE = Path(__file__).resolve().parent


def write_bytes(path: Path, data: bytes):
    temporary = path.with_name(path.name + ".tmp_" + uuid.uuid4().hex)
    with temporary.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    actual = path.read_bytes()
    assert actual == data, (path, len(actual), len(data))


def write_csv(name, rows):
    write_bytes(HERE / name, pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig"))


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)] +
                     ["| " + " | ".join(map(str, row)) + " |" for row in rows])


def main():
    event = pd.read_csv(HERE / "EXACT_EVENT.csv.gz").iloc[0]
    metrics = pd.read_csv(HERE / "ENDPOINT_METRICS.csv.gz").set_index("arm")
    groups = pd.read_csv(HERE / "GROUP_VOTES.csv.gz")
    observations = pd.read_csv(HERE / "OBSERVATION_ASSIGNMENTS.csv.gz")
    background = set(event.common_background.split("|"))
    selected = []
    for corner in [3, 4, 7, 8]:
        row = dict(reference_corner=corner)
        sets = {}
        for arm in "BC":
            # Separate identity groups are never added together to reach the threshold.
            candidates = groups[(groups.arm == arm) & (groups.nearest_reference_corner == corner)]
            group = candidates.sort_values(["support", "paired_bound_distance_deg"], ascending=[False, True]).iloc[0]
            members = observations[(observations.arm == arm) & (observations.group == group.group)]
            bg = members[members.worker.isin(background)]
            block = members[~members.worker.isin(background)]
            sets[arm] = set(zip(bg.worker, bg.object_id, bg.pair_index))
            row.update({arm + "_group": group.group, arm + "_support": int(group.support),
                        arm + "_threshold": int(group.threshold), arm + "_background_votes": len(bg),
                        arm + "_replacement_votes": len(block), arm + "_selected": bool(group.selected),
                        arm + "_paired_bound_distance_deg": float(group.paired_bound_distance_deg),
                        arm + "_background_workers": "|".join(sorted(bg.worker)),
                        arm + "_replacement_workers": "|".join(sorted(block.worker)),
                        arm + "_member_workers": "|".join(sorted(members.worker))})
        row["same_background_observation_keys"] = sets["B"] == sets["C"]
        selected.append(row)
    assert all(r["same_background_observation_keys"] for r in selected)
    write_csv("LOCAL_OPPORTUNITY_VOTES.csv", selected)

    fields = [
        ("B8L2", "总体Q", "分", "higher"), ("D10", "D10", "分", "higher"),
        ("IoU3D100", "三维IoU代理×100", "分", "higher"), ("iou_2d", "底面IoU", "比例", "higher"),
        ("S_bottom_deg", "底点角度项", "度", "lower"), ("dir", "方向正交残差", "度", "lower"),
        ("Hmean", "高度均值项", "冻结评分单位", "lower"), ("Hcenter", "高度中心项", "冻结评分单位", "lower"),
        ("omission", "遗漏", "比例", "lower"), ("extension", "外扩", "比例", "lower"),
        ("nodes", "节点数", "个", "not_monotonic"), ("ref_node_recall_9", "参考节点9°召回诊断", "比例", "diagnostic"),
        ("ref_edge_recall_9", "参考边9°召回诊断", "比例", "diagnostic"),
        ("height_mean_h", "平均高度", "相机高度", "not_monotonic"),
        ("top_y_mean_px", "顶界平均y", "1024×512像素", "not_monotonic"),
        ("bottom_y_mean_px", "底界平均y", "1024×512像素", "not_monotonic"),
        ("source_time_total_seconds", "库存记录时间之和", "秒", "lower")]
    changes = []
    for field, label, unit, good in fields:
        a, b, c = (float(metrics.loc[arm, field]) for arm in "ABC")
        changes.append(dict(field=field, meaning=label, unit=unit, favorable_direction=good,
                            A=a, B=b, C=c, B_minus_A=b-a, C_minus_A=c-a,
                            C_minus_B=c-b, C_minus_source_mean=c-(a+b)/2))
    write_csv("ABC_COMPONENT_CHANGES.csv", changes)
    q = {r["field"]: r for r in changes}
    metric_rows = [[r["meaning"], f'{r["A"]:.4f}', f'{r["B"]:.4f}', f'{r["C"]:.4f}', f'{r["C_minus_B"]:+.4f}']
                   for r in changes if r["field"] in {"B8L2", "D10", "IoU3D100", "iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter", "omission", "extension", "nodes", "source_time_total_seconds"}]
    vote_rows = [[f'r{r["reference_corner"]}', f'{r["B_background_votes"]}+{r["B_replacement_votes"]}={r["B_support"]}',
                  f'{r["C_background_votes"]}+{r["C_replacement_votes"]}={r["C_support"]}',
                  "进入" if r["C_selected"] and not r["B_selected"] else "仍未进入", "相同"] for r in selected]
    time_pct = (metrics.loc["C", "source_time_total_seconds"] / metrics.loc["B", "source_time_total_seconds"] - 1) * 100
    report = f'''# Manual 联合分类的真实机制案例：同一背景下补票与定位取舍

本例确实属于 **Manual 结构＋Q/T 联合分类 `V3_JOINT_QT`**，采用排除 B6ByNegPMKs 建筑的既有楼外标签。不是把结构单域分类案例改名。底层数据、原答、参考及冻结融合/质量算法均为 v2。类别编号只对本折有效。

## 1. 研究对象与精确三队

- 图片：`B6ByNegPMKs-47`；事件：`{event.event_id}`；阶段 A，n=20、m=4，实际替换比例20%。
- 方向：本折 J2→J5，目标类在训练折中历史Q较高、相对源类更快；方向由楼外历史登记，未用目标图Q定义。
- A、B 类别人数均为 `{event.A_counts}`；C 为 `{event.C_counts}`，即用4席 J5 替换4席 J2。
- D（16人）：`{event.common_background}`。
- X（原队源类4人）：`{event.outgoing_block_X}`。
- Y（同类替换4人）：`{event.same_count_block_Y}`。
- Z（跨类替换4人）：`{event.changed_count_block_Z}`。
- A=D+X，B=D+Y，C=D+Z。D、X、Y、Z 互不重叠；所有三种比较实际均换4人。

原队源块X的原答节点数为8、7、9、7，同类块Y为7、6、7、7，目标块Z四人均为10。下图显示每人的完整原答；较多节点具体落在左侧回折和中央薄墙两侧，而不是只凭总节点数给它们“正确”评价。

![源类X、同类Y、目标类Z的原答ERP/BEV/3D叠加](figures/raw_three_views.png)

## 2. 原答如何通过对应与票数改变融合

本队人数20，冻结节点最低支持为10票。对同一可见结构机会，记录各队最高支持的对应组，不把不同身份组的票数相加。r3/r4 对应图像左侧墙面回折；r7/r8 对应中央伸出的薄墙两侧。ERP图上黄色为冻结参考，原图可见这些回折/墙面边缘。

{table(["参考机会", "B：D票＋Y票", "C：D票＋Z票", "C变化", "D原观察集合"], vote_rows)}

**r4 从8票增至10票，r7 从6票增至10票，两个节点跨过门槛进入C。** r4的Y贡献只有W110；Z贡献W109、W126、W130。W102对应的近邻原观察落入另一个身份组，本例没有把它并到r4凑票。r7的Z四人均贡献一票。r3和r8虽然也增加支持，仍分别为9票和8票，尚未进入。

四处B/C的共同背景不仅成员相同，`(worker, object_id, pair_index)` 原观察集合也完全相同。因此本例两处入选可以追到替换块新增的支持，不必借“共同背景被重新分组”解释。精确观察归属见 `OBSERVATION_ASSIGNMENTS.csv.gz`；各组中心、票数与入选状态见 `GROUP_VOTES.csv.gz`；连接直接/投影支持见 `EDGE_VOTES.csv.gz`。

这是**真实结构得到部分补充**的案例。相邻另一侧r3/r8仍不足票，不能说C已完整恢复该结构。C虽有8个有效节点，连接后仍在范围和局部形状上有代价。

## 3. 更好与变化更大分别看

{table(["指标", "A", "B", "C", "C−B"], metric_rows)}

Q的四种有符号变化为：B−A **{q['B8L2']['B_minus_A']:+.4f}**，C−A **{q['B8L2']['C_minus_A']:+.4f}**，C−B **{q['B8L2']['C_minus_B']:+.4f}**，C−(A+B)/2 **{q['B8L2']['C_minus_source_mean']:+.4f}**。D10对应分别为 **{q['D10']['B_minus_A']:+.4f}、{q['D10']['C_minus_A']:+.4f}、{q['D10']['C_minus_B']:+.4f}、{q['D10']['C_minus_source_mean']:+.4f}**。三队均形成有效可评分终点。

**C相对同类替换B的Q提高3.365分，D10提高4.372分，记录时间减少{abs(time_pct):.3f}%。** 底点角度、方向正交残差、两个高度评分项改善，并补入两个结构节点。但是C仍比原队A低1.023分；三维IoU代理、底面IoU、遗漏和外扩均比B差。图中长廊一端的外扩、另一侧未入选的回折使“结构节点补充”与“底面更接近参考”没有同步成立。这里的方向项是正交轴残差，不是独立测得的GT旋转角误差。

总记录时间是同来源既有作答秒数之和，A/B/C分别约57.04、54.72、54.34分钟；不是本轮新测的生产耗时。3D图按相机高度归一，顶部距离从配对底点射线推导，不是实测房高。

![相同视角与坐标尺度下三队融合](figures/comparison.png)

## 4. 案例用途与复现

本例在全部结果已知后选择，理由是实际原图已可取得、跨类对同类净收益为正且对称Q收益接近本背景均值；不是额外的总体效果估计，也不是以最大Q增益挑例。B6整张图在本条件下仍是重要反例：同一个方向可以在某个背景受益、另一些背景下降。因此本例用于解释联合类别的原答、票数、定位和质量取舍，群体推荐仍以完整事件、图片和建筑汇总为准。

`export_case.py`仅进行了已允许的3次融合状态重放，用于取身份对应、节点票账和连接票账；**0次重新评分**。三个候选几何与既有端点逐一校验相同，见 `CASE_EXPORT_RECEIPT.json`。再次运行且已有结果时直接复用，不增加回放。`render_case.py`只读保存状态和已取得原图绘图；`explain_case.py`只从小表派生投票与分项说明，均不融合、不评分。

关键文件：`EXACT_EVENT.csv.gz`、`EXACT_MEMBERS.csv.gz`、`FOLD_MEMBER_HISTORY.csv`、`ENDPOINT_METRICS.csv.gz`、`ABC_COMPONENT_CHANGES.csv`、`LOCAL_OPPORTUNITY_VOTES.csv`、`case.json.gz`，以及 `figures/` 三张图。PNG以完整字节、原子替换保存，并经PIL完全解码和SHA复读；回执为 `figures/PNG_WRITE_VERIFICATION.json`。
'''
    write_bytes(HERE / "MANUAL_JOINT_CASE_ZH.md", report.encode("utf-8"))
    files = ["MANUAL_JOINT_CASE_ZH.md", "LOCAL_OPPORTUNITY_VOTES.csv", "ABC_COMPONENT_CHANGES.csv"]
    receipt = dict(complete=True, metadata_replays=0, score_calls=0, all_four_background_observation_sets_unchanged=True,
                   derived_from_saved_metadata=True, files=[dict(path=name, bytes=(HERE/name).stat().st_size,
                   sha256=hashlib.sha256((HERE/name).read_bytes()).hexdigest()) for name in files])
    write_bytes(HERE / "CASE_EXPLANATION_RECEIPT.json", json.dumps(receipt, ensure_ascii=False, indent=2).encode("utf-8"))
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
