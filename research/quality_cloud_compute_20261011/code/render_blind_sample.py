"""Chinese compact review sheets: actual original + two overlays + equal-scale BEV/3D."""
import io,shutil
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from PIL import Image,ImageDraw,ImageFont
from common import read,save,sha
ROOT=Path(__file__).resolve().parents[1]
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
BOLD='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
FP=FontProperties(fname=FONT)
plt.rcParams.update({'font.family':FP.get_name(),'font.size':10,'axes.unicode_minus':False})
from matplotlib import font_manager
font_manager.fontManager.addfont(FONT)
COLORS=['#ff6900','#0099ff'];REF='#19c943'
def erp(xyz):
 p=np.asarray(xyz);r=np.hypot(p[:,0],p[:,2]);return np.column_stack([np.mod(np.arctan2(-p[:,0],p[:,2])/(2*np.pi),1),.5-np.arctan2(p[:,1],r)/np.pi])
def pano_lines(ax,g,color,floor_only=False):
 for key in ['bottom3d'] if floor_only else ['bottom3d','top3d']:
  loop=np.asarray(g[key])
  for i in range(len(loop)):
   uv=erp(loop[i]+np.linspace(0,1,161)[:,None]*(loop[(i+1)%len(loop)]-loop[i]));br=np.r_[0,np.flatnonzero(abs(np.diff(uv[:,0]))>.5)+1,len(uv)]
   for start,end in zip(br[:-1],br[1:]):
    if end-start>=2:ax.plot(uv[start:end,0],uv[start:end,1],color=color,lw=2)
 if not floor_only:
  for t,b in zip(g['top3d'],g['bottom3d']):
   uv=erp([t,b]);ax.plot(uv[:,0],uv[:,1],color=color,lw=1.7)
def bev(ax,g,color):
 x=np.asarray(g['bottom3d'])[:,[0,2]];x=np.vstack([x,x[0]]);ax.plot(x[:,0],x[:,1],color=color,lw=2);ax.scatter(x[:-1,0],x[:-1,1],s=12,color=color)
def wire(ax,g,color,floor_only=False):
 for key in ['bottom3d'] if floor_only else ['bottom3d','top3d']:
  x=np.asarray(g[key]);x=np.vstack([x,x[0]]);ax.plot(x[:,0],x[:,2],x[:,1],color=color,lw=2)
 if not floor_only:
  for b,t in zip(g['bottom3d'],g['top3d']):ax.plot([b[0],t[0]],[b[2],t[2]],[b[1],t[1]],color=color,lw=1.5)
def png(fig):
 b=io.BytesIO();fig.savefig(b,dpi=100);plt.close(fig);b.seek(0);return Image.open(b).convert('RGB')
