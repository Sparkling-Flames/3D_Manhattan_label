"""Export one final model. Run with Blender --python ... -- --help."""
import argparse,sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from scene_snapshot import capture_scene,clear_geometry,clean,shading_fingerprints
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--asset',type=Path,required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);source=a.input.resolve();bpy.ops.wm.open_mainfile(filepath=str(source))
if bpy.data.libraries:raise RuntimeError('Linked external libraries are not supported')
if any(i.source=='FILE' and not i.packed_file for i in bpy.data.images):raise RuntimeError('Unpacked external image found')
rec=capture_scene();rec['shading_fingerprints']=shading_fingerprints();rec['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest();rec['source_filename']=source.name
for mat in bpy.data.materials:mat.use_fake_user=True
clear_geometry()
# Packed artwork is self-contained. Keep only portable nominal filenames.
for image in bpy.data.images:
    if image.packed_file:image.filepath='//'+Path(image.filepath).name
# Weak append provenance is not an external link and is not needed at runtime.
for prop in bpy.data.bl_rna.properties:
    if prop.type=='COLLECTION':
        for block in getattr(bpy.data,prop.identifier):
            if isinstance(block,bpy.types.ID) and block.library_weak_reference:
                block.library_weak_reference.filepath=''
for screen in bpy.data.screens:
    for area in screen.areas:
        for space in area.spaces:
            if space.type=='FILE_BROWSER' and space.params:
                space.params.directory=b'';space.params.filename=''
for txt in list(bpy.data.texts):bpy.data.texts.remove(txt)
# Preserve shading and render settings while removing host-specific metadata.
for block in [bpy.context.scene,bpy.context.scene.collection,*bpy.data.materials,*bpy.data.worlds]:
    for k,v in list(block.items()):
        if isinstance(v,str):block[k]=clean(v)
s=bpy.context.scene;s.render.filepath='//main.png';s.render.use_persistent_data=False
bpy.context.preferences.filepaths.save_version=0
for path in (a.snapshot,a.asset):path.parent.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(a.asset.resolve()),compress=True,relative_remap=False)
rec['asset_filename']=a.asset.name;rec['asset_sha256']=hashlib.sha256(a.asset.read_bytes()).hexdigest()
a.snapshot.write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('EXPORTED',a.snapshot, 'objects:',len(rec['objects']))
