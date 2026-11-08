"""Photo/depth-supported OOS working reconstructions; never read or edit layout GT.

Python: this_file.py depth|prepare|finish.
Blender: -b --python this_file.py -- final_oblique|final_stairs --gpu.
The working meshes are explanatory reconstructions, not recovered sensor geometry.
"""
from pathlib import Path
import json, math, sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
WORK = ROOT/'docs/thesis_main/论文写作工作资料/OOS分步重建_20261107'
DEPTH = ROOT/'analysis_results/oos_depth_probe_20261107'
CASES = {
    'oblique': ('x8F5xyUWy9e-09', 'test', 'x8F5xyUWy9e_a51a0e2811f342a599ae4cdb9b84ff23'),
    'stairs': ('uNb9QFRL6hY-69', 'test', 'uNb9QFRL6hY_ce88ee8b7ee84fca92c13ab16599d90e'),
    'attic': ('S9hNv5qa7GM-07', 'valid', 'S9hNv5qa7GM_53d54b73e58940019b731673e65c1902'),
    'ceiling': ('q9vSo1VnCiC-09', 'test', 'q9vSo1VnCiC_69591068e5614642b710a8fb7733bdeb'),
}

def source(key):
    _, split, stem = CASES[key]
    return ROOT/f'data/mp3d_layout/{split}/img/{stem}.png'

def depth():
    import importlib, numpy as np, torch
    from PIL import Image
    from types import SimpleNamespace
    from lib.config import config, update_config
    cfg = 'config/mp3d_depth/HOHO_depth_dct_efficienthc_TransEn1_hardnet.yaml'
    checkpoint = ROOT/'ckpt/mp3d_depth_HOHO_depth_dct_efficienthc_TransEn1_hardnet/ep60.pth'
    args=SimpleNamespace(cfg=str(ROOT/cfg),opts=['model.kwargs.backbone_config.kwargs.pretrained','False'])
    update_config(config,args)
    net=getattr(importlib.import_module(config.model.file),config.model.modelclass)(**config.model.kwargs)
    net.load_state_dict(torch.load(checkpoint,map_location='cuda'))
    net=net.eval().cuda()
    records=[]
    with torch.no_grad():
        for key, (code,split,stem) in CASES.items():
            rgb=np.array(Image.open(source(key)))
            inp=torch.from_numpy(rgb).permute(2,0,1)[None].float()/255
            inp=torch.nn.functional.interpolate(inp,config.dataset.common_kwargs.hw,mode='area').cuda()
            pred=net.infer(inp)
            if not torch.is_tensor(pred):pred=pred['depth']
            a=pred.squeeze().cpu().numpy().astype('float32')
            assert a.shape==(512,1024) and np.isfinite(a).all()
            np.save(DEPTH/(stem+'.raw_pred_m.npy'),a)
            record={'case':code,'rgb':str(source(key).relative_to(ROOT)),'npy':stem+'.raw_pred_m.npy',
                    'shape':list(a.shape),'min_m':float(a.min()),'max_m':float(a.max()),
                    'nonpositive_pixels':int((a<=0).sum()),'positive_p01_p50_p99_m':np.percentile(a[a>0],[1,50,99]).tolist()}
            records.append(record);print(json.dumps(record),flush=True)
    (DEPTH/'RAW_MANIFEST.json').write_text(json.dumps({'source':'HoHoNet monocular prediction; NOT observed sensor depth',
        'checkpoint':str(checkpoint.relative_to(ROOT)),'cfg':cfg,'input_transform':'full RGB 2048x1024 to1024x512 area resize',
        'depth_type':'radial Euclidean metres, raw float32; exclude nonpositive values',
        'legacy_png_warning':'infer_depth.py directly casts prediction*1000 to uint16; negative predictions can wrap to near65.5m. Use raw float NPY.',
        'images':records},ensure_ascii=False,indent=2),encoding='utf-8')

def uv_ray(u,v):
    import numpy as np
    lon=(u/2048-.5)*2*math.pi;lat=(.5-v/1024)*math.pi
    return np.array([math.sin(lon)*math.cos(lat),math.cos(lon)*math.cos(lat),math.sin(lat)])

