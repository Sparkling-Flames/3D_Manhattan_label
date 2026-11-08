"""Render the existing doorway and four OOS constructions as readable cutaways.

Blender: -b --python this_file.py -- doorway|oos
Python: this_file.py compose
These are explanatory constructions; no annotation coordinates are repaired.
"""
from pathlib import Path
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'docs/thesis_main/论文写作工作资料/Blender_门洞与OOS_20261107'
FIG = ROOT / 'docs/thesis_main/论文提纲_LaTeX_20261028/figures'
OLD = ROOT / 'docs/thesis_main/论文写作工作资料/Dot交付审查_20261106/Paper_Figures_4_5_6_10_CURRENT_ONLY_20261106/03_Figure10'
WORK.mkdir(exist_ok=True)


def rgb(value):
    vals = [int(value[i:i+2], 16)/255 for i in (1, 3, 5)]
    return tuple(v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in vals)+(1,)


def material(name, color, rough=.7):
    import bpy
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = rgb(color)
    bsdf.inputs['Roughness'].default_value = rough
    return mat


def mesh(name, vertices, faces, mat, bevel=0):
    import bpy
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new('Small display edge bevel', 'BEVEL')
        mod.width, mod.segments = bevel, 2
    return obj


def box(name, lo, hi, mat, bevel=.008):
    x,y,z=lo; X,Y,Z=hi
    return mesh(name, [(x,y,z),(X,y,z),(X,Y,z),(x,Y,z),(x,y,Z),(X,y,Z),(X,Y,Z),(x,Y,Z)],
                [(0,3,2,1),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7)], mat, bevel)


