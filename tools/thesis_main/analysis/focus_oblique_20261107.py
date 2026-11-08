"""Oblique-wall local-room presentation; material pass preserves the rebuilt meshes.

Blender: -b --python this_file.py -- render
Python: this_file.py compose
"""
from pathlib import Path
import ast, json, math, sys

ROOT=Path(__file__).resolve().parents[3]
CASE=ROOT/'docs/thesis_main/论文写作工作资料/OOS分步重建_20261107/oblique'
OUT=CASE/'focus_review'
DOT=ROOT/'docs/thesis_main/论文写作工作资料/Dot交付审查_20261106/Paper_Figures_4_5_6_10_CURRENT_ONLY_20261106/02_Figure6_latest/output'

def load_dot():
    import bpy, numpy as np
    from types import SimpleNamespace
    env={'bpy':bpy,'np':np,'math':math}
    tree=ast.parse((DOT/'geometry_core.py').read_text(encoding='utf-8'))
    selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'rgb','matte'}]
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(DOT/'geometry_core.py'),'exec'),env)
    env['g']=SimpleNamespace(rgb=env['rgb'],matte=env['matte'])
    tree=ast.parse((DOT/'appearance_assets.py').read_text(encoding='utf-8'))
    selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'material','fabric','wood','box'}]
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(DOT/'appearance_assets.py'),'exec'),env)
    return SimpleNamespace(**{k:env[k] for k in ['rgb','material','fabric','wood','box']})

