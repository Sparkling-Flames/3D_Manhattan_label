from __future__ import annotations

import hashlib
from typing import Any, Iterable


def build_crossfit_folds(rows: Iterable[dict[str, Any]], *, n_folds: int = 2) -> list[dict[str, Any]]:
    """Deterministically assign task-level evidence to offline folds."""
    n_folds = max(2, int(n_folds))
    out = []
    for row in rows:
        task_id = str(row.get("task_id", ""))
        fold = int(hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:8], 16) % n_folds
        out.append({**row, "crossfit_fold": fold, "crossfit_role": "candidate_replay_only", "interpretation_allowed": False})
    return out
