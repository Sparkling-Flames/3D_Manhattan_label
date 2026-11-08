"""Reopen delivered Blender assets, pack resources, and check the actual saved scenes."""
from pathlib import Path
import json, math
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

ROOT=Path(__file__).resolve().parents[3]
PACK=ROOT/'docs/thesis_main/论文写作工作资料/Dot_Scene_Refinement_20261107'
paths=sorted(PACK.glob('*/full_model.blend'))+sorted(PACK.glob('*/presentation.blend'))
assert len(paths)==12
records=[]
for path in paths:
    assert path.resolve().is_relative_to(PACK.resolve())
    bpy.ops.wm.open_mainfile(filepath=str(path))
    sc=bpy.context.scene
    if path.parent.name=='05_split_floor' and path.name=='full_model.blend':
        for obj in sc.objects:
            if 'ceiling' in obj.name.lower():obj.hide_render=False
    missing=[]
    for im in bpy.data.images:
        if im.source=='FILE' and not im.packed_file and not Path(bpy.path.abspath(im.filepath)).is_file():missing.append(im.filepath)
    assert not missing,(path,missing)
    meshes=[o for o in sc.objects if o.type=='MESH']
    assert meshes and all(all(math.isfinite(c) for v in o.data.vertices for c in v.co) for o in meshes)
    if path.parent.name=='02_oblique':
        assert len([o for o in meshes if o.name.startswith('Stair tread')])==3
        assert not any(o.name.startswith(('Far landing','Far stair')) for o in meshes)
        treads=[o for o in meshes if o.name.startswith('Stair tread')]
        coords=[o.matrix_world@Vector(b) for o in treads for b in o.bound_box]
        assert max(p.x for p in coords)-min(p.x for p in coords)<.8,'Stair context extended beyond three entrance treads'
    if path.parent.name=='05_split_floor':
        assert any(o.name.startswith('Stairwell near return') for o in meshes)
    bpy.ops.file.pack_all()
    sc.render.image_settings.file_format='PNG'
    sc.render.filepath='//render.png'
    sc.render.use_file_extension=True
    bounds=None
    if path.name=='presentation.blend':
        bpy.context.view_layer.update()
        points=[world_to_camera_view(sc,sc.camera,o.matrix_world@Vector(b)) for o in meshes if not o.hide_render and not any(c.hide_render for c in o.users_collection) for b in o.bound_box]
        bounds=[min(p.x for p in points),max(p.x for p in points),min(p.y for p in points),max(p.y for p in points)]
        assert bounds[0]>-.01 and bounds[1]<1.01 and bounds[2]>-.01 and bounds[3]<1.01,(path,bounds)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(path),compress=True)
    records.append({'file':path.relative_to(PACK).as_posix(),'mesh_objects':len(meshes),'finite_vertices':True,'missing_external_files':missing,'camera_bounds_xy':bounds})
(PACK/'PACKAGE_CHECK.json').write_text(json.dumps({'checked_in':'local Blender 5.2.3','cloud_execution_performed':False,'models':records},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'opened_checked_packed':len(records),'missing_dependencies':0}))
