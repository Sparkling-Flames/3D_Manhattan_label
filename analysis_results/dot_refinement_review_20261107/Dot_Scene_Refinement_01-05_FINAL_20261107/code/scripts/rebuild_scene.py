"""Rebuild one final scene from its editable JSON snapshot and shading asset."""
import argparse,sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from scene_snapshot import rebuild,capture_scene,differences,shading_fingerprints
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--asset',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--report',type=Path);p.add_argument('--allow-edited-asset',action='store_true')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);snap=json.loads(a.snapshot.read_text(encoding='utf-8'))
if not a.allow_edited_asset and hashlib.sha256(a.asset.read_bytes()).hexdigest()!=snap['asset_sha256']:raise RuntimeError('Asset checksum differs; explicitly allow only intentional material edits')
bpy.ops.wm.open_mainfile(filepath=str(a.asset.resolve()))
assert len(bpy.data.objects)==len(bpy.data.meshes)==len(bpy.data.curves)==0,'Asset must not contain geometry'
rebuild(snap);out=a.output.resolve();out.parent.mkdir(parents=True,exist_ok=True);bpy.context.scene.render.filepath='//main.png';bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True,relative_remap=False)
# Verify again after a real save/reload, not only in the construction session.
bpy.ops.wm.open_mainfile(filepath=str(out));actual=capture_scene();expected={k:snap[k] for k in actual};diff=differences(expected,actual)
shading_diff=differences(snap['shading_fingerprints'],shading_fingerprints());diff.extend(['shading'+x for x in shading_diff])
report={'passed':not diff,'blender':bpy.app.version_string,'snapshot':a.snapshot.name,'output':out.name,'objects':len(actual['objects']),'meshes':len(actual['meshes']),'curves':len(actual['curves']),'cameras':len(actual['cameras']),'lights':len(actual['lights']),'materials':len(actual['material_names']),'native_shading_fingerprints_match':not shading_diff,'field_differences':diff,'external_images':[i.filepath for i in bpy.data.images if i.source=='FILE' and not i.packed_file], 'scope':'Round-trip geometry topology/coordinates/attributes, UVs/custom normals, transforms, modifiers, collections/layers, cameras/lights, material assignments. Shading/world/render settings are loaded losslessly from native assets.'}
if a.report:a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
if diff:raise RuntimeError('Round-trip mismatch; see report')