def render(final=False):
    import bpy,numpy as np
    from mathutils import Vector
    from bpy_extras.object_utils import world_to_camera_view
    OUT.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(CASE/'reconstruction.blend'))
    sc=bpy.context.scene;dot=load_dot()
    bpy.data.collections['FULL_MODEL'].hide_render=False
    bpy.data.collections['DISPLAY_CUTAWAY_ONLY'].hide_render=False
    bpy.data.collections['DIAGNOSTIC_WIREFRAME'].hide_render=True
    for obj in sc.objects:
        if 'ceiling' in obj.name.lower():obj.hide_render=True
    for obj in list(sc.objects):
        if obj.name.startswith(('Photo door edge beading','Photo narrow panel rail','Photo continuous crown')):bpy.data.objects.remove(obj,do_unlink=True)
    original_camera=(sc.camera.location.copy(),sc.camera.rotation_euler.copy(),sc.camera.data.ortho_scale)
    original={o.name:(np.array([v.co[:] for v in o.data.vertices]),np.array(o.matrix_world)) for o in sc.objects if o.type=='MESH'}
    plaster=dot.fabric('Photo warm grey pink plaster','#c8afa0',170)
    plaster.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.78
    wood=dot.material('Photo horizontal timber grain','#806046',.43)
    n=wood.node_tree.nodes;l=wood.node_tree.links;bs=n.get('Principled BSDF')
    geo=n.new('ShaderNodeNewGeometry');mapping=n.new('ShaderNodeVectorMath');mapping.operation='MULTIPLY';mapping.inputs[1].default_value=(.9,.9,35)
    l.new(geo.outputs['Position'],mapping.inputs[0]);noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=3;noise.inputs['Detail'].default_value=3.5;noise.inputs['Roughness'].default_value=.7;l.new(mapping.outputs[0],noise.inputs['Vector'])
    ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.22;ramp.color_ramp.elements[0].color=dot.rgb('#5c4835');ramp.color_ramp.elements[1].position=.78;ramp.color_ramp.elements[1].color=dot.rgb('#a18a64')
    l.new(noise.outputs['Fac'],ramp.inputs[0]);l.new(ramp.outputs['Color'],bs.inputs['Base Color'])
    bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.16;bump.inputs['Distance'].default_value=.003;l.new(noise.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs[0],bs.inputs['Normal']);bs.inputs['Coat Weight'].default_value=.12
    dark=dot.material('Photo walnut joinery edge','#5d4935',.4)
    metal=dot.material('Photo metal corner guard','#7d9391',.27,.72)
    stone=dot.wood();stone.name='Photo grey stone floor world metre scale'
    n=stone.node_tree.nodes;l=stone.node_tree.links;br=n.get('Brick Texture');br.offset=0;br.offset_frequency=1
    br.inputs['Brick Width'].default_value=.43;br.inputs['Row Height'].default_value=.43;br.inputs['Mortar Size'].default_value=.0014;br.inputs['Mortar'].default_value=dot.rgb('#6c7068')
    br.inputs['Color1'].default_value=dot.rgb('#969b8d');br.inputs['Color2'].default_value=dot.rgb('#acada0')
    n.get('Vector Math.001').inputs[1].default_value=(8,8,8);n.get('Noise Texture').inputs['Scale'].default_value=2;n.get('Principled BSDF').inputs['Roughness'].default_value=.45
    # Fine broken stone veins use world coordinates, preserving the same physical scale on all treads.
    vor=n.new('ShaderNodeTexVoronoi');vor.feature='DISTANCE_TO_EDGE';vor.inputs['Scale'].default_value=6.2;l.new(n.get('Geometry').outputs['Position'],vor.inputs['Vector'])
    mask=n.new('ShaderNodeValToRGB');mask.color_ramp.elements[0].position=.002;mask.color_ramp.elements[0].color=(.13,.13,.13,1);mask.color_ramp.elements[1].position=.006;mask.color_ramp.elements[1].color=(0,0,0,1);l.new(vor.outputs['Distance'],mask.inputs[0])
    mix=n.new('ShaderNodeMixRGB');l.new(mask.outputs[0],mix.inputs[0]);l.new(n.get('Mix (Legacy)').outputs[0],mix.inputs[1]);mix.inputs[2].default_value=dot.rgb('#c8c8b8');l.new(mix.outputs[0],n.get('Principled BSDF').inputs['Base Color'])
    for obj in sc.objects:
        if obj.type!='MESH':continue
        name=obj.name.lower()
        if 'stone floor joint' in name or ('cornice' in name and 'far stair' not in name):obj.hide_render=True
        elif 'corner metal' in name:obj.data.materials.clear();obj.data.materials.append(metal)
        elif 'wall' in name or 'perimeter' in name or 'facet' in name or 'return' in name:
            if 'baseboard' not in name and 'cornice' not in name:
                obj.data.materials.clear();obj.data.materials.append(plaster)
                for mod in list(obj.modifiers):
                    if mod.type=='BEVEL':obj.modifiers.remove(mod)
        elif 'stone floor' in name or 'stair tread' in name:obj.data.materials.clear();obj.data.materials.append(stone)
        elif 'leaf' in name:obj.data.materials.clear();obj.data.materials.append(wood)
        if ('casing' in name or 'panel rail' in name or 'horizontal panel' in name) and 'far landing' not in name:
            obj.data.materials.clear();obj.data.materials.append(dark)
        if 'panel rail' in name or 'horizontal panel' in name:obj.hide_render=True
    leaves=[o for o in sc.objects if o.type=='MESH' and (o.name=='Observed open timber leaf' or o.name.startswith('Double wooden doors leaf '))]
    assert len(leaves)==3,'Only the three actual door leaves receive panel beading'
    for obj in leaves:
        verts=[obj.matrix_world@Vector(v.co) for v in obj.data.vertices[:4]]
        assert verts[2].z-verts[0].z>2,'A trim bar was mistaken for a door leaf'
        a,b=verts[0],verts[1];edge=b-a;length=edge.length;tangent=edge.normalized();normal=Vector((-tangent.y,tangent.x,0));angle=math.atan2(tangent.y,tangent.x)
        # Narrow edge beading gives the observed door panel depth without moving the door leaf.
        for offset in [.045,length-.045]:
            center=a+tangent*offset-normal*.012;center.z=(verts[0].z+verts[2].z)/2
            dot.box(sc,'Photo door edge beading',center,(.018,.018,verts[2].z-verts[0].z-.09),dark,.003,angle)
        for z in [verts[0].z+.055,verts[0].z+.91,verts[2].z-.055]:
            center=(a+b)/2-normal*.012;center.z=z
            dot.box(sc,'Photo narrow panel rail',center,(length-.09,.018,.018),dark,.003,angle)
    # Continuous mitered crown follows the actual perimeter, leaving the stair opening connected.
    points=np.array([(1.31,-2.35),(1.31,-2.72),(-1.2,-2.72),(-1.2,1.49),(-.18,1.49),(.07,1.46),(.76,.65),(1.38,.61),(1.24,-1.01),(1.31,-1.38)])
    directions=np.diff(points,axis=0);directions/=np.linalg.norm(directions,axis=1)[:,None]
    normals=np.stack([-directions[:,1],directions[:,0]],axis=1);miters=[]
    for i in range(len(points)):
        if i==0:m=normals[0]
        elif i==len(points)-1:m=normals[-1]
        else:
            m=normals[i-1]+normals[i];m=m/float(m@normals[i])
        miters.append(m)
    for k,(height,width,thickness) in enumerate([(2.525,.06,.044),(2.477,.037,.025)]):
        vv=[]
        for q,m in zip(points,miters):
            center=q-m*.022
            a,b=center-m*width/2,center+m*width/2
            vv.extend([(*a,height),(*b,height),(*b,height+thickness),(*a,height+thickness)])
        faces=[(3,2,1,0)]
        for i in range(len(points)-1):
            faces.extend([(i*4+j,(i+1)*4+j,(i+1)*4+(j+1)%4,i*4+(j+1)%4) for j in range(4)])
        last=4*(len(points)-1);faces.append(tuple(last+j for j in range(4)))
        mesh=bpy.data.meshes.new('Continuous crown profile');mesh.from_pydata(vv,[],faces);mesh.update();obj=bpy.data.objects.new('Photo continuous crown '+str(k),mesh);sc.collection.objects.link(obj);obj.data.materials.append(bpy.data.materials['white'])
        bevel=obj.modifiers.new('Fine joined crown edge','BEVEL');bevel.width=.002;bevel.segments=3
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
    for device in prefs.devices:device.use=device.type=='OPTIX'
    sc.cycles.device='GPU';sc.cycles.samples=72 if final else 48;sc.render.resolution_percentage=100
    W,H=(2400,1800) if final else (1600,1200)
    sc.render.resolution_x=W;sc.render.resolution_y=H;sc.render.film_transparent=True
    sc.view_settings.view_transform='AgX';sc.view_settings.look='AgX - Medium High Contrast';sc.view_settings.exposure=.15
    cam=sc.camera;cam.data.type='ORTHO'
    def frame_selected(eye,target,names,pad):
        cam.location=eye;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();bpy.context.view_layer.update()
        right=cam.rotation_euler.to_quaternion()@Vector((1,0,0));up=cam.rotation_euler.to_quaternion()@Vector((0,1,0));pts=[]
        for obj in sc.objects:
            if obj.type=='MESH' and any(obj.name.startswith(s) for s in names):pts.extend(obj.matrix_world@Vector(b) for b in obj.bound_box)
        xs=[p.dot(right) for p in pts];ys=[p.dot(up) for p in pts]
        cam.location+=right*((min(xs)+max(xs))/2-cam.location.dot(right))+up*((min(ys)+max(ys))/2-cam.location.dot(up))
        cam.data.ortho_scale=max(max(xs)-min(xs),(max(ys)-min(ys))*4/3)*pad
    focus=['Main corridor stone floor','Open doorway wall','Door jamb','NONORTHOGONAL','Metal edged','Double door wall','Left corridor return','Near corridor perimeter','Stair left wall','Stair right wall','Stair tread','Observed open timber leaf']
    close=focus
    specs=[('A_room_focus',(-4,-6,14),(.1,-.4,1.2),focus,1.08),('B_wall_detail',(-3,-5,11),(.3,.5,1.2),close,1.08)]
    if final:specs.append(('C_reverse_focus',(5,4,13),(.1,-.4,1.2),focus,1.08))
    panels=[]
    for name,eye,target,names,pad in specs:
        frame_selected(eye,target,names,pad);bpy.context.view_layer.update()
        points=[(.07,1.46,0),(.76,.65,0),(.76,.65,2.57),(.07,1.46,2.57)]
        projected=[world_to_camera_view(sc,cam,Vector(p)) for p in points]
        panels.append({'name':name,'wall_polygon_xy':[[float(p.x)*W,(1-float(p.y))*H] for p in projected],'camera_xyz':list(cam.location),'camera_rotation':list(cam.rotation_euler),'ortho_scale':cam.data.ortho_scale,'image_size':[W,H]})
        sc.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
    assert all(np.array_equal(v,np.array([w.co[:] for w in bpy.data.objects[name].data.vertices])) and np.array_equal(m,np.array(bpy.data.objects[name].matrix_world)) for name,(v,m) in original.items())
    frame_selected(specs[1][1],specs[1][2],specs[1][3],specs[1][4]);bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'oblique_focus.blend'))
    if final:
        for obj in sc.objects:
            if 'ceiling' in obj.name.lower():obj.hide_render=False
        cam.location,cam.rotation_euler,cam.data.ortho_scale=original_camera
        bpy.ops.wm.save_as_mainfile(filepath=str(CASE/'reconstruction.blend'))
    assert len([o for o in sc.objects if o.name.startswith('Stair tread')])==3
    assert not any(o.name.startswith('Far landing') for o in sc.objects)
    (OUT/'FOCUS_REVIEW.json').write_text(json.dumps({'source':str(CASE/'reconstruction.blend'),'scope':'oblique local room and three entrance treads; paper unchanged','material_pass_mesh_vertices_and_transforms_unchanged':True,'stair_context_treads':3,'whole_local_room_framed':True,'dot_helpers':str(DOT/'appearance_assets.py'),'photo_material_changes':['warm grey-pink rough plaster','grey stone .43m tile with weak fine seams','horizontal timber grain and narrow dark beading','metal corner guard','continuous mitered crown without gaps'],'panels':panels},ensure_ascii=False,indent=2),encoding='utf-8')