def prepare():
    import numpy as np
    from PIL import Image
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from urllib.request import urlopen
    points={
      'oblique': [('A',250,756),('B',680,780),('C',795,765),('D',985,773),('E',1040,778),('F',1305,837),('G',1400,772),('H',1760,763),('I',1800,735)],
      'stairs': [('A',245,656),('B',660,681),('C',740,860),('D',900,794),('E',951,691),('F',1100,682),('G',1148,790),('H',1300,875),('I',1990,685)]}
    groups=json.loads((ROOT/'research/same_room/relation_adoption_20261016/original_groups.json').read_text(encoding='utf-8'))
    manifest=[]
    for key in ('oblique','stairs'):
        out=WORK/key;out.mkdir(parents=True,exist_ok=True)
        code,split,stem=CASES[key];building=stem.split('_')[0]
        matches=[{k:g[k] for k in ('review_code','image_ids','numbers')} for g in groups if stem in g['image_ids']]
        (out/'same_room_registry.json').write_text(json.dumps(matches,ensure_ascii=False,indent=2),encoding='utf-8')
        conn=DEPTH/(building+'_connectivity.json')
        if not conn.exists():
            try:conn.write_bytes(urlopen('https://raw.githubusercontent.com/peteanderson80/Matterport3DSimulator/master/connectivity/'+conn.name,timeout=20).read())
            except Exception as e:print('connectivity unavailable:',e)
        selected=[]
        if conn.exists():
            dd=json.loads(conn.read_text());ids={stem.split('_')[1]}
            for g in matches:ids.update(x.split('_')[1] for x in g['image_ids'])
            selected=[{'image_id':x['image_id'],'included':x['included'],'center_m':[x['pose'][j] for j in [3,7,11]],'height_estimate_m':x.get('height')} for x in dd if x['image_id'] in ids]
        (out/'camera_positions.json').write_text(json.dumps(selected,indent=2),encoding='utf-8')
        rgb=np.array(Image.open(source(key)));arr=np.load(DEPTH/(stem+'.raw_pred_m.npy'))
        fig,ax=plt.subplots(2,1,figsize=(15,8),layout='constrained')
        ax[0].imshow(rgb);ax[0].set_title(code+' | observed boundaries and turns (A–I)');recs=[]
        for label,u,v in points[key]:
            block=arr[max(0,v//2-2):v//2+3,max(0,u//2-2):u//2+3];d=float(np.median(block[block>0]));r=uv_ray(u,v)
            rec={'label':label,'uv_original':[u,v],'median_predicted_radial_depth_m':d,'prediction_xyz_camera_m':(r*d).tolist(),
                 'ground_intersection_xyz_assumed_camera_height_1_55m':(r*(-1.55/r[2])+[0,0,1.55]).tolist()}
            recs.append(rec);ax[0].scatter(u,v,s=36,c='#b52523',edgecolors='white');ax[0].text(u+8,v-10,label,color='white',weight='bold',bbox={'facecolor':'#243746','alpha':.75,'pad':2})
        ax[1].imshow(arr,cmap='viridis',vmin=.3,vmax=6,extent=(0,2048,1024,0));ax[1].set_title('HoHoNet radial depth prediction; shared 0.3–6 m color range')
        for a in ax:a.set_xlabel('Panorama u (px)');a.set_ylabel('Panorama v (px)')
        fig.savefig(out/'observed_points_and_depth.png',dpi=170);plt.close(fig)
        (out/'observed_points.json').write_text(json.dumps(recs,indent=2),encoding='utf-8')
        manifest.append({'case':code,'same_room_groups':matches,'camera_positions':selected,'reference':'No layout labels read. Photo features and predicted depth are kept distinct.'})
    (DEPTH/'OBSERVATION_SOURCES.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')

def render(key,build_only=False):
    import bpy
    import numpy as np
    from mathutils import Vector
    sys.path.insert(0,str(Path(__file__).parent))
    import render_scope_blender_20261107 as core
    import render_photo_scope_blender_20261107 as photo
    out=WORK/key;out.mkdir(parents=True,exist_ok=True);core.WORK=out
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc=core.new_scene('Photo reconstruction '+key)
    sc.render.resolution_x=2400;sc.render.resolution_y=1800
    sc.render.threads=6;sc.cycles.samples=64
    sc.render.film_transparent=True
    sc.view_settings.view_transform='AgX';sc.view_settings.look='AgX - Medium High Contrast'
    p={k:core.material(k,v) for k,v in {'wall':'#e9dfd0','white':'#f5f3ec','floor':'#a6a398','wood':'#9b7954','dark':'#47342b','metal':'#4a4947','glass':'#8faeb5','line':'#55737e','accent':'#bf883d','high':'#b69b75','low':'#e1d2b8'}.items()}
    full=bpy.data.collections.new('FULL_MODEL');sc.collection.children.link(full)
    cut=bpy.data.collections.new('DISPLAY_CUTAWAY_ONLY');sc.collection.children.link(cut)
    support=bpy.data.collections.new('DIAGNOSTIC_WIREFRAME');sc.collection.children.link(support)
    def move(obj,coll):
        for c in list(obj.users_collection):c.objects.unlink(obj)
        coll.objects.link(obj);return obj
    def box(name,lo,hi,mat='wall',coll=full,bevel=.007):return move(core.box(name,lo,hi,p[mat],bevel),coll)
    def beam(name,a,b,w,mat='white',coll=full):return move(photo.beam(name,a,b,w,p[mat]),coll)
    def slab(name,pts,offset,mat='floor',coll=full):return move(core.slab(name,pts,offset,p[mat]),coll)
    def wall(name,a,b,height,openings=(),mat='wall',coll=full,base=0):
        a=np.array(a,float);b=np.array(b,float);v=b-a;length=float(np.linalg.norm(v));v/=length
        normal=np.array([-v[1],v[0]])*.12
        def piece(s,t,z,Z,suffix):
            if t-s<.001 or Z-z<.001:return
            aa=a+s*v;bb=a+t*v
            slab(name+' '+suffix,[(*aa,z),(*bb,z),(*bb,Z),(*aa,Z)],(*normal,0),mat,coll)
        last=0
        for i,(left,right,bottom,top) in enumerate(openings):
            assert 0<=left<right<=length+.001 and base<=bottom<top<=height
            piece(last,left,base,height,'pier '+str(i))
            piece(left,right,base,bottom,'sill '+str(i));piece(left,right,top,height,'lintel '+str(i));last=right
        piece(last,length,base,height,'end')
        # Interior baseboard and cornice follow the same actual wall segment; holes stay holes.
        spans=[(0,length)]
        for left,right,bottom,top in openings:
            if bottom<=base+.01:spans=[(s,min(t,left)) for s,t in spans if s<left]+[(max(s,right),t) for s,t in spans if t>right]
        for s,t in spans:
            if t>s:beam(name+' baseboard',(*(a+s*v),base+.065),(*(a+t*v),base+.065),.07,'dark' if key=='oblique' else 'white',coll)
        beam(name+' cornice',(*a,height-.05),(*b,height-.05),.065,'white',coll)
        return a,v,normal,length
    def opening(name,a,b,z,Z,glass=False,door=False,double=False):
        a=np.array(a,float);b=np.array(b,float);v=b-a;ln=np.linalg.norm(v);v/=ln;normal=np.array([-v[1],v[0]])
        for P,Q in [((*a,z),(*a,Z)),((*b,z),(*b,Z)),((*a,Z),(*b,Z))]:beam(name+' casing',P,Q,.075,'white' if glass or key=='stairs' else 'dark')
        if glass:
            beam(name+' sill',(*a,z),(*b,z),.08,'white')
            aa=a+v*.035;bb=b-v*.035
            slab(name+' glazing',[(*aa,z+.03),(*bb,z+.03),(*bb,Z-.03),(*aa,Z-.03)],(*(-normal*.018),0),'glass')
            mid=(a+b)/2
            if key=='stairs':
                for offset,width in [(.035,.025),(.068,.017)]:
                    aa=a-v*offset-normal*.025;bb=b+v*offset-normal*.025
                    for P,Q in [((*aa,z-offset),(*aa,Z+offset)),((*bb,z-offset),(*bb,Z+offset)),((*aa,Z+offset),(*bb,Z+offset))]:beam(name+' layered frame',P,Q,width,'white')
                beam(name+' projecting sill',(*(a-v*.065-normal*.045),z-.035),(*(b+v*.065-normal*.045),z-.035),.09,'white')
                for offset in [-.045,.045]:
                    if 'small' in name or 'garden' in name:beam(name+' vertical mullion',(*(mid+normal*offset),z),(*(mid+normal*offset),Z),.028,'white')
                    if 'transom' not in name and 'garden' not in name:beam(name+' horizontal sash',(*(a+normal*offset),(z+Z)/2),(*(b+normal*offset),(z+Z)/2),.028,'white')
            else:beam(name+' center mullion',(*mid,z),(*mid,Z),.036,'white')
        elif door:
            count=2 if double else 1
            for i in range(count):
                aa=a+v*(ln*i/count+.025);bb=a+v*(ln*(i+1)/count-.025)
                slab(name+' leaf '+str(i),[(*aa,z+.015),(*bb,z+.015),(*bb,Z-.035),(*aa,Z-.035)],(*(-normal*.038),0),'wood' if key=='oblique' or 'timber' in name else 'white')
                if key=='stairs':
                    trim='wood' if 'timber' in name else 'white'
                    for z0,z1 in [(z+.16,z+.65),(z+.79,Z-.14)]:
                        A=aa+v*.075-normal*.047;B=bb-v*.075-normal*.047
                        for P,Q in [((*A,z0),(*B,z0)),((*A,z1),(*B,z1)),((*A,z0),(*A,z1)),((*B,z0),(*B,z1))]:beam(name+' raised panel moulding',P,Q,.025,trim)
                else:
                    for zz in [z+.22,z+.9,Z-.22]:beam(name+' panel rail',(*(aa-normal*.045),zz),(*(bb-normal*.045),zz),.026,'dark')
                mid=aa+(bb-aa)*(.85 if i==0 else .15)-normal*.065
                move(photo.sphere(name+' handle',(*mid,z+1.03),(.027,.027,.027),p['metal']),full)
    wire=[];checks={};unknown=[]
    if key=='oblique':
        H=2.57
        footprint=[(-1.2,-2.72),(-1.2,1.49),(-.18,1.49),(.07,1.46),(.76,.65),(1.38,.61),(1.24,-1.01),(1.31,-1.38),(1.31,-2.35),(1.31,-2.72)]
        slab('Main corridor stone floor',[(x,y,0) for x,y in footprint],(0,0,-.12),'floor')
        wall('Left corridor return',footprint[0],footprint[1],H,coll=cut)
        wall('Open doorway wall',(-1.2,1.49),(-.18,1.49),H,[(.06,.94,0,2.18)])
        opening('Open doorway',(-1.14,1.49),(-.26,1.49),0,2.18)
        # Swing leaf into corridor, matching the photo; no invented room behind it.
        end=(-1.14+.88*math.cos(math.radians(72)),1.49-.88*math.sin(math.radians(72)))
        slab('Observed open timber leaf',[(-1.14,1.49,.02),(*end,.02),(*end,2.14),(-1.14,1.49,2.14)],(.025,.01,0),'wood')
        for z in [.22,1.05,1.97]:beam('Open leaf horizontal panel',(-1.14,1.47,z),(end[0],end[1]-.02,z),.023,'dark')
        slab('Visible doorway threshold',[(-1.14,1.49,0),(-.26,1.49,0),(-.26,1.92,0),(-1.14,1.92,0)],(0,0,-.1),'low')
        wall('Door jamb short return',footprint[2],footprint[3],H)
        wall('NONORTHOGONAL facet',footprint[3],footprint[4],H)
        wall('Metal edged return',footprint[4],footprint[5],H)
        beam('Observed corner metal strip',(*footprint[4],.08),(*footprint[4],H-.05),.026,'metal')
        a=np.array(footprint[5]);b=np.array(footprint[6]);v=(b-a)/np.linalg.norm(b-a);ln=float(np.linalg.norm(b-a))
        wall('Double door wall',a,b,H,[(.05,ln-.05,0,2.19)])
        opening('Double wooden doors',a+v*.05,b-v*.05,0,2.19,door=True,double=True)
        wall('Stair entry return',footprint[6],footprint[7],H)
        # Only the entrance is needed to locate the oblique-wall room; the flight continues outside this local model.
        stair_end=1.31+3*.245
        for i in range(3):
            x=1.31+i*.245
            box('Stair tread %02d'%i,(x,-2.35,0),(x+.245,-1.38,(i+1)*.168),'floor')
            beam('Stair nosing %02d'%i,(x,-2.35,(i+1)*.168+.006),(x,-1.38,(i+1)*.168+.006),.02,'low')
        slab('Stair left wall',[(1.31,-1.38,0),(stair_end,-1.38,0),(stair_end,-1.38,H+.35),(1.31,-1.38,H)],(0,.12,0),'wall')
        slab('Stair right wall',[(stair_end,-2.35,0),(1.31,-2.35,0),(1.31,-2.35,H),(stair_end,-2.35,H+.35)],(0,-.12,0),'wall',cut)
        slab('Stair ceiling',[(1.31,-2.35,H),(stair_end,-2.35,H+.35),(stair_end,-1.38,H+.35),(1.31,-1.38,H)],(0,0,.1),'white',cut)
        for j in range(8,len(footprint)):
            wall('Near corridor perimeter estimate %d'%j,footprint[j],footprint[(j+1)%len(footprint)],H,coll=cut)
        # Close outer joint wedges without moving the observed inner wall faces.
        for j in [0,1,2,3,4,5,6,9]:
            q=np.array(footprint[j]);a=q-np.array(footprint[j-1]);b=np.array(footprint[(j+1)%len(footprint)])-q
            a/=np.linalg.norm(a);b/=np.linalg.norm(b)
            u=q+np.array([-a[1],a[0]])*.12;v=q+np.array([-b[1],b[0]])*.12
            du,dv=u-q,v-q
            if abs(du[0]*dv[1]-du[1]*dv[0])>1e-6:slab('Perimeter wall corner joint %d'%j,[(*q,0),(*u,0),(*v,0)],(0,0,H),'wall')
        slab('Complete main ceiling',[(x,y,H) for x,y in footprint],(0,0,.1),'white',cut)
        # Stone joints are modeled decoratively; not claimed as measured texture.
        for y in np.arange(-2.1,1.1,.42):beam('Stone floor joint',(-1.18,y,.003),(.65,y,.003),.004,'white')
        wire=[[(x,y,z) for x,y in footprint] for z in (0,H)]
        for i in [2,3,4,5,6]:wire.append([(*footprint[i],0),(*footprint[i],H)])
        target=(1.1,-.3,1.6);eye=(-6,-8,6.5);reverse=(7,5,6.5);scale=8.6
        checks={'nonorthogonal_facet_preserved':True,'main_turns':footprint[2:7],'stairs_count':3,'staircase_connects_to_entry':True,'local_model_ends_after_three_treads_without_terminal_wall':True,'open_door_and_double_doors_separate':True}
        unknown=['The stair flight is intentionally represented only by its entrance three treads; this is a local model boundary, not the physical end of the flight.','Far rooms behind doorway/closed closet are deliberately not invented.','Near wall plane follows visible contacts at pano u=0 and1930; its corner behind banner/plant uses planar continuation, not a recovered curve.']
        camera=(0,0,1.55)
    else:
        # Positions follow source rays; large low room, compact raised entry, and short lateral stair.
        H=2.8;left=-2.45;right=.65;front=-2.6;back=2.62
        box('Large lower wood floor',(left,front,-.12),(right,1.2,0),'low')
        box('Central landing continuous with main floor',(left,1.2,-.12),(.22,back,0),'low')
        box('Small raised entry landing',(left,1.2,0),(-1.22,back,.54),'high')
        for i in range(3):
            x=-1.22+i*.22;height=.54-i*.18
            box('Entry stair %d'%(i+1),(x,1.2,0),(x+.22,back,height),'high')
            beam('Wood stair nose %d'%i,(x+.21,1.2,height+.005),(x+.21,back,height+.005),.018,'wood')
            beam('Ascending stair skirting %d'%i,(x,back-.018,height+.09),(x+.22,back-.018,height+.09),.045,'white')
            beam('Ascending skirting riser %d'%i,(x+.22,back-.018,height-.09),(x+.22,back-.018,height+.09),.045,'white')
        # Only the visible descending start is reconstructed; its continuation remains open.
        for i in range(2):
            x=.22+i*.24;z=-.18*(i+1)
            box('Visible descending tread %d'%i,(x,1.2,z-.05),(x+.24,back,z),'high')
            box('Descending white riser %d'%i,(x,1.2,z),(x+.025,back,z+.18),'white')
            beam('Descending oak nose %d'%i,(x+.23,1.2,z+.005),(x+.23,back,z+.005),.018,'wood')
            beam('Descending stair skirting %d'%i,(x,back-.018,z+.09),(x+.24,back-.018,z+.09),.045,'white')
            beam('Descending skirting riser %d'%i,(x,back-.018,z+.09),(x,back-.018,z+.27),.045,'white')
        # The near barn-door wall occludes the continuation; no terminal wall is added.
        side=1.30
        wall('Descending far-side boundary',(right,back),(side,back),2.62,base=-.55)
        # Two genuine rectangular openings in left wall: glazed exterior door and raised entry door.
        wall('Left external wall',(left,front),(left,back),H,[(4.02,4.94,.54,2.55)])
        opening('Raised entry timber door',(left,front+4.02),(left,front+4.94),.54,2.55,door=True)
        # Window wall: two small side windows and tall center window with transom, cut out structurally.
        wall('Window wall',(left,back),(right,back),2.62,[(.75,1.27,1.65,2.15),(1.8,2.53,.53,2.28)],base=-.55)
        opening('Left small window',(left+.75,back),(left+1.27,back),1.65,2.15,glass=True)
        opening('Tall center window',(left+1.8,back),(left+2.53,back),.53,1.84,glass=True)
        opening('Center transom',(left+1.8,back),(left+2.53,back),1.91,2.28,glass=True)
        wall('Right window return',(side,back),(side,1.22),2.62,[(.42,.95,1.3,1.93)],base=-.55)
        opening('Right small window',(side,back-.42),(side,back-.95),1.3,1.93,glass=True)
        # This return encloses the stairwell side; it does not cross the descending direction (+x).
        wall('Stairwell near return',(side,1.22),(right,1.22),2.62,base=-.55)
        for name,loc in [('Left sconce',(-.94,back-.10,1.91)),('Right sconce',(.42,back-.10,1.57))]:
            x,y,z=loc
            box(name+' backplate',(x-.045,y,z-.075),(x+.045,y+.04,z+.075),'metal',bevel=.018)
            box(name+' frosted lamp',(x-.032,y-.015,z),(x+.032,y+.025,z+.12),'white',bevel=.012)
        wall('Barn door right wall',(right,1.22),(right,front),H,[(.01,3.45,0,2.58)],coll=cut)
        # Keep all physical leaf geometry in full model but cut it away for main view.
        before=set(full.objects)
        opening('White sliding double barn doors',(right,1.22),(right,-2.23),0,2.58,door=True,double=True)
        for obj in set(full.objects)-before:move(obj,cut)
        beam('Barn door black track',(right-.05,1.4,2.66),(right-.05,-2.37,2.66),.04,'metal',cut)
        for y in [1.05,-.12,-.65,-2.05]:box('Barn hinge',(right-.085,y-.035,2.36),(right-.03,y+.035,2.74),'metal',cut)
        wall('Garden door end wall',(left,front),(right,front),H,[(.65,2.9,0,2.14)],coll=cut)
        before=set(full.objects)
        opening('Glazed garden double door',(-1.8,front),(.45,front),0,2.14,glass=True)
        for obj in set(full.objects)-before:move(obj,cut)
        # L-shaped half wall; the long face encloses landing, short face protects stair mouth.
        box('Landing half wall long',(left,1.08,0),(-.77,1.2,1.12),'white')
        box('Landing half wall return',(-.77,.54,0),(-.65,1.2,1.12),'white')
        box('Half wall cap long',(left-.02,1.055,1.12),(-.795,1.225,1.165),'white',bevel=.025)
        box('Half wall cap return',(-.795,.52,1.12),(-.625,1.225,1.165),'white',bevel=.025)
        # Ceiling drop across entry as observed; no invented arch dimensions.
        box('Complete high ceiling',(left,front,H),(right,1.1,H+.1),'white',cut)
        box('Complete entry dropped ceiling',(left,1.1,2.62),(side,back,2.72),'white',cut)
        box('Entry soffit cut face',(left,1.03,2.62),(right,1.36,H),'white')
        wire=[[(left,front,0),(right,front,0),(right,back,0),(left,back,0),(left,front,0)],
              [(left,1.2,.54),(-1.22,1.2,.54),(-1.22,back,.54),(left,back,.54),(left,1.2,.54)],
              [(left,1.1,H),(right,1.1,H),(right,1.1,2.62),(left,1.1,2.62)]]
        for x,z in [(-1.22,.54),(-1,.36),(-.78,.18),(-.56,0)]:wire.append([(x,1.2,z),(x,back,z)])
        for x,z in [(.22,0),(.22,-.18),(.46,-.18),(.46,-.36),(.70,-.36)]:wire.append([(x,1.2,z),(x,back,z)])
        target=(-.75,.05,1.1);eye=(6,-8,6.1);reverse=(-7,7,6.3);scale=7.6;camera=(0,0,1.55)
        checks={'lower_floor_visible_area_m2':(right-left)*(1.2-front)+(.22+.56)*(back-1.2),'landing_area_m2':1.23*(back-1.2),'landing_height_m':.54,'ascending_stairs_count':3,'descending_visible_treads':2,'stairwell_side_return_closed':True,'descending_start_not_blocked':True,'window_openings':4,'large_low_floor_and_small_landing':True,'L_half_wall':True}
        assert checks['lower_floor_visible_area_m2']>3*checks['landing_area_m2']
        unknown=['All building RGBs reviewed: train0, valid0, test88; no second viewpoint of this entrance identified.','Stair height/width and far-side wall distance are photo-informed estimates. The two descending treads show only the visible start, not the total flight.','Photograph shows a curved soffit; the simplified ceiling drop preserves the height change, not its precise decorative curvature.','Near return joins the window enclosure to the barn-door wall. Descending steps run beside it, not through it. The unseen lower flight is outside the reconstructed vertical range.','Perimeter reconstructed from visible boundary contacts; it is not a surveyed floor plan.']
    for j,path in enumerate(wire):
        for a,b in zip(path,path[1:]):move(photo.line('Wireframe %02d'%j,a,b,p['line'],.008),support)
    # Diagnostic camera is in actual source-ray frame. Display view cameras are separate.
    diag=bpy.data.objects.new('Original source viewpoint',bpy.data.cameras.new('Original source viewpoint'))
    sc.collection.objects.link(diag);diag.location=camera;diag.rotation_euler=(Vector((0,1,0))).to_track_quat('-Z','Y').to_euler();diag.data.type='PERSP';diag.data.lens=20
    diag['source_rgb']=str(source(key));diag['source_camera_height_assumption_m']=1.55
    cam=sc.camera
    for obj in full.objects:obj['geometry_source']='observed RGB structure + predicted depth proportions; not GT'
    # Full and cutaway physical parts share geometry; hiding is only a view state.
    cut.hide_render=True;support.hide_render=True
    def set_view(eye,scale):
        cam.location=eye;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;sc.camera=cam
    set_view(eye,scale)
    metadata={'case':CASES[key][0],'source_rgb':str(source(key).relative_to(ROOT)),'depth_source':str((DEPTH/(CASES[key][2]+'.raw_pred_m.npy')).relative_to(ROOT)),
              'model_type':'photo-informed local explanatory reconstruction, approximate metric proportions','origin':'panorama camera x=y=0; ground z=0; camera-height assumption1.55m',
              'checks':checks,'unresolved':unknown,'full_geometry_collections':['FULL_MODEL','DISPLAY_CUTAWAY_ONLY'],
              'display_only_hidden_collection':'DISPLAY_CUTAWAY_ONLY','layout_gt_read':False,'annotations_modified':False,
              'render':{'size':[2400,1800],'cycles_samples':64,'device':'CPU','threads':6,'view_transform':'AgX'},'source_camera_xyz':camera}
    (out/'model_manifest.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'reconstruction.blend'))
    if build_only:
        meshes=[o for c in (full,cut) for o in c.objects if o.type=='MESH']
        assert all(all(math.isfinite(x) for v in o.data.vertices for x in v.co) for o in meshes)
        (out/'verification.json').write_text(json.dumps({'finite_mesh_vertices':True,'mesh_objects':len(meshes),'original_rgb_gt_annotations_untouched':True,'build_checks':checks,'source':unknown},ensure_ascii=False,indent=2),encoding='utf-8')
        return
    for name,loc in [('main_render',eye),('reverse_render',reverse)]:
        set_view(loc,scale);sc.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
    # Reprojection check: source viewpoint, all walls/ceiling restored, no invented panorama texture.
    cut.hide_render=False;sc.camera=diag;sc.render.resolution_x=1600;sc.render.resolution_y=1000;sc.cycles.samples=48
    sc.render.filepath=str(out/'source_camera_check.png');bpy.ops.render.render(write_still=True)
    cut.hide_render=True;sc.camera=cam;set_view(eye,scale);sc.render.resolution_x=2400;sc.render.resolution_y=1800
    full.hide_render=True;support.hide_render=False;sc.render.filepath=str(out/'wireframe.png');bpy.ops.render.render(write_still=True)
    full.hide_render=False;support.hide_render=True
    # Scene-wide topology finite and origin preservation checks; openings are constructed as separated wall pieces.
    meshes=[o for o in full.objects if o.type=='MESH']+[o for o in cut.objects if o.type=='MESH']
    assert all(all(math.isfinite(c) for v in o.data.vertices for c in v.co) for o in meshes)
    assert len(meshes)>25
    verification={'finite_mesh_vertices':True,'mesh_objects':len(meshes),'complete_shell_preserved_with_display_hiding':True,
                  'openings_have_separate_sill_pier_lintel_geometry':True,'source_camera_render_created':True,'photogrammetric_fit_or_metric_ground_truth':False,
                  'original_rgb_gt_annotations_untouched':True,'source':metadata['unresolved']}
    (out/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')

def review(key,draft=False):
    """Reframe saved mesh; render cutaways from both sides without changing structural vertices."""
    import bpy
    import numpy as np
    from mathutils import Vector
    sys.path.insert(0,str(Path(__file__).parent))
    import render_scope_blender_20261107 as core
    out=WORK/key;bpy.ops.wm.open_mainfile(filepath=str(out/'reconstruction.blend'))
    sc=bpy.context.scene;full=bpy.data.collections['FULL_MODEL'];cut=bpy.data.collections['DISPLAY_CUTAWAY_ONLY'];support=bpy.data.collections['DIAGNOSTIC_WIREFRAME']
    cam=sc.camera;sc.render.resolution_x=2400;sc.render.resolution_y=1800;sc.cycles.samples=64;sc.render.threads=6
    if draft:sc.render.resolution_percentage=50;sc.cycles.samples=16
    if '--gpu' in sys.argv:
        prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
        enabled=[]
        for device in prefs.devices:
            device.use=device.type=='OPTIX'
            if device.use:enabled.append(device.name)
        assert enabled,'No OPTIX device available'
        sc.cycles.device='GPU'
    # Architectural materials only; no generated or repainted source pixels.
    for name,lo,hi,scale in [('wood','#77563b','#b59369',4),('floor','#88897e','#b8b5a4',6),('high','#967b56','#bba786',5),('low','#baa88c','#dfd1b7',5)]:
        if key=='stairs' and name in ('high','low'):continue
        if name not in bpy.data.materials:continue
        mat=bpy.data.materials[name];nodes=mat.node_tree.nodes;links=mat.node_tree.links
        bs=nodes.get('Principled BSDF');noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=scale;noise.inputs['Detail'].default_value=3
        tex=nodes.new('ShaderNodeTexCoord');mapping=nodes.new('ShaderNodeVectorMath');mapping.operation='MULTIPLY';mapping.inputs[1].default_value=(1,14,1) if name!='floor' else (1,1,1)
        links.new(tex.outputs['Generated'],mapping.inputs[0]);links.new(mapping.outputs[0],noise.inputs['Vector'])
        ramp=nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=core.rgb(lo);ramp.color_ramp.elements[1].color=core.rgb(hi)
        links.new(noise.outputs['Fac'],ramp.inputs[0]);links.new(ramp.outputs['Color'],bs.inputs['Base Color'])
        bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.1;bump.inputs['Distance'].default_value=.012;links.new(noise.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs[0],bs.inputs['Normal'])
    if key=='stairs':
        # Dot's world-aligned floor shader is shared across treads and landing; never used on doors.
        import ast,types
        dot=ROOT/'docs/thesis_main/论文写作工作资料/Dot交付审查_20261106/Paper_Figures_4_5_6_10_CURRENT_ONLY_20261106/02_Figure6_latest/output'
        g=types.ModuleType('geometry_core');g.__dict__.update(bpy=bpy,np=np,math=math,Vector=Vector)
        tree=ast.parse((dot/'geometry_core.py').read_text(encoding='utf-8'))
        selected=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'rgb','matte'}],type_ignores=[])
        exec(compile(selected,str(dot/'geometry_core.py'),'exec'),g.__dict__);sys.modules['geometry_core']=g
        sys.path.insert(0,str(dot));import appearance_assets as a
        oak=a.wood()
        links=oak.node_tree.links;geo=next(n for n in oak.node_tree.nodes if n.type=='NEW_GEOMETRY')
        rotate=oak.node_tree.nodes.new('ShaderNodeVectorRotate');rotate.rotation_type='AXIS_ANGLE';rotate.inputs['Axis'].default_value=(0,0,1);rotate.inputs['Angle'].default_value=math.pi/2
        destinations=[link.to_socket for link in list(links) if link.from_node==geo]
        links.new(geo.outputs['Position'],rotate.inputs['Vector'])
        for socket in destinations:links.new(rotate.outputs['Vector'],socket)
        for n in oak.node_tree.nodes:
            if n.type=='TEX_BRICK':
                n.inputs['Color1'].default_value=g.rgb('#a28e75');n.inputs['Color2'].default_value=g.rgb('#beab8f');n.inputs['Mortar'].default_value=g.rgb('#887661')
                n.inputs['Brick Width'].default_value=1.05;n.inputs['Row Height'].default_value=.18;n.inputs['Mortar Size'].default_value=.001
        for obj in list(full.objects)+list(cut.objects):
            if obj.type!='MESH':continue
            for i,mat in enumerate(obj.data.materials):
                if mat and mat.name in ('low','high'):obj.data.materials[i]=oak
            for mod in list(obj.modifiers):
                if mod.type=='BEVEL':
                    if ('wall' in obj.name.lower() or 'boundary' in obj.name.lower()) and not any(w in obj.name for w in ['cap','casing','skirting','cornice','baseboard']):obj.modifiers.remove(mod)
                    else:mod.width=min(mod.width,.003);mod.segments=3
            if any(m.type=='BEVEL' for m in obj.modifiers):
                mod=obj.modifiers.new('Weighted architectural normals','WEIGHTED_NORMAL');mod.keep_sharp=True
        for name,color,rough in [('wall','#d0c9bd',.83),('white','#efede7',.57),('glass','#71868b',.2)]:
            bs=bpy.data.materials[name].node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=core.rgb(color);bs.inputs['Roughness'].default_value=rough
        sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.36
    # Trim only decorative bars at joins, avoiding coincident faces. Structural meshes are untouched.
    for obj in list(full.objects)+list(cut.objects):
        if key!='stairs' and obj.type=='MESH' and ('cornice' in obj.name or 'casing' in obj.name):
            vv=np.array([v.co[:] for v in obj.data.vertices]);length=vv[:,2].ptp() if hasattr(vv[:,2],'ptp') else np.ptp(vv[:,2])
            if length>.15:
                obj.scale.z*=max(.1,(length-.075)/length)
                for mod in obj.modifiers:
                    if mod.type=='BEVEL':mod.width=.0025
    target=Vector((1,-.3,2)) if key=='oblique' else Vector((-.8,0,1.2))
    views=[('main_render',(-4,-6,18)),('reverse_render',(7,5,18))] if key=='oblique' else [('main_render',(6,-7,26)),('reverse_render',(-6,6,24))]
    def fit(eye):
        bpy.context.view_layer.update()
        cam.location=eye;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';sc.camera=cam
        q=cam.rotation_euler.to_quaternion();right=q@Vector((1,0,0));up=q@Vector((0,1,0));coords=[]
        for obj in sc.objects:
            if obj.type!='MESH' or obj.hide_render or any(c.hide_render for c in obj.users_collection):continue
            coords += [obj.matrix_world@Vector(b) for b in obj.bound_box]
        xs=[p.dot(right) for p in coords];ys=[p.dot(up) for p in coords]
        center=right*((min(xs)+max(xs))/2)+up*((min(ys)+max(ys))/2)
        cam.location+=right*(center.dot(right)-cam.location.dot(right))+up*(center.dot(up)-cam.location.dot(up))
        cam.data.ortho_scale=max(max(xs)-min(xs),(max(ys)-min(ys))*2400/1800)*1.12
    hidden=[]
    for name,eye in views:
        if draft and name=='reverse_render':continue
        full.hide_render=False;cut.hide_render=False;support.hide_render=True
        for obj in hidden:obj.hide_render=False
        hidden=[]
        for obj in list(cut.objects):
            if 'ceiling' in obj.name.lower():obj.hide_render=True;hidden.append(obj)
        fit(eye);sc.render.filepath=str(out/(('draft_' if draft else '')+name+'.png'));bpy.ops.render.render(write_still=True)
    for obj in hidden:obj.hide_render=False
    cut.hide_render=False;support.hide_render=True;full.hide_render=False
    diag=bpy.data.objects['Original source viewpoint'];diag.data.lens=12;sc.camera=diag
    lamp=bpy.data.objects.new('Diagnostic interior illumination',bpy.data.lights.new('Diagnostic interior illumination','POINT'))
    sc.collection.objects.link(lamp);lamp.location=(0,0,2.25);lamp.data.energy=110;lamp.data.shadow_soft_size=.7
    sc.render.resolution_x=1600;sc.render.resolution_y=1000;sc.cycles.samples=32
    sc.render.filepath=str(out/(('draft_' if draft else '')+'source_camera_check.png'));bpy.ops.render.render(write_still=True)
    if draft:return
    lamp.hide_render=True;sc.render.resolution_x=2400;sc.render.resolution_y=1800;sc.cycles.samples=64
    cut.hide_render=False
    for obj in cut.objects:
        if 'ceiling' in obj.name.lower():obj.hide_render=True
    fit(views[0][1]);full.hide_render=True;cut.hide_render=True;support.hide_render=False
    sc.cycles.samples=16;sc.render.filepath=str(out/'wireframe.png');bpy.ops.render.render(write_still=True)
    full.hide_render=False;cut.hide_render=False;support.hide_render=True;sc.cycles.samples=64
    sc.render.filepath=str(out/'main_render.png')
    # Save the user-facing model with the corrected default cutaway and original-view camera retained.
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'reconstruction.blend'))
    j=json.loads((out/'verification.json').read_text(encoding='utf-8'))
    meshes=[o for c in (full,cut) for o in c.objects if o.type=='MESH']
    assert all(all(math.isfinite(x) for v in o.data.vertices for x in v.co) for o in meshes)
    wall_objects=[o for o in meshes if ('wall' in o.name.lower() or 'perimeter' in o.name.lower()) and 'ceiling' not in o.name.lower()]
    assert wall_objects and all(not o.hide_render and not any(c.hide_render for c in o.users_collection) for o in wall_objects)
    bpy.context.view_layer.update();depsgraph=bpy.context.evaluated_depsgraph_get()
    holes=[('Open doorway wall',(-.7,1.1,1),(0,1,0))] if key=='oblique' else [('Window wall',(-.3,2.3,1.2),(0,1,0)),('Garden door end wall',(-.6,-2.9,1),(0,1,0)),('Left external wall',(-2.75,1.8,1.6),(1,0,0))]
    hole_checks={}
    for prefix,origin,direction in holes:
        walls=[o for o in meshes if o.name.startswith(prefix) and not any(t in o.name for t in ('cornice','baseboard'))]
        assert walls
        hit=any(o.evaluated_get(depsgraph).ray_cast(Vector(origin),Vector(direction),distance=.75)[0] for o in walls)
        assert not hit,prefix+' opening blocked by wall mesh'
        hole_checks[prefix]=True
    if key=='stairs':
        for x,z in [(.34,-.18),(.58,-.36)]:
            hit,loc,*_=sc.ray_cast(depsgraph,Vector((x,1.8,.1)),Vector((0,0,-1)),distance=1)
            assert hit and abs(loc.z-z)<.012,('descending floor covered',x,loc[:])
        hit,*_=sc.ray_cast(depsgraph,Vector((.73,1.8,-.25)),Vector((1,0,0)),distance=.4)
        assert not hit,'The side return must not block the descending direction'
        hit,_,_,_,obj,_=sc.ray_cast(depsgraph,Vector((.95,.95,1.2)),Vector((0,1,0)),distance=.5)
        assert hit and obj.name.startswith('Stairwell near return'),'Missing wall beside descending stairwell'
        hole_checks.update({'descending_treads_below_central_floor':True,'side_return_present':True,'descending_direction_clear':True})
    j.update({'framing_fit':'visible meshes bounds plus12percent margin','decorative_joint_overlap_reduced':True,'procedural_material_not_photo_texture':True,'main_and_reverse_keep_all_perimeter_walls':True,'ceiling_hidden_for_roof_removed_view_only':True})
    j.update({'mesh_objects':len(meshes),'finite_mesh_vertices':True,'wall_objects_visible_in_saved_scene':len(wall_objects),'actual_wall_opening_raycast_checks':hole_checks,'render_device':sc.cycles.device,'source':json.loads((out/'model_manifest.json').read_text(encoding='utf-8'))['unresolved']})
    (out/'verification.json').write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
    metadata=json.loads((out/'model_manifest.json').read_text(encoding='utf-8'))
    metadata.update({'primary_display':'all perimeter walls retained; roof panels hidden only','display_only_hidden_collection':None,'render':{'size':[2400,1800],'cycles_samples':64,'device':sc.cycles.device,'view_transform':'AgX'}})
    (out/'model_manifest.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')

