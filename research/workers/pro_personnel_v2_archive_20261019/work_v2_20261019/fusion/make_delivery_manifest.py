"""Hash completed outputs and classify duplicate caches for transparent packaging."""
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from pool_io import OUT,ROOT,save,sha,read


def classification(path):
    rel=path.relative_to(OUT);parts=rel.parts
    if any(part.startswith('.') for part in parts):return 'transfer_or_runtime_temporary',False
    if path.name=='DELIVERY_FREEZE.log':return 'manifest_generation_log',False
    if '__pycache__' in parts or '.tmp.' in path.name or path.suffix=='.lock':return 'temporary',False
    if parts[0] in ('comparisons','comparisons_initial'):return 'duplicate_per_pool_comparisons',False
    if path.name.startswith('INITIAL_') and path.name.endswith('.csv.gz'):return 'duplicate_initial_panel',False
    if parts[0]=='pools':
        if path.name=='states.json.gz':return 'complete_native_geometry_and_node_evidence',True
        if path.name=='request_results.json.gz':return 'all_request_quality_failure_and_time',True
        if path.name=='requests.json.gz':return 'exact_ordered_real_members',True
        if path.name=='scores.json.gz':return 'optional_duplicate_score_cache',False
        if path.name=='team_results.csv':return 'duplicate_per_pool_csv',False
        return 'pool_context_and_execution',True
    if path.name=='team_results.csv':return 'convenience_global_request_table',True
    if path.suffix in ('.py','.txt'):return 'reproducible_code_or_environment',True
    if path.suffix=='.md':return 'chinese_readable_report',True
    return 'registration_results_or_execution_evidence',True


def main():
    run_names=['PILOT_RUN_d56f61f60d50.json','RUN_d56f61f60d50.json','RUN_d602fb93f53e.json']
    runs=[dict(receipt_file=name,receipt_sha256=sha(OUT/name),
        **{k:v for k,v in read(OUT/name).items() if k!='by_pool'}) for name in run_names]
    coverage=read(OUT/'CURRENT_COVERAGE.json');checks=read(OUT/'COMPARISON_INTEGRITY_CHECK_2.json')
    assert checks['all_passed'] and all(x['same_as_previous_process'] for x in checks['files'])
    assert sum(r['actual_new_fusions'] for r in runs)==coverage['unique_teams']
    assert sum(r['actual_new_request_rows'] for r in runs)==coverage['request_rows']
    save(OUT/'FINAL_RUN_RECEIPT.json',dict(
        receipt_kind='Aggregate of completed pilot, initial remainder and extension execution; not a new experiment.',
        git_commit='82c6164b0d4630de5316199c92aa405930973168',
        coverage=coverage,execution_runs=runs,
        execution_exceptions=sum(r['exceptions'] for r in runs),
        final_comparison_counts=read(OUT/'COMPARISON_COVERAGE.json'),
        output_status=read(OUT/'OUTPUT_STATUS_AUDIT.json'),
        engine_verification=read(OUT/'ENGINE_VERIFICATION.json'),
        integrity_evidence=[dict(file=name,sha256=sha(OUT/name)) for name in [
            'COMPARISON_INTEGRITY_CHECK_1.json','COMPARISON_INTEGRITY_CHECK_2.json',
            'FINAL_POLICY_INTEGRITY_RECOVERY.json','INITIAL_COMPARISON_INTEGRITY_RECOVERY.json']],
        all_five_comparison_files_verified_in_two_separate_processes=True,
        score_cache_redundancy_audit='SCORE_CACHE_REDUNDANCY_AUDIT.json',
        source_boundary='Exact processed input, frozen real teams and orders, and archived 12-team v1 comparison fixture. Not a reconstruction of original collection, raw exports, or image acquisition.',
        more_team_experiments_planned=False))
    rows=[];sizes=Counter()
    for path in sorted(OUT.rglob('*')):
        if not path.is_file() or path.name=='FUSION_DELIVERY_MANIFEST.json':continue
        if any(part.startswith('.') for part in path.relative_to(OUT).parts):continue
        role,include=classification(path);size=path.stat().st_size;sizes[role]+=size
        row=dict(path=str(path.relative_to(ROOT)),bytes=size,role=role,recommended_include=include)
        if include:row['sha256']=sha(path)
        rows.append(row)
    save(OUT/'FUSION_DELIVERY_MANIFEST.json',dict(frozen_utc=datetime.now(timezone.utc).isoformat(),
        commit='82c6164b0d4630de5316199c92aa405930973168',coverage=coverage,
        final_comparison_counts=read(OUT/'COMPARISON_COVERAGE.json'),files=rows,bytes_by_role=dict(sizes),
        recommended_files=sum(r['recommended_include'] for r in rows),
        recommended_bytes=sum(r['bytes'] for r in rows if r['recommended_include']),
        score_cache_may_be_omitted='Every score key/value verified present in request_results across 144253 teams; see SCORE_CACHE_REDUNDANCY_AUDIT.json.',
        optional_global_csv='team_results.csv can be omitted if necessary; rebuild it without new fusion using fusion_engine.py --consolidate-only before analyses.',
        external_dependencies=['repo_main_20261019 immutable native source and measurement inputs listed in DESIGN.json',
            'work_v2_20261019/profiles/room_weighting.py and declared_room_groups.csv',
            'profiles/fold_profiles.csv and dtype registration only if redefining requests, not needed for frozen-request replay',
            'audit/fold_behavior_profiles.csv and behavior registration only if redefining requests, not needed for frozen-request replay'],
        source_boundary='Frozen processed evidence and archived 12-team v1 comparison fixture are replayable. This is not a claim of regenerating complete original data collection.',
        no_more_team_experiments_after_freeze=True))
    print(dict(files=len(rows),recommended_files=sum(r['recommended_include'] for r in rows),
        recommended_bytes=sum(r['bytes'] for r in rows if r['recommended_include'])),flush=True)


if __name__=='__main__':main()
