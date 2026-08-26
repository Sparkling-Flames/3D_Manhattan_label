"""Re-run the raw difficulty/time audit with the formal task-worker active-time key.

The first audit intentionally attempted annotation-level matching and showed that
C1 logs do not support that stricter key.  The method contract defines active
 time at project × runtime task × worker, so this wrapper forces the audited,
project-safe task-worker fallback while keeping the original analysis code
unchanged for provenance.
"""
from __future__ import annotations

from tools.thesis_main.analysis import raw_difficulty_time_recompute_20260826 as audit
from tools.thesis_main.analysis.quality_core.active_time import lookup_active_log_entry as formal_lookup


def lookup_with_formal_task_worker_key(active_times, project_id, task_id, annotator_id, annotation_id=None, allow_task_level_fallback=False):
    return formal_lookup(
        active_times,
        project_id,
        task_id,
        annotator_id,
        annotation_id=annotation_id,
        allow_task_level_fallback=True,
    )


def main() -> None:
    audit.lookup_active_log_entry = lookup_with_formal_task_worker_key
    audit.main()


if __name__ == "__main__":
    main()
