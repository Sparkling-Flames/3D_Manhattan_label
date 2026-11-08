"""Source-boundary doorway candidate. Appearance/openings are explicitly estimated.

Blender modes: render, export. Ordinary Python: audit.
"""
from pathlib import Path
import sys,json,math
import numpy as np
ROOT=Path('D:/Work/HOHONET')
WORK=ROOT/'docs/thesis_main/论文写作工作资料/真实场景Blender_20261107/doorway_sop_rebuild'
WORK.mkdir(exist_ok=True)
DOT=ROOT/'docs/thesis_main/论文写作工作资料/Dot交付审查_20261106/Paper_Figures_4_5_6_10_CURRENT_ONLY_20261106/02_Figure6_latest/output'
SOURCE=ROOT/'data/mp3d_layout/valid/label_cor/2t7WUuJeko7_53937db036374126830e0f1203b04ead.txt'
PHOTO=ROOT/'data/mp3d_layout/valid/img/2t7WUuJeko7_53937db036374126830e0f1203b04ead.png'
# s is distance along an unchanged source wall, z is in camera-height units.
OPENINGS={0:[(1.35176,1.76701,-1,.34,'Right side doorway')],
          2:[(.03343,.49204,-.60,.46,'Bathroom sash window')],
          5:[(.03558,.78413,-1,.62,'Hall end door and transom')]}

