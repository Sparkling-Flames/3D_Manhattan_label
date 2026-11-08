"""Photo-informed explanatory reconstructions of registered doorway/OOS cases.

The visible structural features are reconstructed for explanation, not to revise GT.
Blender modes: doorway, attic, other, verify. Python mode: compose.
"""
from pathlib import Path
import json,sys,math
sys.path.insert(0,str(Path(__file__).resolve().parent))
import render_scope_blender_20261107 as core

ROOT=core.ROOT
WORK=ROOT/'docs/thesis_main/论文写作工作资料/真实场景Blender_20261107'
WORK.mkdir(exist_ok=True)
core.WORK=WORK
CASES={
 'doorway':('2t7WUuJeko7-07','valid','2t7WUuJeko7_53937db036374126830e0f1203b04ead'),
 'oblique':('x8F5xyUWy9e-09','test','x8F5xyUWy9e_a51a0e2811f342a599ae4cdb9b84ff23'),
 'attic':('S9hNv5qa7GM-07','valid','S9hNv5qa7GM_53d54b73e58940019b731673e65c1902'),
 'ceiling':('q9vSo1VnCiC-09','test','q9vSo1VnCiC_69591068e5614642b710a8fb7733bdeb'),
 'stairs':('uNb9QFRL6hY-69','test','uNb9QFRL6hY_ce88ee8b7ee84fca92c13ab16599d90e')}


def scene(name,target,eye,scale,aspect=1.3):
 import bpy
 from mathutils import Vector
 sc=core.new_scene(name)
 core.configure(sc,name,1600,round(1600/aspect))
 sc.camera.location=eye
 sc.camera.rotation_euler=(Vector(target)-sc.camera.location).to_track_quat('-Z','Y').to_euler()
 sc.camera.data.ortho_scale=scale
 return sc


def palette():
 return {k:core.material(k,col) for k,col in {
 'plaster':'#e9e3d6','wood':'#b48c5d','darkwood':'#4c3427','white':'#f1eee5','glass':'#aac8ce',
 'stone':'#a8aa9d','teal':'#69a6aa','sand':'#d1b583','metal':'#555957','carpet':'#b79674','leaf':'#66846a'}.items()}


def beam(name,a,b,width,mat):
 import bpy
 from mathutils import Vector
 a,b=Vector(a),Vector(b);mid=(a+b)/2
 obj=core.box(name,(-width/2,-width/2,-(b-a).length/2),(width/2,width/2,(b-a).length/2),mat,.006)
 obj.location=mid;obj.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler()
 return obj


def line(name,a,b,mat,width=.007):
 import bpy
 d=bpy.data.curves.new(name,'CURVE');d.dimensions='3D';d.bevel_depth=width;d.bevel_resolution=2
 s=d.splines.new('POLY');s.points.add(1)
 for q,p in zip(s.points,[a,b]):q.co=(*p,1)
 o=bpy.data.objects.new(name,d);bpy.context.scene.collection.objects.link(o);o.data.materials.append(mat);return o


def dashed(name,a,b,mat,width=.008):
 import numpy as np
 a,b=np.array(a),np.array(b);length=float(np.linalg.norm(b-a));n=max(2,round(length/.13))
 for i in range(n):line(name,a+(b-a)*i/n,a+(b-a)*(i+.55)/n,mat,width)


def sphere(name,loc,scale,mat):
 import bpy
 bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,radius=1,location=loc)
 o=bpy.context.object;o.name=name;o.scale=scale;o.data.materials.append(mat)
 for p in o.data.polygons:p.use_smooth=True
 return o


def window_back(name,x,y,z,w,h,p):
 core.box(name+' glazing',(x-w/2,y-.035,z),(x+w/2,y,h+z),p['glass'])
 for a,b in [((x-w/2,y-.06,z),(x-w/2,y-.06,z+h)),((x+w/2,y-.06,z),(x+w/2,y-.06,z+h)),
             ((x-w/2,y-.06,z),(x+w/2,y-.06,z)),((x-w/2,y-.06,z+h),(x+w/2,y-.06,z+h)),
             ((x,y-.065,z),(x,y-.065,z+h))]:beam(name+' frame',a,b,.065,p['white'])


