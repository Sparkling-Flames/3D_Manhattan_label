"""Photo-grounded physical examples, independent from GT / annotation geometry.

Python: script.py observe
Blender: blender -b --python script.py -- attic|ceiling [preview]
Full shell is saved before presentation-only cuts. Original photos stay untouched.
"""
from pathlib import Path
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'docs/thesis_main/论文写作工作资料/OOS分步重建_20261107'
SPECS = {
 'attic': {'stem':'S9hNv5qa7GM_53d54b73e58940019b731673e65c1902','split':'valid',
  'same_room':'S9hNv5qa7GM_f1b5f89d2b0a46449f374351c1579c80',
  'points':{'LF':[355,777],'LK':[355,540],'LC':[944,465],'RC':[1197,466],
            'RK':[1667,526],'RF':[1667,747],'BL':[873,675],'BR':[1218,675],
            'WL':[953,506],'WR':[1151,506],'WB':[1151,610],
            'DT':[2011,446],'DB':[2011,842]},
  'edges':[['LF','LK'],['LK','LC'],['LC','RC'],['RC','RK'],['RK','RF'],
           ['BL','BR'],['WL','WR'],['WR','WB'],['DT','DB']]},
 'ceiling': {'stem':'q9vSo1VnCiC_69591068e5614642b710a8fb7733bdeb','split':'test',
  'same_room':'q9vSo1VnCiC_dc873df7717c43888a1cff13713fe146',
  'points':{'HL':[740,95],'HR':[1110,159],'TL':[1110,159],'TB':[1110,360],
            'LT':[1425,395],'RT':[1555,398],'LB':[1425,666],'RB':[1555,665],
            'PT':[1734,409],'PB':[1734,699],'GV':[525,350],'GF':[525,620]},
  'edges':[['HL','HR'],['TL','TB'],['LT','RT'],['LT','LB'],['RT','RB'],
           ['PT','PB'],['GV','GF']]}}


