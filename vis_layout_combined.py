"""
Visualize HoHoNet layout with both 2D overlay and 3D mesh in a single view.
Combines the annotated panorama image with the 3D room reconstruction.
"""
import json
import numpy as np
import open3d as o3d
from PIL import Image, ImageDraw
from scipy.signal import correlate2d
from scipy.ndimage import shift

from lib.misc.post_proc import np_coor2xy, np_coorx2u, np_coory2v
from eval_layout import layout_2_depth


def create_2d_overlay(img_path, cor_id):
    """Create 2D image with layout annotations overlaid"""
    img = Image.open(img_path).convert('RGB')
    W, H = img.size
    draw = ImageDraw.Draw(img)
    
    # Draw ceiling/floor boundaries
    bon = np.zeros((2, W))
    ceil_pts = cor_id[::2]
    floor_pts = cor_id[1::2]
    
    ceil_x = ceil_pts[:, 0]
    ceil_y = ceil_pts[:, 1]
    bon[0] = np.interp(np.arange(W), ceil_x, ceil_y, period=W)
    
    floor_x = floor_pts[:, 0]
    floor_y = floor_pts[:, 1]
    bon[1] = np.interp(np.arange(W), floor_x, floor_y, period=W)
    
    # Draw boundaries
    ceil_line = [(x, int(bon[0, x])) for x in range(W)]
    floor_line = [(x, int(bon[1, x])) for x in range(W)]
    draw.line(ceil_line, fill=(0, 255, 0), width=2)
    draw.line(floor_line, fill=(0, 255, 0), width=2)
    
    # Draw corner vertical lines and points
    for i in range(0, len(cor_id), 2):
        ceil_pt = tuple(cor_id[i].astype(int))
        floor_pt = tuple(cor_id[i+1].astype(int))
        
        # Vertical line
        draw.line([ceil_pt, floor_pt], fill=(255, 0, 0), width=3)
        
        # Corner points
        r = 6
        draw.ellipse([ceil_pt[0]-r, ceil_pt[1]-r, ceil_pt[0]+r, ceil_pt[1]+r], 
                     fill=(255, 0, 0), outline=(255, 255, 255), width=2)
        draw.ellipse([floor_pt[0]-r, floor_pt[1]-r, floor_pt[0]+r, floor_pt[1]+r], 
                     fill=(255, 0, 0), outline=(255, 255, 255), width=2)
    
    return np.array(img)


