from __future__ import annotations

import argparse, json
from pathlib import Path
import pandas as pd
from tools.thesis_main.analysis.annotation_uncertainty_common import *
from tools.thesis_main.analysis.annotation_uncertainty_timing import *
from tools.thesis_main.analysis.annotation_uncertainty_metrics_core import *
from tools.thesis_main.analysis.annotation_uncertainty_metrics_analysis import *
from tools.thesis_main.analysis.annotation_uncertainty_context import *
from tools.thesis_main.analysis.annotation_uncertainty_mechanisms import *

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--equal-k-replicates', type=int, default=500)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    inventory, _field_inventory = raw_inventory(out)
    if len(inventory) != 142:
        raise AssertionError(f'raw package inventory drift: {len(inventory)} != 142')
    frozen_dir = find_c1_frozen_log_dir()
    provenance = c1_log_provenance(out, frozen_dir)
    c1_timing, timing_summary = rebuild_c1_timing(out, frozen_dir)
    unified = build_unified_submission(out, c1_timing)
    timing_coverage = read_csv(out / 'unified_timing_coverage_by_stage.csv')
    sidecar, structural, pairwise, quality = load_c1_uncertainty_inputs(c1_timing)
    manual_semi_design_audit(structural, sidecar, out)
    threshold_sensitivity(pairwise, out)
    task_metrics = aggregate_uncertainty(sidecar, structural, pairwise, quality, c1_timing)
    write_csv(out / 'c1_task_condition_uncertainty.csv', task_metrics)
    manual_tasks = set(task_metrics.loc[task_metrics['condition'] == 'manual', 'base_task_id'])
    semi_tasks = set(task_metrics.loc[task_metrics['condition'] == 'semi', 'base_task_id'])
    overlap = sorted(manual_tasks & semi_tasks)
    replay = equal_k_replay(pairwise, overlap, replicates=args.equal_k_replicates)
    write_csv(out / 'manual_semi_equal_k_replay_raw.csv', replay)
    paired, inference = paired_mode_analysis(task_metrics, replay, out)
    if 'manual_task_crowd_structure_status' not in paired and 'task_crowd_structure_status' in paired:
        paired = paired.rename(columns={'task_crowd_structure_status': 'manual_task_crowd_structure_status'})
        write_csv(out / 'manual_semi_paired_task_metrics.csv', paired)
    status_transition_table(paired, out)
    uncertainty_quality_tradeoff(paired, out)
    fixed_effect_mode_models(c1_timing, quality, out)
    pretask = parse_task_data_features(out)
    choices = parse_raw_choices()
    write_csv(out / 'raw_response_choices_long.csv', choices)
    strata_frame = meta_difficulty_summary(choices, paired, pretask, out)
    stratified = stratified_mode_inference(strata_frame, out) if not strata_frame.empty else pd.DataFrame()
    semi_assoc, _task_mechanism = semi_mechanism_analysis(paired, out)
    worker_modes = worker_mode_preference(sidecar, out)
    event_assoc = event_sequence_analysis(unified, task_metrics, out)
    make_plots(paired, out)
    manifest_rows = []
    for path in sorted((p for p in out.rglob('*') if p.is_file())):
        manifest_rows.append({'path': path.relative_to(out).as_posix(), 'size_bytes': path.stat().st_size, 'sha256': sha256(path)})
    manifest = pd.DataFrame(manifest_rows)
    write_csv(out / 'OUTPUT_MANIFEST.csv', manifest)
    run_summary = {'git_head': git_head(), 'raw_file_count': len(inventory), 'manual_semi_overlap_task_count': len(paired), 'c1_timing_context_count': timing_summary.get('task_worker_active_time', {}).get('context_count'), 'c1_timing_eligible_context_count': timing_summary.get('task_worker_active_time', {}).get('eligible_context_count'), 'new_server_used_as_stage': False, 'lead_time_used_as_formal_fallback': False, 'equal_k_replicates': args.equal_k_replicates}
    write_json(out / 'RUN_SUMMARY.json', run_summary)
    generate_report(out, inventory, timing_summary, timing_coverage, task_metrics, paired, inference, stratified, semi_assoc, worker_modes, event_assoc, provenance)
    manifest_rows = [{'path': p.relative_to(out).as_posix(), 'size_bytes': p.stat().st_size, 'sha256': sha256(p)} for p in sorted((x for x in out.rglob('*') if x.is_file() and x.name != 'OUTPUT_MANIFEST.csv'))]
    write_csv(out / 'OUTPUT_MANIFEST.csv', pd.DataFrame(manifest_rows))
    print(json.dumps(run_summary, indent=2, sort_keys=True))

if __name__ == '__main__':
    main()
