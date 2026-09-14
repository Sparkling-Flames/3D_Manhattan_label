"""Shared numerical helpers for exploratory image portraits."""
from pathlib import Path
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
BUNDLE = ROOT / 'analysis_results/image_portrait_20260914_v1'
LOCAL = ROOT / 'output/image_portrait_20260914_v1'
YAW_DEGREES = (0, 90, 180, 270)


def read_images():
    rows = [json.loads(s) for s in (BUNDLE/'metadata/images.jsonl').read_text(encoding='utf8').splitlines()]
    if len({r['image_id'] for r in rows}) != len(rows):
        raise ValueError('duplicate image identity')
    return rows


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf8', newline='\n')


def pool_spatial(feature):
    x = np.asarray(feature, dtype=np.float32)
    if x.ndim not in (2, 3) or x.shape[-1] < 16 or not np.isfinite(x).all():
        raise ValueError(f'invalid feature shape/values: {x.shape}')
    def stats(a):
        a = a.reshape(a.shape[0], -1)
        return np.concatenate((a.mean(1), a.std(1))).astype(np.float32)
    return stats(x), np.stack([stats(a) for a in np.array_split(x, 16, axis=-1)])


def restore_yaw(values, degrees, axis=-1):
    return np.roll(values, -round(values.shape[axis]*degrees/360), axis=axis)


def restore_corners(points, degrees, width=1024):
    points = np.asarray(points, dtype=np.float32).copy()
    if points.ndim != 2 or points.shape[1] != 2 or not np.isfinite(points).all():
        raise ValueError('expected finite Nx2 corners')
    points[:, 0] = (points[:, 0] - width*degrees/360) % width
    return points


def cube_faces(rgb, size=512):
    """Six pinhole views; x right, y down, z forward; one independent capture."""
    import cv2
    rgb = np.asarray(rgb)
    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint8 or size < 2:
        raise ValueError('expected uint8 RGB image')
    frames = {'front': ([0,0,1],[0,-1,0]), 'right': ([1,0,0],[0,-1,0]),
              'back': ([0,0,-1],[0,-1,0]), 'left': ([-1,0,0],[0,-1,0]),
              'up': ([0,-1,0],[0,0,-1]), 'down': ([0,1,0],[0,0,1])}
    t = (np.arange(size, dtype=np.float32)+.5)*2/size-1
    xx, yy = np.meshgrid(t,t)
    rays = np.stack((xx,yy,np.ones_like(xx)),-1)
    rays /= np.linalg.norm(rays,axis=-1,keepdims=True)
    h,w = rgb.shape[:2]
    padded = np.concatenate((rgb[:,-1:],rgb,rgb[:,:1]),axis=1)
    faces, rotations = {}, {}
    for name,(forward,up) in frames.items():
        forward,up = np.asarray(forward),np.asarray(up)
        rotation = np.stack((np.cross(forward,up),-up,forward),axis=1).astype(np.float32)
        world = rays@rotation.T
        u = ((np.arctan2(world[...,0],world[...,2])/(2*np.pi)+.5)*w-.5)%w
        v = (.5+np.arcsin(np.clip(world[...,1],-1,1))/np.pi)*h-.5
        faces[name] = cv2.remap(padded,(u+1).astype(np.float32),np.clip(v,0,h-1).astype(np.float32),cv2.INTER_LINEAR)
        rotations[name] = rotation.tolist()
    return faces, dict(convention='x_right_y_down_z_forward',order=list(frames),
                      source_shape_hw=[h,w],face_size=size,fov_degrees=90,
                      intrinsics=[[size/2,0,(size-1)/2],[0,size/2,(size-1)/2],[0,0,1]],
                      camera_to_panorama=rotations,independent_capture_count=1)