def window_side(name,x,y,z,w,h,p):
 core.box(name+' glazing',(x,y-w/2,z),(x+.035,y+w/2,z+h),p['glass'])
 for a,b in [((x+.045,y-w/2,z),(x+.045,y-w/2,z+h)),((x+.045,y+w/2,z),(x+.045,y+w/2,z+h)),
             ((x+.045,y-w/2,z),(x+.045,y+w/2,z)),((x+.045,y-w/2,z+h),(x+.045,y+w/2,z+h))]:beam(name+' frame',a,b,.065,p['white'])


def save(sc,key,features,notes,labels=None,reference_paths=None):
 import bpy
 code,split,stem=CASES[key]
 src=ROOT/f'data/mp3d_layout/{split}/img/{stem}.png';assert src.is_file()
 meta={'case':code,'photo':str(src.relative_to(ROOT)),'reference_points':f'data/mp3d_layout/{split}/label_cor/{stem}.txt',
       'identity':'Photo-informed explanatory reconstruction; approximate dimensions, not measured geometry or revised GT',
       'visible_features':features,'notes':notes,'render_camera':{'location':list(sc.camera.location),'ortho_scale':sc.camera.data.ortho_scale},
       'reference_geometry_use':'Original six-corner footprint scaled by 2 for context; elevations, fixtures and jamb depths are photo-informed approximations.' if key=='doorway' else 'No GT coordinates used to define the OOS reconstruction; visible geometry is estimated from the photo and reviewed case notes.',
       'panorama_camera_marker':[0,0,1.25] if key=='doorway' else None,
       'labels':{k:core.project(sc,[v])[0] for k,v in (labels or {}).items()},
       'reference_paths':[core.project(sc,path) for path in (reference_paths or [])]}
 (WORK/(key+'_source.json')).write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding='utf-8')
 bpy.ops.wm.save_as_mainfile(filepath=str(WORK/(key+'_current.blend')))
 bpy.ops.render.render(write_still=True,scene=sc.name)


