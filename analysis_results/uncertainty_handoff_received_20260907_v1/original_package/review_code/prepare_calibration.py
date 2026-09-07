"""Generate calibration evidence; generation is NOT visual review. No fitting or ring sorting."""
from pathlib import Path
import sys,json,re,base64,hashlib,math
import numpy as np
import pandas as pd
from PIL import Image,ImageDraw,ImageFont
from shapely.ops import triangulate
from shapely.geometry import Polygon
from audit import ROOT,P,O,load,roles,lift,project,ray,footprint,read,dump,save
FONT=ImageFont.load_default(size=15)
def title(im,text):
 out=Image.new('RGB',(im.width,im.height+32),'white');out.paste(im,(0,32));ImageDraw.Draw(out).text((8,7),text,fill='black',font=FONT);return out

def sample(tex,pts):
 a=project(pts);h,w=tex.shape[:2];x=np.mod(np.rint(a[...,0]/1024*w).astype(int),w);y=np.clip(np.rint(a[...,1]/512*h).astype(int),0,h-1);return tex[y,x]
def perspective(tex,yaw,width=480,height=320,fov=80):
 u=np.deg2rad(yaw);f=np.array([np.sin(u),0,-np.cos(u)]);right=np.array([np.cos(u),0,np.sin(u)]);x=(2*(np.arange(width)+.5)/width-1)*np.tan(np.deg2rad(fov/2));y=(1-2*(np.arange(height)+.5)/height)*np.tan(np.deg2rad(fov/2))*height/width;v=f+x[None,:,None]*right+y[:,None,None]*np.array([0,1,0]);return Image.fromarray(sample(tex,v))
def path(draw,xy,color,width=2):
 for i in range(len(xy)-1):
  if abs(xy[i+1,0]-xy[i,0])<512:draw.line([tuple(xy[i]),tuple(xy[i+1])],fill=color,width=width)
def overlay(tex,points,mapped):
 im=Image.fromarray(tex).resize((1024,512));dr=ImageDraw.Draw(im);p=np.asarray(points,float);mp=list(range(len(p)))
 if mapped:
  f,t,mp=lift(p)
  for ring in [f,t]:
   for i in range(len(ring)):
    z=ring[i][None,:]*(1-np.linspace(0,1,81)[:,None])+ring[(i+1)%len(ring)][None,:]*np.linspace(0,1,81)[:,None];path(dr,project(z),(255,210,0))
  for i in range(len(f)):path(dr,project(np.stack([f[i],t[i]])),(0,255,240))
 else:
  for off in [0,1]:
   r=p[off::2];path(dr,np.vstack([r,r[0]]),(255,100,100))
 for i,(x,y) in enumerate(p):
  dr.ellipse([x-3,y-3,x+3,y+3],fill=(255,255,255),outline=(0,0,0));dr.text((x+4,y+3),str(i),font=FONT,fill=(255,255,255),stroke_width=1,stroke_fill=(0,0,0))
 return im,mp

def surfaces(f,t):
 poly=Polygon(f[:,[0,2]])
 if not poly.is_valid:raise ValueError('invalid_original_footprint_no_mesh')
 tris=[]
 for tr in triangulate(poly):
  if poly.covers(tr):
   xz=np.array(tr.exterior.coords)[:3];q=np.column_stack([xz[:,0],np.full(3,-1.),xz[:,1]]);tris.append(q)
 for i in range(len(f)):
  j=(i+1)%len(f);tris.extend([np.array([f[i],f[j],t[j]]),np.array([f[i],t[j],t[i]])])
 return tris

