"""Finalize a completed sharded run after optional consolidation was stopped.

Does not fuse, score, regenerate a shard, or claim the optional full JSONL was
completed. All counts derive from frozen requests and completed per-pool checks.
"""
import argparse,collections,json
from pathlib import Path
from ac_endpoint_runtime import read_json,sha,write_json

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--plan',required=True)
    ap.add_argument('--endpoints',required=True);ap.add_argument('--stop-receipt',required=True);a=ap.parse_args()
    plan=Path(a.plan);out=Path(a.endpoints);target=out/'RUN_RECEIPT.json'
    assert not target.exists(),'Do not overwrite an existing final run receipt.'
    registration=read_json(plan/'CACHE_PLAN.json');contract=read_json(plan/'ENGINE_AND_INPUT_CONTRACT.json')
    checks=[read_json(p) for p in sorted((out/'pools').glob('*/CHECKS.json'))]
    assert len(checks)==registration['pools'] and all(r['complete'] for r in checks)
    count=collections.Counter()
    for r in checks:
        assert r['total']==r['requested'] and r['scalar_verification']['gzip_read_to_eof']
        count.update(r['acquisition_counts'])
    pilot=read_json(out/'TIMED_FIRST_WAVE.json');pilot_count=collections.Counter()
    for r in pilot['by_pool']:pilot_count.update(r['acquisition_counts'])
    # Per-pool acquisition counts describe only that execution pass. The two
    # existing full endpoints saved before the ENOSPC attempt were resumed by
    # the timed wave, and all timed-wave endpoints were resumed by the full pass.
    initially_resumed=sum(r['resumed'] for r in pilot['by_pool'])
    combined=count+pilot_count+collections.Counter({'reused_full':initially_resumed})
    assert dict(combined)==registration['acquisition_counts']
    assert sum(r['total'] for r in checks)==registration['unique_requests']
    assert sha(registration['requests_file'])==registration['requests_sha256']
    assert (out/'ENDPOINT_SCALARS.csv.gz').exists()
    progress=read_json(out/'PROGRESS.json')
    receipt={'requested_unique_teams':registration['unique_requests'],'endpoint_rows':sum(r['total'] for r in checks),
      'pools':len(checks),'acquisition_counts':dict(combined),'truly_new_physical_teams':combined['new_physical_team'],
      'old_entity_geometry_replays':combined['geometry_replay_existing_team'],'full_endpoint_reused':combined['reused_full'],
      'native_endpoint_evaluations_core_total':combined['new_physical_team']+combined['geometry_replay_existing_team'],
      'native_evaluations_this_run':count['new_physical_team']+count['geometry_replay_existing_team'],
      'current_pass_acquisition_counts':dict(count),'timed_wave_acquisition_counts':dict(pilot_count),
      'full_endpoints_resumed_into_timed_wave':initially_resumed,
      'resumed_endpoints':sum(r['resumed'] for r in checks),'all_complete':True,
      'core_endpoint_phase_seconds':progress['seconds'],'engine_digest':contract['engine_digest'],
      'current_repository_commit':contract['current_repository_commit'],'no_label_or_reference_changes':True,
      'Q_missing_never_imputed':True,'full_geometry_and_failure_states_preserved':True,
      'geometry_storage':'Authoritative complete pools/<pool_id>/part_*.jsonl.gz shards; no consolidated geometry file is required.',
      'consolidated_geometry_completed':False,
      'receipt_finalization':'Generated from all completed pool CHECKS after optional geometry consolidation was intentionally interrupted for disk-space protection.',
      'consolidation_stop_receipt':str(Path(a.stop_receipt).resolve()),'consolidation_stop_receipt_sha256':sha(a.stop_receipt),
      'original_engine_final_receipt_not_written_because_interrupt_occurred_before_that_line':True,
      'new_fusions_or_scores_by_finalization':0,
      'followup_verification':'finalize_execution_accounting.py independently reads the complete scalar index and revalidates all old-scalar replay outcomes.'}
    write_json(target,receipt);print(json.dumps(receipt),flush=True)

if __name__=='__main__':main()
