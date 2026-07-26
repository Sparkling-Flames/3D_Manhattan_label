"""Single deterministic HoHoNet LHFeat backend for Paper A risk materializers."""

from __future__ import annotations

import copy
import importlib
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np


ORBIT_FRACTIONS = (0.0, 0.25, 0.5, 0.75)
OFF_GRID_ROTATION_FRACTIONS = (1 / 7, 2 / 7, 3 / 7)
SEAM_PIXEL_OFFSETS = (-16, -8, 8, 16)


def shared_feature(value: Any):
    if isinstance(value, dict):
        if "1D" not in value:
            raise ValueError("HoHoNet extract_feat output lacks 1D feature")
        return value["1D"]
    return value


def pool_lhfeat(feature: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if feature.ndim != 2:
        raise ValueError(f"expected channel-by-width LHFeat, got {feature.shape}")
    return np.concatenate([feature.mean(1), feature.std(1)]), feature.max(1)


def aggregate_orbit(pooled: Iterable[tuple[np.ndarray, np.ndarray]]) -> tuple[np.ndarray, np.ndarray]:
    values = list(pooled)
    if len(values) != len(ORBIT_FRACTIONS):
        raise ValueError("formal circular orbit requires exactly four phases")
    return np.mean(np.stack([row[0] for row in values]), axis=0), np.mean(np.stack([row[1] for row in values]), axis=0)


def relative_l2(left: tuple[np.ndarray, np.ndarray], right: tuple[np.ndarray, np.ndarray]) -> float:
    return max(
        float(np.linalg.norm(a - b) / max(np.linalg.norm(a), np.finfo(float).eps))
        for a, b in zip(left, right)
    )


def resolve_device(device: str) -> str:
    import torch

    target = "cuda" if device == "auto" and torch.cuda.is_available() else "cpu" if device == "auto" else device
    if target.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    return target


def load_model(checkpoint: Path, config: Path, *, device: str = "auto"):
    import torch
    import yaml

    target = resolve_device(device)
    payload = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    model_config = copy.deepcopy(payload.get("model") or {})
    module_name, class_name = model_config.get("file"), model_config.get("modelclass")
    if not module_name or not class_name:
        raise ValueError("model config must contain model.file and model.modelclass")
    kwargs = model_config.get("kwargs") or {}
    kwargs.setdefault("backbone_config", {}).setdefault("kwargs", {})["pretrained"] = False
    model_class = getattr(importlib.import_module(str(module_name)), str(class_name))
    model = model_class(**kwargs)
    state = torch.load(checkpoint, map_location="cpu", weights_only=True)
    if not isinstance(state, dict) or not state or not all(hasattr(value, "shape") for value in state.values()):
        raise ValueError("HoHoNet checkpoint is not a tensor state_dict")
    model.load_state_dict(state, strict=True)
    if target.startswith("cuda"):
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        torch.use_deterministic_algorithms(True)
    return model.eval().to(target), target


def _orbit_tensors(tensor):
    width = int(tensor.shape[-1])
    return [tensor.roll(shifts=int(round(width * fraction)), dims=-1) for fraction in ORBIT_FRACTIONS]


def extract_orbit_descriptors(
    paths: list[Path], checkpoint: Path, config: Path, *, device: str = "auto", batch_size: int = 4,
    audit_seam: bool = False, seam_sample_count: int = 32, off_grid_sample_count: int = 32,
) -> tuple[dict[str, tuple[np.ndarray, np.ndarray]], dict[str, Any]]:
    import torch
    from PIL import Image

    if batch_size != 4:
        raise ValueError("formal LHFeat physical batch size is frozen at 4")
    model, target = load_model(checkpoint, config, device=device)
    output: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    four_phase_permutation_diagnostic_errors: list[float] = []
    off_grid_circular_errors: list[float] = []
    seam_errors: list[float] = []
    with torch.inference_mode():
        for index, path in enumerate(paths):
            rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0
            tensor = torch.from_numpy(rgb).permute(2, 0, 1)[None]
            orbit = torch.cat(_orbit_tensors(tensor), dim=0).to(target)
            features = shared_feature(model.extract_feat(orbit)).detach().cpu().numpy()
            pooled = [pool_lhfeat(feature) for feature in features]
            descriptor = aggregate_orbit(pooled)
            output[path.resolve().as_posix()] = descriptor
            four_phase_permutation_diagnostic_errors.append(relative_l2(descriptor, aggregate_orbit(pooled[1:] + pooled[:1])))
            if index < off_grid_sample_count:
                for fraction in OFF_GRID_ROTATION_FRACTIONS:
                    shifted = tensor.roll(shifts=int(round(tensor.shape[-1] * fraction)), dims=-1)
                    shifted_orbit = torch.cat(_orbit_tensors(shifted), dim=0).to(target)
                    shifted_features = shared_feature(model.extract_feat(shifted_orbit)).detach().cpu().numpy()
                    shifted_descriptor = aggregate_orbit([pool_lhfeat(feature) for feature in shifted_features])
                    off_grid_circular_errors.append(relative_l2(descriptor, shifted_descriptor))
            if audit_seam and index < seam_sample_count:
                for offset in SEAM_PIXEL_OFFSETS:
                    shifted = tensor.roll(shifts=offset, dims=-1)
                    shifted_orbit = torch.cat(_orbit_tensors(shifted), dim=0).to(target)
                    shifted_features = shared_feature(model.extract_feat(shifted_orbit)).detach().cpu().numpy()
                    shifted_descriptor = aggregate_orbit([pool_lhfeat(feature) for feature in shifted_features])
                    seam_errors.append(relative_l2(descriptor, shifted_descriptor))
    audit = {
        "device": target, "batch_size": batch_size, "dtype": "float32",
        "orbit_fractions": list(ORBIT_FRACTIONS),
        "four_phase_permutation_diagnostic_relative_l2_max": max(four_phase_permutation_diagnostic_errors, default=math.nan),
        "four_phase_permutation_diagnostic_image_count": len(four_phase_permutation_diagnostic_errors),
        "off_grid_rotation_fractions": list(OFF_GRID_ROTATION_FRACTIONS),
        "off_grid_circular_relative_l2_median": float(np.median(off_grid_circular_errors)) if off_grid_circular_errors else "",
        "off_grid_circular_relative_l2_q95": float(np.quantile(off_grid_circular_errors, .95)) if off_grid_circular_errors else "",
        "off_grid_circular_relative_l2_max": max(off_grid_circular_errors, default=math.nan),
        "off_grid_circular_audited_image_count": min(len(paths), off_grid_sample_count),
        # Backward-compatible metric key now points to the real off-grid audit,
        # never to the four-phase permutation identity diagnostic.
        "circular_relative_l2_max": max(off_grid_circular_errors, default=math.nan),
        "circular_audited_image_count": min(len(paths), off_grid_sample_count),
        "seam_offsets_pixels": list(SEAM_PIXEL_OFFSETS),
        "seam_audited_image_count": min(len(paths), seam_sample_count) if audit_seam else 0,
        "seam_relative_l2_median": float(np.median(seam_errors)) if seam_errors else "",
        "seam_relative_l2_q95": float(np.quantile(seam_errors, .95)) if seam_errors else "",
        "seam_relative_l2_max": max(seam_errors, default=""),
    }
    return output, audit
