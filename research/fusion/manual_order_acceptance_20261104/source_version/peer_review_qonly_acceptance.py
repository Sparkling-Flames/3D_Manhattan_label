"""Independent peer review of the new Q-only acceptance outputs.

Weights are constructed top-down with exact rational shares of the frozen
hierarchy, independently of the acceptance producer's groupby transforms.
No producer module is imported, and no study output is overwritten.
"""
from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "source/research/data/releases/v2.1/q_only_exchange_20261031"


def read_jsonl(path):
    with gzip.open(path, "rt", encoding="utf-8-sig") as stream:
        return {r["team_key"]: r for r in map(json.loads, stream)}


def numeric(value):
    return float(value) if value is not None else float("nan")


def finite_pair(a, b):
    a, b = numeric(a), numeric(b)
    return a-b if math.isfinite(a) and math.isfinite(b) else float("nan")


def hierarchical_weights(records):
    """Split unit mass across images, pools, blocks, backgrounds, replicates."""
    result = {}
    levels = [("building", "image"), ("pool_id",), ("block_id",), ("background_id",)]

    def split(rows, level, mass):
        if level == len(levels):
            share = mass / len(rows)
            for row in rows:
                assert row["event_id"] not in result
                result[row["event_id"]] = share
            return
        children = defaultdict(list)
        for row in rows:
            children[tuple(row[k] for k in levels[level])].append(row)
        for child in children.values():
            split(child, level+1, mass / len(children))

    if records:
        split(records, 0, Fraction(1))
        assert sum(result.values(), Fraction(0)) == 1
    return result


def effect(records, field):
    if not records:
        return float("nan")
    weights = hierarchical_weights(records)
    return math.fsum(float(weights[r["event_id"]]) * r[field] for r in records)


