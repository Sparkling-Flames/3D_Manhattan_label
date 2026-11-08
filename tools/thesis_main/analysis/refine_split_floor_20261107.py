"""Calibrate the photographed descent edge in Dot's scene; preserve other geometry."""
from pathlib import Path
import json
import math
import zipfile

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'docs/thesis_main/论文写作工作资料/图5_下沉楼梯校准_20261107'
ARCHIVE = Path('C:/Users/ASUS/Downloads/Dot_Scene_Refinement_01-05_FINAL_20261107.zip')


def run():
    import bpy
    from mathutils import Vector
    from bpy_extras.object_utils import world_to_camera_view
    OUT.mkdir(exist_ok=True)
    src = OUT / '_source.blend'
    with zipfile.ZipFile(ARCHIVE) as z:
        names = [n for n in z.namelist() if n.endswith('/05_split_floor/full_model.blend')]
        assert len(names) == 1
        src.write_bytes(z.read(names[0]))
    bpy.ops.wm.open_mainfile(filepath=str(src))
    src.unlink()
    s = bpy.context.scene
    old, end = .22, 1.05
    # Two manually observed points on the same edge, in the original panorama.
    points = [(1099.733474, 679.475612), (1148.216457, 752.281527)]
    projected = []
    for u, v in points:
        lon, lat = (u / 2048 - .5) * 2 * math.pi, (.5 - v / 1024) * math.pi
        ray = Vector((math.cos(lat) * math.sin(lon), math.cos(lat) * math.cos(lon), math.sin(lat)))
        projected.append(ray * (-1.55 / ray.z) + Vector((0, 0, 1.55)))
    new = sum(p.x for p in projected) / len(projected)
    assert abs(projected[0].x - projected[1].x) < .01 and .60 < new < .67
    meshes = [o for o in s.objects if o.type == 'MESH']
    before = {o.name: [tuple(v.co) for v in o.data.vertices] for o in meshes}
    changed = []
    for o in meshes:
        descend = o.name.startswith(('Visible descending tread', 'Descending ')) or o.name == 'Right return falling skirting'
        landing = o.name in ('Central landing continuous with main floor', 'Central landing visible skirting')
        if not (descend or landing):
            continue
        inv = o.matrix_world.inverted()
        for v in o.data.vertices:
            p = o.matrix_world @ v.co
            if descend:
                # Keep the already-open model boundary fixed; treads depict only the visible start.
                p.x = new + (p.x - old) * ((end - new) / .48)
            elif p.x > old - .001:
                p.x += new - old
            v.co = inv @ p
        o.data.update()
        changed.append(o.name)
    bpy.context.view_layer.update()
    assert len(changed) == 13, changed
    assert all([tuple(v.co) for v in o.data.vertices] == before[o.name] for o in meshes if o.name not in changed)
    assert all(math.isfinite(c) for o in meshes for v in o.data.vertices for c in v.co)
    tread_tops = []
    for i, expected_z in enumerate((-.18, -.36)):
        o = bpy.data.objects[f'Visible descending tread {i}']
        verts = [o.matrix_world @ v.co for v in o.data.vertices]
        assert abs(max(v.z for v in verts) - expected_z) < 1e-5
        tread_tops.append(max(v.z for v in verts))
    for x, z in [(new - .05, 0), (new + .08, -.18), (end - .06, -.36)]:
        hit, loc, *_ = s.ray_cast(bpy.context.evaluated_depsgraph_get(), Vector((x, 1.9, .1)), Vector((0, 0, -1)), distance=1)
        assert hit and abs(loc.z - z) < .01, (x, z, hit, list(loc))
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == 'OPTIX'
    assert any(d.use for d in prefs.devices)
    s.render.engine = 'CYCLES'
    s.cycles.device = 'GPU'
    s.cycles.samples = 64
    s.cycles.use_denoising = True
    s.render.resolution_x, s.render.resolution_y = 2400, 1800
    s.render.resolution_percentage = 100
    s.render.film_transparent = True
    s.render.image_settings.file_format = 'PNG'
    s.render.image_settings.color_mode = 'RGBA'
    bpy.context.preferences.filepaths.save_version = 0
    def camera(name, eye, target, scale=None):
        cam = bpy.data.objects.get(name)
        if cam is None:
            cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
            s.collection.objects.link(cam)
        cam.location = eye
        cam.rotation_euler = (Vector(target) - cam.location).to_track_quat('-Z', 'Y').to_euler()
        cam.data.type = 'ORTHO'
        if scale is not None:
            cam.data.ortho_scale = scale
        return cam
    def roof(visible):
        for col in bpy.data.collections:
            if 'CEILING' in col.name:
                col.hide_render = not visible
        for o in meshes:
            if 'ceiling' in o.name.lower():
                o.hide_render = not visible
    def fit(cam):
        bpy.context.view_layer.update()
        q = cam.rotation_euler.to_quaternion()
        right, up = q @ Vector((1, 0, 0)), q @ Vector((0, 1, 0))
        ps = [o.matrix_world @ Vector(b) for o in meshes if not o.hide_render and not any(c.hide_render for c in o.users_collection) for b in o.bound_box]
        xs, ys = [p.dot(right) for p in ps], [p.dot(up) for p in ps]
        cam.location += right * ((min(xs) + max(xs)) / 2 - cam.location.dot(right)) + up * ((min(ys) + max(ys)) / 2 - cam.location.dot(up))
        cam.data.ortho_scale = max(max(xs) - min(xs), (max(ys) - min(ys)) * 4 / 3) * 1.12
    roof(False)
    main = camera('Main', (9, -4, 13), (-.7, .3, 1.2))
    fit(main)
    reverse = bpy.data.objects['Reverse']
    fit(reverse)
    detail = camera('Stair detail', (6, -1, 8), (-.3, 1.8, .5), 5.4)
    s['main_camera_name'] = main.name
    s['reverse_camera_name'] = reverse.name
    s['refinement_note'] = 'Descent edge fitted to two original-image rays; camera-height convention, not surveyed dimensions.'
    s.camera = main
    bpy.ops.file.pack_all()
    roof(True)
    s.render.filepath = '//main.png'
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'full_model.blend'), compress=True)
    roof(False)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'presentation.blend'), compress=True)
    for name, cam in [('main', main), ('reverse', reverse), ('detail', detail)]:
        s.camera = cam
        s.render.filepath = str(OUT / f'{name}.png')
        bpy.ops.render.render(write_still=True)
    roof(True)
    cam = bpy.data.objects['Original source viewpoint']
    yaw, pitch = math.radians(15), math.radians(-22)
    direction = Vector((math.sin(yaw) * math.cos(pitch), math.cos(yaw) * math.cos(pitch), math.sin(pitch)))
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    cam.data.type = 'PERSP'
    cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.sensor_width = 36
    cam.data.lens = 36 / (2 * math.tan(math.radians(40)))
    s.camera = cam
    lamp = bpy.data.objects.new('Review light', bpy.data.lights.new('Review light', 'POINT'))
    s.collection.objects.link(lamp)
    lamp.location = (0, 0, 2.2)
    lamp.data.energy, lamp.data.shadow_soft_size = 100, .6
    s.render.resolution_x, s.render.resolution_y = 1200, 900
    s.render.filepath = str(OUT / 'source_check.png')
    bpy.ops.render.render(write_still=True)
    bpy.context.view_layer.update()
    uv = world_to_camera_view(s, cam, Vector((new, 2.62, 0)))
    (OUT / 'CHECK.json').write_text(json.dumps({'source_archive': str(ARCHIVE), 'observed_uv': points, 'assumed_camera_height': 1.55, 'old_edge_x': old, 'new_edge_x': new, 'edge_pixel_at_back_wall': [uv.x * 1200, (1 - uv.y) * 900], 'tread_heights': tread_tops, 'changed_objects': changed, 'other_meshes_unchanged': True, 'landing_tread_rays_pass': True, 'open_model_end_x': end, 'source_camera': {'yaw':15,'pitch':-22,'hfov':80}, 'measured_reconstruction': False}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    run()