def render(tex,f,t,top=False,scale=None,size=440):
 tris=surfaces(f,t);q=np.concatenate([f,t]);target=np.array([0.,-.5,0.]);eye=np.array([0,6,0.]) if top else np.array([4.,4.,5.]);forward=(target-eye);forward/=np.linalg.norm(forward);up0=np.array([0.,0.,-1.]) if top else np.array([0.,1.,0.]);right=np.cross(forward,up0);right/=np.linalg.norm(right);up=np.cross(right,forward);s=scale or max(np.ptp(q[:,0]),np.ptp(q[:,2]),np.ptp(q[:,1]),1)*1.35
 color=np.full((size,size,3),238,np.uint8);dep=np.full((size,size),np.inf)
 def screen(p):return np.stack([(p-target)@right/s*size+size/2,size/2-(p-target)@up/s*size,(p-eye)@forward],axis=1)
 for tr in tris:
  pr=screen(tr);x0=max(0,int(np.floor(pr[:,0].min())));x1=min(size-1,int(np.ceil(pr[:,0].max())));y0=max(0,int(np.floor(pr[:,1].min())));y1=min(size-1,int(np.ceil(pr[:,1].max())))
  if x0>x1 or y0>y1:continue
  xx,yy=np.meshgrid(np.arange(x0,x1+1)+.5,np.arange(y0,y1+1)+.5);a,b,c=pr;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
  if abs(den)<1e-10:continue
  w0=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den;w1=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den;w2=1-w0-w1;zz=w0*a[2]+w1*b[2]+w2*c[2];ok=(w0>=-1e-8)&(w1>=-1e-8)&(w2>=-1e-8)&(zz<dep[y0:y1+1,x0:x1+1]);xyz=w0[...,None]*tr[0]+w1[...,None]*tr[1]+w2[...,None]*tr[2];rgb=sample(tex,xyz);color[y0:y1+1,x0:x1+1][ok]=rgb[ok];dep[y0:y1+1,x0:x1+1][ok]=zz[ok]
 im=Image.fromarray(color);dr=ImageDraw.Draw(im)
 for i,p in enumerate(f):
  x,y,_=screen(p);dr.ellipse([x-3,y-3,x+3,y+3],fill=(255,220,0));dr.text((x+4,y+3),f'pair {i}',font=FONT,fill=(0,0,0),stroke_fill=(255,255,255),stroke_width=1)
 return im

