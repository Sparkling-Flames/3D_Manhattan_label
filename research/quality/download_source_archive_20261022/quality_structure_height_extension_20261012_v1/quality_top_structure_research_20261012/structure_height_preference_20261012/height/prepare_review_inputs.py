#!/usr/bin/env python3
"""Prepare two auditable same-image height comparisons, with no invented labels."""
from pathlib import Path
import json
import hashlib
import shutil
import math
import numpy as np
from score_existing import dump, sha, gates

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / "previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010"
PAIRS = [
    {"question_id":"H01", "records":["R01033","R01022"],
     "why":"同图底面IoU、D和平均高度偏差较近，局部高度起伏不同；用于检查小幅局部变化是否可感，以及局部高度/F追加是否误罚。不是极窄尖峰。",
     "blind_question":"这两份标注的顶部位置和各处墙高，哪份更符合图片？请同时考虑是否能看出局部起伏。",
     "decision_effect":"若差异可感且有质量意义，支持保留小幅局部高度响应；若难分或更偏好另一份，先检查底点/遮挡和原始点误差，不能据此自动重设权重。"},
    {"question_id":"H02", "records":["R01973","R02447"],
     "why":"同图底面IoU、D接近，一份整体高度偏差稍大但更平，另一份平均高度较接近而局部起伏稍大；用于比较这两个维度的相对影响。误差较小，不冒充严重高度边界。",
     "blind_question":"这两份标注的顶部，哪份整体更合理？若问题类型不同而难以排序，可直接选择难以排序。",
     "decision_effect":"整体偏移较大但更平的作答若被偏好，支持在该幅度附近局部高低起伏权重不低于整体高度；若相反，则削弱该范围内过强局部处罚。若无法区分，保留参数区间，不制造唯一切点。"}
]


def verified_original(image, out):
    """Use the packaged, hash-verified image without requiring its historic path."""
    indexed_source = Path(image["local_path"])
    destination = out / "originals" / (image["image_code"] + indexed_source.suffix)
    destination.parent.mkdir(exist_ok=True)
    if destination.exists():
        # A present but damaged packaged image is an integrity error, not a reason
        # to silently substitute some other image from the originating workspace.
        assert destination.is_file() and sha(destination) == image["sha256"]
        return destination
    assert indexed_source.is_file(), (
        f"Original image missing from both packaged inputs and historic path: {destination}"
    )
    assert sha(indexed_source) == image["sha256"]
    shutil.copyfile(indexed_source, destination)
    assert sha(destination) == image["sha256"]
    return destination


def main():
    held, gate = gates()
    out = HERE / "inputs"
    out.mkdir(exist_ok=True)
    loader_file = BASE / "inputs/current_formal_loader_data.json"
    geometry_file = BASE / "inputs/current_geometry_compact.json"
    loader = {r["object_id"]:r for r in json.loads(loader_file.read_text())["objects"]}
    geometry = json.loads(geometry_file.read_text())["geometries"]
    metrics = {r["record_id"]:r for r in json.loads((HERE / "results/development907_candidates.json").read_text())}
    images = {r["image_id"]:r for r in json.loads((ROOT / "study_data/original_image_index.json").read_text())}
    selected, research = [], []
    for pair in PAIRS:
        case_rows = []
        for side, rid in zip(["A","B"], pair["records"]):
            assert rid not in held
            m = metrics[rid]
            assert m["applicability_confirmed"] is True
            source = loader[m["object_id"]]
            reference = loader[m["reference_object_id"]]
            a, g = geometry[m["object_id"]], geometry[m["reference_object_id"]]
            image = images[m["image_id"]]
            destination = verified_original(image, out)
            assert source["pairing_basis"] == "existing_verified"
            raw = np.asarray(source["before_preprocessing_points"], float)
            shared = np.asarray(source["preprocessed_points"], float)
            expected = raw.copy()
            deltas = []
            for top, bottom in source["links_zero_based"]:
                delta = ((raw[bottom,0]-raw[top,0]+512)%1024)-512
                assert abs(abs(delta)-512)>1e-10
                midpoint = (raw[top,0]+delta/2)%1024
                expected[top,0]=midpoint; expected[bottom,0]=midpoint
                deltas.append(delta*360/1024)
            assert np.max(np.abs(expected-shared))<1e-9
            # Full original layer and its declared order/pairing provenance stay intact.
            case_rows.append({"anonymous_id":pair["question_id"]+side,"record_id":rid,
                "image_code":m["image_code"],"source_object":source,"reference_object":reference,
                "frozen_geometry":a,"frozen_reference_geometry":g,
                "geometry_status":"unchanged frozen paired reconstruction, not an inferred new ring",
                "original_image_relative_path":str(destination.relative_to(HERE)),
                "original_image_sha256":image["sha256"],"original_resolution":[image["original_width"],image["original_height"]],
                "current_edited_equals_export":source["before_preprocessing_points"]==source["original_export_points"],
                "periodic_pair_residual_deg":deltas,"preprocessing_midpoint_check":"pass",
                "human_answer":None,"human_status":"unreviewed_for_this_question; old-image exposure is retained",
                "formal_qualification_unchanged":True})
        assert case_rows[0]["image_code"]==case_rows[1]["image_code"]
        selected.append({"question_id":pair["question_id"],"question":pair["blind_question"],
             "answer_options":["A更合理","B更合理","差不多","不确定／问题不同难以排序","参考或显示有问题"],
             "answer":None,"cases":case_rows})
        research.append({**pair,"cases":[{k:metrics[rid].get(k) for k in ["record_id","image_code","worker_id","condition","object_id","reference_object_id","iou_2d","iou_3d_corner_mean","dir","flat","Hmean","Hcenter","Q_v11","Q_official_iou3d","Q_hsplit_top0","Q_dbounded1_hsplit","Q_dbounded2_hsplit","Q_dbounded1_hsplit_logMean"]} for rid in pair["records"]],
            "selection_is_development_not_validation":True,
            "not_pure_single_variable_real_data":True})
    dump(out / "height_review_full_inputs.json", {"pairs":selected,"gates":gate,
         "input_sha256":{"formal_loader":sha(loader_file),"frozen_geometry":sha(geometry_file)},
         "raw_original_receipts_changed":False,"scores_are_absent_from_blind_questions":True})
    dump(out / "height_review_research_selection.json",research)
    dump(out / "height_review_blind_questions.json",[{k:pair[k] for k in ["question_id","question","answer_options","answer"]} for pair in selected])
    print(json.dumps({"pairs":len(selected),"records":sum(len(p["cases"]) for p in selected),
                      "original_images":len(list((out/"originals").glob("*"))),"all_midpoint_checks":"pass"}))


if __name__ == "__main__":
    main()
