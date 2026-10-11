"""Render approved annotations against fixed references; no alignment or fabricated B top."""
import argparse,hashlib,json,os,shutil
from pathlib import Path
import numpy as np
os.environ.setdefault('MPLCONFIGDIR','/tmp/quality_review30_mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.font_manager import FontProperties
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
font_manager.fontManager.addfont(FONT);FP=FontProperties(fname=FONT)
plt.rcParams.update({'font.family':FP.get_name(),'font.size':11,'axes.unicode_minus':False})
ANN='#ed6a05';A='#149341';B='#1978c9'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def erp(p):
 p=np.asarray(p);return np.column_stack((np.mod(np.arctan2(-p[:,0],p[:,2])/(2*np.pi),1),.5-np.arctan2(p[:,1],np.hypot(p[:,0],p[:,2]))/np.pi))
def pano(ax,g,color,floor_only=False):
 for key in ['bottom3d'] if floor_only else ['bottom3d','top3d']:
  loop=np.asarray(g[key]);t=np.linspace(0,1,161)[:,None]
  for i,p in enumerate(loop):
   uv=erp(p+t*(loop[(i+1)%len(loop)]-p));split=np.r_[0,np.flatnonzero(np.abs(np.diff(uv[:,0]))>.5)+1,len(uv)]
   for s,e in zip(split[:-1],split[1:]):
    if e-s>=2:ax.plot(uv[s:e,0],uv[s:e,1],color=color,lw=2)
  uv=erp(loop);ax.scatter(uv[:,0],uv[:,1],s=13,c=color,edgecolors='white',linewidths=.4)
 if not floor_only:
  for top,bottom in zip(g['top3d'],g['bottom3d']):
   uv=erp([top,bottom]);ax.plot(uv[:,0],uv[:,1],color=color,lw=1.4)
def bev(ax,g,color):
 p=np.asarray(g['bottom3d'])[:,[0,2]];q=np.vstack((p,p[0]));ax.plot(q[:,0],q[:,1],c=color,lw=2);ax.scatter(p[:,0],p[:,1],s=20,c=color)
def wire(ax,g,color,floor_only=False):
 for key in ['bottom3d'] if floor_only else ['bottom3d','top3d']:
  p=np.asarray(g[key]);q=np.vstack((p,p[0]));ax.plot(q[:,0],q[:,2],q[:,1],c=color,lw=2)
 if not floor_only:
  for top,bottom in zip(g['top3d'],g['bottom3d']):ax.plot([top[0],bottom[0]],[top[2],bottom[2]],[top[1],bottom[1]],c=color,lw=1.4)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--photo-root',type=Path,required=True);args=ap.parse_args();s=read(ROOT/'results/selection_private.json');g=read(ROOT/'results/selected_geometry_private.json');order=read(ROOT/'results/display_order.json');user=ROOT/'user';user.mkdir(exist_ok=True);geo=g['geometries'];items={};extents={}
 for r in s['records']:
  cid=r['case_id'];annotation=geo[r['object_id']];reference=geo[r['reference_object_id']];floor_only=r['case_type']=='single_floor_space_compatibility';objects=[(reference,A),(annotation,ANN)]
  if floor_only:
   assert r['AB_reference_ledger']['A_object_id']==r['reference_object_id'];b={'bottom3d':[[x,-1,z] for x,z in g['confirmed_B_floors_only'][cid]['polygon_XZ_h']]};assert 'top3d' not in b;objects=[(reference,A),(b,B),(annotation,ANN)]
  items[cid]=(r,objects,floor_only)
  # Same photo has identical BEV/3D extents even across separate case pages.
  pts=[np.asarray(obj[k]) for obj,_ in objects for k in (['bottom3d'] if floor_only else ['bottom3d','top3d'])];extents.setdefault(r['image_code'],[]).extend(pts)
 limits={}
 for image,arrays in extents.items():
  pts=np.vstack(arrays);lo=pts.min(axis=0);hi=pts.max(axis=0);center=(lo+hi)/2;span2=max(hi[[0,2]]-lo[[0,2]])*1.2;span3=max(hi-lo)*1.2;limits[image]=(center,span2,span3)
 manifest=[]
 for cid in order['primary_display_order']:
  r,objects,floor_only=items[cid];photo=args.photo_root/r['photo_source_asset_name'];assert sha(photo)==r['photo_sha256']
  with Image.open(photo) as image:image.load();im=image.convert('RGB');assert list(im.size)==r['photo_size']
  shutil.copyfile(photo,user/(cid+'_original.jpg'));files=[];center,span2,span3=limits[r['image_code']]
  # Original pixel aspect remains exactly 2:1; no panorama reprojection or resampling of geometry.
  fig=plt.figure(figsize=(15.36,7.68));ax=fig.add_axes([0,0,1,1]);ax.imshow(im,extent=[0,1,1,0]);ax.set_aspect(.5)
  for obj,col in objects:pano(ax,obj,col,floor_only)
  ax.set_xlim(0,1);ax.set_ylim(1,0);ax.set_axis_off();path=user/(cid+'_overlay.jpg');fig.savefig(path,dpi=100,format='jpg',pil_kwargs={'quality':93});plt.close(fig);files.append(path)
  fig,ax=plt.subplots(figsize=(7,7));fig.subplots_adjust(left=.13,right=.95,bottom=.12,top=.9)
  for obj,col in objects:bev(ax,obj,col)
  ax.set_xlim(center[0]-span2/2,center[0]+span2/2);ax.set_ylim(center[2]-span2/2,center[2]+span2/2);ax.set_aspect('equal');ax.grid(alpha=.2);ax.scatter(0,0,c='black',marker='+',s=80);ax.set_xlabel('x / 相机高度');ax.set_ylabel('z / 相机高度');ax.set_title('同尺度俯视图｜固定相机坐标',fontproperties=FP);path=user/(cid+'_bev.png');fig.savefig(path,dpi=120);plt.close(fig);files.append(path)
  fig=plt.figure(figsize=(7,7));ax=fig.add_subplot(projection='3d')
  for obj,col in objects:wire(ax,obj,col,floor_only)
  ax.set_xlim(center[0]-span3/2,center[0]+span3/2);ax.set_ylim(center[2]-span3/2,center[2]+span3/2);ax.set_zlim(center[1]-span3/2,center[1]+span3/2);ax.set_box_aspect([1,1,1]);ax.view_init(elev=24,azim=-60);ax.set_xlabel('x/h');ax.set_ylabel('z/h');ax.set_zlabel('y/h');ax.set_title('3D仅底面｜B顶界未确认' if floor_only else '同尺度3D｜现有完整参考',fontproperties=FP);path=user/(cid+'_3d.png');fig.savefig(path,dpi=120);plt.close(fig);files.append(path)
  files.insert(0,user/(cid+'_original.jpg'));manifest.append({'case_id':cid,'record_id_private':r['selection_private']['record_id'],'photo_sha256':r['photo_sha256'],'real_pixels_loaded':True,'case_type':r['case_type'],'B_top_created':False,'spatial_panels_floor_only':floor_only,'coordinate_alignment':'none; fixed camera height-normalized coordinates','limits_shared_for_same_photo':True,'center_xyz_h':center.tolist(),'BEV_span_h':float(span2),'3D_span_h':float(span3),'view':{'elev':24,'azim':-60},'files':[{'filename':p.name,'bytes':p.stat().st_size,'sha256':sha(p),'dimensions':list(Image.open(p).size)} for p in files]});print(cid,'rendered',flush=True)
 (ROOT/'results/render_manifest_private.json').write_text(json.dumps({'selection_sha256':sha(ROOT/'results/selection_private.json'),'display_order_sha256':sha(ROOT/'results/display_order.json'),'case_count':30,'image_count':120,'user_answers_prefilled':False,'quality_judgments_generated':False,'strict_Manhattan_wall_certification':False,'records':manifest},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
