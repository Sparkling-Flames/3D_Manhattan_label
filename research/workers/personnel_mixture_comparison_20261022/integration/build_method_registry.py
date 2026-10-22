#!/usr/bin/env python3
"""Link inherited method identities to saved current comparisons; no fitting/fusion.

Run from any directory. Only integration/ and inputs/ are written.
"""
from pathlib import Path
import csv
import gzip
import hashlib
import io
import json
import os
import pandas as pd

HERE = Path(__file__).resolve().parent
ROUND = HERE.parent
REPO = ROUND.parents[2]
COMMIT = "ef148c82df18582228b2d23837faa2659e79eba7"
WORKERS = REPO / "research/workers"
OLD = WORKERS / "personnel_exchange_adoption_followup_20261022/integration"
CLOSURE = WORKERS / "personnel_exchange_closure_20261022/classification"
CROSS = WORKERS / "personnel_effective_exchange_conditions_20261022/cross_condition_taxonomy"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save_bytes(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as handle:
        assert handle.write(payload) == len(payload)
        handle.flush()
        os.fsync(handle.fileno())
    assert tmp.read_bytes() == payload
    os.replace(tmp, path)


def csv_rows(payload):
    rows = list(csv.reader(io.StringIO(payload.decode("utf-8-sig"))))
    assert rows and all(len(row) == len(rows[0]) for row in rows)
    return len(rows) - 1


def save_table(path, df):
    payload = df.to_csv(index=False).encode("utf-8-sig")
    assert csv_rows(payload) == len(df)
    save_bytes(path, payload)
    assert len(pd.read_csv(path)) == len(df)


def rel(path):
    return str(path.relative_to(REPO))


def copy_inputs():
    """Small label/definition sources; large endpoints remain in their own modules."""
    sources = []
    def add(src, dest, identity, usage, compress=False):
        sources.append((src, ROUND / "inputs" / dest, identity, usage, compress))
    for name in ["ALL_METHOD_LABELS_ALL_DATA.csv", "PERSONNEL_LABELS_EXPLAINED.csv",
                 "CLASS_DEFINITIONS.csv", "CLASS_MEMBERS_AND_FEATURES.csv",
                 "JOINT_CLASS_MEMBERS_AND_FEATURES.csv", "CLASS_AUXILIARY_DOMAINS.csv"]:
        add(CLOSURE/name, "four_main/"+name, "ALL_descriptive",
            "四主方案全数据描述；不得用于目标建筑用途检验")
    add(OLD/"分类定义与完整ALL成员.csv", "four_main/ALL_CLASS_MEMBERS_EXPLAINED.csv",
        "ALL_descriptive", "现有整合版中文定义、完整成员与历史支持")
    add(CLOSURE/"ALL_METHOD_LABELS_LOBO.csv.gz", "four_main/ALL_METHOD_LABELS_LOBO.csv.gz",
        "outer_building_excluded_inner_selected", "四主方案实际楼外标签、连续历史中心和缺失状态")
    add(ROUND/"configurations/FOLD_CLASS_DEFINITIONS.csv", "four_main/FOLD_CLASS_DEFINITIONS.csv",
        "derived_LOBO_definition", "本轮使用的逐折粗细类成员及历史中心；与ALL类数可不同")
    add(CLOSURE/"FIELD_GUIDE_ZH.md", "four_main/FIELD_GUIDE_ZH.md",
        "field_contract", "原标签字段与资格合同")
    add(CLOSURE/"LEGACY_LABELS_TARGET_MAPS.csv.gz", "legacy/LEGACY_LABELS_TARGET_MAPS.csv.gz",
        "mixed_historical_fit_scopes_explicit", "M/SP/A2/Rnew2/F01/多域及四主方案的原目标映射；逐行label_fit_scope为准")
    add(CLOSURE/"LEGACY_M_SP_A2_CLASS_CATALOG.csv", "legacy/LEGACY_M_SP_A2_CLASS_CATALOG.csv",
        "legacy_ALL_descriptive", "旧M/SP/A2的实际成员、语义及原fit_scope")
    for name in ["OLD_METHOD_LABELS_ALL.csv", "OLD_METHOD_MEMBERS_ALL.csv", "OLD_METHOD_REGISTRY.csv"]:
        add(CROSS/name, "legacy/"+name, "legacy_original_ALL_or_history_identity",
            "按原方法registry/fit_scope保留旧方法；不拼为统一层级")
    add(CLOSURE/"DOMAIN_SUBSET_COVERAGE_26x2.csv", "legacy/DOMAIN_SUBSET_COVERAGE_26x2.csv",
        "inherited_coverage_not_new_experiment", "五变量域26子集分条件的旧覆盖；不重复共同域G5")
    for name in ["CROSS_LABELS_ALL.csv", "CLASS_DEFINITIONS_ALL.csv", "CROSS_CLASS_CENTERS_ALL.csv",
                 "ADOPTION_MATRIX_FINAL.csv"]:
        add(CROSS/name, "cross_condition/"+name, "cross_condition_ALL_or_inherited_adoption",
            "三个既有双条件方法的ALL描述或原用途判断；效果按Manual/Semi分开")
    for name in ["CROSS_LABELS_LOBO.csv", "CROSS_CLASS_CENTERS_LOBO.csv"]:
        add(CROSS/name, "cross_condition/"+name+".gz", "both_conditions_target_building_excluded",
            "原双条件楼外标签/中心；仅gzip封装原CSV字节，未拟合或重写表", True)
    add(OLD/"分类方案_采用总表.csv", "references/INHERITED_METHOD_ADOPTION.csv",
        "inherited_11_family_registry", "本轮方法选择总表的原始登记，保留阶段身份")
    manifest = []
    for src, dst, identity, usage, compress in sources:
        raw = src.read_bytes()
        output = gzip.compress(raw, compresslevel=5, mtime=0) if compress else raw
        save_bytes(dst, output)
        payload = gzip.decompress(output) if dst.suffix == ".gz" else output
        rows = csv_rows(payload) if ".csv" in dst.name else None
        if compress:
            assert gzip.decompress(dst.read_bytes()) == raw
        else:
            assert sha(dst.read_bytes()) == sha(raw)
        manifest.append(dict(source_path=rel(src), output_path=rel(dst), source_commit=COMMIT,
            data_version="real_v2", identity=identity, intended_use=usage,
            source_bytes=len(raw), output_bytes=len(output), source_sha256=sha(raw),
            output_sha256=sha(output), rows=rows,
            transformation="gzip wrapping only; original CSV bytes preserved" if compress else "byte-identical copy"))
    table = pd.DataFrame(manifest)
    save_table(ROUND/"inputs/SOURCE_MANIFEST.csv", table)
    return table


def load_events(path):
    names = pd.read_csv(path, nrows=0).columns
    desired = ["condition", "method_id", "image", "building", "n", "actual_m_AC",
               "event_id", "actual_physical_ABC", "physical_triple_id", "physical_AC",
               "background_key", "background_id", "parent_fixed"]
    return pd.read_csv(path, usecols=[x for x in desired if x in names])


def event_coverage(df, key, method, condition=None):
    if df.empty:
        return {}
    mask = df.method_id.isin(method)
    if condition in ["manual", "semi"]:
        mask &= df.condition.eq(condition)
    d = df[mask]
    out = {}
    for cond, x in d.groupby("condition"):
        phys = next((c for c in ["actual_physical_ABC", "physical_triple_id", "physical_AC"] if c in x), None)
        bg = next((c for c in ["background_key", "background_id"] if c in x), None)
        out[cond] = dict(registered_rows=len(x), images=x.image.nunique(), buildings=x.building.nunique(),
            n_min=int(x.n.min()), n_max=int(x.n.max()), m_min=int(x.actual_m_AC.min()),
            m_max=int(x.actual_m_AC.max()), unique_physical_sets=int(x[phys].nunique()) if phys else None,
            unique_backgrounds=int(x[bg].nunique()) if bg else None)
    return out


def j(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def make_registry():
    old = pd.read_csv(OLD/"分类方案_采用总表.csv")
    coverage = pd.read_csv(ROUND/"configurations/COMPLETE_COVERAGE_BY_METHOD.csv")
    fine = pd.read_csv(ROUND/"configurations/FINE_INCREMENT_COVERAGE.csv")
    strict_frames = []
    for group in ["manual_joint_A", "manual_joint_B", "manual_structure", "semi_joint"]:
        d = load_events(ROUND/f"exchanges/{group}/EXACT_EVENT_LINKS.csv.gz")
        d["analysis_batch"] = group
        strict_frames.append(d)
    strict = pd.concat(strict_frames, ignore_index=True)
    legacy = load_events(ROUND/"exchanges/legacy_n20/EXACT_EVENT_LINKS.csv.gz")
    ac = load_events(ROUND/"direct_ac/EXACT_AC_EVENTS_AND_OUTCOMES.csv.gz")
    strict_conditions = pd.read_csv(ROUND/"exchanges/ALL_CONDITIONS_SELECTION_REASONS.csv")
    legacy_conditions = pd.read_csv(ROUND/"exchanges/legacy_n20/PARENT_FIXED_M_RESPONSE.csv")
    ac_conditions = pd.read_csv(ROUND/"direct_ac/CONDITION_COMPARISON.csv")
    role = pd.read_csv(ROUND/"difficulty/role_image_contrasts.csv.gz",
                       usecols=["method", "condition", "image_id", "building_id"])
    role = role.rename(columns={"image_id": "image", "building_id": "building"})
    aliases = {"MV_QTD / QT+scope+Semi": ["MV_QTD_manual", "MV_QTD_manual_new",
               "MV_QTScopeSemi_semi_new", "MV_TDScopeSemi_manual_new"]}
    selections = {
      ("V3_BEHAVIOR", "manual"): ("主文：结构构成与困难机会",
        "困难图上可见的实际转折、短细节差异与定向结构替换相衔接；完整配比呈现多数困难机会差异，也保留pa4-18等近零例。",
        "常规→较多转折n20/m4与m7保留；反向及整类较大块可降质。混合面板同/改构成Q变幅差较小，不将类型解释为普遍可互换。",
        "ALL三类无独立细分；楼外部分折实际再分，1633父构成中159有两个以上细构成。细层用于局部表达，不能由均值跨度直接认定比粗类更优。"),
      ("V3_JOINT_QT", "manual"): ("主文：质量—时间角色与可操作替换",
        "完整所有方向比较后保留较高历史Q/较快及最高Q/较慢两个不同用途；共同背景同m的有限面板中时间分离比Q幅度分离清楚。",
        "n20/m4较高Q较快及最高Q较慢分开采用；降Q/更快也保留质量换时间风险。n20/m4混合配比：时间跨配比变化较大24/27图、18/19楼；Q不构成普遍更大变幅。",
        "本轮完整有限面板3297粗构成=3297细构成，没有额外细层；粗细重复标签不算增量。"),
      ("V3_JOINT_QT", "semi"): ("主文：时间构成、条件质量取舍与成员风险",
        "自身历史联合类保留效率用途，完整混合格展示质量、时间及失败，不要求同类普遍更稳定。父内细类有实际配比支持。",
        "按已登记方向/n/m/背景分开采用；B6-22时间差集中于唯一W112细类席位，不能泛称多人可替换；高失败及明显质量代价不删除。",
        "800父构成中272可细分、1274细构成；父内时间与Q可改变。细类使用需同时给具体成员容量，不能用小格单例零波动证明互换性。"),
      ("V3_BEHAVIOR", "semi"): ("主文：终稿表达、位置变化及无差异对照",
        "保留简化/常规、近共线分段和较多转折的可见语义；原来没有其自身严格ABC，本轮补完整混合配比及同背景有限端点对。",
        "7y13角数相同但定位随成员/背景变化；X7-05全配比近零；Z6-10失败分布。用作表达及风险条件分类，不作为普遍质量/同类稳定规则。",
        "284父构成中162可细分、954细构成。n20/m4父内Q跨-同幅度+0.182但仅4/9图更大，保留条件性增量，不作统一排序。"),
      ("M_structure", "manual"): ("主文补充：既有粗细结构与父内规模对照",
        "保留原实际结构分区与较大块实验身份；本轮对旧n20全部事件按真实m和父类构成重汇总，不重复拟合。",
        "总体结构用途保留；父内细类m4/m5/m6的跨-同绝对Q变化约−0.253/+0.054/+0.377，增量依规模且较弱，旧正例不被抹去。",
        "父类固定对照才作为细类增量；旧Y/Z可重叠，C−B实际m与A→B/A→C不同，另阶段报告。"),
      ("SP_scale", "semi"): ("补充：尺度、正反机制与父内机会",
        "原尺度类别有独立解释价值；本轮旧n20及直接AC覆盖保留，主文四类更适合完整构成展示。",
        "尺度作用与质量方向分别解释；旧28个所谓细类事件跨父类，不能写成独立细分增量。新的父内汇总按真实父向量筛选。",
        "保留2粗3细及机会缺失；SP不是Semi联合类的天然父类。"),
      ("A2_relation", "manual"): ("主文补充：原答关系、大块区分与风险",
        "原几何相似性与特定n17/m9信号保持；本轮补旧n20和直接大块AC，实际Manual/Semi评价均存在，输入来源按原标签合同。",
        "用于相似原答与指定块规模的变化解释；困难图同类也可波动更大。旧类号未跨折语义对齐，不能把AC汇总有符号均值称统一换类方向。",
        "A2原分区无统一父细层；不拼入M/结构三类层级。"),
      ("Rnew2", "manual"): ("补充：真实替换关系学习与重要负结果",
        "原关系反推已实现，旧768/新1040候选及直接m2学习未超过Q/原Rnew2的结果保持；本轮不重开搜索。",
        "直接大块AC现有15个条件全部纳入，但原语义未跨折对齐。保留训练侧实际用途，不因本轮主线选择解释类而否定它。",
        "无本轮新增层级；使用原新来源支持与冻结目标映射。"),
      ("F01", "manual"): ("补充：高Q内快慢与完整配比范例",
        "既有37配比/1874队完整枚举及独立复核已回答该有限范围；本轮引用、不重复整轮快慢搜索。",
        "简单图相近质量时记录时间用途保留，困难图质量方向不一；新增直接AC登记34事件/11图/10楼全部关联，不能冒称四主类的穷尽结果。",
        "两类无粗细增量；历史训练10楼/目标12楼身份沿原映射，不假称逐目标楼新拟合。"),
      ("MV_QTD / QT+scope+Semi", "separate"): ("主文补充：多域覆盖、时间方向与父内规模",
        "26域子集覆盖和实际真实团队比较继承；同26人七字段Full/删域K2/K3与反向关系已做，不把候选登记数当完成实验数。",
        "本轮旧QTD n20父内及多域直接AC全方向重汇总；质量/时间方向依支持，保留减慢类平均质量代价及风险。共同域G5/连续QT不重跑。",
        "各自层级及机会域独立；旧QTDS的S=结构，scope倾向不是裁定正确率，Semi编辑机会缺失不填零。"),
      ("CROSS_CONDITION_NATIVE", "separate"): ("补充：联合条件历史及条件性净效率",
        "XCOND_GEOM、XCOND_GEOM_QT、XCOND_PAIRED已真实形成并评价；本轮不新增拟合，继承已完成共同锚点比较。",
        "PAIR Manual C−B Q+1.120/时间−5.576%，但C−A Q−0.992；Semi净Q−2.089/时间−4.273%为取舍。GEOM_QT不整体替代自身联合；GEOM保留原答位置/高度解释。",
        "各方法各折独立粗细；PAIR多折没有额外细层。两条件同时排除目标楼，效果不混为一队。"),
    }
    rows = []
    for _, previous in old.iterrows():
        key = (previous["method"], previous["evaluation_condition"])
        method, condition = key
        methods = aliases.get(method, [method])
        # A2 had Manual-only prose in the inherited catalogue, but both evaluation
        # conditions are present in actual old label maps and current endpoint work.
        actual_cond = "separate_manual_and_semi" if method in ["A2_relation", "CROSS_CONDITION_NATIVE", "MV_QTD / QT+scope+Semi"] else condition
        filter_cond = condition if method != "A2_relation" else None
        level, reason, use, fine_note = selections[key]
        cc = coverage[(coverage.method == method) & (coverage.condition == condition)]
        ff = fine[(fine.method == method) & (fine.condition == condition)]
        current = dict(previous)
        current["inherited_adoption_at_main"] = current.pop("current_adoption")
        current.update(method_family_key=method+"__"+condition,
            source_commit=COMMIT, data_version="real_v2", registry_stage="inherited_11_families_with_current_saved_comparisons",
            prior_evaluation_condition=condition, evaluation_condition=actual_cond,
            all_identity="ALL用于描述人员，不能替代楼外/冻结历史检验",
            evaluation_label_identity=("原目标映射逐行label_fit_scope为准；F01为历史10楼→目标12楼" if method in ["F01", "Rnew2", "M_structure", "SP_scale", "A2_relation", "MV_QTD / QT+scope+Semi"] else
              "同时排除目标建筑Manual和Semi；三候选各自标签、两条件分别评价" if method == "CROSS_CONDITION_NATIVE" else
              "目标建筑外形成；实际折可不同家族/类数；按历史角色对齐，不跨折拼类号"),
            current_maintext_status=level, current_selection_reason=reason,
            current_retained_uses_and_findings=use, coarse_fine_increment_judgment=fine_note,
            current_full_configuration_coverage=j(cc.to_dict("records")),
            current_fine_configuration_coverage=j(ff.where(pd.notna(ff), None).to_dict("records")),
            current_strict_ABC_coverage=j(event_coverage(strict, "strict", methods, filter_cond)),
            current_legacy_n20_coverage=j(event_coverage(legacy, "legacy", methods, filter_cond)),
            current_direct_AC_coverage=j(event_coverage(ac, "direct_AC", methods, filter_cond)),
            current_strict_condition_rows=int(len(strict_conditions[strict_conditions.method_id.isin(methods) & ((strict_conditions.condition==filter_cond) if filter_cond in ['manual','semi'] else True)])),
            current_legacy_condition_rows=int(len(legacy_conditions[legacy_conditions.method_id.isin(methods) & ((legacy_conditions.condition==filter_cond) if filter_cond in ['manual','semi'] else True)])),
            current_direct_AC_condition_rows=int(len(ac_conditions[ac_conditions.method_id.isin(methods) & ((ac_conditions.condition==filter_cond) if filter_cond in ['manual','semi'] else True)])),
            new_classification_fits=0, new_fusion_calls=0, current_work_kind="reuse_endpoints_and_labels; new_aggregation_comparison_and_explanation",
            not_a_method_leaderboard="支持人员/图片/背景不同；未将不共同分母均值排名；共同域G5沿用已有结果")
        evidence = [rel(OLD/"分类方案_采用总表.csv")]
        if not cc.empty:
            evidence += [rel(ROUND/"configurations/README.md"), rel(ROUND/"configurations/COMPLETE_COVERAGE_BY_METHOD.csv"),
                         rel(ROUND/"configurations/FINE_INCREMENT_COVERAGE.csv"),
                         rel(ROUND/f"configurations/CONFIGURATION_OVERVIEW_{condition}.csv.gz"),
                         rel(ROUND/f"exchanges/finite_pair_comparison/{condition}_SUMMARY.csv"),
                         rel(ROUND/"difficulty/role_difficulty_summary.csv")]
            x = role[(role.method==method)&(role.condition==condition)]
            current["current_raw_role_contrast_rows"] = len(x)
            current["current_raw_role_images"] = int(x.image.nunique())
            current["current_raw_role_buildings"] = int(x.building.nunique())
            current["current_finite_pair_scope"] = "所有已存已知标签12选6端点的无向对；同实际D与m=1–6匹配，同/改配比及固定父向量细分；不是严格ABC有符号效果"
        else:
            current["current_raw_role_contrast_rows"] = 0
            current["current_raw_role_images"] = 0
            current["current_raw_role_buildings"] = 0
            current["current_finite_pair_scope"] = "本轮未重新计算该方法完整有限面板端点对；旧结果按原阶段保留"
        if current["current_strict_condition_rows"]:
            evidence += [rel(ROUND/"exchanges/ALL_CONDITIONS_SELECTION_REASONS.csv"), rel(ROUND/"exchanges/COMMON_QT_CONDITIONS.csv")]
        if current["current_legacy_condition_rows"]:
            evidence += [rel(ROUND/"exchanges/legacy_n20/PARENT_FIXED_M_RESPONSE.csv")]
        if current["current_direct_AC_condition_rows"]:
            evidence += [rel(ROUND/"direct_ac/CONDITION_COMPARISON.csv"),rel(ROUND/"direct_ac/ROLE_SUMMARY.csv")]
        if method=="F01":
            evidence += [rel(WORKERS/"personnel_mixture_audit_20261022/F01_RECOMPUTED_CONFIGURATIONS.csv")]
        if method=="CROSS_CONDITION_NATIVE":
            evidence += [rel(CROSS/"ADOPTION_MATRIX_FINAL.csv"), rel(CROSS.parent/"joint_exchange/CROSS_METHOD_FINDINGS_ZH.md")]
        if method=="MV_QTD / QT+scope+Semi":
            evidence += [rel(ROUND/"inputs/legacy/DOMAIN_SUBSET_COVERAGE_26x2.csv")]
        current["evidence_paths"] = "|".join(evidence)
        current["small_input_manifest"] = rel(ROUND/"inputs/SOURCE_MANIFEST.csv")
        rows.append(current)
    result = pd.DataFrame(rows)
    assert len(result)==11 and result.method_family_key.is_unique
    # Data fields must be parseable standard JSON (missing numbers are null).
    for column in ["current_full_configuration_coverage", "current_fine_configuration_coverage"]:
        result[column] = result[column].str.replace("NaN", "null", regex=False)
    for paths in result.evidence_paths:
        assert all((REPO/path).is_file() for path in paths.split("|"))
    save_table(HERE/"METHOD_SELECTION_AND_COVERAGE.csv", result)
    return result


def main():
    manifest = copy_inputs()
    table = make_registry()
    receipt = dict(source_commit=COMMIT, data_version="real_v2", method_families=len(table),
        copied_input_files=len(manifest), copied_input_bytes=int(manifest.output_bytes.sum()),
        new_classification_fits=0,new_fusion_calls=0,
        notes=["配置目录被冻结；此脚本不修改configurations/或main报告",
               "严格ABC、旧Y/Z可重叠ABC、直接AC、有限端点对是不同设计",
               "11家族按原登记保留；A2本轮实际有Manual及Semi评价，未据此虚构新建类",
               "cross-condition三个历史候选实际已做；本轮仅复制完整标签/中心和引用原结论"],
        method_table_sha256=sha((HERE/"METHOD_SELECTION_AND_COVERAGE.csv").read_bytes()),
        input_manifest_sha256=sha((ROUND/"inputs/SOURCE_MANIFEST.csv").read_bytes()))
    save_bytes(HERE/"INTEGRATION_RECEIPT.json",json.dumps(receipt,ensure_ascii=False,indent=2).encode())
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