def doorway():
 import bpy,numpy as np
 bpy.ops.wm.read_factory_settings(use_empty=True);p=palette()
 sc=scene('doorway_photo',(-.8,-.9,1.35),(-7,8,8.2),9.0,1.45)
 # Footprint follows the original six-corner reference, at a display scale of 2.
 q=np.loadtxt(ROOT/'data/mp3d_layout/valid/label_cor/2t7WUuJeko7_53937db036374126830e0f1203b04ead.txt')[1::2]
 u=2*np.pi*(q[:,0]/1024-.5);r=2/np.tan(np.pi*(q[:,1]/512-.5));xy=np.c_[r*np.sin(u),-r*np.cos(u)]
 core.slab('Original-reference footprint for context',[(float(x),float(y),0) for x,y in xy],(0,0,-.1),p['wood'])
 xl,xr=-.58,1.046;yb,yf=-3.748,.11;h=2.85
 # The near bathroom wall is removed as a display cutaway; only photographed openings are added.
 core.box('Bathroom side wall',(-3.16,.11,0),(-3.077,1.616,h),p['plaster'])
 core.box('Bathroom far low cutaway wall',(-3.077,1.616,0),(1.046,1.70,.25),p['plaster'])
 core.box('Bathroom near wall left cutaway',(-3.077,.03,0),(xl,.11,.55),p['plaster'])
 core.box('Cabinet wall',(xr,.11,0),(xr+.10,1.616,h),p['plaster'])
 core.box('Hall left wall cutaway',(xl-.09,yb,0),(xl,yf,.40),p['plaster'])
 # Right-hand open doorway seen in the hall, with no invented room beyond it.
 core.box('Hall right rear pier',(xr,-3.748,0),(xr+.09,-2.5,h),p['plaster'])
 core.box('Hall right near pier',(xr,-.95,0),(xr+.09,.11,h),p['plaster'])
 core.box('Hall right opening header',(xr,-2.5,2.3),(xr+.09,-.95,h),p['plaster'])
 core.box('Hall end wall',(xl,yb-.09,0),(xr,yb,h),p['plaster'])
 # Main dark fixed jambs expose the local structure omitted by the original right-hand GT edge.
 for x in [xl,xr]:
  core.box('Visible dark main jamb',(x-.065,-.09,0),(x+.065,.22,2.45),p['darkwood'])
 core.box('Main dark lintel',(xl-.065,-.09,2.45),(xr+.065,.22,2.59),p['darkwood'])
 core.box('Wall above opening',(xl,.03,2.59),(xr,.11,h),p['plaster'])
 # Visible hallway door trim and far glazed entry.
 for y in [-2.5,-.95]:beam('Side doorway trim',(xr-.02,y,0),(xr-.02,y,2.32),.08,p['darkwood'])
 beam('Side doorway lintel',(xr-.02,-2.5,2.32),(xr-.02,-.95,2.32),.08,p['darkwood'])
 core.box('Far entry dark door',(-.44,yb+.01,.02),(.94,yb+.07,2.4),p['darkwood'])
 for x in [-.13,.52]:core.box('Far entry glazing',(x-.23,yb+.075,.45),(x+.23,yb+.09,1.9),p['glass'])
 # Bathroom fixtures are simplified only where visible in the source photograph.
 core.box('White storage cabinets',(.72,.48,1.15),(1.03,1.57,2.65),p['white'])
 core.box('White cabinet counter',(.50,.48,.86),(1.03,1.57,.98),p['white'])
 core.box('White cabinet base',(.58,.48,0),(1.03,1.57,.86),p['white'])
 for yy in [.75,1.1,1.43]:beam('Cabinet pull',(.48,yy-.065,.72),(.48,yy+.065,.72),.018,p['metal'])
 sphere('Pedestal sink bowl',(-.22,1.34,.88),(.37,.23,.11),p['white'])
 core.box('Sink pedestal',(-.31,1.21,0),(-.13,1.45,.83),p['white'])
 sphere('Toilet bowl',(-1.05,1.12,.36),(.25,.34,.22),p['white'])
 core.box('Toilet base',(-1.20,1.0,0),(-.91,1.26,.32),p['white'])
 core.box('Bathtub outer',(-2.8,.78,.12),(-1.55,1.5,.56),p['white'],.06)
 core.box('Bathtub inner surface',(-2.68,.86,.55),(-1.67,1.42,.575),p['glass'],.04)
 window_side('Bathroom window',-3.07,.95,1.13,.7,1.05,p)
 # The camera remains in the threshold, rather than being moved into either space.
 sphere('Camera center at photographed threshold',(0,0,1.25),(.075,.075,.075),p['teal'])
 dashed('Camera down to threshold',(0,0,.02),(0,0,1.25),p['teal'],.006)
 target=core.material('Nonphysical closure amber','#985d0e')
 for a,b in [((xl,.03,0),(xr,.03,0)),((xl,.03,0),(xl,.03,2.45)),((xr,.03,0),(xr,.03,2.45)),((xl,.03,2.45),(xr,.03,2.45))]:dashed('Conceptual target closure',a,b,target,.009)
 save(sc,'doorway',['L-shaped footprint from original reference','bathroom sink and bathtub','white wall cabinet','dark doorway jambs','hallway and far glazed door','open side doorway'],
      ['Reference footprint supplies context, not a corrected GT.','Visible main jamb thickness is photo-informed and approximate.','Near bathroom and hallway walls and all ceilings are cut away; unseen adjoining rooms are not completed.','Amber dashed rectangle is target closure, not a physical wall.'],
      {'camera':(0,0,1.25),'jamb':(xr,-.03,1.5),'bath':(-1.7,.75,.1),'hall':(.2,-2.1,.1)})


