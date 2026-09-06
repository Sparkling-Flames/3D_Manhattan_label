"""Deterministic raw-layout evidence. No Manhattan fit or corner-adjacency edits.
Perspective views resample the original panorama. 3D texture is a projection of
that SAME image onto a relative-height proxy, not an independent observation.
"""
import sys,math,json,hashlib,argparse
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image,ImageDraw,ImageFont
import cv2
from shapely.geometry import Polygon,Point
import measure as m
sys.path.insert(0,str(m.ROOT))
from tools.label_studio.panorama_studio.geometry import triangulate
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
def font(n=16):return ImageFont.truetype(FONT,n) if Path(FONT).exists() else ImageFont.load_default()
def label(im,text):
 d=ImageDraw.Draw(im);d.rectangle((0,0,im.width,26),fill='white');d.text((8,4),text,fill='black',font=font(15));return im

def sample(image,uv):
 h,w=image.shape[:2];x=(uv[...,0]/1024*w).astype('float32')%w;y=np.clip(uv[...,1]/512*h,0,h-1).astype('float32')
 return cv2.remap(image,x,y,cv2.INTER_LINEAR,borderMode=cv2.BORDER_WRAP)
def perspective(image,yaw=0,pitch=0,w=640,h=420,fov=90):
 ya,pi=np.radians([yaw,pitch]);f=np.array([np.cos(pi)*np.sin(ya),np.sin(pi),-np.cos(pi)*np.cos(ya)]);right=np.array([np.cos(ya),0,np.sin(ya)]);up=np.cross(right,f)
 x=((np.arange(w)+.5)/w*2-1)*np.tan(np.radians(fov/2));y=(1-(np.arange(h)+.5)/h*2)*np.tan(np.radians(fov/2))*h/w
 rr=f+x[None,:,None]*right+y[:,None,None]*up;uv=m.project(rr);return Image.fromarray(sample(image,uv)),dict(yaw=yaw,pitch=pitch,hfov=fov,width=w,height=h,projection='pinhole_from_original_panorama')

def overlay(image,points,role_map=True,title=''):
 im=Image.fromarray(image).resize((1024,512));dr=ImageDraw.Draw(im);a=np.asarray(points,float)
 if role_map:
  try:
   aa,_=m.roles(points)
   for rows in (aa[::2],aa[1::2]):
    rays=m.ray(rows)
    for i in range(len(rows)):
     curve=m.project((1-np.linspace(0,1,161)[:,None])*rays[i]+np.linspace(0,1,161)[:,None]*rays[(i+1)%len(rows)])
     for left,right in zip(curve[:-1],curve[1:]):
      if abs(right[0]-left[0])<512:dr.line([tuple(left),tuple(right)],fill='white',width=3);dr.line([tuple(left),tuple(right)],fill='black',width=1)
   for top,bottom in aa.reshape(-1,2,2):
    if abs(top[0]-bottom[0])<512:dr.line([tuple(top),tuple(bottom)],fill='white',width=2)
  except ValueError:pass
 if a.ndim==2:
  for i,(x,y) in enumerate(a):
   if not np.isfinite([x,y]).all():continue
   dr.ellipse((x-3,y-3,x+3,y+3),fill='white',outline='black');dr.text((x+4,y-14),str(i+1),font=font(16),fill='white',stroke_width=2,stroke_fill='black')
 return label(im,title)

