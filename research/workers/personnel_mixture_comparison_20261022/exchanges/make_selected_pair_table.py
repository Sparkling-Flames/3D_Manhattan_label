#!/usr/bin/env python3
"""Select readable, pre-existing finite-pair results; no scoring or fusion."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
DEST = ROOT / "finite_pair_comparison"

SPECS = [
    ("manual", "V3_BEHAVIOR", "coarse", 20, 3, "abs_B8L2", "结构粗类的 Q 幅度差为正，但远小于同配比成员波动。"),
    ("manual", "V3_BEHAVIOR", "coarse", 20, 4, "abs_B8L2", "结构粗类在多数图片/建筑上有小幅分离；定向收益需另看严格 ABC。"),
    ("manual", "V3_BEHAVIOR", "coarse", 20, 6, "abs_B8L2", "较大替换块仍有分离；支持域与 m3/m4 不同，不能作为固定背景剂量曲线。"),
    ("manual", "V3_JOINT_QT", "coarse", 20, 4, "abs_B8L2", "多数图片差为正而建筑等权均值为负；不支持任意换配比必然更大幅改 Q。"),
    ("manual", "V3_JOINT_QT", "coarse", 20, 3, "abs_recorded_logtime", "联合角色构成明显组织记录时间幅度，方向性节时读严格 ABC。"),
    ("manual", "V3_JOINT_QT", "coarse", 20, 4, "abs_recorded_logtime", "相邻规模继续支持时间幅度用途；幅度差不是节省工时百分比。"),
    ("semi", "V3_BEHAVIOR", "coarse", 20, 4, "abs_B8L2", "总体 Q 幅度分离弱且仅部分图支持；保留结构表达用途。"),
    ("semi", "V3_JOINT_QT", "coarse", 12, 4, "abs_recorded_logtime", "联合粗类在多数图/楼区分时间变化幅度。"),
    ("semi", "V3_JOINT_QT", "fine_all_changes", 12, 4, "abs_recorded_logtime", "细类全配比时间分区更清楚，但包含粗类变化，不等于纯细分增量。"),
    ("manual", "V3_BEHAVIOR", "fine_parent_fixed", 20, 4, "abs_B8L2", "固定完整父类向量后 Q 幅度差约零；此规模不增加总体 Q 幅度解释。"),
    ("semi", "V3_BEHAVIOR", "fine_parent_fixed", 12, 4, "abs_B8L2", "父内细类 Q 平均幅度差约零；不把多数微小正差当成大效果。"),
    ("semi", "V3_JOINT_QT", "fine_parent_fixed", 12, 4, "abs_recorded_logtime", "父内时间分离集中于部分建筑，作为条件性细分用途。"),
]

LABELS = {
    "V3_BEHAVIOR": "结构分类",
    "V3_JOINT_QT": "结构＋Q/T 联合分类",
    "coarse": "粗类完整配比",
    "fine_all_changes": "细类完整配比（允许父类改变）",
    "fine_parent_fixed": "父类完整配比固定后的细类",
    "abs_B8L2": "绝对 Q 变化（分）",
    "abs_recorded_logtime": "绝对 log 记录时间比",
}


def main():
    summaries = {c: pd.read_csv(DEST / f"{c}_SUMMARY.csv") for c in ("manual", "semi")}
    panels = {c: pd.read_csv(DEST / f"{c}_PANEL_MATCHED_PAIR_METRICS.csv.gz") for c in summaries}
    rows = []
    for c, method, view, n, m, metric, interpretation in SPECS:
        keys = dict(method=method, classification_view=view, n=n, actual_m=m, metric=metric)
        frames = []
        for frame in (summaries[c], panels[c]):
            mask = pd.Series(True, index=frame.index)
            for k, v in keys.items():
                mask &= frame[k].eq(v)
            frames.append(frame.loc[mask])
        selected, panel = frames
        assert len(selected) == 1, (c, keys, len(selected))
        r = selected.iloc[0].to_dict()
        rows.append({
            "评价条件": c.title(), "分类": LABELS[method], "配比层级": LABELS[view],
            "总人数_n": n, "实际换人数_m": m, "替换比例_m除n": m / n,
            "指标": LABELS[metric], "同构成平均幅度": r["same_mean"],
            "改构成平均幅度": r["changed_mean"], "改构成减同构成": r["changed_minus_same"],
            "可评价图片数": int(r["known_images"]), "改构成幅度更大图片数": int(r["changed_larger_images"]),
            "更大图片比例": r["changed_larger_images"] / r["known_images"],
            "可评价建筑数": int(r["known_buildings"]), "改构成幅度更大建筑数": int(r["changed_larger_buildings"]),
            "更大建筑比例": r["changed_larger_buildings"] / r["known_buildings"],
            "匹配面板数": panel.loc[panel.matched_backgrounds.gt(0), "panel_id"].nunique(),
            "匹配背景分层数": int(panel.matched_backgrounds.sum()),
            "匹配同构成配对机会数": int(panel.matched_same_pairs.sum()),
            "匹配改构成配对机会数": int(panel.matched_changed_pairs.sum()),
            "用途判断": interpretation, "method": method, "classification_view": view,
            "metric": metric, "来源完整表": f"{c}_SUMMARY.csv",
            "覆盖来源": f"{c}_PANEL_MATCHED_PAIR_METRICS.csv.gz",
            "阶段身份": "本轮对已存真实 v2 端点完整配对并重新汇总；无新增融合/评分",
        })
    result = pd.DataFrame(rows)
    result.to_csv(DEST / "FINITE_PAIR_SELECTED_ZH.csv", index=False, encoding="utf-8-sig")
    lines = [
        "# 有限面板同配比／改配比：主文精选小表", "",
        "从已保存的完整 m=1–6 比较表选择下列 12 行，呈现质量、时间、较大块替换以及近零／反向结果。没有新增融合或改动评分。完整候选仍保存在 `manual_SUMMARY.csv` 与 `semi_SUMMARY.csv`；本表不替代完整结果。", "",
        "所有行都匹配相同图片、实际共同背景、团队人数 n 和实际换人数 m。父内细类行还固定完整粗类人数向量。估计顺序是配对→背景分层→面板→图片→建筑等权，右列报告图片和建筑中改构成幅度更大的实际比例。", "",
        "| 分类／层级 | n／m | 指标 | 同构成 | 改构成 | 差 | 跨更大的图／楼 |", 
        "|---|---:|---|---:|---:|---:|---|",
    ]
    for r in rows:
        label = f"{r['评价条件']} {r['分类']}，{r['配比层级']}"
        support = f"{r['改构成幅度更大图片数']}/{r['可评价图片数']} 图；{r['改构成幅度更大建筑数']}/{r['可评价建筑数']} 楼"
        lines.append(f"| {label} | {r['总人数_n']}／{r['实际换人数_m']} | {r['指标']} | {r['同构成平均幅度']:.4f} | {r['改构成平均幅度']:.4f} | {r['改构成减同构成']:+.4f} | {support} |")
    lines += [
        "", "## 读表与采用", "",
        "联合分类最清楚地区分记录时间的变化幅度：Manual n20 的 m3/m4 及 Semi n12/m4 均得到多数图、楼支持。它说明组成相同的团队记录时间通常更接近；没有方向，不能将绝对 log 时间比差直接写成节省工时百分比。定向节时与质量取舍采用严格 ABC 的 C−A、C−B 结果。", "",
        "Manual 结构粗类的 Q 幅度差在多规模上为正，但比同构成的成员波动小得多；联合粗类 m4 同时出现多数图片正差和总体平均负差，表明具体较大反例影响均值。已有定向升质应按明确类角色采用，不推成任意改变配比都改善或都变化更大。", "",
        "固定父类后，Manual 结构 n20/m4 与 Semi 结构 n12/m4 的总体 Q 幅度增量接近零；Semi 联合的父内时间差有条件性支持。Manual 联合这批粗／细标签没有独立父内细分机会，因此相应结果为 NA，未作为零效果放进表。", "",
        "各 n/m 的可评价图片支持会变化，不能把表中 m3→m6 当固定成员路径的剂量曲线。配对数属于覆盖机会数，同一端点会被多次使用，不是独立样本数。完整失败、分项、结构与几何结果在对应完整表，精选 CSV 还保留每行实际匹配背景及配对分母。", "",
        "复现本表：在仓库中运行 `python research/workers/personnel_mixture_comparison_20261022/exchanges/make_selected_pair_table.py`。", "",
    ]
    (DEST / "FINITE_PAIR_SELECTED_ZH.md").write_text("\n".join(lines), encoding="utf-8")
    print(result[["评价条件", "分类", "配比层级", "总人数_n", "实际换人数_m", "指标", "同构成平均幅度", "改构成平均幅度"]].to_string(index=False))


if __name__ == "__main__":
    main()