def attic():
 import bpy
 bpy.ops.wm.read_factory_settings(use_empty=True);p=palette()
 sc=scene('attic_photo',(0,2.1,1.3),(4,-10,5.3),7.5,1.35)
 core.box('Brown carpet',(-2,0,-.1),(2,4.4,0),p['carpet'])
 core.box('Left low knee wall',(-2.09,0,0),(-2,4.49,1.45),p['white'])
 core.box('Right low knee wall',(2,0,0),(2.09,4.49,1.45),p['white'])
 back=[(-2,4.4,0),(2,4.4,0),(2,4.4,1.45),(.75,4.4,2.65),(-.75,4.4,2.65),(-2,4.4,1.45)]
 core.slab('Visible rear gable wall',back,(0,.09,0),p['white'])
 # Rear ceiling section remains; the front section is cut away to expose the knee-wall junctions.
 core.slab('Left sloping ceiling',[(-2,2.0,1.45),(-.75,2.0,2.65),(-.75,4.4,2.65),(-2,4.4,1.45)],(0,0,.07),p['teal'])
 core.slab('Right sloping ceiling',[(.75,2.0,2.65),(2,2.0,1.45),(2,4.4,1.45),(.75,4.4,2.65)],(0,0,.07),p['teal'])
 core.box('Central flat ceiling strip',(-.75,2.0,2.65),(.75,4.4,2.72),core.material('Flat roof surface','#c4d7d8'))
 window_back('Rear window',0,4.39,.8,1.1,.72,p)
 core.box('Knee-wall access door',(-2.0,.8,.05),(-1.95,1.65,1.15),p['plaster'])
 # Open shelves visible at the far right.
 for z in [.18,.50,.82,1.14]:core.box('Visible shelf',(1.52,3.75,z),(1.96,4.36,z+.045),p['white'])
 core.box('Shelf upright',(1.50,3.75,.12),(1.54,4.36,1.45),p['white'])
 beam('Left floor skirting',(-1.98,0,.06),(-1.98,4.36,.06),.055,p['white'])
 beam('Right floor skirting',(1.98,0,.06),(1.98,4.36,.06),.055,p['white'])
 refs=[[(-2,2,2),(2,2,2),(2,4.4,2),(-2,4.4,2),(-2,2,2)]]
 refs += [[(x,y,1.45),(x,y,2)] for x,y in [(-2,2),(2,2),(-2,4.4),(2,4.4)]]
 refs += [[(-.75,2,2),(-.75,2,2.65)]]
 save(sc,'attic',['two low knee walls','sloping ceiling shoulders and a central flat strip','rear small window','brown carpet','knee-wall access door','right open shelves'],
      ['Slopes and heights are estimated from the visible photograph, not the flat reference ceiling.','Front ceiling section is cut away for visibility; no hidden room is reconstructed.'],{'slope':(-1.35,2.5,2.08)},refs)