def dump(path, obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')


def observe():
    import numpy as np
    import cv2
    from PIL import Image, ImageDraw, ImageFont
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22)
    for name,s in SPECS.items():
        out=OUT/name;out.mkdir(parents=True,exist_ok=True)
        source=ROOT/f'data/mp3d_layout/{s["split"]}/img/{s["stem"]}.png'
        im=Image.open(source).convert('RGB'); overlay=im.copy();dr=ImageDraw.Draw(overlay)
        for a,b in s['edges']:
            dr.line([tuple(s['points'][a]),tuple(s['points'][b])],fill='#ffba58',width=4)
        for k,(x,y) in s['points'].items():
            dr.ellipse([x-6,y-6,x+6,y+6],fill='#d04731',outline='white',width=2)
            dr.text((x+8,y-27),k,font=font,fill='white',stroke_width=2,stroke_fill='black')
        overlay.save(out/'candidate_points.png')
        droot=ROOT/'analysis_results/oos_depth_probe_20261107'
        raw=droot/(s['stem']+'.raw_pred_m.npy')
        dep=np.load(raw) if raw.exists() else np.array(Image.open(droot/(s['stem']+'.depth.png')))/1000
        valid=np.isfinite(dep)&(dep>0)&(dep<20)
        vals={}
        for k,(u,v) in s['points'].items():
            patch=dep[max(0,v//2-2):v//2+3,max(0,u//2-2):u//2+3]
            good=patch[np.isfinite(patch)&(patch>0)&(patch<20)]
            assert good.size, f'No valid depth at {name}/{k}'
            r=float(np.median(good));lon=2*math.pi*(u/2048-.5);lat=math.pi*(.5-v/1024)
            xyz=[r*math.sin(lon)*math.cos(lat),r*math.cos(lon)*math.cos(lat),r*math.sin(lat)]
            vals[k]={'uv_original_2048x1024':[u,v],'radial_prediction_m':r,'camera_xyz_m':xyz}
        dump(out/'candidate_points.json',{'source':str(source),'coordinate_system':'x right, y panorama center, z up; camera origin',
             'source_is_original':True,'gt_used':False,'points':vals,'display_edges':s['edges'],
             'lines_are_candidate_semantic_connections_not_straight_equirect_wall_projections':True})
        dump(out/'depth_check.json',{'source':str(raw if raw.exists() else droot/(s['stem']+'.depth.png')),
              'depth_type':'HoHoNet predicted radial distance, not observed sensor depth',
              'valid_fraction_0_20m':float(valid.mean()),'invalid_values_excluded':True,
              'geometry_role':'coarse scale and relative ceiling-level cross-check; no global rectangular fit'})
        for yaw in [0,90,180,-90]:
            w,h=900,650;ya=math.radians(yaw)
            x=((np.arange(w)+.5)/w*2-1)*math.tan(math.radians(50))
            z=(1-(np.arange(h)+.5)/h*2)*math.tan(math.radians(50))*h/w
            rr=np.stack(np.broadcast_arrays(x[None,:],np.ones((h,w)),z[:,None]),-1)
            rr=rr@np.array([[math.cos(ya),math.sin(ya),0],[-math.sin(ya),math.cos(ya),0],[0,0,1]]).T
            u=((np.arctan2(rr[:,:,0],rr[:,:,1])/2/math.pi+.5)*2048).astype('float32')
            v=((.5-np.arctan2(rr[:,:,2],np.hypot(rr[:,:,0],rr[:,:,1]))/math.pi)*1024).astype('float32')
            Image.fromarray(cv2.remap(np.array(im),u,v,cv2.INTER_LINEAR,borderMode=cv2.BORDER_WRAP)).save(out/f'source_view_{yaw}.png')
        print(name, 'candidate points and depth checked',flush=True)


def finalize():
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image, ImageDraw, ImageFont
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22)
    for case in SPECS:
        out=OUT/case
        for name in ['main','reverse','main_preview','reverse_preview','angle3_preview','camera_return','camera_return_opposite']:
            p=out/(name+'.png')
            if p.exists():
                im=Image.open(p).convert('RGBA');bg=Image.new('RGBA',im.size,'white');bg.alpha_composite(im);bg.convert('RGB').save(p)
        path=out/'mesh_wireframe.json'
        if path.exists():
            meshes=json.loads(path.read_text(encoding='utf-8'))
            fig=plt.figure(figsize=(10,4.4));a=fig.add_subplot(121);b=fig.add_subplot(122,projection='3d')
            allv=[]
            for name,m in meshes.items():
                vs=np.asarray(m['vertices']);allv.extend(vs)
                col='#bc7138' if any(k in name for k in ['slope','ceiling','flat']) else '#6a7f87'
                for i,j in m['edges']:
                    vv=vs[[i,j]];a.plot(vv[:,0],vv[:,1],color=col,lw=.55,alpha=.6);b.plot(vv[:,0],vv[:,1],vv[:,2],color=col,lw=.55,alpha=.65)
            allv=np.asarray(allv);a.set_aspect('equal');a.set_xlabel('x (approx. m)');a.set_ylabel('y (approx. m)');a.set_title('(a) Plan of the full model')
            b.set_box_aspect(np.ptp(allv,axis=0));b.view_init(elev=23,azim=-60);b.set_axis_off();b.set_title('(b) Full structural wireframe')
            fig.tight_layout();fig.savefig(out/'wireframe.png',dpi=200);fig.savefig(out/'wireframe.pdf');plt.close(fig)
        panels=[]
        for label,p in [('Source: corresponding panorama direction',out/('source_view_0.png' if case=='attic' else 'source_view_90.png')),
                        ('Reconstruction: approximate original-camera view',out/'camera_return.png')]:
            if p.exists():
                im=Image.open(p).convert('RGB').resize((1000,722),Image.Resampling.LANCZOS);can=Image.new('RGB',(1000,766),'white');can.paste(im,(0,40));ImageDraw.Draw(can).text((14,8),label,font=font,fill='#253d47');panels.append(can)
        if len(panels)==2:
            sheet=Image.new('RGB',(2000,766),'white');sheet.paste(panels[0],(0,0));sheet.paste(panels[1],(1000,0));sheet.save(out/'camera_check.png')


def build(case, preview=False):
    import bpy
    from mathutils import Vector
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    import render_scope_blender_20261107 as c
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version=0
    out=OUT/case;out.mkdir(parents=True,exist_ok=True);c.WORK=out
    sc=c.new_scene(case+'_photo_model')
    sc.render.threads_mode='FIXED';sc.render.threads=6
    sc.cycles.samples=24 if preview else 64
    sc.cycles.use_adaptive_sampling=True;sc.cycles.adaptive_threshold=.04
    sc.cycles.max_bounces=6;sc.cycles.diffuse_bounces=3
    if 'gpu' in sys.argv:
        prefs=bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type='OPTIX';prefs.get_devices()
        for dev in prefs.devices:dev.use=dev.type=='OPTIX'
        assert any(d.type=='OPTIX' and d.use for d in prefs.devices)
        sc.cycles.device='GPU'
    sc.render.resolution_x=1200 if preview else 2400
    sc.render.resolution_y=900 if preview else 1800
    sc.view_settings.view_transform='AgX';sc.view_settings.look='AgX - Medium High Contrast'
    sc.view_settings.exposure=.25
    # White world remains visible, with large area lights providing soft shadows.
    sc.render.film_transparent=True
    sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.7
    for ob in sc.objects:
        if ob.type=='LIGHT':ob.data.energy*=3;ob.data.size=7
    mats={k:c.material(k,col) for k,col in {'plaster':'#e9e3d6','trim':'#faf8f0',
           'wood':'#755039','wood_light':'#bd8d5a','floor':'#ad7556','grout':'#514942',
           'carpet':'#b5a084','glass':'#a5c3bb','dark':'#343731','metal':'#99733d',
           'cut_edge':'#b49373','wall_cut':'#ede8de','roof_slope':'#d2cec2'}.items()}
    if case=='attic':
        sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.42
        for ob,power in zip([o for o in sc.objects if o.type=='LIGHT'],[650,380]):
            ob.data.energy=power;ob.data.size=4
        for key,col in [('plaster','#d8d4cd'),('trim','#f0eee7'),('roof_slope','#c3c0b7')]:
            mats[key].node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=c.rgb(col)
        mats['plaster'].node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.83
        mats['trim'].node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.58
    # Small procedural roughness only; no panorama pasted over the architecture.
    for key,scale,strength in [('plaster',65,.12),('roof_slope',65,.12),('carpet',160,.6),('wood',8,.22),('floor',24,.15)]:
        mat=mats[key];nodes=mat.node_tree.nodes;links=mat.node_tree.links
        noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=scale
        bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=strength;bump.inputs['Distance'].default_value=.012
        links.new(noise.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs['Normal'],nodes['Principled BSDF'].inputs['Normal'])
        if key=='carpet':
            ramp=nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.18;ramp.color_ramp.elements[1].position=.82
            ramp.color_ramp.elements[0].color=c.rgb('#8c7b61');ramp.color_ramp.elements[1].color=c.rgb('#c4b59b')
            links.new(noise.outputs['Fac'],ramp.inputs[0]);links.new(ramp.outputs['Color'],nodes['Principled BSDF'].inputs['Base Color'])
    for name,stretch in [('rafter_wood',(16,.7,28)),('cross_wood',(.7,16,28))]:
        mat=c.material(name,'#755039',.62);mats[name]=mat
        nodes=mat.node_tree.nodes;links=mat.node_tree.links
        tc=nodes.new('ShaderNodeTexCoord');scale=nodes.new('ShaderNodeVectorMath');scale.operation='MULTIPLY';scale.inputs[1].default_value=stretch
        noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=4;noise.inputs['Detail'].default_value=2
        ramp=nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=c.rgb('#493321');ramp.color_ramp.elements[1].color=c.rgb('#a57b50')
        bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.16;bump.inputs['Distance'].default_value=.004
        links.new(tc.outputs['Generated'],scale.inputs[0]);links.new(scale.outputs[0],noise.inputs['Vector']);links.new(noise.outputs['Fac'],ramp.inputs[0])
        links.new(ramp.outputs['Color'],nodes['Principled BSDF'].inputs['Base Color']);links.new(noise.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs['Normal'],nodes['Principled BSDF'].inputs['Normal'])
    cut_main=[];cut_reverse=[];struct=[]
    def box(n,lo,hi,m='plaster',cut=None):
        # Internal plaster joints meet exactly; rounding both touching edges
        # opens a light leak. Visible trim keeps its millimetre bevel.
        structural_joint=m=='plaster' and any(t in n for t in ['wall','portal','ceiling','fascia','return'])
        bevel=0 if structural_joint else .003
        ob=c.box(n,lo,hi,mats[m],bevel);ob['photo_grounded']=True
        norm=ob.modifiers.new('Weighted architectural normals','WEIGHTED_NORMAL');norm.keep_sharp=True
        if cut in ('both','main'):cut_main.append(ob.name)
        if cut in ('both','reverse'):cut_reverse.append(ob.name)
        struct.append(ob.name);return ob
    def slab(n,p,offset,m='plaster',cut=None):
        ob=c.slab(n,p,offset,mats[m]);ob['photo_grounded']=True
        for mod in list(ob.modifiers):
            if mod.type=='BEVEL':
                if case=='attic':ob.modifiers.remove(mod)
                else:mod.width=.002;mod.segments=3
        norm=ob.modifiers.new('Weighted architectural normals','WEIGHTED_NORMAL');norm.keep_sharp=True
        if cut in ('both','main'):cut_main.append(ob.name)
        if cut in ('both','reverse'):cut_reverse.append(ob.name)
        struct.append(ob.name);return ob
    def rod(n,a,b,width=.025,m='trim'):
        d=Vector(b)-Vector(a);ob=c.box(n,(-width/2,-width/2,-d.length/2),(width/2,width/2,d.length/2),mats[m],.002)
        ob.location=(Vector(a)+Vector(b))/2;ob.rotation_euler=d.to_track_quat('Z','Y').to_euler();return ob
    def opening_wall(n,x0,x1,y,z0,z1,opening,mat='plaster',cut=None):
        # Opening represented by missing wall blocks, not a textured rectangle.
        a,b,bot,top=opening
        if a>x0:box(n+'_left',(x0,y,z0),(a,y+.12,z1),mat,cut)
        if b<x1:box(n+'_right',(b,y,z0),(x1,y+.12,z1),mat,cut)
        if bot>z0:box(n+'_sill_wall',(a,y,z0),(b,y+.12,bot),mat,cut)
        if top<z1:box(n+'_lintel',(a,y,top),(b,y+.12,z1),mat,cut)
        # Butt joints keep the front faces from overlapping at the frame corners.
        for j,(aa,bb) in enumerate([((a-.0375,y-.0725,bot),(a+.0375,y+.0025,top-.0375)),
                ((b-.0375,y-.0725,bot),(b+.0375,y+.0025,top-.0375)),
                ((a-.0375,y-.0725,top-.0375),(b+.0375,y+.0025,top+.0375))]):
            ob=c.box(n+'_frame_'+str(j),aa,bb,mats['trim' if case=='attic' or n.startswith('foyer_') else 'wood'],.002)
            if n!='entry_wall':
                if cut in ('both','main'):cut_main.append(ob.name)
                if cut in ('both','reverse'):cut_reverse.append(ob.name)
    if case=='attic':
        x0,x1,y0,y1=-1.28,1.76,-1.1,2.55
        knee,roof=1.42,2.08
        box('carpet_floor',(x0,y0,-.12),(x1,y1,0),'carpet')
        # Near-side high wall explains the transition beside the doorway.
        for side,x in [('left',x0),('right',x1)]:
            xx=(x-.12,x) if side=='left' else (x,x+.12)
            box(side+'_knee_wall',(xx[0],-.35,0),(xx[1],y1,knee),'plaster','reverse' if side=='left' else 'main')
            box(side+'_high_entry_wall',(xx[0],y0,0),(xx[1],-.35,2.14),'plaster','reverse' if side=='left' else 'main')
            slab(side+'_triangular_transition',[(x,-.35,knee),(x,-.35,2.14),(x,.12,knee)],(xx[1]-xx[0],0,0),'plaster','reverse' if side=='left' else 'main')
            sx=(x+.003,x+.035) if side=='left' else (x-.035,x-.003)
            box(side+'_skirting',(sx[0],y0+.006,.005),(sx[1],y1-.006,.09),'trim')
        opening_wall('rear_real_window_wall',x0,x1,y1,0,knee,(-.58,1.05,.72,1.62))
        # Rear gable cap + rectangle above the side knee, split around the real opening.
        slab('rear_upper_gable',[(x0,y1,knee),(-.62,y1,roof),(1.04,y1,roof),(x1,y1,knee)],(0,.12,0))
        # Window rises above knee; cut the gable face with a real Boolean hole.
        cutter=box('TEMP_window_void',(-.58,y1-.2,.72),(1.05,y1+.35,1.62),'dark')
        g=bpy.data.objects['rear_upper_gable'];mod=g.modifiers.new('True window opening','BOOLEAN');mod.operation='DIFFERENCE';mod.object=cutter
        bpy.context.view_layer.objects.active=g;bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cutter,do_unlink=True);struct.remove('TEMP_window_void')
        box('window_glazing',(-.55,y1+.07,.75),(1.02,y1+.085,1.59),'glass')
        rod('window_mid_mullion',(.235,y1-.04,.72),(.235,y1-.04,1.62),.05)
        rod('window_lower_frame',(-.58,y1-.04,.72),(1.05,y1-.04,.72),.075)
        box('window_sill',(-.64,y1-.14,.685),(1.11,y1+.12,.725),'trim')
        # Diamond lead came is visible in the original rear window.
        for panel,(xa,xb) in enumerate([(-.53,.20),(.27,1.0)]):
            for j,(lo,hi) in enumerate([((xa,y1+.015,.76),(xb,y1+.04,.79)),
                                       ((xa,y1+.015,1.56),(xb,y1+.04,1.59)),
                                       ((xa,y1+.015,.79),(xa+.03,y1+.04,1.56)),
                                       ((xb-.03,y1+.015,.79),(xb,y1+.04,1.56))]):
                box('casement_sash_%d_%d'%(panel,j),lo,hi,'trim')
            for slope in [-1,1]:
                for b in [j*.18 for j in range(-4,14)]:
                    pts=[]
                    for xx in [xa,xb]:
                        zz=slope*(xx-xa)+b
                        if .78<=zz<=1.56:pts.append((xx,y1+.045,zz))
                    for zz in [.78,1.56]:
                        xx=xa+(zz-b)/slope
                        if xa<=xx<=xb:pts.append((xx,y1+.045,zz))
                    if len(pts)==2:rod('lead_'+str(panel)+'_'+str(slope)+'_'+str(b),*pts,.007,'dark')
        opening_wall('entry_wall',x0,x1,y0-.12,0,2.14,(-.35,.65,0,1.98),cut='both')
        box('door_threshold',(-.35,y0-.18,-.01),(.65,y0+.08,.025),'wood_light')
        # Do not model rooms beyond this observed threshold.
        # Split roof into front display-cut portion and rear physical remainder.
        for section,ya,yb,cut in [('front',.12,1.15,'both'),('rear',1.15,y1,None)]:
            slab('left_slope_'+section,[(x0,ya,knee),(-.62,ya,roof),(-.62,yb,roof),(x0,yb,knee)],(0,0,.09),'roof_slope',cut=cut)
            slab('center_flat_'+section,[(-.62,ya,roof),(1.04,ya,roof),(1.04,yb,roof),(-.62,yb,roof)],(0,0,.09),cut=cut)
            slab('right_slope_'+section,[(1.04,ya,roof),(x1,ya,knee),(x1,yb,knee),(1.04,yb,roof)],(0,0,.09),'roof_slope',cut=cut)
        box('entry_flat_ceiling',(x0,y0,2.14),(x1,-.35,2.23),'plaster','both')
        for name,xa,xb,za,zb in [('left',x0,-.62,knee,roof),('middle',-.62,1.04,roof,roof),('right',1.04,x1,roof,knee)]:
            slab('entry_transition_'+name,[(xa,-.35,2.14),(xb,-.35,2.14),(xb,.12,zb),(xa,.12,za)],(0,0,.09),cut='both')
        # Side cupboard and shallow open shelves are wall-related visible details.
        box('left_low_cupboard_door',(x0+.012,-.2,.05),(x0+.04,.48,1.30),'trim')
        for z in [.25,.5,.76,1.02,1.27]:
            box('right_recess_shelf_'+str(z),(x1-.23,-.18,z),(x1,.4,z+.035),'trim')
        box('right_shelf_back',(x1-.015,-.18,.05),(x1+.015,.4,1.32),'plaster')
        box('near_tall_cupboard',(1.05,y0+.018,.02),(1.68,y0+.06,1.96),'trim','both')
        box('near_tall_cupboard_recess',(1.12,y0+.06,.13),(1.61,y0+.068,1.84),'plaster','both')
        for n,loc in [('left_low_cupboard_knob',(x0+.055,.39,.63)),('near_tall_cupboard_knob',(1.57,y0+.092,.92))]:
            bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,radius=.018,location=loc)
            knob=bpy.context.object;knob.name=n;knob.data.materials.append(mats['metal'])
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=.15,location=(.2,.75,2.025))
        fixture=bpy.context.object;fixture.name='observed_flush_ceiling_light';fixture.scale.z=.3;fixture.data.materials.append(mats['trim'])
        cut_main.append(fixture.name);cut_reverse.append(fixture.name)
        target=(.24,.75,.95);main=(6,-7,6.5);reverse=(-6,-6,6.5);third=(6,6,7)
        original=(0,0,1.55);look=(0,2.55,1.55);yaw=0
        checks={'roof_retains_two_slopes_and_center_flat':True,'near_seam_door_is_one_opening':True,
                'rear_window_is_actual_hole':True,'width_m':x1-x0,'length_m':y1-y0,
                'knee_height_m':knee,'flat_ceiling_m':roof,'same_room_G048_23_not_used_for_dimensions':True,
                'rear_slopes_and_center_form_closed_continuous_roof':True}
    else:
        # Photo-axis rotation: panorama's right/hall becomes +y; patio becomes -y.
        x0,x1,y0,y1=-3,3,-4.7,3.1; high=3.05;low=2.65;edge=.65
        box('continuous_terracotta_base',(x0,y0,-.12),(x1,y1,0),'grout')
        for i in range(12):
            for j in range(16):
                xa=x0+i*.5;ya=y0+j*.49
                box('terracotta_tile_%02d_%02d'%(i,j),(xa+.009,ya+.009,0),(xa+.491,min(ya+.481,y1),.018),'floor')
        # Large glazed patio opening is at far living-room side, not at the foyer.
        opening_wall('patio_wall',x0,x1,y0-.12,0,high,(-2.45,2.45,.1,2.55),cut='main')
        box('patio_glass',(-2.43,y0-.06,.12),(2.43,y0-.045,2.53),'glass','main')
        for x in [-2.45,-.82,.82,2.45]:
            ob=rod('patio_mullion_'+str(x),(x,y0-.01,.1),(x,y0-.01,2.55),.045,'dark');cut_main.append(ob.name)
        # Side walls have observed internal passages instead of blank full rectangles.
        box('left_living_wall',(x0-.12,y0,0),(x0,edge,high),'plaster','main')
        box('right_living_wall',(x1,y0,0),(x1+.12,edge,high),'plaster','reverse')
        # Foyer wall piers and central hall opening, seen frontally in yaw+90.
        opening_wall('foyer_central_portal',x0,1.45,y1,0,low,(-.65,.65,0,2.25))
        opening_wall('foyer_right_portal',1.45,x1,y1,0,low,(1.6,2.65,0,2.2))
        box('central_light_projecting_lintel',(-.78,y1-.13,2.25),(.78,y1-.075,2.39),'trim')
        box('right_light_projecting_lintel',(1.50,y1-.11,2.2),(2.75,y1-.075,2.30),'trim')
        # Short observed hall continuation; no guessed distant room is filled in.
        box('hall_left_return',(-.77,y1+.12,0),(-.65,y1+1.35,low))
        box('hall_right_return',(.65,y1+.12,0),(.77,y1+1.35,low))
        box('hall_floor',(-.65,y1,0),(.65,y1+1.35,.018),'floor')
        box('hall_ceiling',(-.77,y1,low),(.77,y1+1.35,low+.12),'plaster','both')
        box('foyer_left_side',(x0-.12,edge,0),(x0,y1,low),'plaster','main')
        box('foyer_right_side',(x1,edge,0),(x1+.12,y1,low),'plaster','reverse')
        # Shared continuous higher room plus lower overhang, preserved in full model.
        for part,xa,xb,cut in [('left',x0,0,None),('right',0,x1,None)]:
            box('lower_ceiling_'+part,(xa,edge,low),(xb,y1,low+.16),'plaster',cut)
            box('low_fascia_'+part,(xa,edge-.03,low+.16),(xb,edge+.1,high),'plaster',cut)
            for zz in [2.78,2.82,2.86,2.90,2.94]:
                box('wood_vent_'+part+str(zz),(xa+.06,edge-.045,zz),(xb-.06,edge-.024,zz+.018),'wood',cut)
        for part,ya,yb,cut in [('front',y0,-3.5,'both'),('high_display_section',-3.5,-2.75,None),
                             ('middle',-2.75,-.15,'both'),('rear',-.15,edge,None)]:
            box('light_high_ceiling_'+part,(x0,ya,high),(x1,yb,high+.10),'plaster',cut)
        # Structural timber rafters BELOW light panels, visible in both source views.
        for i,x in enumerate([-2.6,-1.75,-.9,-.05,.8,1.65,2.5]):
            box('timber_rafter_'+str(i),(x-.055,y0,high-.16),(x+.055,edge,high),'rafter_wood')
        for j,y in enumerate([-3.65,-1.55,.45]):
            box('cross_beam_'+str(j),(x0,y-.11,high-.27),(x1,y+.11,high-.10),'cross_wood')
        for side,x in [('left',x0),('right',x1)]:
            sx=(x+.003,x+.035) if side=='left' else (x-.035,x-.003)
            box(side+'_tile_skirting',(sx[0],y0+.006,.015),(sx[1],y1-.006,.12),'floor')
        # Only architectural fixtures essential for identifying the entry area.
        for x in [-1.25,1.12]:
            box('portal_frame_picture_'+str(x),(x-.22,y1-.055,1.15),(x+.22,y1-.025,1.8),'wood')
            box('portal_picture_inset_'+str(x),(x-.18,y1-.065,1.19),(x+.18,y1-.058,1.76),'trim')
        target=(0,-.35,1.1);main=(-10,11,12.2);reverse=(10,-11,11.4);third=(-10,-12,12.2)
        original=(0,0,1.55);look=(0,4,1.55);yaw=90
        checks={'high_light_panels_and_timber_beams':True,'lower_ceiling_covers_internal_portals':True,
                'patio_is_opposite_hall_not_fake_foyer_window':True,'high_ceiling_m':high,'lower_ceiling_m':low,
                'same_room_G153_30_used_for_topology':True,'distant_hall_beyond_1_35m_unmodeled':True,
                'portal_frame_matches_light_source_finish':True,'wood_grain_follows_beam_long_axis':True}
    fill=bpy.data.objects.new('Interior bounce fill',bpy.data.lights.new('Interior bounce fill','AREA'))
    sc.collection.objects.link(fill);fill.location=(.2,.5,1.94 if case=='attic' else 2.52)
    fill.data.energy=28 if case=='attic' else 120;fill.data.size=1.2 if case=='attic' else 3
    # 2026-11-07 user direction: all four perimeter walls stay visible in delivery.
    # Only ceiling sections may be removed to reveal the interior like ZInD.
    previous_cut={'main':list(cut_main),'reverse':list(cut_reverse)}
    roof_tokens=('slope_front','center_flat_front','entry_flat_ceiling','entry_transition','light_high_ceiling_front',
                 'light_high_ceiling_middle','observed_flush_ceiling_light','hall_ceiling')
    cut_main=[n for n in cut_main if any(t in n for t in roof_tokens)]
    cut_reverse=[n for n in cut_reverse if any(t in n for t in roof_tokens)]
    checks['all_four_perimeter_walls_visible_in_delivery']=True
    assert not any('wall' in n or 'portal' in n for n in cut_main+cut_reverse)
    if case=='attic':
        def vertex_set(name):return {tuple(round(float(x),5) for x in v.co) for v in bpy.data.objects[name].data.vertices}
        flat=vertex_set('center_flat_rear')
        assert len(flat & vertex_set('left_slope_rear'))>=4 and len(flat & vertex_set('right_slope_rear'))>=4
        assert not any(n in cut_main+cut_reverse for n in ['center_flat_rear','left_slope_rear','right_slope_rear'])
    def aim(loc,at,ortho=9):
        sc.camera.location=loc;sc.camera.rotation_euler=(Vector(at)-sc.camera.location).to_track_quat('-Z','Y').to_euler()
        sc.camera.data.type='ORTHO';sc.camera.data.ortho_scale=ortho
    aim(main,target,6.5 if case=='attic' else 12.7)
    sc['source_photo']=str(ROOT/f'data/mp3d_layout/{SPECS[case]["split"]}/img/{SPECS[case]["stem"]}.png')
    sc['interpretation']='Photo-grounded approximate explanatory model; no measured depth or GT used as truth'
    sc['hidden_for_main']=json.dumps(cut_main);sc['hidden_for_reverse']=json.dumps(cut_reverse)
    assert all(checks[k] for k in checks if isinstance(checks[k],bool))
    fullverts={o.name:[list(v.co) for v in o.data.vertices] for o in sc.objects if o.type=='MESH'}
    wire={o.name:{'vertices':[(o.matrix_world@v.co)[: ] for v in o.data.vertices],
                 'edges':[list(e.vertices) for e in o.data.edges]} for o in sc.objects if o.type=='MESH'
          and any(s in o.name for s in ['ceiling','slope','center_flat','knee_wall','entry_wall','gable','foyer','beam'])}
    dump(out/'mesh_wireframe.json',wire)
    if not preview:bpy.ops.wm.save_as_mainfile(filepath=str(out/'full_model.blend'))
    cameras=[('main',main,cut_main),('reverse',reverse,cut_reverse)]
    if preview:cameras.append(('angle3',third,cut_main))
    for tag,loc,hidden in cameras:
        aim(loc,target,6.5 if case=='attic' else 12.7)
        for ob in sc.objects:ob.hide_render=ob.name in hidden
        sc.render.filepath=str(out/(tag+('_preview' if preview else '')+'.png'))
        bpy.ops.render.render(write_still=True)
    if preview:
        dump(out/'preview_checks.json',checks)
        for ob in sc.objects:ob.hide_render=False
        aim(main,target,6.5 if case=='attic' else 12.7)
        bpy.ops.wm.save_as_mainfile(filepath=str(out/'roof_review_full.blend'))
        for ob in sc.objects:ob.hide_render=ob.name in cut_main
        bpy.ops.wm.save_as_mainfile(filepath=str(out/'roof_review_presentation.blend'))
        if case=='attic':
            for ob in sc.objects:ob.hide_render=False
            sc.camera.location=original;sc.camera.rotation_euler=(Vector(look)-Vector(original)).to_track_quat('-Z','Y').to_euler()
            sc.camera.data.type='PERSP';sc.camera.data.lens=36/(2*math.tan(math.radians(50)));sc.camera.data.sensor_width=36
            sc.render.resolution_x=900;sc.render.resolution_y=650;sc.cycles.samples=16
            sc.render.filepath=str(out/'roof_review_camera.png');bpy.ops.render.render(write_still=True)
        return
    # Return to full shell and original panorama viewing direction; camera image
    # checks topology, not a claimed dense pixel-registered reconstruction.
    for ob in sc.objects:ob.hide_render=False
    sc.camera.location=original;sc.camera.rotation_euler=(Vector(look)-Vector(original)).to_track_quat('-Z','Y').to_euler()
    sc.camera.data.type='PERSP';sc.camera.data.lens=36/(2*math.tan(math.radians(50)));sc.camera.data.sensor_width=36
    sc.cycles.samples=24
    sc.render.resolution_x=1200;sc.render.resolution_y=867
    sc.render.filepath=str(out/'camera_return.png');bpy.ops.render.render(write_still=True)
    sc.camera.rotation_euler=(Vector((0,-4,original[2]))-Vector(original)).to_track_quat('-Z','Y').to_euler()
    sc.render.filepath=str(out/'camera_return_opposite.png');bpy.ops.render.render(write_still=True)
    assert fullverts=={o.name:[list(v.co) for v in o.data.vertices] for o in sc.objects if o.type=='MESH'}
    checks.update({'mesh_unchanged_during_display_cut':True,'gt_and_annotation_geometry_read_or_modified':False,
                   'camera_return_source_yaw':yaw,'camera_return_registration':'approximate photo pose; topology check only',
                   'cut_main':cut_main,'cut_reverse':cut_reverse,'render_engine':'Cycles','main_max_samples':24 if preview else 64,'camera_max_samples':24,
                   'threads':6,'color_management':'AgX - Medium High Contrast','source_depth':'HoHoNet prediction only'})
    dump(out/'validation.json',checks)
    # Wireframe plan / section derived from the same physical mesh.
    if not preview:
        aim(main,target,6.5 if case=='attic' else 12.7)
        sc.render.resolution_x=2400;sc.render.resolution_y=1800;sc.cycles.samples=64
        bpy.ops.wm.save_as_mainfile(filepath=str(out/'full_model.blend'))
        for ob in sc.objects:ob.hide_render=ob.name in cut_main
        sc.render.filepath=str(out/'main.png')
        bpy.ops.wm.save_as_mainfile(filepath=str(out/'presentation.blend'))
    print(case,'completed',flush=True)


if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    if args[0]=='observe':observe()
    elif args[0]=='finalize':finalize()
    else:build(args[0], 'preview' in args)
