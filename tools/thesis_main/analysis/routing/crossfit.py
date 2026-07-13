from __future__ import annotations

import hashlib
from typing import Any, Iterable


def build_crossfit_folds(rows: Iterable[dict[str, Any]], *, n_folds: int = 2) -> list[dict[str, Any]]:
    """Assign every annotation of a base image to one deterministic fold."""
    n_folds = max(2, int(n_folds))
    out = []
    for row in rows:
        base_task_id = str(row.get("base_task_id", "")).strip()
        if not base_task_id:
            raise ValueError("base_task_id is required for crossfit folds")
        fold = int(hashlib.sha256(base_task_id.encode("utf-8")).hexdigest()[:8], 16) % n_folds
        out.append({**row, "crossfit_fold": fold, "crossfit_group_key": base_task_id, "crossfit_role": "candidate_replay_only", "interpretation_allowed": False})
    return out
