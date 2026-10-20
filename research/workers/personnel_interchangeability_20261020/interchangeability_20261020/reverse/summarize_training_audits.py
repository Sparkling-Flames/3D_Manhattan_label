#!/usr/bin/env python3
"""Small review tables for the 15 frozen legacy+mixed direct-risk candidates."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from learn_swap_types import clean,sha,write_csv,write_json

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/"interchangeability_20261020/reverse"
OUT=BASE/"review_tables";OUT.mkdir(parents=True,exist_ok=True)
features=pd.read_csv(ROOT/"analysis/forward/results/features_train.csv.gz")
methodrows=[];classrows=[];personrows=[];candidate_rows=[];searchrows=[]
for family,shortfile in [("legacy","LEGACY_SCREEN_SHORTLIST.json"),("mixed","MIXED_SCREEN_SHORTLIST.json")]:
    fit=BASE/(family+"_fit"); audit=BASE/(family+"_audit");baseline=BASE/(family+"_baselines")
    short=json.load(open(BASE/shortfile)); selected={s["method_id"] for s in short["methods"]}
    manifest=json.load(open(fit/"METHOD_MANIFEST.json"));cv=pd.read_csv(fit/"candidate_cv_summary.csv").set_index("method_id")
    profiles=pd.read_csv(audit/"class_explanations.csv.gz");assoc=pd.read_csv(audit/"method_feature_association.csv.gz").set_index("method_id")
    risks=pd.read_csv(audit/"class_history_relation_tails.csv.gz").set_index(["method_id","class_id"])
    lobo=pd.read_csv(audit/"lobo_label_stability.csv"); matched=pd.read_csv(baseline/"inner_baseline_matched_anchor_draw.csv")
    foldledger=pd.read_csv(fit/"candidate_fold_ledger.csv.gz")
    for mid,spec in manifest.items():
        c=dict(family=family,method_id=mid,domain=spec["domain"],representation=spec["representation"],
            algorithm=spec["algorithm"],K=spec["requested_k"],full_history_status=spec["full_history_status"],
            known_workers=spec["known_workers"],class_sizes="|".join(map(str,spec["class_sizes"].values())),
            pair_known_fraction=spec["pair_known_fraction"],training_events=spec["training_events"],
            training_images=spec["history_images"],training_buildings=len(spec["history_buildings"]),
            selected_for_target_blocks=mid in selected)
        if mid in cv.index:
            c.update({name:cv.loc[mid,name] for name in ["cv_buildings","cv_images","cv_folds","within_stable_main",
                "between_stable_main","within_bad_wide","gap_geometry","gap_continuous","selection_score"]})
        statuses=foldledger[foldledger.method_id.eq(mid)].status.value_counts().to_dict()
        c["fold_status_counts"]=json.dumps(statuses,ensure_ascii=False,sort_keys=True)
        candidate_rows.append(c)
    for domain in sorted({s["domain"] for s in manifest.values()}):
        specs=[s for s in manifest.values() if s["domain"]==domain]
        outcomes=pd.Series([s["full_history_status"] for s in specs]).value_counts().to_dict()
        searchrows.append(dict(family=family,domain=domain,candidates=len(specs),K_min=min(s["requested_k"] for s in specs),
            K_max=max(s["requested_k"] for s in specs),algorithms="complete|spectral|partition_b0|partition_b2",
            expressions="joint|geometry|continuous|context_joint",training_events=specs[0]["training_events"],
            images=specs[0]["history_images"],buildings=len(specs[0]["history_buildings"]),
            full_history_status_counts=json.dumps(outcomes,ensure_ascii=False,sort_keys=True),
            search_unit="person partitions learned from actual fixed-core m1 fusion replacements",
            exhaustive_boundary="all 4x4 algorithm/expression cells and every integer K2..floor(eligible/4); not all mathematical personnel partitions, cores, team compositions or n values",
            input_panel="old A exact n8/12/16/24" if family=="legacy" else "old A exact plus metadata-selected 1576 new anchors at 16 new n nodes",
            ledger_path=str((fit/"candidate_fold_ledger.csv.gz").relative_to(ROOT))))
    for item in short["methods"]:
        mid=item["method_id"];spec=manifest[mid];stats=cv.loc[mid]
        row=dict(family=family,method_id=mid,domain=spec["domain"],K=spec["requested_k"],
            workers=spec["known_workers"],class_sizes="|".join(map(str,spec["class_sizes"].values())),
            minimum_class=min(spec["class_sizes"].values()),
            max_m_available_in_every_class_with_disjoint_same_class_replacement=min(spec["class_sizes"].values())//2,
            cv_buildings=stats.cv_buildings,cv_images=stats.cv_images,within_stable_main=stats.within_stable_main,
            between_stable_main=stats.between_stable_main,gap_main=stats.gap_main,
            within_bad_wide=stats.within_bad_wide,gap_geometry=stats.gap_geometry,
            source_cramers_v=assoc.loc[mid,"source_cramers_v"],q_beta_descriptive_eta2=assoc.loc[mid,"q_beta_eta2"],
            pair_count_descriptive_eta2=assoc.loc[mid,"pair_count_effect_eta2"])
        lo=lobo[lobo.method_id.eq(mid)]
        active=lo[lo.dropped_building.isin(spec["history_buildings"])]
        row.update(lobo_active_buildings=len(active),lobo_successful_fits=int(active.ari.notna().sum()),
            lobo_active_ari_mean=active.ari.mean(),lobo_active_ari_min=active.ari.min(),
            lobo_active_pair_flip_mean=active.pair_flip_fraction.mean(),
            lobo_largest_worker_support_loss=active.dropped_worker_support.max(),
            lobo_noncontributing_building_drops_excluded=len(lo)-len(active))
        for kind,prefix in [("source_only","vs_source"),("random_source_preserving_class_capacity","vs_source_capacity_random")]:
            xx=matched[matched.method_id.eq(mid)&matched.baseline.eq(kind)]
            row[prefix+"_draws"]=len(xx)
            row[prefix+"_buildings_min"]=xx.buildings.min() if len(xx) else np.nan
            row[prefix+"_backgrounds_min"]=xx.matched_backgrounds.min() if len(xx) else np.nan
            for metric in ["gap_main","gap_geometry","within_stable_main","within_bad_wide"]:
                row[prefix+"_delta_"+metric]=xx["delta_"+metric].mean() if len(xx) else np.nan
        methodrows.append(row)
        for c,ws in spec["classes"].items():
            p=profiles[profiles.method_id.eq(mid)&profiles.class_id.eq(c)].iloc[0]
            q=float(p.q_beta_mean);points=float(p.pair_count_effect_mean)
            quality="历史Q偏高" if q>=4 else ("历史Q偏低" if q<=-4 else "历史Q近中")
            shape="略多点" if points>=.1 else ("略少点" if points<=-.1 else "点数近中")
            origin=("全新批" if p.new_workers==p.n_workers else "全旧批" if p.v1_workers==p.n_workers
                else "新批为主" if p.new_workers/p.n_workers>=.8 else "旧批为主" if p.v1_workers/p.n_workers>=.8 else "混合来源")
            name=f"{quality}／{shape}／{origin}"
            risk=risks.loc[(mid,c)]
            rr=dict(family=family,method_id=mid,domain=spec["domain"],class_id=c,
                suggested_descriptive_name_zh=name,workers="|".join(ws),n_workers=len(ws),
                new_workers=int(p.new_workers),v1_workers=int(p.v1_workers),
                q_beta_mean=q,individual_absolute_Q_mean=p.q_abs_mean_mean,
                mean_worker_quality_p10=p.q_abs_p10_mean,pair_count_effect_mean=points,
                history_relative_logT_mean=p.t_source_origin_effect_mean,
                theta_hard_finite_workers=int(p.theta_hard_n),theta_hard_mean=p.theta_hard_mean,
                supported_person_pairs=int(risk.supported_pairs),possible_person_pairs=int(risk.possible_pairs),
                in_sample_pair_main_stability_mean=risk.stable_main_mean,
                in_sample_pair_main_stability_p10=risk.stable_main_p10,
                in_sample_pair_mean_endpoint_Q=risk.mean_endpoint_Q_mean,
                scope_supported_workers=int(p.scope_supported_sum),
                old_confirmed_error_supported_workers=int(p.semi_old_error_nonedit_supported_sum),
                new_reported_error_supported_workers=int(p.semi_new_error_nonedit_supported_sum),
                name_limit="仅用冻结后历史画像辅助阅读；不是拟合定义、等级排序或每次作答保证。重复描述表示画像不足以独立区分细类。")
            classrows.append(rr)
            ff=features[features.worker_id.isin(ws)].copy()
            keep=["worker_id","person_origin","q_beta","q_abs_mean","q_abs_p10","q_residual_p10","q_residual_sd",
                "pair_count_effect","bottom_y_effect","top_y_effect","height_log_effect","t_source_origin_effect",
                "t_log_residual_tail","theta_hard","hard_supported","core_tasks","core_buildings",
                "semi_old_error_nonedit_supported","semi_old_error_nonedit_records","semi_new_error_nonedit_supported",
                "semi_new_error_nonedit_records","scope_supported","scope_out_effect","scope_gold_n"]
            for person in ff[keep].to_dict("records"):
                personrows.append(dict(family=family,method_id=mid,domain=spec["domain"],class_id=c,**person))

write_csv(OUT/"selected_method_history_summary.csv",pd.DataFrame(methodrows))
write_csv(OUT/"selected_class_names_and_profiles_zh.csv",pd.DataFrame(classrows))
write_csv(OUT/"selected_worker_explanations.csv.gz",pd.DataFrame(personrows))
write_csv(OUT/"all_candidate_catalog.csv.gz",pd.DataFrame(candidate_rows))
write_csv(OUT/"REVERSE_SEARCH_LEDGER.csv",pd.DataFrame(searchrows))
write_json(OUT/"METHOD_QUALIFICATIONS.json",clean(dict(
    source_context_baseline="context_joint is centered against the whole same-background entrant graph before domain filtering. Thus source-conditioned context_joint candidates indirectly use other-source entrant outcomes for centering on TRAINING buildings; no fold/building leakage. None of the 15 selected source-conditional methods uses context_joint.",
    source_only_baseline="When source partition cannot provide both within/between pairs on an anchor it is unavailable, not zero. Paired tables use only the exact common-anchor intersection.",
    lobo_summary="Only dropped buildings that actually contributed domain outcomes enter the headline mean. Hard domain has 6 active buildings; dropping 4 non-hard buildings trivially yields unchanged labels and is excluded.",
    nontransitivity="Old engineering joint thresholds and no-Q geometric thresholds need not be transitive. Same-context open wedges are exact actual-output relations, not estimates; aggregate edge wedges have explicitly different opportunity sets.",
    profiles="All Q/T/Semi/scope/shape summaries use the frozen 10-history-building feature file. FULL labels and target outcomes are not used. Names are descriptions only; eta-squared increases with class flexibility and is not incremental predictive information.",
    bad_tails="Pair-history p10 is a quantile across supported PERSON-PAIR mean stability values, not a per-team Q p10. Empirical heldout wide-threshold failure is retained separately.",
    gaps="Direct risk classification searches actual replacement evidence, yet remains heuristic; it does not enumerate every possible partition, team, background, n or ratio. All integer K permitted by minimum-four capacity were attempted.",
    no_new_independent_claim="CV buildings are within already explored v2 history. Root target blocks are separate class-efficacy checks; new teams do not increase the number of independent images or buildings.",
    source_script_sha256=sha(Path(__file__)),selected_methods=len(methodrows),selected_classes=len(classrows),
    selected_worker_class_rows=len(personrows),all_candidates=len(candidate_rows))))
