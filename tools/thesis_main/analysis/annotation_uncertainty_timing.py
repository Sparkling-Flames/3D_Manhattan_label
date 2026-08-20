from __future__ import annotations

from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.annotation_uncertainty_common import *
try:
    from tools.thesis_main.analysis.materialize_c1_rehearsal_audits import materialize_active_time_ledgers
except Exception as exc:
    materialize_active_time_ledgers = None
    TIMING_IMPORT_ERROR = repr(exc)
else:
    TIMING_IMPORT_ERROR = ""

def find_c1_frozen_log_dir() -> Path:
    candidates = [ROOT / 'analysis_results' / 'c1_a_formal_closeout_20260801_r2' / 'frozen_active_logs', C1_ROOT / 'raw_snapshots' / 'active_logs', C1_ROOT / 'frozen_active_logs']
    candidates += sorted(ROOT.glob('analysis_results/**/frozen_active_logs'))
    for path in candidates:
        if path.is_dir() and len(list(path.rglob('*.jsonl'))) >= 20:
            return path
    raise FileNotFoundError('No C1 frozen active-log directory with >=20 JSONL files was found')

def normalized_event_counter(folder: Path) -> Counter[str]:
    result: Counter[str] = Counter()
    for path in sorted(folder.rglob('*.jsonl')):
        with path.open(encoding='utf-8-sig') as handle:
            for line in handle:
                if not line.strip():
                    continue
                event = json.loads(line)
                result[json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(',', ':'))] += 1
    return result

def c1_log_provenance(out: Path, frozen_dir: Path) -> dict[str, Any]:
    frozen_files = sorted(frozen_dir.rglob('*.jsonl'))
    current_dir = ROOT / 'active_logs' / 'c1'
    current_files = sorted(current_dir.glob('*.jsonl')) if current_dir.is_dir() else []
    manifest_candidates = sorted(C1_ROOT.rglob('*c1_active_log_freeze_manifest*.json'))
    result: dict[str, Any] = {'frozen_dir': frozen_dir.relative_to(ROOT).as_posix(), 'frozen_file_count': len(frozen_files), 'frozen_event_count': sum((sum((1 for line in p.open(encoding='utf-8-sig') if line.strip())) for p in frozen_files)), 'current_dir': current_dir.relative_to(ROOT).as_posix() if current_dir.exists() else 'missing', 'current_file_count': len(current_files), 'manifest_candidates': [p.relative_to(ROOT).as_posix() for p in manifest_candidates]}
    if current_files:
        frozen_by_name = {p.name: p for p in frozen_files}
        current_by_name = {p.name: p for p in current_files}
        shared = sorted(set(frozen_by_name) & set(current_by_name))
        result['shared_file_count'] = len(shared)
        result['byte_sha_equal_count'] = sum((sha256(frozen_by_name[n]) == sha256(current_by_name[n]) for n in shared))
        result['byte_sha_different_count'] = sum((sha256(frozen_by_name[n]) != sha256(current_by_name[n]) for n in shared))
        result['normalized_event_multiset_equal'] = normalized_event_counter(frozen_dir) == normalized_event_counter(current_dir)
    write_json(out / 'c1_active_log_provenance_audit.json', result)
    return result

