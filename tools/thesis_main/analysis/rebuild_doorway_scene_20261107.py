"""Photo/pose-constrained physical explanation; complete model and display cuts separate."""
from pathlib import Path
import sys,json,math,ast,types
import numpy as np
import bpy
from mathutils import Vector

ROOT=Path('D:/Work/HOHONET')
sys.path.insert(0,str(Path(__file__).parent))
import render_doorway_candidate_20261107 as assets
WORK=ROOT/'docs/thesis_main/论文写作工作资料/门洞实景观察_20261107/精细模型'
WORK.mkdir(parents=True,exist_ok=True)
S=json.loads((ROOT/'analysis_results/doorway_point_folding_20261107/doorway_proportion_fit.json').read_text(encoding='utf-8'))
DOT=assets.DOT
g=types.ModuleType('geometry_core');g.__dict__.update(bpy=bpy,np=np,math=math,Vector=Vector)
tree=ast.parse((DOT/'geometry_core.py').read_text(encoding='utf-8'))
selected=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'rgb','matte','mesh'}],type_ignores=[])
exec(compile(selected,str(DOT/'geometry_core.py'),'exec'),g.__dict__);sys.modules['geometry_core']=g
sys.path.insert(0,str(DOT));import appearance_assets as a


def main():
 bpy.ops.wm.read_factory_settings(use_empty=True)
 sc=bpy.context.scene;sc.name='Doorway physical explanation'
 sc.unit_settings.system='METRIC';sc.unit_settings.scale_length=1
 M={k:a.material(k,c,r,metal) for k,c,r,metal in [
 ('plaster','#e5dfd0',.85,0),('ivory','#e4dfcf',.55,0),('wood','#503323',.44,0),
 ('trim','#35251d',.45,0),('oak','#bb8e54',.58,0),('ceramic','#f5f0e3',.23,0),
 ('brass','#a08752',.3,.65),('glass','#c2d9dc',.20,.15),('dark','#282522',.7,0),
 ('teal','#247c85',.4,0),('wallpaper','#c9bfa5',.85,0),('rug','#84735a',.9,0)]}
 # Fine vertical wallpaper stripes are display material, never geometry or observed pixels.
 mat=M['wallpaper'];nodes=mat.node_tree.nodes;links=mat.node_tree.links
 tex=nodes.new('ShaderNodeTexCoord');wave=nodes.new('ShaderNodeTexWave');wave.wave_type='BANDS';wave.bands_direction='X';wave.inputs['Scale'].default_value=34
 links.new(tex.outputs['Generated'],wave.inputs['Vector']);ramp=nodes.new('ShaderNodeValToRGB')
 ramp.color_ramp.elements[0].color=g.rgb('#c8bea5');ramp.color_ramp.elements[1].color=g.rgb('#e1d8c2')
 links.new(wave.outputs['Color'],ramp.inputs[0]);links.new(ramp.outputs[0],nodes.get('Principled BSDF').inputs['Base Color'])
 floor=a.wood()
 for node in floor.node_tree.nodes:
  if node.type=='TEX_BRICK':
   node.inputs['Color1'].default_value=g.rgb('#a77b46');node.inputs['Color2'].default_value=g.rgb('#bd935d');node.inputs['Mortar'].default_value=g.rgb('#66513a')
 current_group='fixtures'
 def box(name,center,size,mat='ivory',bevel=.004,angle=0):
  assert min(size)>0,(name,size)
  ob=a.box(sc,name,center,size,M[mat] if isinstance(mat,str) else mat,bevel,angle)
  ob['group']=current_group;ob['basis']='photo-informed appearance' if current_group=='fixtures' else 'photo and pose constrained envelope'
  return ob
 def tube(name,A,B,r=.008,mat='brass'):
  v=Vector(B)-Vector(A);ob=a.cylinder(sc,name,(Vector(A)+Vector(B))/2,r,v.length,M[mat]);ob.rotation_euler=v.to_track_quat('Z','Y').to_euler();ob['group']=current_group;return ob
 bx0,bx1,by0,by1=S['bathroom_bounds_xy'];hx0,hx1,hy0,hy1=S['hall_bounds_xy']
 H=S['common_height'];DH=S['door_height'];w=S['door_half_width'];th=.12
 # The opaque cupboard hides its back wall: a separate approximate backing allowance.
 cabinet_back=bx1+.32
 box('Bathroom floor',((bx0+cabinet_back)/2,(by0+by1)/2,-.055),(cabinet_back-bx0,by1-by0,.11),floor)
 box('Hall floor',((hx0+hx1)/2,(hy0+hy1)/2,-.055),(hx1-hx0,hy1-hy0,.11),floor)
 box('Threshold board',(0,0,-.022),(2*w,hy0-by1,.044),'oak')
 wall_records=[];openings=[]
 def wall(name,A,B,normal,bath=False,ops=()):
  nonlocal current_group
  current_group=name;A=np.array(A,float);B=np.array(B,float);n=np.array(normal,float)
  L=np.linalg.norm(B-A);u=(B-A)/L;angle=math.atan2(u[1],u[0])
  def p(s,z,offset=0):return [*(A+u*s+n*offset),z]
  cuts=sorted(set([0.,L]+[s for op in ops for s in op[:2]]))
  for l,r in zip(cuts[:-1],cuts[1:]):
   op=next((o for o in ops if o[0]<(l+r)/2<o[1]),None)
   bands=[(0,op[2]),(op[3],H)] if op else [(0,H)]
   for z0,z1 in bands:
    for low,high in [(z0,min(z1,.32)),(max(z0,.32),min(z1,1.05)),(max(z0,1.05),z1)]:
     if high-low<1e-5:continue
     ob=box(name+' shell',p((l+r)/2,(low+high)/2,-th/2),(r-l,th,high-low),'plaster',.002,angle)
     ob['shell']=True;ob['z0']=low;ob['z1']=high;ob['interval']=json.dumps([l,r]);wall_records.append(ob.name)
     if bath:
      box(name+' finish',p((l+r)/2,(low+high)/2,.003),(r-l,.006,high-low),'ivory' if high<=1.05 else 'wallpaper',0,angle)
   # Skirting and picture rail follow each unbroken wall interval.
   for z,width,depth in [(.09,.18,.024),(1.05,.05,.026),(H-.12,.036,.019)]:
    if op and op[2]<=z<=op[3]:continue
    box(name+' moulding',p((l+r)/2,z,depth/2),(r-l,depth,width),'ivory' if bath else 'wood',.003,angle)
   if bath and not(op and op[2]<1.05):
    for s in np.arange(l+.08,r-.04,.095):box(name+' wainscot bead',p(s,.52,.01),(.008,.012,.87),'ivory',.002,angle)
  for s0,s1,z0,z1,label in ops:
   assert 0<=s0<s1<=L and 0<=z0<z1<H
   openings.append({'wall':name,'interval':[s0,s1],'height':[z0,z1],'name':label})
   for offset,bead in [(0,.055),(.04,.02)]:
    for s in [s0-offset,s1+offset]:box(name+' '+label+' casing',p(s,(z0+z1)/2,.027),(bead,.04,z1-z0+offset),'ivory' if bath else 'wood',.004,angle)
    for z in [z1+offset]+([z0-offset] if z0>0 else []):box(name+' '+label+' head',p((s0+s1)/2,z,.027),(s1-s0+2*offset,.045,bead),'ivory' if bath else 'wood',.004,angle)
  return p
 wall('bath_south',(bx0,by0),(cabinet_back,by0),(0,1),True)
 wall('bath_north',(bx0,by1),(cabinet_back,by1),(0,-1),True,[(-w-bx0,w-bx0,0,DH,'door')])
 p=wall('bath_window',(bx0,by0),(bx0,by1),(1,0),True,[(.27,by1-by0-.24,1.10,2.48,'window')])
 W=by1-by0-.51;mid=(by1-by0+.03)/2
 box('Window glass',p(mid,1.79,-.025),(.025,W-.05,1.34),'glass')
 for y in [by0+.29,by1-.26,(by0+by1)/2]:box('Window stile',(bx0+.012,y,1.79),(.05,.028,1.34),'ivory')
 for z in [1.13,1.79,2.45]:box('Window sash rail',(bx0+.01,(by0+by1)/2,z),(.05,W,.03),'ivory')
 wall('cabinet_back',(cabinet_back,by0),(cabinet_back,by1),(-1,0),True)
 s0,s1=S['side_opening_y']
 wall('hall_right',(hx1,hy0),(hx1,hy1),(-1,0),False,[(s0-hy0,s1-hy0,0,DH,'side doorway')])
 wall('hall_left',(hx0,hy0),(hx0,hy1),(1,0),False,[(1.75,2.70,0,DH,'other side doorway')])
 wall('hall_front',(hx0,hy0),(hx1,hy0),(0,1),False,[(-w-hx0,w-hx0,0,DH,'bathroom doorway')])
 # This is the back of the same partition, not a second overlapping solid.
 for ob in list(sc.objects):
  if ob.get('group')=='hall_front' and ob.get('shell'):
   wall_records.remove(ob.name);bpy.data.objects.remove(ob,do_unlink=True)
 if cabinet_back<hx1:
  ob=box('Hall front beyond cupboard',((cabinet_back+hx1)/2,hy0-th/2,H/2),(hx1-cabinet_back,th,H),'plaster',.002)
  ob['shell']=True;wall_records.append(ob.name)
 p=wall('hall_far',(hx0,hy1),(hx1,hy1),(0,-1),False,[(.12,hx1-hx0-.12,0,2.62,'glazed entry')])
 # Far door uses a real gap: separate leaf stiles, glass lights and transom.
 dw=hx1-hx0-.24;mx=(hx0+hx1)/2
 for x in [hx0+.15,mx,hx1-.15]:box('Hall entry stile',(x,hy1,1.06),(.18,.07,2.12),'wood')
 for z,hh in [(.37,.74),(2.08,.14),(2.22,.14),(2.59,.06)]:box('Hall entry rail',(mx,hy1-.012,z),(dw,.07,hh),'wood')
 for x in [(hx0+.15+mx)/2,(mx+hx1-.15)/2]:box('Hall tall glass',(x,hy1,1.37),(dw/2-.18,.018,1.26),'glass')
 box('Transom glass',(mx,hy1,2.42),(dw-.05,.02,.29),'glass')
 for x in np.arange(hx0+.22,hx1-.15,.14):tube('Transom leading',(x,hy1-.018,2.28),(x,hy1-.018,2.56),.003,'brass')
 current_group='doorway'
 for x,tag in [(-w,'L'),(w,'R')]:
  box(tag+' white reveal',(x+(-.025 if x<0 else .025),0,DH/2),(.05,hy0-by1,DH),'ivory',.002)
  box(tag+' dark jamb',(x,hy0+.016,DH/2),(.045,.045,DH),'wood',.003)
  for delta in [0,.032]:box(tag+' moulded casing',(x+(-delta if x<0 else delta),hy0+.044,DH/2),(.028,.025,DH+.04),'trim',.003)
 box('White soffit',(0,0,DH+.04),(2*w,hy0-by1,.08),'ivory',.002)
 box('Dark lintel',(0,hy0+.03,DH),(2*w+.08,.055,.08),'wood')
 for y in [by1-.01,hy0+.05]:tube('Threshold edge',(-w,y,.005),(w,y,.005),.004,'brass')
 current_group='door_leaf'
 hinge=np.array([-w,hy0]);direction=np.array([-.035,1.]);direction/=np.linalg.norm(direction)
 c=np.r_[hinge+direction*w,DH/2]
 assets.panel_door(sc,a,M,box,'Open bathroom leaf',c,2*w-.025,DH-.025,.045,math.atan2(direction[1],direction[0]))
 for z in [.22,1.0,1.82]:box('Hinge',(-w,hy0,z),(.028,.06,.1),'brass',.003)
 # Side opening remains open; a short recess provides real depth, not a photograph on a wall.
 current_group='side_room_context'
 box('Side threshold',(hx1+.18,(s0+s1)/2,-.025),(.36,s1-s0,.05),floor)
 for y in [s0,s1]:box('Side reveal',(hx1+.16,y,DH/2),(.32,.09,DH),'plaster')
 current_group='fixtures'
 # White cupboard front is the observed envelope; its unobserved backing is separate.
 cy=(by0+by1)/2;cw=by1-by0-.12
 box('Cupboard lower body',(bx1+.15,cy,.45),(.30,cw,.9),'ivory')
 box('Cupboard counter',(bx1+.13,cy,.93),(.35,cw+.035,.06),'ivory',.012)
 box('Cupboard upper body',(bx1+.19,cy,2.27),(.26,cw,1.55),'ivory')
 for yy in [cy-cw/4,cy+cw/4]:
  assets.inset_panel(box,'Upper cupboard door',(bx1+.048,yy,2.27),(.025,cw/2-.022,1.49),'ivory',plane='yz')
  a.sphere(sc,'Cupboard knob',(bx1+.026,yy-.17,1.84),(.014,.014,.014),M['brass'])
  for zz in [.2,.47,.74]:
   assets.inset_panel(box,'Drawer',(bx1-.007,yy,zz),(.025,cw/2-.022,.23),'ivory',plane='yz')
   tube('Drawer pull',(bx1-.034,yy-.055,zz),(bx1-.034,yy+.055,zz),.009)
 # Basin, toilet and tub retain their observed wall/order relationships.
 sinkx=-.62;sinky=by0+.26
 assets.basin(sc,a,g,M,(sinkx,sinky,.86),.57,.43,'sink')
 a.cylinder(sc,'Pedestal base',(sinkx,sinky,.07),.16,.14,M['ceramic'],r2=.10)
 a.cylinder(sc,'Pedestal stem',(sinkx,sinky,.47),.10,.7,M['ceramic'],r2=.072)
 for x in [sinkx-.15,sinkx+.15]:tube('Basin tap',(x,by0+.10,.87),(x,by0+.10,.95),.018);box('Cross tap',(x,by0+.10,.95),(.075,.016,.016),'brass')
 tube('Spout riser',(sinkx,by0+.09,.87),(sinkx,by0+.09,1.0),.014)
 tube('Spout outlet',(sinkx,by0+.09,1.0),(sinkx,by0+.22,1.0),.014)
 wx=-1.62;wy=by0+.30
 a.cylinder(sc,'Toilet pedestal',(wx,wy,.17),.15,.34,M['ceramic'],r2=.10)
 assets.basin(sc,a,g,M,(wx,wy,.43),.37,.49,'toilet')
 assets.bowl_ring(sc,g,'Wood toilet seat',(wx,wy,.47),.19,.25,.14,.19,.025,M['wood'])
 current_group='bath_south'
 box('Raised wooden cistern',(wx,by0+.10,2.12),(.42,.20,.33),'wood',.018)
 box('Cistern crown',(wx,by0+.10,2.30),(.47,.24,.04),'trim')
 tube('Flush pipe',(wx,by0+.075,1.96),(wx,by0+.075,.21),.012,'dark')
 tube('Flush bend',(wx,by0+.075,.21),(wx,wy,.21),.012,'dark')
 tube('Pull cord',(wx+.22,by0+.12,2.0),(wx+.22,by0+.12,1.13),.003,'dark')
 current_group='fixtures'
 tx=bx0+.40;ty=(by0+by1)/2
 assets.basin(sc,a,g,M,(tx,ty,.62),.66,1.24,'tub')
 for x in [tx-.21,tx+.21]:
  for y in [ty-.43,ty+.43]:a.sphere(sc,'Claw tub foot',(x,y,.22),(.055,.055,.22),M['brass'])
 tube('Bath tap',(bx0+.12,ty+.45,.57),(bx0+.12,ty+.45,.79),.015)
 tube('Bath spout',(bx0+.12,ty+.45,.79),(bx0+.30,ty+.45,.79),.015)
 current_group='bath_south'
 box('Mirror frame',(sinkx,by0+.026,1.65),(.30,.035,.43),'trim')
 box('Mirror glass',(sinkx,by0+.047,1.65),(.25,.012,.38),'glass')
 current_group='fixtures'
 # Towel rail on the opposite long wall, leaving the doorway clear.
 tube('Towel rail',(-1.97,by1-.08,.91),(-1.05,by1-.08,.91),.016,'ivory')
 for x in [-1.86,-1.36]:box('Folded towel',(x,by1-.075,.72),(.22,.035,.38),'ivory',.009)
 # Oval woven mat: separated from walls; color cues help compare photographs.
 rug=a.cylinder(sc,'Oval bath mat',(-.65,-.68,.009),.47,.018,M['rug']);rug.scale=(1.45,.62,1)
 for rr in [.88,.72,.58]:assets.bowl_ring(sc,g,'Woven mat stripe',(-.65,-.68,.019),.68*rr,.29*rr,.68*rr-.012,.29*rr-.012,.003,M['dark'])
 current_group='ceiling'
 box('Bathroom complete ceiling',((bx0+cabinet_back)/2,(by0+by1)/2,H+.055),(cabinet_back-bx0,by1-by0,.11),'plaster')
 box('Hall complete ceiling',((hx0+hx1)/2,(hy0+hy1)/2,H+.055),(hx1-hx0,hy1-hy0,.11),'plaster')
 marker=a.sphere(sc,'07 camera marker',S['camera'],(.04,.04,.04),M['teal']);marker['group']='marker'
 # Full model saved before any view-only hiding. Source wall vertices never change.
 sc.render.engine='CYCLES';sc.cycles.samples=24 if '--draft' in sys.argv else 72;sc.cycles.use_denoising=True
 prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
 for dev in prefs.devices:dev.use=dev.type=='OPTIX'
 assert any(d.use for d in prefs.devices),'Expected the installed RTX 4060 OptiX device'
 sc.cycles.device='GPU'
 sc.render.threads_mode='FIXED';sc.render.threads=6;sc.cycles.seed=20261107
 sc.render.resolution_x=1300 if '--draft' in sys.argv else 2400;sc.render.resolution_y=1100 if '--draft' in sys.argv else 2000
 sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.render.image_settings.color_mode='RGBA';sc.render.film_transparent=True
 sc.view_settings.view_transform='AgX';sc.view_settings.look='AgX - Medium High Contrast';sc.view_settings.exposure=.4
 world=bpy.data.worlds.new('Soft studio');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(1,1,1,1);world.node_tree.nodes['Background'].inputs[1].default_value=.45;sc.world=world
 target=Vector((-.65,.65,1.0))
 for i,(loc,power,size) in enumerate([((-3,-4,8),900,5),((4,2,7),600,4),((-2,6,7),500,4)]):
  ob=bpy.data.objects.new('Softbox '+str(i),bpy.data.lights.new('Softbox '+str(i),'AREA'));sc.collection.objects.link(ob);ob.location=loc;ob.data.energy=power;ob.data.size=size;ob.rotation_euler=(target-ob.location).to_track_quat('-Z','Y').to_euler()
 # A low-energy interior light is needed for the original camera inspection.
 for i,loc in enumerate([(-1.3,-.7,H-.15),(.15,1.7,H-.15)]):
  ob=bpy.data.objects.new('Interior light '+str(i),bpy.data.lights.new('Interior light '+str(i),'AREA'));sc.collection.objects.link(ob);ob.location=loc;ob.data.energy=60;ob.data.size=.5
 camera=bpy.data.objects.new('Inspection camera',bpy.data.cameras.new('Inspection camera'));sc.collection.objects.link(camera);sc.camera=camera
 def fit_camera(eye):
  camera.location=eye;camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
  bpy.context.view_layer.update();basis=camera.rotation_euler.to_matrix();inv=basis.transposed()
  coords=np.array([tuple(inv@(o.matrix_world@Vector(p)-camera.location)) for o in sc.objects if o.type=='MESH' and not o.hide_render for p in o.bound_box])
  lo=coords.min(axis=0);hi=coords.max(axis=0);mid=(lo+hi)/2
  camera.location+=basis@Vector((mid[0],mid[1],0))
  camera.data.ortho_scale=max((hi[1]-lo[1])*sc.render.resolution_x/sc.render.resolution_y,hi[0]-lo[0])*1.12
  projected=coords[:,:2]-mid[:2]
  half=np.array([camera.data.ortho_scale/2,camera.data.ortho_scale/2*sc.render.resolution_y/sc.render.resolution_x])
  assert np.all(np.max(np.abs(projected),axis=0)<half), 'Camera crops scene'
 camera.data.type='ORTHO';camera.data.ortho_scale=6.5;camera.location=(-6,-8,10);camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
 original={o.name:[tuple(v.co) for v in o.data.vertices] for o in sc.objects if o.get('shell')}
 bpy.ops.wm.save_as_mainfile(filepath=str(WORK/'doorway_complete.blend'))
 views=[]
 for name,eye in [('main',(5,6,30)),('reverse',(-3,-4,30))]:
  for ob in sc.objects:
   ob.hide_render=ob.get('group')=='ceiling'
  camera.data.type='ORTHO';fit_camera(eye)
  assert all(not ob.hide_render for ob in sc.objects if ob.get('shell')), 'A perimeter wall was hidden'
  if name=='main':
   for ob in sc.objects:ob.hide_viewport=ob.get('group')=='ceiling'
   bpy.ops.wm.save_as_mainfile(filepath=str(WORK/'doorway_display.blend'))
   for ob in sc.objects:ob.hide_viewport=False
  sc.render.filepath=str(WORK/f'doorway_{name}.png');bpy.ops.render.render(write_still=True)
  views.append({'view':name,'hidden':[o.name for o in sc.objects if o.hide_render]})
 if '--draft' in sys.argv:return
 # Inspect both spaces from the actual 07 location; complete walls and ceilings restored.
 for ob in sc.objects:ob.hide_render=ob==marker
 sc.render.resolution_x=1300;sc.render.resolution_y=850;camera.data.type='PERSP';camera.data.lens=18;camera.data.sensor_width=36;camera.location=S['camera']
 for name,direction in [('07_hall',(0,1,0)),('07_bath',(0,-1,0)),('07_window',(-1,-.15,-.13))]:
  camera.rotation_euler=Vector(direction).to_track_quat('-Z','Y').to_euler();sc.render.filepath=str(WORK/f'{name}_reprojection.png');bpy.ops.render.render(write_still=True)
 assert original=={o.name:[tuple(v.co) for v in o.data.vertices] for o in sc.objects if o.get('shell')}
 assert len(wall_records)>10 and len(openings)>=6
 assert by1<S['camera'][1]<hy0 and abs(S['camera'][0])<w and S['camera'][2]<DH
 result={'basis':str(ROOT/'analysis_results/doorway_point_folding_20261107/doorway_proportion_fit.json'),'GT_used':False,
 'complete_model':'doorway_complete.blend','display_views':views,'four_sided_walls_visible':True,'shell_vertices_unchanged':True,'openings':openings,
 'camera_inside_threshold':True,'source_wall_objects':wall_records,'stage':'rendered candidate, visual review required',
 'estimated_details':['cupboard depth .32m beyond visible face','window size','left hall side opening','furniture dimensions','door angle'],
 'physical_scope':'Whole bath and hall envelope; adjacent rooms not completed. No raw annotation is remodeled.'}
 (WORK/'VERIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print('DOORWAY_COMPLETE',len(sc.objects),'objects')

if __name__=='__main__':main()
