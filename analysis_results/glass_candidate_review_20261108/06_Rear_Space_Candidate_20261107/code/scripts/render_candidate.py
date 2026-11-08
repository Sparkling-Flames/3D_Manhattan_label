"""Reproduce the reviewed B candidate preview settings without saving the model."""
import bpy,argparse,sys,json,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--view',choices=['main','rear'],required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--percentage',type=int,default=100);p.add_argument('--samples',type=int,default=12)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);s=bpy.context.scene;name='MAIN' if a.view=='main' else 'B_REAR_BRANCH_REVIEW'
s.camera=bpy.data.objects[name];s.render.resolution_x=900;s.render.resolution_y=694;s.render.resolution_percentage=a.percentage
s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=a.samples;s.render.threads_mode='FIXED';s.render.threads=2;s.render.use_persistent_data=False
s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGBA';s.render.image_settings.color_depth='8'
a.output.parent.mkdir(parents=True,exist_ok=True);s.render.filepath=str(a.output.resolve());start=time.time();bpy.ops.render.render(write_still=True)
record={'view':a.view,'camera':name,'base_resolution':[900,694],'percentage':a.percentage,'samples':a.samples,'threads':2,'device':'CPU','engine':'CYCLES','view_transform':s.view_settings.view_transform,'look':s.view_settings.look,'film_transparent':s.render.film_transparent,'seed':s.cycles.seed,'seconds':round(time.time()-start,2),'visibility':'Saved candidate visibility unchanged; unlocated gray surface remains disabled.','geometry_saved':False}
a.output.with_suffix('.render.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