def slab(name, points, offset, mat):
    n=len(points)
    vertices=list(points)+[tuple(a+b for a,b in zip(v, offset)) for v in points]
    faces=[tuple(range(n-1,-1,-1)),tuple(range(n,n*2))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return mesh(name,vertices,faces,mat,.005)


def configure(scene, name, width=1400, height=1400):
    import bpy
    scene.render.engine='CYCLES'
    scene.cycles.samples=72
    scene.cycles.use_denoising=True
    scene.cycles.device='CPU'
    scene.cycles.seed=20261107
    scene.render.threads_mode='FIXED';scene.render.threads=8
    scene.render.resolution_x=width;scene.render.resolution_y=height
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.render.image_settings.color_mode='RGBA'
    scene.render.film_transparent=True
    scene.view_settings.view_transform='Standard'
    scene.view_settings.look='Medium High Contrast'
    scene.view_settings.exposure=0
    scene.render.filepath=str(WORK/(name+'.png'))
    if not scene.world:
        scene.world=bpy.data.worlds.new(name+'_world')
    scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(1,1,1,1)
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.65


def new_scene(name):
    import bpy
    from mathutils import Vector
    sc=bpy.data.scenes.new(name);bpy.context.window.scene=sc
    configure(sc,name)
    target=Vector((1.45,1.15,1.4))
    cam=bpy.data.objects.new(name+'_camera',bpy.data.cameras.new(name+'_camera'))
    sc.collection.objects.link(cam)
    cam.location=target+Vector((7,-10,7.5))
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.type='ORTHO';cam.data.ortho_scale=5.65;sc.camera=cam
    for loc,power,size in [((1,-4,8),470,5),((6,3,6),240,4)]:
        lamp=bpy.data.objects.new(name+'_softbox',bpy.data.lights.new(name+'_softbox','AREA'))
        sc.collection.objects.link(lamp);lamp.location=loc;lamp.data.energy=power;lamp.data.shape='DISK';lamp.data.size=size
        lamp.rotation_euler=(target-lamp.location).to_track_quat('-Z','Y').to_euler()
    return sc


def project(scene, coords):
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector
    import bpy
    bpy.context.view_layer.update()
    return [[float(v.x),float(v.y)] for v in (world_to_camera_view(scene,scene.camera,Vector(p)) for p in coords)]


def render_doorway():
    import bpy
    import numpy as np
    bpy.ops.wm.open_mainfile(filepath=str(OLD/'output/Figure10_editable.blend'))
    sc=bpy.data.scenes['Fig10_doorway_SCHEMATIC'];bpy.context.window.scene=sc
    original={o.name:np.array([v.co[:] for v in o.data.vertices]) for o in sc.objects if o.type=='MESH'}
    configure(sc,'doorway_render',1800,1161)
    colors={'Room A illustrative floor':'#b1cecc','Room B illustrative floor':'#dbcaa9',
            'Door frame actual display thickness':'#98866c','Boundary wall neutral':'#e1e2df',
            'Uniform neutral walls':'#e3e5e3'}
    for name,color in colors.items():
        m=bpy.data.materials.get(name)
        if m: m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=rgb(color)
    for o in sc.objects:
        if o.type=='MESH' and o.get('schematic_not_measured',False):
            mod=o.modifiers.new('Readable construction edges','BEVEL');mod.width=.012;mod.segments=3
    trim=material('Context skirting ivory','#f2f0e9')
    box('Left back skirting',(-3,1.76,.01),(-.12,1.8,.12),trim,.004)
    box('Right back skirting',(.12,1.76,.01),(3,1.8,.12),trim,.004)
    camera=bpy.data.objects['Camera center under lintel']
    assert abs(camera.location.x)<1e-8 and -.66<camera.location.y<.66 and camera.location.z<2.18
    plane=bpy.data.objects['NONPHYSICAL target closure plane']
    assert len(plane.data.polygons)==1 and not plane.modifiers and not plane['physical_wall']
    assert all(np.array_equal(original[n],np.array([v.co[:] for v in bpy.data.objects[n].data.vertices])) for n in original)
    labels={'camera':(0,0,1.25),'closure':(-.105,.5,.45),'left':(-1.75,-.7,.02),'right':(1.7,-.7,.02)}
    meta={'source_blend':str(OLD/'output/Figure10_editable.blend'),'original_mesh_coordinates_unchanged':True,
          'camera_under_lintel':list(camera.location),'target_is_zero_thickness_nonphysical':True,
          'projected_labels':{k:project(sc,[v])[0] for k,v in labels.items()},
          'source_photo':str(OLD/'inputs/pdfpage14_xref369.png'),'photo_crop':[70,49,2170,1099]}
    (WORK/'doorway_source.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    bpy.ops.wm.save_as_mainfile(filepath=str(WORK/'doorway_current.blend'))
    bpy.ops.render.render(write_still=True,scene=sc.name)


def render_oos():
    import bpy
    import numpy as np
    bpy.ops.wm.read_factory_settings(use_empty=True)
    wall=material('Neutral wall plaster','#d5dfdf')
    floor=material('Neutral floor','#e4e9e6')
    high=material('Higher surface teal','#81b9bb')
    low=material('Lower surface sand','#dfc69b')
    riser=material('Step vertical faces','#54989d')
    specs={}
    def base(name,roof=2.6):
        sc=new_scene(name)
        box('Floor slab',(0,0,-.1),(3,2.4,0),floor)
        box('Back wall',(0,2.4,-.1),(3.08,2.49,roof),wall)
        box('Left wall',(-.09,0,-.1),(0,2.49,roof),wall)
        return sc
    def finish(sc,lines,assertions):
        specs[sc.name]={'reference_paths':[{'coords':coords,'screen':project(sc,coords),'color':color} for coords,color in lines],
                        'assertions':assertions,'camera_location':list(sc.camera.location),'ortho_scale':sc.camera.data.ortho_scale}
        bpy.ops.render.render(write_still=True,scene=sc.name)
    sc=new_scene('oos_a')
    footprint=[(0,0),(3,0),(3,1.2),(1.6,2.4),(0,2.4)]
    slab('Oblique room floor',[(x,y,0) for x,y in footprint],(0,0,-.1),floor)
    box('Left wall',(-.09,0,-.1),(0,2.49,2.6),wall)
    box('Back wall',(0,2.4,-.1),(1.6,2.49,2.6),wall)
    slab('Oblique wall',[(3,1.2,0),(1.6,2.4,0),(1.6,2.4,2.6),(3,1.2,2.6)],(.065,.075,0),high)
    paths=[([(3,1.2,z),(3,2.4,z),(1.6,2.4,z)],'#b56627') for z in (0,2.6)]
    paths.append(([(3,2.4,0),(3,2.4,2.6)],'#b56627'))
    assert np.dot([0,1.2,0],[-1.4,0,0])==0
    finish(sc,paths,{'reference_corner_is_orthogonal':True,'reference_vertical_included':True})
    sc=new_scene('oos_b')
    box('Floor slab',(0,0,-.1),(3,2.4,0),floor)
    slab('Back wall',[(0,2.4,0),(3,2.4,0),(3,2.4,3.05),(0,2.4,2.05)],(0,.09,0),wall)
    box('Left wall',(-.09,0,-.1),(0,2.49,2.05),wall)
    ceiling=[(0,0,2.05),(3,0,3.05),(3,2.4,3.05),(0,2.4,2.05)]
    slab('Sloped ceiling',ceiling,(0,0,.07),high)
    ref=[(0,0,2.6),(3,0,2.6),(3,2.4,2.6),(0,2.4,2.6),(0,0,2.6)]
    paths=[(ref,'#b56627')]+[([(x,y,2.05+x/3),(x,y,2.6)],'#b56627') for x,y in [(0,0),(3,0),(3,2.4),(0,2.4)]]
    paths.append(([(3,0,0),(3,0,2.6)],'#8398a0'))
    assert np.ptp(np.array(ref)[:,2])==0
    finish(sc,paths,{'reference_is_horizontal':True,'all_four_height_links_included':True})
    sc=new_scene('oos_c')
    box('Floor slab',(0,0,-.1),(3,2.4,0),floor)
    box('Left wall',(-.09,0,-.1),(0,2.49,3),wall)
    box('Back high wall',(0,2.4,-.1),(1.5,2.49,3),wall)
    box('Back low wall',(1.5,2.4,-.1),(3.08,2.49,2.2),wall)
    box('Higher horizontal ceiling',(0,0,3),(1.5,2.4,3.07),high)
    box('Lower horizontal ceiling',(1.5,0,2.2),(3,2.4,2.27),low)
    box('Ceiling step vertical face',(1.47,0,2.2),(1.5,2.4,3),riser,.003)
    finish(sc,[],{'ceiling_levels':[3,2.2],'step_vertical':True,'different_level_materials':True})
    sc=base('oos_d',3)
    box('Long lower floor',(0,0,0),(3,1.05,.006),low,.002)
    box('Higher floor platform',(0,1.65,0),(3,2.4,.8),high)
    for i in range(4):
        y=1.05+i*.15;h=(i+1)*.2
        box('Stair riser '+str(i),(0,y,0),(3,y+.15,h),riser,.004)
        box('Stair tread '+str(i),(0,y,h),(3,y+.15,h+.006),high,.002)
    assert 1.05>.6 and abs(4*.2-.8)<1e-9
    finish(sc,[],{'floor_levels':[0,.8],'steps':4,'lower_floor_length':1.05,'stair_run':.6,'upper_floor_length':.75})
    (WORK/'oos_source.json').write_text(json.dumps({'source_script':'tools/thesis_main/analysis/render_oos_schematic.py',
        'identity':'Four generic constructions, not measured annotations','panels':specs},indent=2),encoding='utf-8')
    bpy.ops.wm.save_as_mainfile(filepath=str(WORK/'oos_current.blend'))


def compose():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8.4,'pdf.fonttype':42})
    data=json.loads((WORK/'doorway_source.json').read_text(encoding='utf-8'))
    fig=plt.figure(figsize=(3.5,4.5),facecolor='white')
    fig.text(.5,.978,'(a) Camera at the room boundary',ha='center',fontsize=8.2)
    ax=fig.add_axes([0,.455,1,.50]);ax.imshow(Image.open(WORK/'doorway_render.png'));ax.axis('off')
    for key,txt,xy,col in [('camera','Camera under lintel',(.24,.8),'#344c57'),('closure','Target closure\n(nonphysical)',(.80,.20),'#946221')]:
        ax.annotate(txt,xy=data['projected_labels'][key],xycoords='axes fraction',xytext=xy,textcoords='axes fraction',ha='center',va='center',fontsize=7.1,color=col,arrowprops=dict(arrowstyle='-',lw=.65,color=col),bbox=dict(fc='white',ec='none',pad=.6))
    for key,txt in [('left','Left room'),('right','Right room')]:
        x,y=data['projected_labels'][key];ax.text(x,y-.03,txt,transform=ax.transAxes,ha='center',fontsize=7.1,color='#34515a',bbox=dict(fc='white',ec='none',pad=.3))
    fig.text(.5,.459,'Open passage; the amber plane is not a wall.',ha='center',fontsize=6.8,color='#87642a')
    fig.text(.5,.415,'(b) Separate actual case: 2t7-07',ha='center',fontsize=8.2)
    ax=fig.add_axes([.015,.042,.97,.353]);source=Image.open(data['source_photo']);assert source.size==(2240,1120)
    ax.imshow(source.crop(tuple(data['photo_crop'])));ax.axis('off')
    fig.text(.5,.015,'Original reference overlay retained',ha='center',fontsize=7,color='#59656b')
    for ext in ['png','pdf']:fig.savefig(FIG/('doorway_boundary_3d.'+ext),dpi=400,facecolor='white')
    plt.close(fig)
    data=json.loads((WORK/'oos_source.json').read_text(encoding='utf-8'))
    fig,axes=plt.subplots(2,2,figsize=(7,6.45))
    titles=['(a) Oblique wall','(b) Sloped ceiling','(c) Split-level ceiling','(d) Split-level floor']
    for ax,name,title in zip(axes.flat,['oos_a','oos_b','oos_c','oos_d'],titles):
        ax.imshow(Image.open(WORK/(name+'.png')),extent=[0,1,0,1]);ax.axis('off')
        for line in data['panels'][name]['reference_paths']:
            ax.plot(*zip(*line['screen']),color=line['color'],lw=.95,ls=(0,(4,3)),solid_capstyle='round')
        ax.set_title(title,fontsize=10.5,color='#243b4a',pad=0)
    fig.subplots_adjust(left=.015,right=.985,top=.955,bottom=.01,wspace=.035,hspace=.045)
    for ext in ['png','pdf']:fig.savefig(FIG/('oos_geometry_3d.'+ext),dpi=400,facecolor='white')
    plt.close(fig)
    print('Composed doorway and OOS figures; source records and editable scenes are in',WORK)


