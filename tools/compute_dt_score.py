from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRIMARY_EMBEDDING_BACKEND = "hohonet.shared_pre_head_gapw_l2"
PRIMARY_DISTANCE_METRIC = "euclidean"
PRIMARY_K = 10
PRIMARY_Q = 0.90
REQUIRED_INPUT_COLUMNS = ("task_id", "image_path")
STANDALONE_MANIFEST_REQUIRED_META_KEYS = (
    "strategy",
    "source",
    "frozen_at",
    "ref_hash",
    "model_version",
    "embedding_backend",
    "pool_size",
    "dedup_key",
)
DT_SUMMARY_REQUIRED_META_KEYS = (
    "round_id",
    "source_split",
    "pool_size",
    "dedup_key",
    "model_version",
    "embedding_backend",
    "distance_metric",
    "k",
    "q",
)
STANDALONE_REF_KEYS = ("task_id", "base_task_id", "image_path", "source_split", "inclusion_rank", "embedding_hash")
DT_SUMMARY_REF_KEYS = ("task_id", "base_task_id", "image_path", "source_split", "inclusion_rank")
BLACKLISTED_INPUT_FIELDS = {
    "layout_corners",
    "manual_labels",
    "annotated_polygons",
    "num_walls",
    "iou",
    "iou_edit",
    "IAA_t",
    "r_u",
    "r_u_lcb",
    "worker_group",
    "worker_group_reason",
    "difficulty",
    "model_issue",
    "scope",
    "annotator_id",
}


class BatchAbortError(RuntimeError):
    """Raised when the entire dt batch must abort under the protocol contract."""


def canonical_json_hash(payload: Any) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def l2_normalize(vector: np.ndarray) -> np.ndarray:
    arr = np.asarray(vector, dtype=np.float32)
    norm = np.linalg.norm(arr)
    if not np.isfinite(norm) or norm <= 0:
        raise ValueError("embedding norm must be positive")
    return arr / norm


@dataclass
class ReferenceRecord:
    task_id: str
    base_task_id: str
    image_path: str
    source_split: str
    inclusion_rank: int
    embedding_hash: str
    image_id: str = ""