def reconstruct(points):
 a,mapping=m.roles(points);r=m.ray(a);floor=-r[1::2]/r[1::2,1,None]
 if np.min(abs(r[1::2,1]))<math.sin(math.radians(.5)):raise ValueError('near_horizon_3d_numerical_guard_no_clipping')
 ceil=r[::2]*(np.linalg.norm(floor[:,[0,2]],axis=1)/np.linalg.norm(r[::2][:,[0,2]],axis=1))[:,None]
 poly=Polygon(floor[:,[0,2]]);valid=poly.is_valid and poly.area>1e-10;inside=valid and poly.contains(Point(0,0));tri=triangulate(floor[:,[0,2]]) if valid else []
 area=sum(abs(np.cross(floor[j,[0,2]]-floor[i,[0,2]],floor[k,[0,2]]-floor[i,[0,2]]))/2 for i,j,k in tri)
 back=m.project(np.stack([ceil,floor],axis=1).reshape(-1,3));delta=back-a;delta[:,0]=(delta[:,0]+512)%1024-512
 q=dict(role_map=mapping,endpoint_role_swaps=sum(i!=j for i,j in enumerate(mapping))//2,coordinates_changed=False,corner_adjacency_changed=False,cyclic_origin_changed=False,cycle_reversed=False,
   roundtrip_max_pixels=float(abs(delta).max()),pair_dx_max=float(abs((a[::2,0]-a[1::2,0]+512)%1024-512).max()),footprint_valid=bool(valid),camera_inside=bool(inside),triangulation_area_error=float(abs(area-poly.area)) if valid else None,
   floor_unit='camera_height_relative_1_not_meters',ceiling_depth='own_top_ray_using_paired_floor_horizontal_range_proxy',filled_surface=bool(valid and inside),reason='' if valid and inside else 'original_footprint_invalid_or_camera_outside_wireframe_only',floor=floor.tolist(),ceiling=ceil.tolist(),floor_triangles=tri)
 return floor,ceil,q

def render_mesh(image,floor,ceil,qa,kind='oblique',w=640,h=480):
 pts=np.vstack([floor,ceil]);center=(pts.min(axis=0)+pts.max(axis=0))/2
 if kind=='top':fw=np.array([0.,-1.,0.]);right=np.array([1.,0.,0.]);up=np.array([0.,0.,-1.])
 else:
  fw=-np.array([1.,1.8,1.25]);fw/=np.linalg.norm(fw);right=np.cross(fw,[0,1,0]);right/=np.linalg.norm(right);up=np.cross(right,fw)
 def uvz(p):return np.c_[(p-center)@right,-(p-center)@up,(p-center)@fw]
 projected=uvz(pts);scale=min((w-64)/max(np.ptp(projected[:,0]),1e-6),(h-90)/max(np.ptp(projected[:,1]),1e-6));xy=projected[:,:2]*scale+[w/2,h/2+10];canvas=np.full((h,w,3),242,np.uint8);zb=np.full((h,w),np.inf)
 tris=[];n=len(floor)
 if qa['filled_surface']:
  tris.extend(qa['floor_triangles'])
  for i in range(n):j=(i+1)%n;tris.extend([[i,j,n+j],[i,n+j,n+i]])
 for tri in tris:
  a,b,c=xy[tri];lo=np.maximum(np.floor(np.min([a,b,c],axis=0)).astype(int),0);hi=np.minimum(np.ceil(np.max([a,b,c],axis=0)).astype(int),[w-1,h-1])
  if np.any(hi<lo):continue
  xx,yy=np.meshgrid(np.arange(lo[0],hi[0]+1)+.5,np.arange(lo[1],hi[1]+1)+.5)
  denom=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
  if abs(denom)<1e-8:continue
  wa=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/denom;wb=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/denom;wc=1-wa-wb
  inside=(wa>=-1e-8)&(wb>=-1e-8)&(wc>=-1e-8);depth=wa*projected[tri[0],2]+wb*projected[tri[1],2]+wc*projected[tri[2],2]
  sub=zb[lo[1]:hi[1]+1,lo[0]:hi[0]+1];mask=inside&(depth<sub)
  world=wa[...,None]*pts[tri[0]]+wb[...,None]*pts[tri[1]]+wc[...,None]*pts[tri[2]];tex=sample(image,m.project(world));patch=canvas[lo[1]:hi[1]+1,lo[0]:hi[0]+1];patch[mask]=tex[mask];sub[mask]=depth[mask]
 im=Image.fromarray(canvas);dr=ImageDraw.Draw(im)
 for i in range(n):
  j=(i+1)%n
  for x,y in [(i,j),(n+i,n+j),(i,n+i)]:dr.line([tuple(xy[x]),tuple(xy[y])],fill='black',width=2)
  dr.text(tuple(xy[i]+[4,2]),f'P{i+1}',fill='black',font=font(15),stroke_width=2,stroke_fill='white')
 camera=uvz(np.zeros((1,3)))[0,:2]*scale+[w/2,h/2+10];dr.ellipse((camera[0]-4,camera[1]-4,camera[0]+4,camera[1]+4),fill='white',outline='black');dr.text(tuple(camera+[5,0]),'camera',fill='black',font=font(12))
 dr.text((8,h-34),'Same panorama projected on assumed mesh; relative scale.',fill='black',font=font(13));dr.text((8,h-18),'Auto extent per variant; not independent 3D observation.',fill='black',font=font(13))
 return label(im,kind+' / '+('raw ray proxy' if qa['filled_surface'] else 'DIAGNOSTIC WIREFRAME; fill blocked'))

