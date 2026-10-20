"""Two-arm overlays in ERP / BEV / inferred 3D, with exact crew captions."""
from __future__ import annotations
import argparse,hashlib,json,sys,textwrap
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'analysis/composition'))
import case_visuals as v
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from PIL import Image

COLORS=['#187D9D','#D07B27','#914A9E']

def member_figure(case,photo,out):
 members=case['members'];classes=sorted({x['class_id'] for x in members})
 cols=min(3,len(classes));rows=(len(classes)+cols-1)//cols;fh=5.5*rows+2.7
 fig=plt.figure(figsize=(4.5*cols,fh));bottom=2.55/fh
 grid=fig.add_gridspec(rows*2,cols,left=.065,right=.98,top=1-.9/fh,bottom=bottom,
  wspace=.27,hspace=.34,height_ratios=[1,1.6]*rows)
 ref=case['reference'];mg={x['worker_id']:v.viewer_geometry(x['points']) for x in members}
 bounds=v._bounds([v.viewer_geometry(ref['points_1024x512'],ref['floor_xz_h']),*mg.values()])
 palette=['#187D9D','#D07B27','#914A9E','#527858','#B75C68','#677F94']
 caption=[]
 for i,cls in enumerate(classes):
  subset=[x for x in members if x['class_id']==cls];color=palette[i%len(palette)];r,c=divmod(i,cols)
  ax=fig.add_subplot(grid[2*r,c]);v._erp_background(ax,photo)
  v._erp_edges(ax,ref['points_1024x512'],v.REF_ERP_COLOR,linewidth=1.1,reference=True)
  for x in subset:v._erp_edges(ax,x['points'],color,linewidth=.65,alpha=.22,markers=False)
  label=case.get('class_names',{}).get(cls,cls)
  if len(label)>24:label=cls
  old=sum(x['origin']=='v1' for x in subset)
  ax.set_title(label+f'  |  本例 {len(subset)} 人（旧 {old} / 新 {len(subset)-old}）',fontsize=9,color=color,pad=10)
  ax=fig.add_subplot(grid[2*r+1,c]);v._bev_ring(ax,ref['floor_xz_h'],v.REF_COLOR,reference=True,linewidth=1.3)
  for x in subset:v._bev_ring(ax,mg[x['worker_id']]['floor'],color,linewidth=.9,alpha=.25)
  v._style_bev(ax,bounds)
  caption.extend(textwrap.wrap(cls+' 成员：'+', '.join(x['worker_id'] for x in subset),width=115))
 fig.text(.065,1-.08/fh,case['case_id']+'｜类别成员叠图',fontsize=15,weight='bold',va='top')
 fig.text(.065,1-.45/fh,case['pool_id'].split('__')[0]+'；仅显示本案例所有团队的成员并集，每条细线是一人的冻结标注。',fontsize=9,color='#526474')
 caption+=textwrap.wrap('固定参考：'+ref['reference_id'],width=126)
 caption+=['BEV 参考为虚线，ERP 参考为黄色；各类别共享 BEV 坐标。未按当前图质量删去任何成员。']
 for i,line in enumerate(caption):fig.text(.065,(1.65-.175*i)/fh,line,fontsize=7.6,color='#40566b')
 fig.savefig(out,dpi=140,bbox_inches='tight',pad_inches=.08);plt.close(fig)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--cases',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
 ap.add_argument('--font',type=Path,required=True);a=ap.parse_args();v._configure_font(a.font);receipts=[]
 for path in sorted(a.cases.glob('S*.json')):
  case=json.loads(path.read_text());v._validate_members(case);folder=a.out/path.stem;folder.mkdir(parents=True,exist_ok=True)
  ref=case['reference'];rgeom=v.viewer_geometry(ref['points_1024x512'],ref['floor_xz_h'])
  bykey={t['team_key']:t for t in case['teams']};geoms={k:v.viewer_geometry(t['geometry'].get('points'),t['geometry'].get('footprint')) for k,t in bykey.items()}
  bounds=v._bounds([rgeom,*geoms.values()]);heights=v._heights([rgeom,*geoms.values()]);photo=None
  if case.get('image_path'):
   im=Path(case['image_path']);im=im if im.is_absolute() else path.parent/im
   if im.is_file():
    assert hashlib.sha256(im.read_bytes()).hexdigest()==case['image_sha256']
    photo=np.asarray(Image.open(im).convert('RGB'))
  frames=[]
  for i,e in enumerate([case['event']]+case.get('additional_events',[])):
   frames.append((f'paired_{i+1}',e,[(f'同构成 A / B  |  n={e["n"]}, m={e["m"]}',[(e['A_team_key'],0),(e['B_team_key'],1)]),
     (f'变构成 A / C  |  n={e["n"]}, m={e["m"]}',[(e['A_team_key'],0),(e['C_team_key'],2)])]))
  mechanism=case.get('mechanism')
  if mechanism:
   before,after=mechanism['team_before'],mechanism['team_after']
   frames.append(('threshold_overlay',case['event'],[(f'同一臂 n{mechanism["n_before"]} / n{mechanism["n_after"]}',[(before,0),(after,2)]),
    (f'增加后与固定参考  |  加入 {mechanism["added_worker"]}',[(after,2)])]))
  for basename,event,panels in frames:
   fig=plt.figure(figsize=(10.0,10.7))
   grid=fig.add_gridspec(3,2,left=.065,right=.98,top=.858,bottom=.195,hspace=.22,wspace=.16,height_ratios=[1.,1.32,1.35])
   for col,(title,arms) in enumerate(panels):
    ax=fig.add_subplot(grid[0,col]);v._erp_background(ax,photo)
    v._erp_edges(ax,ref['points_1024x512'],v.REF_ERP_COLOR,linewidth=1.0,reference=True)
    texts=[]
    for tk,c in arms:
     t=bykey[tk];v._erp_edges(ax,t['geometry']['points'],COLORS[c],linewidth=1.5,markers=False)
     q='NA' if t.get('B8L2') is None else f'{t["B8L2"]:.2f}'
     d='NA' if t.get('D10') is None else f'{t["D10"]:.2f}'
     texts.append(str(t['label'])+f': Q {q} / D {d} / 节点 {t["nodes"]}')
    ax.set_title(title+'\n'+'\n'.join(texts),fontsize=9.2,pad=8,color='#243547',linespacing=1.5)
    ax=fig.add_subplot(grid[1,col]);v._bev_ring(ax,ref['floor_xz_h'],v.REF_COLOR,reference=True,linewidth=1.2)
    for tk,c in arms:v._bev_ring(ax,geoms[tk]['floor'],COLORS[c],linewidth=1.7,zorder=7)
    v._style_bev(ax,bounds)
    ax=fig.add_subplot(grid[2,col],projection='3d');v._wire3d(ax,rgeom,v.REF_COLOR,reference=True)
    for tk,c in arms:v._wire3d(ax,geoms[tk],COLORS[c])
    v._style3d(ax,bounds,heights,case.get('view',{}))
   fig.text(.065,.98,case['title'],fontsize=15,color='#1B2B40',weight='bold',va='top')
   fig.text(.065,.947,case['pool_id'].split('__')[0]+'  |  '+case['method_id'],fontsize=8.6,color='#526474')
   reference_line='固定参考：'+ref['reference_id']
   for i,line in enumerate(textwrap.wrap(reference_line,width=124)):
    fig.text(.065,.925-i*.014,line,fontsize=7.2,color='#526474')
   handles=[Line2D([0],[0],color=v.REF_COLOR,ls='--',label='固定参考（ERP黄色）')]
   labels=[(0,'增加前'),(2,'增加后')] if basename=='threshold_overlay' else [(0,'A：基准构成'),(1,'B：同构成换人'),(2,'C：变构成换人')]
   for c,label in labels:handles.append(Line2D([0],[0],color=COLORS[c],label=label))
   fig.legend(handles=handles,loc='lower left',bbox_to_anchor=(.06,.163),ncol=4,frameon=False,fontsize=8)
   lines=[]
   if mechanism and basename=='threshold_overlay':
    for label,tk in [('增加前成员',mechanism['team_before']),('增加后成员',mechanism['team_after'])]:
     lines.extend(textwrap.wrap(label+'：'+', '.join(bykey[tk]['member_workers']),width=116))
    lines.append(f'门槛机制：新增 {mechanism["added_worker"]}；旧观测共簇关系未变，支持数不变而门槛升高的失选组数 = {mechanism["unchanged_support_loss_groups_n"]}。')
    lines.append('构成计数：增加前 '+str(bykey[mechanism['team_before']]['counts'])+'；增加后 '+str(bykey[mechanism['team_after']]['counts']))
   else:
    for label,key in [('共同成员','core_workers'),('A 块','outgoing_workers'),('B 块','within_incoming'),('C 块','cross_incoming')]:
     line=label+'：'+(', '.join(event[key]) if event.get(key) else '无（整队更换）')
     lines.extend(textwrap.wrap(line,width=116))
    lines+=['构成计数：A/B '+str(event['A_counts'])+'；C '+str(event['C_counts'])]
   for i,line in enumerate(lines):fig.text(.065,.146-i*.014,line,fontsize=7.2,color='#364657')
   fig.text(.065,.016,'三行依次为 ERP、BEV、3D；共享坐标。3D 按相机高度 1 从上下配对射线推断，并非测得实体体积。',fontsize=7.2,color='#536574')
   out=folder/(basename+'.png');fig.savefig(out,dpi=150,bbox_inches='tight',pad_inches=.08);plt.close(fig)
   receipts.append(dict(case_id=case['case_id'],figure=str(out),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),original_available=photo is not None,exact_members_in_caption=True))
  out=folder/'member_overlays.png';member_figure(case,photo,out)
  receipts.append(dict(case_id=case['case_id'],figure=str(out),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),original_available=photo is not None,exact_members_in_caption=True))
  print(path.stem,flush=True)
 (a.out/'OVERLAY_RENDER_RECEIPT.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
