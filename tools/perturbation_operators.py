from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from typing import Any


XML_ALIAS_SET = {
    "acceptable",
    "overextend_adjacent",
    "underextend",
    "over_parsing",
    "corner_drift",
    "corner_duplicate",
    "topology_failure",
    "fail",
}


def _wrap_pct(x_pct: float) -> float:
    return float(x_pct) % 100.0


def _clamp_pct(y_pct: float) -> float:
    return max(0.0, min(100.0, float(y_pct)))


def _clone_corners(corners_norm: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(corner) for corner in corners_norm]


def _stable_hash(payload: Any) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _sort_corners(corners_norm: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(corners_norm, key=lambda item: (float(item["x_pct"]), float(item["y_top_pct"]), float(item["y_bottom_pct"])))
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(ordered):
        normalized.append(
            {
                "id": int(item.get("id", index)),
                "x_pct": _wrap_pct(item["x_pct"]),
                "y_top_pct": _clamp_pct(item["y_top_pct"]),
                "y_bottom_pct": _clamp_pct(item["y_bottom_pct"]),
            }
        )
    return normalized


def canonical_corners_to_runtime_pairs(
    corners_norm: list[dict[str, Any]],
    image_width: int,
    image_height: int,
) -> list[dict[str, float]]:
    runtime_pairs = []
    for corner in corners_norm:
        runtime_pairs.append(
            {
                "x": float(corner["x_pct"]) * float(image_width) / 100.0,
                "y_ceiling": float(corner["y_top_pct"]) * float(image_height) / 100.0,
                "y_floor": float(corner["y_bottom_pct"]) * float(image_height) / 100.0,
            }
        )
    return runtime_pairs


def ls_keypoints_to_canonical_corners(
    prediction_result: list[dict[str, Any]],
    threshold_ratio: float = 0.05,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    keypoints: list[dict[str, float]] = []
    width = 1024
    height = 512

    for result in prediction_result:
        if result.get("type") not in {"keypointlabels", "keypointregion"}:
            continue
        value = result.get("value", {})
        x_pct = value.get("x")
        y_pct = value.get("y")
        if x_pct is None or y_pct is None:
            continue
        width = int(result.get("original_width") or width)
        height = int(result.get("original_height") or height)
        keypoints.append({"x_pct": float(x_pct), "y_pct": float(y_pct)})

    if len(keypoints) < 2:
        return [], {"width": width, "height": height, "n_keypoints": len(keypoints), "pair_coverage": 0.0}

    keypoints.sort(key=lambda item: (item["x_pct"], item["y_pct"]))
    threshold = 100.0 * float(threshold_ratio)
    used = [False] * len(keypoints)
    corners_norm: list[dict[str, Any]] = []

    for i, point in enumerate(keypoints):
        if used[i]:
            continue
        best_j = -1
        for j in range(i + 1, len(keypoints)):
            if used[j]:
                continue
            if abs(keypoints[j]["x_pct"] - point["x_pct"]) < threshold:
                best_j = j
                break
        if best_j == -1:
            continue
        used[i] = True
        used[best_j] = True
        other = keypoints[best_j]
        corners_norm.append(
            {
                "id": len(corners_norm),
                "x_pct": 0.5 * (point["x_pct"] + other["x_pct"]),
                "y_top_pct": min(point["y_pct"], other["y_pct"]),
                "y_bottom_pct": max(point["y_pct"], other["y_pct"]),
            }
        )

    pair_coverage = (2.0 * len(corners_norm) / len(keypoints)) if keypoints else 0.0
    return _sort_corners(corners_norm), {
        "width": width,
        "height": height,
        "n_keypoints": len(keypoints),
        "n_corners": len(corners_norm),
        "pair_coverage": pair_coverage,
        "odd_points": len(keypoints) % 2 == 1,
    }


@dataclass
class OperatorResult:
    status: str
    family_id: str
    corners_norm: list[dict[str, Any]]
    failure_code: str | None
    audit: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "family_id": self.family_id,
            "corners_norm": self.corners_norm,
            "failure_code": self.failure_code,
            "audit": self.audit,
        }


class BaseOperator:
    family_id = "base"
    transform_scope = "unspecified"

    def _result(
        self,
        *,
        corners_norm: list[dict[str, Any]],
        seed: int,
        lambda_level: str,
        status: str = "success",
        failure_code: str | None = None,
        extra_audit: dict[str, Any] | None = None,
    ) -> OperatorResult:
        audit = {
            "seed": int(seed),
            "lambda_level": str(lambda_level),
            "transform_scope": self.transform_scope,
            "x_rule": "wrap",
            "y_rule": "clamp",
        }
        if extra_audit:
            audit.update(extra_audit)
        return OperatorResult(
            status=status,
            family_id=self.family_id,
            corners_norm=_sort_corners(corners_norm),
            failure_code=failure_code,
            audit=audit,
        )

    def apply(
        self,
        corners_norm: list[dict[str, Any]],
        image_width: int,
        image_height: int,
        seed: int,
        lambda_level: str,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError


class AcceptableOperator(BaseOperator):
    family_id = "acceptable"
    transform_scope = "global_small_jitter"

    def apply(self, corners_norm, image_width, image_height, seed, lambda_level, config=None):
        if lambda_level not in {"none", "weak", "medium"}:
            return self._result(corners_norm=corners_norm, seed=seed, lambda_level=lambda_level, status="invalid", failure_code="invalid_input").to_dict()

        if lambda_level == "none":
            return self._result(corners_norm=_clone_corners(corners_norm), seed=seed, lambda_level=lambda_level, extra_audit={"jitter_pct": 0.0}).to_dict()

        rng = random.Random(int(seed))
        jitter_pct = 0.2 if lambda_level == "weak" else 0.4
        mutated = []
        for corner in _clone_corners(corners_norm):
            x_delta = rng.uniform(-jitter_pct, jitter_pct)
            y_delta = rng.uniform(-jitter_pct, jitter_pct)
            corner["x_pct"] = _wrap_pct(corner["x_pct"] + x_delta)
            corner["y_top_pct"] = _clamp_pct(corner["y_top_pct"] + y_delta)
            corner["y_bottom_pct"] = _clamp_pct(corner["y_bottom_pct"] + y_delta)
            if corner["y_top_pct"] > corner["y_bottom_pct"]:
                corner["y_top_pct"], corner["y_bottom_pct"] = corner["y_bottom_pct"], corner["y_top_pct"]
            mutated.append(corner)
        return self._result(corners_norm=mutated, seed=seed, lambda_level=lambda_level, extra_audit={"jitter_pct": jitter_pct}).to_dict()


class CornerShiftOperator(BaseOperator):
    family_id = "corner_drift"
    transform_scope = "single_physical_corner"

    def apply(self, corners_norm, image_width, image_height, seed, lambda_level, config=None):
        if not corners_norm:
            return self._result(corners_norm=[], seed=seed, lambda_level=lambda_level, status="invalid", failure_code="invalid_input").to_dict()

        config = config or {}
        magnitudes = {"weak": 1.0, "medium": 2.5, "strong": 4.0}
        if lambda_level not in magnitudes:
            return self._result(corners_norm=corners_norm, seed=seed, lambda_level=lambda_level, status="invalid", failure_code="invalid_input").to_dict()

        rng = random.Random(int(seed))
        mutated = _clone_corners(corners_norm)
        corner_index = int(config.get("corner_index", 0)) % len(mutated)
        delta_x = float(config.get("x_delta_pct", rng.uniform(-magnitudes[lambda_level], magnitudes[lambda_level])))
        delta_top = float(config.get("y_top_delta_pct", rng.uniform(-0.5 * magnitudes[lambda_level], 0.5 * magnitudes[lambda_level])))
        delta_bottom = float(config.get("y_bottom_delta_pct", rng.uniform(-0.5 * magnitudes[lambda_level], 0.5 * magnitudes[lambda_level])))

        mutated[corner_index]["x_pct"] = _wrap_pct(mutated[corner_index]["x_pct"] + delta_x)
        mutated[corner_index]["y_top_pct"] = _clamp_pct(mutated[corner_index]["y_top_pct"] + delta_top)
        mutated[corner_index]["y_bottom_pct"] = _clamp_pct(mutated[corner_index]["y_bottom_pct"] + delta_bottom)
        if mutated[corner_index]["y_top_pct"] > mutated[corner_index]["y_bottom_pct"]:
            return self._result(corners_norm=corners_norm, seed=seed, lambda_level=lambda_level, status="reject", failure_code="transform_degenerate").to_dict()

        return self._result(
            corners_norm=mutated,
            seed=seed,
            lambda_level=lambda_level,
            extra_audit={
                "corner_index": corner_index,
                "x_delta_pct": round(delta_x, 6),
                "y_top_delta_pct": round(delta_top, 6),
                "y_bottom_delta_pct": round(delta_bottom, 6),
            },
        ).to_dict()


class CornerDuplicateOperator(BaseOperator):
    family_id = "corner_duplicate"
    transform_scope = "single_physical_corner"

    def apply(self, corners_norm, image_width, image_height, seed, lambda_level, config=None):
        if not corners_norm:
            return self._result(corners_norm=[], seed=seed, lambda_level=lambda_level, status="invalid", failure_code="invalid_input").to_dict()

        config = config or {}
        if lambda_level not in {"weak", "medium", "strong"}:
            return self._result(corners_norm=corners_norm, seed=seed, lambda_level=lambda_level, status="invalid", failure_code="invalid_input").to_dict()

        offset = {"weak": 0.6, "medium": 1.2, "strong": 1.8}[lambda_level]
        rng = random.Random(int(seed))
        mutated = _clone_corners(corners_norm)
        anchor_index = int(config.get("corner_index", 0)) % len(mutated)
        new_points = int(config.get("new_points", 1 if lambda_level != "strong" else 2))
        anchor = mutated[anchor_index]
        inserts = []
        for point_offset in range(new_points):
            step = float(point_offset + 1)
            inserts.append(
                {
                    "id": len(mutated) + point_offset,
                    "x_pct": _wrap_pct(anchor["x_pct"] + rng.choice([-1.0, 1.0]) * offset * step),
                    "y_top_pct": _clamp_pct(anchor["y_top_pct"] + rng.uniform(-0.2, 0.2) * step),
                    "y_bottom_pct": _clamp_pct(anchor["y_bottom_pct"] + rng.uniform(-0.2, 0.2) * step),
                }
            )
        if any(item["y_top_pct"] > item["y_bottom_pct"] for item in inserts):
            return self._result(corners_norm=corners_norm, seed=seed, lambda_level=lambda_level, status="reject", failure_code="transform_degenerate").to_dict()

        mutated.extend(inserts)
        return self._result(
            corners_norm=mutated,
            seed=seed,
            lambda_level=lambda_level,
            extra_audit={"corner_index": anchor_index, "new_points": new_points, "offset_pct": offset},
        ).to_dict()


class OverExtendOperator(BaseOperator):
    family_id = "overextend_adjacent"
    transform_scope = "adjacent_edge_span"

    def apply(self, corners_norm, image_width, image_height, seed, lambda_level, config=None):
        if len(corners_norm) < 2:
            return self._result(corners_norm=corners_norm, seed=seed, lambda_level=lambda_level, status="invalid", failure_code="insufficient_corners").to_dict()
        config = config or {}
        if "approved_edge_index" not in config:
            return self._result(corners_norm=corners_norm, seed=seed, lambda_level=lambda_level, status="invalid", failure_code="config_missing").to_dict()

        extend_pct = {"weak": 2.0, "medium": 4.0, "strong": 6.0}.get(lambda_level)
        if extend_pct is None:
            return self._result(corners_norm=corners_norm, seed=seed, lambda_level=lambda_level, status="invalid", failure_code="invalid_input").to_dict()

        mutated = _clone_corners(corners_norm)
        edge_index = int(config["approved_edge_index"]) % len(mutated)
        anchor = mutated[edge_index]
        insert = {
            "id": len(mutated),
            "x_pct": _wrap_pct(anchor["x_pct"] + extend_pct),
            "y_top_pct": _clamp_pct(anchor["y_top_pct"]),
            "y_bottom_pct": _clamp_pct(anchor["y_bottom_pct"]),
        }
        mutated.append(insert)
        return self._result(
            corners_norm=mutated,
            seed=seed,
            lambda_level=lambda_level,
            extra_audit={"approved_edge_index": edge_index, "extend_pct": extend_pct},
        ).to_dict()


class UnderExtendOperator(BaseOperator):
    family_id = "underextend"
    transform_scope = "local_wall_span"

    def apply(self, corners_norm, image_width, image_height, seed, lambda_level, config=None):
        if len(corners_norm) < 4:
            return self._result(corners_norm=corners_norm, seed=seed, lambda_level=lambda_level, status="invalid", failure_code="insufficient_corners").to_dict()
        config = config or {}
        removal_count = {"weak": 1, "medium": 2, "strong": 2}.get(lambda_level)
        if removal_count is None:
            return self._result(corners_norm=corners_norm, seed=seed, lambda_level=lambda_level, status="invalid", failure_code="invalid_input").to_dict()

        mutated = _clone_corners(corners_norm)
        start_index = int(config.get("remove_index", 1)) % len(mutated)
        for _ in range(removal_count):
            if len(mutated) <= 3:
                return self._result(corners_norm=corners_norm, seed=seed, lambda_level=lambda_level, status="reject", failure_code="transform_degenerate").to_dict()
            mutated.pop(start_index % len(mutated))
        return self._result(
            corners_norm=mutated,
            seed=seed,
            lambda_level=lambda_level,
            extra_audit={"remove_index": start_index, "remove_count": removal_count},
        ).to_dict()


class OverParsingOperator(BaseOperator):
    family_id = "over_parsing"
    transform_scope = "local_ghost_geometry"

    def apply(self, corners_norm, image_width, image_height, seed, lambda_level, config=None):
        if len(corners_norm) < 2:
            return self._result(corners_norm=corners_norm, seed=seed, lambda_level=lambda_level, status="invalid", failure_code="insufficient_corners").to_dict()
        config = config or {}
        if "approved_edge_index" not in config and not config.get("surrogate_mode"):
            return self._result(corners_norm=corners_norm, seed=seed, lambda_level=lambda_level, status="invalid", failure_code="config_missing").to_dict()

        offset = {"weak": 0.8, "medium": 1.5, "strong": 2.2}.get(lambda_level)
        if offset is None:
            return self._result(corners_norm=corners_norm, seed=seed, lambda_level=lambda_level, status="invalid", failure_code="invalid_input").to_dict()

        edge_index = int(config.get("approved_edge_index", 0)) % len(corners_norm)
        anchor = corners_norm[edge_index]
        insert = {
            "id": len(corners_norm),
            "x_pct": _wrap_pct(anchor["x_pct"] + offset),
            "y_top_pct": _clamp_pct(anchor["y_top_pct"] + 0.3 * offset),
            "y_bottom_pct": _clamp_pct(anchor["y_bottom_pct"] - 0.3 * offset),
        }
        if insert["y_top_pct"] > insert["y_bottom_pct"]:
            return self._result(corners_norm=corners_norm, seed=seed, lambda_level=lambda_level, status="reject", failure_code="transform_degenerate").to_dict()

        mutated = _clone_corners(corners_norm)
        mutated.append(insert)
        return self._result(
            corners_norm=mutated,
            seed=seed,
            lambda_level=lambda_level,
            extra_audit={
                "approved_edge_index": edge_index,
                "surrogate_mode": bool(config.get("surrogate_mode", False)),
                "offset_pct": offset,
            },
        ).to_dict()


class TopologyBreakOperator(BaseOperator):
    family_id = "topology_failure"
    transform_scope = "intentional_invalid_topology"

    def apply(self, corners_norm, image_width, image_height, seed, lambda_level, config=None):
        mutated = _clone_corners(corners_norm)
        if len(mutated) >= 2:
            mutated[0]["y_top_pct"] = mutated[0]["y_bottom_pct"] + 5.0
        return self._result(
            corners_norm=mutated,
            seed=seed,
            lambda_level=lambda_level,
            status="invalid",
            failure_code="transform_degenerate",
            extra_audit={"is_intentionally_invalid": True, "iou_status": "na_intentional"},
        ).to_dict()


class CatastrophicFailOperator(BaseOperator):
    family_id = "fail"
    transform_scope = "intentional_invalid_global"

    def apply(self, corners_norm, image_width, image_height, seed, lambda_level, config=None):
        return self._result(
            corners_norm=[],
            seed=seed,
            lambda_level=lambda_level,
            status="invalid",
            failure_code="transform_degenerate",
            extra_audit={"is_intentionally_invalid": True, "iou_status": "na_intentional"},
        ).to_dict()


OPERATOR_REGISTRY = {
    "acceptable": AcceptableOperator(),
    "corner_drift": CornerShiftOperator(),
    "corner_duplicate": CornerDuplicateOperator(),
    "overextend_adjacent": OverExtendOperator(),
    "underextend": UnderExtendOperator(),
    "over_parsing": OverParsingOperator(),
    "topology_failure": TopologyBreakOperator(),
    "fail": CatastrophicFailOperator(),
}


class PerturbationEngine:
    def __init__(self, operator_registry: dict[str, BaseOperator] | None = None):
        self.operator_registry = operator_registry or OPERATOR_REGISTRY

    def generate_batch(
        self,
        frozen_plan: dict[str, Any],
        task_sources: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        outputs = []
        for perturbation in frozen_plan.get("perturbations", []):
            base_task_id = perturbation["base_task_id"]
            operator_id = perturbation["operator_id"]
            task_source = task_sources.get(base_task_id)
            if task_source is None:
                outputs.append(
                    {
                        "manifest_row_id": perturbation["manifest_row_id"],
                        "base_task_id": base_task_id,
                        "operator_id": operator_id,
                        "status": "blocked_by_dependency",
                        "failure_code": "missing_task_source",
                        "audit": {},
                        "corners_norm": [],
                    }
                )
                continue

            operator = self.operator_registry.get(operator_id)
            if operator is None:
                outputs.append(
                    {
                        "manifest_row_id": perturbation["manifest_row_id"],
                        "base_task_id": base_task_id,
                        "operator_id": operator_id,
                        "status": "invalid",
                        "failure_code": "unsupported_family",
                        "audit": {},
                        "corners_norm": [],
                    }
                )
                continue

            result = operator.apply(
                corners_norm=_clone_corners(task_source.get("corners_norm", [])),
                image_width=int(task_source.get("image_width", 1024)),
                image_height=int(task_source.get("image_height", 512)),
                seed=int(perturbation["seed"]),
                lambda_level=str(perturbation["lambda_level"]),
                config=dict(perturbation.get("config") or {}),
            )
            result.update(
                {
                    "manifest_row_id": perturbation["manifest_row_id"],
                    "base_task_id": base_task_id,
                    "operator_id": operator_id,
                }
            )
            outputs.append(result)
        return outputs


def freeze_plan(
    manifest_rows: list[dict[str, Any]],
    task_sources: dict[str, dict[str, Any]],
    *,
    rule_version: str = "c-perturbation-plan-v1",
    seed_master: int = 2026031101,
) -> dict[str, Any]:
    perturbations = []
    for row in manifest_rows:
        base_task_id = row["base_task_id"]
        task_source = task_sources.get(base_task_id, {})
        perturbations.append(
            {
                "manifest_row_id": row["manifest_row_id"],
                "task_id": row.get("target_registry_uid", row["manifest_row_id"]),
                "base_task_id": base_task_id,
                "title": row.get("title"),
                "operator_id": row["operator_id"],
                "source_type": row["source_type"],
                "lambda_level": row["lambda_level"],
                "seed": int(row["seed"]),
                "config": row.get("config") or {},
                "source_prediction_ref": {
                    "title": task_source.get("title"),
                    "image_width": task_source.get("image_width"),
                    "image_height": task_source.get("image_height"),
                    "prediction_hash": task_source.get("prediction_hash"),
                },
            }
        )

    meta = {
        "rule_version": rule_version,
        "seed_master": int(seed_master),
        "script_hash": _stable_hash({"rule_version": rule_version, "manifest_rows": manifest_rows}),
        "n_perturbations": len(perturbations),
    }
    return {"meta": meta, "perturbations": perturbations}