def assert_near(actual, expected, label, tolerance=1e-10):
    if math.isnan(expected):
        assert pd.isna(actual), (label, actual, expected)
        return 0.0
    error = abs(float(actual)-expected)
    assert error <= tolerance, (label, actual, expected, error)
    return error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--restored-root", type=Path,
                        help="HOHONET repository root containing the previous five delivery batches")
    args = parser.parse_args()
    candidates = [HERE.parent / "HOHONET", *HERE.parents]
    repo = args.restored_root or next(
        (p for p in candidates if (p / "research/fusion/manual_order_impact_20261104").is_dir()), None)
    if repo is None:
        parser.error("Cannot locate HOHONET; pass --restored-root explicitly")
    base = repo / "research/fusion/manual_order_acceptance_20261104"
    out = base / "q_only"
    source_files = []
    for file in (base / "inputs/q_only").iterdir():
        own = SOURCE / file.name
        if own.is_file():
            assert file.read_bytes() == own.read_bytes(), file.name
            source_files.append(file.name)
    links = pd.read_csv(SOURCE / "DESIGN_LINKS.csv")
    original = read_jsonl(SOURCE / "ENDPOINTS.jsonl.gz")
    assisted = read_jsonl(repo / "research/fusion/manual_order_impact_20261104/endpoints/ENDPOINTS.jsonl.gz")
    own_inventory = pd.read_csv(HERE / "audit/FROZEN_POLICY_EVENT_INVENTORY.csv.gz")
    coverage = pd.read_csv(out / "ALL_1040_POLICY_OPPORTUNITIES.csv.gz")
    keys = ["event_id", "policy"]
    old_check, new_check = own_inventory.set_index(keys).sort_index(), coverage.set_index(keys).sort_index()
    assert old_check.index.equals(new_check.index) and len(new_check) == 1040
    assert (old_check.team_key == new_check.team_key).all()
    assert (old_check.requires_connection_review == new_check.needs_human_order).all()
    assert (old_check.returned_confirmed_order == new_check.confirmed_order_available).all()
    assert (old_check.score_status == new_check.automatic_status).all()
    assert (old_check.original_B8L2.isna() == new_check.automatic_Q.isna()).all()
    paired = old_check.original_B8L2.notna()
    assert np.max(np.abs(old_check.loc[paired, "original_B8L2"]-new_check.loc[paired, "automatic_Q"])) < 1e-10
    assert new_check[new_check.needs_human_order].assisted_Q.notna().all()
    assert new_check.needs_human_order.sum() == 29
    assert new_check[new_check.needs_human_order].team_key.nunique() == 21
    assert new_check.remaining_failure.sum() == 3
    assert new_check[new_check.remaining_failure].original_below_four.all()

    # Every final score in the full opportunity table must come from its exact
    # original endpoint or its approved auxiliary counterpart.
    for row in coverage.itertuples():
        record = assisted.get(row.team_key, original[row.team_key])
        assert_near(row.assisted_Q, numeric(record.get("B8L2")), (row.event_id, row.policy, "final_Q"))
        assert row.assisted_status == record["score_status"]
    focus = pd.read_csv(out / "20_7_DIFFERENT_SELECTION_ALL_FIVE_ARMS.csv")
    own_focus = pd.read_csv(HERE / "audit/20_7_DIFFERENT_SELECTION_ALL_FIVE_ARMS.csv")
    assert len(focus) == 35
    assert set(map(tuple, focus[keys].to_numpy())) == set(map(tuple, own_focus[keys].to_numpy()))
    assert not focus.remaining_failure.any()

    decomposition = pd.read_csv(out / "SUPPORT_AND_WEIGHT_DECOMPOSITION.csv")
    contributions = pd.read_csv(out / "EVENT_WEIGHT_CONTRIBUTIONS.csv.gz")
    expected_contribution_rows = 0
    max_error = 0.0
    summaries = []
    for d in decomposition.itertuples():
        records = []
        for eid, frame in links[links.n.eq(d.n)].groupby("event_id", sort=False):
            by = frame.set_index("policy")
            sr, cr = by.loc["STRUCTURE"], by.loc[d.comparator]
            same = set(sr.incoming_members.split("|")) == set(cr.incoming_members.split("|"))
            if d.subset == "different_selection" and same:
                continue
            a, b = original[sr.team_key], original[cr.team_key]
            sa, sb = assisted.get(sr.team_key, a), assisted.get(cr.team_key, b)
            old = finite_pair(a.get(d.metric), b.get(d.metric))
            new = finite_pair(sa.get(d.metric), sb.get(d.metric))
            records.append(dict(event_id=eid, building=sr.building, image=sr.image,
                                pool_id=sr.pool_id, block_id=sr.block_id,
                                background_id=sr.background_id, old=old, new=new))
        old = [r for r in records if math.isfinite(r["old"])]
        new = [r for r in records if math.isfinite(r["new"])]
        old_ids, new_ids = {r["event_id"] for r in old}, {r["event_id"] for r in new}
        assert old_ids <= new_ids
        assert all(r["old"] == r["new"] for r in old)
        old_images, new_images = {r["image"] for r in old}, {r["image"] for r in new}
        additions = [r for r in new if r["event_id"] not in old_ids]
        original_images_expanded = [r for r in new if r["image"] in old_images]
        ow, nw = hierarchical_weights(old), hierarchical_weights(new)
        e0, e1 = effect(old, "old"), effect(new, "new")
        e_old_images = effect(original_images_expanded, "new")
        new_contrib = math.fsum(float(nw[r["event_id"]])*r["new"] for r in additions)
        old_reweight = math.fsum(float(nw[r["event_id"]]-ow[r["event_id"]])*r["old"] for r in old)
        expected = dict(old_events=len(old), added_events=len(additions), expanded_events=len(new),
                        old_images=len(old_images), added_images=len(new_images-old_images),
                        expanded_images=len(new_images), old_effect=e0,
                        assisted_on_original_events=effect(old, "new"),
                        newly_evaluable_only_effect=effect(additions, "new"), expanded_effect=e1,
                        old_images_expanded_effect=e_old_images,
                        within_original_images_shift=e_old_images-e0,
                        adding_new_images_shift=e1-e_old_images,
                        new_event_weighted_contribution=new_contrib,
                        old_event_reweight_contribution=old_reweight)
        for field, expected_value in expected.items():
            max_error = max(max_error, assert_near(getattr(d, field), expected_value,
                            (d.subset, d.n, d.comparator, d.metric, field)))
        assert abs((e1-e0)-(new_contrib+old_reweight)) < 1e-10
        actual = contributions[(contributions.subset == d.subset) & (contributions.n == d.n) &
                               (contributions.comparator == d.comparator) & (contributions.metric == d.metric)].set_index("event_id")
        changed = [r for r in new if r["event_id"] not in old_ids or
                   abs(float(nw[r["event_id"]]-ow[r["event_id"]])) > 1e-14]
        assert set(actual.index) == {r["event_id"] for r in changed}
        expected_contribution_rows += len(changed)
        for r in changed:
            eid = r["event_id"]
            c = actual.loc[eid]
            is_new = eid not in old_ids
            assert bool(c.newly_evaluable) == is_new
            assert bool(c.new_image) == (r["image"] not in old_images)
            expected_row = dict(old_weight=float(ow.get(eid, Fraction(0))), new_weight=float(nw[eid]),
                                old_value=r["old"], new_value=r["new"],
                                new_event_contribution=float(nw[eid])*r["new"] if is_new else 0.0,
                                old_event_reweight_contribution=0.0 if is_new else float(nw[eid]-ow[eid])*r["old"])
            for field, expected_value in expected_row.items():
                max_error = max(max_error, assert_near(c[field], expected_value, (eid, field)))
            if is_new:
                assert pd.isna(c.old_value), "Missing old Q must not become zero"
        if d.metric == "B8L2":
            summaries.append({"subset": d.subset, "n": d.n, "comparator": d.comparator, **expected})
    assert expected_contribution_rows == len(contributions) == 5412
    pd.DataFrame(summaries).to_csv(HERE / "audit/PEER_RECALCULATED_Q_DECOMPOSITION.csv", index=False)

    # Inspect the diagnostic that removes the one newly supported image.
    influence = pd.read_csv(out / "IMAGE_INFLUENCE_DIAGNOSTIC.csv")
    summary = pd.read_csv(out / "INDEPENDENT_SUMMARY.csv")
    for subset in ["all_registered", "different_selection"]:
        lo = influence[(influence.n == 20) & (influence.subset == subset) &
                       (influence.omitted_image == "S9hNv5qa7GM-09")].iloc[0]
        old = summary[(summary.version == "automatic") & (summary.n == 20) &
                      (summary.subset == subset) & (summary.comparator == "Q_RAW") &
                      (summary.metric == "B8L2")].iloc[0]
        for field in ["effect", "ci_low", "ci_high"]:
            max_error = max(max_error, assert_near(lo[field], old[field], (subset, "influence", field)))

    receipt = dict(
        verdict="PASS", input_snapshot_files_matched=source_files,
        opportunity_rows_independently_matched=1040,
        no_connection_links=29, no_connection_unique_endpoints=21,
        uncovered_required_order_links=0, remaining_failure_links=3,
        focused_20_7_event_arms_matched=35, focused_remaining_failures=0,
        decomposition_conditions_recalculated=len(decomposition),
        event_contribution_rows_verified=expected_contribution_rows,
        common_support_value_changes=0, missing_old_Q_filled_with_zero=0,
        largest_numeric_disagreement=max_error,
        independent_weight_method="top-down exact Fraction mass allocation across image, pool, block, background, replicate; no import of production audit code",
        sign_and_support_interpretation="Published decomposition is a change of the supported mean, not a score improvement from zero for missing original Q.",
        material_rerun_gap_found=False,
        scope="Frozen 208-event design and its accepted exact-team manual-order scores only")
    (HERE / "audit/PEER_REVIEW_QONLY_CHECKS.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
