import pandas as pd
from tools.thesis_main.analysis.same_room_local_features_20261021 import local_assign,history_prediction,prediction_tables


def test_seam_and_one_observation_cannot_fill_two_features():
    ref=[[1,180],[1,330],[5,180],[5,330],[512,180],[512,330]]
    points=[[1023,180],[1023,330]]
    m=local_assign(points,ref,3)
    assert len(m)==1 and 0 in m and m[0]["dx"]==-2


def test_local_history_excludes_target_and_other_person_baseline_excludes_self():
    d=pd.DataFrame([["W1","a",1],["W1","b",0],["W2","a",0],["W2","b",1]],
                   columns=["worker_id","image_code","hit"])
    assert history_prediction(d,"W1","b")== (1.,0.,1)
    d.loc[d.image_code.eq("b"),"hit"]=99
    assert history_prediction(d,"W1","b")== (1.,0.,1)


def test_fixed_baselines_keep_targets_and_equal_weight_images():
    d=pd.DataFrame(dict(room="R",tolerance_deg=3,method="others_same_source_views",
        feature="f",image=["a","a","b"],object_id=["1","2","3"],
        y=[0,1,1],probability=[0.,0.,1.],brier=[0.,1.,0.],absolute_error=[0.,1.,0.]))
    pred,summary=prediction_tables(d)
    constant=pred[pred.method.eq("constant_half")]
    shrunk=pred[pred.method.eq("others_half_shrunk")]
    assert constant.object_id.tolist()==d.object_id.tolist()
    assert constant.brier.eq(.25).all()
    assert shrunk.probability.tolist()==[.25,.25,.75]
    assert summary.set_index("method").loc["others_half_shrunk","brier"]==.1875
    again,_=prediction_tables(pred)
    assert len(again)==len(pred)
