"""Read-only independent audit of the frozen Q-only design and human-order coverage.

Input snapshots were read through GitHub at the observed main commit. This audit
does not score endpoints or modify any original or assisted study output.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import pandas as pd


FROZEN = "ac395e703d1fef573d1ef3e105df0286d62a0468"
REPO = "https://github.com/Sparkling-Flames/3D_Manhattan_label"
QREL = "research/data/releases/v2.1/q_only_exchange_20261031"
RREL = "research/fusion/missing_ring_review_20261104/user_order_return"
POLICIES = ["A", "B", "STRUCTURE", "Q_RAW", "Q_PEER"]


def members(value: str) -> set[str]:
    return set(str(value).split("|"))


def sha_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restored-root", type=Path,
                        help="HOHONET repository root containing the original review inputs")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "audit")
    args = parser.parse_args()
    root = Path(__file__).parent
    if args.restored_root is None:
        candidates = [root.parent / "HOHONET", *root.parents]
        args.restored_root = next(
            (p for p in candidates if (p / RREL / "VALIDATED_ENDPOINT_ORDERS.csv.gz").is_file()), None)
        if args.restored_root is None:
            parser.error("Cannot locate HOHONET; pass --restored-root explicitly")
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    source = root / "source"

    # Preserve the exact UTF-8/CRLF/BOM bytes previously fetched from GitHub.
    for old, rel in [("PRO_PROMPT_ZH.md", f"{RREL}/PRO_PROMPT_ZH.md"),
                     ("QONLY_README.md", f"{QREL}/README.md"),
                     ("QONLY_DESIGN.json", f"{QREL}/DESIGN.json")]:
        target = source / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root / "current" / old).read_bytes())

    branch = json.loads((root / "main_branch.json").read_text())
    assert branch["commit"]["sha"] == FROZEN
    directories = [json.loads((root / n).read_text()) for n in
                   ["return_directory.json", "qonly_directory.json"]]
    expected = {r["path"]: r["sha"] for records in directories for r in records if r["type"] == "file"}
    expected["tools/thesis_main/analysis/q_only_exchange_v21_20261031.py"] = "6f7347ea7df98cbcdc872f405f8555a51e951ac3"
    manifest = []
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.suffix == ".b64":
            continue
        rel = path.relative_to(source).as_posix()
        data = path.read_bytes()
        actual = sha_blob(data)
        assert actual == expected[rel], (rel, actual, expected[rel])
        manifest.append(dict(input_kind="github_snapshot", source_path=rel,
                             bytes=len(data), git_blob_sha=actual,
                             sha256=hashlib.sha256(data).hexdigest(),
                             observed_commit=FROZEN, source_url=f"{REPO}/blob/{FROZEN}/{rel}"))

    # Validate the recovered review input against the GitHub tree, rather than
    # accepting a prior delivery receipt as the provenance check.
    for metadata in directories[0]:
        if metadata["type"] != "file":
            continue
        path = args.restored_root / metadata["path"]
        data = path.read_bytes()
        actual = sha_blob(data)
        assert actual == metadata["sha"], (metadata["path"], actual, metadata["sha"])
        manifest.append(dict(input_kind="restored_review_input", source_path=metadata["path"],
                             bytes=len(data), git_blob_sha=actual,
                             sha256=hashlib.sha256(data).hexdigest(),
                             observed_commit=FROZEN,
                             source_url=f"{REPO}/blob/{FROZEN}/{metadata['path']}"))
    pd.DataFrame(manifest).to_csv(output / "SOURCE_VERSION_MANIFEST.csv", index=False)

    q = source / QREL
    links = pd.read_csv(q / "DESIGN_LINKS.csv")
    status = pd.read_csv(q / "OUTPUT_STATUS.csv")
    requests = pd.read_csv(q / "TEAM_REQUESTS.csv")
    overlap = pd.read_csv(q / "SELECTION_OVERLAP.csv")
    design = json.loads((q / "DESIGN.json").read_text())
    endpoints = {r["team_key"]: r for r in
                 (json.loads(line) for line in gzip.open(q / "ENDPOINTS.jsonl.gz", "rt"))}
    validated = pd.read_csv(args.restored_root / RREL / "VALIDATED_ENDPOINT_ORDERS.csv.gz")
    assert len(links) == len(status) == 1040
    assert links.event_id.nunique() == 208
    assert links.groupby("n").event_id.nunique().to_dict() == {14: 147, 20: 61}
    assert len(requests) == requests.team_key.nunique() == len(endpoints) == 670
    assert set(links.team_key) == set(requests.team_key) == set(endpoints)
    assert design["eligible_events"] == 208 and design["unique_requests"] == 670
    assert design["scoreable_filter_before_selection"] is False
    assert design["selection_uses_target_Q"] is False
    req = requests.set_index("team_key")
    assert all(set(g.policy) == set(POLICIES) and len(g) == 5
               for _, g in links.groupby("event_id"))

    fixed_checks = 0
    for r in links.itertuples():
        D, X, Y, Z = (members(getattr(r, k)) for k in ["D", "X", "Y", "Z"])
        parts = [D, X, Y, Z]
        assert not any(a & b for i, a in enumerate(parts) for b in parts[i+1:])
        assert len(D) == r.n-r.m and len(X) == len(Y) == len(Z) == r.m == 7
        requested = req.loc[r.team_key]
        incoming = members(r.incoming_members)
        team = members(requested.members)
        assert requested.pool_id == r.pool_id and int(requested.n) == r.n
        assert len(team) == r.n and team == D | incoming and len(incoming) == 7
        if r.policy == "A":
            assert incoming == X
        elif r.policy == "B":
            assert incoming == Y
        elif r.policy == "STRUCTURE":
            assert incoming == Z
        else:
            assert not incoming & (D | X | Y)
        endpoint = endpoints[r.team_key]
        assert endpoint["pool_id"] == r.pool_id
        assert endpoint["reference_id"] == requested.reference_id
        assert endpoint["reference_version"] == requested.reference_version
        assert set(endpoint["member_workers"]) == team
        assert endpoint["k"] == r.n
        fixed_checks += 1

    joined = links.merge(status, on=["event_id", "n", "image", "building", "policy"],
                         validate="one_to_one").merge(
        requests.drop(columns=["n", "pool_id"]), on="team_key", validate="many_to_one")
    for r in joined.itertuples():
        endpoint = endpoints[r.team_key]
        assert bool(r.scored) == (endpoint.get("B8L2") is not None)
        assert bool(r.complete) == bool(endpoint.get("complete_evaluable"))
        assert bool(r.below_four) == bool(endpoint.get("below_four"))
        assert bool(r.connection_available) == bool(endpoint.get("connection_available"))
        assert r.score_status == endpoint.get("score_status")
    joined["original_B8L2"] = joined.team_key.map(lambda k: endpoints[k].get("B8L2"))
    joined["original_selected_nodes"] = joined.team_key.map(lambda k: endpoints[k].get("nodes"))
    joined = joined.merge(validated[["team_key", "group_id", "review_id", "application_status"]],
                          on="team_key", how="left", validate="many_to_one")
    joined["returned_confirmed_order"] = joined.group_id.notna()
    joined["requires_connection_review"] = joined.score_status.eq("no_connection")
    joined.to_csv(output / "FROZEN_POLICY_EVENT_INVENTORY.csv.gz", index=False)

    failures = joined[~joined.scored].copy()
    failures["failure_class"] = failures.score_status.map({
        "no_connection": "connection_order_review_required",
        "below_four": "insufficient_fixed_nodes_not_repairable_by_order"})
    assert failures.failure_class.notna().all()
    missing = failures[failures.requires_connection_review]
    insufficient = failures[failures.below_four]
    assert len(failures) == 32 and len(missing) == 29 and len(insufficient) == 3
    assert missing.team_key.nunique() == 21 and missing.event_id.nunique() == 14
    assert missing.image.nunique() == 8
    assert missing.returned_confirmed_order.all()
    assert (missing.original_selected_nodes >= 4).all()
    assert (insufficient.original_selected_nodes == 3).all()
    assert not insufficient.returned_confirmed_order.any()
    failures.to_csv(output / "ORIGINAL_POLICY_FAILURE_REQUIREMENTS.csv", index=False)
    missing.drop_duplicates("team_key").to_csv(output / "REQUIRED_CONNECTION_ENDPOINTS_21.csv", index=False)
    insufficient.to_csv(output / "INSUFFICIENT_NODES_3_POLICY_EVENTS.csv", index=False)

    arm = joined.groupby(["n", "m", "policy"], dropna=False).agg(
        registered_events=("event_id", "size"), unique_teams=("team_key", "nunique"),
        images=("image", "nunique"), buildings=("building", "nunique"),
        original_scored=("scored", "sum"), original_below_four=("below_four", "sum"),
        requires_connection_review=("requires_connection_review", "sum"),
        confirmed_order_available=("returned_confirmed_order", "sum")).reset_index()
    arm["uncovered_connection_reviews"] = arm.requires_connection_review - arm.confirmed_order_available
    assert (arm.uncovered_connection_reviews == 0).all()
    arm.to_csv(output / "ORIGINAL_POLICY_SCOPE_AND_ORDER_COVERAGE.csv", index=False)

    # Reconstruct selection overlap from the stored identities, independently
    # of the study's SELECTION_OVERLAP table.
    selection = []
    for eid, event in links.groupby("event_id", sort=False):
        by = event.set_index("policy")
        s = members(by.loc["STRUCTURE", "incoming_members"])
        for policy in ["Q_RAW", "Q_PEER"]:
            c = members(by.loc[policy, "incoming_members"])
            row = overlap[(overlap.event_id == eid) & (overlap.policy == policy)]
            assert len(row) == 1
            row = row.iloc[0]
            assert int(row.shared_incoming) == len(s & c) and bool(row.same_block) == (s == c)
            selection.append(dict(event_id=eid, n=int(by.iloc[0].n), image=by.iloc[0].image,
                                  building=by.iloc[0].building, policy=policy,
                                  same_block=(s == c), shared_incoming=len(s & c),
                                  structure_only_members="|".join(sorted(s-c)),
                                  comparator_only_members="|".join(sorted(c-s))))
    selection = pd.DataFrame(selection)
    selection.to_csv(output / "SELECTION_IDENTITY_RECALCULATION.csv", index=False)
    focus_ids = set(selection.loc[selection.n.eq(20) & ~selection.same_block, "event_id"])
    assert len(focus_ids) == 7
    focus = joined[joined.n.eq(20) & joined.event_id.isin(focus_ids)].copy()
    assert len(focus) == 35 and focus.image.nunique() == 7
    for _, event in focus.groupby("event_id"):
        by = event.set_index("policy")
        assert by.loc["Q_RAW", "team_key"] == by.loc["Q_PEER", "team_key"]
    focused_failures = focus[~focus.scored]
    assert len(focused_failures) == 1
    assert focused_failures.iloc[0].event_id == "154d5aebcb8aaffc968f1e09"
    assert focused_failures.iloc[0].policy == "STRUCTURE"
    focus.to_csv(output / "20_7_DIFFERENT_SELECTION_ALL_FIVE_ARMS.csv", index=False)
    selection[selection.n.eq(20) & ~selection.same_block].to_csv(
        output / "20_7_DIFFERENT_SELECTION_IDENTITIES.csv", index=False)

    receipt = dict(
        status="PASS", scope="Frozen 208 registered Q-only policy events only; no claim of whole-library fairness",
        observed_default_branch="main", observed_commit=branch["commit"]["sha"],
        prior_frozen_commit=FROZEN, version_drift=False,
        commit_timestamp=branch["commit"]["commit"]["committer"]["date"],
        source_files_matched=len(manifest), policy_event_rows=1040, events=208,
        original_unique_requests=670, per_event_fixed_identity_checks=fixed_checks,
        original_failed_policy_events=32, no_connection_policy_events=29,
        no_connection_unique_endpoints=21, no_connection_events=14, no_connection_images=8,
        returned_order_coverage_policy_events=29, returned_order_coverage_unique_endpoints=21,
        missing_required_orders=[], below_four_policy_events=3,
        different_selection_20_7_events=7, different_selection_20_7_images=7,
        different_selection_20_7_missing_original_Q_policy_events=1,
        new_human_order_requests_required_within_registered_scope=0,
        assisted_score_validation="performed separately by main acceptance audit",
        interpretation="All frozen no-connection endpoints in each of the five arms had returned manual orders; unequal raw intervention counts follow unequal original failure counts. This is targeted coverage, not random treatment assignment or proof of global automatic-method performance.")
    (output / "SOURCE_AND_DESIGN_CHECKS.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