def band(canvas,y,text,size=25):ImageDraw.Draw(canvas).text((16,y+5),text,font=ImageFont.truetype(BOLD,size),fill='#181818')
def select(options):return '<select><option value="">请选择</option>'+''.join('<option>'+v+'</option>' for v in options)+'</select>'
def main():
 cases=read(ROOT/'blind_sample/answer_mapping_private.json');geo=read(ROOT/'inputs/current_geometry_compact.json')['geometries'];confirmed=read(ROOT/'inputs/scope/normalized_confirmation_overlay.json')['records']
 user=ROOT/'blind_sample/user';user.mkdir(exist_ok=True);manifest=[]
 for c in cases:
  source=Path(c['photo_path'])
  if not source.exists():source=user/(c['case_id']+'_original.jpg')
  im=Image.open(source).convert('RGB');im.load();a=geo[c['object_1']];g=geo[c['reference_object_id']];cross=c['case_id']=='X01'
  if cross:
   conf=next(r for r in confirmed if r['image_code']==c['image_code']);B={'bottom3d':[[x,-1,z] for x,z in conf['polygon']]};items=[a,a];refs=[g,B]
  else:items=[a,geo[c['object_2']]];refs=[g,g]
  floor=np.vstack([np.asarray(z['bottom3d']) for z in items+refs]);lo=floor[:,[0,2]].min(axis=0);hi=floor[:,[0,2]].max(axis=0);center=(lo+hi)/2;span=max(hi-lo)*1.18
  all3=np.vstack([np.asarray(z[k]) for z in items+refs for k in ['bottom3d','top3d'] if k in z]);ctr=(all3.min(axis=0)+all3.max(axis=0))/2;span3=max(all3.max(axis=0)-all3.min(axis=0))*1.10
  canvas=Image.new('RGB',(1536,1836),'white');band(canvas,0,c['case_id']+'  历史材料｜原图（下图为两种比较视图）',28);canvas.paste(im.resize((1536,768)),(0,48))
  for j in range(2):
   annotation=items[j];reference=refs[j];color=COLORS[0] if cross else COLORS[j];only=cross and j==1
   label=('同一答案对空间'+('A' if j==0 else 'B（仅底面，顶界待定）')) if cross else f'答案{j+1} 与现有GT参考'
   ImageDraw.Draw(canvas).text((j*768+12,824),label,font=ImageFont.truetype(BOLD,23),fill='black')
   fig=plt.figure(figsize=(7.68,3.84));ax=fig.add_axes([0,0,1,1]);ax.imshow(im,extent=[0,1,1,0]);ax.set_aspect(.5);pano_lines(ax,reference,REF,only);pano_lines(ax,annotation,color);ax.set_axis_off();canvas.paste(png(fig),(j*768,864))
   ImageDraw.Draw(canvas).text((j*768+12,1254),'绿色：认可参考'+('B底面' if only else 'A / 当前GT')+'    '+('橙色：同一答案' if cross else ('橙色' if j==0 else '蓝色')+f'：答案{j+1}'),font=ImageFont.truetype(BOLD,21),fill='black')
   # Each comparison gets equally large BEV and 3D with a shared extent and view.
   for kind,xoff in [('bev',j*768),('3d',j*768+384)]:
    fig=plt.figure(figsize=(3.84,4.7))
    if kind=='bev':
     ax=fig.add_axes([.16,.12,.79,.80]);bev(ax,reference,REF);bev(ax,annotation,color);ax.set_xlim(center[0]-span/2,center[0]+span/2);ax.set_ylim(center[1]-span/2,center[1]+span/2);ax.set_aspect('equal');ax.scatter([0],[0],marker='+',color='black');ax.grid(alpha=.2);ax.set_xlabel('x / 相机高度');ax.set_ylabel('z / 相机高度');ax.set_title('俯视图 BEV｜两侧同尺度',fontproperties=FP)
    else:
     ax=fig.add_axes([.02,.08,.94,.87],projection='3d');wire(ax,reference,REF,only);wire(ax,annotation,color);ax.set_xlim(ctr[0]-span3/2,ctr[0]+span3/2);ax.set_ylim(ctr[2]-span3/2,ctr[2]+span3/2);ax.set_zlim(ctr[1]-span3/2,ctr[1]+span3/2);ax.set_box_aspect([1,1,1]);ax.view_init(elev=24,azim=-60);ax.set_title('3D｜两侧同尺度'+('（B仅底面）' if only else ''),fontproperties=FP);ax.set_xlabel('x/h');ax.set_ylabel('z/h');ax.set_zlabel('y/h');ax.tick_params(labelsize=8)
    canvas.paste(png(fig),(xoff,1296))
  band(canvas,1780,'X01只有一份答案；请选择空间匹配，B不提供完整3D质量。' if cross else '结合原图评价每份答案，再比较优劣；无法判断可保持不确定。',23)
  dest=user/(c['case_id']+'.jpg');canvas.save(dest,quality=94);raw=user/(c['case_id']+'_original.jpg')
  if source.resolve()!=raw.resolve():shutil.copyfile(source,raw)
  manifest.append({'case_id':c['case_id'],'rendered_path':'user/'+dest.name,'rendered_sha256':sha(dest),'original_path':'user/'+raw.name,'photo_sha256':sha(source),'photo_size':list(im.size),'render_size':list(canvas.size),'real_pixels_loaded':True,'B_top_created':False,'labels_contain_Q_worker_formula':False,'same_answer_both_panels':cross,'comparison_scales_shared':True});print(c['case_id'],dest.stat().st_size,flush=True)
 shutil.copyfile(ROOT/'blind_sample/user_response_blank.csv',user/'responses.csv')
 from build_review_receipt_page import write_review_page
 write_review_page(user,ROOT/'blind_sample/user_response_blank.csv')
 save(ROOT/'blind_sample/render_manifest.json',manifest)
if __name__=='__main__':main()
