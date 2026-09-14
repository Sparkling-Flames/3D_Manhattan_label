import numpy as np
import pytest
from tools.thesis_main.analysis.image_portrait.common import pool_spatial,restore_yaw,restore_corners,cube_faces,conservative_nadir_masks


def test_nadir_sensitivity_mask():
    masks = conservative_nadir_masks(504)
    assert all(masks[k].all() for k in masks if k != 'down')
    assert not masks['down'][252,252]
    assert masks['down'][0,0]
    np.testing.assert_array_equal(masks['down'], masks['down'][::-1,::-1])


def test_yaw_pool_and_float_corners():
    x=np.arange(2*8*64,dtype=np.float32).reshape(2,8,64)
    for d in (0,90,180,270):
        np.testing.assert_array_equal(restore_yaw(np.roll(x,round(64*d/360),-1),d),x)
    g,s=pool_spatial(x)
    assert g.shape==(4,) and s.shape==(16,4)
    np.testing.assert_allclose(s[:,:2].mean(0),g[:2])
    p=np.array([[.125,3.25],[1023.75,5]],dtype=np.float32)
    q=p.copy(); q[:,0]=(q[:,0]+256)%1024
    np.testing.assert_allclose(restore_corners(q,90),p)
    with pytest.raises(ValueError):
        pool_spatial(np.full((3,32),np.nan))


def test_cube_projection():
    h,w=256,512
    rgb=np.zeros((h,w,3),dtype=np.uint8)
    rgb[:,:,0]=np.arange(w)[None,:]*255//w
    rgb[:,:,1]=np.arange(h)[:,None]*255//h
    faces,m=cube_faces(rgb,33)
    assert len(faces)==6 and m['independent_capture_count']==1
    for r in m['camera_to_panorama'].values():
        np.testing.assert_allclose(np.linalg.det(r),1)
        np.testing.assert_allclose(np.asarray(r).T@r,np.eye(3))
    assert abs(int(faces['front'][16,16,0])-127)<=2
    assert abs(int(faces['right'][16,16,0])-191)<=2
    assert faces['up'][16,16,1]<2 and faces['down'][16,16,1]>250
