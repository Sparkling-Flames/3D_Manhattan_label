import numpy as np
import ast
from pathlib import Path

from tools.thesis_main.analysis.fusion_common_panel_20261024 import medoid
from tools.thesis_main.analysis.quality_independent_validation_20261024 import evaluate_geometry, geometry_to_cor, join_human_answers


def room(offset=0.0, heights=None):
    floor=np.array([[-2.,-1.,-2.],[2.,-1.,-2.],[2.,-1.,2.],[-2.,-1.,2.]])
    floor[:,0]+=offset
    top=floor.copy()
    top[:,1]=1.6 if heights is None else heights
    return dict(bottom3d=floor.tolist(),top3d=top.tolist())


def record(name,offset):
    return dict(id=name,object_id=name,worker=name,worker_id=name,
                points=(geometry_to_cor(room(offset))+.5).tolist())


def test_medoid_uses_pairwise_geometry_and_deterministic_ties():
    selected,_,excluded,_=medoid([record("left",-.5),record("middle",0),record("right",.5),
                                dict(id="bad",object_id="bad",worker="bad",worker_id="bad",points=None)])
    assert selected["object_id"]=="middle"
    assert excluded[0]["object_id"]=="bad"
    selected,_,_,_=medoid([record("z",0),record("a",0)])
    assert selected["object_id"]=="a"


def test_legacy_depth_preserves_local_height_response():
    reference=room()
    perfect=evaluate_geometry(reference,reference)
    tilted=evaluate_geometry(room(heights=[1.08,2.12,2.12,1.08]),reference)
    assert perfect["layout_depth_rmse_m"]==0
    assert perfect["layout_depth_delta1"]==1
    assert abs(tilted["legacy_iou3d_mean_height"]-1)<1e-6
    assert tilted["layout_depth_rmse_m"]>.4
    assert tilted["layout_depth_delta1"]<.9


def test_boundary_matches_local_official_source_and_invalid_is_not_zero():
    from lib.misc import panostretch
    from tools.thesis_main.analysis.quality_core.geometry_metrics import _boundary_from_cor_id_connect
    source=Path(__file__).resolve().parents[1]/"lib/dataset/dataset_layout.py"
    tree=ast.parse(source.read_text(encoding="utf-8"))
    functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ("cor_2_1d","sort_xy_filter_unique")]
    namespace={"np":np,"panostretch":panostretch}
    exec(compile(ast.Module(body=functions,type_ignores=[]),str(source),"exec"),namespace)
    corners=geometry_to_cor(room(heights=[1.08,2.12,2.12,1.08]))
    top,bottom=_boundary_from_cor_id_connect(corners,1024,512)
    local=((np.stack((top,bottom))+.5)/512-.5)*np.pi
    np.testing.assert_allclose(local,namespace["cor_2_1d"](corners,512,1024),atol=2e-6)
    invalid=room();invalid["bottom3d"][0][1]=-2
    assert evaluate_geometry(invalid,room())["legacy_status"].startswith("requires_")


def test_human_mapping_keeps_comments_uncertainty_and_metric_direction():
    import pandas as pd
    import pytest
    mapping=[];rows=[];answers={}
    for key,choice in (("Q1","right"),("Q2","close"),("Q3","uncertain")):
        mapping.append(dict(review_id=key,left_object_id=key+"B",right_object_id=key+"A",
                            image=key,reference_id="ref",exposure_group="new",building="b"))
        answers[key]=dict(choice=choice,reason=" 都有问题，可能左边略好 ")
        for obj,value in ((key+"A",1.),(key+"B",2.)):
            row=dict(review_id=key,object_id=obj,image=key,reference_id="ref",condition="manual")
            row.update({metric:value for metric in ("B8L2","D10","IoU3D100","iou_2d",
                "legacy_iou3d_mean_height","layout_depth_rmse_m","layout_depth_delta1",
                "S_bottom_deg","dir","Hmean","Hcenter")})
            rows.append(row)
    payload=dict(schema="quality_independent_human_answers_20261024_v1",
                 review_set="hohonet_quality_review_20261024_v1",question_count=3,answered_count=3,answers=answers)
    frame=join_human_answers(payload,mapping,pd.DataFrame(rows))
    assert frame.iloc[0].left_object_id=="Q1B" and not frame.iloc[0].agrees_human_B8L2
    assert frame.iloc[0].agrees_human_layout_depth_rmse_m
    assert frame.iloc[2].human_choice=="uncertain" and not frame.iloc[2].directional_human_answer
    assert frame.iloc[2].human_comment==" 都有问题，可能左边略好 "
    assert frame.iloc[1].agrees_human_B8L2 is None and frame.iloc[2].agrees_human_B8L2 is None
    partial={**payload,"answered_count":2,"answers":{k:v for k,v in answers.items() if k!="Q3"}}
    incomplete=join_human_answers(partial,mapping,pd.DataFrame(rows))
    assert len(incomplete)==3 and incomplete.iloc[2].human_choice is None
    assert not incomplete.iloc[2].directional_human_answer and incomplete.iloc[2].human_comment==""
    rows[0]["reference_id"]="wrong"
    with pytest.raises(ValueError,match="reference mismatch"):
        join_human_answers(payload,mapping,pd.DataFrame(rows))


def test_composition_eta2_constant_scores_are_undefined():
    from tools.thesis_main.analysis.personnel_d10_response_summary_20261024 import composition_eta2
    assert np.isnan(composition_eta2(0., 0., [924]))
    assert np.isnan(composition_eta2(2e-25, 0., [924]))
    assert composition_eta2(30., 70., [3, 7]) == .3
    assert composition_eta2(0., 70., [3, 7]) == 0.
    assert composition_eta2(30., 0., [3, 7]) == 1.