def sheet(paths,out,cols=2,width=1024):
 ims=[Image.open(p).convert('RGB') for p in paths];thumbs=[]
 for im in ims:thumbs.append(im.resize((width,round(im.height*width/im.width))))
 rows=[thumbs[i:i+cols] for i in range(0,len(thumbs),cols)];H=sum(max(im.height for im in row) for row in rows);canvas=Image.new('RGB',(width*cols,H),'white');y=0
 for row in rows:
  for j,im in enumerate(row):canvas.paste(im,(j*width,y))
  y+=max(im.height for im in row)
 canvas.save(out,quality=94)

def build(phase):
 a,im,parts,mem,versions,models,refs,raw,norm=m.load();sel=m.read(m.O/'census/selection_12.csv');sel=sel[sel.phase==phase];cluster=pd.read_csv(m.O/'analysis/footprint_cluster_proximity.csv');cluster=cluster.astype(object).where(pd.notna(cluster),None);logs=[];fail=[]
 for sr in sel.to_dict('records'):
  cid=sr['case_id'];mid=sr['image_id'];out=m.O/'cases'/cid;out.mkdir(parents=True,exist_ok=True);src=m.O/'originals'/f'{cid}_original.jpg'
  if not src.exists():fail.append(dict(case_id=cid,variant='',reason='original_download_missing'));continue
  image=np.array(Image.open(src).convert('RGB'));layouts=[]
  for r in models:
   if r['image_id']==mid and (r['source_role']=='offline_dual_prediction' or r['source_role']=='offline_ep300_replay'):layouts.append(dict(name=r['model_family']+'_'+r['head'],role='offline_model',key=r['layout_id'],points=r['points_1024x512'],source=r))
  for j,r in enumerate(rr for rr in refs if rr['image_id']==mid):layouts.append(dict(name='reference_'+str(j+1),role='reference_not_assumed_true',key=r['layout_id'],points=r['points_1024x512'],source=r))
  cc=cluster[(cluster.image_id==mid)&(cluster.floor_support>0)].sort_values(['context_key','rank'])
  chosen=cc.groupby('context_key').head(2)
  for j,r in enumerate(chosen.to_dict('records')):
   k=r['display_representative_id'];source=raw[k];layouts.append(dict(name='human_'+str(j+1)+'_W'+str(source['worker_id']),role='existing_cluster_display_member',key=k,points=source['points_1024x512'],source=source,cluster=r))
  m.dump(f'cases/{cid}/source_layouts.json',layouts)
  local=[];camera=[]
  for yaw in [0,90,180,-90]:
   view,meta=perspective(image,yaw);name=f'perspective_{yaw}.jpg';label(view,f'{cid} yaw {yaw} deg / pitch 0 / HFOV 90').save(out/name,quality=94);local.append(out/name);camera.append(meta)
  sheet(local,out/'perspective_contact.jpg',cols=2,width=640);m.dump(f'cases/{cid}/perspective_cameras.json',camera)
  overlays=[];meshes=[]
  for j,l in enumerate(layouts):
   tag=f'L{j+1:02}';base=out/tag;base.mkdir(exist_ok=True);rawhash=hashlib.sha256(json.dumps(l['points'],separators=(',',':')).encode()).hexdigest();m.dump(f'cases/{cid}/{tag}/raw_points.json',dict(layout_key=l['key'],original_points=l['points'],point_numbers='1-based original serialized row numbers',sha256=rawhash))
   overlay(image,l['points'],False,f'{tag} {l["name"]} / raw numbered points; no inferred edges').save(base/'raw_points.jpg',quality=94)
   overlay(image,l['points'],True,f'{tag} {l["name"]} / original paired-cycle projected edges').save(base/'projected_overlay.jpg',quality=94);overlays.append(base/'projected_overlay.jpg')
   try:
    f,c,q=reconstruct(l['points']);q.update(case_id=cid,variant=tag,name=l['name'],layout_key=l['key'],raw_coordinate_hash=rawhash,role='read_only_preview_not_repaired_annotation')
    m.dump(f'cases/{cid}/{tag}/preview_geometry.json',q)
    render_mesh(image,f,c,q,'top').save(base/'top.jpg',quality=94);render_mesh(image,f,c,q,'oblique').save(base/'oblique.jpg',quality=94);meshes.extend([base/'top.jpg',base/'oblique.jpg'])
    logs.append({k:v for k,v in q.items() if k not in ['floor','ceiling','floor_triangles']})
    if not q['filled_surface']:fail.append(dict(case_id=cid,variant=tag,reason=q['reason'],raw_preview_preserved=True))
   except (ValueError,IndexError) as e:
    q=dict(case_id=cid,variant=tag,name=l['name'],layout_key=l['key'],raw_coordinate_hash=rawhash,reason=str(e),coordinates_changed=False,corner_adjacency_changed=False);logs.append(q);fail.append(q)
    blank=Image.new('RGB',(640,480),'white');dr=ImageDraw.Draw(blank);dr.text((15,80),'3D preview blocked: '+str(e),font=font(15),fill='black');blank.save(base/'top.jpg');blank.save(base/'oblique.jpg');meshes.extend([base/'top.jpg',base/'oblique.jpg'])
   if logs[-1].get('endpoint_role_swaps',0):sheet([base/'raw_points.jpg',base/'projected_overlay.jpg'],base/'before_after_role_interpretation.jpg',cols=2,width=1024)
  sheet(overlays,out/'overlays_contact.jpg',cols=2,width=1024);sheet(meshes,out/'mesh_contact.jpg',cols=2,width=640)
  print(cid,'variants',len(layouts),flush=True)
 m.save(f'rendering/{phase}_preview_log.csv',logs);m.dump(f'rendering/{phase}_preview_log.json',logs);m.save(f'rendering/{phase}_failures.csv',fail if fail else [dict(case_id='',variant='',reason='none')])

