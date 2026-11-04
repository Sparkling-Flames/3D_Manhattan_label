"""Narrow read-only order-reuse review of six already-registered AC opponents.

Reads immutable saved prepared nodes. Does not fuse, score, select teams, create
an order, or alter the completed ac_peer audit. --fetch only retrieves these
six prepared entries from frozen ZIP byte ranges; normal reproduction is local.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import struct
import urllib.request
import zlib

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASE = HERE.parent
PEER = BASE / "ac_peer"
RETURN = ROOT / "research/fusion/missing_ring_review_20261104/user_order_return"
COMMIT = "ac395e703d1fef573d1ef3e105df0286d62a0468"
INPUT = HERE / "inputs/SIX_DIRECT_OPPONENT_REFERENCES.csv.gz"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def csv(frame, name):
    path = HERE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = pd.DataFrame(frame).to_csv(index=False).encode("utf-8-sig")
    path.write_bytes(gzip.compress(raw, mtime=0) if name.endswith(".gz") else raw)


def http_range(url, start, end):
    request = urllib.request.Request(url+f"?read_range={start}-{end}", headers={"Range": f"bytes={start}-{end}"})
    with urllib.request.urlopen(request, timeout=55) as response:
        assert response.status == 206
        assert response.headers.get("Content-Range", "").startswith(f"bytes {start}-{end}/")
        data = response.read()
    assert len(data) == end-start+1
    return data


def fetch_frozen_prepared(teams):
    wanted = {hashlib.sha256(key.encode()).hexdigest()[:24]: key for key in teams}
    directory = json.loads((PEER / "source_cache/PREPARED_SHARD_DIRECTORY.json").read_text())

    def archive(entry):
        if not entry["name"].endswith(".zip"):
            return []
        size, url = entry["bytes"], entry["download_url"]
        assert COMMIT in url
        tail = http_range(url, size-22, size-1)
        assert tail[:4] == b"PK\x05\x06"
        _, _, _, _, count, cdsize, offset, comment = struct.unpack("<4s4H2LH", tail)
        assert comment == 0
        directory_bytes = http_range(url, offset, offset+cdsize-1)
        position, found, seen = 0, [], 0
        while position < len(directory_bytes):
            record = struct.unpack_from("<4s6H3L5H2L", directory_bytes, position)
            assert record[0] == b"PK\x01\x02"
            namelen, extralen, commentlen = record[10:13]
            name = directory_bytes[position+46:position+46+namelen].decode()
            position += 46+namelen+extralen+commentlen
            seen += 1
            review_id = Path(name).name.removesuffix(".json.gz")
            if review_id not in wanted:
                continue
            local_offset, method, crc, compressed, uncompressed = record[16], record[4], record[7], record[8], record[9]
            data = http_range(url, local_offset, min(size-1, local_offset+30+namelen+1024+compressed))
            header = struct.unpack_from("<4s5H3L2H", data, 0)
            assert header[0] == b"PK\x03\x04"
            start = 30+header[9]+header[10]
            payload = data[start:start+compressed]
            assert len(payload) == compressed and method in [0, 8]
            content = payload if method == 0 else zlib.decompress(payload, -15)
            assert len(content) == uncompressed and zlib.crc32(content) == crc
            case = json.loads(gzip.decompress(content))
            assert case["review_id"] == review_id and case["team_key"] == wanted[review_id]
            path = HERE / "inputs/prepared" / (review_id+".json.gz")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            found.append(dict(review_id=review_id, team_key=case["team_key"], archive=entry["path"],
                archive_git_blob_sha=entry["git_blob_sha"], archive_url=url, entry=name, entry_crc32=crc,
                entry_sha256=digest(content), entry_bytes=len(content), nodes=len(case["nodes"]),
                retrieval="frozen GitHub ZIP byte ranges; central/local header and entry CRC checked; whole archive SHA not recalculated"))
        assert seen == count
        print(entry["name"], "matched_entries", len(found), flush=True)
        return found

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = [row for rows in pool.map(archive, directory) for row in rows]
    assert len(results) == len(teams) == 6 and {r["team_key"] for r in results} == set(teams)
    write_json(HERE / "PREPARED_SOURCE_MANIFEST.json", results)


def check():
    refs = pd.read_csv(INPUT)
    input_receipt = json.loads((HERE / "INPUT_EXTRACTION.json").read_text())
    assert digest(INPUT.read_bytes()) == input_receipt["selected_reference_snapshot_sha256"]
    event_path = HERE / input_receipt["affected_event_source"]["snapshot_file"]
    assert digest(event_path.read_bytes()) == input_receipt["affected_event_source"]["snapshot_sha256"]
    event_states = pd.read_csv(event_path).set_index("event_id")
    assert event_states.index.is_unique and set(event_states.index) == set(refs.event_id)
    for ref in refs.itertuples():
        event = event_states.loc[ref.event_id]
        opposite = "C" if ref.failed_arm == "A" else "A"
        assert event[ref.failed_arm+"_team_key"] == ref.failed_team_key
        assert event[opposite+"_team_key"] == ref.opponent_team_key
        assert event[ref.failed_arm+"_nodes"] == ref.selected_nodes
        assert event[ref.failed_arm+"_output_state"] == "no_connection"
    teams = refs.drop_duplicates("failed_team_key").sort_values("failed_team_key")
    assert len(teams) == 6 and refs.opponent_in_confirmed57.all() and not refs.failed_endpoint_in_confirmed57.any()
    assert refs.score_status.eq("no_connection").all() and refs.selected_nodes.ge(4).all()
    manifest = {r["team_key"]: r for r in json.loads((HERE / "PREPARED_SOURCE_MANIFEST.json").read_text())}
    orders = pd.read_csv(RETURN / "VALIDATED_ENDPOINT_ORDERS.csv.gz")
    assert len(orders) == 57
    assert set(refs.opponent_team_key) <= set(orders.team_key)
    assert not set(refs.failed_team_key) & set(orders.team_key)
    known_cases = {}
    for path in (ROOT / "research/fusion/missing_ring_review_20261104/prepared").glob("*.json.gz"):
        case = json.loads(gzip.decompress(path.read_bytes()))
        known_cases[case["team_key"]] = case
    legacy_path = PEER / "source_cache/order_import.json"
    legacy_bytes = legacy_path.read_bytes()
    legacy_blob = hashlib.sha1(b"blob "+str(len(legacy_bytes)).encode()+b"\0"+legacy_bytes).hexdigest()
    assert legacy_blob == "40dc17ed0f8337ab3154e3b9cc7fa06c33e13ade"
    legacy = json.loads(legacy_bytes)["accepted"]
    assert len(legacy) == 33
    output, comparisons, full_cases = [], [], []
    for row in teams.itertuples():
        source = manifest[row.failed_team_key]
        data = (HERE / "inputs/prepared" / (source["review_id"]+".json.gz")).read_bytes()
        assert digest(data) == source["entry_sha256"]
        case = json.loads(gzip.decompress(data))
        nodes = case["nodes"]
        assert case["team_key"] == row.failed_team_key and case["image"] == row.image
        assert len(nodes) == row.selected_nodes
        assert np.isfinite(np.array([n["points"] for n in nodes], dtype=float)).all()
        assert len({n["feature_id"] for n in nodes}) == len(nodes)
        assert case["original_reason"] == "no_source_ring_covering_all_selected_nodes"
        signature = sorted(n["points"] for n in nodes)
        by_id = {n["feature_id"]: n["points"] for n in nodes}
        same57 = orders[orders.image.eq(case["image"])]
        old = [o for o in legacy if o["image"] == case["image"]]
        counts = dict(exact_coordinates_confirmed57=0, exact_context_coordinates_confirmed57=0,
                      exact_id_coordinates_confirmed57=0, exact_coordinates_legacy33=0,
                      exact_id_coordinates_legacy33=0)
        candidates = []
        for candidate in same57.to_dict("records"):
            bound = json.loads(candidate["order_binding"])
            known = known_cases[candidate["team_key"]]
            same_context = all(case.get(k) == known.get(k) for k in ["image_id", "reference_id", "reference_version"])
            candidates.append(("confirmed57", candidate["team_key"], bound, same_context))
        for index, candidate in enumerate(old):
            candidates.append(("legacy33", str(candidate.get("id", candidate.get("team_key", f"same_image_entry_{index}"))), candidate["order_binding"], None))
        for origin, key, binding, same_context in candidates:
            candidate_signature = sorted(n["points"] for n in binding)
            equal_count = len(binding) == len(nodes)
            equal_coordinates = candidate_signature == signature
            equal_ids = {n["feature_id"]: n["points"] for n in binding} == by_id
            counts["exact_coordinates_"+origin] += int(equal_coordinates)
            counts["exact_id_coordinates_"+origin] += int(equal_ids)
            if origin == "confirmed57": counts["exact_context_coordinates_confirmed57"] += int(equal_coordinates and same_context)
            distance = float(np.max(np.abs(np.array(candidate_signature)-np.array(signature)))) if equal_count else None
            comparisons.append(dict(failed_team_key=row.failed_team_key, candidate_source=origin, candidate_key=key,
                candidate_nodes=len(binding), residual_nodes=len(nodes), same_node_count=equal_count,
                same_reference_context=same_context, exact_points_multiset_equal=equal_coordinates,
                exact_feature_id_points_equal=equal_ids,
                sorted_pair_coordinate_max_abs_difference_px=distance,
                distance_note="diagnostic only; no near-coordinate matching or order transfer"))
        own = refs[refs.failed_team_key.eq(row.failed_team_key)]
        output.append(dict(team_key=row.failed_team_key, review_id=source["review_id"], image=case["image"], nodes=len(nodes),
            reference_id=case.get("reference_id"), reference_version=case.get("reference_version"),
            fixed_coordinate_pairs_available=True, exact_node_votes_and_members_in_frozen_prepared=True,
            same_image_confirmed57=len(same57), same_image_legacy33=len(old), **counts,
            affected_reversal_ids="|".join(sorted(set(own.reversal_id))),
            registered_event_ids="|".join(sorted(set(own.event_id))),
            opponent_teams_in_confirmed57="|".join(sorted(set(own.opponent_team_key))),
            conclusion="no reusable confirmed57 or legacy33 order" if not counts["exact_coordinates_confirmed57"] and not counts["exact_coordinates_legacy33"] else "exact geometry candidate found; requires explicit context and binding resolution",
            new_order_generated=False, new_score_computed=False))
        full_cases.append(case)
    result = pd.DataFrame(output)
    csv(result, "SIX_ENDPOINT_REUSE_RESULTS.csv")
    csv(comparisons, "SAME_IMAGE_BINDING_COMPARISONS.csv")
    write_json(HERE / "SIX_FROZEN_CASES.json", full_cases)
    matches = int(result.exact_coordinates_confirmed57.sum()+result.exact_coordinates_legacy33.sum())
    summary = dict(status="PASS_NO_REUSABLE_ORDER_IN_SPECIFIC_SIX" if matches == 0 else "EXACT_GEOMETRY_MATCH_REQUIRES_RESOLUTION",
        frozen_commit=COMMIT, reviewed_teams=6, reviewed_condition_event_references=len(refs),
        reviewed_unique_events=refs.event_id.nunique(), reviewed_reversal_rows=refs.reversal_id.nunique(),
        confirmed57_coordinate_matches=int(result.exact_coordinates_confirmed57.sum()),
        legacy33_coordinate_matches=int(result.exact_coordinates_legacy33.sum()),
        same_image_binding_comparisons=len(comparisons),
        affected_event_source_identity_parity=True,
        all_registered_ac_opportunities_covered=False,
        scope="Only the six newly identified outside57 no_connection endpoints with an already-confirmed57 opponent; the two RAW3 wc2 endpoints were checked earlier in ac_peer",
        does_not_establish=["absence of reusable orders among all other AC residual endpoints", "existence or validity of a new order", "actual missing Q", "equal treatment opportunity in AC"],
        existing_unexported_local_browser_answers_assumed=False,
        new_orders_generated=0, new_fusions=0, new_scores=0, completed_ac_peer_modified=False)
    write_json(HERE / "CHECKS.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true", help="Fetch only the six frozen prepared entries")
    args = parser.parse_args()
    refs = pd.read_csv(INPUT)
    if args.fetch: fetch_frozen_prepared(sorted(set(refs.failed_team_key)))
    summary = check()
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
