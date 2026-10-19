#!/usr/bin/env python3
"""Check replay wiring and copied-input closure without running scientific steps."""
from __future__ import annotations
import argparse, ast, importlib.util, json, subprocess, sys, tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('partA_replay_entry',HERE/'reproduce.py')
entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)

LATE_INPUTS={
 'event_design_opportunity_tables':['events/event_design.csv.gz'],
 'reverse_exchange_summaries':[
  'reverse/results/all_candidate_classes.csv.gz',
  'forward/fold_features.csv.gz',
  'reverse/results/worker_classmate_stability.csv',
  'reverse/results/selected_candidates.csv',
  'reverse/results/coassignment_stability.csv.gz',
  'forward/FEATURE_DOMAINS.json',
  'reverse/explanations/rules.txt'],
 'paired_policies_practical_coverage_origin_diagnostic':[
  'assessment/COMMON_EVENT_ANALYSIS_INPUT.csv.gz',
  'assessment/ALL_SELECTED_AND_BASELINE_LABELS.csv.gz',
  'assessment/EVENT_PREDICTIONS_WIDE.csv.gz',
  'assessment/LAST_SEAT_CHOICES.csv.gz',
  'assessment/MATCHED_BACKGROUND_PER_IMAGE.csv.gz'],
 'combined_portraits_four_node_and_ablation_tables':[
  'assessment/COMMON_EVENT_ANALYSIS_INPUT.csv.gz',
  'assessment/EVENT_PREDICTIONS_WIDE.csv.gz',
  'assessment/NESTED_FOUR_NODE_CHAINS.csv.gz',
  'forward/full_selected_worker_portraits.csv.gz',
  'recovered/work_v2_20261019/profiles/full_profiles.csv',
  'assessment/ALL_SELECTED_AND_BASELINE_LABELS.csv.gz',
  'reverse/results/worker_classmate_stability.csv',
  'events/native_runs/team_results.csv'],
}
PRODUCTS={
 'exact_native_events':['events/common_events.csv.gz','events/native_runs/team_results.csv'],
 'forward_features_B8L2':['forward/fold_features.csv.gz'],
 'forward_descriptive_summary':['forward/full_selected_worker_portraits.csv.gz'],
 'reverse_consolidation':['reverse/results/all_candidate_classes.csv.gz',
  'reverse/results/selected_candidates.csv','reverse/results/coassignment_stability.csv.gz'],
 'reverse_partition_stability':['reverse/results/worker_classmate_stability.csv'],
 'reverse_explanations':['reverse/explanations/rules.txt'],
 'common_recalibration_and_summary':[
  'assessment/COMMON_EVENT_ANALYSIS_INPUT.csv.gz',
  'assessment/ALL_SELECTED_AND_BASELINE_LABELS.csv.gz',
  'assessment/EVENT_PREDICTIONS_WIDE.csv.gz',
  'assessment/MATCHED_BACKGROUND_PER_IMAGE.csv.gz'],
 'class_and_last_seat_analysis':['assessment/LAST_SEAT_CHOICES.csv.gz'],
 'room_duplicate_four_node_sensitivity':['assessment/NESTED_FOUR_NODE_CHAINS.csv.gz'],
}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source-root',type=Path,default=HERE.parent)
    args=ap.parse_args();source=args.source_root.resolve()
    contract=entry.loadj(HERE/'EXCHANGE_FIELD_CONTRACT.json')
    checks={'created_utc':entry.now(),'scientific_steps_executed':0}
    help_run=subprocess.run([sys.executable,str(HERE/'reproduce.py'),'--help'],capture_output=True,text=True)
    checks['help_exits_zero']=help_run.returncode==0
    assert checks['help_exits_zero'],help_run.stderr
    result=entry.verify(source,contract,False)
    assert result['passed'],result['errors']
    checks['default_verification']={'passed':True,'key_sha_checks':len(result['key_inputs']),
      'table_header_checks':len(result['schemas']),'runtime_matches':result['runtime']['all_pins_match']}
    checks['python_syntax_checked']=[]
    acquired=['download_main_inputs.py','recover_bootstrap_inputs.py','audit_inputs_A.py',
              'main_personnel_A_20261019','frozen_source_82c6164b']
    acquisition_references=[]
    code_files=[]
    for folder in ['events','reverse','assessment','forward','reproducibility']:
        for p in sorted((source/folder).glob('*.py')):
            code=p.read_text(encoding='utf8');ast.parse(code,filename=str(p))
            rel=str(p.relative_to(source));checks['python_syntax_checked'].append(rel);code_files.append(rel)
            if folder!='reproducibility':
                for token in acquired:
                    if token in code:acquisition_references.append({'script':rel,'reference':token})
    assert not acquisition_references,acquisition_references
    checks['acquisition_dependency_scan']={'top_level_scientific_scripts_scanned':len(code_files)-len(list((source/'reproducibility').glob('*.py'))),
      'references_to_one_time_restore_download_paths':acquisition_references,
      'scope':'Static scan of current events/forward/reverse/assessment top-level Python; restored native siblings are copied intact.'}
    configs=[folder+'/'+name for folder,names in entry.CONFIG_FILES.items()for name in names]
    folds=entry.loadj(source/'reverse/FROZEN_BUILDING_SPLITS.json')['folds']
    reverse_classes=['reverse/results/folds/'+fold+'/classes.csv.gz'for fold in folds]
    minimum={'schema_version':1,'root_directory_name':entry.LEAF,'all_three_ZIPs':'Unpack each ZIP into the same parent and merge this one root prefix.',
      'restored_subtrees_required_intact':['recovered/work_v2_20261019','recovered/repo_main_20261019'],
      'restored_receipt_required':'recovered/BOOTSTRAP_RECEIPT.json',
      'code_copy_rule':'All top-level *.py and *.md in events/forward/reverse/assessment/reproducibility; reproducibility/*.json is also copied.',
      'code_files_observed':code_files,'configuration_files_required':configs,
      'optional_runtime_directory':'deps; otherwise install pinned requirements in the active Python environment',
      'one_time_acquisition_scripts_not_required':acquired,
      'not_required_for_numerical_replay':['external main checkout','duplicate frozen_source tree','original panorama images','viewer assets','omitted Part A native pool states','omitted Part A candidate prediction caches'],
      'levels':{},'late_stage_inputs':LATE_INPUTS,'late_stage_input_producers':PRODUCTS,
      'limitations':'Static wiring and retained input checks; not a new end-to-end numerical replay or independent collection audit.'}
    for level,expected in [('aggregate',8),('refit',24),('fresh',26)]:
        recipe=entry.plan(level,source,1);assert len(recipe)==expected
        ready=entry.readiness(source,level);assert ready['files_ready'],ready
        extra=list(entry.REUSED_EVENT_FILES)if level!='fresh'else[]
        if level=='aggregate':extra+=entry.AGGREGATE_FILES+reverse_classes
        available={p:'copied retained input'for p in extra+configs}
        available['recovered/work_v2_20261019/profiles/full_profiles.csv']='copied restored native core'
        traces=[]
        for step in recipe:
            name=step['step']
            for rel in LATE_INPUTS.get(name,[]):
                assert rel in available,(level,name,'missing copied input or earlier producer',rel)
                if available[rel].startswith('copied'):assert (source/rel).is_file(),rel
                traces.append({'step':name,'input':rel,'available_from':available[rel]})
            for rel in PRODUCTS.get(name,[]):available[rel]='earlier step: '+name
        checks[level+'_plan_only']={'steps':len(recipe),'files_ready':True,'no_execution':True,
          'late_stage_dependency_closure':traces}
        minimum['levels'][level]={'explicit_execution_steps':len(recipe),'additional_copied_result_inputs':extra,
          'copies_existing_native_states':False,'copies_existing_native_team_result_table':level!='fresh',
          'includes_final_diagnostics_and_report_tables':True,
          'commands':[{'step':s['step'],'script':str(Path(s['command'][1]).relative_to(source)),
                       'arguments':[str(a).replace(str(source),'<WORK_ROOT>')for a in s['command'][2:]]}for s in recipe]}
    guard_parent=Path(tempfile.mkdtemp(prefix='partA-replay-entry-guard-'))
    guard=guard_parent/entry.LEAF;guard.mkdir();sentinel=guard/'sentinel.txt';sentinel.write_text('preserve existing directory\n')
    before=sentinel.read_bytes()
    try:entry.prepare(source,guard,'aggregate',contract)
    except FileExistsError:refused=True
    else:refused=False
    assert refused and sentinel.read_bytes()==before and sorted(p.name for p in guard.iterdir())==['sentinel.txt']
    checks['existing_workspace_guard']={'refused':True,'preserved_all_files':True,'scientific_steps_executed':0,
      'preserved_test_directory':str(guard),'automatic_deletion_performed':False}
    checks['three_expensive_replay_levels_executed_for_this_wrapper_smoke']=False
    checks['final_diagnostics_source_sha256']=entry.sha(source/'assessment/final_diagnostics.py')
    checks['report_tables_source_sha256']=entry.sha(source/'assessment/report_tables.py')
    checks['entry_source_sha256']=entry.sha(HERE/'reproduce.py')
    checks['entry_contract_sha256']=entry.sha(HERE/'EXCHANGE_FIELD_CONTRACT.json')
    entry.savej(HERE/'MINIMUM_LAYOUT.json',minimum)
    entry.savej(HERE/'ENTRY_POINT_CHECKS.json',checks)
    print(json.dumps({'status':'PASS','levels':{k:checks[k+'_plan_only']['steps']for k in minimum['levels']},
      'late_stage_dependency_inputs_checked_per_level':{level:len(checks[level+'_plan_only']['late_stage_dependency_closure'])for level in minimum['levels']},
      'scientific_steps_executed':0,'written':['MINIMUM_LAYOUT.json','ENTRY_POINT_CHECKS.json']},indent=2))

if __name__=='__main__':main()
