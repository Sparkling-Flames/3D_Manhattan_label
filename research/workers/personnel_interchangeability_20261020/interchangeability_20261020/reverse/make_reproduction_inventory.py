#!/usr/bin/env python3
"""Small selected-fold evidence and an explicit lean reverse-route inventory."""
import gzip
import hashlib
import json
from pathlib import Path
import pandas as pd

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
ROOT=BASE.parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_json(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def entry(p,role):
    p=ROOT/p
    assert p.exists(),p
    return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p),role=role)

def main():
    selected=[]
    for name,short in [('legacy_fit','LEGACY_SCREEN_SHORTLIST.json'),('mixed_fit','MIXED_SCREEN_SHORTLIST.json')]:
        x=json.load(open(HERE/short))
        # Shortlists are explicit method records, not a fresh outcome ranking.
        rows=x.get('methods',x.get('selected',x.get('shortlist',[]))) if isinstance(x,dict) else x
        if not rows:
            rows=[r for v in x.values() if isinstance(v,list) for r in v if isinstance(r,dict) and 'method_id' in r]
        mids={r['method_id'] for r in rows}
        assert mids,(short,list(x) if isinstance(x,dict) else type(x))
        f=pd.read_csv(HERE/name/'inner_cv_building.csv.gz');f=f[f.method_id.isin(mids)].copy();f.insert(0,'fit_version',name)
        assert set(f.method_id)==mids
        selected.append(f)
    f=pd.concat(selected,ignore_index=True)
    target=HERE/'review_tables/selected_inner_cv_building.csv.gz';raw=f.to_csv(index=False).encode();target.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(target.read_bytes())==raw
    keep=[]
    code=['learn_swap_types.py','extract_native_history.py','audit_explain_types.py','audit_inner_baselines.py','audit_inner_q_baselines.py','stress_nested_history.py','summarize_training_audits.py','make_reproduction_inventory.py','requirements_reverse.txt','README_REVERSE_ZH.md','REVERSE_REPRODUCTION_ZH.md']
    for p in code:keep.append(entry('interchangeability_20261020/reverse/'+p,'key_reverse_code_or_dependencies'))
    for p in ['LEGACY_SCREEN_SHORTLIST.json','MIXED_SCREEN_SHORTLIST.json','NATIVE_PAIR_EXTRACTION_RECEIPT.json',
        'review_tables/all_candidate_catalog.csv.gz','review_tables/REVERSE_SEARCH_LEDGER.csv','review_tables/METHOD_QUALIFICATIONS.json',
        'review_tables/selected_class_names_and_profiles_zh.csv','review_tables/selected_worker_explanations.csv.gz',
        'review_tables/selected_method_history_summary.csv','review_tables/selected_inner_cv_building.csv.gz']:
        keep.append(entry('interchangeability_20261020/reverse/'+p,'frozen_selection_or_search_evidence'))
    for fit in ['legacy_fit','mixed_fit']:
        for p in ['worker_labels.csv.gz','METHOD_MANIFEST.json','REGISTRATION.json','INPUT_AUDIT.json','RUN_RECEIPT.json','candidate_fold_ledger.csv.gz','candidate_cv_summary.csv']:
            keep.append(entry('interchangeability_20261020/reverse/'+fit+'/'+p,'exact_frozen_labels_and_all_candidate_support'))
    for folder in ['legacy_audit','mixed_audit']:
        for p in ['AUDIT_EXPLANATION_RECEIPT.json','class_explanations.csv.gz','lobo_label_stability.csv','opportunity_shrinkage_sensitivity.csv',
            'aggregate_relation_nontransitivity.csv','actual_nontransitivity_building.csv','actual_nontransitivity_examples.json']:
            q='interchangeability_20261020/reverse/'+folder+'/'+p
            if (ROOT/q).exists():keep.append(entry(q,'history_explanation_stability_and_nontransitivity'))
    for folder in ['legacy_baselines','mixed_baselines']:
        for p in ['BASELINE_RECEIPT.json','inner_baseline_summary.csv','inner_baseline_ledger.csv','inner_baseline_matched_anchor_draw.csv','inner_baseline_draw_summary.csv','fast_aggregation_parity.csv']:
            q='interchangeability_20261020/reverse/'+folder+'/'+p
            if (ROOT/q).exists():keep.append(entry(q,'source_capacity_baseline_small_evidence'))
    for p in ['REGISTRATION.json','Q_BASELINE_RECEIPT.json','paired_summary.csv','paired_draw_summary.csv','support_ledger.csv','eight_building_Q_features.csv.gz']:
        keep.append(entry('interchangeability_20261020/reverse/inner_q_baselines/'+p,'inner_fold_Q_control_small_evidence'))
    for p in ['NESTED_STRESS_RECEIPT.json','nested_stress_summary.csv','nested_stress_building.csv','nested_stress_support.csv','nested_same_pair_changed_background.csv']:
        keep.append(entry('interchangeability_20261020/reverse/nested_stress/'+p,'frozen_after_fit_history_pressure'))
    for p in ['analysis/composition/SPLIT.json','analysis/forward/results/features_train.csv.gz',
        'interchangeability_20261020/history_panel/HISTORY_PANEL_REGISTRATION.json',
        'interchangeability_20261020/history_panel/history_anchors.json.gz','interchangeability_20261020/history_panel/history_requests.json.gz',
        'interchangeability_20261020/assessment/ASSESSMENT_FREEZE.json','interchangeability_20261020/assessment/NESTED_NEW2_SPEC.json',
        'interchangeability_20261020/assessment/NESTED_NEW2_CAPACITY.json','interchangeability_20261020/assessment/NESTED_NEW2_DESIGN_RECEIPT.json',
        'interchangeability_20261020/assessment/w132_probe_requests.json.gz']:
        keep.append(entry(p,'shared_precise_design_or_history_input_small'))
    interp=HERE/'assessment_interpretation'
    for p in sorted(interp.glob('*.py')):keep.append(entry(str(p.relative_to(ROOT)),'assessment_summary_and_probe_reproduction_code'))
    # Exact small assessment summaries, all failures and whole-loop support.
    for p in ['ASSESSMENT_FINDINGS_ZH.md','NESTED_ANALYSIS_PLAN.json','FINAL_REVERSE_ASSESSMENT_SMALL.csv',
        'FINAL_REVERSE_CASE_SUGGESTIONS.json','EXPORT_S07_AND_COUNTER_SELECTION.json','FINAL_REVERSE_OUTPUT_AUDIT.json',
        'directions/direction_aggregate.csv.gz','directions/direction_per_true_image.csv.gz','directions/direction_per_building.csv.gz',
        'directions/DIRECTION_COVERAGE.csv','directions/ASSESSMENT_DIRECTION_RECEIPT.json','directions/PERSON_REMOVAL_DESCRIPTIVE.csv.gz','directions/R04_INCOMING_PAIR_COVERAGE.csv',
        'nested_new2/primary_n13_aggregate.csv.gz','nested_new2/primary_n13_per_true_image.csv.gz','nested_new2/primary_n13_per_building.csv.gz',
        'nested_new2/primary_by_difficulty_aggregate.csv.gz','nested_new2/curves_aggregate.csv.gz','nested_new2/METADATA_COHORTS.json',
        'nested_new2/PRIMARY_COVERAGE.csv','nested_new2/PRIMARY_EXACT_MEMBER_SUPPORT.csv','nested_new2/PRIMARY_UNION_SUPPORT.json',
        'nested_new2/NEW2_HISTORY_CLASS_FEATURES.csv','nested_new2/NEW2_HISTORY_WORKERS.csv.gz','nested_new2/NEW2_CLASS_MEMBERS.json',
        'nested_new2/HISTORY_EXPLANATION_AND_SUPPORT_RECEIPT.json','nested_new2/NESTED_ANALYSIS_RECEIPT.json','nested_new2/PERSON_REMOVAL_DESCRIPTIVE.csv.gz',
        'nested_new2/paired_m5_minus_m2_n13_per_true_image.csv.gz','nested_new2/paired_m5_minus_m2_n13_aggregate.csv.gz',
        'nested_new2/steps_by_support_increment_aggregate.csv.gz','nested_new2/CHINESE_CURVE_FIGURE_RECEIPT.json',
        'nested_new2/NEW2_C01_TO_C02_CURVES_ZH.png','nested_new2/NEW2_C01_TO_C02_CURVES_ZH.pdf',
        'nested_new2/NEW2_C02_TO_C01_CURVES_ZH.png','nested_new2/NEW2_C02_TO_C01_CURVES_ZH.pdf',
        'nested_new2/full_vectors/FULL_VECTOR_SMALL.csv','nested_new2/full_vectors/FULL_VECTOR_FINDINGS_ZH.md',
        'nested_new2/full_vectors/full_vector_aggregate.csv.gz','nested_new2/full_vectors/full_vector_per_true_image.csv.gz',
        'nested_new2/full_vectors/full_vector_per_building.csv.gz','nested_new2/full_vectors/exact_events_and_members.csv.gz',
        'nested_new2/full_vectors/FULL_VECTOR_RECEIPT.json',
        'w132_probe/REGISTER.json','w132_probe/DESIGN_RECEIPT.json','w132_probe/CAPACITY_AND_EXACT_LINKS.json',
        'w132_probe/CAPACITY_SUMMARY.csv','w132_probe/all_available_aggregate.csv.gz','w132_probe/by_W132_position_aggregate.csv.gz',
        'w132_probe/matched_parent_effects.csv.gz','w132_probe/exact_alternative_effects.csv.gz','w132_probe/PROBE_ANALYSIS_RECEIPT.json',
        'w132_probe/W132_MATCHED_MECHANISM_ZH.png','w132_probe/W132_MATCHED_MECHANISM_ZH.pdf','w132_probe/FIGURE_RECEIPT.json']:
        keep.append(entry('interchangeability_20261020/reverse/assessment_interpretation/'+p,'core_assessment_evidence_or_figure'))
    # Final curation removes only explicitly listed regenerable detail. The
    # parent assembler applies this policy to its additional directory globs.
    prune_path=HERE/'PRUNE_REBUILDABLE.json'
    pruning=json.load(open(prune_path)) if prune_path.exists() else {'prune':[],'rebuild_roles':{}}
    pruned_paths={item['path'] for item in pruning['prune']}
    removed_from_initial_keep=[item['path'] for item in keep if item['path'] in pruned_paths]
    keep=[item for item in keep if item['path'] not in pruned_paths]
    if prune_path.exists():keep.append(entry(str(prune_path.relative_to(ROOT)),'explicit_rebuildable_pruning_policy'))
    audit=json.load(open(HERE/'mixed_fit/INPUT_AUDIT.json'))
    recovery=dict(repository='Sparkling-Flames/3D_Manhattan_label',
        archive_commit_verified_in_this_workspace='e572eb73bedc4fe9056df838e458bab83c3fa423',
        latest_document_commit='445686f8f3cf6039c4ce1f60016cad1d26829044',scientific_source_commit='82c6164b0d4630de5316199c92aa405930973168',
        entry='research/workers/personnel_type_discovery_next_20261019/bootstrap.py',
        archive_map='research/workers/personnel_type_discovery_next_20261019/ARCHIVE_FILE_MAP.json',
        payload_bundles='research/workers/personnel_type_discovery_next_20261019/PAYLOAD_BUNDLES.json',
        previous_archive='research/workers/pro_personnel_v2_archive_20261019',
        output='restored/work_personnel_typing_A_20261019/',
        old_history_event_inputs=audit['loaded_pool_files'],
        metadata_inputs=[dict(path='restored/work_personnel_typing_A_20261019/events/DESIGN.json',sha256=audit['source_design_sha256']),
            dict(path='restored/work_personnel_typing_A_20261019/events/FIELD_CONTRACT.json',sha256=audit['source_field_contract_sha256']),
            dict(path='restored/work_personnel_typing_A_20261019/events/EVENT_VERIFICATION_RECEIPT.json',sha256=sha(ROOT/'restored/work_personnel_typing_A_20261019/events/EVENT_VERIFICATION_RECEIPT.json'))],
        note='The input archive is pinned to a verified commit and per-file SHAs; document main is reported separately. The code reads 79 historical per-pool event files, not the 95MB common_events duplicate. Full archive recovery is byte restoration, not a claim of newly redoing its science.')
    write_json(HERE/'REVERSE_RECOVERY_INPUTS.json',recovery)
    derived=[]
    for p,recipe in [('native_history_events.csv.gz','Rebuild history requests/anchors with design_history_panel.py; frozen fusion_runner for history_panel/native_runs; extract_native_history.py.'),
        ('mixed_fit/historical_pair_relations.csv.gz','learn_swap_types.py from the two historical actual-replacement event panels.'),
        ('legacy_fit/historical_pair_relations.csv.gz','learn_swap_types.py from the legacy actual-replacement event panel.'),
        ('mixed_fit/inner_cv_building.csv.gz','Re-run all candidates; selected 15-route fold rows are directly retained.'),
        ('legacy_fit/inner_cv_building.csv.gz','Re-run all candidates; selected 15-route fold rows are directly retained.'),
        ('inner_q_baselines/paired_building_draws.csv.gz','audit_inner_q_baselines.py; 8-building Q feature table, seeds, support and aggregate are retained.'),
        ('assessment_interpretation/nested_new2/nested_adjacent_steps.csv.gz','analyze_nested_new2.py from exact nested requests and final native metrics.'),
        ('assessment_interpretation/nested_new2/curves_per_true_image.csv.gz','analyze_nested_new2.py; aggregate curves and primary per-image evidence retained.')]:
        derived.append(entry('interchangeability_20261020/reverse/'+p,'rebuildable_not_required_in_lean_zip')|dict(recipe=recipe))
    for item in pruning['prune']:
        role=pruning['rebuild_roles'][item['role_id']]
        derived.append({k:item[k] for k in ['path','bytes','sha256']} | dict(
            role='rebuildable_detail_removed_by_final_curation',recipe=role['rebuild_recipe_zh']))
    write_json(HERE/'REVERSE_MINIMAL_REPRODUCTION.json',dict(
        selected_inner_cv_rows=len(f),suggested_retained_files=keep,total_retained_bytes_before_zip=sum(x['bytes'] for x in keep),
        upstream_input_recovery='interchangeability_20261020/reverse/REVERSE_RECOVERY_INPUTS.json',rebuildable_large=derived,
        final_pruning_policy=str(prune_path.relative_to(ROOT)) if prune_path.exists() else None,
        removed_from_initial_keep=removed_from_initial_keep,
        parent_additional_globs_must_exclude=sorted(pruned_paths),
        omit_directories=['reverse/native_pair_chunks','history_panel/native_runs','assessment/native_nested_new2','assessment/native_w132_probe','all Python bytecode/logs/virtual environments'],
        note='This inventory is an explicit suggestion for the parent package; shared inputs/code must be included once, not duplicated. Exact frozen labels are used to replay main conclusions; refitting is a separate level. Include final selected-case embedded geometry from parent exporter. Apply the final pruning policy to additional assembler globs as well; no physical files are deleted by this inventory generator.'))
    print(json.dumps(dict(files=len(keep),bytes=sum(x['bytes'] for x in keep),selected_fold_rows=len(f))))


if __name__=='__main__':main()