def compose():
    from PIL import Image,ImageDraw,ImageFont
    import numpy as np
    OUT.mkdir(parents=True,exist_ok=True)
    meta=json.loads((OUT/'FOCUS_REVIEW.json').read_text(encoding='utf-8'))
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',28);small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',22)
    board=Image.new('RGB',(2400,1660),'white');d=ImageDraw.Draw(board)
    for i,p in enumerate(meta['panels'][:2]):
        im=Image.open(OUT/(p['name']+'.png')).convert('RGBA');white=Image.new('RGBA',im.size,'white');white.alpha_composite(im);im=white.convert('RGB');im.save(OUT/(p['name']+'.png'))
        # Shape cue is an overlay; the model/material and source image remain separate.
        o=ImageDraw.Draw(im);poly=[tuple(x) for x in p['wall_polygon_xy']]
        eye,target=((-4,-6,14),(.1,-.4,1.2)) if i==0 else ((-3,-5,11),(.3,.5,1.2))
        forward=np.array(target)-np.array(eye);forward=forward/np.linalg.norm(forward);right=np.cross(forward,[0,0,1]);right/=np.linalg.norm(right);up=np.cross(right,forward)
        def project(point):
            v=np.array(point)-np.array(p['camera_xyz']);W,H=p['image_size'];return np.array([(float(v@right)/p['ortho_scale']+.5)*W,(.5-float(v@up)/(p['ortho_scale']*.75))*H])
        assert np.linalg.norm(project((.07,1.46,0))-np.array(poly[0]))<.01
        E=np.array([.07,1.46]);F=np.array([.76,.65]);G=np.array([1.38,.61]);t=(G-F)/np.linalg.norm(G-F);R=E+t*float((F-E)@t)
        paths=[[(E[0],E[1],z),(*R,z),(F[0],F[1],z)] for z in (0,2.57)]+[[(*R,0),(*R,2.57)]]
        for path in paths:
            for a,b in zip(path,path[1:]):
                a,b=project(a),project(b);distance=np.linalg.norm(b-a)
                for s in np.arange(0,distance,19):
                    o.line([tuple(a+(b-a)*s/distance),tuple(a+(b-a)*min(s+10,distance)/distance)],fill='#7c898e',width=3)
        o.line(poly+[poly[0]],fill='#a4612c',width=5)
        im.resize((1200,900)).save(OUT/(p['name']+'_marked.png'))
        board.paste(im.resize((1200,900)),(i*1200,55));d.text((i*1200+20,12),'A  门区完整周界取景' if i==0 else 'B  斜墙与两侧门局部取景',font=font,fill='#243746')
        d.text((i*1200+20,960),'完整门区与入口三阶；后续梯段不在本局部模型内。',font=small,fill='#555555')
        d.text((i*1200+20,995),'橙实线：斜墙轮廓；灰虚线：正交延长参考。',font=small,fill='#555555')
    src=Image.open(ROOT/'data/mp3d_layout/test/img/x8F5xyUWy9e_a51a0e2811f342a599ae4cdb9b84ff23.png').convert('RGB')
    dr=ImageDraw.Draw(src);poly=[(1040,357),(1305,284),(1305,837),(1040,778)];dr.line(poly+[poly[0]],fill='#b96528',width=5)
    crop=src.crop((610,245,1810,875)).resize((1050,551));board.paste(crop,(25,1090))
    d.text((1120,1110),'观察对应',font=font,fill='#243746')
    for i,line in enumerate(['焦点是两扇门之间的非直角墙面及连续回折。','金属护角、上下边界与原照片对应。','长梯间只交代入口方向，不作为图a的主体。','暖灰粉墙、弱石纹细缝与横向原木纹。','B用于工作主图；正式论文尚未替换。']):d.text((1120,1170+i*65),line,font=small,fill='#333333')
    board.save(OUT/'focus_candidates.png')

