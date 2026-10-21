#!/usr/bin/env python3
"""Reconcile frozen personnel methods and experimental coverage without rerunning fusion.

Run from any directory: python path/to/coverage/build_coverage.py.
All paths in exported tables are relative to the input repository root.  This
ledger separates fitted domains, population gates, and extra geometry.  It does
not call a joint full model evidence that every proper subset was investigated.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
INPUT_COMMIT = "51b519f943b2dd3a4fb2f0198133ac5dd17209ab"
OLD = Path("research/workers/personnel_composition_study_20261019")
NEW = Path("research/workers/personnel_interchangeability_20261020/interchangeability_20261020")
EARLY = Path("research/workers/personnel_type_discovery_next_20261019/work_personnel_typing_A_20261019/forward")
FOLLOW = Path("research/workers/personnel_interchangeability_followup_20261020/audit_learning")
TAX = Path("research/workers/personnel_taxonomy_20261021")
DOMAINS = ("Q", "T", "D", "Scope", "Semi")
READS = set()


def read_json(p):
    p = Path(p)
    READS.add(p)
    return json.loads((ROOT / p).read_text())


def read_csv(p):
    p = Path(p)
    READS.add(p)
    return pd.read_csv(ROOT / p)


def save_csv(name, rows):
    pd.DataFrame(rows).to_csv(HERE / name, index=False)


def ordered(values):
    return "|".join(d for d in (*DOMAINS, "Geometry") if d in values)


def field_domain(field):
    if field in {"Q", "T"}:
        return field
    if field in {"difficulty"} or any(t in field for t in ("hard_minus", "medium_minus")):
        return "D"
    if "scope" in field:
        return "Scope"
    if field == "semi" or "edit" in field:
        return "Semi"
    if field == "structure" or any(t in field for t in ("pair_", "bottom_y", "top_y", "height_")):
        return "Geometry"
    if field == "T" or field.startswith("t_") or "time_" in field:
        return "T"
    if field.startswith(("q_", "theta_")) or "_q_" in field:
        return "Q"
    raise ValueError(f"Unmapped feature: {field}")


def spec_methods(path):
    return {x["method_id"] for x in read_json(path)["methods"]}


def observed_methods(path):
    if not (ROOT / path).exists():
        return set()
    d = read_csv(path)
    return set(d.method_id)


old_manifest = read_json(OLD / "analysis/forward/results/method_manifest.json")
new_manifest = read_json(NEW / "forward/method_manifest.json")
search = read_json(OLD / "analysis/SEARCH_COVERAGE_NOTES.json")
early_domains = read_json(EARLY / "FEATURE_DOMAINS.json")
early_registration = read_json(EARLY / "REGISTRATION.json")
early_summary = read_json(EARLY / "FORWARD_SUMMARY_NUMBERS.json")
forward_labels = read_csv(NEW / "forward/worker_labels.csv.gz")
features = read_csv(NEW / "forward/features_train.csv.gz")
common16 = read_csv(NEW / "forward/common_panel/compact_two_phase_evidence/common16_methods.csv.gz")
hist_lobo = read_csv(NEW / "forward/HISTORY_LOBO_summary.csv")
common_methods = set(common16.method_id)
disc_spec = spec_methods(NEW / "discovery/FORWARD_SPEC.json")
assess_spec = spec_methods(NEW / "assessment/DIRECTION_SPEC.json")
disc_observed = observed_methods(NEW / "forward/discovery_interpretation/method_aggregate.csv.gz")
assess_observed = observed_methods(NEW / "forward/assessment_interpretation/F11_aggregate.csv.gz")
screen_path = OLD / "analysis/forward/screen_final/candidate_search_ledger.csv.gz"
screen = read_csv(screen_path) if (ROOT / screen_path).exists() else pd.DataFrame()
old_method_sets = {k: {x["method_id"] for x in v} for k, v in search["method_sets"].items()}

ledger = []


def add_method(stage, mid, fields, gate, condition, label_source, n_people, k,
               label_status, screen_status, planned, observed, audit, extra_note=""):
    fit = {field_domain(f) for f in fields}
    if "Adapt" in mid:
        # These rules split a person's difficulty-specific Q relative to q_beta.
        fit.add("D")
    fit_five = fit - {"Geometry"}
    joint = fit_five | set(gate)
    ledger.append({
        "stage": stage, "method_id": mid, "fitted_domains": ordered(fit_five),
        "extra_geometry_domain": "Geometry" in fit,
        "population_gate_domains": ordered(gate),
        "fit_plus_population_domains": ordered(joint),
        "pure_fitted_subset": ordered(fit_five) if "Geometry" not in fit and len(fit_five) >= 2 else "",
        "pure_conditioned_subset": ordered(joint) if "Geometry" not in fit and len(joint) >= 2 else "",
        "condition": condition, "known_people": n_people, "classes": k,
        "label_status": label_status, "label_source": str(label_source),
        "ordinary_screen_status": screen_status,
        "actual_team_plan_stages": "|".join(sorted(planned)),
        "actual_team_result_stages": "|".join(sorted(observed)),
        "independent_check": audit, "fields": "|".join(fields), "note": extra_note,
    })


# Early 28 are family x requested-K definitions, not 28 independent domain sets.
early_families = ("full", "minus_difficulty", "minus_semi", "minus_scope", "minus_structure", "QT_only", "base_plus_difficulty")
for family in early_families:
    groups = {"Q", "T"} if family == "QT_only" else set(early_domains)
    if family.startswith("minus_"):
        groups.remove(family.removeprefix("minus_"))
    for k in early_registration["candidates_K"]:
        mid = f"fw_{family}_K{k}"
        add_method("early_type_discovery_20261019", mid,
                   list(itertools.chain.from_iterable(early_domains[g] for g in sorted(groups))), [],
                   "ordinary Manual; auxiliary Semi/scope history is explicitly cross-condition",
                   EARLY / "candidate_labels_by_training_set.csv.gz", "context-specific", k,
                   "export receipts; selected FULL membership separately read", "nested candidate screening",
                   [], [], "frozen nested export and feature replay receipts",
                   "base_plus_difficulty refines the full-six-domain parent; not a pure Q+D model" if family == "base_plus_difficulty" else
                   "69 distinct training sets; 23 selection contexts; all selected QT_only_K4; not new whole-composition experiment")

for mid, m in old_manifest["methods"].items():
    selected_screen = "registry only; per-method screen table unavailable"
    if len(screen):
        q = screen[screen.method_id.eq(mid)]
        selected_screen = ";".join(sorted(set(q.selection.astype(str)))) if "selection" in q else f"screen ledger rows={len(q)}"
        if len(q) and not q.eligible_teams.fillna(0).gt(0).any():
            selected_screen += ";no_ordinary_team_opportunity"
        if "status" in q:
            selected_screen += ";" + ";".join(sorted(set(q.status.astype(str))))
    stages = {name for name, methods in old_method_sets.items() if mid in methods}
    add_method("composition_forward_20261019", mid, m["features"], [], m["domain"],
               OLD / "analysis/forward/results/worker_labels.csv.gz", m["known_workers"], m["actual_classes"],
               "frozen class membership verified in manifest", selected_screen, stages, stages,
               "frozen request reproduction and selected case replay; not every team replayed in this round",
               "QTDS S is structure/geometry, not Scope")

for mid, m in new_manifest["methods"].items():
    plan = set()
    obs = set()
    if mid in disc_spec: plan.add("discovery_direct_events")
    if mid in assess_spec: plan.add("assessment_direct_events")
    if mid in disc_observed: obs.add("discovery_direct_events")
    if mid in assess_observed: obs.add("assessment_direct_events")
    if mid in common_methods:
        plan.update({"common26_discovery_m2", "common26_assessment_m2"})
        obs.update({"common26_discovery_m2", "common26_assessment_m2"})
    label_rows = forward_labels[forward_labels.method_id.eq(mid)]
    assert len(label_rows) == 60
    known = int(label_rows.known.fillna(False).sum())
    assert known == m["known_workers_n"]
    add_method("interchangeability_forward_20261020", mid, m["required_fields"],
               ["Q"] if "highQ" in mid else [], m["pool_filter"],
               NEW / "forward/worker_labels.csv.gz", known, m["classes_n"], m["status"],
               "history opportunity/capacity screen; no target outcomes in label generation",
               plan, obs, "all 188 definitions and 11280 labels independently reconstructed; selected actual teams replayed",
               "highQ is a population condition, not an additional fitted field; missing opportunities stay unknown")

save_csv("METHOD_DOMAIN_LEDGER.csv", ledger)
ld = pd.DataFrame(ledger)

# Opportunity check uses the already frozen 10-building history.  New Semi
# report and old confirmed-error evidence must not silently become one field.
opportunity_fields = {
    "Q": ["q_beta", "q_residual_p10", "q_residual_sd"],
    "T": ["t_source_origin_effect", "t_log_residual_tail"],
    "D": ["hard_minus_easy", "medium_minus_easy"],
    "Scope": ["scope_out_effect"],
    "Semi": ["semi_new_edit_effect", "semi_new_error_nonedit_effect"],
}
subset_rows = []
for n in range(2, 6):
    for ds in itertools.combinations(DOMAINS, n):
        key = ordered(ds)
        fitted = ld[ld.pure_fitted_subset.eq(key)]
        conditioned = ld[ld.pure_conditioned_subset.eq(key) & ~ld.pure_fitted_subset.eq(key)]
        augmented = ld[ld.extra_geometry_domain.eq(True) & ld.fit_plus_population_domains.eq(key)]
        exact_any = pd.concat([fitted, conditioned])
        fit_teams = fitted[fitted.actual_team_result_stages.ne("")]
        cond_teams = conditioned[conditioned.actual_team_result_stages.ne("")]
        required = list(itertools.chain.from_iterable(opportunity_fields[x] for x in ds))
        ok = features.core_supported.eq(True) & features[required].notna().all(axis=1)
        new_ok = ok & features.person_origin.eq("new")
        subset_rows.append({
            "subset_id": key, "domain_count": n, "coverage_time": "before_current_round; input main 51b519f",
            "pure_fitted_candidate_definitions": len(fitted),
            "pure_population_conditioned_definitions": len(conditioned),
            "extra_geometry_definitions": len(augmented),
            "pure_fitted_actual_team_methods": len(fit_teams),
            "pure_conditioned_actual_team_methods": len(cond_teams),
            "pure_fitted_old_screen_methods": int(fitted.stage.eq("composition_forward_20261019").sum()),
            "pure_conditioned_old_screen_methods": int(conditioned.stage.eq("composition_forward_20261019").sum()),
            "labels_status": "fitted" if len(fitted) else "population_conditioned_only" if len(conditioned) else "not_found_pure_subset",
            "team_status": "actual_pure_fitted_results" if len(fit_teams) else "actual_population_conditioned_results" if len(cond_teams) else "no_pure_subset_composition_result_found",
            "independent_check_scope": "188 forward label reconstruction; selected team replay" if any(exact_any.stage.eq("interchangeability_forward_20261020")) else "old export/screen evidence only" if len(exact_any) else "not_done_for_pure_subset",
            "history_domain_complete_core_people": int(ok.sum()),
            "history_domain_complete_new_people": int(new_ok.sum()),
            "support_status": "history_fields_available; target team capacity still image-specific" if ok.any() else "no_complete_history_fields",
            "not_done": "systematic whole-composition/member enumeration for this pure subset; class utility not implied by existing labels",
            "fitted_example_methods": ";".join(fitted.method_id.head(4)),
            "conditioned_example_methods": ";".join(conditioned.method_id.head(4)),
            "extra_geometry_example_methods": ";".join(augmented.method_id.head(3)),
            "history_required_fields": "|".join(required),
            "scope_caution": "Scope is out-response tendency, not adjudicated accuracy; Semi uses new self-reported error opportunity and edit state; no inferred precise edit trajectory",
        })
assert len(subset_rows) == 26
save_csv("DOMAIN_SUBSET_COVERAGE.csv", subset_rows)

current_domain_path = Path("research/workers/personnel_global_composition_20261021/multivariate/domain_subset_26_coverage.csv")
if (ROOT / current_domain_path).exists():
    current = read_csv(current_domain_path)
    current["subset_id"] = current.domain_subset.str.replace("+", "|", regex=False).str.replace("scope", "Scope", regex=False)
    old_for_join = pd.DataFrame(subset_rows).drop(columns=["domain_count"])
    joined = current.merge(old_for_join, on="subset_id", validate="many_to_one", suffixes=("_current", "_old"))
    assert len(joined) == 52
    joined.to_csv(HERE / "OLD_NEW_DOMAIN_COVERAGE.csv", index=False)

# Exact old stage counts are retained separately from any later stage.  Per-stage
# unique sets overlap; only the original global union is an additive endpoint.
stages = read_csv(OLD / "analysis/composition/coverage/stage_coverage.csv")
experiment_rows = []
for _, row in stages.iterrows():
    record = row.to_dict()
    record.update(stage_family="composition_study_20261019", count_scope="within-stage; cannot add unique_teams across rows")
    meta = search["metadata_coverage"].get(row.stage, {})
    for field in ("feasible_vectors", "selected_vectors", "omitted_feasible_vectors", "member_exhaustive_cells", "member_sampled_cells", "attempted_patterns", "capped_pattern_candidates", "capped_patterns_not_attempted"):
        record[field] = meta.get(field, "")
    record["actual_turnover_values"] = "|".join(map(str, meta.get("actual_turnover_values", [])))
    record["order_coverage"] = "sampled chains and orders" if "nested" in row.stage else "not enumerated / irrelevant to deterministic endpoint"
    record["physical_cache_identity"] = "historical endpoints; compact summaries and cases; full requests reconstructable; no claim all native geometry is presently cached"
    record["source"] = str(OLD / "analysis/composition/coverage/stage_coverage.csv")
    experiment_rows.append(record)
save_csv("EXPERIMENT_COVERAGE.csv", experiment_rows)

# Compact old shared-panel evidence, retaining all16 and both phases.
alln = common16[common16.n.astype(str).eq("ALL")]
alln.to_csv(HERE / "COMMON16_RESULT_CHECK.csv", index=False)
m2 = read_csv(FOLLOW / "block_fit/paired_summary.csv")
m2_cols = ["method_id", "baseline", "matched_anchors", "candidate_within_distance", "baseline_within_distance", "delta_within_distance", "candidate_between_distance", "baseline_between_distance", "delta_between_distance"]
m2[m2_cols].to_csv(HERE / "DIRECT_M2_NEGATIVE_RESULT_CHECK.csv", index=False)

# Exact identities and full-data membership are an index, never interchangeable
# heldout labels.  The taxonomy class catalog preserves its own stage labels.
catalog = read_csv(TAX / "labels/class_catalog.csv")
catalog.to_csv(HERE / "EXISTING_TAXONOMY_CLASS_MEMBERS.csv", index=False)
manual = read_csv(TAX / "labels/manual_labels.csv")
semi = read_csv(TAX / "labels/semi_labels.csv")
working = read_csv(FOLLOW / "RESEARCH_WORKING_LABELS_60.csv")
schema = read_json(FOLLOW / "RESEARCH_WORKING_LABELS_SCHEMA.json")
correction = read_json(TAX / "CORRECTION_RECEIPT.json")

identities = [
    {"method": "M", "definition": "Manual structure Ward K2 plus nested K4; short turns, ordinary turns and near-straight redundancy are distinct",
     "population": "Manual; 59 assigned of 62 inventory workers", "coarse_sizes": "M0:40|M1:19", "fine_sizes": "M00:6|M01:34|M10:13|M11:6",
     "label_source": str(TAX / "labels/manual_labels.csv"), "heldout_source": str(TAX / "labels/lobo_labels.csv"),
     "proper_use": "Manual descriptive coarse structure; fine conditional explanatory subtypes", "old_team_scope": "main n5/m1,n9/m2,n13/m3; counts in taxonomy report; 5810 unique new teams across routes",
     "increment_limit": "structure is not Q; no old proof of structure-specific team gain beyond history Q"},
    {"method": "SP", "definition": "Semi position/scale Ward K3 aggregated to K2; final geometry, not imagined edit trajectory",
     "population": "Semi; 59 assigned of 62 inventory workers", "coarse_sizes": "SP_LOW:5|SP_OTHER:54", "fine_sizes": "SP_L:5|SP_A:5|SP_T:49",
     "label_source": str(TAX / "labels/semi_labels.csv"), "heldout_source": str(TAX / "labels/lobo_labels.csv"),
     "proper_use": "conditional scale group; SP_T a comparison group, not homogeneous style", "old_team_scope": "Semi-specific cases and replacement checks; small SP_L capacity limits within replacements",
     "increment_limit": "Manual M used under Semi is auxiliary only; does not replace SP classification"},
    {"method": "A2", "definition": "cross-image continuous raw-answer geometric relationship partition; Manual and Semi fitted separately",
     "population": "Manual 59; Semi 59", "coarse_sizes": "Manual A01:17|A02:23|A03:19; Semi A01:24|A02:17|A03:18", "fine_sizes": "not a finer level of M or SP",
     "label_source": str(TAX / "route_a/worker_labels.csv"), "heldout_source": str(TAX / "route_a/worker_labels_lobo.csv"),
     "proper_use": "independent raw-answer similarity axis", "old_team_scope": "relabels reused 63476 historical pair comparisons plus dedicated A2 panel",
     "increment_limit": "count-matched Q/source result corrected; same-answer similarity does not itself prove fusion interchangeability"},
    {"method": "Rnew2", "definition": "R_directswap_geometry_partition_b2_K2__ordinary_new__mixed_history_v1",
     "population": "35 new workers; Manual ordinary", "coarse_sizes": "C01:21|C02:14", "fine_sizes": "none adopted",
     "label_source": str(FOLLOW / "RESEARCH_WORKING_LABELS_60.csv"), "heldout_source": str(NEW / "reverse/mixed_fit/worker_labels.csv.gz"),
     "proper_use": "working actual replacement-geometry relation class on frozen history10 / target12 split", "old_team_scope": "includes n13/m5; primary and fresh probes; reversals preserved",
     "increment_limit": "not a Semi class; 10 history delete-one sensitivity is not target22 LOBO labels"},
    {"method": "F01", "definition": "F20_highQ23_T_qK2; high-Q history population followed by relative-time quantile",
     "population": "23 high-Q workers; new15+old8; ordinary Manual", "coarse_sizes": "C01 fast:12|C02 slow:11", "fine_sizes": "conditional speed split within highQ population",
     "label_source": str(FOLLOW / "RESEARCH_WORKING_LABELS_60.csv"), "heldout_source": str(NEW / "forward/HISTORY_LOBO_labels.csv.gz"),
     "proper_use": "efficiency direction; source/task-adjusted historical time", "old_team_scope": "n13/m2 primary C02 to C01; stress and composition followup",
     "increment_limit": "speed direction need not yield geometric separation; no source-mixed absolute-time causal claim"},
    {"method": "Full16", "definition": "same26 new people; Full/drop one of seven field groups; K2/K3",
     "population": "26 complete-field new workers", "coarse_sizes": "method-specific; see COMMON26_CLASS_MEMBERS.csv", "fine_sizes": "K3 is separate partition, not declared nested K2 refinement",
     "label_source": str(NEW / "forward/worker_labels.csv.gz"), "heldout_source": str(NEW / "forward/HISTORY_LOBO_labels.csv.gz"),
     "proper_use": "domain-ablation common-team comparison", "old_team_scope": "same-team common16 panel; n5/9/13/17,m2; both discovery and assessment",
     "increment_limit": "7 field groups are Q,T,D,Geometry,edit,new_error_nonedit,Scope; edit+nonedit together are one Semi domain"},
    {"method": "continuous_Q_T_D_Scope_Semi", "definition": "continuous domain-balanced historical variables and component responses; compare to categories without inventing fixed people types",
     "population": "per-domain observed support; 60 old history table; profiles separate182 condition-person records", "coarse_sizes": "not applicable", "fine_sizes": "not applicable",
     "label_source": str(NEW / "forward/features_train.csv.gz"), "heldout_source": "research/workers/personnel_profiles_composition_20261020/tables/history_lobo.csv",
     "proper_use": "continuous baseline / category explanation / source and Q adjustment after total effect", "old_team_scope": "previous high-low Q, fast-slow mixtures; not new multi-domain taxonomy",
     "increment_limit": "time retains source/unit; response propensity is not accuracy; lack of editing opportunity stays unknown"},
]
save_csv("METHOD_IDENTITIES.csv", identities)
common_members = forward_labels[forward_labels.method_id.isin(common_methods) & forward_labels.known.eq(True)].copy()
common_members.to_csv(HERE / "COMMON26_CLASS_MEMBERS.csv", index=False)
working.to_csv(HERE / "EXISTING_RNEW2_F01_MEMBERS.csv", index=False)

legacy_manifest = read_json(NEW / "reverse/legacy_fit/METHOD_MANIFEST.json")
mixed_manifest = read_json(NEW / "reverse/mixed_fit/METHOD_MANIFEST.json")
assert len(legacy_manifest) == 768 and len(mixed_manifest) == 1040
assert len(old_manifest["methods"]) == 157 and len(new_manifest["methods"]) == 188
assert len(forward_labels) == 11280 and len(common_methods) == 16

receipt = {
    "schema": "personnel_classification_coverage_v1_20261021", "input_main": INPUT_COMMIT,
    "purpose": "old research coverage; no fusion run and no existing label refit by this script",
    "five_domains": list(DOMAINS), "extra_geometry_not_scope": True,
    "method_definitions": {"early_forward": 28, "old_forward": 157, "later_forward": 188, "reverse_legacy": 768, "reverse_mixed": 1040},
    "old245_identity": search["candidate_counts"], "old_global_set_union": search["overall"],
    "pure_fitted_subsets": [x["subset_id"] for x in subset_rows if x["pure_fitted_candidate_definitions"]],
    "conditional_only_subsets": [x["subset_id"] for x in subset_rows if not x["pure_fitted_candidate_definitions"] and x["pure_population_conditioned_definitions"]],
    "no_pure_old_definition": [x["subset_id"] for x in subset_rows if not x["pure_fitted_candidate_definitions"] and not x["pure_population_conditioned_definitions"]],
    "common16_actual_table": {"rows": len(common16), "per_phase": common16.groupby("phase").method_id.nunique().to_dict(), "n": sorted(common16.n.astype(str).unique())},
    "forward_actual_observed_methods": {"discovery": len(disc_observed), "assessment": len(assess_observed)},
    "forward_plan_methods": {"discovery": len(disc_spec), "assessment": len(assess_spec)},
    "history_opportunity_fields": opportunity_fields,
    "history_opportunity_caution": "field-complete support, not target image substitution capacity; new report Semi evidence is not old confirmed error or exact initialization",
    "taxonomy_correction": correction,
    "physical_cache_caution": "historical computed unique sets != all currently available native geometries; requests reconstructable separately; current-run cache intersection delegated to composition coverage",
    "source_files": [{"path": str(p), "bytes": (ROOT / p).stat().st_size, "sha256": hashlib.sha256((ROOT / p).read_bytes()).hexdigest()} for p in sorted(READS)],
}
(HERE / "COVERAGE_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
save_csv("STAGE_IDENTITY_LEDGER.csv", [
    {"stage": "type_discovery_next_20261019", "labels": "28 forward; 64 reverse", "screening": "nested 69 training sets / 23 selection contexts; QT_only_K4 selected in all23", "actual_team_scope": "earlier selected-class checks; no all26 domain experiment", "independent_check": "feature/partition replay receipts", "coverage_limit": "candidate definitions and selected label exports; not new whole-composition sweep", "source": str(EARLY / "FORWARD_SUMMARY_NUMBERS.json")},
    {"stage": "composition_study_20261019", "labels": "157 forward +62 reverse method ids /78 reverse domains +10 baseline =229 ids/245 method-domain instances", "screening": "16 no ordinary opportunity;211 screen not selected;8 screen dense followup", "actual_team_scope": "589990 requests;583261 unique sets;13 stages;126 pools;106 images;12 buildings;59 workers", "independent_check": "frozen 13-request reconstruction; duplicate geometry parity; selected case replay", "coverage_limit": "269732 breadth configurations /36009 selected;member/order sampling remains;stage counts overlap", "source": str(OLD / "analysis/SEARCH_COVERAGE_NOTES.json")},
    {"stage": "interchangeability_forward_20261020", "labels": "188 methods;11280 rows;184 supported;179 distinct supported domain partitions", "screening": "history capacity + opportunity;36 shortlist;50 methods x10 history delete folds", "actual_team_scope": "61 discovery method IDs with actual aggregates;10 method IDs/11 assessment directions;common26 all16 same-team comparison", "independent_check": "all188 labels reconstructed;500 ARI records checked;selected native teams replayed", "coverage_limit": "common panel n5/9/13/17,m2;sampled backgrounds/blocks;not all compositions", "source": str(NEW / "forward/BUILD_RECEIPT.json")},
    {"stage": "reverse_actual_replacement_20261020", "labels": "legacy768 + mixed1040;Rnew2 ordinary_new35 C01:21/C02:14", "screening": "actual historical replacement-geometry/joint relations;candidate/label manifests retained", "actual_team_scope": "Rnew2 n13/m5 and fresh block probes exist;member and building sensitivities retained", "independent_check": "1808 manifests checked;Rnew2 full+10 delete folds+5 inner refits", "coverage_limit": "manifest check does not mean all1808 refitted in audit;conditional working partition", "source": str(NEW / "reverse/mixed_fit/METHOD_MANIFEST.json")},
    {"stage": "direct_m2_block_learning_followup", "labels": "K2/K3 direct-m2 candidates;not adopted over Q/Rnew2", "screening": "7670 teams;20 history images;10 buildings;160 backgrounds;144140 block comparisons", "actual_team_scope": "fixed matched anchors compare K2/K3 to Q and original Rnew2;negative within-distance increments", "independent_check": "paired_summary.csv actually read this round;retained recovery/refit receipts", "coverage_limit": "do not rerun the same m2 objective as novel;new large-block questions remain separate", "source": str(FOLLOW / "block_fit/paired_summary.csv")},
    {"stage": "interchangeability_independent_audit_20261020", "labels": "60x328 features;188 methods/11280 labels;1808 reverse manifests;selected true refits", "screening": "18 design streams:16 rule rebuilt,2 exact frozen requests", "actual_team_scope": "17726 core teams;32 native fields+geometry;1819 events;10 cases39 teams", "independent_check": "independent source replay;not whole569529-team repeat", "coverage_limit": "audited subset distinct from historical experimental union", "source": "research/statistics/personnel_interchangeability_audit_20261020/README.md"},
    {"stage": "followup_recovery_completed_20261020", "labels": "unchanged;no refit or new selection", "screening": "3844 inputs hash checked", "actual_team_scope": "69164 frozen endpoints;10 reconstructed tables 5104246 rows;29 retained tables63467 rows matched", "independent_check": "current reconstructed outputs verified;not byte parity with unavailable historical full tables", "coverage_limit": "CDF4752992 rows/96series;8MiB parts;oneoldPNG and19item historical count difference unresolved", "source": "research/workers/personnel_interchangeability_followup_20261020/RECOVERY_STATUS.md"},
    {"stage": "profiles_composition_20261020", "labels": "182 profiles=Manual62/Semi61/doorway59;not new formal personnel types", "screening": "3997 historyLOBO rows;182profiles;source/Q/time definitions retained", "actual_team_scope": "15404 selected-team membership/scalar rows retained;12case native geometries;source88048 computed sets claim kept separate", "independent_check": "80 speed-summary rows and 12 selected native teams rechecked in existing integration", "coverage_limit": "not a re-run of all88048;4fast1slow/H-L analyses should be reused", "source": "research/workers/personnel_profiles_composition_20261020/README.md"},
    {"stage": "taxonomy_20261021_original", "labels": "124 inventory condition-worker rows;118assigned;2108LOBO;ManualM/SemiSP/A2 separate", "screening": "structural and geometric relation candidates;final and heldout labels separate", "actual_team_scope": "5810 dedicated unique teams;old63476 pair comparisons relabeled;main n5m1/n9m2/n13m3", "independent_check": "later two-statistic correction;current Markdown/CSV supersede affected originalHTML/PDF numbers", "coverage_limit": "original input6503e2f;not same stage as new global-composition study", "source": str(TAX / "README.md")},
    {"stage": "taxonomy_20261021_corrected", "labels": "unchanged", "screening": "reference-panel->image->building weights;Q/source pair match adds shared corner count", "actual_team_scope": "no new fusion;no new labels;Manualturn+.6070677156;short+.3359067751;A2Manual-.4961142551/Semi-.2433894144deg", "independent_check": "CORRECTION_RECEIPT and correctedCSV authoritative for affected statistics", "coverage_limit": "correction is not an independent new dataset or new team experiment", "source": str(TAX / "CORRECTION_RECEIPT.json")},
])
print(json.dumps({k: receipt[k] for k in ("input_main", "pure_fitted_subsets", "conditional_only_subsets", "no_pure_old_definition", "forward_actual_observed_methods")}, ensure_ascii=False, indent=2))
