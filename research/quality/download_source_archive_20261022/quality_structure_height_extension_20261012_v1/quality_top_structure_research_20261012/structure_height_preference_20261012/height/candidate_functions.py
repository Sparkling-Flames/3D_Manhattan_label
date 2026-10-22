#!/usr/bin/env python3
"""Finite mechanism-led height/structure candidates; no label or ref selection.

score(metrics) returns historical baselines and this round's finite candidates.
No absent geometry, pairing or reference is manufactured. Input metric names
are those of the unchanged quality_v11 engine plus Hcenter.
"""
from __future__ import annotations
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location(
    "prior_top_height_candidate_functions", ROOT / "top_structure_20261012/analysis/candidate_functions.py")
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
CONFIG = json.loads((HERE / "candidate_config.json").read_text(encoding="utf-8"))
LOG_ADDENDUM = json.loads((HERE / "candidate_config_log_addendum.json").read_text(encoding="utf-8"))
ALL_CONFIGS = CONFIG["candidates"] + LOG_ADDENDUM["candidates"]
NEW_METHODS = [c["name"] for c in ALL_CONFIGS]


def number(m, *keys):
    for key in keys:
        if key in m and m[key] not in (None, ""):
            value = float(m[key])
            if math.isfinite(value):
                return value
    raise ValueError("Missing finite metric: " + "/".join(keys))


def mean_ratio(m):
    if m.get("height_mean_ratio") not in (None, ""):
        r = number(m, "height_mean_ratio")
    elif m.get("annotation_height_mean_h") not in (None, "") and m.get("reference_height_mean_h") not in (None, ""):
        r = number(m, "annotation_height_mean_h") / number(m, "reference_height_mean_h")
    else:
        return None
    if r <= 0:
        raise ValueError("Positive mean wall heights required for log ratio.")
    return r


def terms(m, config):
    i = number(m, "iou_2d", "iou", "I")
    st = number(m, "S_top_deg", "St")
    sb = number(m, "S_bottom_deg", "Sb")
    hm = number(m, "Hmean")
    hc = number(m, "Hcenter")
    d = number(m, "dir", "D")
    f = number(m, "flat", "F")
    if not 0 <= i <= 1 + 1e-10 or min(st, sb, hm, hc, d, f) < 0:
        raise ValueError("Outside component domain.")
    old_d_fraction = d * d / (d * d + 25)
    old_f_fraction = f * f / (f * f + 4)
    numerator = 1.0
    direction = 0.0
    if config["direction_mode"] == "old_numerator":
        numerator -= .075 * old_d_fraction
    elif config["direction_mode"] == "bounded_denominator":
        scale = config["direction_scale_deg"]
        direction = config["direction_cap"] * d * d / (d * d + scale * scale)
    elif config["direction_mode"] == "unbounded_denominator":
        direction = (d / config["direction_scale_deg"]) ** 2
    else:
        raise ValueError("Unknown direction combination")
    if config["flat_mode"] == "old_numerator":
        numerator -= .075 * old_f_fraction
    elif config["flat_mode"] != "none":
        raise ValueError("Unknown flatness combination")
    if config.get("height_mean_representation") == "absolute_log_ratio":
        ratio = mean_ratio(m)
        if ratio is None:
            raise ValueError("Actual positive mean ratio missing; it is not recoverable from absolute Hmean.")
        global_height_error = abs(math.log(ratio))
    else:
        global_height_error = hm
    global_height = (global_height_error / config["height_mean_scale"]) ** 2
    local_height = (hc / config["height_center_scale"]) ** 2
    if config["height_combine"] == "sum":
        height = global_height + local_height
    elif config["height_combine"] == "max":
        height = max(global_height, local_height)
    else:
        raise ValueError("Unknown height combination")
    top = config["top_weight"] * st * st / 32
    if config["top_combine"] == "sum":
        top_height = top + height
    elif config["top_combine"] == "max":
        top_height = max(top, height)
    else:
        raise ValueError("Unknown top combination")
    bottom = sb * sb / 32
    denominator = 1 + bottom + direction + top_height
    factor = numerator / denominator
    return {"direction_denominator": direction, "height_mean_denominator": global_height,
            "height_center_denominator": local_height, "top_denominator_before_combination": top,
            "bottom_denominator": bottom, "combined_height_loss": height,
            "combined_top_height_loss": top_height, "numerator_factor": numerator,
            "denominator": denominator, "factor_relative_to_floor_iou": factor,
            "penalty_relative_to_floor_iou": 1 - factor,
            "global_height_error_used": global_height_error, "score": 100 * i * factor}


def score(m):
    result = prior.score(m)
    for config in ALL_CONFIGS:
        if config.get("height_mean_representation") == "absolute_log_ratio" and mean_ratio(m) is None:
            result[config["name"]] = None
        else:
            result[config["name"]] = terms(m, config)["score"]
    return result


def parameter_terms(m):
    return {config["name"]: ({"status": "missing_actual_mean_ratio"} if config.get("height_mean_representation") == "absolute_log_ratio" and mean_ratio(m) is None else terms(m, config)) for config in ALL_CONFIGS}
