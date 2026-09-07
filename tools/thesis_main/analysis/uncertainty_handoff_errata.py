"""Post-hoc errata for initialization joins and association bootstrap denominators."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[3]
INPUT = ROOT / "analysis_results" / "uncertainty_cloud_inputs_20260906_v1"
REPRODUCED = ROOT / "analysis_results" / "uncertainty_visual_review_20260907_v1" / "reproduced_numerical"
OUTPUT = ROOT / "analysis_results" / "uncertainty_visual_review_20260907_v1" / "errata"
SEED = 20260906
REQUESTED = 500


def _block(value: object) -> str:
    text = str(value).strip()
    try:
        number = float(text)
    except ValueError:
        return text
    return str(int(number)) if number.is_integer() else text


def corrected_initialization(
    contexts: pd.DataFrame, proposals: pd.DataFrame, proposal_responses: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    proposal = proposals.copy()
    if "raw_condition" in proposal:
        proposal["condition"] = proposal.raw_condition.str.lower()
    else:
        required = set(proposal.proposal_id)
        observed = proposal_responses[proposal_responses.proposal_id.isin(required)].groupby("proposal_id").raw_condition.agg(lambda values: sorted(set(map(str.lower, values))))
        missing = sorted(required - set(observed.index))
        invalid = {key: value for key, value in observed.items() if value != ["semi"]}
        if missing or invalid:
            raise ValueError(f"proposal condition not verified: missing={missing}, invalid={invalid}")
        proposal["condition"] = proposal.proposal_id.map(lambda value: observed[value][0])
    proposal["block_index"] = proposal.block_index.map(_block)
    keys = ["stage", "block_index", "image_id", "condition"]
    if proposal.duplicated(keys).any():
        raise ValueError("duplicate complete initialization key")
    mapping = proposal.set_index(keys).initialization_source_kind
    corrected = contexts.copy()
    parts = corrected.context_key.str.split("|", regex=False)
    if not parts.map(len).eq(4).all():
        raise ValueError("context_key must have four parts")
    corrected["block_index"] = parts.str[1].map(_block)
    expected = corrected.apply(lambda row: "|".join((str(row.stage), row.block_index, str(row.image_id), str(row.condition))), axis=1)
    if not expected.eq(corrected.context_key).all():
        raise ValueError("context_key disagrees with stage/image/condition columns")
    corrected["initialization_source_kind_corrected"] = [
        mapping.get((row.stage, str(row.block_index), row.image_id, row.condition), "manual_or_not_recorded")
        for row in corrected.itertuples()
    ]
    changed = corrected[corrected.initialization_source_kind != corrected.initialization_source_kind_corrected].copy()
    changed = changed.rename(columns={"initialization_source_kind": "old_initialization_source_kind"})
    corrected["initialization_source_kind_original"] = corrected.initialization_source_kind
    corrected["initialization_source_kind"] = corrected.initialization_source_kind_corrected
    corrected = corrected.drop(columns=["initialization_source_kind_corrected", "block_index"])
    return corrected, changed[[
        "context_key", "stage", "block_index", "image_id", "condition", "raw_count",
        "old_initialization_source_kind", "initialization_source_kind_corrected",
    ]]


def rho_status(x: np.ndarray, y: np.ndarray) -> tuple[float, str]:
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 4:
        return np.nan, "invalid_fewer_than_4"
    if np.ptp(x[ok]) == 0:
        return np.nan, "invalid_constant_x"
    if np.ptp(y[ok]) == 0:
        return np.nan, "invalid_constant_y"
    value = float(spearmanr(x[ok], y[ok]).statistic)
    return (value, "evaluable") if np.isfinite(value) else (np.nan, "invalid_nonfinite_rho")


def replay_associations(contexts: pd.DataFrame, extended: pd.DataFrame, old: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(SEED)
    old_index = old.set_index(["scope", "stratum", "x", "y"])
    rows, draw_rows = [], []
    scopes = [
        ("extended73", extended),
        ("without_synthetic", extended[extended.initialization_source_kind != "trap_synthetic_disjoint_source"]),
        ("all_n3", contexts[contexts.floor_count >= 3]),
    ]
    for scope, frame in scopes:
        strata = [("all", frame)] + [(f"{stage}|{condition}", group) for (stage, condition), group in frame.groupby(["stage", "condition"])]
        for stratum, group in strata:
            for x, y in [("bi_floor", "d_floor"), ("bi_band", "d_band"), ("bi_linear", "d_linear"), ("bi_solid", "d_solid"), ("bi_floor", "cluster_count")]:
                if y not in group:
                    continue
                data = group.dropna(subset=[x, y])
                base_rho, base_status = rho_status(data[x].to_numpy(float), data[y].to_numpy(float))
                buildings = sorted(data.building_id.unique())
                draws, reasons = [], Counter()
                not_evaluable_reason = ""
                if base_status != "evaluable":
                    not_evaluable_reason = f"original_{base_status}"
                elif len(buildings) < 3:
                    not_evaluable_reason = "fewer_than_3_buildings"
                else:
                    values = data[[x, y]].to_numpy(float)
                    building = data.building_id.to_numpy()
                    groups = [np.flatnonzero(building == item) for item in buildings]
                    for draw_index in range(REQUESTED):
                        index = np.concatenate([groups[j] for j in rng.integers(0, len(buildings), len(buildings))])
                        value, status = rho_status(values[index, 0], values[index, 1])
                        reasons[status] += 1
                        draw_rows.append({"scope": scope, "stratum": stratum, "x": x, "y": y, "draw_index": draw_index, "status": status, "rho": value if status == "evaluable" else np.nan})
                        if status == "evaluable":
                            draws.append(value)
                old_row = old_index.loc[(scope, stratum, x, y)]
                low = float(np.quantile(draws, .025)) if draws else np.nan
                high = float(np.quantile(draws, .975)) if draws else np.nan
                old_low, old_high = float(old_row.ci_low) if pd.notna(old_row.ci_low) else np.nan, float(old_row.ci_high) if pd.notna(old_row.ci_high) else np.nan
                rows.append({
                    "scope": scope, "stratum": stratum, "x": x, "y": y,
                    "contexts": len(data), "buildings": len(buildings), "rho": base_rho,
                    "analysis_status": "evaluable" if draws else "not_evaluable",
                    "not_evaluable_reason": not_evaluable_reason,
                    "bootstrap_requested_n": REQUESTED if not not_evaluable_reason else 0,
                    "bootstrap_evaluable_n": len(draws),
                    "bootstrap_invalid_n": sum(reasons.values()) - len(draws),
                    "bootstrap_missing_fraction": (sum(reasons.values()) - len(draws)) / REQUESTED if not not_evaluable_reason else np.nan,
                    "invalid_fewer_than_4_n": reasons["invalid_fewer_than_4"],
                    "invalid_constant_x_n": reasons["invalid_constant_x"],
                    "invalid_constant_y_n": reasons["invalid_constant_y"],
                    "invalid_nonfinite_rho_n": reasons["invalid_nonfinite_rho"],
                    "ci_low_replayed": low, "ci_high_replayed": high,
                    "ci_low_original": old_low, "ci_high_original": old_high,
                    "old_ci_reproduced_within_1e_12": bool(
                        np.isclose(low, old_low, rtol=0, atol=1e-12, equal_nan=True)
                        and np.isclose(high, old_high, rtol=0, atol=1e-12, equal_nan=True)
                    ),
                    "interval_interpretation": "finite_draw_conditional_building_bootstrap_current_tasks_and_workers",
                })
    return pd.DataFrame(rows), pd.DataFrame(draw_rows)


def run(input_dir: Path = INPUT, reproduced_dir: Path = REPRODUCED, output_dir: Path = OUTPUT) -> dict[str, object]:
    contexts = pd.read_csv(reproduced_dir / "analysis" / "contexts.csv")
    proposals = pd.read_csv(input_dir / "facts" / "proposal_fact.csv.gz", dtype=str, keep_default_na=False)
    proposal_responses = pd.read_csv(input_dir / "facts" / "proposal_response.csv.gz", dtype=str, keep_default_na=False)
    corrected, changes = corrected_initialization(contexts, proposals, proposal_responses)
    partitions = pd.read_csv(input_dir / "clusters" / "partitions.csv.gz", dtype=str, keep_default_na=False)
    extended = corrected.merge(
        partitions[partitions.version == "extended73"][["context_key", "cluster_count", "partition_status", "structure_status"]],
        on="context_key", validate="one_to_one",
    )
    extended.cluster_count = extended.cluster_count.astype(int)
    old = pd.read_csv(reproduced_dir / "analysis" / "associations.csv")
    associations, draws = replay_associations(corrected, extended, old)
    output_dir.mkdir(parents=True, exist_ok=True)
    corrected.to_csv(output_dir / "contexts_initialization_corrected.csv", index=False)
    changes.to_csv(output_dir / "initialization_changes.csv", index=False)
    associations.to_csv(output_dir / "association_bootstrap_errata.csv", index=False)
    draws.to_csv(output_dir / "association_bootstrap_draws.csv.gz", index=False, compression="gzip")
    qa = {
        "schema_version": "uncertainty_handoff_errata_v1",
        "context_count": len(corrected),
        "initialization_changed_context_count": len(changes),
        "initialization_changed_response_count": int(changes.raw_count.sum()),
        "changed_stage_condition_counts": changes.groupby(["stage", "condition"]).size().rename("count").reset_index().to_dict("records"),
        "proposal_condition_verification": "proposal_fact_has_no_condition; all_proposal_ids_covered_by_proposal_response_and_uniquely_semi",
        "association_count": len(associations),
        "association_not_evaluable_count": int((associations.analysis_status == "not_evaluable").sum()),
        "bootstrap_requested_total": int(associations.bootstrap_requested_n.sum()),
        "bootstrap_evaluable_total": int(associations.bootstrap_evaluable_n.sum()),
        "bootstrap_invalid_total": int(associations.bootstrap_invalid_n.sum()),
        "bootstrap_draw_row_count": len(draws),
        "old_ci_reproduced_within_1e_12_count": int(associations.old_ci_reproduced_within_1e_12.sum()),
        "raw_sources_modified": False,
    }
    (output_dir / "ERRATA_QA.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return qa


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=INPUT)
    parser.add_argument("--reproduced-dir", type=Path, default=REPRODUCED)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(json.dumps(run(args.input_dir, args.reproduced_dir, args.output_dir), ensure_ascii=False))
