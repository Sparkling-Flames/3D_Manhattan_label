#!/usr/bin/env python3
"""Merge fair-degree control sensitivity and retain all candidate decisions.

All inputs derive from the fixed discovery request panel. This script does not
open a pool cache or validation result. The original uncontrolled, linear, and
image-specific results are unchanged; matching rerun keys replace older rows.
"""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
import pandas as pd

KEY = ["method_id", "domain", "route", "panel", "model", "controlled", "target_group", "outcome"]
SELECTED = {
    ("F_rule_Q_threshold_K3", "all"): "相对任务同伴Q的−3/+3可解释阈值，22/20/13人，优先直接配比与方向复查。",
    ("F_rule_Q_quantile_K5", "all"): "质量更细的五等分，每类11人；检查分辨率收益及高类人数/比例，不宣称五个天然群体。",
    ("F_rule_Q2xDetail2", "all"): "Q×历史点数二分的四象限，8/20/15/12人；允许总分相近而结构不同的解释。",
    ("F_medoids_S_K4", "all"): "只用结构/范围习惯的四类，5/31/12/7人；不含Q拟合，保留方法与机制多样性。",
    ("R_geo9_source_signed_p2_K2", "all"): "历史几何共标关系先去来源关系再有符号谱分区，27/28人；检验超出批次的二类组合。",
    ("R_geo9_spectral_p2_K3", "all"): "历史几何关系谱分区14/20/21人；与去来源二类不同的关系表达，需控制来源。",
    ("R_role_ward_K5", "all"): "历史几何角色Ward五类18/19/7/5/6人；角色机制与实际几何可读性，保留小类限制。",
    ("R_role_ward_difficulty_K2", "hard"): "困难图条件历史角色30/7人；6张发现图/3楼结构诊断强，单独条件复查，不与全域排名直接比较。",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def merge(base, newer):
    for frame in (base, newer):
        frame["target_group"] = frame.target_group.fillna("")
        assert not frame.duplicated(KEY).any(), "ambiguous model result key"
    replacement = pd.MultiIndex.from_frame(newer[KEY])
    keep = ~pd.MultiIndex.from_frame(base[KEY]).isin(replacement)
    out = pd.concat([base.loc[keep], newer], ignore_index=True)
    assert not out.duplicated(KEY).any()
    return out.sort_values(KEY).reset_index(drop=True), int((~keep).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("analysis/forward"))
    ap.add_argument("--out", type=Path, default=Path("analysis/forward/screen_final"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    bpath, npath = args.root / "screen/screen_outcomes.csv.gz", args.root / "screen_fair_control/screen_outcomes.csv.gz"
    d, replaced = merge(pd.read_csv(bpath), pd.read_csv(npath))
    d.to_csv(args.out / "screen_outcomes.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    coverage = pd.read_csv(args.root / "screen/screen_coverage.csv")
    coverage.to_csv(args.out / "screen_coverage.csv", index=False)
    labs = pd.concat([pd.read_csv(args.root / "results/worker_labels.csv.gz"),
                      pd.read_csv(args.root.parent / "reverse/worker_labels.csv.gz"),
                      pd.read_csv(args.root / "screen/screen_baseline_labels.csv.gz")], ignore_index=True)
    labs["domain"] = labs.domain.replace({"global": "all"})
    labs = labs[labs.known.astype(str).str.lower().eq("true")]
    sizes = labs.groupby(["method_id", "domain", "class_id"]).size()
    ledger = coverage.copy()
    ledger["class_sizes"] = [";".join(f"{c}:{n}" for c, n in sizes.loc[(m, dom)].items())
        if (m, dom) in sizes.index.droplevel(2) else "" for m, dom in zip(ledger.method_id, ledger.domain)]
    ledger["min_class_n"] = [int(sizes.loc[(m, dom)].min()) if (m, dom) in sizes.index.droplevel(2) else 0
        for m, dom in zip(ledger.method_id, ledger.domain)]
    ledger["ranking_stratum"] = np.where(ledger.domain.eq("all"), "all_global", "conditional:" + ledger.domain)
    for panel in ("native_support", "shared_new35"):
        for model in ("linear", "quadratic", "condition_linear", "image_linear"):
            for controlled in (False, True):
                z = d[(d.panel == panel) & (d.model == model) & (d.controlled == controlled) & (d.status == "screened")]
                measure = "additional_reduction_over_Q_origin" if controlled else "mse_reduction_fraction"
                tag = ("common35_" if panel == "shared_new35" else "") + model + ("_extra_Qsource" if controlled else "")
                for outcome in ("B8L2", "D10", "ref_node_recall_9", "ref_edge_recall_9", "footprint_24ray_MSE", "score_failure"):
                    q = z[z.outcome.eq(outcome)][["method_id", "domain", measure]].rename(columns={measure: f"{tag}__{outcome}"})
                    if len(q):
                        ledger = ledger.merge(q, on=["method_id", "domain"], how="left", validate="one_to_one")
    ledger["linear_quality_rank_within_route_and_domain"] = ledger.groupby(["route", "ranking_stratum"])["linear__B8L2"].rank(method="min", ascending=False)
    ledger["selection"] = ["dense_followup" if (m, dom) in SELECTED else "control" if route == "baseline"
        else "not_selected" for m, dom, route in zip(ledger.method_id, ledger.domain, ledger.route)]
    ledger["selection_reason"] = [SELECTED.get((m, dom), "") for m, dom in zip(ledger.method_id, ledger.domain)]
    ledger.loc[ledger.eligible_teams.eq(0), "selection"] = "no_ordinary_screen_opportunity"
    ledger.loc[ledger.min_class_n.eq(1) & ledger.selection.eq("not_selected"), "selection_reason"] = "含单人类；即使有预测收益，也不能支持该类内换人，保留个体特异性反例。"
    ledger.loc[ledger.selection.eq("not_selected") & ledger.selection_reason.eq(""), "selection_reason"] = "全表保留；密集阶段受计算预算约束，优先可解释、真实组内成员支持、质量/结构及表达多样性。未入选不等于无效。"
    ledger = ledger.sort_values(["ranking_stratum", "route", "linear_quality_rank_within_route_and_domain", "method_id"], na_position="last")
    ledger.to_csv(args.out / "candidate_search_ledger.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    selected = ledger[ledger.selection.eq("dense_followup")]
    selected.to_csv(args.out / "selected_candidate_summary.csv", index=False)
    named = list(SELECTED)
    s = d[[ (m, dom) in named for m, dom in zip(d.method_id, d.domain) ]]
    s.to_csv(args.out / "selected_candidate_outcomes.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    receipt = {
        "base_sha256": sha(bpath), "fair_control_sha256": sha(npath), "rows": len(d),
        "rows_replaced_by_equal_flexibility_control": replaced, "candidate_method_domain_instances": len(ledger),
        "distinct_method_ids": int(ledger.method_id.nunique()), "selected_method_domains": [list(x) for x in named],
        "model_selection": "uncontrolled actual-fusion utility plus class/member support, interpretability and representation diversity; not maximum among all model×target cells",
        "control_correction": "quadratic controls include meanQ², meanQ×origin and origin²; condition controls include the same difficulty/scene interactions; linear/image unchanged",
        "validation_read": False,
        "independence": "discovery images only; different heldout teams are not new independent images or personnel",
        "per_image_reconstruction": "same replacement on KEY plus pool_id using screen and screen_fair_control screen_per_image.csv.gz; code can rerun all models directly with current equal-flexibility controls",
    }
    (args.out / "FINAL_SCREEN_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    hard_control_paths = {
        "theta_hard_plus_source": args.root / "screen_hard_domain_Q/screen_outcomes.csv.gz",
        "q_beta_theta_hard_plus_source": args.root / "screen_hard_global_domain_Q/screen_outcomes.csv.gz",
    }
    if all(p.exists() for p in hard_control_paths.values()):
        original = d[(d.method_id == "R_role_ward_difficulty_K2") & d.domain.eq("hard") & d.controlled].copy()
        pieces = [original.assign(control_definition="q_beta_plus_source")]
        compare_key = ["panel", "model", "target_group", "outcome"]
        original_keyed = original.set_index(compare_key).sort_index()
        for name, path in hard_control_paths.items():
            sensitivity = pd.read_csv(path)
            keyed = sensitivity.set_index(compare_key).sort_index()
            assert keyed.index.equals(original_keyed.index), "hard control changed the fixed comparison frame"
            for column in ("tested_teams", "images", "buildings", "pool_size_cells", "baseline_mse"):
                assert np.allclose(keyed[column], original_keyed[column], rtol=1e-12, atol=1e-12, equal_nan=True), column
            pieces.append(sensitivity.assign(control_definition=name))
        pd.concat(pieces, ignore_index=True).to_csv(args.out / "hard_control_sensitivity.csv", index=False)
        hard_receipt = {"same_targets_teams_images_buildings_folds_and_baseline": True,
                        "labels_refit": False, "split_changed": False,
                        "control_definitions": ["q_beta_plus_source", *hard_control_paths],
                        "input_hashes": {str(p): sha(p) for p in hard_control_paths.values()},
                        "validation_read": False}
        (args.out / "HARD_CONTROL_RECEIPT.json").write_text(json.dumps(hard_receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