def finish(keys=('oblique','stairs')):
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
    for key in keys:
        out=WORK/key
        for name in ['main_render','reverse_render','wireframe','source_camera_check']:
            path=out/(name+'.png')
            if not path.exists():continue
            im=Image.open(path).convert('RGBA');white=Image.new('RGBA',im.size,'white');white.alpha_composite(im);white.convert('RGB').save(path)
        # Real-photo versus model camera view: perspective uses exactly the original pano camera direction.
        src=Image.open(source(key)).convert('RGB');w,h=1600,1000;fov=math.degrees(2*math.atan(36/24))
        x=np.linspace(-math.tan(math.radians(fov/2)),math.tan(math.radians(fov/2)),w)
        z=np.linspace(math.tan(math.radians(fov/2))*h/w,-math.tan(math.radians(fov/2))*h/w,h)
        X,Z=np.meshgrid(x,z);Y=np.ones_like(X);lon=np.arctan2(X,Y);lat=np.arctan2(Z,np.sqrt(X*X+Y*Y))
        import cv2
        image=cv2.remap(np.array(src),((lon/(2*np.pi)+.5)*2048).astype('float32'),((.5-lat/np.pi)*1024).astype('float32'),cv2.INTER_LINEAR,borderMode=cv2.BORDER_WRAP)
        photo=Image.fromarray(image);photo.save(out/'source_perspective.png')
        model=Image.open(out/'source_camera_check.png').convert('RGB').resize((w,h))
        board=Image.new('RGB',(w*2,h+50),'white');board.paste(photo,(0,50));board.paste(model,(w,50));d=ImageDraw.Draw(board)
        font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',24)
        d.text((20,10),'Original panorama: perspective from same camera',fill='black',font=font)
        d.text((w+20,10),'Reconstruction check: same direction, approximate geometry',fill='black',font=font)
        board.save(out/'source_view_comparison.png')