def source_check():
    import bpy
    bpy.ops.wm.open_mainfile(filepath=str(CASE/'reconstruction.blend'))
    sc=bpy.context.scene
    for name in ('FULL_MODEL','DISPLAY_CUTAWAY_ONLY'):bpy.data.collections[name].hide_render=False
    bpy.data.collections['DIAGNOSTIC_WIREFRAME'].hide_render=True
    for obj in sc.objects:
        if 'ceiling' in obj.name.lower():obj.hide_render=False
    lamp=bpy.data.objects.get('Diagnostic interior illumination')
    if lamp is None:
        lamp=bpy.data.objects.new('Diagnostic interior illumination',bpy.data.lights.new('Diagnostic interior illumination','POINT'))
        sc.collection.objects.link(lamp);lamp.location=(0,0,2.25);lamp.data.energy=110;lamp.data.shadow_soft_size=.7
    lamp.hide_render=False
    sc.camera=bpy.data.objects['Original source viewpoint'];sc.camera.data.lens=12
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
    for device in prefs.devices:device.use=device.type=='OPTIX'
    sc.cycles.device='GPU';sc.cycles.samples=32;sc.render.resolution_x=1600;sc.render.resolution_y=1000;sc.render.resolution_percentage=100
    sc.render.filepath=str(CASE/'source_camera_check.png');bpy.ops.render.render(write_still=True)
    bpy.ops.wm.open_mainfile(filepath=str(OUT/'oblique_focus.blend'))
    sc=bpy.context.scene;support=bpy.data.collections['DIAGNOSTIC_WIREFRAME'];support.hide_render=False
    bpy.data.collections['FULL_MODEL'].hide_render=True;bpy.data.collections['DISPLAY_CUTAWAY_ONLY'].hide_render=True
    for obj in sc.objects:
        if obj.type=='MESH':obj.hide_render=obj.name not in support.objects
    sc.cycles.samples=16;sc.render.filepath=str(CASE/'wireframe.png');bpy.ops.render.render(write_still=True)