def run():
 census_path=O/'census/images_380.csv'
 if not census_path.exists():raise RuntimeError('Census not complete: selection prohibited')
 census=pd.read_csv(census_path);assets=ROOT/'available_images';assets.mkdir(exist_ok=True);studio=ROOT/'analysis_results/panorama_studio_20260906_v2';s=(studio/'data.js').read_text();d=json.loads(s[s.index('=')+1:].strip().rstrip(';'));sources=[]
 for i,c in enumerate(d['cases']):
  mid=c.get('id',c.get('image_id',''));text=(studio/f'image_{i:02}.js').read_text();m=re.search(r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)',text)
  if m and mid:
   b=base64.b64decode(m.group(1));f=assets/f'{mid}.jpg';f.write_bytes(b);sources.append(dict(image_id=mid,file=str(f),source=str((studio/f'image_{i:02}.js').relative_to(ROOT)),sha256=hashlib.sha256(b).hexdigest()))
 avail=census.merge(pd.DataFrame(sources),on='image_id',how='inner');save('census/available_image_assets.csv',avail)
 # Preserve exact-byte provenance. Availability-constrained exploratory calibration, not random prevalence sample.
 pool=avail[avail.human30_id.fillna('')==''].copy();selected=[];buildings=set()
 for score,asc,reason in [('human_floor_mean',False,'higher observed human floor dispersion'),('human_floor_mean',True,'lower observed human floor dispersion'),('bi_floor',False,'larger Bi floor gap'),('bi_floor',True,'smaller Bi floor gap')]:
  ss=pool[~pool.building_id.isin(buildings)&~pool.image_id.isin([x['image_id'] for x in selected])].sort_values([score,'image_id'],ascending=[asc,True])
  if ss.empty:ss=pool[~pool.image_id.isin([x['image_id'] for x in selected])].sort_values([score,'image_id'],ascending=[asc,True])
  if ss.empty:break
  r=ss.iloc[0].to_dict();r.update(case_id=f'V{len(selected)+1:02}',phase='calibration',selection_reason=reason,selection_constraint='available pinned studio image bytes; remote download failed',visual_review_completed=False);selected.append(r);buildings.add(r['building_id'])
 save('selection.csv',selected)
 a,im,pa,me,ve,mo,re,raw,norm=load();clusters=pd.read_csv(O/'analysis/clusters_to_bi.csv');allvariants=[];cal=[];fail=[]
 for sel in selected:
  mid=sel['image_id'];cid=sel['case_id'];dest=O/'cases'/cid;dest.mkdir(parents=True,exist_ok=True);original=Image.open(sel['file']).convert('RGB');original.save(dest/'01_original_blind.jpg',quality=95);tex=np.asarray(original);views=[]
  for yaw in [0,90,180,270]:
   v=title(perspective(tex,yaw),f'yaw {yaw}, horizontal FOV 80 deg');v.save(dest/f'perspective_{yaw}.jpg',quality=95);views.append(v)
  grid=Image.new('RGB',(960,704),'white')
  for i,v in enumerate(views):grid.paste(v,((i%2)*480,(i//2)*352))
  grid.save(dest/'02_perspectives.jpg',quality=95)
  variants=[]
  for r in mo:
   if r['image_id']==mid and r['source_role'] in ['offline_dual_prediction','offline_ep300_replay']:variants.append(dict(name=r['model_family']+'_'+r['head'],source_id=r['layout_id'],points=r['points_1024x512'],source_path=r.get('source_path',''),source_role=r['source_role']))
  for r in re:
   if r['image_id']==mid:variants.append(dict(name='reference_'+str(len(variants)),source_id=r['layout_id'],points=r['points_1024x512'],source_path=r.get('source_path',''),source_role=r.get('source_role',''),scope_status=r.get('scope_status',''),reference_status=r.get('reference_quality_status','')))
  cs=clusters[(clusters.image_id==mid)&clusters.representative_id.notna()].sort_values(['rank','cluster_id']).head(3)
  for r in cs.to_dict('records'):
   k=r['representative_id'];variants.append(dict(name='human_cluster_rank_'+str(r['rank']),source_id=k,points=norm[k],source_role='new_display_medoid_of_existing_cluster',cluster_id=r['cluster_id'],partition_id=r['partition_id'],cluster_support=r['original_support'],raw_points=raw[k]['points_1024x512'],source_path=raw[k]['source_path']))
  for j,v in enumerate(variants):
   vid=f'{j:02}_{v["name"]}';row=dict(case_id=cid,image_id=mid,variant=vid,source_id=v['source_id'],coordinate_mode='1024x512 pixels, no pixel-center offset',camera_height='1 relative unit, no metric scale',corner_adjacency_changed=False,cycle_reversed=False,cycle_start_changed=False,coordinates_changed=False,viewed_by_assistant=False)
   dump(f'cases/{cid}/{vid}_source.json',v)
   try:
    f,t,mp=lift(v['points']);footprint(v['points']);arr,mp=roles(v['points']);proj=project(np.stack([t,f],axis=1).reshape(-1,3));err=proj-arr;err[:,0]=(err[:,0]+512)%1024-512;row.update(roundtrip_error_px=float(abs(err).max()),endpoint_role_map_json=json.dumps(mp),within_pair_role_swaps=sum(i!=x for i,x in enumerate(mp))//2,max_pair_dx_px=float(abs((arr[::2,0]-arr[1::2,0]+512)%1024-512).max()))
    rawim,_=overlay(tex,v['points'],False);mapim,_=overlay(tex,v['points'],True);title(rawim,'Original indexed serialization (2D diagnostic only)').save(dest/f'{vid}_raw.jpg',quality=93);title(mapim,'Original IDs; role-resolved spherical edge projection').save(dest/f'{vid}_overlay.jpg',quality=93)
    top=title(render(tex,f,t,True),'Top; original adjacency; relative scale');ob=title(render(tex,f,t,False),'Oblique; triangle proxy; no Manhattan fitting');top.save(dest/f'{vid}_top.jpg',quality=93);ob.save(dest/f'{vid}_oblique.jpg',quality=93)
    panel=Image.new('RGB',(1024,1080),'white');panel.paste(mapim,(0,0));panel.paste(top,(0,530));panel.paste(ob,(520,530));panel.save(dest/f'{vid}_evidence.jpg',quality=92);row['render_status']='generated_not_reviewed'
   except Exception as e:row['render_status']='failed';row['failure']=type(e).__name__+': '+str(e);fail.append(row.copy())
   allvariants.append(row)
  cal.append(dict(case_id=cid,image_id=mid,phase='calibration',raw_image_downloaded=False,raw_image_from_pinned_studio=True,rendered_variants=sum(x['render_status']=='generated_not_reviewed' for x in allvariants if x['case_id']==cid),actually_viewed=False,completed_visual_review=False,reason='Render generation alone is not visual inspection; expansion is gated on actual calibration review.'))
 save('point_order_and_render_log.csv',allvariants);save('visual_completion_log.csv',cal);save('render_failures.csv',fail if fail else [dict(status='none')]);dump('RENDER_STATUS.json',dict(selected=len(selected),generated_variants=sum(x['render_status']=='generated_not_reviewed' for x in allvariants),failed_variants=len(fail),completed_visual_reviews=0,expansion_started=False))
 print(json.dumps({'selected':len(selected),'variants':len(allvariants),'failures':len(fail)},indent=2))
if __name__=='__main__':run()
