"""Render a saved scene. Does not save or modify the input .blend file."""
import argparse,sys,json,time
from pathlib import Path
import bpy
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',type=Path,required=True);p.add_argument('--view',default='main',choices=['main','reverse']);p.add_argument('--percentage',type=int,default=100);p.add_argument('--samples',type=int,default=96);p.add_argument('--threads',type=int,default=4)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);s=bpy.context.scene
if a.view=='reverse':s.camera=bpy.data.objects.get(s.get('reverse_camera_name','Reverse')) or bpy.data.objects.get('REVERSE')
if not s.camera:raise RuntimeError('Requested camera is absent')
if 'hidden_for_'+a.view in s:
    names=set(json.loads(s['hidden_for_main']))|set(json.loads(s['hidden_for_reverse']))
    hidden=set(json.loads(s['hidden_for_'+a.view]))
    for name in names:
        if name in bpy.data.objects:bpy.data.objects[name].hide_render=name in hidden
s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=a.samples;s.cycles.use_denoising=True;s.cycles.use_animated_seed=False
s.render.threads_mode='FIXED';s.render.threads=a.threads;s.render.resolution_percentage=a.percentage
s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGBA';s.render.image_settings.color_depth='8'
s.render.use_persistent_data=False;a.output.parent.mkdir(parents=True,exist_ok=True);s.render.filepath=str(a.output.resolve());start=time.time()
bpy.ops.render.render(write_still=True)
record={'view':a.view,'camera':s.camera.name,'output':a.output.name,'base_resolution':[s.render.resolution_x,s.render.resolution_y],'color_transform':s.view_settings.view_transform,'resolution':[s.render.resolution_x*a.percentage//100,s.render.resolution_y*a.percentage//100],'samples':a.samples,'blender':bpy.app.version_string,'seconds':round(time.time()-start,2),'camera_ortho_scale':s.camera.data.ortho_scale,'background':'Native render; alpha can be composited onto white with png_white.py.','view_scope':'Saved presentation camera.'}
a.output.with_suffix('.render.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(record))
