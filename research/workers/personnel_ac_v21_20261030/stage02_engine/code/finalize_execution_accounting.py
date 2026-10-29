"""Clarify endpoint execution counts without replacing the native run receipt."""
from __future__ import annotations
import argparse,collections,csv,gzip,json
from pathlib import Path
from ac_endpoint_runtime import read_json,write_json,write_csv,sha,iter_jsonl,replay_difference,finite

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--plan',required=True);ap.add_argument('--endpoints',required=True)
    ap.add_argument('--out',required=True);a=ap.parse_args();plan=Path(a.plan);end=Path(a.endpoints);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    registration=read_json(plan/'CACHE_PLAN.json');run=read_json(end/'RUN_RECEIPT.json');pilot=read_json(end/'TIMED_FIRST_WAVE.json')
    assert run['all_complete'];assert run['endpoint_rows']==registration['unique_requests']
    assert run['acquisition_counts']==registration['acquisition_counts']
    checks=[read_json(p) for p in sorted((end/'pools').glob('*/CHECKS.json'))]
    assert len(checks)==run['pools'] and all(x['complete'] for x in checks)
    assert sum(x['total'] for x in checks)==run['endpoint_rows']
    baseline={r['team_key']:r for r in iter_jsonl(plan/'EXISTING_SCALAR_REPLAY_BASELINE.jsonl.gz')}
    csv_parity=[];counts=collections.Counter();statuses=collections.Counter();seen=set();missing=0
    with gzip.open(end/'ENDPOINT_SCALARS.csv.gz','rt',encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        for row in reader:
            assert None not in row and all(v is not None for v in row.values());key=row['team_key'];assert key not in seen;seen.add(key)
            counts[row['endpoint_acquisition']]+=1;statuses[row['score_status']]+=1;missing+=not row['B8L2']
            if key in baseline:
                prior=baseline[key];check=replay_difference(prior,row)
                check.update(prior_score_status=prior.get('score_status'),current_score_status=row.get('score_status'),
                  status_compared=prior.get('score_status') not in (None,''),
                  prior_Q_available=finite(prior.get('B8L2')),current_Q_available=finite(row.get('B8L2')),
                  source_cache=prior.get('cache_source'))
                csv_parity.append(check)
    assert len(seen)==run['endpoint_rows'] and dict(counts)==run['acquisition_counts']
    replay=[]
    for p in sorted((end/'pools').glob('*/REPLAY_PARITY.json')):
        obj=read_json(p);assert obj['all_passed'];replay+=obj['checks']
    assert len(replay)==counts['geometry_replay_existing_team']
    assert len(csv_parity)==len(baseline)==len(replay)
    assert {r['team_key'] for r in replay}==set(baseline)
    full_study_native=counts['new_physical_team']+counts['geometry_replay_existing_team']
    pilot_native=pilot['native_evaluations'];continued_native=full_study_native-pilot_native
    assert run['resumed_endpoints']==pilot['pilot_teams']
    receipt={
      'frozen_requested_unique_teams':len(seen),'full_existing_endpoint_reuse':counts['reused_full'],
      'new_physical_teams':counts['new_physical_team'],'old_physical_entities_replayed_for_geometry':counts['geometry_replay_existing_team'],
      'native_endpoint_evaluations_in_core_endpoint_run':full_study_native,
      'native_endpoint_evaluations_in_first_timed_wave':pilot_native,
      'native_endpoint_evaluations_in_continued_full_pass':continued_native,
      'resumed_endpoints_in_continued_pass':run['resumed_endpoints'],
      'resumed_endpoints_are_not_fused_or_scored_again':True,
      'original_receipt_field_native_evaluations_this_run_means':'Native evaluations newly performed in the continued full pass; per-pool acquisition counts exclude previously saved resumed endpoints.',
      'provisional_interpretation_correction':'An earlier provisional concern that this field would include the first wave was rejected by inspecting the actual per-pool counts. Seven fully resumed pilot pools have empty current-pass acquisition counts. There is no counting defect in that native receipt formula.',
      'native_count_scope':'Core registered endpoint execution only. Excludes later case full_state replay, mechanism or QA reproduction, and separate minimal-input reproduction. Those evaluate already existing physical teams and add no new team samples.',
      'original_run_receipt_sha256':sha(end/'RUN_RECEIPT.json'),
      'original_timed_wave_receipt_sha256':sha(end/'TIMED_FIRST_WAVE.json'),
      'old_entity_replay_parity_checks':len(replay),
      'max_replay_numeric_difference':max((x['maximum_difference'] for x in replay),default=0),
      'max_saved_scalar_revalidation_difference':max((x['maximum_difference'] for x in csv_parity),default=0),
      'old_entity_replay_state_and_Q_availability_exceptions':[],
      'old_entity_replay_status_compared_n':sum(x['status_compared'] for x in csv_parity),
      'old_entity_replay_prior_missing_Q_n':sum(not x['prior_Q_available'] for x in csv_parity),
      'old_entity_replay_numeric_field_count_distribution':dict(collections.Counter(x['fields_compared'] for x in csv_parity)),
      'old_entity_replay_parity_definition':'All available pre-existing scalar fields listed in SCORE_PARITY_FIELDS compared within 1e-7; native score_status and Q availability preserved, and final exported scalar CSV independently revalidated. Missing pre-existing components are not imputed.',
      'score_status_counts':dict(statuses),'Q_missing_rows':missing,
      'scalar_file_read_to_gzip_EOF':True,'scalar_unique_identity_set_and_csv_width_verified':True,
      'trace_only_full_state_replays':'Case mechanism export receipts separately count later trace-only replays of existing endpoints; they create zero new physical teams.',
      'resource_incident':'The initial ENOSPC attempt failed before any native team evaluation; two existing full endpoints were preserved. It is not a fusion failure.',
      'original_receipts_unchanged':True}
    by_native={r['team_key']:r for r in replay}
    detail=[]
    for row in csv_parity:
        row=dict(row);row['max_native_replay_difference']=by_native[row['team_key']]['maximum_difference']
        row['differences_json']=json.dumps(row.pop('differences'),sort_keys=True,separators=(',',':'));detail.append(row)
    write_csv(out/'OLD_SCALAR_REPLAY_PARITY_FULL.csv.gz',detail)
    # Read through EOF after atomic gzip close; this is a compact audit table.
    with gzip.open(out/'OLD_SCALAR_REPLAY_PARITY_FULL.csv.gz','rt',encoding='utf-8-sig',newline='') as f:
        assert sum(1 for _ in csv.DictReader(f))==len(detail)
    write_json(out/'EXECUTION_ACCOUNTING_CLARIFICATION.json',receipt);print(json.dumps(receipt),flush=True)

if __name__=='__main__':main()