class DtScoreComputer:
    def __init__(self, source_path: Path, model_version: str | None = None, config: dict[str, Any] | None = None):
        self.source_path = Path(source_path)
        self.source_payload = json.loads(self.source_path.read_text(encoding="utf-8"))
        self.config = {
            "cfg_path": None,
            "checkpoint_path": None,
            "device": "auto",
            "image_root": str(PROJECT_ROOT),
            "strict_manifest_hash": True,
            "strict_input_blacklist": True,
            "primary_k": None,
            "quantile": None,
            "round_id": "C1",
        }
        if config:
            self.config.update(config)

        self._model = None
        self._device = None
        self.audit_failures: list[dict[str, Any]] = []
        self.runtime_counter: Counter[str] = Counter()
        self.reference_records: list[ReferenceRecord] = []
        self.reference_embeddings: np.ndarray | None = None
        self.reference_failures: Counter[str] = Counter()
        self.threshold_manifest: dict[str, Any] | None = None
        self.tau_d: float | None = None
        self.input_audit: dict[str, Any] = {}
        self.quantile = float(self.config["quantile"] or PRIMARY_Q)

        self.source_kind, self.manifest, self.summary_seed = self._normalize_source_payload(self.source_payload)
        self._validate_manifest(model_version)
        self.model_version = model_version or str(self.manifest["meta"]["model_version"])
        self.metric = str(self.manifest["meta"].get("distance_metric") or PRIMARY_DISTANCE_METRIC)
        self.k = int(self.config["primary_k"] or self.manifest["meta"].get("k") or PRIMARY_K)
        self.quantile = float(self.config["quantile"] or self.manifest["meta"].get("q") or PRIMARY_Q)
        self.ref_hash = str(self.manifest["meta"]["ref_hash"])

    def _normalize_source_payload(self, payload: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any] | None]:
        if not isinstance(payload, dict):
            raise ValueError("dt source artifact must be a JSON object")

        if isinstance(payload.get("refs"), list):
            return "manifest", payload, None

        if isinstance(payload.get("reference_pool"), list):
            meta = payload.get("meta")
            if not isinstance(meta, dict):
                raise ValueError("dt summary must contain meta")
            missing_meta = [key for key in DT_SUMMARY_REQUIRED_META_KEYS if key not in meta]
            if missing_meta:
                raise ValueError(f"dt summary meta missing keys: {', '.join(missing_meta)}")

            refs: list[dict[str, Any]] = []
            for idx, ref in enumerate(payload["reference_pool"]):
                if not isinstance(ref, dict):
                    raise ValueError(f"dt summary reference_pool[{idx}] must be an object")
                missing_ref = [key for key in DT_SUMMARY_REF_KEYS if key not in ref]
                if missing_ref:
                    raise ValueError(f"dt summary reference_pool[{idx}] missing keys: {', '.join(missing_ref)}")
                refs.append(
                    {
                        "task_id": str(ref["task_id"]),
                        "base_task_id": str(ref["base_task_id"]),
                        "image_path": str(ref["image_path"]),
                        "source_split": str(ref["source_split"]),
                        "inclusion_rank": int(ref["inclusion_rank"]),
                        "embedding_hash": str(ref.get("embedding_hash") or ""),
                        "image_id": str(ref.get("image_id") or ""),
                    }
                )

            normalized_manifest = {
                "meta": {
                    "strategy": str(meta.get("selection_strategy") or "from_dt_reference_summary_C1"),
                    "source": str(meta.get("source_split") or "Calibration_manual"),
                    "frozen_at": str(meta.get("frozen_at") or ""),
                    "ref_hash": str(meta.get("reference_pool_hash") or canonical_json_hash(refs)),
                    "model_version": str(meta["model_version"]),
                    "embedding_backend": str(meta["embedding_backend"]),
                    "pool_size": int(meta["pool_size"]),
                    "dedup_key": str(meta["dedup_key"]),
                    "distance_metric": str(meta["distance_metric"]),
                    "k": int(meta["k"]),
                    "q": float(meta["q"]),
                    "round_id": str(meta.get("round_id") or self.config["round_id"]),
                    "provisional_tau_d": meta.get("provisional_tau_d"),
                },
                "refs": refs,
                "_source_kind": "dt_summary",
            }
            return "dt_summary", normalized_manifest, payload

        raise ValueError("dt source artifact must be either reference_pool_manifest.json or dt_reference_summary_C1.json")

    def _validate_manifest(self, requested_model_version: str | None) -> None:
        meta = self.manifest.get("meta")
        refs = self.manifest.get("refs")
        if not isinstance(meta, dict):
            raise ValueError("reference manifest must contain meta")
        if not isinstance(refs, list):
            raise ValueError("reference manifest must contain refs")

        missing_meta = [key for key in STANDALONE_MANIFEST_REQUIRED_META_KEYS if key not in meta]
        if missing_meta:
            raise ValueError(f"reference manifest meta missing keys: {', '.join(missing_meta)}")
        missing_ref_keys: list[str] = []
        duplicate_base_task_ids: set[str] = set()
        seen_base_task_ids: set[str] = set()

        for idx, ref in enumerate(refs):
            if not isinstance(ref, dict):
                raise ValueError(f"reference ref[{idx}] must be an object")
            missing_ref = [key for key in STANDALONE_REF_KEYS if key not in ref]
            if missing_ref:
                missing_ref_keys.extend(missing_ref)
            base_task_id = str(ref.get("base_task_id") or "")
            if base_task_id in seen_base_task_ids:
                duplicate_base_task_ids.add(base_task_id)
            seen_base_task_ids.add(base_task_id)

        if missing_ref_keys:
            raise ValueError(f"reference refs missing keys: {sorted(set(missing_ref_keys))}")
        if requested_model_version and str(meta["model_version"]) != str(requested_model_version):
            raise ValueError("requested model_version does not match manifest meta.model_version")
        if str(meta["embedding_backend"]) != PRIMARY_EMBEDDING_BACKEND:
            raise ValueError(f"unsupported embedding_backend: {meta['embedding_backend']}")
        if str(meta["dedup_key"]) != "base_task_id":
            raise ValueError("primary manifest must deduplicate by base_task_id")
        if str(meta["source"]) != "Calibration_manual":
            raise ValueError("primary reference pool must come from Calibration_manual")
        if int(meta["pool_size"]) != len(refs):
            raise ValueError("manifest meta.pool_size must match refs length")
        if duplicate_base_task_ids:
            raise ValueError(f"reference manifest has duplicate base_task_id values: {sorted(duplicate_base_task_ids)}")

        computed_ref_hash = canonical_json_hash(refs)
        if bool(self.config.get("strict_manifest_hash", True)) and str(meta["ref_hash"]) != computed_ref_hash:
            raise BatchAbortError("reference manifest ref_hash mismatch")

    def _resolve_device(self) -> str:
        if self._device is not None:
            return self._device
        device = str(self.config.get("device") or "auto")
        if device == "auto":
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
        self._device = device
        return device

    def _ensure_model_loaded(self) -> None:
        if self._model is not None:
            return
        cfg_path = self.config.get("cfg_path")
        checkpoint_path = self.config.get("checkpoint_path")
        if not cfg_path or not checkpoint_path:
            raise ValueError("cfg_path and checkpoint_path are required for real embedding extraction")

        import torch
        import yaml

        cfg_payload = yaml.safe_load(Path(cfg_path).read_text(encoding="utf-8"))
        model_cfg = cfg_payload.get("model") or {}
        module_name = model_cfg.get("file")
        class_name = model_cfg.get("modelclass")
        kwargs = model_cfg.get("kwargs") or {}
        if not module_name or not class_name:
            raise ValueError("model config must contain model.file and model.modelclass")

        module = importlib.import_module(str(module_name))
        model_class = getattr(module, str(class_name))
        model = model_class(**kwargs)
        state_dict = torch.load(str(checkpoint_path), map_location=self._resolve_device())
        model.load_state_dict(state_dict)
        self._model = model.eval().to(self._resolve_device())

    def _resolve_image_path(self, image_path: str) -> Path:
        text = str(image_path).strip()
        if not text:
            raise ValueError("image_path is empty")
        if text.startswith("http://") or text.startswith("https://"):
            raise ValueError("remote image_path is not supported for compute_dt_score primary path")
        path = Path(text)
        if not path.is_absolute():
            image_root = Path(str(self.config.get("image_root") or PROJECT_ROOT))
            path = image_root / path
        if not path.exists():
            raise FileNotFoundError(f"image_path not found: {path}")
        return path

    def validate_inputs(self, df: pd.DataFrame) -> dict[str, Any]:
        missing = [col for col in REQUIRED_INPUT_COLUMNS if col not in df.columns]
        if missing:
            raise ValueError(f"input csv missing columns: {', '.join(missing)}")

        blacklisted_columns = sorted(BLACKLISTED_INPUT_FIELDS.intersection(df.columns))
        if blacklisted_columns and bool(self.config.get("strict_input_blacklist", True)):
            raise BatchAbortError(
                "leakage_check_failed: blacklisted columns present in thesis-facing input: "
                + ", ".join(blacklisted_columns)
            )
        return {
            "row_count": int(len(df)),
            "ignored_blacklist_columns": blacklisted_columns,
            "strict_input_blacklist": bool(self.config.get("strict_input_blacklist", True)),
        }

    def extract_embedding(self, image_path: str) -> np.ndarray:
        self._ensure_model_loaded()
        path = self._resolve_image_path(image_path)

        import torch
        from imageio.v2 import imread

        rgb = imread(path)
        if rgb.ndim != 3 or rgb.shape[2] < 3:
            raise ValueError(f"expected RGB image, got shape={rgb.shape}")

        x = torch.from_numpy(np.asarray(rgb[..., :3])).permute(2, 0, 1)[None].float() / 255.0
        x = x.to(self._resolve_device())
        with torch.no_grad():
            feat = self._model.extract_feat(x)
        if feat.ndim != 3:
            raise ValueError(f"unexpected feature shape: {tuple(feat.shape)}")
        pooled = feat.mean(dim=-1).squeeze(0).detach().cpu().numpy()
        return l2_normalize(pooled)

    def build_reference_pool(self) -> dict[str, Any]:
        if self.reference_embeddings is not None:
            return {
                "n_ref_success": int(len(self.reference_records)),
                "n_ref_fail": int(sum(self.reference_failures.values())),
            }

        refs = self.manifest["refs"]
        embeddings: list[np.ndarray] = []
        expected_dim: int | None = None

        for ref in refs:
            ref_record = ReferenceRecord(
                task_id=str(ref["task_id"]),
                base_task_id=str(ref["base_task_id"]),
                image_path=str(ref["image_path"]),
                source_split=str(ref["source_split"]),
                inclusion_rank=int(ref["inclusion_rank"]),
                embedding_hash=str(ref.get("embedding_hash") or ""),
                image_id=str(ref.get("image_id") or ""),
            )
            try:
                embedding = self.extract_embedding(ref_record.image_path)
                if expected_dim is None:
                    expected_dim = int(embedding.shape[0])
                elif int(embedding.shape[0]) != expected_dim:
                    raise ValueError("reference embedding dimension mismatch")
                embeddings.append(embedding)
                self.reference_records.append(ref_record)
            except Exception as exc:  # noqa: BLE001
                reason = "embed_dim_error" if "dimension mismatch" in str(exc).lower() else "extract_fail"
                self.reference_failures[reason] += 1
                self.audit_failures.append(
                    {
                        "row_type": "reference",
                        "task_id": ref_record.task_id,
                        "base_task_id": ref_record.base_task_id,
                        "image_path": ref_record.image_path,
                        "d_t_status": reason,
                        "d_t_failure_reason": str(exc),
                    }
                )

        if len(embeddings) < self.k:
            raise BatchAbortError(
                f"insufficient reference embeddings after extraction failures: need k={self.k}, got {len(embeddings)}"
            )
        self.reference_embeddings = np.stack(embeddings, axis=0)
        self.threshold_manifest = self._build_threshold_manifest()
        self.tau_d = self.threshold_manifest.get("tau_d") if self.threshold_manifest else None
        return {
            "n_ref_success": int(len(self.reference_records)),
            "n_ref_fail": int(sum(self.reference_failures.values())),
        }

    def _compute_kth_neighbor_distance(self, embedding: np.ndarray, reference_embeddings: np.ndarray) -> float:
        if self.metric != PRIMARY_DISTANCE_METRIC:
            raise ValueError(f"unsupported metric: {self.metric}")
        if reference_embeddings.ndim != 2:
            raise ValueError("reference_embeddings must be 2-D")
        if reference_embeddings.shape[0] < self.k:
            raise ValueError("reference_embeddings smaller than k")
        distances = np.linalg.norm(reference_embeddings - embedding[None, :], axis=1)
        kth_distance = np.partition(distances, self.k - 1)[self.k - 1]
        return float(kth_distance)

    def _build_threshold_manifest(self) -> dict[str, Any] | None:
        assert self.reference_embeddings is not None
        if self.reference_embeddings.shape[0] <= self.k:
            return None

        loo_scores: list[float] = []
        for idx in range(self.reference_embeddings.shape[0]):
            current = self.reference_embeddings[idx]
            rest = np.delete(self.reference_embeddings, idx, axis=0)
            loo_scores.append(self._compute_kth_neighbor_distance(current, rest))

        tau_d = float(np.quantile(np.asarray(loo_scores, dtype=np.float32), self.quantile))
        threshold_manifest = {
            "rule_version": "dt_threshold_v1",
            "created_at": utc_now_iso(),
            "source_artifact": str(self.source_path),
            "source_kind": self.source_kind,
            "reference_pool_hash": self.ref_hash,
            "metric": self.metric,
            "k": self.k,
            "q": self.quantile,
            "tau_d": tau_d,
            "n_ref_success": int(self.reference_embeddings.shape[0]),
            "n_ref_fail": int(sum(self.reference_failures.values())),
            "loo_score_min": float(min(loo_scores)),
            "loo_score_median": float(np.median(np.asarray(loo_scores, dtype=np.float32))),
            "loo_score_max": float(max(loo_scores)),
        }
        threshold_manifest["threshold_manifest_hash"] = canonical_json_hash(
            {k: v for k, v in threshold_manifest.items() if k != "threshold_manifest_hash"}
        )
        return threshold_manifest

    def build_dt_reference_summary(self) -> dict[str, Any]:
        if self.reference_embeddings is None:
            self.build_reference_pool()

        loo_summary = {
            "n_ref_success": int(len(self.reference_records)),
            "n_ref_fail": int(sum(self.reference_failures.values())),
            "loo_score_min": self.threshold_manifest.get("loo_score_min") if self.threshold_manifest else None,
            "loo_score_median": self.threshold_manifest.get("loo_score_median") if self.threshold_manifest else None,
            "loo_score_max": self.threshold_manifest.get("loo_score_max") if self.threshold_manifest else None,
            "provisional_tau_d": self.tau_d,
        }
        failure_audit = {
            "extract_fail_count": int(self.reference_failures.get("extract_fail", 0)),
            "embed_dim_error_count": int(self.reference_failures.get("embed_dim_error", 0)),
            "knn_runtime_error_count": 0,
            "ref_hash_mismatch": False,
            "leakage_check_failed": False,
        }
        return {
            "meta": {
                "round_id": str(self.manifest["meta"].get("round_id") or self.config.get("round_id") or "C1"),
                "source_split": str(self.manifest["meta"].get("source") or "Calibration_manual"),
                "pool_size": int(self.manifest["meta"]["pool_size"]),
                "dedup_key": str(self.manifest["meta"]["dedup_key"]),
                "model_version": self.model_version,
                "embedding_backend": PRIMARY_EMBEDDING_BACKEND,
                "distance_metric": self.metric,
                "k": self.k,
                "q": self.quantile,
                "provisional_tau_d": self.tau_d,
                "reference_pool_hash": self.ref_hash,
                "frozen_at": str(self.manifest["meta"].get("frozen_at") or ""),
                "selection_strategy": str(self.manifest["meta"].get("strategy") or self.source_kind),
            },
            "reference_pool": [
                {
                    "task_id": str(ref["task_id"]),
                    "base_task_id": str(ref["base_task_id"]),
                    "image_id": str(ref.get("image_id") or Path(str(ref["image_path"])).stem),
                    "image_path": str(ref["image_path"]),
                    "source_split": str(ref["source_split"]),
                    "inclusion_rank": int(ref["inclusion_rank"]),
                    "embedding_hash": str(ref.get("embedding_hash") or ""),
                }
                for ref in self.manifest["refs"]
            ],
            "loo_summary": loo_summary,
            "failure_audit": failure_audit,
        }

    def compute_one(self, row: pd.Series) -> dict[str, Any]:
        assert self.reference_embeddings is not None
        task_id = str(row["task_id"])
        image_path = str(row["image_path"])
        compute_ts = utc_now_iso()
        try:
            embedding = self.extract_embedding(image_path)
            if embedding.shape[0] != self.reference_embeddings.shape[1]:
                raise ValueError("query embedding dimension mismatch")
            dt_score = self._compute_kth_neighbor_distance(embedding, self.reference_embeddings)
            threshold_hash = (
                str(self.threshold_manifest["threshold_manifest_hash"])
                if self.threshold_manifest is not None
                else ""
            )
            return {
                "task_id": task_id,
                "d_t": dt_score,
                "d_t_status": "success",
                "d_t_k": self.k,
                "d_t_ref_hash": self.ref_hash,
                "d_t_model_ver": self.model_version,
                "d_t_metric": self.metric,
                "d_t_pool_size": int(self.reference_embeddings.shape[0]),
                "d_t_failure_reason": "",
                "d_t_compute_ts": compute_ts,
                "tau_d": self.tau_d,
                "tau_d_quantile": self.quantile if self.tau_d is not None else np.nan,
                "I_t_OOD": int(dt_score > self.tau_d) if self.tau_d is not None else np.nan,
                "threshold_manifest_hash": threshold_hash,
            }
        except Exception as exc:  # noqa: BLE001
            status = "embed_dim_error" if "dimension mismatch" in str(exc).lower() else "extract_fail"
            if isinstance(exc, np.linalg.LinAlgError):
                status = "knn_runtime_error"
            return {
                "task_id": task_id,
                "d_t": np.nan,
                "d_t_status": status,
                "d_t_k": self.k,
                "d_t_ref_hash": self.ref_hash,
                "d_t_model_ver": self.model_version,
                "d_t_metric": self.metric,
                "d_t_pool_size": int(self.reference_embeddings.shape[0]),
                "d_t_failure_reason": str(exc),
                "d_t_compute_ts": compute_ts,
                "tau_d": self.tau_d,
                "tau_d_quantile": self.quantile if self.tau_d is not None else np.nan,
                "I_t_OOD": np.nan,
                "threshold_manifest_hash": (
                    str(self.threshold_manifest["threshold_manifest_hash"])
                    if self.threshold_manifest is not None
                    else ""
                ),
            }

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        self.input_audit = self.validate_inputs(df)
        self.build_reference_pool()
        out_df = df.copy()

        rows: list[dict[str, Any]] = []
        for _, row in out_df.iterrows():
            result = self.compute_one(row)
            rows.append(result)
            self.runtime_counter[result["d_t_status"]] += 1
            if result["d_t_status"] != "success":
                self.audit_failures.append(
                    {
                        "row_type": "task",
                        "task_id": result["task_id"],
                        "image_path": str(row["image_path"]),
                        "d_t_status": result["d_t_status"],
                        "d_t_failure_reason": result["d_t_failure_reason"],
                    }
                )

        result_df = pd.DataFrame.from_records(rows)
        return out_df.merge(result_df, on="task_id", how="left", validate="one_to_one")

    def build_audit_report(self) -> dict[str, Any]:
        return {
            "rule_version": "dt_score_v1",
            "run_at": utc_now_iso(),
            "source_artifact": {
                "path": str(self.source_path),
                "kind": self.source_kind,
                "reference_pool_hash": self.ref_hash,
            },
            "primary_config": {
                "embedding_backend": PRIMARY_EMBEDDING_BACKEND,
                "metric": self.metric,
                "k": self.k,
                "q": self.quantile,
                "model_version": self.model_version,
            },
            "reference_pool": {
                "hash": self.ref_hash,
                "unique_base_task_ids": int(len(self.reference_records)),
                "configured_pool_size": int(self.manifest["meta"]["pool_size"]),
                "success_pool_size": int(len(self.reference_records)),
            },
            "runtime_summary": {
                "total_tasks": int(sum(self.runtime_counter.values())),
                "success": int(self.runtime_counter.get("success", 0)),
                "na_count": int(sum(v for k, v in self.runtime_counter.items() if k != "success")),
                "ignored_blacklist_columns": list(self.input_audit.get("ignored_blacklist_columns", [])),
                "strict_input_blacklist": bool(self.input_audit.get("strict_input_blacklist", True)),
            },
            "failure_breakdown": {
                "reference_extract_fail": int(self.reference_failures.get("extract_fail", 0)),
                "reference_embed_dim_error": int(self.reference_failures.get("embed_dim_error", 0)),
                "task_extract_fail": int(self.runtime_counter.get("extract_fail", 0)),
                "task_embed_dim_error": int(self.runtime_counter.get("embed_dim_error", 0)),
                "task_knn_runtime_error": int(self.runtime_counter.get("knn_runtime_error", 0)),
            },
            "appendix_runs": [],
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compute thesis-facing primary d_t scores from a fixed calibration-only reference pool.")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--dt-summary", type=Path, help="Thesis-facing dt_reference_summary_C1.json")
    source_group.add_argument("--manifest", type=Path, help="Frozen standalone reference_pool_manifest.json")
    parser.add_argument("--input", required=True, type=Path, help="Task-level CSV with at least task_id and image_path")
    parser.add_argument("--output", required=True, type=Path, help="Output CSV path for task-level table with d_t columns")
    parser.add_argument("--cfg", required=True, type=Path, help="HoHoNet YAML config used for feature extraction")
    parser.add_argument("--pth", required=True, type=Path, help="HoHoNet checkpoint used for feature extraction")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--image-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--audit-output", type=Path, default=None)
    parser.add_argument("--failures-output", type=Path, default=None)
    parser.add_argument("--ref-snapshot-output", type=Path, default=None)
    parser.add_argument("--threshold-output", type=Path, default=None)
    parser.add_argument("--dt-summary-output", type=Path, default=None, help="Write contract-shaped dt_reference_summary_C1.json")
    parser.add_argument(
        "--allow-blacklisted-columns",
        action="store_true",
        help="Exploratory-only override. Thesis-facing primary path defaults to strict blacklist rejection.",
    )
    parser.add_argument("--round-id", default="C1")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_df = pd.read_csv(args.input, dtype=str).fillna("")
    source_path = args.dt_summary or args.manifest
    assert source_path is not None

    computer = DtScoreComputer(
        source_path,
        config={
            "cfg_path": str(args.cfg),
            "checkpoint_path": str(args.pth),
            "device": args.device,
            "image_root": str(args.image_root),
            "strict_input_blacklist": not args.allow_blacklisted_columns,
            "round_id": args.round_id,
        },
    )
    scored = computer.run(input_df)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    scored.to_csv(args.output, index=False, encoding="utf-8")

    audit_output = args.audit_output or args.output.with_name("dt_audit_report.json")
    failures_output = args.failures_output or args.output.with_name("dt_failures.csv")
    audit_output.parent.mkdir(parents=True, exist_ok=True)
    failures_output.parent.mkdir(parents=True, exist_ok=True)

    audit_output.write_text(json.dumps(computer.build_audit_report(), indent=2, ensure_ascii=False), encoding="utf-8")
    pd.DataFrame.from_records(computer.audit_failures).to_csv(failures_output, index=False, encoding="utf-8")

    if args.ref_snapshot_output is not None:
        args.ref_snapshot_output.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            [
                {
                    "task_id": ref.task_id,
                    "base_task_id": ref.base_task_id,
                    "image_id": ref.image_id or Path(ref.image_path).stem,
                    "image_path": ref.image_path,
                    "source_split": ref.source_split,
                    "inclusion_rank": ref.inclusion_rank,
                }
                for ref in computer.reference_records
            ]
        ).to_csv(args.ref_snapshot_output, index=False, encoding="utf-8")

    if args.threshold_output is not None and computer.threshold_manifest is not None:
        args.threshold_output.parent.mkdir(parents=True, exist_ok=True)
        args.threshold_output.write_text(
            json.dumps(computer.threshold_manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    if args.dt_summary_output is not None:
        args.dt_summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.dt_summary_output.write_text(
            json.dumps(computer.build_dt_reference_summary(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