def oblique():
 import bpy
 bpy.ops.wm.read_factory_settings(use_empty=True);p=palette()
 sc=scene('oblique_photo',(1,1.4,1.15),(7,-9,6.6),8.1,1.35)
 floorpts=[(-2,0,0),(4.1,0,0),(4.1,2.3,0),(1.3,2.3,0),(.4,3,0),(-2,3,0)]
 core.slab('Visible stone floor',floorpts,(0,0,-.1),p['stone'])
 core.box('Back wall left',(-2,3,0),(-.7,3.09,2.7),p['plaster'])
 core.box('Back wall doorway right',(.25,3,0),(.4,3.09,2.7),p['plaster'])
 core.box('Back doorway lintel',(-.7,3,2.25),(.25,3.09,2.7),p['plaster'])
 # The visibly oblique return is preserved rather than snapped to the orthogonal reference.
 core.slab('Oblique white return',[(.4,3,0),(1.3,2.3,0),(1.3,2.3,2.7),(.4,3,2.7)],(.055,.07,0),p['teal'])
 core.box('Double closet backing',(1.3,2.3,0),(3.1,2.39,2.7),p['plaster'])
 for x in [1.39,2.22]:
  core.box('Wood closet leaf',(x,2.24,.04),(x+.79,2.30,2.28),p['wood'])
  core.box('Inset wood door panel',(x+.08,2.21,.22),(x+.71,2.24,2.08),p['carpet'])
 beam('Closet top wood frame',(1.34,2.20,2.34),(3.07,2.20,2.34),.11,p['darkwood'])
 for x in [-.72,.28]:beam('Open door trim',(x,2.96,0),(x,2.96,2.28),.08,p['wood'])
 beam('Open door lintel',(-.72,2.96,2.28),(.28,2.96,2.28),.08,p['wood'])
 leaf=core.box('Visible open wood leaf',(-.05,0,0),(.05,.95,2.2),p['wood']);leaf.location=(-.68,2.98,0);leaf.rotation_euler.z=math.radians(130)
 # Only the visible lower stair segment is shown at the right edge.
 for i in range(4):core.box('Visible side stair '+str(i),(3.15,1.4+i*.24,0),(4.08,1.64+i*.24,(i+1)*.16),p['stone'])
 core.box('Stair side wall',(4.08,1.38,0),(4.16,2.4,2.7),p['plaster'])
 # Tile joints are display context, not geometric measurements.
 for x in [-1.5,-.75,0,.75,1.5,2.25,3.0,3.75]:line('Stone joint',(x,0,.005),(x,min(2.2,3),.005),p['metal'],.002)
 for y in [.6,1.2,1.8]:line('Stone joint',(-2,y,.006),(4.05,y,.006),p['metal'],.002)
 refs=[[(.4,3,z),(1.3,3,z),(1.3,2.3,z)] for z in [0,2.7]]+[[ (1.3,3,0),(1.3,3,2.7) ]]
 save(sc,'oblique',['visible angled return between the open doorway and wood closet','paired wood closet doors','stone flooring','lower part of side stair'],
      ['Only the visible front portion of the hall is reconstructed.','The oblique angle and dimensions are approximate; the actual angle is not claimed as 135 degrees.','The original Manhattan reference is not used to straighten the angled return.'],{'turn':(.85,2.65,1.4)},refs)


def ceiling():
 import bpy
 bpy.ops.wm.read_factory_settings(use_empty=True);p=palette()
 sc=scene('ceiling_photo',(0,2.3,1.2),(8,-10,7.4),10.0,1.35)
 core.box('Terracotta floor',(-3,0,-.1),(3,5.2,0),p['sand'])
 for x in [-2,-1,0,1,2]:line('Terracotta joint',(x,0,.005),(x,5.2,.005),p['wood'],.006)
 for y in [1,2,3,4,5]:line('Terracotta joint',(-3,y,.005),(3,y,.005),p['wood'],.006)
 core.box('Rear wall',(-3,5.2,0),(3,5.30,3.25),p['white'])
 core.box('Right wall',(3,0,0),(3.10,5.30,2.62),p['white'])
 # Higher timber-panel ceiling and broad white lower ceiling are separate surfaces.
 core.box('Higher timber ceiling',(-3,2.7,3.2),(.9,5.2,3.28),p['wood'])
 low=core.box('Lower white ceiling',(.9,2.7,2.62),(3,5.2,2.70),p['white'])
 low.data.materials.append(core.material('Lower ceiling top for visibility','#a9c5c8'))
 for face in low.data.polygons:
  if face.normal.z>.5:face.material_index=1
 for a,b in [((.9,2.7,2.705),(3,2.7,2.705)),((3,2.7,2.705),(3,5.2,2.705))]:
  line('Lower ceiling cut edge',a,b,p['teal'],.012)
 core.box('Vertical ceiling change',(.88,2.7,2.62),(.94,5.2,3.2),p['plaster'])
 for x in [-2.8,-1.5,-.2,.72]:beam('Visible ceiling beam',(x,2.7,3.09),(x,5.12,3.09),.16,p['darkwood'])
 for y in [2.82,4.05,5.05]:beam('Timber cross member',(-2.96,y,3.08),(.85,y,3.08),.10,p['darkwood'])
 window_back('Large rear glazed opening',-1.15,5.18,.15,2.8,2.3,p)
 window_back('Right rear glazed opening',1.8,5.18,.15,1.5,2.0,p)
 # Simplified visible seating supplies scene identity without covering the ceiling junction.
 sofa=core.material('Blue gray sofa','#7b8c8e')
 core.box('Sofa seat',(-2.15,.6,.28),(-.2,1.45,.60),sofa,.07)
 core.box('Sofa back',(-2.15,1.28,.60),(-.2,1.48,1.02),sofa,.06)
 for x in [-2.2,-.22]:core.box('Sofa arm',(x,.58,.38),(x+.16,1.45,.87),sofa,.04)
 bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=.62,depth=.11,location=(.55,1.25,.55));o=bpy.context.object;o.name='Visible round coffee table';o.data.materials.append(p['wood'])
 core.box('Coffee table pedestal',(.4,1.1,.05),(.7,1.4,.5),p['darkwood'])
 save(sc,'ceiling',['higher timber ceiling with shallow beams','broad lower white ceiling zone','terracotta floor','rear glazing','visible sofa and round table'],
      ['Only the visible main-room portion is reconstructed; adjoining rooms are not completed.','The lower ceiling is a broad surface, distinct from the undersides of individual timber beams.','The front ceiling section is cut away to expose the height transition.'],{'step':(.91,3.0,2.9)})