def verify_saved(key):
    import bpy
    from mathutils import Vector
    from bpy_extras.object_utils import world_to_camera_view
    out=WORK/key;bpy.ops.wm.open_mainfile(filepath=str(out/'reconstruction.blend'))
    sc=bpy.context.scene;bpy.context.view_layer.update()
    meshes=[o for c in ('FULL_MODEL','DISPLAY_CUTAWAY_ONLY') for o in bpy.data.collections[c].objects if o.type=='MESH']
    assert all(all(math.isfinite(x) for v in o.data.vertices for x in v.co) for o in meshes)
    walls=[o for o in meshes if ('wall' in o.name.lower() or 'perimeter' in o.name.lower()) and 'ceiling' not in o.name.lower()]
    assert walls and all(not o.hide_render and not any(c.hide_render for c in o.users_collection) for o in walls)
    corners=[world_to_camera_view(sc,sc.camera,o.matrix_world@Vector(b)) for o in meshes if not o.hide_render for b in o.bound_box]
    bounds=[min(v.x for v in corners),max(v.x for v in corners),min(v.y for v in corners),max(v.y for v in corners)]
    assert min(bounds[0],bounds[2])>=.01 and max(bounds[1],bounds[3])<=.99,bounds
    record=json.loads((out/'verification.json').read_text(encoding='utf-8'))
    record.update({'saved_scene_meshes_checked':len(meshes),'saved_scene_wall_objects_visible':len(walls),'saved_main_view_bounds_xy':bounds,'saved_main_view_no_clipping':True,'source':json.loads((out/'model_manifest.json').read_text(encoding='utf-8'))['unresolved']})
    (out/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False))



if __name__=='__main__':
    mode=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else sys.argv[1]
    if mode=='depth':depth()
    elif mode=='prepare':prepare()
    elif mode in ('oblique','stairs'):render(mode)
    elif mode.startswith('build_'):render(mode.removeprefix('build_'),True)
    elif mode.startswith('final_'):
        key=mode.removeprefix('final_');render(key,True);review(key)
    elif mode.startswith('draft_'):
        key=mode.removeprefix('draft_');render(key,True);review(key,True)
    elif mode.startswith('review_'):review(mode.removeprefix('review_'))
    elif mode=='finish':finish()
    elif mode.startswith('verify_'):verify_saved(mode.removeprefix('verify_'))