def create_3d_mesh(equirect_texture, cor_id, show_ceiling=False, 
                   ignore_floor=False, ignore_wall=False, ignore_wireframe=False):
    """Create 3D mesh from layout"""
    H, W = equirect_texture.shape[:2]
    
    # Convert corners to layout
    depth, floor_mask, ceil_mask, wall_mask = layout_2_depth(cor_id, H, W, return_mask=True)
    coorx, coory = np.meshgrid(np.arange(W), np.arange(H))
    us = np_coorx2u(coorx, W)
    vs = np_coory2v(coory, H)
    zs = depth * np.sin(vs)
    cs = depth * np.cos(vs)
    xs = cs * np.sin(us)
    ys = -cs * np.cos(us)

    # Aggregate mask
    mask = np.ones_like(floor_mask)
    if ignore_floor:
        mask &= ~floor_mask
    if not show_ceiling:
        mask &= ~ceil_mask
    if ignore_wall:
        mask &= ~wall_mask

    # Prepare ply's points and faces
    xyzrgb = np.concatenate([
        xs[...,None], ys[...,None], zs[...,None],
        equirect_texture], -1)
    xyzrgb = np.concatenate([xyzrgb, xyzrgb[:,[0]]], 1)
    mask = np.concatenate([mask, mask[:,[0]]], 1)
    lo_tri_template = np.array([[0, 0, 0], [0, 1, 0], [0, 1, 1]])
    up_tri_template = np.array([[0, 0, 0], [0, 1, 1], [0, 0, 1]])
    ma_tri_template = np.array([[0, 0, 0], [0, 1, 1], [0, 1, 0]])
    lo_mask = (correlate2d(mask, lo_tri_template, mode='same') == 3)
    up_mask = (correlate2d(mask, up_tri_template, mode='same') == 3)
    ma_mask = (correlate2d(mask, ma_tri_template, mode='same') == 3) & (~lo_mask) & (~up_mask)
    ref_mask = (
        lo_mask | (correlate2d(lo_mask, np.flip(lo_tri_template, (0,1)), mode='same') > 0) |\
        up_mask | (correlate2d(up_mask, np.flip(up_tri_template, (0,1)), mode='same') > 0) |\
        ma_mask | (correlate2d(ma_mask, np.flip(ma_tri_template, (0,1)), mode='same') > 0)
    )
    points = xyzrgb[ref_mask]

    ref_id = np.full(ref_mask.shape, -1, np.int32)
    ref_id[ref_mask] = np.arange(ref_mask.sum())
    faces_lo_tri = np.stack([
        ref_id[lo_mask],
        ref_id[shift(lo_mask, [1, 0], cval=False, order=0)],
        ref_id[shift(lo_mask, [1, 1], cval=False, order=0)],
    ], 1)
    faces_up_tri = np.stack([
        ref_id[up_mask],
        ref_id[shift(up_mask, [1, 1], cval=False, order=0)],
        ref_id[shift(up_mask, [0, 1], cval=False, order=0)],
    ], 1)
    faces_ma_tri = np.stack([
        ref_id[ma_mask],
        ref_id[shift(ma_mask, [1, 0], cval=False, order=0)],
        ref_id[shift(ma_mask, [0, 1], cval=False, order=0)],
    ], 1)
    faces = np.concatenate([faces_lo_tri, faces_up_tri, faces_ma_tri])

    # Create mesh
    mesh = o3d.geometry.TriangleMesh()
    mesh.vertices = o3d.utility.Vector3dVector(points[:, :3])
    mesh.vertex_colors = o3d.utility.Vector3dVector(points[:, 3:] / 255.)
    mesh.triangles = o3d.utility.Vector3iVector(faces)
    
    geometries = [mesh]
    
    # Add wireframe
    if not ignore_wireframe:
        N = len(cor_id) // 2
        floor_z = -1.6
        floor_xy = np_coor2xy(cor_id[1::2], floor_z, W, H, floorW=1, floorH=1)
        c = np.sqrt((floor_xy**2).sum(1))
        v = np_coory2v(cor_id[0::2, 1], H)
        ceil_z = (c * np.tan(v)).mean()

        wf_points = [[x, y, floor_z] for x, y in floor_xy] +\
                    [[x, y, ceil_z] for x, y in floor_xy]
        wf_lines = [[i, (i+1)%N] for i in range(N)] +\
                   [[i+N, (i+1)%N+N] for i in range(N)] +\
                   [[i, i+N] for i in range(N)]
        wf_colors = [[1, 0, 0] for i in range(len(wf_lines))]
        wf_line_set = o3d.geometry.LineSet()
        wf_line_set.points = o3d.utility.Vector3dVector(wf_points)
        wf_line_set.lines = o3d.utility.Vector2iVector(wf_lines)
        wf_line_set.colors = o3d.utility.Vector3dVector(wf_colors)
        geometries.append(wf_line_set)
    
    return geometries


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--img', required=True,
                        help='Image texture in equirectangular format')
    parser.add_argument('--layout', required=True,
                        help='Txt or json file containing layout corners (cor_id)')
    parser.add_argument('--out_ply', default=None,
                        help='Export 3D mesh to PLY file')
    parser.add_argument('--out_2d', default=None,
                        help='Export 2D overlay image')
    parser.add_argument('--show_ceiling', action='store_true',
                        help='Rendering ceiling (skip by default)')
    parser.add_argument('--ignore_floor', action='store_true',
                        help='Skip rendering floor')
    parser.add_argument('--ignore_wall', action='store_true',
                        help='Skip rendering wall')
    parser.add_argument('--ignore_wireframe', action='store_true',
                        help='Skip rendering wireframe')
    parser.add_argument('--no_vis', action='store_true',
                        help='Skip interactive visualization')
    args = parser.parse_args()

    # Load image and layout
    equirect_texture = np.array(Image.open(args.img))
    H, W = equirect_texture.shape[:2]
    
    if args.layout.endswith('json'):
        with open(args.layout) as f:
            inferenced_result = json.load(f)
        cor_id = np.array(inferenced_result['uv'], np.float32)
        cor_id[:, 0] *= W
        cor_id[:, 1] *= H
    else:
        cor_id = np.loadtxt(args.layout).astype(np.float32)

    # Create 2D overlay
    overlay_img = create_2d_overlay(args.img, cor_id)
    if args.out_2d:
        Image.fromarray(overlay_img).save(args.out_2d)
        print(f'Saved 2D overlay to {args.out_2d}')

    # Create 3D mesh
    geometries = create_3d_mesh(
        equirect_texture, cor_id,
        show_ceiling=args.show_ceiling,
        ignore_floor=args.ignore_floor,
        ignore_wall=args.ignore_wall,
        ignore_wireframe=args.ignore_wireframe
    )
    
    # Export PLY if requested
    if args.out_ply:
        mesh = geometries[0]
        o3d.io.write_triangle_mesh(args.out_ply, mesh)
        print(f'Saved 3D mesh to {args.out_ply}')

    # Interactive visualization with both views
    if not args.no_vis:
        # Create image as textured plane for side-by-side view
        overlay_o3d = o3d.geometry.Image(overlay_img.astype(np.uint8))
        
        # Show 3D visualization
        print("Displaying 3D mesh. Close window to show 2D overlay next.")
        o3d.visualization.draw_geometries(geometries, 
                                          mesh_show_back_face=True,
                                          window_name="HoHoNet Layout - 3D Mesh")
        
        # Show 2D overlay in separate window
        print("Displaying 2D overlay.")
        Image.fromarray(overlay_img).show(title="HoHoNet Layout - 2D Overlay")
