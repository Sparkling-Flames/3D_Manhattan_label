import numpy as np
import pytest

from tools.thesis_main.analysis.quality_height_correspondence_20261013 import ray_depth_diagnostic


def geometry(xz, height=2.5):
    b=np.column_stack((np.asarray(xz)[:,0],-np.ones(len(xz)),np.asarray(xz)[:,1]))
    t=b.copy();t[:,1]+=height
    return dict(bottom3d=b.tolist(),top3d=t.tolist())


def test_fixed_top_rays_depth_effect_is_diagnostic_without_editing_input():
    ref=geometry([[-1,-1],[1,-1],[1,1],[-1,1]])
    ann=geometry([[-2,-2],[2,-2],[2,2],[-2,2]],height=4)
    before=repr(ann)
    out=ray_depth_diagnostic(ann,ref,2.5)
    assert out['unique_reference_depth_corners']==4
    assert out['observed_height_residual_rms_relative']==pytest.approx(.6)
    assert out['top_ray_residual_at_reference_depth_rms_relative']==pytest.approx(0)
    assert repr(ann)==before
    tilted=geometry([[-1,-1],[1,-1],[1,1],[-1,1]],height=3)
    assert ray_depth_diagnostic(tilted,ref,2.5)['top_ray_residual_at_reference_depth_rms_relative']==pytest.approx(.2)


def test_multiple_ray_intersections_are_not_silently_matched():
    ref=geometry([[-1,-1],[1,-1],[1,.5],[2,.5],[2,-1],[3,-1],[3,1],[-1,1]])
    ann=geometry([[.5,0],[0,.5],[-.5,0]])
    out=ray_depth_diagnostic(ann,ref,2.5)
    assert out['corners'][0]['status']=='multiple_reference_depths'
    assert 'top_ray_height_at_reference_depth' not in out['corners'][0]
