"""Exact ERP + local crop + BEV display for supplied frozen observations.
No fusion/score computation or camera-to-camera registration is done here.
Usage: HOHONET_REPO=/path/repo python render_case.py case.json [--out-dir figures]
Case format: {case_id,title,note,views:[{image,image_id,photo,reference:{points_1024x512,floor_xz_h},
 records:[{worker_id,points,color,label}],teams:[{label,points,footprint,color,B8L2,D10,nodes}],
 zoom:[x0,x1,y0,y1],component_text:str}]}. Coordinates stay 1024x512.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from local_study_paths import WORK,CODE_ROOT,NATIVE,TAXONOMY,MECHANISMS,BUDGET,BUDGET_CASES,BUDGET_FINAL,FIGURES,ENGINE,REPO

from pathlib import Path
import os,json,argparse,importlib.util,sys
sys.path.insert(0,str(ENGINE/'deps'))
import numpy as np
from PIL import Image
R=REPO
s=importlib.util.spec_from_file_location('frozen_v',R/'research/workers/personnel_interchangeability_20261020/analysis/composition/case_visuals.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v)
font=Path(os.environ.get('HOHONET_FONT',MECHANISMS/'NotoSansCJKsc-Regular.otf'))
if font.exists():v._configure_font(font)
plt=v.plt

def draw(case,outdir):
 views=case['views'];fig=plt.figure(figsize=(18,5.8*len(views)))
 gs=fig.add_gridspec(len(views),3,width_ratios=[2.35,1,1.15],hspace=.46,wspace=.17)
 for i,view in enumerate(views):
  photo_path=Path(view['photo'])
  if not photo_path.exists():photo_path=Path(os.environ.get('HOHONET_PHOTOS',MECHANISMS/'photos'))/photo_path.name
  photo=np.asarray(Image.open(photo_path).convert('RGB'));ref=view['reference'];records=view.get('records',[]);teams=view.get('teams',[])
  ax=fig.add_subplot(gs[i,0]);v._erp_background(ax,photo)
  for x in records:v._erp_edges(ax,x['points'],x.get('color','#ffffff'),linewidth=x.get('linewidth',.7),alpha=x.get('alpha',.45))
  for x in teams:v._erp_edges(ax,x['points'],x.get('color','#00c9e8'),linewidth=1.8,markers=True)
  v._erp_edges(ax,ref['points_1024x512'],v.REF_ERP_COLOR,reference=True,linewidth=1.2,markers=True)
  ax.set_title(view['image']+' · '+view.get('subtitle','原图与原答／融合'),loc='left',fontsize=11)
  lines=[x.get('label',x.get('worker_id','')) for x in records if x.get('label')]+[x['label'] for x in teams]
  ax.text(0,-.055,'\n'.join(lines),transform=ax.transAxes,va='top',fontsize=8.7,color='#263445')
  zoom=fig.add_subplot(gs[i,1]);v._erp_background(zoom,photo,view.get('zoom'))
  for x in records:v._erp_edges(zoom,x['points'],x.get('color','#ffffff'),linewidth=x.get('linewidth',.9),alpha=x.get('alpha',.45))
  for x in teams:v._erp_edges(zoom,x['points'],x.get('color','#00c9e8'),linewidth=2.1,markers=True)
  v._erp_edges(zoom,ref['points_1024x512'],v.REF_ERP_COLOR,reference=True,linewidth=1.3,markers=True)
  zoom.set_title(view.get('zoom_title','视角内局部放大'),loc='left',fontsize=10)
  bx=fig.add_subplot(gs[i,2]);geos=[]
  for x in records:
   g=v.viewer_geometry(x['points']);geos.append(g);v._bev_ring(bx,g['floor'],x.get('color','#8596aa'),linewidth=x.get('linewidth',.8),alpha=x.get('alpha',.45))
  for x in teams:
   g=v.viewer_geometry(x['points'],x.get('footprint'));geos.append(g);v._bev_ring(bx,g['floor'],x.get('color','#00c9e8'),linewidth=2)
  rg=v.viewer_geometry(ref['points_1024x512'],ref.get('floor_xz_h'));geos.append(rg);v._bev_ring(bx,rg['floor'],'#111827',reference=True,linewidth=1.5)
  v._style_bev(bx,v._bounds(geos));bx.set_title('BEV：每图独立相机坐标，单位 h',fontsize=10)
  if view.get('component_text'):bx.text(0,-.22,view['component_text'],transform=bx.transAxes,va='top',fontsize=8.6)
 fig.suptitle(case['title'],fontsize=16,y=.985)
 fig.text(.5,.04,case.get('note',''),ha='center',fontsize=10,color='#263445')
 fig.text(.5,.018,'Release 原图；冻结处理后点序、参考与几何；参考在照片中为黄色、BEV中为黑虚线。视角间未做空间配准。',ha='center',fontsize=9,color='#4e6074')
 fig.subplots_adjust(top=.92,bottom=.17)
 outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
 path=outdir/(case['case_id']+'.png');fig.savefig(path,dpi=150);plt.close(fig);return path

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('case');p.add_argument('--out-dir',default=str(MECHANISMS/'figures'));a=p.parse_args();c=json.loads(Path(a.case).read_text());print(draw(c,a.out_dir))