def verify_saved():
    import bpy
    import numpy as np
    bpy.ops.wm.open_mainfile(filepath=str(WORK/'doorway_current.blend'))
    camera=bpy.data.objects['Camera center under lintel']
    plane=bpy.data.objects['NONPHYSICAL target closure plane']
    assert abs(camera.location.x)<1e-8 and -.66<camera.location.y<.66 and camera.location.z<2.18
    assert len(plane.data.polygons)==1 and not plane.modifiers
    assert np.ptp([v.co.x for v in plane.data.vertices])==0
    bpy.ops.wm.open_mainfile(filepath=str(WORK/'oos_current.blend'))
    for name in ['oos_a','oos_b','oos_c','oos_d']:
        bpy.context.window.scene=bpy.data.scenes[name]
        bpy.context.view_layer.update()
    cams=[bpy.data.scenes[n].camera for n in ['oos_a','oos_b','oos_c','oos_d']]
    assert all(np.allclose(cams[0].matrix_world,c.matrix_world) and cams[0].data.ortho_scale==c.data.ortho_scale for c in cams[1:])
    def z_bounds(name):
        return min(v.co.z for v in bpy.data.objects[name].data.vertices),max(v.co.z for v in bpy.data.objects[name].data.vertices)
    assert np.allclose(z_bounds('Higher horizontal ceiling'),[3,3.07])
    assert np.allclose(z_bounds('Lower horizontal ceiling'),[2.2,2.27])
    assert np.allclose([z_bounds('Stair riser '+str(i))[1] for i in range(4)],[.2,.4,.6,.8])
    lower=bpy.data.objects['Long lower floor']
    assert np.isclose(np.ptp([v.co.y for v in lower.data.vertices]),1.05)
    report={'passed':True,'blender':bpy.app.version_string,'saved_scene_checks':['camera inside doorway below lintel','zero-thickness target plane','shared OOS orthographic camera','two horizontal ceiling levels','four equal-height stair risers','lower-floor run exceeds stair run'],
            'display_only':'Small outward wall/roof thicknesses and edge bevels clarify generic constructions; no original annotation is modified.'}
    (WORK/'saved_scene_checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':
    mode=sys.argv[-1]
    if mode=='doorway':render_doorway()
    elif mode=='oos':render_oos()
    elif mode=='compose':compose()
    elif mode=='verify':verify_saved()
    else:raise SystemExit('Expected doorway, oos, compose, or verify')