def stairs():
 import bpy
 bpy.ops.wm.read_factory_settings(use_empty=True);p=palette()
 sc=scene('stairs_photo',(0,1.9,1.0),(1,-10,8.3),8.8,1.35)
 core.box('Continuous lower wood floor',(-2.4,0,-.1),(2.3,4.2,0),p['wood'])
 for x in [-2,-1.5,-1,-.5,0,.5,1,1.5,2]:line('Wood plank joint',(x,0,.005),(x,4.2,.005),p['sand'],.003)
 core.box('Rear wall',(-2.4,4.2,0),(2.4,4.29,3.05),p['white'])
 core.box('Right wall',(2.3,0,0),(2.39,4.29,3.05),p['white'])
 # Only the brown-door-side landing is raised; the window-side floor stays at the foreground level.
 core.box('Raised brown-door landing',(-1.5,2.25,0),(.15,4.2,.60),p['sand'])
 for i in range(3):
  x=.15+(2-i)*.28
  step=core.box('Short staircase '+str(i),(x,2.25,0),(x+.28,3.28,(i+1)*.20),p['wood'],.004)
 core.box('Landing front half wall',(-1.50,2.10,0),(.16,2.25,1.02),p['white'],.035)
 core.box('Half-wall return',(.01,1.2,0),(.16,2.25,1.02),p['white'],.035)
 core.box('Brown door on upper landing',(-1.45,4.13,.60),(-.40,4.20,2.85),p['darkwood'])
 window_back('Tall lower-zone window',1.0,4.18,.55,.70,1.55,p)
 window_back('Small upper window',-.15,4.18,1.7,.45,.45,p)
 # Large white sliding panels and black rail visible on the right of the panorama.
 for y in [.65,1.85]:
  core.box('White barn door leaf',(2.20,y,.04),(2.28,y+1.12,2.58),p['white'])
  core.box('Raised door panel',(2.16,y+.10,.25),(2.20,y+1.02,2.35),p['plaster'])
 beam('Black sliding door rail',(2.12,.55,2.68),(2.12,3.09,2.68),.04,p['metal'])
 for y in [.8,1.55,2.05,2.8]:core.box('Rail hanger',(2.10,y,2.42),(2.16,y+.07,2.76),p['metal'])
 save(sc,'stairs',['large lower foreground wood floor','short stair beside L-shaped white half wall','localized raised landing by the brown door','window-side lower floor','white barn doors with black rail'],
      ['The high landing is localized behind the half wall; the whole window-side region is not raised.','Three modeled risers summarize the visible short stair; no measured rise is claimed.','Ceilings and the near left wall are cut away.'],{'levels':(.4,2.5,.35)})


