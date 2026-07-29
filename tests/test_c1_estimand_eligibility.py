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
    assert result["global_analysis_eligible"] == 0
    assert result["peer_analysis_eligible"] == 1
    assert result["structural_opportunity_eligible"] == 1