def build():
 import bpy
 from mathutils import Vector
 # Reuse Dot's pure geometry helpers without its image/composition imports.
 import ast,types
 sys.path.insert(0,str(DOT))
 g=types.ModuleType('geometry_core');g.__dict__.update(bpy=bpy,np=np,math=math,Vector=Vector)
 tree=ast.parse((DOT/'geometry_core.py').read_text(encoding='utf-8'))
 wanted={'project','reproject','area','cross','in_tri','inside','triangulate','rgb','matte','mesh','line'}
 selected=ast.Module(body=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in wanted],type_ignores=[])
 exec(compile(selected,str(DOT/'geometry_core.py'),'exec'),g.__dict__);sys.modules['geometry_core']=g
 import appearance_assets as a
 bpy.ops.wm.read_factory_settings(use_empty=True)
 sc=bpy.context.scene;sc.name='2t7-07 source-boundary photo-guided candidate'
 p=np.loadtxt(SOURCE)
 assert p.shape==(12,2) and np.isfinite(p).all() and np.allclose(p[::2,0],p[1::2,0])
 assert ((p[:,0]>=0)&(p[:,0]<1024)).all() and ((p[:,1]>=0)&(p[:,1]<512)).all()
 f,t=g.project(p);n=len(f)
 M={k:a.material(k,c,r,mt) for k,c,r,mt in [
 ('plaster','#d8d1bf',.86,0),('ivory','#e1ded3',.53,0),('wood','#684734',.46,0),
 ('oak','#a78760',.65,0),('ceramic','#eeeae0',.25,0),('brass','#82735b',.32,.7),
 ('glass','#a4b4b4',.20,.1),('dark','#292522',.75,0),('trim','#5c4030',.45,0),
 ('cut','#c6c9c5',.8,0),('wallpaper','#ccc7b5',.82,0),('teal','#197d87',.45,0)]}
 floor=a.wood();bs=floor.node_tree.nodes.get('Principled BSDF')
 for node in floor.node_tree.nodes:
  if node.type=='TEX_BRICK':
   node.inputs['Color1'].default_value=g.rgb('#a58a65');node.inputs['Color2'].default_value=g.rgb('#baa17d');node.inputs['Mortar'].default_value=g.rgb('#8f795b')
 g.mesh('SOURCE floor',f.tolist(),g.triangulate(f),floor,sc.collection)
 g.mesh('DISPLAY outward floor slab',f.tolist()+(f-[0,0,.035]).tolist(),[(i,(i+1)%n,(i+1)%n+n,i+n)for i in range(n)],M['cut'],sc.collection)
 normals=[]
 for A,B in zip(f,np.roll(f,-1,axis=0)):
  u=(B-A)/np.linalg.norm(B[:2]-A[:2]);normals.append(np.array([u[1],-u[0],0]))
 offsets=[]
 for i in range(n):
  v=normals[i-1]+normals[i];offsets.append(v*.035/np.dot(v,normals[i]))
 offsets=np.array(offsets)
 wallrecords=[]
 def box(name,center,size,mat='ivory',bevel=.003,angle=0):
  o=a.box(sc,'APPEARANCE '+name,center,size,M[mat] if isinstance(mat,str) else mat,bevel,angle)
  o['identity']='Photo-guided estimated appearance, not GT';return o
 def tube(name,A,B,r,mat='brass'):
  v=Vector(B)-Vector(A);o=a.cylinder(sc,'APPEARANCE '+name,(Vector(A)+Vector(B))/2,r,v.length,M[mat]);o.rotation_euler=v.to_track_quat('Z','Y').to_euler();return o
 # Source wall domains are partitioned around explicit estimated openings.
 for i in range(n):
  j=(i+1)%n;A=f[i];B=f[j];L=np.linalg.norm((B-A)[:2]);u=(B-A)/L;normal=-normals[i]
  def point(s,z):v=A+u*s;v[2]=z;return v
  def top(s):return float(t[i,2]+(t[j,2]-t[i,2])*s/L)
  ops=OPENINGS.get(i,[]);xs=sorted(set([0.,L]+[x for op in ops for x in op[:2]]))
  for s0,s1 in zip(xs[:-1],xs[1:]):
   op=next((q for q in ops if q[0]<(s0+s1)/2<q[1]),None)
   bands=[(-1,op[2]),(op[3],None)]if op else[(-1,None)]
   for z0,z1 in bands:
    zL,zR=(top(s0),top(s1))if z1 is None else(z1,z1)
    if min(zL,zR)<=z0+1e-9:continue
    inner=[point(s0,z0),point(s1,z0),point(s1,zR),point(s0,zL)]
    outer=[v+offsets[i]*(1-s/L)+offsets[j]*s/L for v,s in zip(inner,[s0,s1,s1,s0])]
    ob=g.mesh('VISIBLE source wall '+str(i),[v.tolist()for v in inner+outer],[(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)],M['plaster'],sc.collection)
    ob['source_edge']=i;ob['source_inner_face']=0;ob['s_range']=json.dumps([s0,s1]);ob['z_band']=json.dumps([z0,z1]);ob['identity']='Source plane and per-corner top preserved; subtract registered photo-estimated openings only'
    wallrecords.append(ob.name)
  ang=math.atan2(u[1],u[0])
  intervals=[];starts=0.
  for op in sorted(ops):
   if op[2]<=-1+1e-8:intervals.append((starts,op[0]));starts=op[1]
  intervals.append((starts,L))
  for ss,ee in intervals:
   if ee-ss>.01:
    for z,w,d in [(-.965,.07,.014),(-.92,.016,.023)]:box('source-following skirting',point((ss+ee)/2,z)+normal*d/2,(ee-ss,d,w),'trim',.002,ang)
  # Bath lower wainscoting only in unbroken spans; decorative surface sits inside source wall.
  if i in [1,2,3]:
   for ss in np.arange(.035,L-.015,.065):
    if any(o[0]-.02<ss<o[1]+.02 and o[2]<-.35 for o in ops):continue
    box('bath vertical wainscot seam',point(ss,-.69)+normal*.005,(.003,.005,.48),'ivory',0,ang)
   railbreaks=sorted(set([0.,L]+[x for op in ops if op[2]<-.43<op[3] for x in op[:2]]))
   for ss,ee in zip(railbreaks[:-1],railbreaks[1:]):
    if not any(op[0]<(ss+ee)/2<op[1] and op[2]<-.43<op[3] for op in ops):box('bath chair rail',point((ss+ee)/2,-.43)+normal*.014,(ee-ss,.028,.025),'ivory',.003,ang)
  for s0,s1,z0,z1,name in ops:
   mid=(s0+s1)/2;W=s1-s0;H=z1-z0
   # Window/door borders sit around real gaps rather than on intact wall panels.
   mat='ivory' if i==2 else 'trim'
   for extra,d,thick in [(0,.025,.035),(.018,.016,.018),(.032,.008,.013)]:
    for ss in [s0-extra,s1+extra]:box(name+' side moulding',point(ss,(z0+z1)/2)+normal*d,(thick,.025,H+.04+2*extra),mat,.002,ang)
    for zz in ([z1+extra]if z0<=-1 else[z0-extra,z1+extra]):box(name+' head/sill moulding',point(mid,zz)+normal*d,(W+.06+2*extra,.03,thick),mat,.002,ang)
   if i==2:
    box(name+' recessed glazing',point(mid,(z0+z1)/2)-normal*.018,(W-.025,.012,H-.025),'glass',.001,ang)
    for ss in [s0+.015,s1-.015,mid]:box(name+' sash mullion',point(ss,(z0+z1)/2),( .016,.025,H),'ivory',.001,ang)
    for zz in [z0+.01,z1-.01,(z0+z1)/2]:box(name+' sash rail',point(mid,zz),(W,.025,.018),'ivory',.001,ang)
   elif i==5:
    # Two long glazed lights and a separate transom, with a real frame lattice.
    leafTop=.33
    for ss in [s0+.025,s1-.025,mid]:box('hall door stile',point(ss,(-1+leafTop)/2),( .045,.055,1+leafTop),'wood',.004,ang)
    for zz,hh in [(-.94,.12),(-.78,.055),(.29,.08),(.36,.055),(.61,.045)]:box('hall door horizontal rail',point(mid,zz),(W,.055,hh),'wood',.004,ang)
    for ss in [(s0+mid)/2,(mid+s1)/2]:box('hall tall glass',point(ss,-.225),(W/2-.052,.015,1.04),'glass',.002,ang)
    box('hall transom glazing',point(mid,.49),(W-.05,.014,.20),'glass',.002,ang)
    for ss in np.arange(s0+.1,s1-.05,.12):box('transom lead vertical',point(ss,.49)+normal*.01,(.004,.006,.18),'ivory',0,ang)
    for zz in [.445,.535]:box('transom lead horizontal',point(mid,zz)+normal*.01,(W-.05,.006,.004),'ivory',0,ang)
    a.sphere(sc,'APPEARANCE hall door handle',point(s0+.07,-.36)+normal*.06,(.018,.022,.018),M['brass'])
   else:
    # Estimated open leaf hangs from the far jamb. No neighboring room is fabricated.
    hinge=point(s0,-1)-normal*.02;direction=(u*.57-normal*.82);leafang=math.atan2(direction[1],direction[0]);center=hinge+direction*(W*.48);center[2]=(z0+z1)/2
    panel_door(sc,a,M,box,name+' open panel leaf',center,W*.96,H,.035,leafang)
 # Near camera doorway is a separate photo-estimated structural detail omitted by GT.
 framey=.025;frameL=-.2901;frameR=.5225;head=.86
 for x in [frameL,frameR]:
  box('threshold jamb estimated',(x,framey,(-1+head)/2),(.045,.105,1+head),'trim',.004)
  box('threshold casing estimated',(x,framey+.06,(-1+head)/2),(.066,.026,1+head+.04),'wood',.003)
 box('threshold lintel estimated',((frameL+frameR)/2,framey,head),(.88,.105,.075),'trim',.004)
 # The large near leaf lies against the left corridor wall, supported by the panorama.
 panel_door(sc,a,M,box,'near open panel leaf',(-.247,-.35,-.09),.78,1.80,.042,-math.pi/2+.045)
 for zz in [-.78,.12,.70]:box('near leaf hinge',(-.29,.04,zz),(.025,.035,.05),'brass',.002)
 # Bathroom basin: square-ish rim, depressed bowl, pedestal and three-piece tap.
 basin(sc,a,g,M,center=(-.23,.615,-.44),width=.40,depth=.28,kind='sink')
 a.cylinder(sc,'APPEARANCE pedestal basin foot',(-.23,.66,-.96),.105,.065,M['ceramic'],r2=.065)
 a.cylinder(sc,'APPEARANCE tapered basin pedestal',(-.23,.66,-.72),.060,.43,M['ceramic'],r2=.040)
 for xx in [-.34,-.12]:
  a.cylinder(sc,'APPEARANCE basin tap base',(xx,.72,-.405),.016,.035,M['brass'])
  box('cross tap handle',(xx,.72,-.385),(.055,.009,.009),'brass',.003)
 tube('basin faucet upright',(-.23,.73,-.43),(-.23,.73,-.34),.012)
 tube('basin faucet spout',(-.23,.73,-.34),(-.23,.67,-.34),.012)
 # Raised flush cistern, flush pipe, hollow seat and pedestal bowl.
 wc=(-.78,.59)
 a.cylinder(sc,'APPEARANCE WC pedestal',(*wc,-.90),.09,.18,M['ceramic'],r2=.065)
 basin(sc,a,g,M,center=(*wc,-.72),width=.26,depth=.34,kind='toilet')
 bowl_ring(sc,g,'APPEARANCE wood toilet seat',(*wc,-.685),.13,.17,.095,.128,.018,M['wood'])
 box('high wooden cistern',(-.78,.752,.42),(.29,.115,.21),'wood',.013)
 box('cistern overhanging lid',(-.78,.749,.535),(.32,.135,.022),'trim',.004)
 tube('long cistern flush pipe',(-.78,.77,.31),(-.78,.77,-.91),.009,'dark')
 tube('WC flush bend',(-.78,.77,-.91),(-.78,.64,-.91),.009,'dark')
 tube('cistern pull cord',(-.64,.73,.33),(-.64,.73,-.22),.002,'dark')
 # Rounded freestanding bathtub beside the actual window.
 basin(sc,a,g,M,center=(-1.30,.43,-.70),width=.39,depth=.62,kind='tub')
 for xx in [-1.43,-1.17]:
  for yy in [.23,.63]:a.sphere(sc,'APPEARANCE tub foot',(xx,yy,-.96),(.032,.028,.05),M['brass'])
 tube('tub tap upright',(-1.43,.65,-.71),(-1.43,.65,-.59),.01)
 tube('tub tap spout',(-1.43,.65,-.59),(-1.36,.65,-.59),.01)
 # Built-in cupboard on the bathroom's right wall, supported by the full panorama.
 box('cabinet lower carcass',(.425,.49,-.71),(.19,.58,.55),'ivory',.006)
 box('cabinet countertop',(.405,.49,-.415),(.25,.62,.035),'ivory',.007)
 box('cabinet upper carcass',(.445,.49,.385),(.15,.62,.95),'ivory',.006)
 for yy in [.34,.64]:
  inset_panel(box,'upper cupboard door',(.362,yy,.385),(.017,.285,.91),'ivory',plane='yz')
  a.sphere(sc,'APPEARANCE cupboard knob',(.344,yy-.115,.10),(.008,.009,.009),M['brass'])
 for zz in [-.50,-.66,-.83]:
  for yy in [.34,.64]:
   inset_panel(box,'drawer front',(.322,yy,zz),(.02,.275,.14),'ivory',plane='yz')
   tube('drawer handle',(.302,yy-.035,zz),(.302,yy+.035,zz),.006)
 # Photo-visible shallow mirror above basin, avoiding invented openings.
 box('basin mirror frame',(-.23,.797,-.02),(.27,.018,.40),'trim',.004)
 box('basin mirror surface',(-.23,.784,-.02),(.24,.008,.37),'glass',.001)
 a.sphere(sc,'PANORAMA camera center',(0,0,0),(.035,.035,.035),M['teal'])
 # Freeze source/appearance identities and render parameters.
 sc.render.engine='CYCLES';sc.cycles.samples=128;sc.cycles.use_denoising=True;sc.cycles.device='CPU';sc.cycles.seed=20261107
 sc.render.threads_mode='FIXED';sc.render.threads=8;sc.render.resolution_x=2400;sc.render.resolution_y=2100;sc.render.resolution_percentage=100
 sc.render.image_settings.file_format='PNG';sc.render.image_settings.color_mode='RGBA';sc.render.film_transparent=True
 sc.view_settings.view_transform='AgX';sc.view_settings.look='AgX - Medium High Contrast';sc.view_settings.exposure=.4
 wo=bpy.data.worlds.new('Neutral studio');wo.use_nodes=True;wo.node_tree.nodes['Background'].inputs['Color'].default_value=(1,1,1,1);wo.node_tree.nodes['Background'].inputs['Strength'].default_value=.42;sc.world=wo
 center=np.array([-.5,-.5,-.03])
 for k,(loc,power,size) in enumerate([((-3,1,5),500,4),((3,3,5),300,5),((0,-3,4),100,3)]):
  data=bpy.data.lights.new('Soft area '+str(k),'AREA');data.energy=power;data.size=size;o=bpy.data.objects.new(data.name,data);sc.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector(center)-o.location).to_track_quat('-Z','Y').to_euler()
 camd=bpy.data.cameras.new('DISPLAY render camera');cam=bpy.data.objects.new(camd.name,camd);sc.collection.objects.link(cam);camd.type='ORTHO';sc.camera=cam
 metadata={'case':'2t7WUuJeko7-07','source':str(SOURCE),'photo':str(PHOTO),'source_points':p.tolist(),'floor':f.tolist(),'top':t.tolist(),'camera_height_unit':1,'panorama_camera':[0,0,0],
   'openings':OPENINGS,'visible_wall_objects':wallrecords,'wall_thickness':.035,'full_wall_height':True,'cutaway_edges':[],
   'appearance_identity':'Photo-guided estimates of openings, threshold, fixtures and materials, not revised GT or dimension measurements.',
   'uncertainties':['Right threshold jamb is visible in photo but not explicitly represented by the six-corner reference.','Side room beyond the open door is not reconstructed.','Door/window extents were estimated from image rays intersecting existing reference planes.','Open door angles, fixture dimensions and depth are visual estimates.']}
 (WORK/'candidate_source.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
 for name,az in [('main',65),('reverse',245)]:
  elev=72*math.pi/180;aaz=az*math.pi/180;cam.location=Vector(center)+Vector((math.cos(elev)*math.cos(aaz),math.cos(elev)*math.sin(aaz),math.sin(elev)))*10
  cam.rotation_euler=(Vector(center)-cam.location).to_track_quat('-Z','Y').to_euler();camd.ortho_scale=4.4
  sc.render.filepath=str(WORK/('candidate_'+name+'.png'));bpy.ops.wm.save_as_mainfile(filepath=str(WORK/('candidate_'+name+'.blend')))
  bpy.ops.render.render(write_still=True)

def inset_panel(box,name,c,size,mat,plane='xy'):
 x,y,z=c;w,d,h=size
 if plane=='yz':
  box(name+' inset',c,(w,d-.025,h-.025),mat,.002)
  for yy in [y-d/2+.012,y+d/2-.012]:box(name+' stile',(x-.006,yy,z),(w,.024,h),mat,.002)
  for zz in [z-h/2+.012,z+h/2-.012]:box(name+' rail',(x-.006,y,zz),(w,d,.024),mat,.002)

def panel_door(sc,a,M,box,name,c,W,H,D,ang):
 c=np.array(c);u=np.array([math.cos(ang),math.sin(ang),0]);normal=np.array([-u[1],u[0],0])
 box(name+' slab',c,(W,D,H),'wood',.005,ang)
 for face in [-1,1]:
  for xx in [-W*.24,W*.24]:
   for zz,hh in [(-H*.26,H*.36),(H*.20,H*.45)]:
    cc=c+u*xx+normal*D*.54*face+np.array([0,0,zz]);pw=W*.39
    box(name+' raised panel',cc,(pw,.012,hh),'trim',.004,ang)
    for dx in [-pw/2,pw/2]:box(name+' panel vertical bead',cc+u*dx+normal*.009*face,(.012,.012,hh),'wood',.002,ang)
    for dz in [-hh/2,hh/2]:box(name+' panel horizontal bead',cc+np.array([0,0,dz])+normal*.009*face,(pw,.012,.012),'wood',.002,ang)
  a.sphere(sc,'APPEARANCE '+name+' knob',c+u*W*.39+normal*.05*face,(.017,.017,.017),M['brass'])

def rounded_loop(cx,cy,z,rx,ry,power=4,N=64):
 out=[]
 for q in np.linspace(0,2*math.pi,N,endpoint=False):
  out.append((cx+rx*math.copysign(abs(math.cos(q))**(2/power),math.cos(q)),cy+ry*math.copysign(abs(math.sin(q))**(2/power),math.sin(q)),z))
 return out

def bowl_ring(sc,g,name,c,rx,ry,ix,iy,h,mat,power=2):
 x,y,z=c;loops=[rounded_loop(x,y,z,rx,ry,power),rounded_loop(x,y,z,ix,iy,power),rounded_loop(x,y,z-h,ix,iy,power),rounded_loop(x,y,z-h,rx,ry,power)]
 N=len(loops[0]);v=sum(loops,[]);faces=[]
 for k in range(4):
  for j in range(N):faces.append((k*N+j,k*N+(j+1)%N,((k+1)%4)*N+(j+1)%N,((k+1)%4)*N+j))
 ob=g.mesh(name,v,faces,mat,sc.collection)
 for p in ob.data.polygons:p.use_smooth=True
 return ob

def basin(sc,a,g,M,center,width,depth,kind):
 x,y,z=center;rx=width/2;ry=depth/2;power=4 if kind=='sink' else 3 if kind=='tub' else 2
 drop=.10 if kind=='sink' else .23 if kind=='tub' else .17
 specs=[(rx*.65,ry*.65,z-drop),(rx,ry,z-.015),(rx*.97,ry*.97,z+.012),(rx*.82,ry*.82,z+.007),(rx*.43,ry*.43,z-drop+.055)]
 loops=[rounded_loop(x,y,zz,xx,yy,power)for xx,yy,zz in specs];N=64;v=sum(loops,[]);faces=[]
 for k in range(len(loops)-1):
  for j in range(N):faces.append((k*N+j,k*N+(j+1)%N,(k+1)*N+(j+1)%N,(k+1)*N+j))
 faces.append(tuple(range((len(loops)-1)*N,len(loops)*N)));faces.append(tuple(range(N-1,-1,-1)))
 ob=g.mesh('APPEARANCE '+kind+' hollow ceramic bowl',v,faces,M['ceramic'],sc.collection)
 for q in ob.data.polygons:q.use_smooth=True
 a.cylinder(sc,'APPEARANCE '+kind+' drain',(x,y,z-drop+.057),.012,.004,M['brass'])

def export():
 import bpy
 from mathutils import Vector
 out={}
 for view in ['main','reverse']:
  bpy.ops.wm.open_mainfile(filepath=str(WORK/('candidate_'+view+'.blend')));bpy.context.view_layer.update()
  objects=[]
  for ob in bpy.context.scene.objects:
   if 'source_edge' not in ob:continue
   assert ob.type=='MESH' and not ob.hide_render and not ob.modifiers
   objects.append({'name':ob.name,'edge':int(ob['source_edge']),'vertices':[(ob.matrix_world@v.co)[:]for v in ob.data.vertices],
       'faces':[list(p.vertices)for p in ob.data.polygons],'s_range':json.loads(ob['s_range']),'z_band':json.loads(ob['z_band']),
       'alpha':ob.data.materials[0].node_tree.nodes.get('Principled BSDF').inputs['Alpha'].default_value})
  out[view]=objects
 (WORK/'actual_visible_wall_meshes.json').write_text(json.dumps(out,indent=2),encoding='utf-8')

def audit():
 from shapely.geometry import Polygon,box as sbox
 from shapely.ops import unary_union
 p=np.loadtxt(SOURCE);bottom=[];top=[]
 for a,b in zip(p[::2],p[1::2]):
  u=2*math.pi*(a[0]/1024-.5);r=1/math.tan(math.pi*(b[1]/512-.5));bottom.append([r*math.sin(u),-r*math.cos(u),-1]);top.append([r*math.sin(u),-r*math.cos(u),-r*math.tan(math.pi*(a[1]/512-.5))])
 f,t=np.array(bottom),np.array(top);allviews=json.loads((WORK/'actual_visible_wall_meshes.json').read_text());results={}
 for view,obs in allviews.items():
  planeerr=0;outwarderr=0;coverage=0;toperr=0;group={i:[]for i in range(6)};reproject=[]
  for ob in obs:
   i=ob['edge'];A=f[i];B=f[(i+1)%6];L=np.linalg.norm((B-A)[:2]);u=(B-A)/L;out=np.array([u[1],-u[0],0]);vs=np.array(ob['vertices']);face=vs[np.array(ob['faces'][0])]
   planeerr=max(planeerr,float(abs((face-A)@out).max()));outwarderr=max(outwarderr,float(abs((vs[4:]-vs[:4])@out-.035).max()))
   s=(face-A)@u;group[i].append(Polygon(np.c_[s,face[:,2]]))
   if ob['z_band'][1] is None:toperr=max(toperr,float(abs(face[2:,2]-(t[i,2]+(t[(i+1)%6,2]-t[i,2])*s[2:]/L)).max()))
   assert ob['alpha']==1
  for i,polys in group.items():
   L=np.linalg.norm((f[(i+1)%6]-f[i])[:2]);expected=Polygon([(0,-1),(L,-1),(L,t[(i+1)%6,2]),(0,t[i,2])])
   for a,b,z0,z1,_ in OPENINGS.get(i,[]):expected=expected.difference(sbox(a,z0,b,z1))
   actual=unary_union(polys);coverage=max(coverage,actual.symmetric_difference(expected).area)
  # Reproject visible mesh source endpoints, not a hidden canonical copy.
  for i in range(6):
   vertices=np.vstack([ob['vertices'] for ob in obs if ob['edge']==i]);target=np.vstack([f[i],t[i]])
   for j,want in enumerate(target):
    v=vertices[np.argmin(np.linalg.norm(vertices-want,axis=1))];x=(math.atan2(v[0],-v[1])/(2*math.pi)+.5)*1024;y=(.5-math.atan2(v[2],math.hypot(v[0],v[1]))/math.pi)*512
    src=p[2*i+(1 if j==0 else 0)];dx=abs(x-src[0]);dx=min(dx,1024-dx);reproject.append(max(dx,abs(y-src[1])))
  assert planeerr<3e-7 and outwarderr<3e-7 and coverage<2e-6 and toperr<3e-7 and max(reproject)<2e-5
  results[view]={'actual_visible_shell_plane_error_h':planeerr,'outward_thickness_error_h':outwarderr,'per_corner_top_interpolation_error_h':toperr,'registered_openings_only_symmetric_difference_area_h2':coverage,'visible_endpoint_reprojection_error_px':max(reproject),'all_six_wall_segments_present':True}
 for a,b in zip(allviews['main'],allviews['reverse']):assert a==b
 results['scope']='Independent checks of saved actual visible wall pieces against six source walls, with registered estimated openings subtracted. Does not validate physical realism or measured appearance dimensions.'
 (WORK/'WALL_GEOMETRY_VERIFICATION.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print(json.dumps(results))

def compose():
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from PIL import Image
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9})
 fig=plt.figure(figsize=(8,8.15),facecolor='white')
 fig.text(.5,.982,'(a) Original panorama: 2t7WUuJeko7-07',ha='center',fontsize=10)
 ax=fig.add_axes([.015,.49,.97,.47]);ax.imshow(Image.open(PHOTO));ax.axis('off')
 for x,view,label in [(.01,'main','(b) Complete source walls: main view'),(.51,'reverse','(c) Complete source walls: reverse view')]:
  ax=fig.add_axes([x,.055,.48,.415]);ax.imshow(Image.open(WORK/('candidate_'+view+'.png')));ax.axis('off')
  fig.text(x+.24,.468,label,ha='center',fontsize=8.5)
 fig.text(.5,.025,'Reference-constrained walls; photo-estimated openings and appearance.',ha='center',fontsize=8.5,color='#455258')
 fig.savefig(WORK/'candidate_review.png',dpi=300,facecolor='white');plt.close(fig)

if __name__=='__main__':
 mode=sys.argv[-1]
 if mode=='render':build()
 elif mode=='export':export()
 elif mode=='audit':audit()
 elif mode=='compose':compose()
 else:raise SystemExit('render, export, audit')