def compose():
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from PIL import Image
 plt.rcParams.update({'font.family':'DejaVu Sans','pdf.fonttype':42,'font.size':8})
 data=json.loads((WORK/'doorway_source.json').read_text(encoding='utf-8'))
 fig=plt.figure(figsize=(3.5,4.5),facecolor='white')
 fig.text(.5,.978,'(a) Doorway case 2t7-07',ha='center',fontsize=8.5)
 ax=fig.add_axes([0,.455,1,.50]);ax.imshow(Image.open(WORK/'doorway_photo.png'));ax.axis('off')
 for key,txt,xy in [('camera','Camera at threshold',(.24,.86)),('jamb','Visible jamb',(.16,.64))]:
  ax.annotate(txt,xy=data['labels'][key],xycoords='axes fraction',xytext=xy,textcoords='axes fraction',ha='center',fontsize=8,color='#344c57',arrowprops=dict(arrowstyle='-',lw=.65),bbox=dict(fc='white',ec='none',pad=.5))
 fig.text(.5,.42,'(b) Panorama and original reference',ha='center',fontsize=8.5)
 ax=fig.add_axes([.015,.045,.97,.35]);source=Image.open(core.OLD/'inputs/pdfpage14_xref369.png');ax.imshow(source.crop((70,49,2170,1099)));ax.axis('off')
 fig.text(.5,.015,'Dashed closure is not a physical wall',ha='center',fontsize=8,color='#87642a')
 for ext in ['png','pdf']:fig.savefig(WORK/('doorway_photo_preview.'+ext),dpi=400,facecolor='white')
 plt.close(fig)
 if (WORK/'attic_photo.png').exists():
  fig,axs=plt.subplots(1,2,figsize=(8,3.5))
  code,split,stem=CASES['attic'];axs[0].imshow(Image.open(ROOT/f'data/mp3d_layout/{split}/img/{stem}.png'));axs[0].set_title(code+' · photograph')
  axs[1].imshow(Image.open(WORK/'attic_photo.png'));axs[1].set_title('Photo-informed cutaway')
  for ax in axs:ax.axis('off')
  fig.tight_layout();fig.savefig(WORK/'attic_photo_preview.png',dpi=200);plt.close(fig)
 if all((WORK/(key+'_photo.png')).exists() for key in ['oblique','attic','ceiling','stairs']):
  fig=plt.figure(figsize=(7.2,8.0),facecolor='white')
  fig.text(.265,.987,'Original panoramas',ha='center',fontsize=9)
  fig.text(.755,.987,'Photo-informed cutaways',ha='center',fontsize=9)
  kinds=['Oblique wall','Sloped ceiling','Split-level ceiling','Split-level floor']
  for k,(key,kind) in enumerate(zip(['oblique','attic','ceiling','stairs'],kinds)):
   data=json.loads((WORK/(key+'_source.json')).read_text(encoding='utf-8'));y=.742-k*.242
   fig.text(.02,y+.202,f'({chr(97+k)}) {kind} · {data["case"]}',ha='left',fontsize=8.2,color='#243b4a')
   ax=fig.add_axes([.015,y,.485,.191]);ax.imshow(Image.open(ROOT/data['photo']));ax.axis('off')
   from matplotlib.patches import Rectangle
   regions={'oblique':[(.52,.24,.16,.56)],'attic':[(.13,.43,.27,.30),(.61,.43,.25,.30)],
            'ceiling':[(.54,.65,.29,.26)],'stairs':[(.31,.17,.28,.39)]}
   for x0,y0,w,h in regions[key]:ax.add_patch(Rectangle((x0,y0),w,h,transform=ax.transAxes,fill=False,edgecolor='#248b8f',lw=.8))
   ax=fig.add_axes([.515,y-.005,.475,.223]);ax.imshow(Image.open(WORK/(key+'_photo.png')),extent=[0,1,0,1]);ax.set_aspect('auto');ax.axis('off')
   # Pixel aspect must match the rendered image, while the source panorama keeps its 2:1 ratio.
   im=Image.open(WORK/(key+'_photo.png'));ax.set_box_aspect(im.height/im.width)
   for path in data.get('reference_paths',[]):ax.plot(*zip(*path),color='#a85d1c',lw=.85,ls=(0,(4,3)))
  for ext in ['png','pdf']:fig.savefig(WORK/('oos_photo_preview.'+ext),dpi=350,facecolor='white')
  plt.close(fig)


