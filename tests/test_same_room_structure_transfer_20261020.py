import numpy as np
from tools.thesis_main.analysis.same_room_structure_transfer_20261020 import floor, geometry_features


def test_identical_geometry_and_seam_correspondence():
    p=np.array([[1,180],[1,330],[256,180],[256,330],[512,180],[512,330],[768,180],[768,330]],float)
    f=geometry_features(p,p)
    assert f["corner_delta"]==0 and f["unmatched_ref_9"]==0
    assert abs(f["omission"])<1e-12 and abs(f["extension"])<1e-12
    q=p.copy();q[:2,0]=1023
    assert geometry_features(q,p)["unmatched_ref_9"]==0
    assert floor(p)[0,1]>0


def test_bottom_y_and_missing_reference_are_distinct():
    p=np.array([[0,180],[0,320],[256,180],[256,320],[512,180],[512,320],[768,180],[768,320]],float)
    q=p.copy();q[1::2,1]+=5
    f=geometry_features(q,p)
    assert np.isclose(f["bottom_bias_9"],5)
    assert f["omission"]>0 and f["extension"]<1e-12
    assert "omission" not in geometry_features(p,None)
