import csv

from tools.thesis_main.analysis.materialize_c1_rehearsal_audits import materialize_row_analysis_eligibility


def _write(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer=csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def test_gt_pending_does_not_close_peer_or_structural(tmp_path):
    canonical=tmp_path/"canonical.csv"; versions=tmp_path/"versions.csv"; quality=tmp_path/"quality.csv"; loo=tmp_path/"loo.csv"; structural=tmp_path/"struct.csv"; reference=tmp_path/"ref.csv"; independence=tmp_path/"ind.csv"
    _write(canonical,[{"canonical_annotation_id":"c","annotation_id":"a","worker_id":"w","base_task_id":"b","project_id":"p","ls_runtime_task_id":"l","task_id":"t","condition":"manual","assignment_provenance":"original_assignment","assigned_expected":True,"outside_assignment_submission":False,"duplicate_worker_task_submission":False}])
    _write(versions,[{"annotation_id":"a","version_disposition":"selected_canonical"}]); _write(quality,[{"canonical_annotation_id":"c","quality_evaluable":False}])
    _write(loo,[{"canonical_annotation_id":"c","peer_count_excluding_self":2,"q_LOO_tu":.8,"primary_loo_eligible":False,"worker_excluded_unique_dominant_cluster":True,"task_crowd_structure_status":"unimodal","medoid_tie_sensitive":False}])
    _write(structural,[{"canonical_annotation_id":"c","structural_validation_status":"passed"}]); _write(reference,[{"project_id":"p","ls_runtime_task_id":"l","task_id":"t","base_task_id":"b","condition":"manual","final_scope":"in_scope","geometry_reference_ready":False}]); _write(independence,[{"canonical_annotation_id":"c","independence_status":"independent"}])
    result=materialize_row_analysis_eligibility(canonical,versions,quality,loo,structural,reference,tmp_path,independence_csv=independence)
    assert result["gt_primary_analysis_eligible"] == 0
    assert result["peer_analysis_eligible"] == 1
    assert result["structural_opportunity_eligible"] == 1


def test_manual_validator_false_positive_retains_structural_denominator(tmp_path):
    canonical=tmp_path/"canonical.csv"; versions=tmp_path/"versions.csv"; quality=tmp_path/"quality.csv"; loo=tmp_path/"loo.csv"; structural=tmp_path/"struct.csv"; reference=tmp_path/"ref.csv"; independence=tmp_path/"ind.csv"
    _write(canonical,[{"canonical_annotation_id":"c","annotation_id":"a","worker_id":"w","base_task_id":"b","project_id":"p","ls_runtime_task_id":"l","task_id":"t","condition":"manual","assignment_provenance":"original_assignment","assigned_expected":True,"outside_assignment_submission":False,"duplicate_worker_task_submission":False}])
    _write(versions,[{"annotation_id":"a","version_disposition":"selected_canonical"}]); _write(quality,[{"canonical_annotation_id":"c","quality_evaluable":False}])
    _write(loo,[{"canonical_annotation_id":"c","peer_count_excluding_self":0,"primary_loo_eligible":False}])
    _write(structural,[{"canonical_annotation_id":"c","structural_validation_status":"not_evaluable","structural_denominator_eligible":True,"worker_failure_numerator":False,"final_scope":"in_scope"}])
    _write(reference,[{"project_id":"p","ls_runtime_task_id":"l","task_id":"t","base_task_id":"b","condition":"manual","final_scope":"in_scope","geometry_reference_ready":False}]); _write(independence,[{"canonical_annotation_id":"c","independence_status":"independent"}])

    materialize_row_analysis_eligibility(canonical,versions,quality,loo,structural,reference,tmp_path,independence_csv=independence)
    row=next(csv.DictReader((tmp_path/"c1_row_analysis_eligibility.csv").open(encoding="utf-8")))

    assert row["structural_attribution_eligible"] == "True"
    assert row["structural_opportunity_eligible"] == "True"


def test_c1_repaired_geometry_is_usable_for_qgt_and_loo_without_erasing_fstruct(tmp_path):
    canonical=tmp_path/"canonical.csv"; versions=tmp_path/"versions.csv"; quality=tmp_path/"quality.csv"; loo=tmp_path/"loo.csv"; structural=tmp_path/"struct.csv"; reference=tmp_path/"ref.csv"; independence=tmp_path/"ind.csv"
    _write(canonical,[{"canonical_annotation_id":"c","annotation_id":"a","worker_id":"w","base_task_id":"b","project_id":"p","ls_runtime_task_id":"l","task_id":"t","condition":"manual","assignment_provenance":"original_assignment","assigned_expected":True,"outside_assignment_submission":False,"duplicate_worker_task_submission":False}])
    _write(versions,[{"annotation_id":"a","version_disposition":"selected_canonical"}])
    _write(quality,[{"canonical_annotation_id":"c","quality_evaluable":True,"gt_score_computable":True}])
    _write(loo,[{"canonical_annotation_id":"c","peer_count_excluding_self":4,"q_LOO_tu":.8,"q_LOO_primary":.8,"primary_loo_eligible":True,"worker_excluded_unique_dominant_cluster":True,"task_crowd_structure_status":"unimodal","medoid_tie_sensitive":False}])
    _write(structural,[{"canonical_annotation_id":"c","structural_validation_status":"failed_confirmed_worker_submission","geometry_calculation_eligible":True,"worker_failure_numerator":True}])
    _write(reference,[{"project_id":"p","ls_runtime_task_id":"l","task_id":"t","base_task_id":"b","condition":"manual","final_scope":"in_scope","geometry_reference_ready":True}])
    _write(independence,[{"canonical_annotation_id":"c","independence_status":"independent"}])

    materialize_row_analysis_eligibility(canonical,versions,quality,loo,structural,reference,tmp_path,independence_csv=independence)
    row=next(csv.DictReader((tmp_path/"c1_row_analysis_eligibility.csv").open(encoding="utf-8")))

    assert row["gt_primary_analysis_eligible"] == "True"
    assert row["loo_medoid_analysis_eligible"] == "True"
    assert row["strict_loo_analysis_eligible"] == "True"
    assert row["structural_opportunity_eligible"] == "True"
