"""提取已冻结的 v2 人员分类展示数据；不拟合标签、不计算新融合。"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("research/workers/personnel_exchange_closure_20261022/classification")
TAXONOMY = Path("research/workers/personnel_v3_20261021/raw_answer_evidence/taxonomy")
OUT = ROOT / "research/workers/personnel_main_figures_v2_20261023/data"
FEATURES = {
    "turn_history": ("非近共线转折历史残差", "个转折"),
    "short_history": ("短转折边历史残差", "条短边"),
    "redundancy_history": ("近共线节点历史残差", "个节点"),
    "area_history": ("底面面积对数历史残差", "自然对数；面积以相机高度平方归一"),
    "height_history": ("推导高度对数历史残差", "自然对数；高度以相机高度归一"),
    "simple_turn_history": ("简单结构机会的转折残差", "个转折；结构条件C"),
    "complex_turn_history": ("复杂结构机会的转折残差", "个转折；结构条件C"),
    "complex_short_history": ("复杂结构机会的短边残差", "条短边；结构条件C"),
    "q_history": ("本条件历史Q残差", "Q分；相对同图人员均值"),
    "q_downside": ("历史Q低尾差", "Q分；历史均值减建筑内个人P10后建筑均值"),
    "t_history": ("本条件记录时间对数残差", "自然对数；同图同来源同时间口径中心化"),
}
INPUTS = {
    "TURN": ["turn_history", "short_history"],
    "STRUCTURE": ["turn_history", "short_history", "redundancy_history"],
    "CQT": ["simple_turn_history", "complex_turn_history", "complex_short_history",
            "q_history", "q_downside", "t_history"],
    "EQT": ["turn_history", "short_history", "q_history", "q_downside", "t_history"],
}
SCHEMES = [
    ("manual_structure", "V3_BEHAVIOR", "manual", "Manual结构类", "TURN", 3, 3,
     "表达差异、混合配比、类内换人和跨类变化；连接复杂结构机会与人工难度"),
    ("manual_joint_qt", "V3_JOINT_QT", "manual", "Manual结构＋Q/T联合类", "CQT", 5, 5,
     "质量—时间—表达角色、构成变化和效率取舍；具体选人同时保留连续Q/T"),
    ("semi_structure", "V3_BEHAVIOR", "semi", "Semi终稿结构类", "STRUCTURE", 3, 4,
     "区分较少转折、常规、近共线分段和较多转折；观察类内几何及成员差异"),
    ("semi_joint_qt", "V3_JOINT_QT", "semi", "Semi自身结构＋Q/T联合类", "EQT", 5, 5,
     "终稿表达与记录时间角色、质量代价及构成变化；与Manual分别评价"),
]


def read(path: Path) -> pd.DataFrame:
    return pd.read_csv(ROOT / path)


def save(frame: pd.DataFrame, name: str) -> None:
    frame.to_csv(OUT / name, index=False, encoding="utf-8-sig")
    loaded = pd.read_csv(OUT / name)
    assert loaded.shape == frame.shape, name


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    labels = read(SOURCE / "ALL_METHOD_LABELS_ALL_DATA.csv")
    definitions = read(SOURCE / "CLASS_DEFINITIONS.csv")
    centers = pd.concat([read(SOURCE / name) for name in
                         ["CLASS_MEMBERS_AND_FEATURES.csv", "JOINT_CLASS_MEMBERS_AND_FEATURES.csv"]])
    assert len(labels) == 248
    assert not labels.duplicated(["method", "condition", "worker_id"]).any()
    assert labels.heldout_building.eq("ALL").all()
    assert labels.label_stage.eq("all_data_descriptive").all()
    scheme_rows, member_rows, center_rows, selection_rows = [], [], [], []
    for sid, method, condition, title, family, coarse_k, fine_k, use in SCHEMES:
        people = labels[(labels.method == method) & (labels.condition == condition)].copy()
        classes = definitions[(definitions.method == method) & (definitions.condition == condition)]
        assert len(people) == 62 and people.worker_id.nunique() == 62
        assert people.selected_family.eq(family).all()
        assert people.coarse_k.eq(coarse_k).all() and people.fine_k.eq(fine_k).all()
        assert people[people.known].coarse_label.nunique() == coarse_k
        assert people[people.known].fine_label.nunique() == fine_k
        assert people.known.eq(people.fine_label.ne("unknown")).all()
        assert people[~people.known].missing_reason.notna().all()
        counts = []
        for row in classes.itertuples(index=False):
            p = people[people.fine_label == row.fine_label]
            assert set(row.members.split("|")) == set(p.worker_id)
            assert int(row.n_members) == len(p)
            counts.append(f"{row.fine_label} {row.name_zh}：{len(p)}人")
            for person in p.to_dict("records"):
                member_rows.append(dict(
                    scheme_id=sid, scheme_name_zh=title, method=method, condition=condition,
                    coarse_label=person["coarse_label"], fine_label=person["fine_label"],
                    name_zh=row.name_zh, definition_zh=row.definition_zh,
                    worker_id=person["worker_id"], known=person["known"],
                    missing_reason=person["missing_reason"], selected_family=family,
                    heldout_building="ALL", label_stage=person["label_stage"],
                    n_images=person["n_images"], n_buildings=person["n_buildings"],
                    n_records=person["n_records"], origin=person["origin"],
                    source_file=(SOURCE / "ALL_METHOD_LABELS_ALL_DATA.csv").as_posix()))
            original = centers[(centers.method == method) & (centers.condition == condition)
                               & (centers.fine_label == row.fine_label)]
            assert len(original) == 1
            original = original.iloc[0]
            assert set(original.members.split("|")) == set(p.worker_id)
            source_center = "JOINT_CLASS_MEMBERS_AND_FEATURES.csv" if method == "V3_JOINT_QT" else "CLASS_MEMBERS_AND_FEATURES.csv"
            for field, (feature_name, unit) in FEATURES.items():
                if field not in original or field not in p:
                    continue
                value = float(original[field])
                expected = float(p[field].mean())
                assert np.isclose(value, expected, atol=1e-12, rtol=1e-12, equal_nan=True), (sid, row.fine_label, field)
                center_rows.append(dict(
                    scheme_id=sid, method=method, condition=condition, coarse_label=row.coarse_label,
                    fine_label=row.fine_label, name_zh=row.name_zh, known=row.known,
                    n_members=len(p), feature=field, feature_name_zh=feature_name, unit=unit,
                    value=value, n_nonmissing_people=int(p[field].notna().sum()),
                    is_training_input=field in INPUTS[family],
                    source_file=(SOURCE / source_center).as_posix(),
                    interpretation="类中心；个人建筑等权历史的成员均值" if row.known else "未知成员残存观测均值，不解释为类别中心"))
        prefix = "JOINT_" if method == "V3_JOINT_QT" else ""
        selected = [x for x in json.loads((ROOT / TAXONOMY / f"{prefix}SELECTED_MODELS.json").read_text(encoding="utf-8-sig"))
                    if x["condition"] == condition and x["heldout_building"] == "ALL"]
        assert len(selected) == 1
        selected = selected[0]
        assert (selected["family"], selected["coarse_k"], selected["fine_k"]) == (family, coarse_k, fine_k)
        candidates = read(TAXONOMY / f"{prefix}CANDIDATE_SELECTION_ALL.csv")
        candidates = candidates[(candidates.condition == condition) & (candidates.heldout_building == "ALL")]
        best = candidates[candidates.eligible_selection].sort_values(["score", "k", "family"]).iloc[0]
        assert (best.family, int(best.k)) == (family, fine_k)
        for decision in selected["coarse_choice"]:
            selection_rows.append(dict(scheme_id=sid, selected_family=family,
                                       selected_fine_k=fine_k, selected_coarse_k=coarse_k, **decision))
        scheme_rows.append(dict(
            scheme_id=sid, scheme_name_zh=title, condition=condition, method=method,
            selected_family=family, training_inputs="|".join(INPUTS[family]),
            training_inputs_zh="；".join(FEATURES[f][0] for f in INPUTS[family]),
            coarse_k=coarse_k, fine_k=fine_k, independent_fine_level=coarse_k != fine_k,
            total_people=62, known_people=int(people.known.sum()), unknown_people=int((~people.known).sum()),
            all_class_counts_zh="；".join(counts), intended_use_zh=use,
            selection_basis_zh="内侧留楼原答几何表达重构误差" if method == "V3_BEHAVIOR" else "内侧留楼结构/尺度、历史Q与记录时间的联合重构误差",
            fusion_quality_used_for_class_selection=False, label_stage="all_data_descriptive",
            source_file=(SOURCE / "ALL_METHOD_LABELS_ALL_DATA.csv").as_posix()))
    save(pd.DataFrame(scheme_rows), "CLASSIFICATION_SCHEMES.csv")
    save(pd.DataFrame(member_rows), "CLASSIFICATION_MEMBERS.csv")
    save(pd.DataFrame(center_rows), "CLASSIFICATION_CENTERS.csv")
    save(pd.DataFrame(selection_rows), "CLASSIFICATION_K_SELECTION.csv")

    renderer = Path("research/workers/personnel_v3_20261021/repro/personnel_useful_taxonomy_v3_20261021/evidence/render_raw_behavior.py")
    tree = ast.parse((ROOT / renderer).read_text(encoding="utf-8-sig"))
    spec_node = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == "SPECS" for t in node.targets))
    assert all(isinstance(node.func, ast.Name) and node.func.id == "dict"
               for node in ast.walk(spec_node) if isinstance(node, ast.Call))
    specs = eval(compile(ast.Expression(spec_node), str(renderer), "eval"), {"__builtins__": {}, "dict": dict})
    lobo = read(SOURCE / "ALL_METHOD_LABELS_LOBO.csv.gz")
    behavior = read(TAXONOMY / "BEHAVIOR_RECORDS.csv.gz")
    examples = []
    for spec in specs[:2]:
        building = spec["image"].rsplit("-", 1)[0]
        photo = Path("research/workers/personnel_v3_20261021/raw_answer_evidence/evidence/figures") / spec["case_id"] / "raw_three_views.png"
        assert (ROOT / photo).is_file()
        for label, description, workers in spec["groups"]:
            for worker in workers:
                ll = lobo[(lobo.method == "V3_BEHAVIOR") & (lobo.condition == spec["condition"])
                          & (lobo.heldout_building == building) & (lobo.worker_id == worker)]
                rr = behavior[(behavior.condition == spec["condition"]) & (behavior.image_code == spec["image"])
                              & (behavior.worker_id == worker)]
                aa = labels[(labels.method == "V3_BEHAVIOR") & (labels.condition == spec["condition"])
                            & (labels.worker_id == worker)]
                assert len(ll) == len(rr) == len(aa) == 1
                ll, rr, aa = ll.iloc[0], rr.iloc[0], aa.iloc[0]
                assert ll.fine_label == label
                examples.append(dict(
                    case_id=spec["case_id"], condition=spec["condition"], image_code=spec["image"],
                    image_id=rr.image_id, building_id=building, worker_id=worker, object_id=rr.object_id,
                    lobo_coarse_label=ll.coarse_label, lobo_fine_label=ll.fine_label,
                    all_coarse_label=aa.coarse_label, all_fine_label=aa.fine_label,
                    turn_n=rr.turn_n, short_turn_edges=rr.short_turn_edges,
                    near_straight_nodes_5deg=rr.near_straight_nodes_5deg,
                    figure_path=photo.as_posix(), displayed_group_zh=description,
                    selection_note_zh=spec["note"], renderer_source=renderer.as_posix(),
                    record_source=(TAXONOMY / "BEHAVIOR_RECORDS.csv.gz").as_posix(),
                    label_source=(SOURCE / "ALL_METHOD_LABELS_LOBO.csv.gz").as_posix()))
    assert len(examples) == 12
    save(pd.DataFrame(examples), "CLASSIFICATION_RAW_EXAMPLE_MEMBERS.csv")
    (OUT / "CLASSIFICATION_EXTRACTION_RECEIPT.json").write_text(json.dumps(dict(
        schemes=len(scheme_rows), all_member_rows=len(member_rows), all_classes=len(definitions),
        center_values=len(center_rows), visual_member_rows=len(examples),
        checked="逐人名单、原始中心与个人均值、ALL类数与选型账、案例成员及楼外标签",
        new_class_fits=0, new_fusion_calls=0), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(schemes=len(scheme_rows), members=len(member_rows),
                          center_values=len(center_rows), example_members=len(examples)), ensure_ascii=False))


if __name__ == "__main__":
    main()
