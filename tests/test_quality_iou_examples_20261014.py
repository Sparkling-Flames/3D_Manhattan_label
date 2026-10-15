import numpy as np
from tools.thesis_main.analysis.quality_iou_examples_20261014 import controls,metrics,official_primitives


def test_control_counterexamples_and_positive_control():
    expected=[[1,1],[.9,.9],[1,.9875],[1,2/3],[1,.5],[3/3.1,1]]
    assert len(controls())==len(expected)
    for case,wanted in zip(controls(),expected):
        _,_,ref,answers,_=case
        for (_,g),value in zip(answers,wanted):
            actual=metrics(g,ref)['mean_height_prism_iou3d']
            assert abs(actual-value)<1e-12
            assert abs(actual-official_primitives(g,ref))<1e-12
    # For S01's explicitly planar roof: h(x)=3+x/2; integrate the intersection.
    x=(np.arange(10000)+.5)*4/10000-2
    vi=4*4*np.minimum(3,3+x/2).mean()
    assert abs(vi/(48+48-vi)-11/13)<1e-10
    _,_,ref,answers,_=controls()[-1]
    errors=[np.sqrt(np.mean((np.array(g['top3d'])[:,1]-np.array(ref['top3d'])[:,1])**2)) for _,g in answers]
    assert abs(errors[0]-.1)<1e-12 and abs(errors[1]-1)<1e-12
    assert expected[-1][0]<expected[-1][1] and errors[0]<errors[1]
