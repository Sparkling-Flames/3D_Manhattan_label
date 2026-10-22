"""LOBO category-priority permutations for the v2 population-prefix study.

Only historical labels and historical fold centroids are consumed.  This module
never reads target-image quality, annotation geometry, or target recorded time.
Consensus is deliberately delegated to the caller's frozen engine/cache.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


ROLE_SPECS = {
    "structure_moreturn_first": {
        "method": "V3_BEHAVIOR", "tier": "fine",
        "role_zh": "历史非冗余转折较多类优先",
        "sort": ["turn_history_mean", "people", "class_id"],
        "ascending": [False, False, True],
    },
    "structure_dominant_first": {
        "method": "V3_BEHAVIOR", "tier": "fine",
        "role_zh": "历史人数最多的结构类优先",
        "sort": ["people", "class_id"], "ascending": [False, True],
    },
    "joint_highq_first": {
        "method": "V3_JOINT_QT", "tier": "coarse",
        "role_zh": "联合分类中历史Q中心最高类优先",
        "sort": ["q_history_mean", "people", "class_id"],
        "ascending": [False, False, True],
    },
    "joint_fast_first": {
        "method": "V3_JOINT_QT", "tier": "coarse",
        "role_zh": "联合分类中历史相对时间最低类优先",
        "sort": ["t_history_mean", "people", "class_id"],
        "ascending": [True, False, True],
    },
}


def stable_seed(*parts: object) -> int:
    payload = json.dumps(parts, ensure_ascii=True, separators=(",", ":"))
    return int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8], "little")


class RoleBook:
    def __init__(self, labels_path: str | Path, definitions_path: str | Path):
        self.labels_path = Path(labels_path)
        self.definitions_path = Path(definitions_path)
        self.labels = pd.read_csv(self.labels_path)
        self.definitions = pd.read_csv(self.definitions_path)
        if (self.labels.heldout_building == "ALL").any():
            raise ValueError("Use building-excluded labels, not descriptive ALL labels")
        duplicate_key = ["condition", "heldout_building", "method", "worker_id"]
        if self.labels.duplicated(duplicate_key).any():
            raise ValueError("LOBO worker/method/fold keys are not unique")
        self.roles = self._build_roles()
        self._roles = {
            (r["condition"], r["heldout_building"], r["policy"]): r
            for r in self.roles.to_dict("records")
        }
        self._labels = {
            key: g.set_index("worker_id").to_dict("index")
            for key, g in self.labels.groupby(["condition", "heldout_building", "method"])
        }

    def _build_roles(self) -> pd.DataFrame:
        rows = []
        for policy, spec in ROLE_SPECS.items():
            d = self.definitions[
                (self.definitions.method == spec["method"])
                & (self.definitions.tier == spec["tier"])
            ]
            for (condition, building), group in d.groupby(["condition", "heldout_building"]):
                group = group.dropna(subset=[spec["sort"][0]])
                if group.empty:
                    continue
                role = group.sort_values(spec["sort"], ascending=spec["ascending"]).iloc[0].to_dict()
                role.update({
                    "policy": policy,
                    "role_zh": spec["role_zh"],
                    "role_selection": json.dumps(dict(zip(spec["sort"], spec["ascending"]))),
                    "evaluation_history": "target_building_excluded",
                    "target_data_used_for_role_selection": False,
                })
                rows.append(role)
        return pd.DataFrame(rows)

    def pool_role(self, workers: Iterable[str], condition: str, building: str, policy: str) -> dict:
        workers = list(workers)
        if len(workers) != len(set(workers)):
            raise ValueError("Pool must contain unique actual workers")
        spec = ROLE_SPECS[policy]
        role = self._roles.get((condition, building, policy))
        base = {"condition": condition, "heldout_building": building, "policy": policy,
                "pool_size": len(workers), "method": spec["method"], "tier": spec["tier"]}
        if role is None:
            return dict(base, eligible=False, reason="no_LOBO_role_for_building", target_members=[],
                        known_members=[], unknown_members=sorted(workers), target_capacity=0)
        label_rows = self._labels[(condition, building, spec["method"])]
        label_column = "fine_label" if spec["tier"] == "fine" else "coarse_label"
        known = [w for w in workers if w in label_rows and label_rows[w]["known"] in (True, "True", 1)]
        target = [w for w in known if label_rows[w][label_column] == role["class_id"]]
        unknown = sorted(set(workers) - set(known))
        counts = pd.Series([label_rows[w][label_column] for w in known]).value_counts().sort_index().to_dict()
        if unknown:
            counts["UNKNOWN"] = len(unknown)
        eligible = bool(target) and len(target) < len(workers)
        return dict(base, **{
            "eligible": eligible,
            "reason": "supported" if eligible else ("target_class_absent" if not target else "entire_pool_is_target"),
            "target_class": role["class_id"], "selected_family": role["selected_family"],
            "target_members": sorted(target), "known_members": sorted(known), "unknown_members": unknown,
            "target_capacity": len(target), "non_target_capacity": len(workers) - len(target),
            "known_capacity": len(known), "unknown_capacity": len(unknown),
            "full_pool_class_vector": json.dumps(counts, ensure_ascii=False, sort_keys=True),
            "history_people": role["people"],
            "history_turn_center": role["turn_history_mean"],
            "history_short_center": role["short_history_mean"],
            "history_redundancy_center": role["redundancy_history_mean"],
            "history_q_center": role["q_history_mean"], "history_t_center": role["t_history_mean"],
        })

    def prioritize(self, natural_order: Iterable[str], condition: str, building: str, policy: str) -> tuple[list[str], dict]:
        """Stable binary partition of one uniform order; final pool is unchanged.

        The returned metadata explicitly marks absent or uninformative classes.
        Unknown people stay in the random remainder, never imputed to a class.
        """
        order = list(natural_order)
        metadata = self.pool_role(order, condition, building, policy)
        target = set(metadata["target_members"])
        result = [w for w in order if w in target] + [w for w in order if w not in target]
        assert sorted(result) == sorted(order)
        return result, metadata

    def orders(self, workers: Iterable[str], condition: str, image: str, replicate: int,
               master_seed: int = 20261023, building: str | None = None,
               policies: Iterable[str] = tuple(ROLE_SPECS)) -> list[dict]:
        workers = sorted(workers)
        building = building or image.rsplit("-", 1)[0]
        rng_seed = stable_seed("v2-full-pool-prefix", master_seed, condition, image, replicate)
        natural = np.random.default_rng(rng_seed).permutation(workers).tolist()
        rows = [dict(policy="natural_random", worker_order=natural, eligible=True, reason="supported",
                     target_members=[], target_capacity=0, pool_size=len(workers))]
        for policy in policies:
            order, meta = self.prioritize(natural, condition, building, policy)
            rows.append(dict(meta, worker_order=order))
        for row in rows:
            row.update(condition=condition, image=image, building=building, replicate=replicate,
                       rng_seed=str(rng_seed), master_seed=master_seed,
                       final_pool_identity="same_actual_full_pool",
                       pairing="same_uniform_base_order_stable_binary_partition")
        return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", required=True)
    parser.add_argument("--definitions", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--pools", help="CSV with image,condition,workers (pipe separated); building optional")
    parser.add_argument("--replicates", type=int, default=8)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    book = RoleBook(args.labels, args.definitions)
    book.roles.to_csv(out / "LOBO_PRIORITY_ROLE_DEFINITIONS.csv", index=False)
    if args.pools:
        pools = pd.read_csv(args.pools)
        supports, orders = [], []
        for pool in pools.to_dict("records"):
            workers = pool["workers"].split("|")
            building = pool.get("building") or pool["image"].rsplit("-", 1)[0]
            for policy in ROLE_SPECS:
                supports.append(dict(book.pool_role(workers, pool["condition"], building, policy), image=pool["image"]))
            for replicate in range(args.replicates):
                orders.extend(book.orders(workers, pool["condition"], pool["image"], replicate, building=building))
        for rows, name in [(supports, "POLICY_POOL_CAPACITY.csv"), (orders, "EXACT_ORDER_DESIGN.csv.gz")]:
            frame = pd.DataFrame(rows)
            for col in ["worker_order", "target_members", "known_members", "unknown_members"]:
                if col in frame:
                    frame[col] = frame[col].map(lambda x: "|".join(x) if isinstance(x, list) else x)
            frame.to_csv(out / name, index=False)


if __name__ == "__main__":
    main()
