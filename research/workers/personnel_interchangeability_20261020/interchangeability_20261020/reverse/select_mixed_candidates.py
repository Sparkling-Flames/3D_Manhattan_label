#!/usr/bin/env python3
"""Freeze a support/diversity shortlist after history-only inner CV.

This list was chosen before reading any new discovery/validation replacement
outcomes. The whole 1,040-candidate ledger is retained, including failed folds.
"""
from datetime import datetime,timezone
import json
from pathlib import Path
import pandas as pd
from learn_swap_types import clean,sha,write_csv,write_json

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/"interchangeability_20261020/reverse"
FIT=BASE/"mixed_fit"
SPEC=[
    ("ordinary","continuous","partition_b2",3,"coarse no-Q continuous risk with wide-geometry-tail penalty; large replaceable classes"),
    ("ordinary","geometry","partition_b0",7,"no-Q geometry risk, seven classes with minimum six people; strongest broad-support middle-K geometry separation"),
    ("ordinary","joint","partition_b0",10,"high-K actual joint-risk stress; all ten history buildings evaluated, minimum four capacity explicitly restrictive"),
    ("ordinary_new","geometry","partition_b2",2,"same-source 35-person coarse no-Q path; every class/source count cannot itself be the discriminating variable"),
    ("ordinary_new","geometry","partition_b0",7,"same-source fine no-Q risk path; high-K support/capacity challenge retained"),
    ("hard_new","joint","partition_b2",3,"same-source difficulty-conditional coarse classes, all six available hard buildings in CV and capacity9/14/12"),
    ("hard_new","geometry","partition_b0",7,"same-source hard no-Q geometry path; all six available hard buildings, high bad tail still retained"),
    ("small_n","geometry","partition_b2",7,"n<=12 conditional no-Q risk with bad-tail penalty, all ten history buildings; evaluates whether weak small-team stability is condition-specific"),
    ("large_n","continuous","partition_b0",2,"n>=16 coarse continuous-risk classes; avoids selecting apparent best high-K rows that lose two CV buildings"),
    ("hard","geometry","spectral",7,"source-inclusive hard comparator to hard_new; supported within-class relations, remaining source association must be disclosed"),
]
manifest=json.load(open(FIT/"METHOD_MANIFEST.json")); summary=pd.read_csv(FIT/"candidate_cv_summary.csv").set_index("method_id")
registration=json.load(open(FIT/"REGISTRATION.json"))
methods=[]; rows=[]
fields=["cv_buildings","cv_folds","cv_images","cv_within_events","cv_between_events",
        "within_stable_main","between_stable_main","within_bad_wide","within_failure",
        "gap_main","gap_geometry","gap_continuous","selection_score",
        "within_abs_B8L2_change","between_abs_B8L2_change"]
for domain,representation,algorithm,k,reason in SPEC:
    mid=f"R_directswap_{representation}_{algorithm}_K{k}__{domain}__mixed_history_v1"
    spec=manifest[mid]; stats=summary.loc[mid]
    assert spec["full_history_status"]=="ok" and min(spec["class_sizes"].values())>=4
    assert stats.cv_buildings==(6 if domain.startswith("hard") else 10)
    row=dict(method_id=mid,domain=domain,representation=representation,algorithm=algorithm,K=k,
             class_sizes="|".join(map(str,spec["class_sizes"].values())),selection_reason=reason,
             **{f:stats[f] for f in fields})
    rows.append(row)
    methods.append(dict(method_id=mid,domain=domain,selection_reason=reason,
        known_workers=spec["known_workers"],class_sizes=spec["class_sizes"],classes=spec["classes"],
        training_n_values=spec["training_n_values"],inner_cv={f:stats[f] for f in fields},
        entrant_domain=registration["domains"][domain],
        fixed_background="Workers outside this domain may only remain unchanged background; inference applies to the actually tested background/source restriction.",
        difficulty_boundary="Existing reviewed reference-aligned difficulty; not a new-image automatic pre-collection classifier" if domain.startswith("hard") else None))
result=dict(schema="mixed_history_direct_replacement_shortlist_v1",
    frozen_utc=datetime.now(timezone.utc).isoformat(),
    labels=str((FIT/"worker_labels.csv.gz").relative_to(ROOT)),labels_sha256=sha(FIT/"worker_labels.csv.gz"),
    full_manifest_sha256=sha(FIT/"METHOD_MANIFEST.json"),candidate_cv_sha256=sha(FIT/"candidate_cv_summary.csv"),
    selection_source="Only fixed five two-building inner history folds; no new discovery/validation outcomes read",
    candidate_total=1040,full_history_valid_candidates=752,
    selection_principles=["all available domain buildings represented in CV; incomplete-fold apparent winners not promoted",
        "coarse/intermediate/high integer K, direct joint/no-Q geometry/continuous risk and n/difficulty domains",
        "explicit new-source paths; source-inclusive hard candidate remains a sensitivity comparator",
        "within-class remaining bad tail and minimum class capacity retained; no claim of universal interchangeability"],
    excluded_important=["hard_v1 has full-history partitions but no inner held-out same-background comparison after history support gates; not promoted",
        "complete-linkage tiny classes and unsupported relation classes are retained as failed candidates, not singletons",
        "higher score obtained by dropping held-out buildings is not comparable to complete-support scores"],
    pending_history_audits=["source-only and exact source-preserving class-capacity random baselines",
        "leave-one-history-building labels and opportunity shrinkage",
        "class explanatory features and same-background nontransitivity"],
    methods=methods)
write_json(BASE/"MIXED_SCREEN_SHORTLIST.json",clean(result))
write_csv(BASE/"MIXED_SCREEN_SHORTLIST.csv",pd.DataFrame(rows))
print(json.dumps({"methods":len(methods),"shortlist_sha256":sha(BASE/"MIXED_SCREEN_SHORTLIST.json")},ensure_ascii=False))
