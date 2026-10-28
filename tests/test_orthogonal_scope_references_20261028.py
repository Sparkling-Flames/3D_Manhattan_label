import numpy as np
from tools.thesis_main.analysis.orthogonal_scope_references_20261028 import axis,constrain_ring,points_for,user_axis_projection
from tools.thesis_main.analysis.scope_reference_reconstruction_20261016 import geometry


def test_joint_constraints_preserve_concavity_and_ring():
    p=np.array([[-2,-2],[2,-2],[2,0],[0,0],[0,2],[-2,2]],float)
    a=.23;r=np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]])
    noisy=p@r.T+np.array([[0,.001],[.002,0],[0,-.001],[.001,0],[0,.002],[-.001,0]])
    fixed=constrain_ring(noisy,a)
    assert len(fixed)==6 and axis(fixed)[1]<1e-8
    assert np.max(np.linalg.norm(fixed-p@r.T,axis=1))<.003
    np.testing.assert_allclose(constrain_ring(fixed,a),fixed,atol=1e-12)


def test_pair_reprojection_keeps_each_height_break():
    p=np.array([[-1,-1],[1,-1],[1,1],[-1,1]],float)
    heights=np.array([1,1,1.2,1.2])
    points=points_for(p,heights)
    np.testing.assert_allclose(np.asarray(geometry(points)['top3d'])[:,1],heights,atol=1e-12)


def test_manual_axis_uses_user_geometry_not_world_axes():
    a=.31;r=np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]])
    p=np.array([[-2,-1],[2,-1],[2,1],[-2,1]])@r.T
    fitted,result=user_axis_projection(p)
    assert abs(fitted-a)<1e-7
    np.testing.assert_allclose(result,p,atol=1e-7)