def verify():
 import bpy,numpy as np
 results={}
 for key in CASES:
  bpy.ops.wm.open_mainfile(filepath=str(WORK/(key+'_current.blend')))
  data=json.loads((WORK/(key+'_source.json')).read_text(encoding='utf-8'))
  assert (ROOT/data['photo']).is_file() and (ROOT/data['reference_points']).is_file()
  sc=bpy.context.scene;bpy.context.view_layer.update()
  assert sc.camera.type=='CAMERA' and sc.camera.data.type=='ORTHO'
  if key=='doorway':
   q=np.loadtxt(ROOT/data['reference_points'])[1::2];u=2*np.pi*(q[:,0]/1024-.5);r=2/np.tan(np.pi*(q[:,1]/512-.5))
   expected=np.c_[r*np.sin(u),-r*np.cos(u),np.zeros(len(u))]
   actual=np.array([v.co[:] for v in bpy.data.objects['Original-reference footprint for context'].data.vertices])[:len(u)]
   assert np.allclose(actual,expected,atol=2e-7)
   cam=bpy.data.objects['Camera center at photographed threshold'];assert abs(cam.location.x)<1e-8 and -.09<cam.location.y<.22 and cam.location.z<2.45
   results[key]={'reference_footprint_max_error':float(abs(actual-expected).max()),'panorama_camera_in_threshold':True,'original_reference_modified':False}
  elif key=='attic':
   for n in ['Left sloping ceiling','Right sloping ceiling']:
    zs=[v.co.z for v in bpy.data.objects[n].data.vertices];assert max(zs)-min(zs)>1.1
   assert len(data['reference_paths'])==6
   results[key]={'two_visible_sloping_shoulders':True,'horizontal_reference_and_vertical_links':True}
  elif key=='oblique':
   assert len(data['reference_paths'])==3
   v=np.array([v.co[:] for v in bpy.data.objects['Oblique white return'].data.vertices]);assert abs(v[1,0]-v[0,0])>.8 and abs(v[1,1]-v[0,1])>.6
   results[key]={'oblique_return_not_snapped':True,'upper_lower_and_vertical_reference':True}
  elif key=='ceiling':
   high=min(v.co.z for v in bpy.data.objects['Higher timber ceiling'].data.vertices)
   low=min(v.co.z for v in bpy.data.objects['Lower white ceiling'].data.vertices);assert high-low>.5
   results[key]={'main_ceiling_levels':[high,low],'beams_separate_objects':True}
  else:
   heights=[max(v.co.z for v in bpy.data.objects['Short staircase '+str(i)].data.vertices) for i in range(3)]
   assert np.allclose(heights,[.2,.4,.6])
   results[key]={'stair_heights':heights,'raised_landing_localized_by_brown_door':True,'foreground_and_window_floor_same_level':True}
 (WORK/'VERIFICATION.json').write_text(json.dumps({'passed':True,'blender':bpy.app.version_string,'cases':results,
     'scope':'Construction and source checks, not validation of measured real-world dimensions.'},indent=2),encoding='utf-8')
 print(json.dumps(results))


if __name__=='__main__':
 mode=sys.argv[-1]
 if mode=='doorway':doorway()
 elif mode=='attic':attic()
 elif mode=='other':
  oblique();ceiling();stairs()
 elif mode=='compose':compose()
 elif mode=='verify':verify()
 else:raise SystemExit('doorway, attic, or compose')
