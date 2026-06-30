"""Boundary package for future analyze_quality.py decomposition.

The legacy analyzer remains the active compatibility entrypoint.
"""

from .contracts import (
    ANALYZE_QUALITY_LEGACY_COMPAT,
    DRY_RUN_ONLY_FOR_SMOKE,
    FORMAL_PIPELINE_ENTRY,
    NO_ADMISSION_DECISION,
    NO_GT_MUTATION,
    NO_WORKER_ROUTING,
    OUTPUT_SCHEMA_CHANGE_ALLOWED,
)

__all__ = [
    "ANALYZE_QUALITY_LEGACY_COMPAT",
    "FORMAL_PIPELINE_ENTRY",
    "OUTPUT_SCHEMA_CHANGE_ALLOWED",
    "DRY_RUN_ONLY_FOR_SMOKE",
    "NO_WORKER_ROUTING",
    "NO_ADMISSION_DECISION",
    "NO_GT_MUTATION",
]