def adopt():
    from PIL import Image,ImageDraw,ImageFont
    import shutil
    mapping={'B_wall_detail':'main_render','A_room_focus':'overview_render','C_reverse_focus':'reverse_render'}
    for src,dst in mapping.items():
        im=Image.open(OUT/(src+'.png')).convert('RGBA');white=Image.new('RGBA',im.size,'white');white.alpha_composite(im);white.convert('RGB').save(CASE/(dst+'.png'))
    presentation=CASE/'presentation.blend'
    if presentation.exists():presentation.unlink()
    (OUT/'oblique_focus.blend').rename(presentation)
    im=Image.open(CASE/'source_camera_check.png').convert('RGBA');white=Image.new('RGBA',im.size,'white');white.alpha_composite(im);white.convert('RGB').save(CASE/'source_camera_check.png')
    photo=Image.open(CASE/'source_perspective.png').convert('RGB');model=Image.open(CASE/'source_camera_check.png').convert('RGB');board=Image.new('RGB',(3200,1050),'white');board.paste(photo,(0,50));board.paste(model,(1600,50));d=ImageDraw.Draw(board);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',24)
    d.text((20,10),'Original panorama: perspective from same camera',font=font,fill='black');d.text((1620,10),'Model check: same camera; source-matched surface detail',font=font,fill='black');board.save(CASE/'source_view_comparison.png')
    metadata=json.loads((CASE/'model_manifest.json').read_text(encoding='utf-8'))
    metadata.update({'primary_figure_title':'Oblique wall: room with short stair entrance','primary_display':'whole local room and three entrance treads; no remote stairwell or terminal door','overview':'overview_render.png (A)','reverse':'reverse_render.png (C)','presentation_blend':'presentation.blend','complete_model_blend':'reconstruction.blend','render':{'size':[2400,1800],'cycles_samples':72,'device':'GPU','view_transform':'AgX'},'dot_material_helpers':str(DOT/'appearance_assets.py'),'main_figure_has_annotation_frame':False})
    (CASE/'model_manifest.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    j=json.loads((CASE/'verification.json').read_text(encoding='utf-8'))
    j.update({'whole_local_model_in_main_and_reverse':True,'stair_entrance_treads':3,'material_pass_preserved_rebuilt_meshes':True,'final_main_has_no_orange_frame':True})
    (CASE/'verification.json').write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'focus_candidates.png').replace(OUT/'photo_structure_review.png')
    safe=[*OUT.glob('*_marked.png'),*(OUT/(s+'.png') for s in mapping),*OUT.glob('*.blend1'),*CASE.glob('*.blend1')]
    assert all(p.resolve().is_relative_to(CASE.resolve()) for p in safe)
    for p in safe:
        if p.exists():p.unlink()

if __name__=='__main__':
    mode=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else sys.argv[1]
    if mode=='render':render()
    elif mode=='final':render(True)
    elif mode=='compose':compose()
    elif mode=='source_check':source_check()
    elif mode=='adopt':adopt()