def rebuild_c1_timing(out: Path, frozen_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    timing_out = out / 'c1_timing_rebuild'
    timing_out.mkdir(parents=True, exist_ok=True)
    if materialize_active_time_ledgers is None:
        raise RuntimeError(f'C1 timing materializer import failed: {TIMING_IMPORT_ERROR}')
    version_candidates = sorted(C1_ROOT.glob('*annotation*version*.csv'))
    version_path = version_candidates[0] if version_candidates else None
    canonical = read_csv(C1_ROOT / 'c1_canonical_annotations.csv')
    canonical['canonical_eligibility_status'] = 'selected_canonical'
    timing_meta = timing_out / 'c1_timing_meta_augmented.csv'
    write_csv(timing_meta, canonical)
    summary = materialize_active_time_ledgers(timing_meta, frozen_dir, timing_out, annotation_version_csv=version_path, collection_window_closed=True, formal=True)
    timing = read_csv(timing_out / 'c1_task_worker_active_time.csv')
    write_json(out / 'c1_timing_rebuild_summary.json', summary)
    return (timing, summary)

def normalize_stage_frame(path: Path, stage: str, *, c1_timing: pd.DataFrame | None=None) -> pd.DataFrame:
    frame = read_csv(path)
    rename = {'annotator_id': 'worker_id', 'active_time': 'source_active_time', 'task_id': 'source_task_id'}
    frame = frame.rename(columns={key: value for key, value in rename.items() if key in frame.columns})
    if 'worker_id' not in frame.columns:
        frame['worker_id'] = ''
    frame['worker_id'] = frame['worker_id'].map(norm_worker)
    frame['stage'] = stage
    frame['condition_normalized'] = frame.get('condition', '').map(clean_condition) if 'condition' in frame else ''
    frame['project_id'] = frame.get('project_id', '').astype(str)
    runtime = frame.get('runtime_task_id', frame.get('ls_runtime_task_id', frame.get('source_task_id', '')))
    frame['runtime_task_id'] = runtime.astype(str)
    frame['ls_runtime_task_id'] = frame.get('ls_runtime_task_id', '') if 'ls_runtime_task_id' in frame else ''
    if not isinstance(frame['ls_runtime_task_id'], pd.Series):
        frame['ls_runtime_task_id'] = ''
    frame['base_task_id'] = frame.get('base_task_id', frame.get('planned_task_id', frame.get('task_label', frame.get('source_task_id', '')))).astype(str)
    frame['annotation_id'] = frame.get('annotation_id', '').astype(str)
    frame['canonical_annotation_id'] = frame.get('canonical_annotation_id', frame['annotation_id']).astype(str)
    frame['lead_time_seconds'] = pd.to_numeric(frame.get('lead_time_seconds', frame.get('lead_time', np.nan)), errors='coerce')
    frame['formal_active_time_seconds'] = pd.to_numeric(frame.get('source_active_time', np.nan), errors='coerce')
    frame['formal_active_time_eligible'] = frame.get('primary_active_time_eligible', False).map(truth) if 'primary_active_time_eligible' in frame else False
    frame['active_time_identity_level'] = 'annotation_or_stage_frozen_context'
    if stage == 'C1' and c1_timing is not None:
        timing = c1_timing.copy()
        for col in ('project_id', 'runtime_task_id', 'worker_id'):
            timing[col] = timing[col].astype(str)
        timing['worker_id'] = timing['worker_id'].map(norm_worker)
        keep = ['project_id', 'runtime_task_id', 'worker_id', 'task_worker_active_seconds', 'task_worker_time_analysis_eligible', 'timing_status', 'timing_exclusion_reason', 'timing_rule_version', 'session_count', 'eligible_session_count']
        timing = timing[[c for c in keep if c in timing.columns]].drop_duplicates(['project_id', 'runtime_task_id', 'worker_id'])
        frame['runtime_task_id'] = frame['ls_runtime_task_id'].astype(str)
        frame = frame.merge(timing, how='left', on=['project_id', 'runtime_task_id', 'worker_id'], validate='many_to_one')
        frame['formal_active_time_seconds'] = pd.to_numeric(frame['task_worker_active_seconds'], errors='coerce')
        frame['formal_active_time_eligible'] = frame['task_worker_time_analysis_eligible'].map(truth)
        frame['active_time_identity_level'] = 'project_runtime_task_worker'
    frame['formal_active_time_seconds'] = frame['formal_active_time_seconds'].where(frame['formal_active_time_eligible'])
    frame['source_artifact'] = path.relative_to(ROOT).as_posix()
    frame['source_sha256'] = sha256(path)
    return frame

def build_unified_submission(out: Path, c1_timing: pd.DataFrame) -> pd.DataFrame:
    sources = [(ROOT / 'analysis_results' / 'prescreen_closeout_final_gold_v2_20260701' / 'prescreen_canonical_annotations.csv', 'P1'), (C1_ROOT / 'c1_canonical_annotations.csv', 'C1'), (ROOT / 'analysis_results' / 'c2b_closeout_20260806_final' / 'c2b_canonical_submissions.csv', 'C2-B'), (ROOT / 'analysis_results' / 'c2a_rp_block1_reestimate_20260810_v1' / 'c2a_rp_block1_canonical_submissions.csv', 'C2A-RP-B1'), (ROOT / 'analysis_results' / 'c2a_rp_block2_reestimate_20260814_v1' / 'c2a_rp_block2_canonical_submissions.csv', 'C2A-RP-B2')]
    frames = [normalize_stage_frame(path, stage, c1_timing=c1_timing) for path, stage in sources]
    unified = pd.concat(frames, ignore_index=True, sort=False)
    keep = ['stage', 'project_id', 'runtime_task_id', 'ls_runtime_task_id', 'base_task_id', 'condition_normalized', 'worker_id', 'annotation_id', 'canonical_annotation_id', 'canonical_valid', 'parse_error', 'formal_active_time_seconds', 'formal_active_time_eligible', 'active_time_identity_level', 'lead_time_seconds', 'source_artifact', 'source_sha256']
    for col in keep:
        if col not in unified:
            unified[col] = ''
    write_csv(out / 'unified_submission_timing_fact.csv', unified[keep])
    summary = unified.groupby('stage', dropna=False).agg(canonical_rows=('annotation_id', 'size'), formal_time_eligible_rows=('formal_active_time_eligible', 'sum'), formal_time_nonmissing_rows=('formal_active_time_seconds', lambda x: int(x.notna().sum())), unique_workers=('worker_id', 'nunique'), unique_tasks=('base_task_id', 'nunique')).reset_index()
    write_csv(out / 'unified_timing_coverage_by_stage.csv', summary)
    return unified