def tests():
 rng=np.random.default_rng(137);a=rng.uniform([0,1],[1024,511],size=(10000,2));b=m.project(m.ray(a));dif=b-a;dif[:,0]=(dif[:,0]+512)%1024-512
 grid=np.zeros((512,1024,3),np.uint8);grid[:,:,0]=(np.arange(1024)[None,:]//4)%256;grid[:,:,1]=np.arange(512)[:,None]//2;grid[:,:,2]=127
 returned=sample(grid,m.project(m.ray(a)));expected=sample(grid,a)
 checks=dict(pixel_ray_roundtrip_max=float(abs(dif).max()),texture_sample_roundtrip_max=int(abs(returned.astype(int)-expected.astype(int)).max()),coordinate_convention='u=2pi(x/1024-.5), elevation=pi(.5-y/512), Y up, forward -Z',source_metric_pixel_centers='stored coordinates unchanged; sample columns at j+.5',manhattan_fit_performed=False)
 assert checks['pixel_ray_roundtrip_max']<1e-8 and checks['texture_sample_roundtrip_max']<=1
 m.dump('rendering/numerical_calibration.json',checks)
 if not (m.O/'rendering').exists():(m.O/'rendering').mkdir()
 im=Image.fromarray(grid);d=ImageDraw.Draw(im)
 for j in range(8):d.text((j*128+10,230),str(j*45-180)+' deg',font=font(20),fill='white',stroke_width=2,stroke_fill='black')
 im.save(m.O/'rendering/texture_coordinate_grid.png')
 views=[]
 for j in range(8):
  v,_=perspective(np.array(im),j*45-180,w=320,h=240,fov=70);q=m.O/'rendering'/f'texture_direction_{j}.jpg';label(v,str(j*45-180)+' deg').save(q);views.append(q)
 sheet(views,m.O/'rendering/texture_directions.jpg',cols=4,width=320)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['calibration','expansion'],default='calibration');args=parser.parse_args();tests();build(args.phase)
